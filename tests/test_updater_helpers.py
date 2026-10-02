import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import updater


def _fields(new):
    exe = Path("C:/Apps/event-printer.exe")
    return updater._helper_fields(exe, Path(new) if new else None)


class HelperScriptTests(unittest.TestCase):
    def test_templates_render_for_update_and_restart(self):
        for new in ("C:/Apps/event-printer.new", None):
            for tpl in (updater._HELPER_BAT, updater._HELPER_SH):
                out = tpl.format(**_fields(new))
                self.assertNotIn("{", out)
                self.assertIn("event-printer", out)

    def test_restart_has_empty_new_and_scripts_reset_pyinstaller_env(self):
        self.assertEqual(_fields(None)["new"], "")
        for tpl in (updater._HELPER_BAT, updater._HELPER_SH):
            out = tpl.format(**_fields(None))
            self.assertIn("PYINSTALLER_RESET_ENVIRONMENT=1", out)
            self.assertIn("_MEIPASS2", out)


if __name__ == "__main__":
    unittest.main()
