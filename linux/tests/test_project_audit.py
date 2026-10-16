"""One focused trigger test per stable project readiness diagnostic."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship.project_audit import audit_project, MAX_FILES


class ProjectAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def put(self, name, value=b'x\n'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else value.encode())
        return path

    def codes(self):
        return {x.code for x in audit_project(self.root)}

    def test_all_metadata_handoff_checks(self):
        expected = {'META_README','META_LICENSE','META_SECURITY','META_CONTRIBUTING','META_CODE_OF_CONDUCT','META_CHANGELOG','META_GITIGNORE','META_EDITORCONFIG','META_CODEOWNERS','META_ISSUE_TEMPLATE','META_PR_TEMPLATE','META_CI'}
        self.assertTrue(expected <= self.codes())

    def test_metadata_directories_count_as_present(self):
        for name in ('README.md', 'LICENSE', 'SECURITY.md', 'CONTRIBUTING.md',
                     'CODE_OF_CONDUCT.md', 'CHANGELOG.md', '.gitignore',
                     '.editorconfig', '.github/CODEOWNERS',
                     '.github/ISSUE_TEMPLATE/bug.md',
                     '.github/PULL_REQUEST_TEMPLATE.md', '.github/workflows/ci.yml'):
            self.put(name)
        codes = self.codes()
        self.assertNotIn('META_ISSUE_TEMPLATE', codes)
        self.assertNotIn('META_CI', codes)

    def test_package_json_syntax_and_required_fields(self):
        self.put('package.json', '{bad')
        self.assertIn('MANIFEST_PACKAGE_JSON', self.codes())

    def test_package_version(self):
        self.put('package.json', '{"scripts":{"test":"t","build":"b"}}')
        self.put('package-lock.json', '{}')
        self.assertIn('MANIFEST_PACKAGE_VERSION', self.codes())

    def test_package_test_script(self):
        self.put('package.json', '{"version":"1.0.0","scripts":{"build":"b"}}')
        self.put('package-lock.json')
        self.assertIn('MANIFEST_PACKAGE_TEST', self.codes())

    def test_package_build_script(self):
        self.put('package.json', '{"version":"1.0.0","scripts":{"test":"t"}}')
        self.put('package-lock.json')
        self.assertIn('MANIFEST_PACKAGE_BUILD', self.codes())

    def test_package_lockfile(self):
        self.put('package.json', '{"version":"1.0.0","scripts":{"test":"t","build":"b"}}')
        self.assertIn('MANIFEST_PACKAGE_LOCK', self.codes())

    def test_pyproject_toml_parse(self):
        self.put('pyproject.toml', '[invalid')
        self.assertIn('MANIFEST_PYPROJECT', self.codes())

    def test_empty_requirements(self):
        self.put('requirements.txt', '# comments only\n')
        self.assertIn('MANIFEST_REQUIREMENTS_EMPTY', self.codes())

    def test_editable_requirements(self):
        self.put('requirements.txt', '-e ../local-package\n')
        self.assertIn('MANIFEST_REQUIREMENTS_EDITABLE', self.codes())

    def test_csproj_xml_parse(self):
        self.put('App.csproj', '<Project>')
        self.assertIn('MANIFEST_CSPROJ_XML', self.codes())

    def test_csproj_framework_required(self):
        self.put('App.csproj', '<Project />\n')
        self.assertIn('MANIFEST_CSPROJ_FRAMEWORK', self.codes())

    def test_global_dotnet_sdk_version(self):
        self.put('global.json', '{"sdk":{}}')
        self.assertIn('MANIFEST_DOTNET_SDK', self.codes())

    def test_directory_build_props_xml(self):
        self.put('Directory.Build.props', '<Project>')
        self.assertIn('MANIFEST_BUILD_PROPS', self.codes())

    def test_file_size_limit_diagnostic(self):
        self.put('large.txt', b'x' * (256 * 1024 + 1))
        self.assertIn('FILE_TOO_LARGE', self.codes())

    def test_filename_whitespace(self):
        self.put('odd name.txt')
        self.assertIn('PATH_WHITESPACE', self.codes())

    def test_sensitive_filename(self):
        self.put('.env')
        self.assertIn('PATH_SENSITIVE_NAME', self.codes())

    def test_empty_file(self):
        self.put('empty.txt', b'')
        self.assertIn('FILE_EMPTY', self.codes())

    def test_final_newline(self):
        self.put('line.txt', 'hello')
        self.assertIn('TEXT_FINAL_NEWLINE', self.codes())

    def test_trailing_whitespace(self):
        self.put('line.txt', 'hello  \n')
        self.assertIn('TEXT_TRAILING_SPACE', self.codes())

    def test_mixed_line_endings(self):
        self.put('line.txt', b'one\r\ntwo\n')
        self.assertIn('TEXT_MIXED_EOL', self.codes())

    def test_merge_conflict_marker(self):
        self.put('line.txt', '<<<<<<< ours\nvalue\n=======\nother\n>>>>>>> theirs\n')
        self.assertIn('TEXT_CONFLICT_MARKER', self.codes())

    def test_casefold_path_collision(self):
        self.put('Readme.md')
        self.put('README.md')
        self.assertIn('PATH_CASE_COLLISION', self.codes())

    def test_symlinks_are_reported_without_following(self):
        target = self.put('target.txt')
        try:
            (self.root / 'link.txt').symlink_to(target)
        except OSError as error:
            self.skipTest(f'symlink unavailable: {error}')
        self.assertIn('PATH_SYMLINK', self.codes())

    def test_workflow_write_all(self):
        self.put('.github/workflows/ci.yml', 'permissions: write-all\n')
        self.assertIn('CI_WRITE_ALL', self.codes())

    def test_workflow_mutable_action_ref(self):
        self.put('.github/workflows/ci.yml', 'jobs:\n  test:\n    steps:\n      - uses: actions/checkout@main\n')
        self.assertIn('CI_MUTABLE_REF', self.codes())

    def test_workflow_pull_request_target_warning(self):
        self.put('.github/workflows/ci.yml', 'on:\n  pull_request_target:\n')
        self.assertIn('CI_PR_TARGET', self.codes())

    def test_workflow_contents_write_warning(self):
        self.put('.github/workflows/ci.yml', 'permissions:\n  contents: write\n')
        self.assertIn('CI_CONTENTS_WRITE', self.codes())

    def test_workflow_tag_pin_warning(self):
        self.put('.github/workflows/ci.yml', 'steps:\n  - uses: actions/checkout@v4\n')
        self.assertIn('CI_TAG_PIN', self.codes())

    def test_workflow_explicit_permissions(self):
        self.put('.github/workflows/ci.yml', 'name: CI\njobs:\n  build:\n    runs-on: ubuntu-latest\n')
        self.assertIn('CI_PERMISSIONS', self.codes())

    def test_file_cap_is_enforced(self):
        # Keep this cheap: lower the cap in the module and verify the guard.
        from octoship import project_audit
        old = project_audit.MAX_FILES
        try:
            project_audit.MAX_FILES = 1
            self.put('a.txt'); self.put('b.txt')
            with self.assertRaisesRegex(ValueError, '10,000 files'):
                audit_project(self.root)
        finally:
            project_audit.MAX_FILES = old


if __name__ == '__main__':
    unittest.main()
