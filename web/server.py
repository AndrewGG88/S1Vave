#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""
S1Vave & Roland S-1 Dual Calibration Web Server with Real-time PipeWire Audio API.
Serves static web files (docs/sim and web/editor) and provides REST endpoints for
live audio routing, A/B monitoring, and volume adjustments.
"""

import sys
import os
import json
import http.server
import socketserver

# Add tools directory to path to import audio_monitor
TOOLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import audio_monitor

DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "sim"))
EDITOR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "editor"))

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

class CalibrationServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DOCS_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def translate_path(self, path):
        clean_path = path.split("?", 1)[0].split("#", 1)[0]
        if clean_path.startswith("/web/editor/"):
            rel = clean_path[len("/web/editor/"):]
            return os.path.join(EDITOR_DIR, rel) if rel else os.path.join(EDITOR_DIR, "index.html")
        elif clean_path == "/web/editor":
            return os.path.join(EDITOR_DIR, "index.html")
        elif clean_path.startswith("/editor/"):
            rel = clean_path[len("/editor/"):]
            return os.path.join(EDITOR_DIR, rel) if rel else os.path.join(EDITOR_DIR, "index.html")
        elif clean_path == "/editor":
            return os.path.join(EDITOR_DIR, "index.html")
        return super().translate_path(path)

    def do_GET(self):
        clean_path = self.path.split("?", 1)[0]
        if clean_path == "/api/audio" or clean_path.startswith("/api/audio/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            status = audio_monitor.get_audio_status()
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return

        # Redirect /web/editor to /web/editor/ and /editor to /editor/
        if clean_path in ("/web/editor", "/editor"):
            self.send_response(301)
            self.send_header("Location", clean_path + "/")
            self.end_headers()
            return

        super().do_GET()

    def do_POST(self):
        if self.path == "/api/audio/route":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}

            mode = data.get("mode", "both")
            sink = data.get("sink", None)
            audio_monitor.set_monitor_mode(mode, sink)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            status = audio_monitor.get_audio_status()
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return

        elif self.path == "/api/audio/volume":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}

            dev = data.get("device", "master")
            vol = data.get("volume", 1.0)
            audio_monitor.set_device_volume(dev, vol)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            status = audio_monitor.get_audio_status()
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

def run_server(port=8737):
    with ThreadedTCPServer(("", port), CalibrationServerHandler) as httpd:
        print(f"Serving S1Vave Simulator & Editor on http://localhost:{port}/")
        audio_monitor.set_monitor_mode("both")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8737
    run_server(port)
