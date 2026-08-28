"""Cross-platform persistent config store for backend integration settings."""
import json
import os
import platform
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_APP_NAME = "event-printer"

VALID_ELEMENTS = ("name", "role", "company", "title", "country", "table_no", "qr")

CUSTOM_FIELD_ID_PREFIX = "custom_"
MAX_CUSTOM_FIELDS = 6

DEFAULT_BADGE_TYPES = [
    "Visitor", "Delegate", "Speaker", "Moderator", "Student",
    "Staff", "Organizer", "Exhibitor", "VIP", "VVIP",
]
MAX_BADGE_TYPES = 30

DEFAULT_LAYOUT = {
    "paper": {"width_mm": 100.0, "height_mm": 80.0},
    "elements": ["name", "role", "company", "qr"],
    "element_scales": {},
    "vertical_offset_mm": 0.0,
}

# Per-element size multipliers (relative to the auto-fit size). 1.0 = default.
MIN_ELEMENT_SCALE = 0.5
MAX_ELEMENT_SCALE = 2.0

# Per-element position nudge, millimeters from the auto-computed spot. 0 = default.
MAX_ELEMENT_OFFSET_MM = 10.0

MAX_LAYOUT_PRESETS = 20
MAX_PRESET_NAME_LEN = 40

# Vertical shift of the whole content block, in mm. Positive pushes the
# block down (adds a gap at the top); negative pulls it up (gap at the
# bottom). 0 keeps the default centered position.
MIN_VERTICAL_OFFSET_MM = -80.0
MAX_VERTICAL_OFFSET_MM = 80.0


def _sanitize_vertical_offset(value: Any) -> float:
    """Validates a vertical offset in mm; returns 0.0 on anything unusable."""
    try:
        offset = float(value)
    except (TypeError, ValueError):
        return 0.0
    if abs(offset) < 1e-9:
        return 0.0  # 0 is the default; storing it adds noise
    return round(min(MAX_VERTICAL_OFFSET_MM, max(MIN_VERTICAL_OFFSET_MM, offset)), 1)


def _sanitize_element_scales(value: Any, known_elements: set) -> Dict[str, float]:
    """Validates {element_id: scale}; drops unknown ids and out-of-range values."""
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for el, raw in value.items():
        if not isinstance(el, str) or el not in known_elements:
            continue
        try:
            scale = float(raw)
        except (TypeError, ValueError):
            continue
        if abs(scale - 1.0) < 1e-9:
            continue  # 1.0 is the default; storing it adds noise
        result[el] = round(min(MAX_ELEMENT_SCALE, max(MIN_ELEMENT_SCALE, scale)), 2)
    return result


def _sanitize_element_offsets(value: Any, known_elements: set) -> Dict[str, Dict[str, float]]:
    """Validates {element_id: {dx_mm, dy_mm}}; drops unknown ids and clamps range."""
    if not isinstance(value, dict):
        return {}
    result: Dict[str, Dict[str, float]] = {}
    for el, raw in value.items():
        if not isinstance(el, str) or el not in known_elements or not isinstance(raw, dict):
            continue
        try:
            dx = float(raw.get("dx_mm", 0))
            dy = float(raw.get("dy_mm", 0))
        except (TypeError, ValueError):
            continue
        dx = round(min(MAX_ELEMENT_OFFSET_MM, max(-MAX_ELEMENT_OFFSET_MM, dx)), 1)
        dy = round(min(MAX_ELEMENT_OFFSET_MM, max(-MAX_ELEMENT_OFFSET_MM, dy)), 1)
        if dx == 0 and dy == 0:
            continue  # (0, 0) is the default; storing it adds noise
        result[el] = {"dx_mm": dx, "dy_mm": dy}
    return result


def _sanitize_badge_types(value: Any) -> Optional[list]:
    """Validates a badge type list; trims, dedupes, caps count. None if empty."""
    if not isinstance(value, list):
        return None
    result: list = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()[:40]
        if text and text.lower() not in (t.lower() for t in result):
            result.append(text)
        if len(result) >= MAX_BADGE_TYPES:
            break
    return result or None


def new_custom_field_id() -> str:
    """Generates a unique layout element id like custom_a1b2c3."""
    return f"{CUSTOM_FIELD_ID_PREFIX}{uuid.uuid4().hex[:6]}"


def _sanitize_custom_fields(value: Any) -> Dict[str, Dict[str, str]]:
    """Validates a custom field defs dict keyed by element id; drops invalid rows."""
    if not isinstance(value, dict):
        return {}
    result: Dict[str, Dict[str, str]] = {}
    for raw_id, raw_def in value.items():
        if not isinstance(raw_id, str) or not raw_id.startswith(CUSTOM_FIELD_ID_PREFIX):
            continue
        field_id = raw_id[: len(CUSTOM_FIELD_ID_PREFIX) + 12]
        if not isinstance(raw_def, dict):
            continue
        label = str(raw_def.get("label") or "").strip()[:60]
        if not label:
            continue
        backend_key = str(raw_def.get("backend_key") or "").strip()[:60]
        if field_id not in result:
            result[field_id] = {"label": label, "backend_key": backend_key}
    return dict(list(result.items())[:MAX_CUSTOM_FIELDS])


def sanitize_layout(value: Any) -> Optional[Dict[str, Any]]:
    """Public wrapper around _sanitize_layout for use by preview endpoints."""
    return _sanitize_layout(value)


def _sanitize_layout(value: Any) -> Optional[Dict[str, Any]]:
    """Validate a layout dict; returns normalized layout or None if invalid."""
    if not isinstance(value, dict):
        return None
    paper = value.get("paper")
    if not isinstance(paper, dict):
        return None
    try:
        width_mm = float(paper.get("width_mm"))
        height_mm = float(paper.get("height_mm"))
    except (TypeError, ValueError):
        return None
    if not (20 <= width_mm <= 500 and 20 <= height_mm <= 500):
        return None
    elements_raw = value.get("elements")
    if not isinstance(elements_raw, list):
        return None
    custom_fields = _sanitize_custom_fields(value.get("custom_fields"))
    elements = []
    for el in elements_raw:
        valid = isinstance(el, str) and (
            el in VALID_ELEMENTS or el in custom_fields
        )
        if isinstance(el, str) and valid and el not in elements:
            elements.append(el)
    if not elements:
        return None
    known = set(VALID_ELEMENTS) | set(custom_fields)
    return {
        "paper": {"width_mm": width_mm, "height_mm": height_mm},
        "elements": elements,
        "custom_fields": custom_fields,
        "element_scales": _sanitize_element_scales(value.get("element_scales"), known),
        "element_offsets": _sanitize_element_offsets(value.get("element_offsets"), known),
        "vertical_offset_mm": _sanitize_vertical_offset(value.get("vertical_offset_mm")),
    }


def _sanitize_layout_presets(value: Any) -> Dict[str, Dict[str, Any]]:
    """Validates {preset_name: layout}; drops invalid entries, caps count."""
    if not isinstance(value, dict):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for raw_name, raw_layout in value.items():
        if not isinstance(raw_name, str):
            continue
        name = raw_name.strip()[:MAX_PRESET_NAME_LEN]
        if not name:
            continue
        layout = _sanitize_layout(raw_layout)
        if layout:
            result[name] = layout
        if len(result) >= MAX_LAYOUT_PRESETS:
            break
    return result


def _sanitize_active_preset(value: Any, presets: Dict[str, Any]) -> Optional[str]:
    if isinstance(value, str) and value in presets:
        return value
    return None


def _config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / _APP_NAME
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / _APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / _APP_NAME


def config_path() -> Path:
    return _config_dir() / "config.json"


def _defaults() -> Dict[str, Any]:
    return {
        "backend_url": os.environ.get("EVENTZ_BACKEND_URL", ""),
        "event_slug": os.environ.get("EVENTZ_EVENT_SLUG", ""),
        "api_key": os.environ.get("EVENTZ_API_KEY", ""),
        "badge_types": list(DEFAULT_BADGE_TYPES),
        "layout": json.loads(json.dumps(DEFAULT_LAYOUT)),
        "layout_presets": {},
        "active_preset": None,
    }


def load() -> Dict[str, Any]:
    path = config_path()
    data = _defaults()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                stored = json.load(f) or {}
            for key in ("backend_url", "event_slug", "api_key"):
                if key in stored and isinstance(stored[key], str):
                    data[key] = stored[key]
            badge_types = _sanitize_badge_types(stored.get("badge_types"))
            if badge_types:
                data["badge_types"] = badge_types
            layout = _sanitize_layout(stored.get("layout"))
            if layout:
                data["layout"] = layout
            presets = _sanitize_layout_presets(stored.get("layout_presets"))
            data["layout_presets"] = presets
            data["active_preset"] = _sanitize_active_preset(stored.get("active_preset"), presets)
        except (OSError, json.JSONDecodeError):
            pass
    return data


def save(values: Dict[str, Any]) -> Dict[str, Any]:
    """Merge supplied values with existing config, write atomically with secure perms."""
    current = load()
    for key in ("backend_url", "event_slug", "api_key"):
        if key in values and isinstance(values[key], str):
            current[key] = values[key].strip()
    if "badge_types" in values:
        badge_types = _sanitize_badge_types(values["badge_types"])
        if badge_types:
            current["badge_types"] = badge_types
    if "layout" in values:
        layout = _sanitize_layout(values["layout"])
        if layout:
            current["layout"] = layout
    if "layout_presets" in values:
        current["layout_presets"] = _sanitize_layout_presets(values["layout_presets"])
    if "active_preset" in values:
        current["active_preset"] = _sanitize_active_preset(values["active_preset"], current["layout_presets"])

    path = config_path()
    # Create dir with 0700 so only owner can list/read it
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass

    tmp = path.with_suffix(".tmp")
    # Write with 0600 from creation — no race window
    if sys.platform != "win32":
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
    else:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)

    os.replace(tmp, path)
    return current


def reset() -> None:
    """Clear all backend credentials from persistent config."""
    save({"backend_url": "", "event_slug": "", "api_key": ""})


def public_view(values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Returns config with api key masked for safe display in dashboard."""
    values = values if values is not None else load()
    masked_key = ""
    api_key = values.get("api_key", "")
    if api_key:
        masked_key = "•" * max(0, len(api_key) - 4) + api_key[-4:]
    return {
        "backend_url": values.get("backend_url", ""),
        "event_slug": values.get("event_slug", ""),
        "api_key_masked": masked_key,
        "api_key_set": bool(api_key),
        "config_path": str(config_path()),
        "badge_types": values.get("badge_types") or list(DEFAULT_BADGE_TYPES),
        "layout": values.get("layout") or json.loads(json.dumps(DEFAULT_LAYOUT)),
        "layout_presets": values.get("layout_presets") or {},
        "active_preset": values.get("active_preset"),
    }
