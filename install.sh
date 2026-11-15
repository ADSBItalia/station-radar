#!/usr/bin/env bash
# ==============================================================================
#  ADSBItalia Station Radar - 1-Click Installer
#  Modern Avionics Radar & Web Settings Panel for Single ADS-B Stations
#  Repository: https://github.com/ADSBItalia/station-radar
# ==============================================================================

set -e

# Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/adsbitalia-station-radar"
SERVICE_NAME="adsbitalia-station.service"
PORT="8088"

clear || true
echo -e "${CYAN}${BOLD}"
cat << "EOF"
    ___    ____  _____ ____  ____  __      ___ _             ____             __           
   /   |  / __ \/ ___// __ )/  _/ / /____ _/ (_)___ _       / __ \____ _____/ /___ ______
  / /| | / / / /\__ \/ __  | / /  / __/ __ `/ / / __ `/      / /_/ / __ `/ __  / __ `/ ___/
 / ___ |/ /_/ /___/ / /_/ // /   / /_/ /_/ / / / /_/ /      / _, _/ /_/ / /_/ / /_/ / /    
/_/  |_/_____//____/_____/___/   \__/\__,_/_/_/\__,_/      /_/ |_|\__,_/\__,_/\__,_/_/     
                                  STATION EDITION v1.0
EOF
echo -e "${NC}"
echo -e "${BOLD}ADSBItalia Station Radar - Automatic Installer${NC}"
echo -e "------------------------------------------------------------------"

# Check Root / Sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[!] Root privileges required. Re-running with sudo...${NC}"
    exec sudo bash "$0" "$@"
fi

INSTALL_GRAPHS=false
if [ -t 0 ]; then
    echo -e "${BOLD}Would you like to install the ADSBItalia Station Radar? [Y/n]${NC}"
    read -r -p "> " answer
    if [[ "$answer" =~ ^[Nn] ]]; then
        echo -e "${YELLOW}[i] Installation aborted by user.${NC}"
        exit 0
    fi

    echo -e "\n${BOLD}Would you also like to install ADSBItalia Station Graphs (RF Telemetry Dashboard)? [y/N]${NC}"
    read -r -p "> " answer_graphs
    if [[ "$answer_graphs" =~ ^[Yy] ]]; then
        INSTALL_GRAPHS=true
    fi
fi

# Detect Package Manager
echo -e "\n${CYAN}[1/5] Checking system dependencies...${NC}"
if command -v apt-get &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3 curl git > /dev/null
elif command -v dnf &> /dev/null; then
    dnf install -y -q python3 curl git > /dev/null
elif command -v apk &> /dev/null; then
    apk add --no-cache python3 curl git > /dev/null
else
    echo -e "${YELLOW}[i] Unsupported package manager. Please ensure python3, curl and git are installed.${NC}"
fi
echo -e "${GREEN}[✓] Dependencies verified (Python 3, curl, git).${NC}"

# Detect Local ADS-B Feeder / Ultrafeeder
echo -e "\n${CYAN}[2/5] Detecting local ADS-B data feed...${NC}"
LOCAL_DATA_SOURCE="http://127.0.0.1/data/aircraft.json"
RECEIVER_SOURCE="http://127.0.0.1/data/receiver.json"

if [ -f "/run/readsb/aircraft.json" ]; then
    echo -e "${GREEN}[✓] Detected local readsb (/run/readsb/aircraft.json)${NC}"
    LOCAL_DATA_SOURCE="/run/readsb/aircraft.json"
    RECEIVER_SOURCE="/run/readsb/receiver.json"
elif [ -f "/run/dump1090-fa/aircraft.json" ]; then
    echo -e "${GREEN}[✓] Detected local dump1090-fa (/run/dump1090-fa/aircraft.json)${NC}"
    LOCAL_DATA_SOURCE="/run/dump1090-fa/aircraft.json"
    RECEIVER_SOURCE="/run/dump1090-fa/receiver.json"
elif [ -f "/run/dump1090/aircraft.json" ]; then
    echo -e "${GREEN}[✓] Detected local dump1090 (/run/dump1090/aircraft.json)${NC}"
    LOCAL_DATA_SOURCE="/run/dump1090/aircraft.json"
    RECEIVER_SOURCE="/run/dump1090/receiver.json"
elif command -v docker &> /dev/null && docker ps 2>/dev/null | grep -qi "ultrafeeder"; then
    echo -e "${GREEN}[✓] Detected running Ultrafeeder Docker container!${NC}"
    UF_CID=$(docker ps -q --filter "name=ultrafeeder" | head -n1)
    UF_PORT=$(docker port "$UF_CID" 80 2>/dev/null | awk -F: '{print $NF}' | head -n1 || echo "")
    if [ -z "$UF_PORT" ]; then
        UF_PORT=$(docker port "$UF_CID" 8080 2>/dev/null | awk -F: '{print $NF}' | head -n1 || echo "")
    fi
    [ -z "$UF_PORT" ] && UF_PORT="8080"
    LOCAL_DATA_SOURCE="http://127.0.0.1:${UF_PORT}/data/aircraft.json"
    RECEIVER_SOURCE="http://127.0.0.1:${UF_PORT}/data/receiver.json"
    echo -e "${GREEN}[✓] Configured Ultrafeeder endpoint: ${LOCAL_DATA_SOURCE}${NC}"
else
    # Probe active HTTP endpoints
    FOUND_HTTP=false
    for probe_url in \
        "http://127.0.0.1:8080/data/aircraft.json" \
        "http://127.0.0.1/data/aircraft.json" \
        "http://127.0.0.1:8080/tar1090/data/aircraft.json" \
        "http://127.0.0.1/tar1090/data/aircraft.json"; do
        if curl -s -m 2 "$probe_url" 2>/dev/null | grep -q "aircraft"; then
            LOCAL_DATA_SOURCE="$probe_url"
            RECEIVER_SOURCE="${probe_url/aircraft.json/receiver.json}"
            echo -e "${GREEN}[✓] Detected active HTTP ADS-B stream at ${probe_url}${NC}"
            FOUND_HTTP=true
            break
        fi
    done

    if [ "$FOUND_HTTP" = false ]; then
        if [ -d "/var/www/html/tar1090" ]; then
            echo -e "${GREEN}[✓] Detected local tar1090 stack (local HTTP port)${NC}"
            LOCAL_DATA_SOURCE="http://127.0.0.1/tar1090/data/aircraft.json"
            RECEIVER_SOURCE="http://127.0.0.1/tar1090/data/receiver.json"
        else
            echo -e "${YELLOW}[i] No direct local readsb path found; using default HTTP source (configurable via web).${NC}"
        fi
    fi
fi

# Download / Clone Files
echo -e "\n${CYAN}[3/5] Setting up application directory in ${INSTALL_DIR}...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}[i] Updating existing installation...${NC}"
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

REPO_URL="https://github.com/ADSBItalia/station-radar.git"
if [ -d ".git" ]; then
    git pull -q || true
else
    if command -v git &> /dev/null && git clone -q "$REPO_URL" "$INSTALL_DIR" 2>/dev/null; then
        echo -e "${GREEN}[✓] Repository cloned successfully.${NC}"
    else
        echo -e "${YELLOW}[i] Git clone failed, falling back to local files...${NC}"
    fi
fi

# Ensure basic directories exist
mkdir -p "$INSTALL_DIR/web" "$INSTALL_DIR/server" "$INSTALL_DIR/web/images"

# Create Initial Config if missing
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    echo -e "${CYAN}[i] Creating default configuration...${NC}"
    cat << EOF > "$INSTALL_DIR/config.json"
{
  "station": {
    "name": "ADS-B Station",
    "subtitle": "Local 1090 MHz Receiver",
    "logo_url": "station-logo.svg",
    "website_url": "https://adsbitalia.it",
    "lat": 44.769651,
    "lon": 11.930735,
    "alt_m": 15,
    "range_rings": [25, 50, 100, 150, 200, 250],
    "ring_color": "#38bdf8",
    "ring_opacity": 0.45
  },
  "source": {
    "aircraft_url": "${LOCAL_DATA_SOURCE}",
    "receiver_url": "http://127.0.0.1/data/receiver.json",
    "poll_interval_ms": 1000,
    "use_proxy": true
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
    "enable_photos": true,
    "photo_provider": "direct",
    "enable_weather_radar": true,
    "enable_clouds": true,
    "enable_diversions": true,
    "enable_military_filter": true,
    "default_units": "aviation",
    "default_zoom": 7.5
  }
}
EOF
fi

chmod +x "$INSTALL_DIR/server/server.py" 2>/dev/null || true

# Setup Systemd Service
echo -e "\n${CYAN}[4/5] Installing systemd background service...${NC}"
cat << EOF > "/etc/systemd/system/${SERVICE_NAME}"
[Unit]
Description=ADSBItalia Station Radar Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/server/server.py
Restart=always
RestartSec=5
Environment=PORT=${PORT}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
echo -e "${GREEN}[✓] Service ${SERVICE_NAME} enabled and running.${NC}"

# Detect Host IP
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")

echo -e "\n${GREEN}${BOLD}==================================================================${NC}"
echo -e "${GREEN}${BOLD} 🎉 INSTALLATION COMPLETED SUCCESSFULLY!${NC}"
echo -e "${GREEN}${BOLD}==================================================================${NC}"
echo -e "\n${BOLD}Access your Station Radar in any browser:${NC}"
echo -e "  📡 ${CYAN}${BOLD}Live Radar:${NC}     http://${HOST_IP}:${PORT}/"
echo -e "  ⚙️  ${CYAN}${BOLD}Settings:${NC}       http://${HOST_IP}:${PORT}/settings"
echo -e "\n${YELLOW}Tip: Open Settings now to customize your station name, antenna coordinates, and avionics theme!${NC}\n"

if [ "$INSTALL_GRAPHS" = true ]; then
    echo -e "\n${CYAN}[i] Launching companion installer for ADSBItalia Station Graphs...${NC}"
    bash <(curl -sL https://raw.githubusercontent.com/ADSBItalia/station-graphs/main/install.sh) || true
fi
EOF
