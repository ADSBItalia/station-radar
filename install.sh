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
echo -e "${BOLD}Installazione Automatica ADSBItalia Station Radar${NC}"
echo -e "------------------------------------------------------------------"

# Check Root / Sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[!] Questo script richiede i privilegi di root. Rieseguo con sudo...${NC}"
    exec sudo bash "$0" "$@"
fi

# Detect Package Manager
echo -e "\n${CYAN}[1/5] Verifica dipendenze di sistema...${NC}"
if command -v apt-get &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3 curl git > /dev/null
elif command -v dnf &> /dev/null; then
    dnf install -y -q python3 curl git > /dev/null
elif command -v apk &> /dev/null; then
    apk add --no-cache python3 curl git > /dev/null
else
    echo -e "${RED}[X] Gestore pacchetti non supportato automaticamente. Assicurati che python3, curl e git siano installati.${NC}"
fi
echo -e "${GREEN}[✓] Dipendenze verificate (Python 3, curl, git).${NC}"

# Detect Local ADS-B Feeder
echo -e "\n${CYAN}[2/5] Rilevamento sorgente dati ADS-B locale...${NC}"
LOCAL_DATA_SOURCE="http://127.0.0.1/data/aircraft.json"

if [ -f "/run/readsb/aircraft.json" ]; then
    echo -e "${GREEN}[✓] Rilevato readsb locale (/run/readsb/aircraft.json)${NC}"
    LOCAL_DATA_SOURCE="/run/readsb/aircraft.json"
elif [ -f "/run/dump1090-fa/aircraft.json" ]; then
    echo -e "${GREEN}[✓] Rilevato dump1090-fa locale (/run/dump1090-fa/aircraft.json)${NC}"
    LOCAL_DATA_SOURCE="/run/dump1090-fa/aircraft.json"
elif [ -f "/run/dump1090/aircraft.json" ]; then
    echo -e "${GREEN}[✓] Rilevato dump1090 locale (/run/dump1090/aircraft.json)${NC}"
    LOCAL_DATA_SOURCE="/run/dump1090/aircraft.json"
elif [ -d "/var/www/html/tar1090" ]; then
    echo -e "${GREEN}[✓] Rilevato stack tar1090 (porta HTTP locale)${NC}"
    LOCAL_DATA_SOURCE="http://127.0.0.1/tar1090/data/aircraft.json"
else
    echo -e "${YELLOW}[i] Nessun readsb locale diretto trovato, userò sorgente HTTP predefinita (configurabile da web).${NC}"
fi

# Download / Clone Files
echo -e "\n${CYAN}[3/5] Configurazione cartella applicazione in ${INSTALL_DIR}...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}[i] Aggiornamento installazione esistente...${NC}"
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

REPO_URL="https://github.com/ADSBItalia/station-radar.git"
if [ -d ".git" ]; then
    git pull -q || true
else
    if command -v git &> /dev/null && git clone -q "$REPO_URL" "$INSTALL_DIR" 2>/dev/null; then
        echo -e "${GREEN}[✓] Repository clonato con successo.${NC}"
    else
        echo -e "${YELLOW}[i] Clone da git non riuscito, estrazione pacchetto locale in corso...${NC}"
    fi
fi

# Ensure basic directories exist
mkdir -p "$INSTALL_DIR/web" "$INSTALL_DIR/server" "$INSTALL_DIR/web/images"

# Create Initial Config if missing
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    echo -e "${CYAN}[i] Creazione configurazione iniziale personalizzata...${NC}"
    cat << EOF > "$INSTALL_DIR/config.json"
{
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
    "photo_provider": "adsbitalia_proxy",
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
echo -e "\n${CYAN}[4/5] Installazione servizio di avvio automatico (systemd)...${NC}"
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
echo -e "${GREEN}[✓] Servizio ${SERVICE_NAME} abilitato e avviato.${NC}"

# Detect Host IP
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")

echo -e "\n${GREEN}${BOLD}==================================================================${NC}"
echo -e "${GREEN}${BOLD} 🎉 INSTALLAZIONE COMPLETATA CON SUCCESSO!${NC}"
echo -e "${GREEN}${BOLD}==================================================================${NC}"
echo -e "\n${BOLD}Puoi ora accedere al tuo Radar Station da qualsiasi browser:${NC}"
echo -e "  📡 ${CYAN}${BOLD}Radar Live:${NC}         http://${HOST_IP}:${PORT}/"
echo -e "  ⚙️  ${CYAN}${BOLD}Pannello Opzioni:${NC}   http://${HOST_IP}:${PORT}/settings"
echo -e "\n${YELLOW}Consiglio: Apri subito la pagina Impostazioni per inserire il nome della tua stazione e le coordinate esatte della tua antenna!${NC}\n"
EOF
