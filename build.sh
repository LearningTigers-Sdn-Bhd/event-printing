#!/bin/bash
set -e

echo "=== Event Printing - Build Script ==="

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install --quiet fastapi==0.118.0 "uvicorn[standard]==0.37.0" pydantic==2.12.0 \
    pydantic-settings==2.11.0 python-dotenv==1.1.1 reportlab==4.4.4 \
    pillow==11.3.0 qrcode==8.2 pyinstaller

echo "Building executable..."
pyinstaller event-printing.spec --clean --noconfirm

echo ""
echo "Done! Executable at: dist/EventPrinting"
echo "Copy 'dist/EventPrinting' to target machine and double-click to run."
