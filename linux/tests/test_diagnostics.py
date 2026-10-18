import json
import tempfile
import unittest
from pathlib import Path

from octoship.diagnostics import environment_report, format_report


class EnvironmentReportTests(unittest.TestCase):
    def test_report_is_offline_and_omits_credential_values(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            private_mount = home / 'private-customer-mount'
            report = environment_report(
                environ={'HOME': str(home), 'XDG_STATE_HOME': str(private_mount), 'GH_TOKEN': 'must-not-appear'},
                which=lambda name: None,
            )
            self.assertEqual(report['network_requests'], 0)
            self.assertFalse(report['credentials_collected'])
            self.assertGreaterEqual(len(report['checks']), 20)
            self.assertTrue((private_mount / 'octoship').is_dir())
            self.assertNotIn('must-not-appear', format_report(report))
            self.assertNotIn('must-not-appear', format_report(report, 'json'))
            self.assertNotIn(str(private_mount), format_report(report))
            self.assertNotIn(str(private_mount), format_report(report, 'json'))

    def test_json_and_text_formats(self):
        report = {'summary': 'ready', 'checks': [], 'network_requests': 0, 'credentials_collected': False}
        self.assertEqual(json.loads(format_report(report, 'json')), report)
        self.assertIn('OctoShip environment diagnostics', format_report(report))


if __name__ == '__main__':
    unittest.main()
