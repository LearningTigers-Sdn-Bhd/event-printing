import subprocess
import re
from typing import Dict, Any, Optional

from settings import settings # Import settings

def print_via_lp(file_path: str, printer_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends a file to the printer using the 'lp' command.
    """
    printer = printer_name or settings.PRINTER_NAME
    if not printer:
        # Instead of a bare RuntimeError, use an HTTPException in the FastAPI route 
        # but this internal function raises a base Exception to be caught higher up.
        raise Exception("PRINTER_NAME not set. Set it in .env or environment.")

    try:  # Corrected indentation: aligned with 'if'
        # The '-d' flag specifies the destination printer
        out = subprocess.check_output(["lp", "-d", printer, file_path], text=True)
        
        # Parse the job ID from the output
        m = re.search(r"request id is (\S+)", out)
        job_id = m.group(1) if m else out.strip()
        
        return {"job_id": job_id, "raw": out}
    except subprocess.CalledProcessError as e:
        # This occurs if the 'lp' command returns a non-zero exit code (e.g., printer is down)
        return {"error": str(e), "output:": e.output}
    except FileNotFoundError:
        # This occurs if the 'lp' command itself is not found (CUPS not installed/in PATH)
        return {"error": "The 'lp' command was not found. Is CUPS installed?"}


# Corrected indentation: Unindented to be a top-level function
def list_cups_printers() -> str:
    """
    Lists available CUPS printers using the 'lpstat -p' command.
    """
    out = subprocess.check_output(["lpstat", "-p"], text=True)
    return out