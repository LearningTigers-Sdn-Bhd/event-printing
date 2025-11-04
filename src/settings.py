import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    """
    PRINTER_NAME: str = "Bar Code Printer P422T_2"
    # PRINTER_NAME: str = "HP_DeskJet_2700_series_2"
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "out")
    PORT: int = int(os.getenv("PORT", "8000"))

# Instantiate settings once
settings = Settings()

# Utility function
def ensure_outdir():
	"""Ensure the output directory for PDFs exists."""
	from pathlib import Path
	Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)