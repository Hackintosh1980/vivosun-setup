#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math
import config

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
