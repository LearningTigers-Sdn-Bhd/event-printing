import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    
    PRINTER_NAME: Set this to your printer's exact name as it appears in your system.
                  - Windows: Check "Devices and Printers" in Control Panel
                  - Mac/Linux: Run `lpstat -p` to see available printers
                  - Or use the /printers endpoint to list available printers
    """
    # Default printer name - UPDATE THIS to match your printer
    PRINTER_NAME: str = os.getenv("PRINTER_NAME", "Microsoft Print to PDF")
    # Example Windows printer: "Microsoft Print to PDF"
    # Example Mac printer: "HP_DeskJet_2700_series_2"
    # Your barcode printer: "Bar Code Printer P422T"
    
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "out")
    PORT: int = int(os.getenv("PORT", "8000"))

# Instantiate settings once
settings = Settings()

# Utility function
def ensure_outdir():
	"""Ensure the output directory for PDFs exists."""
	from pathlib import Path
	Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)