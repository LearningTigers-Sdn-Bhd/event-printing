@echo off
echo === Event Printing - Build Script ===

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
pip install --quiet fastapi==0.118.0 "uvicorn[standard]==0.37.0" pydantic==2.12.0 ^
    pydantic-settings==2.11.0 python-dotenv==1.1.1 reportlab==4.4.4 ^
    pillow==11.3.0 qrcode==8.2 pywin32 PyMuPDF pyinstaller

echo Building executable...
pyinstaller event-printing.spec --clean --noconfirm

echo.
echo Done! Executable at: dist\EventPrinting.exe
echo Copy 'dist\EventPrinting.exe' to target machine and double-click to run.
pause
