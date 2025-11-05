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
    
    # If still doesn't fit, use smaller font and wrap
    font_size = 16
    lines = wrap_text_to_width(name_upper, font_name, font_size, max_width)
    return font_size, lines

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
    current_y = h - 2.0 * inch

    # --- 1. Participant Name ---
    font_size, name_lines = get_name_lines(data.name)
    # Increased line spacing for better readability when names are split across lines
    if font_size >= 20:
        line_spacing = 0.4 * inch  # Increased from 0.3 inch
    else:
        line_spacing = 0.35 * inch  # Increased from 0.25 inch
    
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
    bottom_y = 1.40 * inch
    c.drawCentredString(w / 2, bottom_y, data.ticket_type.upper())

    # Save PDF
    c.showPage()
    c.save()