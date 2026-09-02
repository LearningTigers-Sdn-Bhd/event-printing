# -*- mode: python ; coding: utf-8 -*-
"""macOS build for event-printer.

Produces a single-file binary at dist/event-printer (rename to
event-printer-mac before attaching to a release). Build ON a Mac:
PyInstaller cannot cross-compile.

    pyinstaller event-printer-mac.spec --clean --noconfirm
    mv dist/event-printer dist/event-printer-mac

The binary name stays constant so the self-updater can always find and
replace it. Bump the version in src/version.py on each release.
"""
from PyInstaller.utils.hooks import collect_all

datas = [
    ('src/static', 'src/static'),
    ('src', 'src'),
]
binaries = []

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
    # macOS webview backend (WKWebView via pyobjc).
    'webview.platforms.cocoa',
    'objc',
    'Foundation',
    'WebKit',
    'httpx',
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
