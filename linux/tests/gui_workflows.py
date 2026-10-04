"""Native GUI component checks under Xvfb; all GitHub operations use a fixture."""
from pathlib import Path
import subprocess
import tempfile
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch
from test_workflows import FakeGitHub, HEAD, NEW
from octoship.app import App
from octoship.queue_store import QueueStore


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class GuiWorkflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'example.txt'; self.path.write_text('example content')
        self.root = tk.Tk()
        self.app = App(self.root, QueueStore(Path(self.temp.name) / 'queues'))
        self.api = FakeGitHub(); self.app.api = self.api
        self.app.repo.set('owner/project'); self.app.branch.set('feature/test')
        self.errors = []
        for name in ('showerror', 'showwarning', 'showinfo'):
            mock = patch('tkinter.messagebox.' + name, side_effect=lambda *args, **kw: self.errors.append(args))
            mock.start(); self.addCleanup(mock.stop)
        yes = patch('tkinter.messagebox.askyesno', return_value=True); yes.start(); self.addCleanup(yes.stop)
        self.root.update()

    def tearDown(self):
        self.app.close()

    def wait(self):
        deadline = time.monotonic() + 8
        while self.app.busy and time.monotonic() < deadline:
            self.root.update(); time.sleep(.02)
        self.root.update()
        self.assertFalse(self.app.busy, 'GUI operation timed out')

    def button(self, text):
        return next(w for w in descendants(self.root) if isinstance(w, ttk.Button) and w.cget('text') == text)

    def review(self):
        self.app.show_files([self.path]); self.app.tree.selection_set('0')
        self.app.review(); self.wait()

    def test_tabs_render_without_remote_calls(self):
        self.assertEqual(self.api.calls, [])
        for size in ('1000x760', '1180x860'):
            self.root.geometry(size); self.root.update()
            for index in range(4):
                self.app.notebook.select(1); self.app.tools.tabs.select(index); self.root.update()
            self.assertTrue(self.app.tools.publish_button.winfo_viewable())
            self.assertLess(self.app.tools.publish_button.winfo_rooty() + self.app.tools.publish_button.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())
            self.app.notebook.select(0); self.root.update()
            self.assertGreater(self.app.tree.winfo_height(), 50)
            button = self.button('Review upload…')
            self.assertTrue(button.winfo_viewable())
            self.assertLess(button.winfo_rooty() + button.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())
        self.assertEqual(self.api.calls, [])
        output = Path('/tmp/octoship-linux-1.6-upload.png')
        subprocess.run(['import', '-window', str(self.root.winfo_id()), str(output)], check=True)
        self.app.notebook.select(1); self.app.tools.tabs.select(3); self.root.update()
        subprocess.run(['import', '-window', str(self.root.winfo_id()), '/tmp/octoship-linux-1.6-tools.png'], check=True)

    def test_atomic_review_confirmation_and_persisted_success(self):
        self.app.remember.set(True)
        self.review(); self.assertEqual(self.api.writes, [])
        self.button('Upload these files').invoke(); self.wait()
        self.assertEqual(self.api.current, NEW)
        self.assertEqual(self.app.status.get(), '1 uploaded, 0 failed.')
        snapshot = self.app.queue_store.load('owner/project', 'feature/test')
        self.assertEqual(snapshot['entries'][0]['status'], 'uploaded')
        self.assertEqual(self.errors, [])

    def test_secret_confirmation_and_resume_requires_fresh_review(self):
        self.path.write_text('ghp_' + 'x' * 30)
        self.review()
        upload = self.button('Upload these files'); self.assertTrue(upload.instate(['disabled']))
        upload.invoke(); self.assertEqual(self.api.writes, [])
        ack = next(w for w in descendants(self.root) if isinstance(w, ttk.Checkbutton) and w.cget('text').startswith('I reviewed'))
        ack.invoke(); self.assertFalse(upload.instate(['disabled']))
        self.button('Back').invoke()
        from octoship.core import plan_upload
        items = plan_upload(self.api, 'owner/project', 'feature/test', [self.path], target_ref=HEAD)[1]
        snapshot = self.app.queue_store.snapshot('owner/project', 'feature/test', 'atomic', 'message', items)
        self.app.queue_store.save(snapshot)
        self.app.resume_queue(); self.wait()
        self.assertEqual(self.api.writes, [])
        self.app.review(); self.wait()
        self.assertTrue(self.button('Upload these files').instate(['disabled']))

    def test_compare_branch_and_pr_controls(self):
        tools = self.app.tools
        tools.local.set(str(self.path.parent)); tools.compare(); self.wait()
        self.assertIn('Local only', tools.comparison.get('1.0', 'end'))
        tools.new_branch.set('feature/new'); tools.branch(); self.wait()
        self.assertTrue(any(body == {'ref': 'refs/heads/feature/new', 'sha': HEAD} for _, _, body in self.api.writes))
        tools.pr_title.set('Test PR'); tools.pull_request(); self.wait()
        self.assertTrue(self.app.last_url.endswith('/pull/1'))
        self.assertEqual(self.errors, [])

    def test_draft_asset_review_and_separate_publish(self):
        tools = self.app.tools
        self.assertTrue(tools.publish_button.instate(['disabled']))
        tools.tag.set('v1.6.0'); tools.release_title.set('Linux update'); tools.create_release(); self.wait()
        self.assertTrue(self.api.release['draft'])
        with patch('tkinter.filedialog.askopenfilenames', return_value=[str(self.path)]):
            tools.attach_assets(); self.wait()
        self.assertEqual(self.api.assets, [])
        self.button('Upload reviewed assets').invoke(); self.wait()
        self.assertEqual(self.api.assets[0][1], self.path.read_bytes())
        self.assertTrue(self.api.release['draft'])
        tools.publish(); self.wait()
        self.assertFalse(self.api.release['draft'])
        self.assertTrue(tools.publish_button.instate(['disabled']))
        self.assertEqual(self.errors, [])

    def test_declined_remote_actions_make_no_writes(self):
        tools = self.app.tools
        with patch('tkinter.messagebox.askyesno', return_value=False):
            tools.tag.set('v1'); tools.create_release()
            tools.pr_title.set('PR'); tools.pull_request()
            tools.new_branch.set('feature/no'); tools.branch(); self.wait()
        self.assertEqual(self.api.writes, [])

    def test_failed_asset_keeps_publish_disabled(self):
        tools = self.app.tools; tools.tag.set('v1'); tools.create_release(); self.wait()
        with patch('tkinter.filedialog.askopenfilenames', return_value=[str(self.path)]):
            tools.attach_assets(); self.wait()
        from octoship.core import OctoShipError
        with patch.object(self.api, 'asset_request', side_effect=OctoShipError('Lost response')):
            self.button('Upload reviewed assets').invoke(); self.wait()
        self.assertTrue(tools.publish_button.instate(['disabled']))
        tools.publish()
        self.assertTrue(self.api.release['draft'])

    def test_per_file_pause_cancel_and_saved_pending_rows(self):
        from octoship.core import plan_upload
        second = self.path.parent / 'second.txt'; second.write_text('second file')
        items = plan_upload(self.api, 'owner/project', 'feature/test', [self.path, second])[1]
        calls = []
        def upload(*args):
            calls.append(args)
            self.app.pause.set()
            return {'content': {'html_url': 'https://github.com/owner/project'}}
        with patch.object(self.api, 'upload', side_effect=upload):
            self.app.upload(self.api, 'owner/project', 'feature/test', items, 'message', remember=True)
            deadline = time.monotonic() + 3
            while not calls and time.monotonic() < deadline:
                self.root.update(); time.sleep(.02)
            self.assertEqual(len(calls), 1)
            time.sleep(.15); self.root.update()
            self.assertEqual(len(calls), 1)
            self.app.cancel.set(); self.wait()
        snapshot = self.app.queue_store.load('owner/project', 'feature/test')
        self.assertEqual([r['status'] for r in snapshot['entries']], ['uploaded', 'pending'])
        self.app.resume_queue(); self.wait()
        self.assertEqual(self.app.files, [second])

    def test_release_cannot_follow_changed_repository(self):
        tools = self.app.tools; tools.tag.set('v1'); tools.create_release(); self.wait()
        before = len(self.api.writes)
        self.app.repo.set('someone/else'); tools.publish()
        self.assertEqual(len(self.api.writes), before)
        self.assertTrue(self.api.release['draft'])


if __name__ == '__main__': unittest.main(verbosity=2)
