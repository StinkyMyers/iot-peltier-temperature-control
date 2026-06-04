# 🧊 Peltier IoT Temperature Control

Tímový projekt POIT – IoT systém na reguláciu teploty chladiacej kvapaliny pomocou Peltierovho článku.

## Popis

Systém reguluje teplotu kvapaliny v uzavretom hydraulickom okruhu pomocou Peltierovho článku (TEC1-12706). Mikrokontrolér ESP32 implementuje PID regulátor a komunikuje cez MQTT s backendom na Raspberry Pi. Webový dashboard umožňuje vzdialené monitorovanie a ovládanie systému.

## Architektúra
DS18B20 → ESP32 (WiFi/MQTT) → Mosquitto → Flask → SQLite
↓
Dashboard (WebSocket)
↓
ThingsBoard (Cloud)

## Štruktúra repozitára
iot-peltier-temperature-control/
├── esp32/                  # ESP32 firmvér (PlatformIO)
│   └── src/main.cpp
├── flask/                  # Flask backend
│   ├── app.py
│   └── templates/
│       ├── index.html
│       └── login.html
├── ident/                  # Identifikačné skripty
│   ├── live.py
│   └── data/
├── hw/                     # Schéma zapojenia
├── docs/                   # LaTeX dokumentácia
│   └── report/
└── README.md

## Inštalácia

### ESP32
1. Otvoriť projekt v PlatformIO
2. Nastaviť WiFi a MQTT v `esp32/src/main.cpp`:
```cpp
const char* WIFI_SSID   = "nazov_siete";
const char* WIFI_PASS   = "heslo";
const char* MQTT_SERVER = "147.175.105.185";
```
3. Nahrať firmvér na ESP32

### Raspberry Pi
```bash
pip3 install flask flask-socketio flask-sqlalchemy paho-mqtt --break-system-packages
sudo apt install mosquitto mosquitto-clients -y
sudo systemctl enable mosquitto
```

## Spustenie

```bash
# Spustenie služieb
sudo systemctl start mosquitto
sudo systemctl start peltier

# Manuálne spustenie
cd ~/peltier && python3 app.py
```

Dashboard: `http://147.175.105.185:5000`

## Prihlasovacie údaje

| Rola | Používateľ | Prístup |
|------|-----------|---------|
| Operátor | `operator` | Plný prístup – ovládanie a regulácia |
| Spektátor | `spectator` | Iba sledovanie |

## MQTT Topiky

| Topik | Smer | Popis |
|-------|------|-------|
| `peltier/data` | ESP32 → RPi | Merané hodnoty (CSV) |
| `peltier/cmd` | RPi → ESP32 | Príkazy |

### Formát dát
<time_ms>,<temp_C>,<tec_pwm>,<pump_pwm>,<mode>

### Príkazy
| Príkaz | Popis |
|--------|-------|
| `STABILIZE` | Ustálenie (TEC 25%, pumpa 50%) |
| `PID_TEC` | Mód 2 – PID regulácia TEC |
| `PID` | Mód 3 – PID regulácia pumpy |
| `MANUAL:tec:pump` | Mód 1 – manuálne PWM |
| `HEATER_ON/OFF` | Simulácia poruchy |
| `STOP` | Zastavenie všetkých výstupov |

## Regulačné módy

| Mód | Popis | Kp | Ki | Kd |
|-----|-------|----|----|----|
| Mód 1 | Manuálne PWM | – | – | – |
| Mód 2 | PID – TEC | -50.0 | -0.053 | -25.0 |
| Mód 3 | PI – Pumpa | 103.81 | 0.0515 | 0 |

## Hardware

| Komponent | Parameter |
|-----------|-----------|
| ESP32-DevKitC 38pin | 240 MHz, WiFi |
| TEC1-12706 | 12V, 6A, max 80W |
| DS18B20 | OneWire, 0.0625°C rozlíšenie |
| Napájanie | 12V / 12.5A / 150W |

## ThingsBoard

Cloudová vizualizácia: [[thingsboard.cloud](https://thingsboard.cloud)](https://eu.thingsboard.cloud/dashboards/all/914723d0-5ff9-11f1-a6df-b7b5c1df0b6e)

Telemetria: `temperature`, `tec_pwm`, `pump_pwm`, `mode`, `setpoint`
