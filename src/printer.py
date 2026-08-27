import subprocess
import re
import platform
import sys
from typing import Dict, Any, Optional, List

from settings import settings # Import settings

# Detect the operating system
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


def print_via_lp(file_path: str, printer_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Cross-platform printing function.
    Uses 'lp' command on Mac/Linux and Windows printing API on Windows.
    """
    printer = printer_name or settings.PRINTER_NAME
    if not printer:
        raise Exception("PRINTER_NAME not set. Set it in .env or environment.")

    if IS_WINDOWS:
        return _print_windows(file_path, printer)
    else:
        return _print_unix(file_path, printer)


def _print_unix(file_path: str, printer_name: str) -> Dict[str, Any]:
    """
    Sends a file to the printer using the 'lp' command (Mac/Linux).
    Pre-rasterizes the PDF to a 1-bit PNG at the printer's native
    203dpi so text prints as crisp solid pixels instead of being
    halftone-dithered by the driver.
    """
    try:
        raster_path = _rasterize_pdf_for_zebra(file_path)
        cmd = [
            "lp",
            "-d", printer_name,
            "-o", "Darkness=15",
            raster_path,
        ]
        out = subprocess.check_output(cmd, text=True)

        # Parse the job ID from the output
        m = re.search(r"request id is (\S+)", out)
        job_id = m.group(1) if m else out.strip()

        return {"job_id": job_id, "raw": out, "platform": "unix"}
    except subprocess.CalledProcessError as e:
        return {"error": str(e), "output": e.output}
    except FileNotFoundError:
        return {"error": "The 'lp' command was not found. Is CUPS installed?"}


def _rasterize_pdf_for_zebra(pdf_path: str) -> str:
    """
    Render first page of PDF to a 1-bit PNG at 203dpi (P422T native).
    Supersamples at 2x then downsamples with LANCZOS so anti-aliased
    edges resolve into cleaner 1-bit pixels with fewer broken strokes.
    """
    import fitz
    from PIL import Image
    import os

    target_dpi = 203
    super_dpi = target_dpi * 2
    zoom = super_dpi / 72
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csGRAY)
    hi = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    target_w = round(pix.width / 2)
    target_h = round(pix.height / 2)
    lo = hi.resize((target_w, target_h), Image.Resampling.LANCZOS)
    bw = lo.point(lambda p: 0 if p < 220 else 255, mode="1")
    out_path = os.path.splitext(pdf_path)[0] + "-print.png"
    bw.save(out_path, "PNG", dpi=(target_dpi, target_dpi))
    doc.close()
    return out_path


def _create_printer_dc(printer_name: str, hprinter):
    """
    Create the printer DC, forcing paper size from the saved layout config
    (config_store.load()["layout"]["paper"]) via a custom DEVMODE so users
    don't have to match it manually in Windows' printer settings.

    ponytail: some label-printer drivers only accept sizes from their own
    predefined list and ignore a custom DEVMODE — falls back silently to
    the printer's own default DC in that case (previous behavior).
    """
    import win32print
    import win32ui
    import win32gui
    import win32con
    import config_store

    try:
        paper = (config_store.load().get("layout") or {}).get("paper") or {}
        width_mm = paper.get("width_mm")
        height_mm = paper.get("height_mm")
        if width_mm and height_mm:
            devmode = win32print.GetPrinter(hprinter, 2)["pDevMode"]
            devmode.PaperSize = 0  # 0 = use PaperWidth/PaperLength instead of a preset
            devmode.PaperWidth = int(round(width_mm * 10))   # tenths of a mm
            devmode.PaperLength = int(round(height_mm * 10))
            devmode.Fields |= (
                win32con.DM_PAPERSIZE | win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH
            )
            devmode = win32print.DocumentProperties(
                0, hprinter, printer_name, devmode, devmode,
                win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER,
            )
            hdc_handle = win32gui.CreateDC("WINSPOOL", printer_name, None, devmode)
            return win32ui.CreateDCFromHandle(hdc_handle)
    except Exception:
        pass

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    return hdc


def _print_windows(file_path: str, printer_name: str) -> Dict[str, Any]:
    """
    Sends a file to the printer using Windows printing system.
    Pure Python solution using PyMuPDF + win32print.
    """
    import os
    abs_path = os.path.abspath(file_path)
    
    try:
        import fitz  # PyMuPDF
        import win32print
        import win32ui
        import win32gui
        from PIL import Image
        import tempfile
        import win32con

        # Open the PDF
        pdf_document = fitz.open(abs_path)
        num_pages = len(pdf_document)

        # Open printer
        hprinter = win32print.OpenPrinter(printer_name)

        try:
            # Create printer DC, forcing the configured paper size when possible
            hdc = _create_printer_dc(printer_name, hprinter)
            
            # Start print job
            hdc.StartDoc(os.path.basename(abs_path))
            
            # Process each page
            for page_num in range(num_pages):
                page = pdf_document[page_num]
                
                # Render page to high-res image (200 DPI)
                zoom = 200 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Rotate 180 degrees
                img = img.rotate(180, expand=True)
                
                # Save as temporary BMP
                with tempfile.NamedTemporaryFile(suffix='.bmp', delete=False) as tmp:
                    tmp_path = tmp.name
                    img.save(tmp_path, 'BMP')
                
                # Start page
                hdc.StartPage()
                
                # Get printer resolution
                printer_width = hdc.GetDeviceCaps(win32con.HORZRES)
                printer_height = hdc.GetDeviceCaps(win32con.VERTRES)
                
                # Calculate scaling
                scale = min(printer_width / pix.width, printer_height / pix.height)
                width = int(pix.width * scale)
                height = int(pix.height * scale)
                
                # Center image
                x = (printer_width - width) // 2
                y = (printer_height - height) // 2
                
                # Draw the image using DDB (Device Dependent Bitmap)
                bmp = Image.open(tmp_path)
                if bmp.mode != 'RGB':
                    bmp = bmp.convert('RGB')
                
                # Resize for printing
                bmp_resized = bmp.resize((width, height), Image.Resampling.LANCZOS)
                
                # Printer is 1-bit: threshold here or the driver halftone-dithers
                # the grey anti-aliased edges into visible dots on the text.
                bmp_resized = bmp_resized.convert('L').point(lambda v: 0 if v < 220 else 255, mode='1')

                # Save resized version
                bmp_resized.save(tmp_path, 'BMP')
                
                # Load and draw bitmap
                import win32gui
                hbmp = win32ui.CreateBitmapFromHandle(
                    win32gui.LoadImage(0, tmp_path, win32con.IMAGE_BITMAP, 0, 0, win32con.LR_LOADFROMFILE)
                )
                
                # Create compatible DC and select bitmap
                mem_dc = hdc.CreateCompatibleDC()
                mem_dc.SelectObject(hbmp)
                
                # Copy to printer
                hdc.BitBlt((x, y), (width, height), mem_dc, (0, 0), win32con.SRCCOPY)
                
                # Cleanup
                mem_dc.DeleteDC()
                hdc.EndPage()
                os.unlink(tmp_path)
            
            # Finish
            hdc.EndDoc()
            hdc.DeleteDC()
            pdf_document.close()
            
            return {
                "job_id": "python_print_job",
                "raw": f"Printed {num_pages} page(s) to: {printer_name}",
                "platform": "windows",
                "method": "pymupdf_pure_python",
                "file": abs_path,
                "pages": num_pages
            }
            
        finally:
            win32print.ClosePrinter(hprinter)
            
    except ImportError as e:
        missing = str(e).split("'")[1] if "'" in str(e) else str(e)
        return {
            "error": f"Missing Python package: {missing}",
            "solution": "Run: pip install PyMuPDF pillow pywin32"
        }
    except Exception as e:
        return {"error": f"Printing failed: {str(e)}"}


def list_cups_printers() -> str:
    """
    Cross-platform function to list available printers.
    """
    if IS_WINDOWS:
        return _list_windows_printers()
    else:
        return _list_unix_printers()


def _list_unix_printers() -> str:
    """
    Lists available CUPS printers using the 'lpstat -p' command (Mac/Linux).
    """
    try:
        out = subprocess.check_output(["lpstat", "-p"], text=True)
        return out
    except FileNotFoundError:
        return "Error: lpstat command not found. Is CUPS installed?"
    except subprocess.CalledProcessError as e:
        return f"Error listing printers: {str(e)}"


def _list_windows_printers() -> str:
    """
    Lists available printers on Windows.
    """
    try:
        import win32print
        
        printers = []
        # Get all printers
        printer_enum = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        
        for printer in printer_enum:
            printer_name = printer[2]  # Printer name is at index 2
            printers.append(f"printer {printer_name} is available")
        
        if not printers:
            return "No printers found"
        
        return "\n".join(printers)
        
    except ImportError:
        # Fallback: Use PowerShell
        try:
            ps_command = "Get-Printer | Select-Object Name, DriverName, PortName | Format-List"
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout + "\n\nNote: Install pywin32 for better printer support: pip install pywin32"
            else:
                return f"Error: {result.stderr}"
                
        except Exception as e:
            return f"Error listing printers: {str(e)}"
    except Exception as e:
        return f"Error listing printers: {str(e)}"


def get_default_printer() -> Optional[str]:
    """
    Get the system's default printer name.
    """
    if IS_WINDOWS:
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except ImportError:
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "(Get-WmiObject -Query 'SELECT * FROM Win32_Printer WHERE Default=$true').Name"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.stdout.strip() if result.returncode == 0 else None
            except:
                return None
        except Exception:
            return None
    else:
        # Unix/Mac
        try:
            result = subprocess.check_output(["lpstat", "-d"], text=True)
            match = re.search(r"system default destination: (\S+)", result)
            return match.group(1) if match else None
        except:
            return None