import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image

import printer


class ThickenTests(unittest.TestCase):
    def test_stroke_grows_one_pixel_each_side(self):
        img = Image.new("RGB", (20, 5), "white")
        for x in range(8, 12):  # 4px wide black stroke
            for y in range(5):
                img.putpixel((x, y), (0, 0, 0))
        out = printer._thicken(img).convert("L")
        dark = [x for x in range(20) if out.getpixel((x, 2)) == 0]
        self.assertEqual(dark, list(range(7, 13)))


class DirectThermalConfigTests(unittest.TestCase):
    def test_defaults_off_and_persists(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import config_store

        with TemporaryDirectory() as tmp:
            with patch.object(config_store, "config_path", return_value=Path(tmp) / "config.json"):
                self.assertFalse(config_store.load()["direct_thermal"])
                config_store.save({"direct_thermal": True})
                self.assertTrue(config_store.load()["direct_thermal"])
                self.assertTrue(config_store.public_view()["direct_thermal"])
                config_store.save({"direct_thermal": False})
                self.assertFalse(config_store.load()["direct_thermal"])


if __name__ == "__main__":
    unittest.main()
