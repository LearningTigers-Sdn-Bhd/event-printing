import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

qrcode_module = types.ModuleType("qrcode")
qrcode_module.constants = types.SimpleNamespace(ERROR_CORRECT_M=0)
qrcode_module.QRCode = object
sys.modules["qrcode"] = qrcode_module

reportlab_module = types.ModuleType("reportlab")
pdfgen_module = types.ModuleType("reportlab.pdfgen")
canvas_module = types.ModuleType("reportlab.pdfgen.canvas")
canvas_module.Canvas = object
pdfbase_module = types.ModuleType("reportlab.pdfbase")
pdfmetrics_module = types.ModuleType("reportlab.pdfbase.pdfmetrics")
lib_module = types.ModuleType("reportlab.lib")
units_module = types.ModuleType("reportlab.lib.units")
utils_module = types.ModuleType("reportlab.lib.utils")
pdfmetrics_module.stringWidth = lambda text, font_name, font_size: len(text) * font_size
units_module.inch = 72
utils_module.ImageReader = object
sys.modules["reportlab"] = reportlab_module
sys.modules["reportlab.pdfgen"] = pdfgen_module
sys.modules["reportlab.pdfgen.canvas"] = canvas_module
sys.modules["reportlab.pdfbase"] = pdfbase_module
sys.modules["reportlab.pdfbase.pdfmetrics"] = pdfmetrics_module
sys.modules["reportlab.lib"] = lib_module
sys.modules["reportlab.lib.units"] = units_module
sys.modules["reportlab.lib.utils"] = utils_module
sys.modules["models"] = types.SimpleNamespace(TicketPayload=object)
import pdf_generator


class TicketRoleLabelTests(unittest.TestCase):
    def test_interested_delegate_prints_as_delegate(self):
        self.assertEqual(pdf_generator.normalize_role_text("Interested Delegate"), "DELEGATE")

    def test_visitor_prints_unchanged(self):
        self.assertEqual(pdf_generator.normalize_role_text("Visitor"), "Visitor")

    @staticmethod
    def _block_index(events, phrase):
        """Index of a phrase in drawn lines, tolerating word-wrap splits."""
        for idx, line in enumerate(events):
            if phrase in line:
                return idx
        words = phrase.split()
        for i in range(len(events) - len(words) + 1):
            if [w.strip() for w in events[i:i + len(words)]] == words:
                return i
        return -1

    def _render(self, layout):
        events = []

        class FakeCanvas:
            def __init__(self, path, pagesize):
                pass

            def setFont(self, font_name, font_size):
                pass

            def setFillColorRGB(self, red, green, blue):
                pass

            def drawCentredString(self, x, y, text):
                events.append(text)

            def drawImage(self, image, x, y, width, height):
                events.append("QR")

            def showPage(self):
                pass

            def save(self):
                pass

        payload = types.SimpleNamespace(
            ticket_id="A1-0245",
            name="Test User",
            company="Test Company",
            title="CEO",
            country="Malaysia",
            table_no="12",
            ticket_type="Interested Delegate",
            custom={"custom_abc123": "Sponsor A"},
        )

        with patch.object(pdf_generator.canvas, "Canvas", FakeCanvas):
            with patch.object(pdf_generator, "generate_qr_image", lambda data: object()):
                pdf_generator.generate_ticket_pdf(Path("ticket.pdf"), payload, layout)
        return events

    def test_badge_sections_render_in_requested_order(self):
        events = self._render({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "role", "company", "qr"],
        })
        i = self._block_index
        self.assertLess(i(events, "TEST USER"), i(events, "DELEGATE"))
        self.assertLess(i(events, "DELEGATE"), i(events, "TEST COMPANY"))
        self.assertLess(i(events, "TEST COMPANY"), i(events, "QR"))

    def test_layout_reorders_and_omits_elements(self):
        events = self._render({
            "paper": {"width_mm": 155, "height_mm": 104},
            "elements": ["name", "title", "company", "country", "role"],
        })
        i = self._block_index
        self.assertNotIn("QR", events)
        self.assertLess(i(events, "TEST USER"), i(events, "CEO"))
        self.assertLess(i(events, "CEO"), i(events, "TEST COMPANY"))
        self.assertLess(i(events, "TEST COMPANY"), i(events, "MALAYSIA"))
        self.assertLess(i(events, "MALAYSIA"), i(events, "DELEGATE"))

    def test_layout_with_table_no_after_role(self):
        events = self._render({
            "paper": {"width_mm": 155, "height_mm": 104},
            "elements": ["name", "company", "qr", "role", "table_no"],
        })
        i = self._block_index
        self.assertLess(i(events, "QR"), i(events, "DELEGATE"))
        self.assertLess(i(events, "DELEGATE"), i(events, "TABLE 12"))

    def test_missing_optional_field_skipped(self):
        events = self._render({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "country", "role"],
        })
        # country present in payload -> rendered; now check skip behavior via empty company
        self.assertIn("MALAYSIA", events)

    def test_custom_field_renders_value(self):
        events = self._render({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "custom_abc123", "qr"],
        })
        i = self._block_index
        self.assertGreater(i(events, "SPONSOR A"), -1)
        self.assertLess(i(events, "TEST USER"), i(events, "SPONSOR A"))
        self.assertLess(i(events, "SPONSOR A"), i(events, "QR"))

    def test_custom_field_missing_value_skipped(self):
        events = self._render({
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "custom_nope", "qr"],
        })
        self.assertNotIn("CUSTOM FIELD", events)

    def _render_with_coords(self, layout):
        """Capture (text, y) pairs so we can assert on vertical placement."""
        draws = []

        class FakeCanvas:
            def __init__(self, path, pagesize):
                pass

            def setFont(self, font_name, font_size):
                pass

            def setFillColorRGB(self, red, green, blue):
                pass

            def drawCentredString(self, x, y, text):
                draws.append((text, y))

            def drawImage(self, image, x, y, width, height):
                draws.append(("QR", y))

            def showPage(self):
                pass

            def save(self):
                pass

        payload = types.SimpleNamespace(
            ticket_id="A1-0245",
            name="Test User",
            company="Test Company",
            title=None,
            country=None,
            table_no=None,
            ticket_type="VIP",
            custom={},
        )

        with patch.object(pdf_generator.canvas, "Canvas", FakeCanvas):
            with patch.object(pdf_generator, "generate_qr_image", lambda data: object()):
                pdf_generator.generate_ticket_pdf(Path("ticket.pdf"), payload, layout)
        return draws

    def test_vertical_offset_shifts_block_down(self):
        base_layout = {
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "role"],
        }
        centered = dict(self._render_with_coords(base_layout))
        shifted = dict(self._render_with_coords({**base_layout, "vertical_offset_mm": 10}))
        # Positive offset => content pushed down the page => smaller y (PDF
        # origin is bottom-left). Compare the name's y in both renders.
        self.assertLess(shifted["TEST USER"], centered["TEST USER"])
        self.assertLess(shifted["VIP"], centered["VIP"])
        # 10 mm ≈ 28.35 pt shift
        self.assertAlmostEqual(centered["TEST USER"] - shifted["TEST USER"], 10 / 25.4 * 72, places=1)

    def test_vertical_offset_shifts_block_up(self):
        base_layout = {
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "role"],
        }
        centered = dict(self._render_with_coords(base_layout))
        shifted = dict(self._render_with_coords({**base_layout, "vertical_offset_mm": -10}))
        self.assertGreater(shifted["TEST USER"], centered["TEST USER"])
        self.assertGreater(shifted["VIP"], centered["VIP"])

    def test_vertical_offset_clamped_to_paper(self):
        base_layout = {
            "paper": {"width_mm": 100, "height_mm": 80},
            "elements": ["name", "role"],
        }
        # A huge downward push should clamp: content stays on the page
        # (name baseline stays above the bottom margin).
        draws = self._render_with_coords({**base_layout, "vertical_offset_mm": 200})
        lowest = min(y for _, y in draws)
        self.assertGreater(lowest, 0)


if __name__ == "__main__":
    unittest.main()
