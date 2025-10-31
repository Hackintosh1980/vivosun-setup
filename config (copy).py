#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py – zentrale JSON-Konfig für VIVOSUN-Dashboard
"""
import json, os
from kivy.utils import platform

# Android-sicherer Pfad
if platform == "android":
    APP_DIR = "/data/user/0/org.hackintosh1980.dashboard/files"
else:
    APP_DIR = os.path.abspath(os.path.dirname(__file__))

CONFIG_FILE = os.path.join(APP_DIR, "config.json")

DEFAULTS = {
    "device_id": None,          # BLE MAC / ID
    "mode": "simulation",       # "simulation" | "live"
    "refresh_interval": 4.0,    # Sekunden – JSON Polling
    "poll_jitter": 0.3,         # zufälliger Offset (sek) gegen Zippern
    "ui_scale": 0.85,           # für nächste App-Starts (Header/Fonts)
    "chart_window": 120,        # X-Range (Samples)
    "clear_on_mode_switch": True,
}

def _ensure_dir():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

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
        _ensure_dir()
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
        print("💾 Config gespeichert:", cfg)
    except Exception as e:
        print("❌ Fehler beim Speichern:", e)

def set_field(key, value):
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)

def save_device_id(device_id):
    cfg = load_config()
    cfg["device_id"] = device_id
    cfg["mode"] = "live"
    save_config(cfg)

def get_device_id():
    return load_config().get("device_id")
