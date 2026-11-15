# 📡 ADSBItalia Station Radar

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20%7C%20Linux%20%7C%20Docker-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.7%2B%20(Zero%20Dependencies)-yellow.svg)]()
[![Rust](https://img.shields.io/badge/Rust-Autonomous%20Resolver-orange.svg)]()
[![Community](https://img.shields.io/badge/Community-ADSBItalia.it-cyan.svg)](https://adsbitalia.it)

> **Next-generation avionics radar interface and web control panel for single ADS-B stations.**  
> Transform your local receiver (`readsb`, `dump1090-fa`, `ultrafeeder`, or `tar1090`) into a modern, fluid air traffic control display—fully configurable directly from your web browser with zero terminal editing.

---

## ✨ Key Features

* 🎨 **Modern Avionics Dark UI**: Cockpit-grade dark interface featuring precise directional aircraft silhouettes, animated vector tracks, tactical flight tables, and live telemetry stats.
* ⚙️ **Web-Based Station Settings Panel (`/settings`)**: Configure your entire station directly in the browser:
  * Station name, receiver subtitle, custom website link, and station logo upload.
  * **Interactive coordinate map picker** with drag-and-drop antenna pin and a **one-click GPS location detection button**.
  * Customizable Nautical Mile Range Rings (`25, 50, 100, 150, 200, 250 NM`).
* 🌈 **Dynamic Theme & Color Engine**:
  * 💎 **Avionics Cyan** (Neon cockpit cyan)
  * 🟢 **Radar Emerald** (Military phosphor green)
  * 🟠 **Amber Glow** (Warm Boeing amber)
  * 🟣 **Stealth Night** (Cyberpunk purple)
  * ⚪ **Arctic Mono** (High-contrast clean monochrome)
  * 🔴 **Tactical Red** (Alert mission red)
  * **Custom Color Pickers**: choose your exact accent color and range ring hue with real-time preview before saving!
* 📸 **Direct Multi-Provider Aircraft Photo Engine**: High-resolution aircraft photos loaded dynamically via public CORS APIs (Planespotters.net and Airport-Data.com), with seamless fallback to detailed SVG silhouettes for private or uncataloged aircraft.
* ⚠️ **Live Flight Diversion Detection**: Automatically detects when a flight diverts to an alternate airport (e.g. weather/emergency), displaying diversion alert banners and crossed-out route vectors (`STN ➔ ~~VCE~~ ➔ BLQ`).
* 🌧️ **Live Weather Radar & Satellite Cloud Cover**: Real-time precipitation radar overlay and global NASA GIBS satellite cloud imagery.
* ⚔️ **Tactical Quick Filters**: One-click filtering for Military, Air Ambulance / Medevac, Police & Law Enforcement, Firefighting, State & VIP transports, and Emergency Squawks (7700 / 7600).
* 🦀 **Autonomous Rust Logo Resolver (`resolver/`)**: Bundled with an autonomous Rust engine (`adsbitalia-resolver`) and 12,900+ airline banners. When an unknown aircraft or operator is spotted, it automatically discovers, downloads, trims, and generates standard transparent vector banners locally on your machine!
* ⚡ **100% Independent & Autonomous**: Zero API calls or bandwidth consumption on central servers. Fully self-contained, privacy-friendly, and uses less than 30 MB of RAM.

---

## 🚀 Quickstart Installation

### Method 1: 1-Click Shell Installer (Raspberry Pi OS / Debian / Ubuntu)

If you are running a local feeder on Linux or a Raspberry Pi, run this single command:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ADSBItalia/station-radar/main/install.sh)
```

The installer will automatically:
1. Detect your existing local ADS-B feed (`readsb`, `dump1090-fa`, or `ultrafeeder`).
2. Set up the lightweight station web server.
3. Install and enable the `adsbitalia-station.service` systemd daemon for automatic startup.
4. Provide the local URLs to open your radar and control panel!

---

### Method 2: Docker & Docker Compose

Ideal for users running Docker, Portainer, CasaOS, Unraid, or containerized feeder stacks (`adsb.im` / `ultrafeeder`).

#### Case A: Bare-Metal readsb / dump1090 on the Host:
If readsb or dump1090 runs natively on the host:

```yaml
version: '3.8'

services:
  station-radar:
    image: ghcr.io/adsbitalia/station-radar:latest
    container_name: station-radar
    restart: unless-stopped
    ports:
      - "8088:8088"
    volumes:
      - ./config.json:/app/config.json
      - ./custom_images:/app/web/images/custom
      # Mount local readsb / dump1090 runtime directory:
      - /run/readsb:/run/readsb:ro
    environment:
      - PORT=8088
      - PYTHONUNBUFFERED=1
```

#### Case B: readsb inside a Container (Ultrafeeder / Docker Stack):
If readsb runs inside another container (e.g. Ultrafeeder), **no host volumes are needed**! Simply specify a single parameter `FEEDER_URL`:

```yaml
version: '3.8'

services:
  station-radar:
    image: ghcr.io/adsbitalia/station-radar:latest
    container_name: station-radar
    restart: unless-stopped
    ports:
      - "8088:8088"
    environment:
      - PORT=8088
      - PYTHONUNBUFFERED=1
      # Single parameter: automatically deduces aircraft.json and receiver.json!
      - FEEDER_URL=http://ultrafeeder
```
*(Tip: You can also specify full URLs with `AIRCRAFT_URL=http://ultrafeeder/data/aircraft.json` or `http://host.docker.internal:8080/data/aircraft.json`).*

Start the container:
```bash
docker compose up -d
```

3. Open in your browser:
   * **Live Radar**: `http://<YOUR-IP>:8088/`
   * **Settings Panel**: `http://<YOUR-IP>:8088/settings`

---

## 🛠️ Configuring Your Station

1. Open the **Settings Panel** at `http://<YOUR-IP>:8088/settings`.
2. Enter your **Station Name** (e.g. *Rome ADS-B Station* or *Mike's Flight Radar*).
3. On the **Interactive Map**, click or drag the marker to your antenna's exact location, or click *🎯 Use my GPS location*.
4. Pick your favorite **Avionics Theme** or customize your accent colors.
5. Click **💾 Save Settings**.
6. Click **🚀 Open Live Radar** and enjoy your modern flight tracking dashboard!

---

## 🔌 Feeder Compatibility

ADSBItalia Station Radar works out of the box with all standard ADS-B / Mode-S decoders:
* **readsb** (standard `adsb.im` / `ultrafeeder`)
* **dump1090-fa** (FlightAware PiAware)
* **dump1090-mutability**
* **tar1090** HTTP feeds (`/data/aircraft.json`)
* Any custom receiver exposing standard `aircraft.json` over HTTP or file path.

---

## 🌐 Community & Feed Sharing

ADSBItalia is an independent community flight tracking network. If you operate an ADS-B station in Italy or Europe and wish to contribute your feed:  
👉 Visit [https://adsbitalia.it](https://adsbitalia.it) to learn how to feed in under 2 minutes!

---

## 📄 License

Released under the [MIT License](LICENSE). Free for personal, educational, and amateur radio / aviation community use.
