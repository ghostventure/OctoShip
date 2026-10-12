"""Actual Tk controls, explicit confirmations, and locked callbacks; offline fixtures."""
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch
from test_shipping import ShippingAPI
from octoship.app import App
from octoship.session import SessionController, SessionState


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class ShippingGUI(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.path=Path(self.tmp.name)
        self.project=self.path/'project'; self.project.mkdir(); (self.project/'hello.txt').write_text('Hello\n')
        env=patch.dict(os.environ,{'XDG_STATE_HOME':str(self.path/'state'),'XDG_SESSION_ID':''}); env.start(); self.addCleanup(env.stop)
        self.root=tk.Tk(); self.app=App(self.root); self.api=ShippingAPI(); self.app.api=self.api
        self.app.repo.set('owner/project'); self.app.branch.set('main'); self.panel=self.app.workbench; self.panel.folder.set(str(self.project))
        self.errors=[]
        for name in ('showerror','showinfo','showwarning'):
            mock=patch('tkinter.messagebox.'+name,side_effect=lambda *a,**kw:self.errors.append(a)); mock.start(); self.addCleanup(mock.stop)
        yes=patch('tkinter.messagebox.askyesno',return_value=True); yes.start(); self.addCleanup(yes.stop)
        self.root.update()
    def tearDown(self):
        # Reclaim destroyed Tk variables on the UI thread before the next worker.
        import gc
        self.app.close()
        del self.panel, self.app, self.root
        gc.collect()
    def wait(self,predicate=None):
        deadline=time.monotonic()+6
        while (predicate() if predicate else self.app.busy) and time.monotonic()<deadline:
            self.root.update(); time.sleep(.02)
        self.root.update()
        self.assertFalse(predicate() if predicate else self.app.busy)
    def button(self,text): return next(w for w in descendants(self.root) if isinstance(w,ttk.Button) and w.cget('text')==text)
    def test_shipping_controls_review_then_ship(self):
        self.panel.new_branch.set('ship/gui'); self.panel.title.set('GUI shipping')
        self.panel.review_ship(); self.wait(); self.assertFalse(self.api.writes)
        self.panel.publish_ship(); self.wait()
        self.assertIn('Verified:',self.panel.ship_report.get('1.0','end')); self.assertFalse(self.errors)
    def test_preparation_controls_review_and_explicit_publish(self):
        self.panel.map_project(); self.wait(); self.assertEqual(len(self.panel.mapping.get_children()),1)
        self.panel.review_preparation(); self.wait(); self.assertFalse(self.api.writes)
        self.button('Publish reviewed files').invoke(); self.wait()
        self.assertIn('/commit/',self.panel.prep_report.get('1.0','end')); self.assertFalse(self.errors)
    def test_lock_hides_child_windows_and_defers_completed_callbacks(self):
        child=tk.Toplevel(self.root); child.title('Sensitive filename'); ttk.Label(child,text='private content').pack(); self.root.update()
        state=SessionState(self.path/'session.json')
        self.app.session=SessionController(self.app,state,verifier=lambda password:password=='fixture password')
        self.api.guard=state.guard
        self.app.session.lock(); self.root.update()
        self.assertEqual(self.root.state(),'withdrawn'); self.assertEqual(child.state(),'withdrawn'); self.assertEqual(child.title(),'OctoShip — Locked')
        called=[]; self.app.events.put(('done',lambda result:called.append(result),'done')); self.root.after_cancel(self.app.drain_timer); self.app.drain()
        self.assertFalse(called)
        session=self.app.session; session.password.insert(0,'wrong'); session.unlock()
        self.wait(lambda:session.authenticating)
        self.assertTrue(state.check()); self.assertFalse(called)
        session.retry=0; session.password.insert(0,'fixture password'); session.unlock()
        self.wait(lambda:state.check()); self.wait(lambda:not called)
        self.assertEqual(child.title(),'Sensitive filename'); self.assertEqual(self.root.state(),'normal')
        child.destroy()
    def test_tcl_native_dialog_is_masked_and_restored(self):
        # A Tcl-only top level matches native Tk file dialogs, which have no
        # corresponding Python object and cannot be found via winfo_children().
        self.root.tk.call('toplevel', '.native_dialog')
        self.root.tk.call('wm', 'title', '.native_dialog', 'Private project folder')
        self.root.tk.call('grab', 'set', '.native_dialog')
        self.root.update()
        state=SessionState(self.path/'session.json')
        self.app.session=SessionController(self.app,state,verifier=lambda password:True)
        self.app.session.lock(); self.root.update()
        self.assertEqual(self.root.tk.call('wm','state','.native_dialog'),'withdrawn')
        self.assertEqual(self.root.tk.call('wm','title','.native_dialog'),'OctoShip — Locked')
        self.app.session.password.insert(0,'fixture'); self.app.session.unlock()
        self.wait(lambda:state.check())
        self.assertEqual(self.root.tk.call('wm','state','.native_dialog'),'normal')
        self.assertEqual(self.root.tk.call('wm','title','.native_dialog'),'Private project folder')
        self.assertEqual(str(self.root.tk.call('grab','current',self.root._w)),'.native_dialog')
        self.root.tk.call('destroy','.native_dialog')

    def test_privacy_preferences_do_not_save_workspace_paths(self):
        self.panel.privacy.set(True); self.panel.save_preferences()
        text=(self.path/'state/octoship/preferences.json').read_text()
        self.assertNotIn(str(self.project),text); self.assertNotIn('owner/project',text)
    def test_all_new_tabs_render_and_controls_fit(self):
        self.app.notebook.select(2)
        for size, text_size in (('1000x760',12),('1180x860',12),('1000x760',18)):
            self.panel.size.set(text_size); self.panel.apply_display()
            self.root.geometry(size); self.root.update()
            for index in range(5):
                self.panel.tabs.select(index); self.root.update()
                for w in descendants(self.panel.tabs.nametowidget(self.panel.tabs.tabs()[index])):
                    if isinstance(w,ttk.Button) and w.winfo_viewable():
                        self.assertLessEqual(w.winfo_rootx()+w.winfo_width(),self.root.winfo_rootx()+self.root.winfo_width(),w.cget('text'))
                        # Every button is in the scroll region, including at 18-point size.
                        canvas = self.panel.viewports[index]
                        self.assertLessEqual(w.winfo_rooty()+w.winfo_height()-canvas.winfo_rooty(),float(canvas.cget('scrollregion').split()[3])+2,w.cget('text'))
        self.assertFalse(self.api.calls); self.assertFalse(self.api.writes)


if __name__=='__main__': unittest.main(verbosity=2)
