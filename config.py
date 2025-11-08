#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py – zentrale JSON-Konfiguration für VIVOSUN Ultimate
© 2025 Dominik Rosenthal (Hackintosh1980)
"""
import json, os
from kivy.utils import platform

if platform == "android":
    APP_DIR = "/data/user/0/org.hackintosh1980.dashboard/files"
else:
    APP_DIR = os.path.abspath(os.path.dirname(__file__))

CONFIG_FILE = os.path.join(APP_DIR, "config.json")

DEFAULTS = {
    "device_id": None,
    "mode": "simulation",          # oder 'live'
    "poll_jitter": 0.3,            # Zufalls-Offset (optional)
    "ui_scale": 0.85,              # Globales Scaling
    "unit": "°C",                  # °C oder °F
    "leaf_offset": 0.0,            # °C Offset für Leaf Temp
    "vpd_offset": 0.0,             # Korrektur für VPD
    "theme": "Dark",               # Theme-Auswahl
    "clear_on_mode_switch": True,  # Charts leeren bei Moduswechsel
    "refresh_interval": 2.0,
    "chart_window": 120,
    "allow_auto_stop": True,
    "stale_timeout": 12.0
}

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return {**DEFAULTS, **data}
    except Exception as e:
        print("⚠️ Fehler beim Laden der config:", e)
    return DEFAULTS.copy()

def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
        print("💾 Config gespeichert:", cfg)
    except Exception as e:
        print("❌ Fehler beim Speichern:", e)

def save_device_id(device_id):
    cfg = load_config()
    cfg["device_id"] = device_id
    cfg["mode"] = "live"
    save_config(cfg)

def get_device_id():
    return load_config().get("device_id")

# -------------------------------------------------------------
# 📡 Gerät speichern / laden (MAC-Adresse)
# -------------------------------------------------------------
import os, json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def save_device_id(addr: str):
    """Speichert die aktive BLE-MAC-Adresse ins config.json."""
    try:
        cfg = load_config()
        cfg["device_id"] = addr
        with open(CONFIG_PATH, "w", encoding="utf8") as f:
            json.dump(cfg, f, indent=2)
        print(f"💾 device_id gespeichert → {addr}")
    except Exception as e:
        print("⚠️ Fehler beim Speichern der device_id:", e)

def load_device_id() -> str | None:
    """Lädt gespeicherte BLE-MAC-Adresse aus config.json."""
    try:
        if not os.path.exists(CONFIG_PATH):
            return None
        with open(CONFIG_PATH, "r", encoding="utf8") as f:
            cfg = json.load(f)
        return cfg.get("device_id")
    except Exception as e:
        print("⚠️ Fehler beim Laden der device_id:", e)
        return None
# -------------------------------------------------------------
# 🌡️ Temperature Unit (°C / °F)
# -------------------------------------------------------------
def get_unit():
    """Liest die Temperatureinheit aus der Config (°C oder °F)."""
    try:
        cfg = load_config()
        return cfg.get("unit", "°C")
    except Exception:
        return "°C"

def toggle_unit():
    """Wechselt zwischen °C und °F, speichert und gibt neue Einheit zurück."""
    cfg = load_config()
    current = cfg.get("unit", "°C")
    new_unit = "°F" if current == "°C" else "°C"
    cfg["unit"] = new_unit
    save_config(cfg)
    print(f"🌡️ Einheit umgeschaltet → {new_unit}")
    return new_unit
# ------------------------------------------------------------
# Zusatz: Timing-Parameter für Watchdog und Polling
# ------------------------------------------------------------

def get_refresh_interval():
    """
    Gibt die Poll-Interval-Zeit (Sekunden) aus config.json zurück.
    Fallback: 2.0 Sekunden
    """
    try:
        cfg = load_config()
        return float(cfg.get("refresh_interval", 5.0))
    except Exception:
        return 2.0


def get_stale_timeout():
    """
    Gibt den Timeout (Sekunden ohne neue Pakete) zurück,
    bevor der Watchdog den Stream als 'stale' betrachtet.
    Fallback: 10.0 Sekunden
    """
    try:
        cfg = load_config()
        return float(cfg.get("stale_timeout", 8.0))
    except Exception:
        return 10.0


def get_chart_window():
    """
    Gibt die Anzahl Punkte pro Plot-Fenster zurück.
    Fallback: 120
    """
    try:
        cfg = load_config()
        return int(cfg.get("chart_window", 200))
    except Exception:
        return 120
