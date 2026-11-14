#!/usr/bin/env python3
"""
ADSBItalia Station Radar - Embedded Lightweight Server
Handles:
  - Static file serving (web UI, data, db, images)
  - GET/POST /api/config (Safe JSON configuration management)
  - GET /api/aircraft.json (Proxy / local cache to avoid CORS & mixed content)
  - GET /api/receiver.json
  - POST /api/upload-logo (Optional custom station logo upload)
Zero external dependencies (uses standard library only: http.server, urllib, json).
"""

import os
import sys
import json
import mimetypes
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
import cgi

PORT = int(os.environ.get("PORT", 8088))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_DIR = os.path.join(BASE_DIR, "web")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DEFAULT_CONFIG_PATH = os.path.join(WEB_DIR, "config.example.json")

# Ensure mime types are registered
mimetypes.init()
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("application/geo+json", ".geojson")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

def get_default_config():
    return {
        "station": {
            "name": "Stazione ADS-B",
            "subtitle": "Ricevitore Locale 1090 MHz",
            "logo_url": "fiscaglia-favicon.svg",
            "website_url": "https://adsbitalia.it",
            "lat": 44.769651,
            "lon": 11.930735,
            "alt_m": 15,
            "range_rings": [25, 50, 100, 150, 200, 250],
            "ring_color": "#38bdf8",
            "ring_opacity": 0.45
        },
        "source": {
            "aircraft_url": "http://127.0.0.1/data/aircraft.json",
            "receiver_url": "http://127.0.0.1/data/receiver.json",
            "poll_interval_ms": 1000,
            "use_proxy": True
        },
        "theme": {
            "preset": "cyan",
            "primary_color": "#38bdf8",
            "bg_dark": "#050c14",
            "bg_panel": "rgba(7, 23, 36, 0.94)",
            "bg_card": "rgba(11, 34, 52, 0.96)",
            "border_color": "rgba(56, 189, 248, 0.22)",
            "accent_glow": "rgba(56, 189, 248, 0.45)"
        },
        "features": {
            "enable_photos": True,
            "photo_provider": "adsbitalia_proxy",
            "enable_weather_radar": True,
            "enable_clouds": True,
            "enable_diversions": True,
            "enable_military_filter": True,
            "default_units": "aviation",
            "default_zoom": 7.5
        }
    }

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Error reading {CONFIG_PATH}: {e}, using default.")
    
    cfg = get_default_config()
    save_config(cfg)
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to write config: {e}")
        return False

class StationRadarHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        # Route: API Configuration
        if self.path == "/api/config" or self.path == "/api/config/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            cfg = load_config()
            self.wfile.write(json.dumps(cfg).encode("utf-8"))
            return

        # Route: Proxy / Local live aircraft.json
        if self.path.startswith("/api/aircraft.json") or self.path.startswith("/data/aircraft.json"):
            self.proxy_aircraft_json()
            return

        # Route: Proxy / Local receiver.json
        if self.path.startswith("/api/receiver.json") or self.path.startswith("/data/receiver.json"):
            self.proxy_receiver_json()
            return

        # Fallback to serving web/ directory static files
        if self.path == "/settings" or self.path == "/settings/":
            self.path = "/settings.html"
        elif self.path == "/" or self.path == "":
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/config" or self.path == "/api/config/":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                new_cfg = json.loads(body)
                
                # Merge / validate basic fields
                current = load_config()
                for section in ["station", "source", "theme", "features"]:
                    if section in new_cfg and isinstance(new_cfg[section], dict):
                        current.setdefault(section, {}).update(new_cfg[section])

                if save_config(current):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "config": current}).encode("utf-8"))
                else:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "Save failed"}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return

        # Upload Custom Logo
        if self.path == "/api/upload-logo":
            try:
                content_type = self.headers.get('Content-Type')
                if not content_type or 'multipart/form-data' not in content_type:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'{"ok":false,"error":"Expected multipart/form-data"}')
                    return

                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST',
                             'CONTENT_TYPE': self.headers['Content-Type']}
                )
                if 'logo' in form:
                    file_item = form['logo']
                    if file_item.file:
                        fn = os.path.basename(file_item.filename or "custom-logo.png")
                        ext = os.path.splitext(fn)[1].lower()
                        if ext not in ['.png', '.jpg', '.jpeg', '.svg', '.webp']:
                            ext = '.png'
                        out_name = f"custom-logo{ext}"
                        out_path = os.path.join(WEB_DIR, "images", out_name)
                        os.makedirs(os.path.dirname(out_path), exist_ok=True)
                        with open(out_path, 'wb') as f:
                            f.write(file_item.file.read())

                        # Update config
                        cfg = load_config()
                        cfg['station']['logo_url'] = f"images/{out_name}"
                        save_config(cfg)

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"ok": True, "logo_url": f"images/{out_name}"}).encode("utf-8"))
                        return

                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"ok":false,"error":"No logo file found in request"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def proxy_aircraft_json(self):
        # 1. First check local standard paths (zero network overhead on local install)
        local_candidates = [
            "/run/readsb/aircraft.json",
            "/run/dump1090-fa/aircraft.json",
            "/run/dump1090/aircraft.json",
            "/var/run/readsb/aircraft.json",
            "/var/run/dump1090-fa/aircraft.json"
        ]
        for path in local_candidates:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass

        # 2. Otherwise proxy from configured aircraft_url
        cfg = load_config()
        url = cfg.get("source", {}).get("aircraft_url", "http://127.0.0.1/data/aircraft.json")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ADSBItalia-Station-Radar/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "now": 0,
                "messages": 0,
                "aircraft": [],
                "error": f"Failed to connect to source: {url} ({str(e)})"
            }).encode("utf-8"))

    def proxy_receiver_json(self):
        local_candidates = [
            "/run/readsb/receiver.json",
            "/run/dump1090-fa/receiver.json",
            "/var/run/readsb/receiver.json"
        ]
        for path in local_candidates:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass
        
        cfg = load_config()
        st = cfg.get("station", {})
        fallback = {
            "version": "ADSBItalia Station Radar 1.0",
            "lat": st.get("lat", 44.769),
            "lon": st.get("lon", 11.930),
            "alt": st.get("alt_m", 15)
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(fallback).encode("utf-8"))

if __name__ == "__main__":
    print(f"==================================================")
    print(f" 📡 ADSBItalia Station Radar Server")
    print(f" Listening on http://0.0.0.0:{PORT}")
    print(f" Radar:     http://localhost:{PORT}/")
    print(f" Settings:  http://localhost:{PORT}/settings")
    print(f"==================================================")
    server = HTTPServer(("0.0.0.0", PORT), StationRadarHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()
