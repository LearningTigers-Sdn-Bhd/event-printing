import re
import sys
import os
import time
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from datetime import datetime
from pydantic import BaseModel

from settings import settings, ensure_outdir
from models import TicketPayload
from pdf_generator import generate_test_pdf, generate_ticket_pdf
from printer import print_via_lp, list_cups_printers, get_default_printer
import config_store
from api_client import BackendClient, BackendError, BackendAlreadyCheckedIn

app = FastAPI(title="Event Ticket Printer")

SERVER_STARTED_AT = time.time()

# Resolve static dir for both dev and PyInstaller bundled runs.
if getattr(sys, "frozen", False):
    _static_dir = Path(sys._MEIPASS) / "src" / "static"
else:
    _static_dir = Path(__file__).parent / "static"

# NEW: Custom exception handler to log 422 errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print("--- Pydantic Validation Error ---")
    # Log the detailed errors to your Uvicorn console
    print(exc.errors())
    print("-----------------------------------")
    # Return the standard 422 response
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# --- Dashboard ---

@app.get("/")
def dashboard():
    """Serves the dashboard HTML."""
    index_path = _static_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail=f"Dashboard not found at {index_path}")
    return FileResponse(str(index_path), media_type="text/html")


if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# --- Server control ---

@app.get("/server/status")
def server_status():
    """Server uptime + pid for the dashboard control panel."""
    return {
        "ok": True,
        "pid": os.getpid(),
        "uptime_seconds": int(time.time() - SERVER_STARTED_AT),
        "started_at": SERVER_STARTED_AT,
    }


@app.post("/server/restart")
def server_restart():
    """Re-execs the current process. Window stays open (pywebview keeps URL)."""
    def _do_restart():
        time.sleep(0.4)  # let the HTTP response flush first
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception:
            os._exit(0)
    threading.Thread(target=_do_restart, daemon=True).start()
    return {"ok": True, "action": "restart"}


@app.post("/server/quit")
def server_quit():
    """Hard-exit the process. Closes the pywebview window."""
    def _do_quit():
        time.sleep(0.4)
        os._exit(0)
    threading.Thread(target=_do_quit, daemon=True).start()
    return {"ok": True, "action": "quit"}


# --- Health and Status Endpoints ---

@app.get("/health")
def health():
    """Checks the application's basic configuration."""
    return {
        "ok": True,
        "printer": settings.PRINTER_NAME,
        "output_dir": settings.OUTPUT_DIR,
    }

@app.get("/printers")
def list_printers():
    """Lists available printers (cross-platform: CUPS on Mac/Linux, Windows API on Windows)."""
    try:
        out = list_cups_printers()
        default = get_default_printer()
        return {
            "raw": out,
            "default_printer": default,
            "configured_printer": settings.PRINTER_NAME
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list printers: {str(e)}")

# --- PDF Generation Endpoints ---

@app.post("/pdf-test")
def pdf_test():
    """Generates a test PDF file (no printing)."""
    ensure_outdir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = Path(settings.OUTPUT_DIR) / f"test-ticket-{ts}.pdf"
    path = generate_test_pdf(pdf_path)
    return {"ok": True, "pdf": path}

class PreviewPayload(BaseModel):
    """Ticket data plus an optional unsaved layout override for live preview."""
    ticket: TicketPayload
    layout: dict | None = None


def _preview_layout(override: dict | None) -> dict | None:
    """Sanitize an unsaved layout override; None falls back to saved config."""
    if not override:
        return None
    return config_store.sanitize_layout(override)


@app.post("/pdf-preview")
def pdf_preview(payload: PreviewPayload):
    """Generates badge PDF and returns it for browser preview (no printing)."""
    ensure_outdir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = Path(settings.OUTPUT_DIR) / f"preview-{payload.ticket.ticket_id}-{ts}.pdf"
    generate_ticket_pdf(pdf_path, payload.ticket, layout=_preview_layout(payload.layout))
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=pdf_path.name)


@app.post("/png-preview")
def png_preview(payload: PreviewPayload):
    """Generates badge PDF and returns it as a PNG for embedded preview."""
    import fitz
    from io import BytesIO
    from fastapi.responses import Response

    ensure_outdir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = Path(settings.OUTPUT_DIR) / f"preview-{payload.ticket.ticket_id}-{ts}.pdf"
    generate_ticket_pdf(pdf_path, payload.ticket, layout=_preview_layout(payload.layout))

    doc = fitz.open(str(pdf_path))
    page = doc[0]
    # 150 dpi = sharp on screen, small enough to be quick.
    zoom = 150 / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    buf = BytesIO(pix.tobytes("png"))
    doc.close()
    return Response(content=buf.getvalue(), media_type="image/png")

# --- Printing Endpoints ---

@app.post("/print-test")
def print_test():
    """Generates a test PDF and attempts to print it."""
    ensure_outdir()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    pdf_path = Path(settings.OUTPUT_DIR) / f"test-ticket-{ts}.pdf"
    
    # 1. Generate PDF
    generate_test_pdf(pdf_path)
    
    # 2. Print via lp using the configured single printer name
    try:
        job = print_via_lp(str(pdf_path), printer_name=settings.PRINTER_NAME)
        if "error" in job:
            raise HTTPException(status_code=500, detail=f"Printing failed: {job['error']}")
            
        return {"ok": True, "pdf": str(pdf_path), "print_job": job, "target_printer": settings.PRINTER_NAME}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/print-ticket")
def print_ticket(payload: TicketPayload):
    """
    Generates an event badge PDF and attempts to print it.
    Uses the single PRINTER_NAME defined in settings for simplified testing.
    """
    ensure_outdir()

    target_printer_name = settings.PRINTER_NAME
    ts = datetime.now().strftime("%Y%m%d %H%M%S")
    pdf_path = Path(settings.OUTPUT_DIR) / f"badge-{payload.ticket_id}-{ts}.pdf"

    generate_ticket_pdf(pdf_path, payload)

    try:
        job = print_via_lp(str(pdf_path), printer_name=target_printer_name)
        if "error" in job:
            raise HTTPException(status_code=500, detail=f"Printing failed: {job['error']}")

        return {
            "ok": True,
            "printed": True,
            "pdf": str(pdf_path),
            "print_job": job,
            "target_printer": target_printer_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Printing failed during execution: {str(e)}")


# --- Backend integration ---

_SAFE_FILENAME = re.compile(r"[^\w\-]")


def _safe_ticket_id(ticket_id: str) -> str:
    """Sanitize ticket_id for use in filenames — strip path traversal chars."""
    cleaned = _SAFE_FILENAME.sub("_", ticket_id.replace("\x00", ""))
    if not cleaned or cleaned.strip("_") == "":
        raise ValueError("Invalid ticket_id for filename.")
    return cleaned


def _custom_values_from_backend(custom_fields: Any, defs: Any) -> dict:
    """Maps backend custom_fields_data into layout custom field ids.

    Each layout custom field def carries a backend_key; when unset or not
    found, falls back to a case-insensitive match on the field label.
    """
    if not isinstance(custom_fields, dict):
        return {}
    values = {}
    lower_map = {str(k).strip().lower(): k for k in custom_fields}
    for field_id, field_def in (defs or {}).items():
        if not isinstance(field_def, dict):
            continue
        backend_key = str(field_def.get("backend_key") or "").strip()
        raw = custom_fields.get(backend_key) if backend_key else None
        if raw is None:
            label = str(field_def.get("label") or "").strip()
            match_key = lower_map.get(label.lower())
            if match_key is not None:
                raw = custom_fields[match_key]
        if raw is None or raw == "":
            continue
        values[field_id] = raw
    return values


def _ticket_payload_from_backend(data: dict, custom_defs: Any = None) -> TicketPayload:
    """Maps backend ticket response into local TicketPayload."""
    custom_fields = data.get("custom_fields_data") or {}
    company = None
    title = None
    country = None
    table_no = None
    if isinstance(custom_fields, dict):
        company = (
            custom_fields.get("company")
            or custom_fields.get("organisation_institution")
            or custom_fields.get("organization")
            or custom_fields.get("organisation")
            or None
        )
        title = (
            custom_fields.get("title")
            or custom_fields.get("position")
            or custom_fields.get("job_title")
            or custom_fields.get("designation")
            or None
        )
        country = custom_fields.get("country") or None
        table_no = (
            custom_fields.get("table_no")
            or custom_fields.get("table_number")
            or custom_fields.get("table")
            or None
        )
    return TicketPayload(
        ticket_id=str(data.get("public_id") or "").strip(),
        name=str(data.get("attendee_name") or "").strip(),
        company=company,
        title=title,
        country=country,
        table_no=table_no,
        ticket_type=str(data.get("ticket_type") or "").strip() or "Visitor",
        custom=_custom_values_from_backend(custom_fields, custom_defs),
    )


def _do_print(payload: TicketPayload, prefix: str = "scan") -> dict:
    """Generate PDF and print. Returns print result dict. Raises HTTPException on failure."""
    ensure_outdir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = _safe_ticket_id(payload.ticket_id)
    pdf_path = Path(settings.OUTPUT_DIR) / f"{prefix}-{safe_id}-{ts}.pdf"
    generate_ticket_pdf(pdf_path, payload)
    try:
        job = print_via_lp(str(pdf_path), printer_name=settings.PRINTER_NAME)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Printing failed: {e}")
    if "error" in job:
        raise HTTPException(status_code=500, detail=f"Printing failed: {job['error']}")
    return {"pdf": str(pdf_path), "print_job": job}


class ConfigPayload(BaseModel):
    backend_url: str | None = None
    event_slug: str | None = None
    api_key: str | None = None
    badge_types: list | None = None
    layout: dict | None = None


@app.get("/config")
def get_config():
    """Returns current backend integration config (api key masked)."""
    return config_store.public_view()


@app.put("/config")
def put_config(payload: ConfigPayload):
    """Updates and persists backend integration config."""
    values = {k: v for k, v in payload.model_dump().items() if v is not None}
    saved = config_store.save(values)
    return config_store.public_view(saved)


@app.delete("/config")
def delete_config():
    """Clears all backend credentials. Disables scanning."""
    config_store.reset()
    return config_store.public_view()


@app.post("/scan/{public_id}")
def scan_ticket(public_id: str):
    """
    Check-in first, then print. Flow:
    1. Lookup ticket on backend
    2. Mark as checked-in
    3. Print badge
    If already checked-in: return 200 with already_scanned=true, no print.
    Operator can trigger reprint via /scan/{public_id}/reprint.
    """
    cfg = config_store.load()
    if not cfg.get("backend_url") or not cfg.get("event_slug") or not cfg.get("api_key"):
        raise HTTPException(status_code=400, detail="Backend not configured. Set backend URL, event slug, and API key.")

    client = BackendClient(cfg["backend_url"], cfg.get("api_key", ""))

    try:
        ticket_data = client.fetch_ticket(cfg["event_slug"], public_id)
    except BackendError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        payload = _ticket_payload_from_backend(
            ticket_data,
            custom_defs=(config_store.load().get("layout") or {}).get("custom_fields"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Invalid ticket data from backend: {e}")

    if not payload.ticket_id:
        raise HTTPException(status_code=502, detail="Backend response missing public_id.")

    try:
        check_in = client.check_in(payload.ticket_id)
    except BackendAlreadyCheckedIn as e:
        return {
            "ok": True,
            "already_scanned": True,
            "check_in_message": str(e),
            "ticket": payload.model_dump(),
        }
    except BackendError as e:
        raise HTTPException(status_code=502, detail=str(e))

    print_result = _do_print(payload, prefix="scan")

    return {
        "ok": True,
        "already_scanned": False,
        "ticket": payload.model_dump(),
        "check_in": check_in,
        **print_result,
    }


@app.post("/scan/{public_id}/reprint")
def reprint_ticket(public_id: str):
    """
    Force reprint for an already-checked-in ticket.
    Looks up ticket (no check-in call), prints badge.
    """
    cfg = config_store.load()
    if not cfg.get("backend_url") or not cfg.get("event_slug"):
        raise HTTPException(status_code=400, detail="Backend not configured.")

    client = BackendClient(cfg["backend_url"], cfg.get("api_key", ""))

    try:
        ticket_data = client.fetch_ticket(cfg["event_slug"], public_id)
    except BackendError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        payload = _ticket_payload_from_backend(
            ticket_data,
            custom_defs=(config_store.load().get("layout") or {}).get("custom_fields"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Invalid ticket data from backend: {e}")

    print_result = _do_print(payload, prefix="reprint")

    return {
        "ok": True,
        "reprinted": True,
        "ticket": payload.model_dump(),
        **print_result,
    }
