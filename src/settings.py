import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# When bundled with PyInstaller, load .env from the exe's directory
if getattr(sys, 'frozen', False):
    _base_dir = Path(sys.executable).parent
else:
    _base_dir = Path(__file__).parent.parent

load_dotenv(_base_dir / ".env")


def _auto_detect_printer() -> str:
    """
    Auto-detect printer. Priority:
    1. PRINTER_NAME env var (manual override)
    2. Only one printer available → use it
    3. System default printer
    4. First available printer
    """
    import platform
    import subprocess
    import re

    # Manual override
    env_printer = os.getenv("PRINTER_NAME", "").strip()
    if env_printer:
        return env_printer

    is_windows = platform.system() == "Windows"

    if is_windows:
        try:
            import win32print
            printers = [p[2] for p in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )]
            if len(printers) == 1:
                return printers[0]
            default = win32print.GetDefaultPrinter()
            if default:
                return default
            return printers[0] if printers else ""
        except Exception:
            return ""
    else:
        try:
            # Get all printers
            out = subprocess.check_output(["lpstat", "-p"], text=True)
            printers = re.findall(r"^printer (\S+)", out, re.MULTILINE)
            if len(printers) == 1:
                return printers[0]
            # Try system default
            try:
                default_out = subprocess.check_output(["lpstat", "-d"], text=True)
                match = re.search(r"system default destination: (\S+)", default_out)
                if match:
                    return match.group(1)
            except Exception:
                pass
            return printers[0] if printers else ""
        except Exception:
            return ""


PRINTER_NAME = _auto_detect_printer()
_raw_output_dir = Path(os.getenv("OUTPUT_DIR", "out"))
if not _raw_output_dir.is_absolute():
    _raw_output_dir = _base_dir / _raw_output_dir
OUTPUT_DIR = str(_raw_output_dir)
PORT = int(os.getenv("PORT", "8000"))


class _Settings:
    def __init__(self):
        self.PRINTER_NAME = PRINTER_NAME
        self.OUTPUT_DIR = OUTPUT_DIR
        self.PORT = PORT


settings = _Settings()


def ensure_outdir():
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
