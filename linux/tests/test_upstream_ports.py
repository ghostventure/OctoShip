"""Focused checks for Linux ports of recent OctoShip desktop improvements."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from octoship.content_types import detect_content_kind, extension_mismatch, is_known_binary
from octoship.core import ApiError
from octoship.editor import vscode_command


class UpstreamPortTest(unittest.TestCase):
    def test_content_type_uses_bounded_signatures_and_warns_on_extension_mismatch(self):
        self.assertEqual(detect_content_kind(b"\x89PNG\r\n\x1a\nrest"), "PNG")
        self.assertEqual(detect_content_kind(b"GIF89a"), "GIF")
        self.assertEqual(detect_content_kind(b"%PDF-1.7"), "PDF")
        self.assertEqual(detect_content_kind(b"unknown\0binary"), "Unknown binary")
        self.assertIsNone(extension_mismatch("photo.PNG", "PNG"))
        self.assertEqual(extension_mismatch("photo.png", "JPEG"),
                         "Filename extension suggests PNG, but file content looks like JPEG.")
        self.assertTrue(is_known_binary("Unknown binary"))

    def test_rate_limit_guidance_uses_retry_after_and_reset(self):
        now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
        secondary = ApiError(429, {"Retry-After": "20"}, now)
        self.assertIn("Retry in less than a minute", str(secondary))
        primary = ApiError(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(now.timestamp()) + 90)}, now)
        self.assertIn("Retry in about 2 minutes", str(primary))
        permission = ApiError(403, {}, now)
        self.assertIn("Access denied or API rate limit reached", str(permission))

    def test_rate_limit_guidance_accepts_http_date(self):
        now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
        error = ApiError(429, {"Retry-After": "Thu, 15 Oct 2026 12:02:00 GMT"}, now)
        self.assertIn("Retry in about 2 minutes", str(error))

    def test_vscode_command_is_argv_based_and_handles_workspace_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            code_file = root / "a file.py"
            code_file.write_text("print('ok')")
            workspace = root / "sample.code-workspace"
            workspace.write_text("{}")
            with patch("octoship.editor.shutil.which", return_value="/usr/bin/code"):
                folder_args, folder_cwd = vscode_command(root)
                self.assertEqual(folder_args, ["/usr/bin/code", "--reuse-window", str(root)])
                self.assertEqual(folder_cwd, str(root))
                file_args, file_cwd = vscode_command(code_file)
                self.assertEqual(file_args, ["/usr/bin/code", "--reuse-window", "--goto", str(code_file)])
                self.assertEqual(file_cwd, str(root))
                workspace_args, _ = vscode_command(workspace)
                self.assertNotIn("--goto", workspace_args)


if __name__ == "__main__":
    unittest.main()
