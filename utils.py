#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math

def calc_vpd(temp_c: float, rh: float) -> float:
    """Berechnet den VPD (Vapor Pressure Deficit) in kPa."""
    if rh <= 0 or rh > 100:
        return 0.0
    es = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * (rh / 100.0)
    return round(es - ea, 2)
