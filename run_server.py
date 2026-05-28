import sys
import os
import threading
import time

import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from main import app

PORT = int(os.environ.get("PORT", 8000))
URL = f"http://127.0.0.1:{PORT}/"


def _run_server():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


def _wait_for_server(timeout: float = 10.0) -> bool:
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL + "health", timeout=1)
            return True
        except (urllib.error.URLError, ConnectionResetError, OSError):
            time.sleep(0.2)
    return False


def main():
    # Honor a flag to run headless (server only, no window) for debugging.
    headless = os.environ.get("HEADLESS", "").lower() in ("1", "true", "yes")

    try:
        import webview  # pywebview
    except ImportError:
        webview = None

    if headless or webview is None:
        if webview is None and not headless:
            print("pywebview not installed; running headless. Install with: pip install pywebview")
        _run_server()
        return

    server = threading.Thread(target=_run_server, daemon=True)
    server.start()

    if not _wait_for_server():
        print(f"Server did not start on {URL} within timeout.")
        return

    webview.create_window(
        "Event Printer",
        URL,
        width=960,
        height=720,
        min_size=(720, 560),
    )
    webview.start()


if __name__ == "__main__":
    main()
