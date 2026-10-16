"""Offline tests for bounded release artifact auditing."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship.release_audit import (MAX_MANIFEST_BYTES, ReleaseAuditError, audit_json,
                                   audit_release, create_checksum_manifest)


class ReleaseAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def rows(self, **kwargs):
        return {row.key: row for row in audit_release(self.root, **kwargs)}

    def put(self, name, data=b'payload'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_all_40_diagnostics_have_stable_unique_keys(self):
        report = audit_release(self.root, '1.2.3', host_platform='linux')
        self.assertEqual(len(report), 40)
        self.assertEqual(len({row.key for row in report}), 40)
        self.assertTrue(all(row.title and row.status and row.detail for row in report))
        self.assertEqual({row.key: row for row in report}['expected_version'].detail, '1.2.3')

    def test_checksum_manifest_verifies_and_finds_missing_coverage(self):
        artifact = self.put('OctoShip-1.2.3-linux-x86_64.run', b'package')
        self.put('manual.txt', b'manual')
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.put('SHA256SUMS', f'{digest}  {artifact.name}\n'.encode())
        rows = self.rows(expected_version='1.2.3', host_platform='linux')
        self.assertEqual(rows['checksum_verified'].detail, '1')
        self.assertEqual(rows['checksum_mismatch'].status, 'ok')
        self.assertEqual(rows['version_mismatches'].status, 'ok')
        self.assertEqual(rows['platform_coverage'].status, 'ok')
        self.assertIn('manual.txt', rows['checksum_unlisted_artifacts'].detail)

    def test_checksum_digest_mismatch_missing_and_duplicate_rows(self):
        self.put('release.deb', b'actual')
        self.put('SHA256SUMS', ('0' * 64 + '  release.deb\n' + '1' * 64 + '  release.deb\n' + '2' * 64 + '  gone.deb\n').encode())
        rows = self.rows()
        self.assertEqual(rows['checksum_duplicate_paths'].status, 'review')
        self.assertEqual(rows['checksum_missing_artifacts'].status, 'error')
        self.assertEqual(rows['checksum_mismatch'].status, 'error')
        self.assertIn('release.deb', rows['checksum_mismatch'].detail)

    def test_malformed_and_unsafe_manifest_entries_are_not_followed(self):
        self.put('safe.zip', b'not a zip')
        self.put('SHA256SUMS', (('a' * 64) + '  ../outside\n' + 'bad digest  safe.zip\n').encode())
        rows = self.rows()
        self.assertEqual(rows['checksum_path_safety'].status, 'error')
        self.assertEqual(rows['checksum_manifest_errors'].status, 'error')
        self.assertEqual(rows['zip_integrity'].status, 'error')

    def test_manifest_size_is_checked_before_reading(self):
        self.put('SHA256SUMS', b'x' * (MAX_MANIFEST_BYTES + 1))
        rows = self.rows()
        self.assertEqual(rows['checksum_manifest_budget'].status, 'review')
        self.assertEqual(rows['checksum_manifest_errors'].status, 'error')

    def test_filename_version_platform_and_case_collisions(self):
        self.put('Tool-1.0-linux.zip')
        self.put('tool-1.0-linux.zip')
        self.put('tool-2.0-windows.exe')
        rows = self.rows(expected_version='3.0', host_platform='linux')
        self.assertEqual(rows['version_consistency'].status, 'review')
        self.assertEqual(rows['version_mismatches'].status, 'review')
        self.assertEqual(rows['filename_case_duplicates'].status, 'review')
        self.assertEqual(rows['platform_coverage'].status, 'ok')

    def test_zip_crc_layout_and_metadata_are_checked_without_extracting(self):
        path = self.root / 'OctoShip-1.0-linux.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('folder/one.txt', 'one')
            archive.writestr('other/two.txt', 'two')
        rows = self.rows(host_platform='linux')
        self.assertEqual(rows['zip_count'].detail, '1')
        self.assertEqual(rows['zip_integrity'].status, 'info')
        self.assertIn('Checked', rows['zip_integrity'].detail)
        self.assertEqual(rows['zip_layout'].status, 'review')
        self.assertFalse((self.root / 'folder').exists())

    def test_deb_format_and_installer_inventory(self):
        self.put('octoship_1.0_amd64.deb', b'!<arch>\n' + b'payload')
        self.put('octoship_1.0_bad.deb', b'not-deb')
        rows = self.rows()
        self.assertEqual(rows['deb_archive_format'].status, 'error')
        self.assertIn('octoship_1.0_bad.deb', rows['deb_archive_format'].detail)
        self.assertEqual(rows['linux_packages'].status, 'info')
        self.assertEqual(rows['standalone_installers'].detail, '0')

    def test_checksum_manifest_creation_is_atomic_and_verifiable(self):
        artifact = self.put('app-linux.run', b'package bytes')
        output = self.root / 'SHA256SUMS.txt'
        before = artifact.read_bytes()
        saved, count = create_checksum_manifest(self.root, output)
        digest = hashlib.sha256(before).hexdigest()
        self.assertEqual(saved, output)
        self.assertEqual(count, 1)
        self.assertEqual(output.read_text(), f'{digest}  app-linux.run\n')
        self.assertEqual(artifact.read_bytes(), before)
        self.assertEqual(self.rows()['checksum_verified'].status, 'ok')

    def test_checksum_manifest_refuses_arbitrary_output_and_symlink_artifact(self):
        self.put('asset.bin', b'a')
        with self.assertRaises(ReleaseAuditError):
            create_checksum_manifest(self.root, self.root / 'important.txt')
        (self.root / 'linked.bin').symlink_to(self.root / 'asset.bin')
        with self.assertRaises(ReleaseAuditError):
            create_checksum_manifest(self.root, self.root / 'SHA256SUMS')

    def test_empty_unknown_large_and_signature_artifact_advisories(self):
        self.put('empty.bin', b'')
        self.put('payload.weird', b'x')
        self.put('release.asc', b'signature')
        rows = self.rows()
        self.assertEqual(rows['empty_files'].status, 'review')
        self.assertIn('payload.weird', rows['unknown_extensions'].detail)
        self.assertEqual(rows['signatures'].detail, '1')

    def test_symlinks_are_reported_and_never_hashed(self):
        target = self.put('actual.bin')
        (self.root / 'alias.bin').symlink_to(target)
        rows = self.rows()
        self.assertEqual(rows['symlinks'].status, 'review')
        self.assertNotIn('alias.bin', rows['artifact_extensions'].detail)

    def test_release_directory_symlink_rejected(self):
        link = self.root.parent / (self.root.name + '-link')
        link.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(link.unlink)
        with self.assertRaises(ReleaseAuditError):
            audit_release(link)

    def test_json_export_is_valid_and_executable_artifacts_are_not_run(self):
        marker = self.root / 'marker'
        script = self.put('danger.run', f'#!/bin/sh\ntouch {marker}\n'.encode())
        data = json.loads(audit_json(self.root))
        self.assertEqual(len(data), 40)
        self.assertFalse(marker.exists())
        self.assertEqual(script.read_text().splitlines()[0], '#!/bin/sh')


if __name__ == '__main__':
    unittest.main()
