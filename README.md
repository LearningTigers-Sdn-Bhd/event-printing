# Event Printing System

A cross-platform FastAPI application for generating and printing event badges/tickets with automatic printer support for Windows, macOS, and Linux.

## Features

- 🖨️ **Cross-platform printing** - Works on Windows, macOS, and Linux
- 📄 **PDF generation** - Creates professional event badges with QR codes
- 🔄 **Auto text wrapping** - Intelligently handles long names and text
- 🎨 **Custom layouts** - Configurable badge designs
- 🌐 **REST API** - Easy integration with event management systems

---

## Quick Start

### Prerequisites

- **Python 3.9+** installed on your system
- A printer configured on your system (physical or virtual)

---

## 🪟 Windows Setup

### 1. Install Python Dependencies

```bash
# Navigate to project directory
cd event-printing

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Your Printer

Find your printer name:

**Option A: Using Windows Settings**
1. Open **Settings** → **Devices** → **Printers & scanners**
2. Copy the exact printer name (e.g., "HP LaserJet Pro", "Microsoft Print to PDF")

**Option B: Using PowerShell**
```powershell
Get-Printer | Select-Object Name
```

**Option C: Using the API** (after starting the server)
```bash
# Start server first, then visit:
http://localhost:8000/printers
```

### 3. Set Environment Variables

Create a `.env` file in the project root:

```env
PRINTER_NAME=Your Printer Name Here
OUTPUT_DIR=out
PORT=8000
```

**Example for physical printer:**
```env
PRINTER_NAME=HP LaserJet Pro M404dn
```

**Example for testing (virtual printer):**
```env
PRINTER_NAME=Microsoft Print to PDF
```

### 4. Run the Application

```bash
# Make sure virtual environment is activated
venv\Scripts\activate

# Start the server
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test Printing

Open your browser and visit:
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **List Printers**: http://localhost:8000/printers

Or use curl/PowerShell:

```powershell
# Test print
Invoke-RestMethod -Uri "http://localhost:8000/print-test" -Method POST
```

### Windows-Specific Notes

- ✅ **No CUPS required** - Uses native Windows printing APIs
- ✅ **Works with all Windows printers** - Network, USB, virtual printers
- ✅ **Automatic 180° rotation** - Built into the Windows printing function
- ⚠️ **Requires pywin32 and PyMuPDF** - Automatically installed via requirements.txt

---

## 🍎 macOS Setup

### 1. Install Python Dependencies

```bash
# Navigate to project directory
cd event-printing

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Your Printer

Find your printer name using Terminal:

```bash
# List all available printers
lpstat -p

# Example output:
# printer HP_DeskJet_2700_series is idle
# printer Brother_HL_L2350DW is idle
```

Copy the printer name (e.g., `HP_DeskJet_2700_series`)

### 3. Set Environment Variables

Create a `.env` file in the project root:

```env
PRINTER_NAME=Your_Printer_Name_Here
OUTPUT_DIR=out
PORT=8000
```

**Example:**
```env
PRINTER_NAME=HP_DeskJet_2700_series
```

### 4. Run the Application

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Start the server
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test Printing

Open your browser and visit:
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **List Printers**: http://localhost:8000/printers

Or use curl:

```bash
# Test print
curl -X POST http://localhost:8000/print-test
```

### macOS-Specific Notes

- ✅ **Uses CUPS** - Standard macOS printing system
- ✅ **Works with all Mac printers** - AirPrint, USB, network printers
- ⚠️ **CUPS must be running** - Usually enabled by default on macOS
- 💡 **Printer names use underscores** - Spaces are replaced with underscores in CUPS

---

## 📡 API Endpoints

### Health & Status

- `GET /health` - Check application status and configuration
- `GET /printers` - List all available printers

### PDF Generation

- `POST /pdf-test` - Generate a test PDF (no printing)

### Printing

- `POST /print-test` - Generate and print a test badge
- `POST /print-ticket` - Generate and print an event badge

### Print Ticket Example

```bash
curl -X POST http://localhost:8000/print-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "12345",
    "name": "John Doe",
    "company": "Tech Corp",
    "title": "Software Engineer",
    "ticket_type": "VIP"
  }'
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PRINTER_NAME` | Exact name of your printer | `Microsoft Print to PDF` | Yes |
| `OUTPUT_DIR` | Directory for generated PDFs | `out` | No |
| `PORT` | Server port | `8000` | No |

### Badge Customization

Edit `src/pdf_generator.py` to customize:
- Badge dimensions
- Font sizes and styles
- Text positioning
- Colors and layouts

---

## 🐛 Troubleshooting

### Windows Issues

**Problem: "Missing Python package: win32print"**
```bash
pip install pywin32
```

**Problem: "Missing Python package: fitz"**
```bash
pip install PyMuPDF
```

**Problem: Printer not found**
- Verify printer name exactly matches (case-sensitive)
- Check printer is online and not paused
- Try using "Microsoft Print to PDF" for testing

### macOS Issues

**Problem: "The 'lp' command was not found"**
- CUPS is not installed or not running
- Try: `sudo cupsctl WebInterface=yes`

**Problem: "Printer not found"**
- Run `lpstat -p` to verify printer name
- Check printer is not paused: `lpstat -p <printer-name>`
- Enable printer: `cupsenable <printer-name>`

**Problem: Permission denied**
- Add your user to the lpadmin group:
  ```bash
  sudo dseditgroup -o edit -a $USER -t user lpadmin
  ```

### General Issues

**Problem: Long names are cut off**
- The system automatically wraps long names to multiple lines
- Names are automatically sized: 26pt (short), 20pt (medium), 16pt (long)

**Problem: PDFs generated but not printing**
- Check `/printers` endpoint to verify printer availability
- Check printer queue on your system
- Verify `.env` file has correct printer name

---

## 📁 Project Structure

```
event-printing/
├── src/
│   ├── main.py              # FastAPI application & endpoints
│   ├── printer.py           # Cross-platform printing logic
│   ├── pdf_generator.py     # PDF generation with ReportLab
│   ├── pdf_visualizer.py    # PDF preview utilities
│   ├── settings.py          # Configuration management
│   └── models.py            # Pydantic data models
├── out/                     # Generated PDF output directory
├── .env                     # Environment configuration (create this)
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

---

## 🚀 Production Deployment

### Using Gunicorn (Linux/Mac)

```bash
pip install gunicorn
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Using Uvicorn (All Platforms)

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### As a Windows Service

Use NSSM (Non-Sucking Service Manager):
1. Download NSSM from https://nssm.cc/
2. Install service:
   ```cmd
   nssm install EventPrinting "C:\path\to\venv\Scripts\python.exe" "-m uvicorn src.main:app --host 0.0.0.0 --port 8000"
   nssm set EventPrinting AppDirectory "C:\path\to\event-printing"
   nssm start EventPrinting
   ```

---

## 🔒 Security Notes

- This application is designed for **internal network use**
- No authentication is implemented by default
- For production, consider adding:
  - API key authentication
  - HTTPS/TLS encryption
  - Rate limiting
  - Input validation and sanitization

---

## 📝 License

This project is for internal use by LT-Tech-Team.

---

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify your printer configuration
3. Check the API documentation at `/docs`
4. Review application logs for error messages

---

## ✨ Features in Detail

### Automatic Text Wrapping

The system intelligently handles long text:
- **Names**: Automatically sized (26pt → 20pt → 16pt) and wrapped at word boundaries
- **Company names**: Wrapped to multiple lines at 15pt
- **Titles**: Wrapped to multiple lines at 14pt italic

### Cross-Platform Compatibility

| Feature | Windows | macOS | Linux |
|---------|---------|-------|-------|
| PDF Generation | ✅ | ✅ | ✅ |
| Direct Printing | ✅ | ✅ | ✅ |
| Printer Discovery | ✅ | ✅ | ✅ |
| Network Printers | ✅ | ✅ | ✅ |
| Virtual Printers | ✅ | ✅ | ✅ |

**Note:** The application automatically detects your operating system and uses the appropriate printing method. Mac configuration is completely independent from Windows configuration.

