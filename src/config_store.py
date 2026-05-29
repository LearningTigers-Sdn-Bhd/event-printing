"""Cross-platform persistent config store for backend integration settings."""
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_APP_NAME = "event-printer"


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
    }


def load() -> Dict[str, Any]:
    path = config_path()
    data = _defaults()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                stored = json.load(f) or {}
            for key in data:
                if key in stored and isinstance(stored[key], str):
                    data[key] = stored[key]
        except (OSError, json.JSONDecodeError):
            pass
    return data


def save(values: Dict[str, Any]) -> Dict[str, Any]:
    """Merge supplied values with existing config, write atomically with secure perms."""
    current = load()
    for key in ("backend_url", "event_slug", "api_key"):
        if key in values and isinstance(values[key], str):
            current[key] = values[key].strip()

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
    }
