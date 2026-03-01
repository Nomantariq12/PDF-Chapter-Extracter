"""
PDF Chapter Splitter — Desktop Launcher
========================================
Opens the Streamlit app inside a native desktop window using pywebview.
This is the entry point for both development and the PyInstaller EXE.
"""

import os
import sys
import socket
import subprocess
import time
import threading
import signal
import urllib.request

import webview


# ─── Resolve paths (works inside PyInstaller bundle too) ────────────────────
def _get_base_dir():
    """Return the directory containing app.py.

    Inside a PyInstaller --onefile build the bundled files are extracted to
    sys._MEIPASS.  In dev mode it's simply the script's own directory.
    """
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()
APP_SCRIPT = os.path.join(BASE_DIR, "app.py")


# ─── Find a free port ──────────────────────────────────────────────────────
def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ─── Wait until Streamlit is actually listening ─────────────────────────────
def _wait_for_server(port: int, timeout: float = 30.0):
    """Poll the Streamlit health endpoint until it responds."""
    url = f"http://localhost:{port}/_stcore/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    port = _find_free_port()

    # Build the Streamlit command
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run", APP_SCRIPT,
        "--server.port", str(port),
        "--server.headless", "true",             # don't open a browser
        "--server.address", "localhost",
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none",       # no hot-reload in desktop
        "--global.developmentMode", "false",
    ]

    # Start Streamlit as a subprocess
    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"

    proc = subprocess.Popen(
        streamlit_cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    # Wait for the server to become ready
    if not _wait_for_server(port):
        print("ERROR: Streamlit server did not start in time.", file=sys.stderr)
        proc.kill()
        sys.exit(1)

    # Create the native desktop window
    window = webview.create_window(
        title="PDF Chapter Splitter",
        url=f"http://localhost:{port}",
        width=1200,
        height=800,
        min_size=(800, 600),
    )

    def _on_closed():
        """Kill the Streamlit process when the window is closed."""
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    window.events.closed += _on_closed

    # This blocks until the window is closed
    webview.start()

    # Safety net — make sure the subprocess is gone
    if proc.poll() is None:
        proc.kill()


if __name__ == "__main__":
    main()
