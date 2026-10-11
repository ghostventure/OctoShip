"""Regression checks for the Windows October 11 feature port (no live mutations)."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship import inspection as inspect, preparation as prep, workbench as ship, workflows as flow
from octoship.core import OctoShipError, GitHub, ApiError
from octoship.session import SessionState, verify_password
from octoship.storage import save_json, load_json
from test_workflows import FakeGitHub, HEAD, NEW, CHANGED, blob_sha


class ShippingAPI(FakeGitHub):
    def __init__(self):
        super().__init__(); self.login = 'octocat'; self.visibility = 'private'; self.sent_tree = []; self.lost_response = False
        self.downloads = {}; self.releases = []; self.branch_names = set()
    def request(self, path, method='GET', body=None):
        if path == '/user': return {'login':self.login,'name':'Example','email':None}
        if path == '/repos/owner/project': return {'visibility':self.visibility,'permissions':{'push':True}}
        if '/contents/' in path and method == 'GET':
            value = super().request(path,method,body)
            entry = path.split('/contents/')[1].split('?')[0]
            data = self.downloads.get(entry,b'baseline\n')
            value.update(encoding='base64',content=base64.b64encode(data).decode(),size=len(data)); return value
        if path.endswith('/git/trees') and method == 'POST': self.sent_tree = body['tree']
        if path.endswith('/git/refs') and method == 'POST':
            if body['ref'] in self.branch_names: raise ApiError(422)
            self.branch_names.add(body['ref'])
        if '/git/refs/heads/' in path and method == 'PATCH':
            result = super().request(path,method,body)
            for entry in self.sent_tree: self.entries[entry['path']] = entry
            if self.lost_response: raise OctoShipError('Lost response')
            return result
        if path.endswith('/releases?per_page=100'): return self.releases
        if '/rules/' in path or '/protection' in path or '/pages' in path: raise ApiError(404)
        return super().request(path,method,body)
    def download_digest(self, path, cancel=None):
        data = self.downloads[path.rsplit('/',1)[-1]]
        return len(data),hashlib.sha256(data).hexdigest()
    def public_download_status(self,url): return 'Anonymous link inaccessible: HTTP 404'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.project = self.root / 'project'; self.project.mkdir()
        self.api = ShippingAPI()
        env = patch.dict(os.environ, {'XDG_STATE_HOME':str(self.root/'state')}); env.start(); self.addCleanup(env.stop)
    def file(self,name='hello.txt',data=b'hello\n'):
        p = self.project / name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data); return p
    def review(self): return ship.review_project(self.api,'owner/project','main',self.project)
    def plan(self): return prep.map_project(self.project,'owner/project','main')


class ShippingTests(Fixture):
    def test_ship_skips_same_and_verifies_immutable_commit_and_draft(self):
        self.file('same.txt',b'same'); self.file(); self.api.entry('same.txt',b'same')
        review = self.review(); self.assertEqual(len(review.items),1)
        result = ship.ship_project(self.api,review,'ship/test','Ship test')
        self.assertIn('Verified:',result['verification']); self.assertTrue(result['pull_request'])
        pr = next(b for m,p,b in self.api.writes if p.endswith('/pulls'))
        self.assertTrue(pr['draft']); self.assertEqual(pr['base'],'main')
    def test_changed_bytes_head_account_visibility_stop_before_branch(self):
        for change in ('bytes','head','account','visibility'):
            self.api = ShippingAPI(); path = self.file(); review = self.review()
            if change == 'bytes': path.write_bytes(b'changed')
            if change == 'head': self.api.current = CHANGED
            if change == 'account': self.api.login = 'other'
            if change == 'visibility': self.api.visibility = 'public'
            with self.assertRaises(OctoShipError): ship.ship_project(self.api,review,'ship/test','Ship test')
            self.assertFalse(self.api.writes)
    def test_secrets_links_duplicates_and_oversized_batch_block(self):
        path = self.file(data=b'ghp_' + b'x'*30)
        with self.assertRaises(OctoShipError): self.review()
        path.unlink(); path.symlink_to(self.root/'outside')
        with self.assertRaises(OctoShipError): self.review()
        path.unlink()
        for i in range(101): self.file(f'{i}.txt')
        with self.assertRaises(OctoShipError): self.review()
    def test_exclusions_prune_folders(self):
        self.file(); self.file('dist/large.txt'); self.file('node_modules/a.txt')
        review = ship.review_project(self.api,'owner/project','main',self.project,exclusions=['dist/*'])
        self.assertEqual([i.destination for i in review.items],['hello.txt'])
    def test_possible_move_is_suggestion_only(self):
        self.file('new.txt',b'moved'); self.api.entry('old.txt',b'moved')
        review = self.review()
        self.assertTrue(any('Possible move' in status for _,status in review.rows))
        ship.ship_project(self.api,review,'ship/move','Move candidate')
        self.assertIn('old.txt',self.api.entries)
    def test_existing_branch_failure_identifies_recovery(self):
        self.file(); review=self.review(); self.api.branch_names.add('refs/heads/ship/test')
        with self.assertRaisesRegex(OctoShipError,'Inspect branch ship/test'): ship.ship_project(self.api,review,'ship/test','Ship')
        self.assertFalse(self.api.writes)
    def test_verification_mismatch_and_unknown(self):
        self.file(); review=self.review()
        self.assertTrue(ship.verify_commit(self.api,review.repo,HEAD,review.items).startswith('Mismatch'))
        self.api.truncated=True
        self.assertTrue(ship.verify_commit(self.api,review.repo,HEAD,review.items).startswith('Could not verify'))
    def test_lost_patch_response_reconciles_without_retry(self):
        self.file(); review=self.review(); self.api.lost_response=True
        result=flow.atomic_upload(self.api,review.repo,review.branch,review.items,'Test',HEAD)
        self.assertTrue(result.endswith(NEW))
        self.assertEqual(len([m for m,_,_ in self.api.writes if m=='PATCH']),1)
    def test_descendant_reconciliation_and_unknown(self):
        self.file(); review=self.review(); original=self.api.request
        def request(path,method='GET',body=None):
            if method=='PATCH': self.api.current=CHANGED; raise OctoShipError('Lost')
            if '/compare/' in path: return {'status':'ahead','merge_base_commit':{'sha':NEW}}
            return original(path,method,body)
        self.api.request=request
        self.assertTrue(flow.atomic_upload(self.api,review.repo,review.branch,review.items,'Test',HEAD).endswith(NEW))
        self.api = ShippingAPI(); self.api.fail_patch=True; review=self.review()
        with self.assertRaisesRegex(OctoShipError,'not confirmed'): flow.atomic_upload(self.api,review.repo,review.branch,review.items,'Test',HEAD)
    def test_recipes_cannot_include_local_paths_or_credentials(self):
        valid={'version':1,'repository':'owner/project','branch':'main','destination':'docs','exclusions':['dist/*'],'release_name':'v{version}'}
        self.assertEqual(ship.recipe(valid),valid)
        for extra in ({'root':'/home/example'},{'destination':'../escape'},{'exclusions':['/tmp/*']},{'release_name':'ghp_'+'x'*30}):
            with self.assertRaises(OctoShipError): ship.recipe(dict(valid,**extra))
    def test_diagnostics_do_not_call_unknown_endpoints_clear(self):
        result=ship.diagnostics(self.api,'owner/project','main')
        self.assertIn('Unknown',result['rules']); self.assertEqual(result['account']['login'],'octocat')
        self.assertFalse(self.api.writes)
    def test_channel_selects_stable_or_prerelease(self):
        self.api.releases=[{'tag_name':'v2-beta','prerelease':True,'assets':[{'name':'preview.run'}]}, {'tag_name':'v1','prerelease':False,'assets':[{'name':'stable.run'}]}]
        result=ship.release_channel(self.api,'owner/project',False,'v1','stable.run')
        self.assertTrue(result['expected_tag_matches']); self.assertTrue(result['expected_asset_present'])
    def test_draft_recovery_preserves_mismatches_and_never_publishes(self):
        path=self.file(); digest=hashlib.sha256(path.read_bytes()).hexdigest()
        self.api.release={'id':42,'draft':True,'assets':[{'id':100,'name':path.name,'size':3}]}
        self.api.downloads['100']=b'old'
        rows=ship.recover_assets(self.api,'owner/project',42,[(path,digest)],True)
        self.assertIn('Mismatch',rows[0][1]); self.assertFalse(self.api.assets); self.assertFalse(self.api.writes)
        self.api.release['assets']=[]
        ship.recover_assets(self.api,'owner/project',42,[(path,digest)],True)
        self.assertEqual(len(self.api.assets),1); self.assertTrue(self.api.release['draft'])
    def test_release_tester_separates_digest_size_and_public_access(self):
        self.api.release={'id':42,'draft':True,'assets':[{'id':100,'name':'asset','size':3}]}; self.api.downloads['100']=b'abc'
        rows=ship.test_release(self.api,'owner/project',42)
        self.assertIn('unverified',rows[0][1]); self.assertIn('404',rows[0][2])
        rows=ship.test_release(self.api,'owner/project',42,{'asset':hashlib.sha256(b'abc').hexdigest(),'missing':'x'})
        self.assertEqual(rows[0][1],'Verified'); self.assertEqual(rows[1][1],'Missing asset')


class PreparationTests(Fixture):
    def test_offline_plan_roundtrip_and_private_permissions(self):
        self.file(); plan=self.plan(); path=self.root/'plan.json'; save_json(path,plan)
        self.assertEqual(prep.validate_plan(load_json(path)),plan); self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertFalse(self.api.calls)
    def test_binding_and_visibility_rechecked_at_publish(self):
        self.file(); plan=self.plan(); prep.bind_project(self.api,plan)
        review=prep.review(self.api,plan); self.api.visibility='public'
        with self.assertRaisesRegex(OctoShipError,'visibility changed'): prep.publish(self.api,review,'Publish')
        self.api.login='other'
        with self.assertRaisesRegex(OctoShipError,'binding'): prep.review(self.api,plan)
        self.assertFalse(self.api.writes)
    def test_empty_folder_placeholder_does_not_write_source(self):
        self.file(); plan=self.plan(); empty=self.project/'empty'; empty.mkdir()
        result=prep.placeholder(plan,empty,'empty/.gitkeep')
        self.assertEqual(list(empty.iterdir()),[]); self.assertEqual(Path(result['files'][-1]['source']).read_bytes(),b'')
    def test_selective_preserves_line_endings_and_reconstructs_random_inputs(self):
        before=b'a\r\nb\r\nc\n'; after=b'A\r\nb\r\nC\n'
        lines,changes=inspect.selective_changes(before,after)
        self.assertEqual(inspect.apply_changes(lines,changes,{0}),b'A\r\nb\r\nc\n')
        rng=random.Random(9)
        for _ in range(100):
            a=''.join(rng.choice(['a\n','b\r\n','c\n']) for _ in range(20)).encode()
            b=''.join(rng.choice(['a\n','b\r\n','c\n']) for _ in range(20)).encode()
            lines,changes=inspect.selective_changes(a,b)
            self.assertEqual(inspect.apply_changes(lines,changes,set()),a)
            self.assertEqual(inspect.apply_changes(lines,changes,set(range(len(changes)))),b)
    def test_selective_rejects_stale_head_and_changed_destination(self):
        self.file(data=b'changed\n'); self.api.entry('hello.txt',b'baseline\n'); plan=self.plan()
        value=prep.selective_baseline(self.api,plan,plan['files'][0])
        self.api.current=CHANGED
        with self.assertRaisesRegex(OctoShipError,'baseline'): prep.review(self.api,plan,value)
        self.api.current=HEAD; changed=copy.deepcopy(plan); changed['files'][0]['destination']='other.txt'
        with self.assertRaisesRegex(OctoShipError,'destination'): prep.review(self.api,changed,value)
    def test_plan_rejects_traversal_duplicate_and_unknown_fields(self):
        self.file(); plan=self.plan()
        for modified in (dict(plan,token='fixture'),dict(plan,files=plan['files']*2),dict(plan,files=[{'source':'relative','destination':'../bad'}])):
            with self.assertRaises(OctoShipError): prep.validate_plan(modified)


class InspectionTests(Fixture):
    def test_zip_scans_without_extraction_and_flags_unsafe_names(self):
        path=self.root/'archive.zip'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('../escape.txt','x'); z.writestr('.env','x'); z.writestr('safe.txt','ghp_'+'x'*30); z.writestr('big.bin',b'x'*(512*1024+1))
        rows=dict(inspect.inspect_zip(path))
        self.assertIn('UNSAFE',rows['../escape.txt']); self.assertIn('UNSAFE',rows['.env']); self.assertIn('GitHub token',rows['safe.txt']); self.assertIn('Not scanned',rows['big.bin'])
        self.assertFalse((self.root/'escape.txt').exists())
    def test_markdown_version_and_lfs_findings(self):
        self.file('Readme.md',b'[wrong](readme.md) [missing](missing.txt) [outside](../outside.md)')
        self.file('package.json',b'{"version":"1.0.0"}'); self.file('.gitattributes',b'*.zip filter=lfs diff=lfs merge=lfs -text')
        text=json.dumps(inspect.inspect_project(self.project,'v2.0.0'))
        for term in ('capitalization','missing','outside project','differs','LFS'): self.assertIn(term,text)
    def test_installer_inspection_never_executes_file(self):
        header=bytearray(64); header[:4]=b'\x7fELF'; header[4]=2; header[5]=1; header[18]=62
        path=self.file('installer',header)
        with patch('subprocess.run',side_effect=AssertionError('must not execute')):
            self.assertIn('x86_64',inspect.inspect_installer(path))
        self.assertIn('not verified',inspect.inspect_installer(path))
    def test_redaction_removes_common_credentials_and_home(self):
        text='ghp_'+'x'*30+'\npassword=example-password\nuser@example.com\n'+str(Path.home())+'\nhttps://host/?token=example\n-----BEGIN PRIVATE KEY-----\nprivate material'
        redacted=inspect.redact(text)
        for secret in ('x'*30,'example-password','user@example.com',str(Path.home()),'private material'): self.assertNotIn(secret,redacted)


class SessionTests(Fixture):
    def test_exact_boundary_cannot_be_reset_by_first_input(self):
        now=[10000]; state=SessionState(self.root/'session.json',lambda:now[0])
        now[0]+=1799; state.activity(); self.assertFalse(state.check())
        now[0]+=1800; state.activity(); self.assertTrue(state.check())
        with self.assertRaises(OctoShipError): state.guard()
        state.verified(False); self.assertTrue(state.check()); state.verified(True); self.assertFalse(state.check())
    def test_lock_survives_restart_and_corrupt_state_fails_closed(self):
        path=self.root/'session.json'; state=SessionState(path); state.lock(); self.assertTrue(SessionState(path).check())
        for data in ('{broken','{"locked":false,"last":NaN}','{"locked":"false","last":10}'):
            path.write_text(data); self.assertTrue(SessionState(path).check())
    def test_clock_rollback_locks(self):
        now=[1000]; state=SessionState(self.root/'session.json',lambda:now[0]); now[0]-=1; self.assertTrue(state.check())
    def test_transport_lock_prevents_send(self):
        api=GitHub('fixture'); state=SessionState(self.root/'session.json'); state.lock(); api.guard=state.guard
        with patch.object(api.opener,'open',side_effect=AssertionError('must not send')):
            with self.assertRaises(OctoShipError): api.request('/user')
            with self.assertRaises(OctoShipError): api.asset_request('/assets',io.BytesIO(b'x'),1)
            with self.assertRaises(OctoShipError): api.download_digest('/asset')
    def test_empty_password_never_authenticates(self):
        self.assertFalse(verify_password('')); self.assertFalse(verify_password('bad\0value'))



class TransportAndPamTests(unittest.TestCase):
    def test_signed_asset_redirect_does_not_forward_authorization(self):
        from urllib.error import HTTPError
        from unittest.mock import Mock
        api=GitHub('fixture-only-token')
        redirect=HTTPError('https://api.github.com/asset',302,'redirect',{'Location':'https://assets.example/download?signed=fixture'},None)
        downloaded=Mock(); downloaded.open.return_value=io.BytesIO(b'asset bytes')
        with patch.object(api.opener,'open',side_effect=redirect) as original, patch('octoship.core.build_opener',return_value=downloaded):
            size,digest=api.download_digest('/asset')
        self.assertEqual(size,11); self.assertEqual(digest,hashlib.sha256(b'asset bytes').hexdigest())
        self.assertTrue(original.call_args.args[0].get_header('Authorization'))
        self.assertIsNone(downloaded.open.call_args.args[0].get_header('Authorization'))
    def test_insecure_asset_redirect_is_rejected(self):
        from urllib.error import HTTPError
        api=GitHub('fixture')
        redirect=HTTPError('https://api.github.com/asset',302,'redirect',{'Location':'http://example/download'},None)
        with patch.object(api.opener,'open',side_effect=redirect):
            with self.assertRaises(OctoShipError): api.download_digest('/asset')
    def test_pam_abi_conversation_account_check_and_current_uid(self):
        import ctypes as C
        import pwd
        from types import SimpleNamespace
        current='fixture-user'
        class Function:
            def __init__(self,fn): self.fn=fn
            def __call__(self,*args): return self.fn(*args)
        real_cdll=C.CDLL; libc=real_cdll(None); libc.free.argtypes=[C.c_void_p]
        username=C.create_string_buffer(current.encode()); conversations=[]; ended=[]; account_status=[0]; auth_status=[0]
        def start(service,user,conv,handle):
            self.assertEqual(service,b'login'); self.assertEqual(user,current.encode())
            conversations.append(conv._obj); handle._obj.value=1; return 0
        def authenticate(handle,flags):
            self.assertEqual(flags,1)
            callback=conversations[-1].function
            Message=callback._argtypes_[1]._type_._type_
            Response=callback._argtypes_[2]._type_._type_
            messages=(C.POINTER(Message)*1)(C.pointer(Message(1,b'Password:')))
            answers=C.POINTER(Response)()
            self.assertEqual(callback(1,messages,C.byref(answers),None),0)
            self.assertEqual(C.string_at(answers[0].response),b'fixture password')
            libc.free(answers[0].response); libc.free(C.cast(answers,C.c_void_p))
            return auth_status[0]
        def get_item(handle,key,result): result._obj.value=C.cast(username,C.c_void_p).value; return 0
        pam=SimpleNamespace(pam_start=Function(start),pam_authenticate=Function(authenticate),pam_acct_mgmt=Function(lambda *a:account_status[0]),pam_get_item=Function(get_item),pam_end=Function(lambda *a:ended.append(a) or 0))
        with patch('octoship.session.C.CDLL',side_effect=lambda name:pam if name=='libpam.so.0' else real_cdll(name)), \
             patch('octoship.session.pwd.getpwuid',return_value=SimpleNamespace(pw_name=current)), \
             patch('octoship.session.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid())):
            self.assertTrue(verify_password('fixture password'))
            account_status[0]=13; self.assertFalse(verify_password('fixture password'))
            account_status[0]=0; auth_status[0]=7; self.assertFalse(verify_password('fixture password'))
            auth_status[0]=0
            with patch('octoship.session.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid()+1)):
                self.assertFalse(verify_password('fixture password'))
        self.assertEqual(len(ended),4)


if __name__ == '__main__': unittest.main()
