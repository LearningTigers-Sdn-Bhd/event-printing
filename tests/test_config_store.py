import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config_store


class SanitizeLayoutTests(unittest.TestCase):
    def test_custom_fields_persist_through_sanitize(self):
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "custom_abc123"],
            "custom_fields": {"custom_abc123": {"label": "Sponsor", "backend_key": "sponsor"}},
        })
        self.assertEqual(layout["elements"], ["name", "custom_abc123"])
        self.assertEqual(
            layout["custom_fields"]["custom_abc123"],
            {"label": "Sponsor", "backend_key": "sponsor"},
        )

    def test_unknown_elements_still_dropped(self):
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "not_a_field"],
        })
        self.assertEqual(layout["elements"], ["name"])
        self.assertEqual(layout["custom_fields"], {})

    def test_custom_field_without_label_dropped(self):
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "custom_bad"],
            "custom_fields": {"custom_bad": {"label": "", "backend_key": ""}},
        })
        self.assertEqual(layout["elements"], ["name"])

    def test_max_custom_fields_enforced(self):
        defs = {f"custom_{i:06d}": {"label": f"F{i}", "backend_key": ""} for i in range(10)}
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name"] + list(defs),
            "custom_fields": defs,
        })
        self.assertLessEqual(len(layout["custom_fields"]), config_store.MAX_CUSTOM_FIELDS)


class VerticalOffsetTests(unittest.TestCase):
    def test_offset_persisted(self):
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name"],
            "vertical_offset_mm": 12.5,
        })
        self.assertEqual(layout["vertical_offset_mm"], 12.5)

    def test_offset_defaults_to_zero(self):
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name"],
        })
        self.assertEqual(layout["vertical_offset_mm"], 0.0)

    def test_offset_clamped_to_range(self):
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name"],
            "vertical_offset_mm": 500,
        })
        self.assertEqual(layout["vertical_offset_mm"], config_store.MAX_VERTICAL_OFFSET_MM)
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name"],
            "vertical_offset_mm": -500,
        })
        self.assertEqual(layout["vertical_offset_mm"], config_store.MIN_VERTICAL_OFFSET_MM)

    def test_offset_invalid_falls_back_to_zero(self):
        layout = config_store._sanitize_layout({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name"],
            "vertical_offset_mm": "not a number",
        })
        self.assertEqual(layout["vertical_offset_mm"], 0.0)


if __name__ == "__main__":
    unittest.main()
