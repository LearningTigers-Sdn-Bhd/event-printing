# Build & Distribution Guide

How to build the `event-printer` executable for each platform and distribute to non-technical users.

---

## Overview

PyInstaller bundles Python + all dependencies into a single executable. **Builds are platform-specific** — you must build on each OS separately.

| OS | Build on | Output |
|----|----------|--------|
| Linux | Linux machine | `dist/event-printer` |
| macOS | Mac machine | `dist/event-printer-mac` |
| Windows | Windows machine | `dist/event-printer.exe` |

---

## Prerequisites

- Python 3.9+
- Git
- Printer driver installed on the build machine

### Setup (all platforms)

```bash
git clone <repo-url>
cd event-printing

python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
pip install pyinstaller
```

---

## Build Commands

### Linux / macOS

```bash
pyinstaller --onefile --name event-printer \
  --add-data "src:src" \
  --hidden-import fastapi \
  --hidden-import uvicorn \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import pydantic \
  --hidden-import pydantic_settings \
  --hidden-import reportlab \
  --hidden-import reportlab.pdfgen \
  --hidden-import reportlab.pdfgen.canvas \
  --hidden-import reportlab.pdfbase \
  --hidden-import reportlab.pdfbase.pdfmetrics \
  --hidden-import reportlab.pdfbase.ttfonts \
  --hidden-import reportlab.lib \
  --hidden-import reportlab.lib.units \
  --hidden-import reportlab.lib.utils \
  --hidden-import qrcode \
  --hidden-import qrcode.image.pure \
  --hidden-import qrcode.image.pil \
  --hidden-import dotenv \
  --collect-all reportlab \
  run_server.py
```

Output: `dist/event-printer`

> On macOS, rename the output: `mv dist/event-printer dist/event-printer-mac`

### Windows (Command Prompt or PowerShell)

```cmd
pyinstaller --onefile --name event-printer ^
  --add-data "src;src" ^
  --hidden-import fastapi ^
  --hidden-import uvicorn ^
  --hidden-import uvicorn.logging ^
  --hidden-import uvicorn.loops ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols ^
  --hidden-import uvicorn.protocols.http ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import uvicorn.protocols.websockets ^
  --hidden-import uvicorn.protocols.websockets.auto ^
  --hidden-import uvicorn.lifespan ^
  --hidden-import uvicorn.lifespan.on ^
  --hidden-import pydantic ^
  --hidden-import pydantic_settings ^
  --hidden-import reportlab ^
  --hidden-import reportlab.pdfgen ^
  --hidden-import reportlab.pdfgen.canvas ^
  --hidden-import reportlab.pdfbase ^
  --hidden-import reportlab.pdfbase.pdfmetrics ^
  --hidden-import reportlab.pdfbase.ttfonts ^
  --hidden-import reportlab.lib ^
  --hidden-import reportlab.lib.units ^
  --hidden-import reportlab.lib.utils ^
  --hidden-import qrcode ^
  --hidden-import qrcode.image.pure ^
  --hidden-import qrcode.image.pil ^
  --hidden-import dotenv ^
  --hidden-import fitz ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  --hidden-import PIL.ImageDraw ^
  --hidden-import PIL.ImageFont ^
  --hidden-import win32print ^
  --hidden-import win32ui ^
  --hidden-import win32con ^
  --hidden-import win32gui ^
  --hidden-import win32api ^
  --collect-all reportlab ^
  --collect-all fitz ^
  --collect-all PIL ^
  run_server.py
```

Output: `dist/event-printer.exe`

---

## Running the Executable

### Linux
```bash
chmod +x event-printer
./event-printer
```

### macOS
```bash
chmod +x event-printer-mac
./event-printer-mac
```

If macOS blocks it with a security warning:
```bash
xattr -d com.apple.quarantine event-printer-mac
```

### Windows
Double-click `event-printer.exe` or run in Command Prompt:
```cmd
event-printer.exe
```

---

## Verify It Works

Open browser and go to:
```
http://localhost:8000/health
```

Expected response:
```json
{"ok": true, "printer": "YourPrinterName", "output_dir": "out"}
```

Printer is **auto-detected** — no config needed if only one printer is connected.

---

## Optional: Override Printer

Create a `.env` file in the same folder as the executable:

```env
PRINTER_NAME=YourExactPrinterName
PORT=8000
```

To find printer name:
- **Windows**: `Get-Printer | Select-Object Name` in PowerShell
- **macOS / Linux**: `lpstat -p` in Terminal

---

## Troubleshooting

**Port already in use**
Set different port in `.env`: `PORT=8001`

**Linux: CUPS not installed**
```bash
sudo apt install cups
```

**Printer not detected**
Check `/printers` endpoint, then set `PRINTER_NAME` in `.env`
