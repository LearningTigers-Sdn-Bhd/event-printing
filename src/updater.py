"""Self-update against GitHub Releases.

Flow (all driven from the dashboard's Software section):
1. check()     -> compare running version to the latest release tag.
2. download()  -> pull the new exe to a temp file next to the current one.
3. apply()     -> launch a small helper process that waits for this process
                  to exit, swaps the exe, relaunches it, then cleans up.

Only meaningful in a frozen (PyInstaller) build; in dev mode the endpoints report
update_supported=False and the UI hides the controls.

Security notes:
- Everything comes over HTTPS from the GitHub API. The release asset URL is
  validated to stay on github.com before downloading.
- We verify the downloaded bytes are a plausible executable for the current
  platform (PE "MZ" header on Windows, Mach-O on macOS) and non-trivial in
  size before swapping.
- The swap happens only after this process exits, so the running exe is
  never locked; a .old backup is kept alongside for manual rollback.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from version import __version__

# GitHub repo that publishes the releases. Public repo -> no auth needed.
GITHUB_REPO = "LearningTigers-Sdn-Bhd/event-printing"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# The release asset for the current platform. Each OS publishes its own
# single-file build on the same release; the updater picks the matching one.
def _asset_name() -> str:
    if sys.platform == "win32":
        return "event-printer.exe"
    if sys.platform == "darwin":
        return "event-printer-mac"
    return "event-printer"  # linux / other unix

ASSET_NAME = _asset_name()

_HTTP_TIMEOUT = 15.0
_MIN_EXE_BYTES = 1_000_000  # a real build is tens of MB; anything tiny is an error page

# In-memory status for the UI to poll while a download runs in the background.
_state_lock = threading.Lock()
_state: Dict[str, Any] = {
    "phase": "idle",        # idle | checking | downloading | ready | applying | error
    "progress": None,       # 0..100 while downloading
    "detail": "",
    "latest": None,         # latest version string from GitHub
    "update_available": False,
    "release_url": None,
    "error": None,
}
_download_thread: Optional[threading.Thread] = None


def current_version() -> str:
    return __version__


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def update_supported() -> bool:
    """Self-update only makes sense for the bundled frozen single-file build."""
    return is_frozen()


def _set_state(**kwargs) -> None:
    with _state_lock:
        _state.update(kwargs)


def status() -> Dict[str, Any]:
    with _state_lock:
        snap = dict(_state)
    snap["current_version"] = current_version()
    snap["update_supported"] = update_supported()
    return snap


# --- Version comparison -------------------------------------------------

def parse_version(text: str):
    """Parse "v1.2.3" / "1.2.3" into a comparable tuple (1, 2, 3)."""
    if not isinstance(text, str):
        return (0,)
    m = re.search(r"(\d+(?:\.\d+)+)", text)
    if not m:
        return (0,)
    return tuple(int(p) for p in m.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    """True if latest is a higher version than current (zero-pads to compare)."""
    a, b = parse_version(latest), parse_version(current)
    length = max(len(a), len(b))
    a += (0,) * (length - len(a))
    b += (0,) * (length - len(b))
    return a > b


# --- GitHub release lookup ----------------------------------------------

def _fetch_latest_release() -> Dict[str, Any]:
    """Return {tag_name, url, asset_url} for the latest release with our exe."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"event-printer/{current_version()}",
    }
    with httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        r = client.get(LATEST_RELEASE_API, headers=headers)
        r.raise_for_status()
        data = r.json()
    tag = data.get("tag_name") or ""
    asset_url = None
    for asset in data.get("assets", []) or []:
        if asset.get("name") == _asset_name():
            asset_url = asset.get("browser_download_url")
            break
    if not asset_url:
        raise RuntimeError(f"Latest release ({tag}) has no {_asset_name()} asset.")
    return {
        "tag_name": tag,
        "url": data.get("html_url") or "",
        "asset_url": asset_url,
    }


def check() -> Dict[str, Any]:
    """Query GitHub for the latest release and decide if an update exists."""
    if not update_supported():
        _set_state(phase="idle", update_available=False,
                   detail="Updates only apply to the installed app.")
        return status()
    _set_state(phase="checking", error=None, detail="Checking for updates…")
    try:
        rel = _fetch_latest_release()
        latest = rel["tag_name"]
        available = is_newer(latest, current_version())
        _set_state(
            phase="idle",
            latest=latest,
            update_available=available,
            release_url=rel["url"],
            detail=("Update available" if available else "You're on the latest version"),
            _asset_url=rel["asset_url"],  # stash for the download step
        )
    except Exception as e:  # network down, rate limit, no asset, etc.
        _set_state(phase="error", error=str(e), detail="Couldn't check for updates",
                   update_available=False)
    return status()


def _asset_url() -> Optional[str]:
    with _state_lock:
        return _state.get("_asset_url")


def _validate_asset_url(url: str) -> None:
    """Refuse to download from anywhere that isn't github.com over HTTPS."""
    if not isinstance(url, str) or not url.startswith("https://"):
        raise RuntimeError("Refusing download: not an HTTPS URL.")
    host = url.split("/", 3)[2].lower()
    if not (host == "github.com" or host.endswith(".github.com")):
        raise RuntimeError(f"Refusing download from unexpected host: {host}")


# --- Download ------------------------------------------------------------

def start_download() -> Dict[str, Any]:
    """Begin downloading the new exe in the background (idempotent)."""
    global _download_thread
    if not update_supported():
        _set_state(phase="error", error="Updates only apply to the installed app.")
        return status()
    with _state_lock:
        if _state.get("phase") == "downloading":
            return status()  # already running
        asset_url = _state.get("_asset_url")
        if not asset_url or not _state.get("update_available"):
            # Nothing queued yet — force a check first.
            pass
    if not asset_url:
        st = check()
        asset_url = _asset_url()
        if not asset_url or not st.get("update_available"):
            return status()

    _set_state(phase="downloading", progress=0, error=None,
               detail="Downloading update…")
    _download_thread = threading.Thread(
        target=_download_worker, args=(asset_url,), daemon=True
    )
    _download_thread.start()
    return status()


def _target_exe() -> Path:
    return Path(sys.executable).resolve()


def _download_worker(asset_url: str) -> None:
    try:
        _validate_asset_url(asset_url)
        exe = _target_exe()
        tmp = exe.with_suffix(".new")
        headers = {"User-Agent": f"event-printer/{current_version()}"}
        with httpx.Client(timeout=None, follow_redirects=True) as client:
            with client.stream("GET", asset_url, headers=headers) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length") or 0)
                downloaded = 0
                with tmp.open("wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1 << 16):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            _set_state(progress=int(downloaded * 100 / total))
        _verify_download(tmp)
        _set_state(phase="ready", progress=100,
                   detail="Update downloaded — ready to install.")
    except Exception as e:
        try:
            _target_exe().with_suffix(".new").unlink(missing_ok=True)
        except Exception:
            pass
        _set_state(phase="error", error=str(e), detail="Download failed.")


def _verify_download(path: Path) -> None:
    """Sanity-check the downloaded file looks like a real executable for this platform."""
    size = path.stat().st_size
    if size < _MIN_EXE_BYTES:
        raise RuntimeError("Downloaded file is too small to be the app.")
    with path.open("rb") as f:
        magic = f.read(4)
    if sys.platform == "win32":
        if magic[:2] != b"MZ":
            raise RuntimeError("Downloaded file isn't a Windows executable.")
    elif sys.platform == "darwin":
        # Mach-O magics (incl. byte-swapped + universal/fat binary).
        if magic not in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",
                         b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
                         b"\xca\xfe\xba\xbe"):
            raise RuntimeError("Downloaded file isn't a macOS executable.")
    # Other platforms: the size check above is the best cheap guard.


# --- Apply (swap + relaunch) --------------------------------------------

def apply() -> Dict[str, Any]:
    """Launch the helper that swaps the exe after we exit, then quit."""
    if not update_supported():
        _set_state(phase="error", error="Updates only apply to the installed app.")
        return status()
    with _state_lock:
        if _state.get("phase") != "ready":
            _set_state(phase="error", error="No downloaded update to install yet.")
            return status()

    exe = _target_exe()
    new = exe.with_suffix(".new")
    if not new.exists():
        _set_state(phase="error", error="Downloaded update is missing.")
        return status()

    _set_state(phase="applying", detail="Installing update…")
    _launch_swap_helper(exe, new)

    # Give the HTTP response a moment to flush, then exit so the helper can
    # replace the (no longer running) exe.
    def _quit():
        time.sleep(0.6)
        os._exit(0)
    threading.Thread(target=_quit, daemon=True).start()
    return status()


def _launch_swap_helper(exe: Path, new: Path) -> None:
    """Write a small helper script and launch it detached.

    The script waits for this PID to exit, backs up the current binary to
    .old, moves the new one into place, relaunches it, then deletes itself.
    A .bat is used on Windows (no interpreter needed once the bundled Python
    dies); a POSIX shell script does the same job on macOS/Linux. The .old
    copy is left as a manual rollback.
    """
    if sys.platform == "win32":
        _launch_swap_helper_windows(exe, new)
    else:
        _launch_swap_helper_unix(exe, new)


def _launch_swap_helper_windows(exe: Path, new: Path) -> None:
    old = exe.with_suffix(".old")
    bat = Path(tempfile.gettempdir()) / f"event-printer-updater-{os.getpid()}.bat"
    bat.write_text(
        _HELPER_BAT.format(
            pid=os.getpid(), exe=exe, new=new, old=old
        ),
        encoding="utf-8",
    )

    creation_flags = (
        subprocess.CREATE_NO_WINDOW
        | subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
    )
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        creationflags=creation_flags,
        close_fds=True,
    )


def _launch_swap_helper_unix(exe: Path, new: Path) -> None:
    """macOS/Linux variant: a self-deleting /bin/sh script.

    The downloaded file is made executable before the swap (the browser
    download doesn't preserve the +x bit), and quarantine is cleared so
    Gatekeeper doesn't block the relaunch on macOS.
    """
    old = exe.with_suffix(".old")
    script = Path(tempfile.gettempdir()) / f"event-printer-updater-{os.getpid()}.sh"
    script.write_text(
        _HELPER_SH.format(pid=os.getpid(), exe=exe, new=new, old=old),
        encoding="utf-8",
    )
    script.chmod(0o755)
    subprocess.Popen(
        ["/bin/sh", str(script)],
        start_new_session=True,  # detach so we can exit cleanly
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# Waits for the app PID to exit, swaps the exe, relaunches, self-deletes.
# ~1s poll via ping is the classic no-extra-tools sleep on Windows.
_HELPER_BAT = r"""@echo off
set "PID={pid}"
set "EXE={exe}"
set "NEW={new}"
set "OLD={old}"

:wait
tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if %errorlevel%==0 (
  ping -n 2 127.0.0.1 >nul
  goto wait
)

rem extra settle so the exe's file handles are fully released
ping -n 2 127.0.0.1 >nul

if exist "%OLD%" del /f /q "%OLD%"
if exist "%EXE%" move /y "%EXE%" "%OLD%" >nul
move /y "%NEW%" "%EXE%" >nul

start "" /b "%EXE%"
del /f /q "%~f0" >nul 2>&1
"""
# Waits for the app PID to exit, swaps the binary, relaunches, self-deletes.
_HELPER_SH = r"""#!/bin/sh
PID={pid}
EXE='{exe}'
NEW='{new}'
OLD='{old}'

# Wait until the app process is gone.
while kill -0 "$PID" 2>/dev/null; do
  sleep 1
done
sleep 1  # let file handles fully release

chmod +x "$NEW" 2>/dev/null
# Clear macOS quarantine so Gatekeeper doesn't block the relaunch.
xattr -d com.apple.quarantine "$NEW" 2>/dev/null

rm -f "$OLD"
[ -e "$EXE" ] && mv "$EXE" "$OLD"
mv "$NEW" "$EXE"

"$EXE" &
rm -f "$0"
"""
