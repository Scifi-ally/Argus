#!/usr/bin/env python3
"""
SinglePass3D — Web UI Studio & 3D Model Viewer Server
Usage:
    python scripts/serve_viewer.py --port 8080
"""

from __future__ import annotations
import argparse
import http.server
import json
import os
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

# Add SIHBackend to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
UI_DIR = ROOT_DIR / "ui"
OUTPUTS_DIR = ROOT_DIR / "outputs"


class SinglePass3DHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """
    Custom HTTP request handler with CORS support, /api/jobs endpoint,
    and automatic mapping for UI and reconstructed 3D output files.
    """

    def end_headers(self):
        # Enable CORS and caching headers for 3D assets
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # Favicon handler
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # API: List all available reconstruction jobs in outputs/
        if path == "/api/jobs":
            jobs = []
            if OUTPUTS_DIR.exists():
                for item in sorted(OUTPUTS_DIR.iterdir()):
                    if item.is_dir() and not item.name.startswith("."):
                        jobs.append(item.name)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(jobs).encode("utf-8"))
            return

        # Serve files from outputs/ directory
        if path.startswith("/outputs/"):
            rel_path = path[len("/outputs/"):]
            file_path = OUTPUTS_DIR / rel_path
            if file_path.exists() and file_path.is_file():
                self._serve_file(file_path)
                return
            else:
                self.send_error(404, f"Output file not found: {rel_path}")
                return

        # Default: Serve static files from ui/
        target_path = UI_DIR / path.lstrip("/")
        if path == "/" or path == "":
            target_path = UI_DIR / "index.html"

        if target_path.exists() and target_path.is_file():
            self._serve_file(target_path)
        else:
            self.send_error(404, f"UI resource not found: {path}")

    def _serve_file(self, file_path: Path):
        ext = file_path.suffix.lower()
        mime_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".glb": "model/gltf-binary",
            ".gltf": "model/gltf+json",
            ".obj": "text/plain",
            ".ply": "application/octet-stream",
            ".mtl": "text/plain",
            ".svg": "image/svg+xml",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".tfw": "text/plain",
            ".pgw": "text/plain",
            ".geojson": "application/geo+json"
        }
        content_type = mime_types.get(ext, "application/octet-stream")
        
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")


def main():
    parser = argparse.ArgumentParser(description="SinglePass3D Web UI Studio Server")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to serve UI on (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")
    args = parser.parse_args()

    server_address = ("", args.port)
    httpd = http.server.ThreadingHTTPServer(server_address, SinglePass3DHTTPHandler)

    url = f"http://localhost:{args.port}"
    print("=" * 65)
    print(" SinglePass3D Interactive Web UI Studio")
    print(f" Server running at: {url}")
    print(f" Serving 3D Outputs from: {OUTPUTS_DIR.resolve()}")
    print("=" * 65)

    if not args.no_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SinglePass3D Web Server...")
        httpd.server_close()


if __name__ == "__main__":
    main()
