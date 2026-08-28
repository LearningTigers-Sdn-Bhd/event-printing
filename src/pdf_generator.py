from pathlib import Path
from datetime import datetime
import io
import qrcode
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

from models import TicketPayload # Import the model
from config_store import DEFAULT_LAYOUT
import config_store

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

def _balanced_split(words, font_name, font_size, max_width):
    """Find the most balanced 2-line split that fits both lines under max_width."""
    best_split = None
    best_score = float("inf")
    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        w1 = stringWidth(line1, font_name, font_size)
        w2 = stringWidth(line2, font_name, font_size)
        if w1 <= max_width and w2 <= max_width:
            score = abs(w1 - w2)
            if score < best_score:
                best_score = score
                best_split = (line1, line2)
    return best_split


def get_name_lines_for_width(name: str, max_width: float, font_name: str = "Helvetica-Bold"):
    """
    Prefers the largest possible font size, even if that means wrapping
    onto two lines. Iterates per size: tries single line, then a
    balanced two-line split, before falling back to the next smaller size.
    """
    name_upper = name.upper().strip()
    words = name_upper.split()

    for font_size in [26, 24, 22, 20, 18, 16, 14, 12]:
        if stringWidth(name_upper, font_name, font_size) <= max_width:
            return font_size, [name_upper]
        if len(words) >= 2:
            split = _balanced_split(words, font_name, font_size, max_width)
            if split:
                return font_size, list(split)

    return 11, wrap_text_to_width(name_upper, font_name, 11, max_width)


def get_role_lines_for_width(role: str, max_width: float, font_name: str = "Helvetica-Bold"):
    """
    Same large-first wrapping strategy as the name, scaled for the
    ticket type/role line.
    """
    role_upper = role.upper().strip()
    words = role_upper.split()

    for font_size in [22, 20, 18, 16, 14, 12]:
        if stringWidth(role_upper, font_name, font_size) <= max_width:
            return font_size, [role_upper]
        if len(words) >= 2:
            split = _balanced_split(words, font_name, font_size, max_width)
            if split:
                return font_size, list(split)

    return 11, wrap_text_to_width(role_upper, font_name, 11, max_width)


def normalize_role_text(role_text: str) -> str:
    role_text_lower = role_text.lower()
    if "conference" in role_text_lower or "delegate" in role_text_lower:
        return "DELEGATE"
    return role_text


def generate_qr_image(data: str) -> ImageReader:
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _shrink_wrap(text: str, font_name: str, max_width: float):
    """Company-style shrink: 13pt, then 11, then 9 as line count grows."""
    font_size = 13
    lines = wrap_text_to_width(text, font_name, font_size, max_width)
    if len(lines) > 3:
        font_size = 9
        lines = wrap_text_to_width(text, font_name, font_size, max_width)
    elif len(lines) > 2:
        font_size = 11
        lines = wrap_text_to_width(text, font_name, font_size, max_width)
    return font_size, lines


# Auto-fit bounds for sparse badges. Growth stops well before the edges:
# the block tops out at a share of badge height, lines keep margin from the
# sides, and growing never adds wrap lines (re-wrapping reads worse than
# slightly smaller type).
_FIT_FILL_TARGET = 0.80
_FIT_WIDTH_LIMIT = 0.92
_SCALE_STEP = 0.05

# Absolute per-element ceilings for auto-fit growth. Sparse badges (few
# fields) would otherwise balloon to fill the height budget — a two-field
# badge reading "VVIP" at poster size. Caps keep the visual hierarchy:
# name largest, then role, then supporting fields.
_ELEMENT_GROWTH_CAPS = {"name": 44, "role": 36, "table_no": 30}
_ELEMENT_GROWTH_CAP_DEFAULT = 20


def _text_for_element(el: str, data: TicketPayload):
    """Returns the text content for a layout element, or None to skip."""
    if el == "name":
        return data.name
    if el == "role":
        return normalize_role_text(data.ticket_type or "")
    if el == "company":
        return data.company
    if el == "title":
        return data.title
    if el == "country":
        return data.country
    if el == "table_no":
        return f"TABLE {data.table_no}" if data.table_no else None
    if el.startswith("custom_"):
        return (data.custom or {}).get(el)
    return None


def _lines_at_size(text: str, font: str, size: float, max_width: float, line_budget: int):
    """
    Re-wraps text at an arbitrary size using at most line_budget lines —
    growth must never add wrap lines (re-wrapping reads worse than
    slightly smaller type). Returns None when it can't stay in budget.
    """
    upper = text.upper().strip()
    if stringWidth(upper, font, size) <= max_width:
        return [upper]
    words = upper.split()
    if len(words) >= 2 and line_budget >= 2:
        split = _balanced_split(words, font, size, max_width)
        if split:
            return list(split)
    if line_budget >= 1 and words:
        widest = max(stringWidth(w, font, size) for w in words)
        if widest <= max_width:
            return wrap_text_to_width(upper, font, size, max_width)
    return None


def _gap_between(prev: dict, cur: dict) -> float:
    """Modest breathing room around QR codes."""
    if prev["kind"] == "qr" or cur["kind"] == "qr":
        return 0.12 * inch
    return 0.07 * inch


def _block_height(items) -> float:
    total = 0.0
    for i, it in enumerate(items):
        if i:
            total += _gap_between(items[i - 1], it)
        total += it["size"] if it["kind"] == "qr" else len(it["lines"]) * it["line_h"]
    return total


# Overflow handling: when natural content exceeds the badge, the QR code
# shrinks first (it stays scannable much below its 1.15in natural size),
# then text steps down. QR never goes below _QR_MIN — data density matters.
_QR_NATURAL = 1.15 * inch
_QR_MIN = 0.55 * inch
_FIT_SAFETY = 0.03 * inch  # keeps glyph edges off the paper edge


def _shrink_to_fit(items, usable_h: float):
    """
    Overflow pass: when the block is taller than the usable badge height,
    shrink the QR first (floor _QR_MIN), then the largest text one point
    at a time. Existing line splits are kept — a smaller size always fits
    the same wraps, so height decreases monotonically.
    """
    for _ in range(400):
        if _block_height(items) <= usable_h:
            return
        qr = next((it for it in items if it["kind"] == "qr" and it["size"] > _QR_MIN), None)
        if qr is not None:
            qr["size"] = max(_QR_MIN, qr["size"] - 0.05 * inch)
            continue
        text_items = [it for it in items if it["kind"] == "text" and it["size"] > 8]
        if not text_items:
            return  # nothing left to shrink; render clipped rather than vanish
        biggest = max(text_items, key=lambda it: it["size"])
        biggest["size"] = max(8.0, biggest["size"] - 1.0)
        biggest["line_h"] = (biggest["size"] + 3) / 72 * inch


def _auto_fit_scale(items, data: TicketPayload, h: float, max_text_width: float):
    """
    Sparse-badge auto-fit: when the natural-size content leaves lots of
    slack, grow the type until the block fills a target share of the
    badge height. Guardrails: the block stops at _FIT_FILL_TARGET of the
    height, every line keeps _FIT_WIDTH_LIMIT of the text width, each
    element stops at its growth cap (scaled by the user's size setting),
    and a step is rolled back if it would add wrap lines or overflow.
    """
    text_items = [it for it in items if it["kind"] == "text"]
    if not text_items:
        return
    height_budget = h * _FIT_FILL_TARGET

    def _cap_for(it):
        base = _ELEMENT_GROWTH_CAPS.get(it["el"], _ELEMENT_GROWTH_CAP_DEFAULT)
        return base * it.get("scale", 1.0)

    while _block_height(items) < height_budget:
        grew = False
        trial = []
        for it in items:
            if it["kind"] != "text" or it["size"] >= _cap_for(it):
                trial.append(it)  # QRs never grow; capped elements are done
                continue
            grown = min(it["size"] * (1 + _SCALE_STEP), _cap_for(it))
            text = _text_for_element(it["el"], data)
            lines = _lines_at_size(text, it["font"], grown, max_text_width, len(it["lines"]))
            width_ok = lines and all(
                stringWidth(line, it["font"], grown) <= max_text_width * _FIT_WIDTH_LIMIT
                for line in lines
            )
            if not width_ok:
                trial.append(it)  # this element is done growing
                continue
            grew = True
            trial.append({**it, "size": grown, "lines": lines,
                          "line_h": (grown + 3) / 72 * inch, "scale": it.get("scale", 1.0)})
        if not grew:
            break
        if _block_height(trial) > height_budget:
            break
        items[:] = trial


def _measure_element(el: str, data: TicketPayload, max_width: float, scale: float = 1.0, bold=None):
    """
    Measures one layout element. Returns a render item dict or None if
    the element has no content for this ticket.
    Text item: {kind: 'text', font, size, lines, line_h, el, cap}
    QR item:   {kind: 'qr', size}
    `scale` is a user-set size multiplier (1.0 = auto default). For text
    it scales the base font and the width budget together so the natural
    wrap structure is preserved; auto-fit growth caps scale along so the
    relative hierarchy the user picked survives the grow pass.
    `bold` is a user-set weight override: True forces Helvetica-Bold,
    False forces Helvetica, None keeps the element's built-in default
    (name/role/table_no bold, everything else normal).
    """
    if el == "qr":
        return {"kind": "qr", "size": _QR_NATURAL * scale, "el": "qr"}

    text = _text_for_element(el, data)
    if not text:
        return None

    fit_width = max_width / scale  # grow the box with the type: same wraps, bigger glyphs

    if bold is None:
        bold = el in ("name", "role", "table_no")
    font = "Helvetica-Bold" if bold else "Helvetica"

    if el == "name":
        size, lines = get_name_lines_for_width(text, fit_width, font)
    elif el in ("role", "table_no"):
        size, lines = get_role_lines_for_width(text, fit_width, font)
    else:  # company, title, country, custom fields
        size, lines = _shrink_wrap(text, font, fit_width)

    if not lines:
        return None
    size *= scale
    line_h = (size + 3) / 72 * inch
    return {"kind": "text", "font": font, "size": size, "lines": lines, "line_h": line_h, "el": el}


def generate_ticket_pdf(path: Path, data: TicketPayload, layout: dict = None):
    """
    Renders the badge from a layout config: paper size in mm plus an
    ordered list of elements. Falls back to the persisted config, then
    to DEFAULT_LAYOUT.
    """
    if layout is None:
        layout = config_store.load().get("layout") or DEFAULT_LAYOUT

    paper = layout.get("paper") or DEFAULT_LAYOUT["paper"]
    elements = layout.get("elements") or DEFAULT_LAYOUT["elements"]
    element_scales = layout.get("element_scales") or {}
    element_bolds = layout.get("element_bolds") or {}
    element_offsets = layout.get("element_offsets") or {}
    try:
        vertical_offset_mm = float(layout.get("vertical_offset_mm") or 0.0)
    except (TypeError, ValueError):
        vertical_offset_mm = 0.0

    w = float(paper["width_mm"]) / 25.4 * inch
    h = float(paper["height_mm"]) / 25.4 * inch
    c = canvas.Canvas(str(path), pagesize=(w, h))

    side_margin = 0.2 * inch
    max_text_width = w - (2 * side_margin)
    bottom_margin = 0.06 * inch

    # --- Measure ---
    items = []
    for el in elements:
        scale = element_scales.get(el, 1.0)
        item = _measure_element(el, data, max_text_width, scale=scale,
                                bold=element_bolds.get(el))
        if item:
            item["scale"] = scale
            items.append(item)

    _auto_fit_scale(items, data, h, max_text_width)
    _shrink_to_fit(items, h - bottom_margin - _FIT_SAFETY)

    block_h = _block_height(items)
    usable_h = h - bottom_margin
    # Center the block in the usable area above the bottom margin — the
    # block's lowest ink never crosses the bottom margin line. Then apply
    # the user's vertical offset: positive pushes content down (gap at the
    # top), negative pulls it up (gap at the bottom). Clamped so the block
    # never slides off the paper.
    if block_h >= usable_h:
        start_y = h  # shrink pass already handled this; clamp defensively
    else:
        start_y = bottom_margin + (usable_h + block_h) / 2
    if vertical_offset_mm:
        shift = vertical_offset_mm / 25.4 * inch
        start_y -= shift  # PDF origin is bottom-left: subtract to move down
        # Keep the whole block on the paper: top never above h, bottom never
        # below bottom_margin.
        start_y = max(bottom_margin + block_h, min(h, start_y))

    # --- Render ---
    current_y = start_y
    c.setFillColorRGB(0, 0, 0)  # pure black: printer is 1-bit, any grey gets halftone-dithered into dots
    for i, item in enumerate(items):
        if i > 0:
            current_y -= _gap_between(items[i - 1], item)
        # Position nudge from the layout editor: applied only at the draw
        # call, never to current_y, so moving one element never shoves
        # the ones after it.
        offset = element_offsets.get(item["el"], {})
        dx = offset.get("dx_mm", 0) / 25.4 * inch
        dy = offset.get("dy_mm", 0) / 25.4 * inch
        if item["kind"] == "qr":
            qr_size = item["size"]
            qr_img = generate_qr_image(data.ticket_id)
            c.drawImage(qr_img, (w - qr_size) / 2 + dx, current_y - qr_size + dy,
                        width=qr_size, height=qr_size)
            current_y -= qr_size
        else:
            c.setFont(item["font"], item["size"])
            for line in item["lines"]:
                c.drawCentredString(w / 2 + dx, current_y - item["line_h"] + dy, line)
                current_y -= item["line_h"]

    c.showPage()
    c.save()
