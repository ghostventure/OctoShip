"""Persistent inactivity shield with Linux PAM verification; no stored passwords."""
import ctypes as C
import math
import os
import pwd
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk
from .core import OctoShipError
from .storage import load_json, save_json, state_root


class SessionState:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = path, clock
        self.mutex = threading.RLock()
        self.last = clock(); self.locked = False; self.error = ''
        if path.exists():
            try:
                value = load_json(path, 4096)
                if type(value['locked']) is not bool or type(value['last']) not in (int, float) or not math.isfinite(value['last']): raise ValueError()
                self.locked, self.last = value['locked'], value['last']
            except Exception: self.locked = True
        self.check(); self.save()

    def check(self):
        with self.mutex:
            now = self.clock()
            if now < self.last or now - self.last >= 1800: self.locked = True
            return self.locked

    def save(self):
        with self.mutex:
            try: save_json(self.path, {'locked':self.locked, 'last':self.last}); self.error = ''
            except Exception: self.error = 'Session state could not be saved. Restart persistence is unavailable.'

    def activity(self):
        with self.mutex:
            if not self.check(): self.last = self.clock()

    def lock(self):
        with self.mutex: self.locked = True; self.save()

    def verified(self, success):
        with self.mutex:
            if success is True: self.locked = False; self.last = self.clock(); self.save()

    def guard(self):
        if self.check(): raise OctoShipError('OctoShip is locked. Unlock, then review the operation before retrying.')


def verify_password(password):
    """Authenticate the process UID via system login PAM policy, then check account validity.

    PAM owns/frees successful conversation allocations. Python/Tk cannot promise
    complete erasure of transient password strings; none are logged or persisted.
    """
    if not password or '\0' in password: return False
    user = pwd.getpwuid(os.getuid()).pw_name.encode()
    class Message(C.Structure): _fields_ = [('style', C.c_int), ('message', C.c_char_p)]
    class Response(C.Structure): _fields_ = [('response', C.c_void_p), ('code', C.c_int)]
    callback_type = C.CFUNCTYPE(C.c_int, C.c_int, C.POINTER(C.POINTER(Message)), C.POINTER(C.POINTER(Response)), C.c_void_p)
    class Conversation(C.Structure): _fields_ = [('function', callback_type), ('data', C.c_void_p)]
    pam = C.CDLL('libpam.so.0'); libc = C.CDLL(None)
    libc.calloc.argtypes = [C.c_size_t, C.c_size_t]; libc.calloc.restype = C.c_void_p
    libc.strdup.argtypes = [C.c_char_p]; libc.strdup.restype = C.c_void_p
    libc.free.argtypes = [C.c_void_p]
    secret = password.encode()
    @callback_type
    def conversation(count, messages, response, data):
        if not 1 <= count <= 32: return 19
        allocated = libc.calloc(count, C.sizeof(Response))
        if not allocated: return 19
        answers = C.cast(allocated, C.POINTER(Response))
        ok = False
        try:
            for i in range(count):
                style = messages[i].contents.style
                if style in (1, 2):
                    answers[i].response = libc.strdup(secret if style == 1 else user)
                    if not answers[i].response: return 19
                elif style not in (3, 4): return 19
            response[0] = answers; ok = True; return 0
        finally:
            if not ok:
                for i in range(count):
                    if answers[i].response: libc.free(answers[i].response)
                libc.free(allocated)
    pam.pam_start.argtypes = [C.c_char_p, C.c_char_p, C.POINTER(Conversation), C.POINTER(C.c_void_p)]
    for name in ('pam_authenticate', 'pam_acct_mgmt', 'pam_end'):
        getattr(pam, name).argtypes = [C.c_void_p, C.c_int]
    pam.pam_get_item.argtypes = [C.c_void_p, C.c_int, C.POINTER(C.c_void_p)]
    handle = C.c_void_p(); conv = Conversation(conversation, None)
    status = pam.pam_start(b'login', user, C.byref(conv), C.byref(handle))
    if status: return False
    try:
        status = pam.pam_authenticate(handle, 1)  # PAM_DISALLOW_NULL_AUTHTOK
        if status: return False
        status = pam.pam_acct_mgmt(handle, 0)
        if status: return False
        actual = C.c_void_p()
        if pam.pam_get_item(handle, 2, C.byref(actual)) or not actual.value: return False  # PAM_USER
        return pwd.getpwnam(C.string_at(actual).decode()).pw_uid == os.getuid()
    finally:
        pam.pam_end(handle, status)
        secret = b''


class SessionController:
    def __init__(self, app, state=None, verifier=verify_password):
        self.app, self.root = app, app.root
        self.state = state or SessionState(state_root() / 'session.json')
        self.verifier = verifier; self.hidden = {}; self.window = None
        self.auth_result = None; self.authenticating = False; self.retry = 0
        self.last_save = time.monotonic(); self.stopped = threading.Event()
        self.desktop_locked = threading.Event()
        self.root.bind_all('<KeyPress>', self.activity, add='+')
        self.root.bind_all('<ButtonPress>', self.activity, add='+')
        self.root.bind_all('<Motion>', self.activity, add='+')
        self.root.bind_all('<Control-Shift-L>', lambda e: self.lock(), add='+')
        self.root.bind_all('<Control-Shift-l>', lambda e: self.lock(), add='+')
        self.root.bind_all('<Map>', lambda e: self.shield() if self.state.check() else None, add='+')
        self.timer = self.root.after(100, self.tick)
        threading.Thread(target=self.monitor_desktop, daemon=True).start()
        if self.state.check(): self.shield()

    def monitor_desktop(self):
        session = os.environ.get('XDG_SESSION_ID')
        if not session: return
        while not self.stopped.is_set():
            try:
                result = subprocess.run(['loginctl', 'show-session', session, '-p', 'LockedHint', '-p', 'Active'], capture_output=True, text=True, timeout=3)
                if result.returncode == 0 and ('LockedHint=yes' in result.stdout or 'Active=no' in result.stdout):
                    self.desktop_locked.set(); self.state.lock()
                else: self.desktop_locked.clear()
            except (OSError, subprocess.TimeoutExpired): pass
            self.stopped.wait(2)

    def activity(self, event=None):
        self.state.activity()
        if self.state.check(): self.shield()

    def lock(self):
        self.state.lock(); self.app.cancel.set(); self.shield()

    def shield(self):
        if self.window is None:
            self.previous_grab = str(self.root.tk.call('grab', 'current', self.root._w))
            win = tk.Toplevel(self.root); self.window = win
            win.title('Unlock OctoShip'); win.geometry('480x300'); win.protocol('WM_DELETE_WINDOW', lambda: None)
            ttk.Label(win, text='OctoShip is locked', style='Header.TLabel', padding=16).pack()
            ttk.Label(win, text='Unlock with your current Linux account password.\nPAM login policy must permit authentication.', padding=8).pack()
            self.password = ttk.Entry(win, show='•'); self.password.pack(fill='x', padx=24)
            self.password.bind('<Return>', lambda e: self.unlock())
            ttk.Button(win, text='Unlock with Linux account', command=self.unlock).pack(pady=8)
            self.status = tk.StringVar(value=self.state.error)
            ttk.Label(win, textvariable=self.status, wraplength=430).pack()
            ttk.Button(win, text='Close OctoShip', command=self.close_app).pack(pady=8)
            self.password.focus_set()
        # Tcl-created file/message dialogs have no Python widget object. Enumerate
        # Tcl paths directly so those dialogs are hidden and restored as well.
        def windows(path):
            for child in self.root.tk.splitlist(self.root.tk.call('winfo', 'children', path)):
                child = str(child)
                if str(self.root.tk.call('winfo', 'toplevel', child)) == child: yield child
                yield from windows(child)
        for path in [self.root._w, *windows(self.root._w)]:
            if path == self.window._w or path in self.hidden: continue
            state = self.root.tk.call('wm', 'state', path)
            title = self.root.tk.call('wm', 'title', path)
            self.hidden[path] = (state, title)
            self.root.tk.call('wm', 'title', path, 'OctoShip — Locked')
            self.root.tk.call('wm', 'withdraw', path)
        try: self.window.grab_set()
        except tk.TclError: pass

    def unlock(self):
        if self.authenticating or time.monotonic() < self.retry: return
        password = self.password.get(); self.password.delete(0, 'end')
        if not password: return
        self.authenticating = True; self.status.set('Verifying Linux account…')
        def work():
            try: success = self.verifier(password) is True
            except Exception: success = False
            self.auth_result = success
        threading.Thread(target=work, daemon=True).start()

    def tick(self):
        if self.auth_result is not None:
            success, self.auth_result = self.auth_result, None
            self.authenticating = False
            if success and not self.desktop_locked.is_set():
                self.state.verified(True)
                self.window.grab_release(); self.window.destroy(); self.window = None
                for path, (state, title) in self.hidden.items():
                    if self.root.tk.call('winfo', 'exists', path):
                        self.root.tk.call('wm', 'title', path, title)
                        if state != 'withdrawn': self.root.tk.call('wm', 'state', path, state)
                self.hidden.clear()
                if self.previous_grab and self.root.tk.call('winfo', 'exists', self.previous_grab):
                    self.root.tk.call('grab', 'set', self.previous_grab)
            else:
                self.retry = time.monotonic() + 5
                self.status.set('Authentication failed or desktop is locked. Workspace remains locked.')
        if self.state.check(): self.shield()
        if time.monotonic() - self.last_save >= 30:
            self.state.save(); self.last_save = time.monotonic()
            if self.state.error:
                if self.window is not None: self.status.set(self.state.error)
                else: self.app.record(self.state.error)
        self.timer = self.root.after(500, self.tick)

    def close_app(self):
        self.app.cancel.set(); self.app.busy = False; self.app.close()

    def close(self):
        self.stopped.set(); self.state.save(); self.root.after_cancel(self.timer)
