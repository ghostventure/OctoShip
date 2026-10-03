"""Exercise the actual review/confirm/upload GUI against a local HTTP fixture."""
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
from test_core import LocalGitHub
from octoship.app import App


def wait(root, app):
    deadline = time.monotonic() + 10
    while app.busy and time.monotonic() < deadline:
        root.update()
        time.sleep(.02)
    root.update()
    assert not app.busy, 'GUI operation timed out'


def buttons(widget):
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button):
            yield child
        yield from buttons(child)


fixture = LocalGitHub()
try:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / 'demo.txt'
        path.write_text('GUI upload integration test\n')
        root = tk.Tk()
        app = App(root)
        app.api = fixture.api
        app.repo.set('owner/project')
        app.branch.set('feature/test')
        app.show_files([path])
        app.tree.selection_set('0')
        app.review()
        wait(root, app)
        assert not fixture.writes, 'Review must not upload'
        confirm = [button for button in buttons(root) if button.cget('text') == 'Upload these files']
        assert len(confirm) == 1, 'Review confirmation missing'
        confirm[0].invoke()
        wait(root, app)
        assert fixture.files['demo.txt'][0] == path.read_bytes()
        assert app.status.get() == '1 uploaded, 0 failed.'
        assert len(fixture.writes) == 1
        root.destroy()
        print('PASS: native GUI review, explicit confirm, real HTTP upload, result status (loopback only).')
finally:
    fixture.close()
