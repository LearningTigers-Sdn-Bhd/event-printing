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

def calculate_layout_spacing(name_lines_count: int, company_lines_count: int, title_lines_count: int):
    """
    Dynamically calculates spacing based on total content to prevent overlap with ticket type.
    Returns: (name_line_spacing, section_spacing, line_spacing)
    """
    total_lines = name_lines_count + company_lines_count + title_lines_count
    
    # Default spacings (for short content)
    name_line_spacing = 0.4 * inch
    section_spacing = 0.4 * inch  # Space between name and company
    line_spacing = 0.2 * inch  # Space between company/title lines
    
    # Adjust based on total content length - increased line spacing to prevent overlap
    if total_lines >= 12:  # Super extreme content
        name_line_spacing = 0.20 * inch
        section_spacing = 0.18 * inch
        line_spacing = 0.23 * inch  # Increased a bit more for perfect spacing
    elif total_lines >= 10:  # Extremely long content
        name_line_spacing = 0.22 * inch
        section_spacing = 0.20 * inch
        line_spacing = 0.23 * inch  # Increased a bit more for perfect spacing
    elif total_lines >= 8:  # Very long content
        name_line_spacing = 0.26 * inch
        section_spacing = 0.22 * inch
        line_spacing = 0.23 * inch  # Increased a bit more for perfect spacing
    elif total_lines >= 6:  # Long content
        name_line_spacing = 0.35 * inch
        section_spacing = 0.35 * inch
        line_spacing = 0.25 * inch
    elif total_lines >= 5:  # Medium-long content
        name_line_spacing = 0.35 * inch
        section_spacing = 0.35 * inch
        line_spacing = 0.18 * inch
    
    return name_line_spacing, section_spacing, line_spacing


def generate_ticket_pdf(path: Path, data: TicketPayload):
    """
    Generates an event badge PDF with all-caps text and auto-wrapped lines.
    Dynamically adjusts spacing to prevent overlap with fixed ticket type.
    """
    # Badge size (H, W)
    h, w = 5.7 * inch, 4.15 * inch
    c = canvas.Canvas(str(path), pagesize=(w, h))

    # Margins and layout constants
    side_margin = 0.3 * inch
    max_text_width = w - (2 * side_margin)
    
    # Fixed positions
    ticket_type_y = 1.40 * inch  # Fixed position for ticket type
    min_gap = 0.15 * inch  # Minimum gap between title and ticket type
    
    # --- PRE-CALCULATE all content to determine spacing ---
    
    # 1. Get name lines
    name_font_size, name_lines = get_name_lines(data.name)
    
    # 2. Get company lines with progressive font sizing
    font_name_company = "Helvetica"
    font_size_company = 15
    company_lines = wrap_text_to_width(data.company, font_name_company, font_size_company, max_text_width)
    
    # Progressive font reduction for company - very aggressive for extreme cases
    if len(company_lines) > 5:
        font_size_company = 6  # Even smaller for extreme cases
        company_lines = wrap_text_to_width(data.company, font_name_company, font_size_company, max_text_width)
    elif len(company_lines) > 4:
        font_size_company = 6
        company_lines = wrap_text_to_width(data.company, font_name_company, font_size_company, max_text_width)
    elif len(company_lines) > 3:
        font_size_company = 12
        company_lines = wrap_text_to_width(data.company, font_name_company, font_size_company, max_text_width)
    elif len(company_lines) > 2:
        font_size_company = 13
        company_lines = wrap_text_to_width(data.company, font_name_company, font_size_company, max_text_width)
    
    # 3. Get title lines with progressive font sizing
    font_name_title = "Helvetica-Oblique"
    font_size_title = 14
    title_lines = wrap_text_to_width(data.title, font_name_title, font_size_title, max_text_width)
    
    # Progressive font reduction for title - very aggressive for extreme cases
    if len(title_lines) > 5:
        font_size_title = 6  # Even smaller for extreme cases
        title_lines = wrap_text_to_width(data.title, font_name_title, font_size_title, max_text_width)
    elif len(title_lines) > 4:
        font_size_title = 6
        title_lines = wrap_text_to_width(data.title, font_name_title, font_size_title, max_text_width)
    elif len(title_lines) > 3:
        font_size_title = 11
        title_lines = wrap_text_to_width(data.title, font_name_title, font_size_title, max_text_width)
    elif len(title_lines) > 2:
        font_size_title = 12
        title_lines = wrap_text_to_width(data.title, font_name_title, font_size_title, max_text_width)
    
    # Calculate dynamic spacing
    name_line_spacing, section_spacing, line_spacing = calculate_layout_spacing(
        len(name_lines), len(company_lines), len(title_lines)
    )
    
    # Adjust name line spacing based on font size - ensure proper spacing
    if name_font_size >= 20:
        # For larger fonts (20pt, 26pt), ensure adequate spacing between name lines
        name_line_spacing = max(name_line_spacing, 0.35 * inch)  # More spacing for larger text
    else:
        # For smaller fonts (14pt, 16pt), ensure minimum spacing
        name_line_spacing = max(name_line_spacing, 0.28 * inch)  # Minimum spacing for readability
    
    # --- CALCULATE total height needed ---
    total_height_needed = (
        (len(name_lines) * name_line_spacing) +  # Name section
        section_spacing +  # Gap after name
        (len(company_lines) * line_spacing) +  # Company section
        section_spacing * 0.5 +  # Gap after company
        (len(title_lines) * line_spacing)  # Title section
    )
    
    # Calculate starting Y position to ensure we don't overlap with ticket type
    available_height = h - 2.0 * inch - (ticket_type_y + 0.4 * inch + min_gap)
    
    if total_height_needed > available_height:
        # Content is too tall, need to compress further
        scale_factor = available_height / total_height_needed
        name_line_spacing *= scale_factor
        section_spacing *= scale_factor
        line_spacing *= scale_factor
    
    current_y = h - 2.1 * inch

    # --- RENDER: 1. Participant Name ---
    c.setFont("Helvetica-Bold", name_font_size)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    for i, line in enumerate(name_lines):
        line_y = current_y - (i * name_line_spacing)
        c.drawCentredString(w / 2, line_y, line)
    current_y -= (len(name_lines) * name_line_spacing) + section_spacing

    # --- RENDER: 2. Company Name ---
    c.setFont(font_name_company, font_size_company)
    for line in company_lines:
        c.drawCentredString(w / 2, current_y, line)
        current_y -= line_spacing
    current_y -= section_spacing * 0.5

    # --- RENDER: 3. Title ---
    c.setFont(font_name_title, font_size_title)
    for line in title_lines:
        c.drawCentredString(w / 2, current_y, line)
        current_y -= line_spacing

    # --- RENDER: 4. Ticket Type (Fixed Position) ---
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(w / 2, ticket_type_y, data.ticket_type.upper())

    # Save PDF
    c.showPage()
    c.save()