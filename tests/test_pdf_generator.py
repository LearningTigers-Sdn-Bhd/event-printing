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

    def test_badge_sections_render_in_requested_order(self):
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
            ticket_type="Interested Delegate",
        )

        with patch.object(pdf_generator.canvas, "Canvas", FakeCanvas):
            with patch.object(pdf_generator, "generate_qr_image", lambda data: object()):
                pdf_generator.generate_ticket_pdf(Path("ticket.pdf"), payload)

        self.assertLess(events.index("TEST USER"), events.index("DELEGATE"))
        self.assertLess(events.index("DELEGATE"), events.index("TEST COMPANY"))
        self.assertLess(events.index("TEST COMPANY"), events.index("QR"))


if __name__ == "__main__":
    unittest.main()
