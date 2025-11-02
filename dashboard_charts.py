#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChartManager – Live-Only (Android-robust, Bridge-Autostart, kein JSON-Clear)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, json
from kivy.clock import Clock
from kivy_garden.graph import LinePlot
from kivy.utils import platform
import config, utils

# ----------------------------------------------------------
# APP_JSON robust ermitteln (keine harte Paket-ID mehr)
# ----------------------------------------------------------
def _resolve_app_json():
    if platform == "android":
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            files_dir = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
            return os.path.join(files_dir, "ble_scan.json")
        except Exception as e:
            print("⚠️ Konnte filesDir nicht ermitteln, fallback:", e)
            # letzter Ausweg (funktioniert i.d.R. auch):
            return "/sdcard/Android/data/{pkg}/files/ble_scan.json".format(
                pkg="org.hackintosh1980.vivosunreader"
            )
    else:
        # Desktop-Pfad ggf. anpassen
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
        self._bridge_started = False   # damit wir den Autostart nur einmal triggern

        # --- Config laden ---
        self.cfg = config.load_config()
        self.refresh_interval = float(self.cfg.get("refresh_interval", 4.0))
        self.chart_window   = int(self.cfg.get("chart_window", 120))
        print(f"🌿 ChartManager init – Live, Poll={self.refresh_interval}s, Window={self.chart_window}")

        # --- Graphs vorbereiten ---
        for key in [
            "tile_t_in", "tile_h_in", "tile_vpd_in",
            "tile_t_out", "tile_h_out", "tile_vpd_out"
        ]:
            tile = dashboard.ids.get(key)
            if not tile:
                print(f"⚠️ Tile nicht gefunden: {key}")
                continue
            graph = tile.ids.g
            plot = LinePlot(color=(*tile.accent, 1))
            plot.line_width = 4.0
            graph.add_plot(plot)
            self.plots[key] = plot
            self.buffers[key] = []

            # ZeroDivision-Schutz
            if graph.ymax == graph.ymin:
                graph.ymin = 0
                graph.ymax = 1

        # --- Sofort Bridge sicherstellen (Android), dann Poll starten ---
        self._ensure_bridge_started()
        print(f"📡 Starte Live-Polling (Plattform: {platform})")
        self._poll_event = Clock.schedule_interval(self._poll_json, self.refresh_interval)

    # ----------------------------------------------------------
    # Bridge-Autostart (nur Android)
    # ----------------------------------------------------------
    def _ensure_bridge_started(self):
        if platform != "android" or self._bridge_started:
            return
        try:
            # nur starten, wenn config live ist
            cfg = config.load_config()
            if not (cfg and cfg.get("mode") == "live"):
                print("ℹ️ Live-Mode in config nicht aktiv → Bridge-Autostart übersprungen.")
                return

            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ctx = PythonActivity.mActivity
            BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")

            ret = BleBridgePersistent.start(ctx, "ble_scan.json")
            print(f"🚀 Bridge.start → {ret}")

            # optional aktive MAC aus config setzen
            device_id = cfg.get("device_id")
            if device_id:
                try:
                    BleBridgePersistent.setActiveMac(device_id)
                    print(f"🎯 setActiveMac({device_id}) OK")
                except Exception as e:
                    print("⚠️ setActiveMac fehlgeschlagen:", e)

            self._bridge_started = True

        except Exception as e:
            print("⚠️ Bridge-Autostart-Fehler:", e)

    # ----------------------------------------------------------
    # Polling
    # ----------------------------------------------------------
    def _poll_json(self, *a):
        if not self.running:
            return
        try:
            # Wenn Datei fehlt/leer → Bridge sicherstellen (einmalig) und warten
            if not os.path.exists(APP_JSON):
                print(f"⚠️ JSON fehlt: {APP_JSON}")
                self._ensure_bridge_started()
                self._set_no_data_labels()
                return

            with open(APP_JSON, "r") as f:
                content = f.read().strip()
            if not content:
                # Datei existiert, aber noch nicht befüllt
                print("⚠️ JSON aktuell leer (Schreibvorgang läuft).")
                self._ensure_bridge_started()
                self._set_no_data_labels()
                return

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                print("⚠️ JSON noch unvollständig – nächster Poll …")
                return

            if not data or not isinstance(data, list):
                print("⚠️ JSON leer oder ungültig.")
                self._set_no_data_labels()
                return

            # 🔍 Nur Gerät aus config.json zeigen (wenn gesetzt)
            device_id = None
            try:
                # falls du eine Hilfsfunktion hast:
                device_id = getattr(config, "load_device_id", lambda: None)()
            except Exception:
                device_id = None
            if not device_id:
                # fallback aus bereits geladener cfg
                device_id = self.cfg.get("device_id")

            if device_id:
                filtered = [d for d in data if d.get("address") == device_id]
                if filtered:
                    data = filtered
                else:
                    print(f"⚠️ Keine Daten für aktives Gerät {device_id}.")
                    self._set_no_data_labels()
                    return

            d = data[0]

            # Werte
            t_int = d.get("temperature_int", 0.0)
            t_ext = d.get("temperature_ext", 0.0)
            h_int = d.get("humidity_int", 0.0)
            h_ext = d.get("humidity_ext", 0.0)
            vpd_in  = utils.calc_vpd(t_int, h_int)
            vpd_out = utils.calc_vpd(t_ext, h_ext)

            values = {
                "tile_t_in":   t_int,
                "tile_h_in":   h_int,
                "tile_vpd_in": vpd_in,
                "tile_t_out":  t_ext,
                "tile_h_out":  h_ext,
                "tile_vpd_out": vpd_out,
            }

            # Charts & Labels updaten
            for key, val in values.items():
                self._append_value(key, val)
                tile = self.dashboard.ids.get(key)
                if tile:
                    tile.ids.big.text = f"{val:.2f}"
                    self._auto_scale_y(tile.ids.g, key)

            # Scatter-Fenster live aktualisieren, falls offen
            try:
                from kivy.app import App
                app = App.get_running_app()
                if hasattr(app, "scatter_window") and app.scatter_window:
                    Clock.schedule_once(
                        lambda dt: app.scatter_window.update_values(t_int, h_int, t_ext, h_ext)
                    )
            except Exception as e:
                print("⚠️ Scatter update error:", e)

        except Exception as e:
            print("⚠️ Polling-Fehler:", e)
            self._set_no_data_labels()

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
        for key in ["tile_t_in","tile_h_in","tile_vpd_in","tile_t_out","tile_h_out","tile_vpd_out"]:
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"

    # ----------------------------------------------------------
    # Steuerung
    # ----------------------------------------------------------
    def stop_polling(self):
        if hasattr(self, "_poll_event"):
            Clock.unschedule(self._poll_event)
        self.running = False
        print("⏹ Polling gestoppt.")

    def reset_data(self):
        for key in list(self.buffers.keys()):
            self.buffers[key].clear()
            plot = self.plots.get(key)
            if plot:
                plot.points = []
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"
        self.counter = 0
        print("🧹 Charts & Werte zurückgesetzt")

    def reload_config(self):
        new_cfg = config.load_config()
        self.refresh_interval = float(new_cfg.get("refresh_interval", self.refresh_interval))
        self.chart_window     = int(new_cfg.get("chart_window", self.chart_window))
        self.cfg.update(new_cfg or {})
        print(f"♻️ Config neu geladen: Poll={self.refresh_interval}, Window={self.chart_window}")
