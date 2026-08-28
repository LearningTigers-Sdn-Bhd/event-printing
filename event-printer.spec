# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# The exe name stays constant (event-printer.exe) so the self-updater can
# always find and replace it. The version lives in src/version.py and is
# reported by /health; bump it there on each release.

datas = [
    ('src/static', 'src/static'),
    ('src', 'src'),
]
binaries = []

# pywin32's win32ui/win32print depend on loose DLLs (pywintypesNN.dll,
# pythoncomNN.dll) normally installed into System32 by pywin32_postinstall.py.
# hiddenimports alone won't pull these in, and machines without that
# postinstall having run (i.e. anything but the build machine) get
# "DLL load failed while importing win32ui" at runtime.
#
# Locate pywin32_system32 via an actual pywin32 module's __file__ instead of
# guessing from sys.executable — that guess assumed a venv layout and silently
# found zero DLLs on a global/differently-laid-out Python install.
import glob, os
import win32api
_site_packages = os.path.dirname(os.path.dirname(win32api.__file__))
_pywin32_system32 = os.path.join(_site_packages, 'pywin32_system32')
_pywin32_dlls = glob.glob(os.path.join(_pywin32_system32, '*.dll'))
if not _pywin32_dlls:
    raise RuntimeError(
        f"No pywin32 DLLs found in {_pywin32_system32!r} - "
        "win32ui will DLL-load-fail at runtime. Check pywin32 is installed."
    )
for _dll in _pywin32_dlls:
    binaries.append((_dll, '.'))
hiddenimports = [
    'fastapi',
    'fastapi.staticfiles',
    'fastapi.responses',
    'fastapi.exceptions',
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'pydantic',
    'pydantic_settings',
    'pydantic_core',
    'reportlab',
    'reportlab.pdfgen',
    'reportlab.pdfgen.canvas',
    'reportlab.pdfbase',
    'reportlab.pdfbase.pdfmetrics',
    'reportlab.pdfbase.ttfonts',
    'reportlab.lib',
    'reportlab.lib.units',
    'reportlab.lib.utils',
    'qrcode',
    'qrcode.image.pure',
    'qrcode.image.pil',
    'dotenv',
    'fitz',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'clr_loader',
    'pythonnet',
    'httpx',
    'win32print',
    'win32ui',
    'win32con',
    'win32gui',
    'win32api',
]

packages_to_collect = [
    'reportlab',
    'fitz',
    'PIL',
    'webview',
    'fastapi',
    'starlette',
    'uvicorn',
    'httpx',
    'pydantic',
    'pydantic_core',
    'pydantic_settings',
    'qrcode',
    'pythonnet',
    'clr_loader',
]

for pkg in packages_to_collect:
    try:
        tmp_ret = collect_all(pkg)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception as e:
        print(f"Warning collecting {pkg}: {e}")

a = Analysis(
    ['run_server.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='event-printer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
