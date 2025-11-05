#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChartManager Deluxe – Auto 3/6 Tiles (extern erkennen + weich umschalten)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, json
from kivy.clock import Clock
from kivy.animation import Animation
from kivy_garden.graph import LinePlot
from kivy.utils import platform
from kivy.metrics import dp
from kivy.app import App
import config, utils

# ----------------------------------------------------------
# 🌿 Einheitliche Utility-Funktion für Einheiten  (REPLACE THIS BLOCK)
# ----------------------------------------------------------
def get_unit_for_key(key: str) -> str:
    """Gibt die passende Einheit je nach Tile-Key zurück (liest 'unit' aus config.json)."""
    try:
        cfg = config.load_config() or {}
        unit_str = str(cfg.get("unit", "°C"))
        is_f = "F" in unit_str.upper()
    except Exception:
        is_f = False

    if key.startswith("tile_t_"):
        return "°F" if is_f else "°C"
    if key.startswith("tile_h_"):
        return "%"
    if key.startswith("tile_vpd_"):
        return "kPa"
    return ""

# ----------------------------------------------------------
# APP_JSON robust ermitteln
# ----------------------------------------------------------
def _resolve_app_json():
    if platform == "android":
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            files_dir = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
            return os.path.join(files_dir, "ble_scan.json")
        except Exception as e:
            print("⚠️ filesDir nicht ermittelbar, fallback:", e)
            return "/sdcard/Android/data/org.hackintosh1980.dashboard/files/ble_scan.json"
    else:
        return os.path.expanduser("~/vivosun-setup/blebridge_desktop/ble_scan.json")

APP_JSON = _resolve_app_json()
print(f"🗂️ Verwende APP_JSON = {APP_JSON}")


class ChartManager:
    def __init__(self, dashboard):
        self.dashboard = dashboard
        self.buffers = {}
        self.plots = {}
        self.counter = 0
        self.running = True
        self._poll_event = None
        self._bridge_started = False

        # Status-Flags
        self.ext_present = None          # unbekannt am Start → erste Erkennung triggert Layout
        self._header_cache = {"mac": None, "rssi": None}

        # Config
        self.cfg = config.load_config() or {}
        self.refresh_interval = float(self.cfg.get("refresh_interval", 4.0))
        self.chart_window     = int(self.cfg.get("chart_window", 120))
        print(f"🌿 ChartManager init – Poll={self.refresh_interval}s, Window={self.chart_window}")

        # Tiles vorbereiten (dicke Linien + Basisgrößen merken)
        self._tile_keys_int = ["tile_t_in","tile_h_in","tile_vpd_in"]
        self._tile_keys_ext = ["tile_t_out","tile_h_out","tile_vpd_out"]

        for key in self._tile_keys_int + self._tile_keys_ext:
            tile = dashboard.ids.get(key)
            if not tile:
                print(f"⚠️ Tile nicht gefunden: {key}")
                continue

            # Basis-Höhe zur Animation merken (einmalig)
            if not hasattr(tile, "base_height") or not tile.base_height:
                tile.base_height = tile.height if tile.height > 0 else dp(160)

            graph = tile.ids.g
            plot = LinePlot(color=(*tile.accent, 1))
            plot.line_width = 4.0
            graph.add_plot(plot)
            self.plots[key] = plot
            self.buffers[key] = []

            # Y-Band initial
            if graph.ymax == graph.ymin:
                graph.ymin, graph.ymax = 0, 1

            # weiches Einblenden sicherstellen
            tile.opacity = 1.0
            tile.disabled = False

        # Bridge sicherstellen (Android), dann Poll starten
        self._ensure_bridge_started()
        self.start_polling()

    # ----------------------------------------------------------
    # Bridge-Autostart (robust)
    # ----------------------------------------------------------
    def _ensure_bridge_started(self):
        if platform != "android" or self._bridge_started:
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ctx = PythonActivity.mActivity
            BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")

            live_cfg = config.load_config() or {}
            dev = live_cfg.get("device_id")

            ret = BleBridgePersistent.start(ctx, "ble_scan.json")
            print(f"🚀 Bridge.start → {ret}")

            try:
                if dev:
                    BleBridgePersistent.setActiveMac(dev)
                    print(f"🎯 Aktive MAC gesetzt: {dev}")
                else:
                    # Kein device_id → Vollscan erlauben (deine gewünschte Logik)
                    BleBridgePersistent.setActiveMac(None)
                    print("🔍 Vollscan (keine aktive MAC)")
            except Exception as e:
                print("⚠️ setActiveMac fehlgeschlagen:", e)

            self._bridge_started = True

        except Exception as e:
            print("⚠️ Bridge-Autostart-Fehler:", e)

    # ----------------------------------------------------------
    # Polling Lifecycle
    # ----------------------------------------------------------
    def start_polling(self):
        if self._poll_event:
            Clock.unschedule(self._poll_event)
        self.running = True
        print(f"▶️ Starte Polling ({self.refresh_interval}s)")
        self._poll_event = Clock.schedule_interval(self._poll_json, self.refresh_interval)

    def stop_polling(self):
        if self._poll_event:
            Clock.unschedule(self._poll_event)
            self._poll_event = None
        self.running = False
        print("⏹ Polling gestoppt.")

    # ----------------------------------------------------------
    # Haupt-Poll
    # ----------------------------------------------------------
    def _poll_json(self, *a):
        if not self.running:
            return
        try:
            # aktive device_id (stabil – kein Mac-Hopping, wenn gesetzt)
            device_id = (getattr(config, "load_device_id", lambda: None)() or
                         self.cfg.get("device_id"))

            if not os.path.exists(APP_JSON):
                self._set_no_data_labels()
                return

            with open(APP_JSON, "r") as f:
                content = f.read().strip()
            if not content:
                self._set_no_data_labels()
                return

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return

            if not isinstance(data, list) or not data:
                self._set_no_data_labels()
                return

            # Device filtern
            if device_id:
                data = [d for d in data if (d.get("address") or d.get("mac")) == device_id]
                if not data:
                    self._set_no_data_labels()
                    return
            else:
                def _valid(d):
                    return isinstance(d.get("humidity_int"), (int, float))
                data = sorted(data, key=lambda d: 0 if _valid(d) else 1)

            d = data[0]

            # --- Rohwerte in °C laden ---
            t_int_c = d.get("temperature_int", 0.0)
            t_ext_c = d.get("temperature_ext", 0.0)
            h_int   = d.get("humidity_int", 0.0)
            h_ext   = d.get("humidity_ext", 0.0)

            # 🌿 externen Sensor erkennen (vor Umrechnung!)
            ext_now = self._detect_external_present(t_ext_c, h_ext)
            if self.ext_present is None or ext_now != self.ext_present:
                self.ext_present = ext_now
                self._apply_layout(ext_now)

            # 🧮 VPD immer in °C berechnen
            vpd_in  = utils.calc_vpd(t_int_c, h_int)
            vpd_out = utils.calc_vpd(t_ext_c, h_ext)

            # 🌡 Einheit aus config lesen
            try:
                cfg = config.load_config() or {}
                unit_str = str(cfg.get("unit", "°C"))
                is_f = "F" in unit_str.upper()
            except Exception:
                is_f = False

            from utils import convert_temperature
            if is_f:
                t_int_disp = convert_temperature(t_int_c, "F")
                t_ext_disp = convert_temperature(t_ext_c, "F")
            else:
                t_int_disp = t_int_c
                t_ext_disp = t_ext_c

            # Charts & Labels aktualisieren
            values = {
                "tile_t_in":   t_int_disp,
                "tile_h_in":   h_int,
                "tile_vpd_in": vpd_in,
                "tile_t_out":  t_ext_disp,
                "tile_h_out":  h_ext,
                "tile_vpd_out": vpd_out,
            }
            for key, val in values.items():
                self._append_value(key, val)
                tile = self.dashboard.ids.get(key)
                if tile:
                    from dashboard_charts import get_unit_for_key
                    unit = get_unit_for_key(key)
                    tile.ids.big.text = f"{val:.2f} {unit}" if unit else f"{val:.2f}"
                    self._auto_scale_y(tile.ids.g, key)

            # Scatter aktualisieren, falls offen
            try:
                app = App.get_running_app()
                if hasattr(app, "scatter_window") and app.scatter_window:
                    Clock.schedule_once(lambda dt: app.scatter_window.update_values(
                        t_int, h_int, t_ext, h_ext))
            except Exception:
                pass

            # Header-Update ruhig halten
            try:
                app = App.get_running_app()
                dash = app.sm.get_screen("dashboard").children[0]
                header = dash.ids.header

                mac = d.get("address") or d.get("mac") or self.cfg.get("device_id") or "--"
                if mac and mac != self._header_cache["mac"]:
                    header.ids.device_label.text = (
                        f"[font=assets/fonts/fa-solid-900.ttf]\uf293[/font] {mac}"
                    )
                    self._header_cache["mac"] = mac

                rssi = d.get("rssi")
                if isinstance(rssi, (int, float)):
                    self._header_cache["rssi"] = rssi
                if self._header_cache["rssi"] is None:
                    self._header_cache["rssi"] = -99

                stable_rssi = self._header_cache["rssi"]
                header.ids.rssi_value.text = f"{stable_rssi:.0f} dBm"
                if stable_rssi > -60:
                    col = (0.3, 1.0, 0.3, 1)
                elif stable_rssi > -75:
                    col = (0.9, 0.9, 0.3, 1)
                else:
                    col = (1.0, 0.4, 0.3, 1)
                header.ids.rssi_value.color = col

                # App-weit publizieren (falls main.update_header darauf zugreift)
                try:
                    app.current_mac = mac
                    app.last_rssi = stable_rssi
                    app.bt_active = True
                except Exception:
                    pass

            except Exception as e:
                print("⚠️ Header-Update-Fehler:", e)

        except Exception as e:
            print("⚠️ Polling-Fehler:", e)
            self._set_no_data_labels()

    # ----------------------------------------------------------
    # Externen Sensor erkennen
    #   –99, None, t_ext < –50°C oder h_ext < 0  ⇒ NICHT präsent
    # ----------------------------------------------------------
    def _detect_external_present(self, t_ext, h_ext):
        try:
            if t_ext is None or h_ext is None:
                return False
            if isinstance(t_ext, (int, float)) and isinstance(h_ext, (int, float)):
                if (t_ext == -99) or (h_ext == -99):
                    return False
                if (t_ext < -50) or (h_ext < 0):
                    return False
                return True
        except Exception:
            pass
        return False

    # ----------------------------------------------------------
    # Layout weich umschalten (6 → 3 Tiles und zurück)
    # ----------------------------------------------------------
    def _apply_layout(self, ext_visible: bool):
        grid = self.dashboard.ids.get("grid")
        if not grid:
            return

        # Ziel-Grid
        if ext_visible:
            # 2 Reihen × 3 Spalten (alle 6 sichtbar)
            grid.rows = 2
            grid.cols = 3
        else:
            # 1 Reihe × 3 Spalten (nur interne sichtbar)
            grid.rows = 1
            grid.cols = 3

        # externe Tiles animieren
        self._toggle_external_tiles(ext_visible)

    def _toggle_external_tiles(self, visible):
        # externe
        for key in self._tile_keys_ext:
            tile = self.dashboard.ids.get(key)
            if not tile:
                continue
            Animation.cancel_all(tile)
            if visible:
                tile.disabled = False
                anim = Animation(opacity=1.0, height=tile.base_height, d=0.35)
            else:
                tile.disabled = True
                anim = Animation(opacity=0.0, height=0, d=0.35)
            anim.start(tile)

        # interne leicht “atmen”, damit Layout clean neu verteilt
        for key in self._tile_keys_int:
            tile = self.dashboard.ids.get(key)
            if not tile:
                continue
            Animation.cancel_all(tile)
            # kleiner Nudge der Höhe, dann zurück → Grid re-layoutet sauber
            h = tile.height if tile.height > 0 else tile.base_height
            Animation(height=h + dp(1), d=0.05).start(tile)
            Clock.schedule_once(lambda *_t, t=tile: setattr(t, "height", t.base_height), 0.08)

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _append_value(self, key, val):
        buf = self.buffers.setdefault(key, [])
        self.counter += 1
        buf.append((self.counter, val))
        if len(buf) > self.chart_window:
            buf.pop(0)
        plot = self.plots.get(key)
        if plot:
            plot.points = buf

    def _auto_scale_y(self, graph, key):
        try:
            vals = [v for _, v in self.buffers.get(key, []) if isinstance(v, (int, float))]
            if not vals:
                return
            y_min, y_max = min(vals), max(vals)
            if abs(y_max - y_min) < 1e-6:
                y_max, y_min = y_min + 0.5, y_min - 0.5
            margin = max((y_max - y_min) * 0.2, 0.2)
            graph.ymin = round(y_min - margin, 1)
            graph.ymax = round(y_max + margin, 1)
            if self.counter >= self.chart_window:
                graph.xmin = self.counter - self.chart_window
                graph.xmax = self.counter
            else:
                graph.xmin = 0
                graph.xmax = self.chart_window
        except Exception as e:
            print(f"⚠️ Auto-Scale-Fehler ({key}):", e)

    def _set_no_data_labels(self):
        for key in ["tile_t_in","tile_h_in","tile_vpd_in",
                    "tile_t_out","tile_h_out","tile_vpd_out"]:
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"

    # ----------------------------------------------------------
    # Reset & Config-Reload
    # ----------------------------------------------------------
    def reset_data(self):
        was_running = self.running
        if was_running and self._poll_event:
            Clock.unschedule(self._poll_event)
            self._poll_event = None

        for key in list(self.buffers.keys()):
            self.buffers[key].clear()
            if key in self.plots:
                self.plots[key].points = []
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"

        self.counter = 0
        print("🧹 Charts & Werte zurückgesetzt")

        if was_running:
            self.start_polling()

    def reload_config(self):
        new_cfg = config.load_config() or {}
        self.refresh_interval = float(new_cfg.get("refresh_interval", self.refresh_interval))
        self.chart_window     = int(new_cfg.get("chart_window", self.chart_window))
        self.cfg.update(new_cfg)
        print(f"♻️ Config neu geladen: Poll={self.refresh_interval}, Window={self.chart_window}")
        if self.running:
            self.start_polling()
