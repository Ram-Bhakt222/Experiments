"""
HALO macOS desktop entrypoint.

Runs the existing Flask backend on localhost and opens it in a native WebKit
window through pywebview. Build this file on macOS with script/build_and_run.sh.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import webview


APP_NAME = "HALO"
DEFAULT_PORT = 8765


def app_support_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def available_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(url: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"HALO backend did not start: {last_error}")


def run_backend(port: int) -> None:
    from server import app

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def main() -> None:
    data_dir = app_support_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HALO_DATA_DIR", str(data_dir))

    port = available_port(int(os.environ.get("PORT", str(DEFAULT_PORT))))
    os.environ["PORT"] = str(port)
    base_url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(target=run_backend, args=(port,), daemon=True)
    thread.start()
    wait_for_server(base_url)

    webview.create_window(
        APP_NAME,
        base_url,
        width=1180,
        height=840,
        min_size=(980, 700),
        text_select=True,
    )
    if sys.platform == "darwin":
        webview.start(gui="cocoa")
    else:
        webview.start()


if __name__ == "__main__":
    main()
