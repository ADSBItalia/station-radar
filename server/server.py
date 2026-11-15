#!/usr/bin/env python3
"""
ADSBItalia Station Radar - Embedded Lightweight Server
Handles:
  - Static file serving (web UI, data, db, images)
  - GET/POST /api/config (Safe JSON configuration management)
  - GET /api/aircraft.json (Proxy / local cache to avoid CORS & mixed content)
  - GET /api/receiver.json
  - GET /api/route/<callsign> & POST /api/routes (Route resolution via hexdb)
  - POST /api/upload-logo (Custom station logo / favicon upload)
Zero external dependencies (standard library only).
"""

import os
import sys
import json
import re
import mimetypes
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8088))
ENV_TAR1090_URL = os.environ.get("TAR1090_URL")
ENV_FEEDER_URL = os.environ.get("FEEDER_URL") or ENV_TAR1090_URL
ENV_AIRCRAFT_URL = os.environ.get("AIRCRAFT_URL")
ENV_RECEIVER_URL = os.environ.get("RECEIVER_URL")

# Auto-derive endpoints if TAR1090_URL or FEEDER_URL is specified
if ENV_FEEDER_URL:
    clean = ENV_FEEDER_URL.rstrip("/")
    if clean.endswith("/aircraft.json"):
        ENV_AIRCRAFT_URL = clean
        ENV_RECEIVER_URL = clean.replace("aircraft.json", "receiver.json")
    elif clean.endswith("/data"):
        ENV_AIRCRAFT_URL = f"{clean}/aircraft.json"
        ENV_RECEIVER_URL = f"{clean}/receiver.json"
    else:
        ENV_AIRCRAFT_URL = f"{clean}/data/aircraft.json"
        ENV_RECEIVER_URL = f"{clean}/data/receiver.json"
elif ENV_AIRCRAFT_URL and not ENV_RECEIVER_URL:
    if "aircraft.json" in ENV_AIRCRAFT_URL:
        ENV_RECEIVER_URL = ENV_AIRCRAFT_URL.replace("aircraft.json", "receiver.json")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_DIR = os.path.join(BASE_DIR, "web")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DEFAULT_CONFIG_PATH = os.path.join(WEB_DIR, "config.example.json")

# In-memory route cache (callsign -> route data)
ROUTE_CACHE = {}

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
            "name": "ADS-B Station",
            "subtitle": "Live ADS-B Receiver",
            "logo_url": "station-logo.svg",
            "website_url": "https://adsbitalia.it",
            "lat": None,
            "lon": None,
            "alt_m": 0,
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
                cfg = json.load(f)
                # Ensure defaults for logo and name if missing or legacy
                st = cfg.setdefault("station", {})
                if not st.get("name") or "Fiscaglia" in st.get("name", ""):
                    st["name"] = "ADS-B Station"
                if not st.get("logo_url") or "fiscaglia" in st.get("logo_url", "").lower():
                    st["logo_url"] = "station-logo.svg"
                return cfg
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

def resolve_single_route(callsign):
    if not callsign:
        return None
    cs = callsign.strip().upper()
    if cs in ROUTE_CACHE:
        return ROUTE_CACHE[cs]
    
    # Query hexdb
    url = f"https://hexdb.io/api/v1/route/icao/{cs}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ADSBItalia-StationRadar/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            route_str = data.get("route", "")
            if route_str and "-" in route_str:
                parts = route_str.split("-")
                orig = parts[0].strip()
                dest = parts[1].strip()
                res_obj = {
                    "callsign": cs,
                    "route": route_str,
                    "_airports": [
                        {"icao": orig},
                        {"icao": dest}
                    ]
                }
                ROUTE_CACHE[cs] = res_obj
                return res_obj
    except Exception:
        pass
    
    empty_obj = {"callsign": cs, "_airports": []}
    ROUTE_CACHE[cs] = empty_obj
    return empty_obj

class StationRadarHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")

        # Route: API Configuration
        if clean_path == "/api/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            cfg = load_config()
            self.wfile.write(json.dumps(cfg).encode("utf-8"))
            return

        # Route: Proxy / Local live aircraft data
        if clean_path == "/api/aircraft.json":
            self.proxy_aircraft_json()
            return

        # Route: Proxy / Local receiver data
        if clean_path == "/api/receiver.json":
            self.proxy_receiver_json()
            return

        # Route: Single Route Lookup
        if clean_path.startswith("/api/route/"):
            callsign = clean_path.split("/")[-1].strip().upper()
            route_data = resolve_single_route(callsign)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps([route_data] if route_data else []).encode("utf-8"))
            return

        # Route: Proxy / Local Flags (serves local bundled SVG, or fetches from adsbitalia CDN)
        if clean_path.startswith("/flags/"):
            clean_rel = clean_path.lstrip("/")
            local_flag = os.path.join(WEB_DIR, clean_rel)
            if os.path.exists(local_flag):
                return super().do_GET()
            try:
                remote_url = f"https://adsbitalia.it{self.path}"
                req = urllib.request.Request(remote_url, headers={"User-Agent": "ADSBItalia-Station-Radar/1.0"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = resp.read()
                try:
                    os.makedirs(os.path.dirname(local_flag), exist_ok=True)
                    with open(local_flag, "wb") as f:
                        f.write(data)
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                self.send_response(404)
                self.end_headers()
                return

        # Route: Proxy / Local Aircraft Silhouettes
        if clean_path.startswith("/aircraft_sil/"):
            clean_rel = clean_path.lstrip("/")
            local_sil = os.path.join(WEB_DIR, clean_rel)
            if os.path.exists(local_sil):
                return super().do_GET()
            try:
                remote_url = f"https://adsbitalia.it{self.path}"
                req = urllib.request.Request(remote_url, headers={"User-Agent": "ADSBItalia-Station-Radar/1.0"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = resp.read()
                try:
                    os.makedirs(os.path.dirname(local_sil), exist_ok=True)
                    with open(local_sil, "wb") as f:
                        f.write(data)
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                self.send_response(404)
                self.end_headers()
                return

        # Route: Settings redirect
        if clean_path == "/settings":
            self.send_response(302)
            self.send_header("Location", "settings.html")
            self.end_headers()
            return

        if clean_path == "":
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")

        # Route: Proxy Live Routes API
        if clean_path.startswith("/api/0/routeset"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                req_body = self.rfile.read(length)
                remote_url = "https://adsbitalia.it/api/0/routeset"
                req = urllib.request.Request(
                    remote_url,
                    data=req_body,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "ADSBItalia-Station-Radar/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    resp_data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp_data)
                return
            except Exception as e:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"[]")
                return

        # Route: Save Configuration
        if clean_path == "/api/config":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                new_cfg = json.loads(body)
                current = load_config()

                for sec in ["station", "source", "theme", "features"]:
                    if sec in new_cfg and isinstance(new_cfg[sec], dict):
                        current.setdefault(sec, {}).update(new_cfg[sec])

                if save_config(current):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "config": current}).encode("utf-8"))
                else:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "message": "Failed to write config"}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
            return

        # Route: Batch Route Resolution
        if clean_path == "/api/routes":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body)
                planes = payload.get("planes", [])
                results = []
                for p in planes:
                    cs = p.get("callsign", "").strip().upper()
                    if cs:
                        r = resolve_single_route(cs)
                        if r and r.get("_airports"):
                            results.append(r)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(results).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps([]).encode("utf-8"))
                return

        # Route: Custom Logo Upload
        if clean_path == "/api/upload-logo":
            try:
                length = int(self.headers.get("Content-Length", 0))
                content_type = self.headers.get("Content-Type", "")
                
                # Check for direct raw image body or multipart
                if "image/" in content_type:
                    ext = ".png"
                    if "svg" in content_type:
                        ext = ".svg"
                    elif "jpeg" in content_type or "jpg" in content_type:
                        ext = ".jpg"
                    dest_name = f"custom-logo{ext}"
                    dest_path = os.path.join(WEB_DIR, dest_name)
                    data = self.rfile.read(length)
                    with open(dest_path, "wb") as f:
                        f.write(data)
                    
                    cfg = load_config()
                    cfg.setdefault("station", {})["logo_url"] = dest_name
                    save_config(cfg)
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "logo_url": dest_name}).encode("utf-8"))
                    return

                # If multipart/form-data
                body = self.rfile.read(length)
                # Save as custom-logo.png
                dest_name = "custom-logo.png"
                dest_path = os.path.join(WEB_DIR, dest_name)
                # Find PNG / JPEG / SVG header in multipart
                png_sig = b"\x89PNG\r\n\x1a\n"
                jpg_sig = b"\xff\xd8\xff"
                svg_sig = b"<svg"
                
                saved = False
                if png_sig in body:
                    start = body.find(png_sig)
                    end = body.find(b"\r\n--", start)
                    file_data = body[start:end] if end != -1 else body[start:]
                    with open(dest_path, "wb") as f:
                        f.write(file_data)
                    saved = True
                elif jpg_sig in body:
                    start = body.find(jpg_sig)
                    end = body.find(b"\r\n--", start)
                    file_data = body[start:end] if end != -1 else body[start:]
                    dest_name = "custom-logo.jpg"
                    dest_path = os.path.join(WEB_DIR, dest_name)
                    with open(dest_path, "wb") as f:
                        f.write(file_data)
                    saved = True
                elif svg_sig in body:
                    start = body.find(svg_sig)
                    end = body.find(b"</svg>", start)
                    file_data = body[start:end+6] if end != -1 else body[start:]
                    dest_name = "custom-logo.svg"
                    dest_path = os.path.join(WEB_DIR, dest_name)
                    with open(dest_path, "wb") as f:
                        f.write(file_data)
                    saved = True

                if saved:
                    cfg = load_config()
                    cfg.setdefault("station", {})["logo_url"] = dest_name
                    save_config(cfg)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "logo_url": dest_name}).encode("utf-8"))
                    return

                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "No valid image detected"}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def proxy_aircraft_json(self):
        local_candidates = [
            "/run/readsb/aircraft.json",
            "/run/dump1090-fa/aircraft.json",
            "/var/run/readsb/aircraft.json",
            "/opt/adsb/ultrafeeder/readsb/aircraft.json"
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

        cfg = load_config()
        configured_url = ENV_AIRCRAFT_URL or cfg.get("source", {}).get("aircraft_url", "http://127.0.0.1/data/aircraft.json")

        candidates_to_try = [configured_url]
        fallback_probes = [
            "http://127.0.0.1:8080/data/aircraft.json",
            "http://127.0.0.1/data/aircraft.json",
            "http://127.0.0.1:8080/tar1090/data/aircraft.json",
            "http://127.0.0.1/tar1090/data/aircraft.json",
            "http://ultrafeeder/data/aircraft.json",
            "http://ultrafeeder:8080/data/aircraft.json",
        ]
        for p in fallback_probes:
            if p not in candidates_to_try:
                candidates_to_try.append(p)

        last_error = "No endpoint answered"
        for url in candidates_to_try:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ADSBItalia-Station-Radar/1.0"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = resp.read()
                if url != configured_url and not ENV_AIRCRAFT_URL:
                    cfg.setdefault("source", {})["aircraft_url"] = url
                    save_config(cfg)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as e:
                last_error = str(e)
                if url == configured_url and ENV_AIRCRAFT_URL:
                    break
                if url == configured_url and configured_url not in ["http://127.0.0.1/data/aircraft.json", "http://localhost/data/aircraft.json"]:
                    break

        self.send_response(502)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "now": 0,
            "messages": 0,
            "aircraft": [],
            "error": f"Failed to connect to ADS-B source ({last_error})"
        }).encode("utf-8"))

    def proxy_receiver_json(self):
        local_candidates = [
            "/run/readsb/receiver.json",
            "/run/dump1090-fa/receiver.json",
            "/var/run/readsb/receiver.json",
            "/opt/adsb/ultrafeeder/readsb/receiver.json"
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
        configured_url = ENV_RECEIVER_URL or cfg.get("source", {}).get("receiver_url", "http://127.0.0.1/data/receiver.json")

        candidates_to_try = [configured_url]
        fallback_probes = [
            "http://127.0.0.1:8080/data/receiver.json",
            "http://127.0.0.1/data/receiver.json",
            "http://127.0.0.1:8080/tar1090/data/receiver.json",
            "http://127.0.0.1/tar1090/data/receiver.json",
            "http://ultrafeeder/data/receiver.json",
            "http://ultrafeeder:8080/data/receiver.json",
        ]
        for p in fallback_probes:
            if p not in candidates_to_try:
                candidates_to_try.append(p)

        for url in candidates_to_try:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ADSBItalia-Station-Radar/1.0"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception:
                if url == configured_url and ENV_RECEIVER_URL:
                    break
                if url == configured_url and configured_url not in ["http://127.0.0.1/data/receiver.json", "http://localhost/data/receiver.json"]:
                    break

        st = cfg.get("station", {})
        fallback = {
            "version": "ADSBItalia Station Radar 1.0",
            "lat": st.get("lat"),
            "lon": st.get("lon"),
            "alt": st.get("alt_m", 0)
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
