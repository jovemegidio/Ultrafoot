# -*- coding: utf-8 -*-
"""
Ultrafoot — Lightweight HTTP Server (Tauri Sidecar)
====================================================
Zero-dependency HTTP bridge that exposes UltrafootAPI methods as
POST /api/<method>.  Uses only Python's stdlib (http.server) to
keep the sidecar build small (<50 MB vs ~130 MB with FastAPI).

The Tauri Rust shell reads stdout for the ULTRAFOOT_PORT=<port> line
and then navigates the webview to http://127.0.0.1:<port>.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from desktop_app import UltrafootAPI

# PyInstaller --onefile extracts data to sys._MEIPASS
_BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
_api = UltrafootAPI()

# MIME types for static files
_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
}


class UltrafootHandler(BaseHTTPRequestHandler):
    """Routes requests to static files or the UltrafootAPI bridge."""

    # Suppress per-request log lines for performance
    def log_message(self, fmt, *args):
        pass

    # ── CORS preflight ──
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ── Static files & index ──
    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/" or path == "":
            path = "/index.html"

        # Resolve safely — prevent path traversal
        safe = os.path.normpath(path.lstrip("/"))
        if safe.startswith(".."):
            self._err(403, "Forbidden")
            return

        full = os.path.join(_BASE, safe)
        if os.path.isfile(full):
            ext = os.path.splitext(full)[1].lower()
            mime = _MIME.get(ext, "application/octet-stream")
            try:
                with open(full, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self._err(500, "Read error")
        else:
            self._err(404, "Not found")

    # ── API bridge ──
    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            self._err(404, "Not found")
            return

        method = path[5:]  # strip "/api/"
        if method.startswith("_") or not method:
            self._err(403, "Forbidden")
            return

        fn = getattr(_api, method, None)
        if fn is None or not callable(fn):
            self._err(404, f"Unknown method: {method}")
            return

        # Read body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        try:
            args = json.loads(body) if body else []
            if not isinstance(args, list):
                args = [args]
        except json.JSONDecodeError:
            args = []

        # Call API
        try:
            result_str = fn(*args)
            # UltrafootAPI methods return JSON strings
            if isinstance(result_str, str):
                try:
                    result = json.loads(result_str)
                except (json.JSONDecodeError, TypeError):
                    result = result_str
            else:
                result = result_str
            payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
        except Exception as e:
            payload = json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── Helpers ──
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "http://tauri.localhost")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _err(self, code, msg):
        payload = json.dumps({"error": msg}).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class ThreadedHTTPServer(HTTPServer):
    """Handle each request in a new thread for non-blocking API calls."""
    allow_reuse_address = True
    daemon_threads = True

    def process_request(self, request, client_address):
        t = threading.Thread(target=self.process_request_thread,
                             args=(request, client_address), daemon=True)
        t.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port = int(os.environ.get("ULTRAFOOT_PORT", "0"))
    if port == 0:
        port = _find_free_port()

    server = ThreadedHTTPServer(("127.0.0.1", port), UltrafootHandler)

    # Tauri reads this line from stdout to discover the port
    print(f"ULTRAFOOT_PORT={port}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
