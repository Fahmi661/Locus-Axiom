"""
LOCUS (Cursor for Scientific Integrity)
Desktop Application Launcher (PyInstaller & pywebview Wrapper)
Mode: 100% Offline (127.0.0.1:8000)
"""

import sys
import os

# Force 100% Offline mode for Hugging Face and ML libraries
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import time
import threading
import uvicorn
import urllib.request
import webbrowser

# Add current workspace directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.main import app

HOST = "127.0.0.1"
PORT = 8000
SERVER_URL = f"http://{HOST}:{PORT}"


def start_server():
    """Runs uvicorn server in a dedicated thread."""
    config = uvicorn.Config(
        app=app,
        host=HOST,
        port=PORT,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()


def wait_for_server(timeout_sec=15):
    """Waits until the FastAPI local server is reachable."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with urllib.request.urlopen(f"{SERVER_URL}/", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    print("=" * 60)
    print("  LOCUS v3.1: Cursor for Scientific Integrity")
    print(f"  Mode: 100% Offline | Alamat: {SERVER_URL}")
    print("=" * 60)

    # 1. Start server in daemon thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 2. Wait for server readiness
    print("Memulai server audit neuro-simbolik lokal...")
    time.sleep(1.0)

    # 3. Check pywebview for desktop native shell
    has_webview = False
    try:
        import webview
        has_webview = True
    except ImportError:
        has_webview = False

    if has_webview:
        print("Membuka jendela aplikasi desktop native (pywebview)...")
        window = webview.create_window(
            title="LOCUS: Cursor for Scientific Integrity",
            url=SERVER_URL,
            width=1366,
            height=860,
            min_size=(960, 640),
            text_select=True
        )
        webview.start()
    else:
        print("Membuka antarmuka melalui peramban web bawaan...")
        webbrowser.open(SERVER_URL)
        print("Tekan Ctrl+C di terminal ini untuk menghentikan aplikasi.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMenghentikan LOCUS. Sampai jumpa!")
            sys.exit(0)


if __name__ == "__main__":
    main()
