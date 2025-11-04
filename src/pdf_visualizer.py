from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from pydantic import BaseModel, Field
from typing import Optional


# --- DATA MODEL ---
class TicketPayload(BaseModel):
    """Schema for event badge data."""
    name: str = Field(..., json_schema_extra="Fazli Bin Omar")
    company: str = Field(..., json_schema_extra="Fazli Technologies")
    title: str = Field(..., json_schema_extra="CEO")
    ticket_type: Optional[str] = Field(default="Delegate")


# --- TEXT WRAPPING UTILS ---
def wrap_text_to_width(text: str, font_name: str, font_size: int, max_width: float):
    """
    Automatically wraps text into multiple lines that fit within the given max_width.
    Returns a list of uppercase lines.
    """
    words = text.upper().split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        if stringWidth(test_line, font_name, font_size) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def get_name_lines(name: str):
    """
    Determines appropriate font size and line splits for the name.
    """
    name_upper = name.upper().strip()
    MAX_CHARS_SINGLE_LINE = 25
    MAX_CHARS_TWO_LINES = 50

    if len(name_upper) <= MAX_CHARS_SINGLE_LINE:
        return 26, [name_upper]
    elif len(name_upper) <= MAX_CHARS_TWO_LINES:
        font_size = 20
        mid_point = len(name_upper) // 2
        split_point = name_upper.rfind(" ", 0, mid_point + 5)
        if split_point > 0:
            return font_size, [
                name_upper[:split_point].strip(),
                name_upper[split_point:].strip(),
            ]
        else:
            return font_size, [name_upper[:mid_point], name_upper[mid_point:]]
    else:
        font_size = 16
        mid_point = len(name_upper) // 2
        return font_size, [
            name_upper[:mid_point].strip(),
            name_upper[mid_point:].strip(),
        ]


# --- MAIN PDF GENERATOR ---
def generate_ticket_pdf(path: Path, data: TicketPayload):
    """
    Generates an event badge PDF with all-caps text and auto-wrapped lines.
    """
    # Badge size (H, W)
    h, w = 5.7 * inch, 4.15 * inch
    c = canvas.Canvas(str(path), pagesize=(w, h))

    # Margins and layout constants
    side_margin = 0.3 * inch
    max_text_width = w - (2 * side_margin)
    current_y = h - 2 * inch

    # --- 1. Participant Name ---
    font_size, name_lines = get_name_lines(data.name)
    line_spacing = 0.3 * inch if font_size > 20 else 0.25 * inch
    c.setFont("Helvetica-Bold", font_size)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    for i, line in enumerate(name_lines):
        line_y = current_y - (i * line_spacing)
        c.drawCentredString(w / 2, line_y, line)
    current_y -= (len(name_lines) * line_spacing) + 0.4 * inch

    # --- 2. Company Name ---
    font_name = "Helvetica"
    font_size_company = 15
    c.setFont(font_name, font_size_company)
    company_lines = wrap_text_to_width(data.company, font_name, font_size_company, max_text_width)
    for line in company_lines:
        c.drawCentredString(w / 2, current_y, line)
        current_y -= 0.2 * inch
    current_y -= 0.2 * inch

    # --- 3. Title ---
    font_name = "Helvetica-Oblique"
    font_size_title = 14
    c.setFont(font_name, font_size_title)
    title_lines = wrap_text_to_width(data.title, font_name, font_size_title, max_text_width)
    for line in title_lines:
        c.drawCentredString(w / 2, current_y, line)
        current_y -= 0.2 * inch

    # --- 4. Ticket Type ---
    c.setFont("Helvetica-Bold", 24)
    bottom_y = 1.25 * inch
    c.drawCentredString(w / 2.1, bottom_y, data.ticket_type.upper())

    # Save PDF
    c.showPage()
    c.save()


# --- TEST HARNESS ---
if __name__ == "__main__":
    mock_data_vip = TicketPayload(
        name="Associate Professor Dr. Chin Pei Yee",
        company="KEMENTERIAN PELANCONGAN, KEBUDAYAAN DAN ALAM SEKITAR",
        title="DEPUTY HEAD OF INVESTMENT DEVELOPMENT DIVISION",
        ticket_type="VIP",
    )

    mock_data_delegate = TicketPayload(
        name="Fiona Tan",
        company="Jesselton Pixel",
        title="Software Engineer",
        ticket_type="Delegate",
    )

    output_path_vip = Path("test_badge_vip.pdf")
    output_path_delegate = Path("test_badge_delegate.pdf")

    generate_ticket_pdf(output_path_vip, mock_data_vip)
    generate_ticket_pdf(output_path_delegate, mock_data_delegate)

    print(f"✅ Generated: {output_path_vip.resolve()}")
    print(f"✅ Generated: {output_path_delegate.resolve()}")
