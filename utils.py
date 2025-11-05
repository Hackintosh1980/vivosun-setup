#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math
import config

# -------------------------------------------------------
# 🌿 VPD-Berechnung mit Leaf-Offset
# -------------------------------------------------------
def calc_vpd(temp_c: float, rh: float) -> float:
    """
    Berechnet den VPD (kPa) mit Leaf-Offset aus config.json.
    Positive Werte = Blatt wärmer, negative Werte = Blatt kühler.
    """
    try:
        cfg = config.load_config() or {}
        leaf_offset = float(cfg.get("leaf_offset", 0.0))
    except Exception:
        leaf_offset = 0.0

    # Blatt-Temperatur mit Offset (z. B. -2.0 = Blatt 2°C kühler)
    t_leaf = temp_c + leaf_offset

    if rh <= 0 or rh > 100:
        return 0.0

    es = 0.6108 * math.exp((17.27 * t_leaf) / (t_leaf + 237.3))
    ea = es * (rh / 100.0)
    vpd = es - ea

    return round(vpd, 2)


# -------------------------------------------------------
# 🌡 Temperatur-Konvertierung °C ↔ °F
# -------------------------------------------------------
def convert_temperature(value, mode="C"):
    """Konvertiert Temperatur von °C nach °F (oder bleibt °C)."""
    if value is None:
        return None
    try:
        v = float(value)
    except (ValueError, TypeError):
        return value
    if mode.upper() == "F":
        return v * 9 / 5 + 32
    return v


# -------------------------------------------------------
# 🌍 Einheitliches Interface für alle Module
# -------------------------------------------------------
def convert_unit(value):
    """
    Liest die aktuelle Einheit aus config.json und wendet sie an.
    Beispiel: Dashboard & Charts zeigen Werte direkt in der eingestellten Einheit.
    """
    try:
        cfg = config.load_config()
        unit = cfg.get("unit", "°C")
        if "F" in unit.upper():
            return convert_temperature(value, "F")
    except Exception:
        pass
    return convert_temperature(value, "C")
