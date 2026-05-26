from pathlib import Path
from datetime import datetime
import io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

from models import TicketPayload # Import the model

def generate_test_pdf(path: Path) -> str:
    """Generates a simple test PDF file for printer pipeline dry run."""
    PAGE_SIZE = (5.7 * inch, 4.1 * inch)
    c = canvas.Canvas(str(path), pagesize=PAGE_SIZE)
    w, h = PAGE_SIZE
    
    # Simple Content
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, h - 0.5 * inch, "Event Badge — TEST")
    c.setFont("Helvetica", 10)
    c.drawString(0.5 * inch, h - 1.0 * inch, f"Generated at: {datetime.now().isoformat(timespec='seconds')}")
    c.rect(0.2 * inch, 0.2 * inch, w - 0.4 * inch, h - 0.4 * inch) # Border
    
    c.showPage()
    c.save()
    return str(path)

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
    Uses balanced line splitting - aims for at least 2 words per line when possible.
    """
    name_upper = name.upper().strip()
    
    # Try single line with large font first
    font_size = 26
    font_name = "Helvetica-Bold"
    max_width = 3.55 * inch  # Max width for name (badge width minus margins)
    
    if stringWidth(name_upper, font_name, font_size) <= max_width:
        return font_size, [name_upper]
    
    # Try two lines with medium font
    font_size = 20
    words = name_upper.split()
    
    # Strategy: Try to split with at least 2 words per line for better balance
    # Find the split that creates the most balanced line lengths
    best_split = None
    best_balance_score = float('inf')
    
    for i in range(2, len(words)):  # Start from 2 to ensure minimum 2 words on first line
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        
        # Check if both lines fit
        width1 = stringWidth(line1, font_name, font_size)
        width2 = stringWidth(line2, font_name, font_size)
        
        if width1 <= max_width and width2 <= max_width:
            # Calculate balance score (lower is better)
            # Prefer more balanced line lengths
            balance_score = abs(width1 - width2)
            
            if balance_score < best_balance_score:
                best_balance_score = balance_score
                best_split = (line1, line2)
    
    # If we found a good split, use it
    if best_split:
        return font_size, [best_split[0], best_split[1]]
    
    # Fallback: try any valid split (even single word on first line)
    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        if (stringWidth(line1, font_name, font_size) <= max_width and 
            stringWidth(line2, font_name, font_size) <= max_width):
            return font_size, [line1, line2]
    
    # If still doesn't fit with 20pt, try 16pt
    font_size = 16
    lines = wrap_text_to_width(name_upper, font_name, font_size, max_width)
    
    # If still too many lines (>3), try even smaller font
    if len(lines) > 3:
        font_size = 14
        lines = wrap_text_to_width(name_upper, font_name, font_size, max_width)
    
    return font_size, lines

def get_name_lines_for_width(name: str, max_width: float):
    name_upper = name.upper().strip()
    font_name = "Helvetica-Bold"

    for font_size in [20, 16, 13, 11]:
        if stringWidth(name_upper, font_name, font_size) <= max_width:
            return font_size, [name_upper]

    for font_size in [16, 13, 11]:
        words = name_upper.split()
        for i in range(1, len(words)):
            line1 = " ".join(words[:i])
            line2 = " ".join(words[i:])
            if (stringWidth(line1, font_name, font_size) <= max_width and
                    stringWidth(line2, font_name, font_size) <= max_width):
                return font_size, [line1, line2]

    lines = wrap_text_to_width(name_upper, font_name, 10, max_width)
    return 10, lines


def generate_qr_image(data: str) -> ImageReader:
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def generate_ticket_pdf(path: Path, data: TicketPayload):
    # Sticker size: 100mm x 80mm
    w, h = 100 / 25.4 * inch, 80 / 25.4 * inch
    c = canvas.Canvas(str(path), pagesize=(w, h))

    side_margin = 0.2 * inch
    max_text_width = w - (2 * side_margin)

    # --- Pre-calculate content ---
    name_font_size, name_lines = get_name_lines_for_width(data.name, max_text_width)

    font_name_company = "Helvetica"
    font_size_company = 10
    company_lines = wrap_text_to_width(data.company or "", font_name_company, font_size_company, max_text_width)
    if len(company_lines) > 3:
        font_size_company = 7
        company_lines = wrap_text_to_width(data.company or "", font_name_company, font_size_company, max_text_width)
    elif len(company_lines) > 2:
        font_size_company = 8
        company_lines = wrap_text_to_width(data.company or "", font_name_company, font_size_company, max_text_width)

    role_font_size = 16
    qr_size = 0.85 * inch
    qr_box_pad = 0.02 * inch  # tight padding inside QR box
    qr_box_size = qr_size + 2 * qr_box_pad

    name_line_h = (name_font_size + 3) / 72 * inch
    company_line_h = (font_size_company + 3) / 72 * inch
    role_line_h = (role_font_size + 3) / 72 * inch
    gap = 0.14 * inch  # padding between sections

    total_h = (
        len(name_lines) * name_line_h +
        gap +
        len(company_lines) * company_line_h +
        gap +
        qr_box_size +
        gap +
        role_line_h
    )

    # Center block vertically
    start_y = (h + total_h) / 2

    current_y = start_y

    # --- RENDER: 1. Name ---
    c.setFont("Helvetica-Bold", name_font_size)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    for line in name_lines:
        c.drawCentredString(w / 2, current_y - name_line_h, line)
        current_y -= name_line_h
    current_y -= gap

    # --- RENDER: 2. Company ---
    c.setFont(font_name_company, font_size_company)
    for line in company_lines:
        c.drawCentredString(w / 2, current_y - company_line_h, line)
        current_y -= company_line_h
    current_y -= gap

    # --- RENDER: 3. QR box + QR ---
    qr_box_x = (w - qr_box_size) / 2
    qr_box_y = current_y - qr_box_size
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(0.5)
    c.rect(qr_box_x, qr_box_y, qr_box_size, qr_box_size)
    qr_img = generate_qr_image(data.ticket_id)
    c.drawImage(qr_img, qr_box_x + qr_box_pad, qr_box_y + qr_box_pad, width=qr_size, height=qr_size)
    current_y = qr_box_y - gap

    # --- RENDER: 4. Role ---
    c.setFont("Helvetica-Bold", role_font_size)
    c.drawCentredString(w / 2, current_y - role_line_h, data.ticket_type.upper())

    c.showPage()
    c.save()