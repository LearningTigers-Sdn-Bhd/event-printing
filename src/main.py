import sys

from fastapi import FastAPI, HTTPException
# IMPORT THIS:
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from datetime import datetime
from pathlib import Path

# Import components from other files
from settings import settings, ensure_outdir # Removed get_printer_name since it's not needed here
from models import TicketPayload
from pdf_generator import generate_test_pdf, generate_ticket_pdf
from printer import print_via_lp, list_cups_printers

app = FastAPI(title="Event Ticket Printer")

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
    """Lists available CUPS printers using lpstat."""
    try:
        out = list_cups_printers()
        return {"raw": out}
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
