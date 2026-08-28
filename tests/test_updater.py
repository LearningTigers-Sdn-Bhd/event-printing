import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# updater imports httpx; stub it so tests don't need the network or the package.
httpx_stub = types.ModuleType("httpx")
httpx_stub.Client = object
sys.modules.setdefault("httpx", httpx_stub)

import updater


class ParseVersionTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(updater.parse_version("1.2.3"), (1, 2, 3))

    def test_leading_v(self):
        self.assertEqual(updater.parse_version("v1.2.3"), (1, 2, 3))

    def test_two_part(self):
        self.assertEqual(updater.parse_version("1.2"), (1, 2))

    def test_garbage(self):
        self.assertEqual(updater.parse_version("not a version"), (0,))

    def test_embedded_in_tag(self):
        self.assertEqual(updater.parse_version("release-1.4.0-final"), (1, 4, 0))


class IsNewerTests(unittest.TestCase):
    def test_newer_patch(self):
        self.assertTrue(updater.is_newer("1.0.1", "1.0.0"))

    def test_newer_minor(self):
        self.assertTrue(updater.is_newer("v1.1.0", "1.0.9"))

    def test_same_is_not_newer(self):
        self.assertFalse(updater.is_newer("1.0.0", "1.0.0"))

    def test_older_is_not_newer(self):
        self.assertFalse(updater.is_newer("1.0.0", "1.0.1"))

    def test_different_lengths(self):
        self.assertTrue(updater.is_newer("1.1", "1.0.9"))
        self.assertFalse(updater.is_newer("1.0", "1.0.1"))


class CheckTests(unittest.TestCase):
    def _stub_release(self, tag):
        return {"tag_name": tag, "url": "http://example", "asset_url": "https://github.com/x/event-printer.exe"}

    def test_update_available_when_github_newer(self):
        with patch.object(updater, "update_supported", return_value=True), \
             patch.object(updater, "_fetch_latest_release", return_value=self._stub_release("9.9.9")), \
             patch.object(updater, "current_version", return_value="1.0.0"):
            st = updater.check()
        self.assertTrue(st["update_available"])
        self.assertEqual(st["latest"], "9.9.9")

    def test_no_update_when_current(self):
        with patch.object(updater, "update_supported", return_value=True), \
             patch.object(updater, "_fetch_latest_release", return_value=self._stub_release("1.0.0")), \
             patch.object(updater, "current_version", return_value="1.0.0"):
            st = updater.check()
        self.assertFalse(st["update_available"])

    def test_unsupported_platform_short_circuits(self):
        with patch.object(updater, "update_supported", return_value=False):
            st = updater.check()
        self.assertFalse(st["update_supported"])
        self.assertFalse(st["update_available"])

    def test_network_error_reported(self):
        with patch.object(updater, "update_supported", return_value=True), \
             patch.object(updater, "_fetch_latest_release", side_effect=RuntimeError("boom")):
            st = updater.check()
        self.assertEqual(st["phase"], "error")
        self.assertIn("boom", st["error"])


if __name__ == "__main__":
    unittest.main()
