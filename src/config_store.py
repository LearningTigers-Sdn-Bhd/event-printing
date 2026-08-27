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
}


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
    return {
        "paper": {"width_mm": width_mm, "height_mm": height_mm},
        "elements": elements,
        "custom_fields": custom_fields,
    }


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
    }
