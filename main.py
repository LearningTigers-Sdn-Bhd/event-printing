import os
from fastapi import FastAPI
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

#check if CUPS can be connected
import subprocess
from fastapi import HTTPException

#test PDF printing
from reportlab.lib.pagesizes import A6, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.units import inch
from datetime import datetime
from pathlib import Path

#for qr code generation
from pydantic import BaseModel, Field
from typing import Optional
import io
import qrcode
from reportlab.lib.utils import ImageReader

import re
import subprocess

load_dotenv()

class Settings(BaseSettings):
  PRINTER_NAME: str = os.getenv("PRINTER_NAME", "")
  OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "out")
  PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()

app = FastAPI(title="Event Ticket Printer")

class TicketPayload(BaseModel):
  name: str = Field(..., example="Fazli")
  ticket_id: str = Field(..., example="A1-0245")
  ticket_type: Optional[str] = Field(default="General")
  event_name: str = Field(..., example="Kota Kinabalu Tech Expo")
  event_datetime: Optional[str] = Field(default=None, example="2025-10-21 09:00")
  seat: Optional[str] = Field(default=None, example="B-14")
  qr_text: str = Field(..., example="https://ticketz.bot/verify?code=A1-0245")

def ensure_outdir():
  Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

def generate_test_pdf(path: Path):
  c = canvas.Canvas(str(path), pagesize=landscape(A6))
  w, h = landscape(A6)
  c.setFont("Helvetica-Bold", 14)
  c.drawString(20*mm, h - 20*mm, "Event Ticket — TEST")
  c.setFont("Helvetica", 10)
  c.drawString(20*mm, h - 30*mm, f"Generated at: {datetime.now().isoformat(timespec='seconds')}")
  c.drawString(20*mm, h - 40*mm, "This is a printer pipeline dry run.")
  c.rect(10*mm, 10*mm, w - 20*mm, h - 20*mm)  # border box
  c.showPage()
  c.save()
  return str(path)

def generate_ticket_pdf(path: Path, data: TicketPayload):
  c = canvas.Canvas(str(path), pagesize=landscape(A6))
  w, h = landscape(A6)

  # Border
  c.setLineWidth(1)
  c.rect(8*mm, 8*mm, w - 16*mm, h - 16*mm)

  # Event title
  c.setFont("Helvetica-Bold", 16)
  c.drawString(15*mm, h - 18*mm, data.event_name)

  # Event date/time
  c.setFont("Helvetica", 10)
  when = data.event_datetime or ""
  c.drawString(15*mm, h - 26*mm, when)

  # Attendee info
  c.setFont("Helvetica-Bold", 14)
  c.drawString(15*mm, h - 38*mm, f"Name: {data.name}")
  c.setFont("Helvetica", 11)
  c.drawString(15*mm, h - 48*mm, f"Ticket: {data.ticket_id}   Type: {data.ticket_type or '-'}")
  c.drawString(15*mm, h - 56*mm, f"Seat: {data.seat or '-'}")

  # QR code (generated from qr_text)
  qr_img = qrcode.make(data.qr_text)
  buf = io.BytesIO()
  qr_img.save(buf, format="PNG")
  buf.seek(0)
  qr_reader = ImageReader(buf)
  qr_size = 40*mm
  c.drawImage(qr_reader, w - 15*mm - qr_size, h - 18*mm - qr_size, width=qr_size, height=qr_size, mask='auto')

  # Footer
  c.setFont("Helvetica-Oblique", 8)
  c.drawRightString(w - 10*mm, 10*mm, f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")

  c.showPage()
  c.save()
  return str(path)


def print_via_lp(file_path: str, printer_name: str | None = None):
  printer = printer_name or settings.PRINTER_NAME
  if not printer:
    raise RuntimeError("PRINTER_NAME not set. Set it in .env or environment.")

  try:
    out = subprocess.check_output(["lp", "-d", printer, file_path], text=True)
    m = re.search(r"request id is (\S+)", out)
    job_id = m.group(1) if m else out.strip()
    return {"job_id": job_id, "raw": out}
  except subprocess.CalledProcessError as e:
    return {"error": str(e), "output:": e.output}

@app.get("/health")
def health():
  return {
 	"of": True,
	"printer": settings.PRINTER_NAME,
	"output_dir": settings.OUTPUT_DIR,
  }

@app.get("/printers")
def list_printers():
  try:
    out = subprocess.check_output(s)
    return {"raw": out}
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/pdf-test")
def pdf_test():
  ensure_outdir()
  ts = datetime.now().strftime("%Y%m%d %H%M%S")
  pdf_path = Path(settings.OUTPUT_DIR) / f"test-ticket-{ts}.pdf"
  path = generate_test_pdf(pdf_path)
  return {"ok": True, "pdf": path}

@app.post("/print-test")
def print_test():
  ensure_outdir()
  ts = datetime.now().strftime("%Y%m%d-%H%M%S")
  pdf_path = Path(settings.OUTPUT_DIR) / f"test-ticket-{ts}.pdf"
  generate_test_pdf(pdf_path)
  job = print_via_lp(pdf_path)
  return {"ok": True, "pdf": str(pdf_path), "print_job": job}

@app.post("/print-ticket")
def print_ticket(payload: TicketPayload):
  ensure_outdir()
  ts = datetime.now().strftime("%Y%m%d %H%M%S")
  safe_event = "".join(ch for ch in payload.event_name if ch.isalnum() or ch in (" ", "_", "-")).strip().replace(" ", "_")
  pdf_path = Path(settings.OUTPUT_DIR) / f"{safe_event}-{payload.ticket_id}-{ts}.pdf"

  generate_ticket_pdf(pdf_path, payload)
  job = print_via_lp(str(pdf_path))
  return {"ok": True, "printed": True, "pdf": str(pdf_path), "print_job": job}

