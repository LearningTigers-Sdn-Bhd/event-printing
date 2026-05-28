import sys
import os
import time
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
# IMPORT THIS:
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from datetime import datetime
from pydantic import BaseModel

# Import components from other files
from settings import settings, ensure_outdir # Removed get_printer_name since it's not needed here
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

@app.post("/pdf-preview")
def pdf_preview(payload: TicketPayload):
    """Generates badge PDF and returns it for browser preview (no printing)."""
    ensure_outdir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = Path(settings.OUTPUT_DIR) / f"preview-{payload.ticket_id}-{ts}.pdf"
    generate_ticket_pdf(pdf_path, payload)
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=pdf_path.name)


@app.post("/png-preview")
def png_preview(payload: TicketPayload):
    """Generates badge PDF and returns it as a PNG for embedded preview."""
    import fitz
    from io import BytesIO
    from fastapi.responses import Response

    ensure_outdir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = Path(settings.OUTPUT_DIR) / f"preview-{payload.ticket_id}-{ts}.pdf"
    generate_ticket_pdf(pdf_path, payload)

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
    
    # The target printer is simply the one defined in settings.PRINTER_NAME
    target_printer_name = settings.PRINTER_NAME
    
    ts = datetime.now().strftime("%Y%m%d %H%M%S")

    # Filename creation
    pdf_path = Path(settings.OUTPUT_DIR) / f"badge-{payload.ticket_id}-{ts}.pdf"

    # 1. Generate PDF
    generate_ticket_pdf(pdf_path, payload)
        
    # 2. Print via lp using the target printer name
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


# --- Backend integration: settings + scan ---

class ConfigPayload(BaseModel):
    backend_url: str | None = None
    event_slug: str | None = None
    api_key: str | None = None


class ScanOptions(BaseModel):
    print_label: bool = True
    mark_scanned: bool = True


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


def _ticket_payload_from_backend(data: dict) -> TicketPayload:
    """Maps an EventzFlow ticket response into the local TicketPayload model."""
    custom_fields = data.get("custom_fields_data") or {}
    if isinstance(custom_fields, dict):
        company = (
            custom_fields.get("company")
            or custom_fields.get("organisation_institution")
            or custom_fields.get("organization")
            or custom_fields.get("organisation")
            or None
        )
    else:
        company = None

    return TicketPayload(
        ticket_id=str(data.get("public_id") or "").strip(),
        name=str(data.get("attendee_name") or "").strip(),
        company=company,
        ticket_type=str(data.get("ticket_type") or "").strip() or "Visitor",
    )


@app.post("/scan/{public_id}")
def scan_ticket(public_id: str, options: ScanOptions = ScanOptions()):
    """
    Looks up a ticket on the EventzFlow backend, prints the badge,
    then marks the ticket as scanned. Designed to be called from the
    dashboard's scan input (USB QR scanner emits the public_id).
    """
    cfg = config_store.load()
    if not cfg.get("backend_url") or not cfg.get("event_slug"):
        raise HTTPException(status_code=400, detail="Backend URL or event slug is not configured.")

    client = BackendClient(cfg["backend_url"], cfg.get("api_key", ""))

    # 1. Lookup
    try:
        ticket_data = client.fetch_ticket(cfg["event_slug"], public_id)
    except BackendError as e:
        raise HTTPException(status_code=502, detail=str(e))

    payload = _ticket_payload_from_backend(ticket_data)
    if not payload.ticket_id:
        raise HTTPException(status_code=502, detail="Backend response missing public_id.")

    result: dict = {
        "ok": True,
        "ticket": payload.model_dump(),
    }

    # 2. Print
    if options.print_label:
        ensure_outdir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = Path(settings.OUTPUT_DIR) / f"scan-{payload.ticket_id}-{ts}.pdf"
        generate_ticket_pdf(pdf_path, payload)
        try:
            job = print_via_lp(str(pdf_path), printer_name=settings.PRINTER_NAME)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Printing failed: {e}")
        if "error" in job:
            raise HTTPException(status_code=500, detail=f"Printing failed: {job['error']}")
        result["pdf"] = str(pdf_path)
        result["print_job"] = job

    # 3. Check-in
    if options.mark_scanned:
        try:
            check_in = client.check_in(payload.ticket_id)
            result["check_in"] = check_in
            result["already_scanned"] = False
        except BackendAlreadyCheckedIn as e:
            result["already_scanned"] = True
            result["check_in_message"] = str(e)
        except BackendError as e:
            # Print already happened; surface the check-in error but keep
            # a 200 response so the operator sees the printed badge result.
            result["check_in_error"] = str(e)

    return result
