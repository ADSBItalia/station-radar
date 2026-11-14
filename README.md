# 📡 ADSBItalia Station Radar (Community Edition)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20%7C%20Linux%20%7C%20Docker-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.7%2B%20(Zero%20Dependencies)-yellow.svg)]()
[![Network](https://img.shields.io/badge/Network-ADSBItalia.it-cyan.svg)](https://adsbitalia.it)

> **L'interfaccia radar avionica di nuova generazione per la tua stazione ADS-B.**  
> Trasforma il tuo ricevitore locale (readsb, dump1090-fa, ultrafeeder o tar1090) in un radar da centro di controllo aereo moderno, fluido e completamente configurabile via web.

---

## ✨ Caratteristiche Principali

* 🎨 **Grafica Avionica Moderna**: Tema Dark ispirato ai cockpit e ai radar ATC di ultima generazione. Addio al vecchio look datato di dump1090 e tar1090.
* ⚙️ **Pannello Impostazioni Web Integrato (`/settings`)**: Configura tutto direttamente dal browser, senza mai toccare file di configurazione via terminale:
  * Nome, sottotitolo e logo personalizzato della stazione.
  * **Mappa interattiva** con cursore trascinabile e pulsante GPS per impostare le coordinate esatte dell'antenna.
  * Cerchi di portata (Range Rings in NM) personalizzabili.
* 🌈 **Motore Temi Dinamico**:
  * 💎 **Avionics Cyan** (Ciano neon cockpit)
  * 🟢 **Radar Emerald** (Verde fosforo ATC militare)
  * 🟠 **Amber Glow** (Ambra avionica Boeing)
  * 🟣 **Stealth Night** (Viola cyberpunk)
  * ⚪ **Arctic Mono** (Bianco high-contrast)
  * 🔴 **Tactical Red** (Rosso operativo)
  * **Color Picker personalizzato** per scegliere qualsiasi sfumatura tu preferisca!
* 📸 **Motore Fotografico HD**: Caricamento in tempo reale della fotografia ad alta risoluzione del velivolo selezionato (Planespotters / flotta), con fallback automatico su sagoma vettoriale precisa per aerei militari o non censiti.
* ⚠️ **Allerta Deviazioni di Volo (Flight Diversions)**: Rileva automaticamente se un aereo sta dirottando su un aeroporto alternato (es. causa nebbia o emergenza), mostrando l'allerta avionica e la rotta aggiornata (`STN ➔ ~~VCE~~ ➔ BLQ`).
* 🌧️ **Radar Meteo & Nuvole Satellitari**: Overlay in tempo reale delle precipitazioni piovose e della copertura nuvolosa globale NASA GIBS.
* ⚔️ **Filtri Tattici Speciali**: Filtra istantaneamente con un click voli Militari, Elisoccorso 118, Polizia/Carabinieri, Vigili del Fuoco, Voli di Stato e codici Squawk di emergenza (7700 / 7600).
* ⚡ **Prestazioni Estreme & Zero Dipendenze**: Il server interno è scritto in puro Python (libreria standard) senza necessità di `pip install`. Consuma meno di 30 MB di RAM ed è perfetto per Raspberry Pi Zero/2/3/4/5 e MiniPC.

---

## 🚀 Installazione Rapida

### Metodo 1: Script 1-Click (Raspberry Pi OS / Debian / Ubuntu)

Se hai un Raspberry Pi o un MiniPC con Linux e il tuo ricevitore (readsb o dump1090), incolla questo singolo comando nel terminale:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ADSBItalia/station-radar/main/install.sh)
```

Lo script in automatico:
1. Rileva il feeder ADS-B già presente sul sistema.
2. Installa e avvia il servizio systemd ad avvio automatico (`adsbitalia-station.service`).
3. Ti fornisce il link per aprire il tuo radar e il pannello impostazioni!

---

### Metodo 2: Docker & Docker Compose

Ideale per chi usa **adsb.im**, Portainer, CasaOS, Unraid, Proxmox o stack a container.

1. Clona il repository o crea un file `docker-compose.yml`:

```yaml
version: '3.8'

services:
  adsbitalia-station:
    image: adsbitalia/station-radar:latest
    container_name: adsbitalia-station-radar
    restart: unless-stopped
    ports:
      - "8088:8088"
    volumes:
      - ./config.json:/app/config.json
      - ./images:/app/web/images/custom
    environment:
      - PORT=8088
```

2. Avvia il container:
```bash
docker compose up -d
```

3. Apri il browser all'indirizzo:
   * **Radar Live**: `http://IP-DEL-TUO-SERVER:8088/`
   * **Impostazioni**: `http://IP-DEL-TUO-SERVER:8088/settings`

---

## 🛠️ Come Configurare la Tua Antenna

1. Apri la pagina **Impostazioni** (`http://tuo-ip:8088/settings`).
2. Digita il **Nome della tua stazione** (es. *Stazione ADS-B di Milano*).
3. Nella **Mappa Interattiva**, clicca sul punto esatto dove si trova la tua antenna (o usa il pulsante *🎯 Usa la mia posizione GPS*).
4. Scegli il tuo **Tema di colori preferito** tra i preset o con il Color Picker.
5. Clicca su **💾 Salva Tutte le Impostazioni**.
6. Clicca su **🚀 Apri Radar Live** e goditi il tuo radar avionico personale!

---

## 🔌 Compatibilità Sorgenti ADS-B

ADSBItalia Station Radar è nativamente compatibile con tutti i software di decodifica Mode-S / ADS-B:
* **readsb** (standard adsb.im / ultrafeeder)
* **dump1090-fa** (FlightAware PiAware)
* **dump1090-mutability**
* **tar1090** (sorgente `/data/aircraft.json`)
* Qualsiasi feed HTTP remoto che esporta un file `aircraft.json` conforme alle specifiche standard.

---

## 🌐 Unisciti alla Rete ADSBItalia

Se hai una stazione ricevente e vuoi condividere i tuoi dati con la community italiana indipendente:
👉 Visita [https://adsbitalia.it](https://adsbitalia.it) e scopri come inviare il tuo feed Beast in 2 minuti!

---

## 📄 Licenza

Rilasciato sotto licenza [MIT](LICENSE). Libero per uso personale, didattico e per la community di radioamatori ed appassionati di volo.
EOF
