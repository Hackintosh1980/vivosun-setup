#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_charts.py – FINAL ONE-FILE DROP-IN (Nov 2025)
VIVOSUN Dashboard – Cross-Platform BLE Monitor
© 2025 Dominik Rosenthal (Hackintosh1980)

Features
--------
• 3/6-Tile-Dashboard mit Auto-Layout (externer Fühler)
• Watchdog:
    – Freeze bei Datenstille (keine neuen Punkte)
    – Auto-Stop des Pollings (config.allow_auto_stop)
    – Auto-Recovery bei JEDEM Counter-Wechsel (auch Reset/Wrap)
• Manuelle Steuerung: user_stop() / user_start() / reset_data() / reload_config()
• Konfigurierbar über config.json:
    - refresh_interval: float (s)
    - chart_window: int (Punkte)
    - stale_timeout: float (s)  ← NEU
    - allow_auto_stop: bool
• MAC + RSSI im Header (mit Farblogik)
• Keine JSON-Löschung
• Ruhige Logs
"""

from __future__ import annotations
import os, json, time
from typing import Any, Dict, List, Optional, Tuple

from kivy.clock import Clock
from kivy.animation import Animation
from kivy_garden.graph import LinePlot
from kivy.utils import platform
from kivy.metrics import dp
from kivy.app import App

import config, utils


# ======================================================================
# Einheiten
# ======================================================================

def get_unit_for_key(key: str) -> str:
    """Einheit passend zum Tile-Key; liest 'unit' (°C/°F) aus config.json."""
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


# ======================================================================
# APP_JSON Pfad (Android/Desktop robust)
# ======================================================================

def _resolve_app_json() -> str:
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
if platform != "android":
    print(f"🗂️ Verwende APP_JSON = {APP_JSON}")


# ======================================================================
# ChartManager
# ======================================================================

class ChartManager:
    """
    Zentrale Dashboard-Logik: Polling, Parsing, Anzeige, Watchdog, Start/Stop, Recovery.
    Erwartete Dashboard-IDs:
      - root.ids["grid"]             → GridLayout mit 6 Kacheln
      - tile.ids["g"]                → kivy_garden.graph.Graph
      - tile.ids["big"]              → Label (Großwert)
      - screen('dashboard').ids.header.{device_label, rssi_value}
    """

    # ------------------------------
    # Konstruktor
    # ------------------------------
    def __init__(self, dashboard):
        self.dashboard = dashboard

        # Chart-Puffer + Plot-Objekte
        self.buffers: Dict[str, List[Tuple[int, float]]] = {}
        self.plots: Dict[str, LinePlot] = {}
        self.counter: int = 0

        # Laufstatus
        self.running: bool = True
        self._poll_event = None
        self._bridge_started: bool = False

        # Watchdog / Flow-Tracking
        self._last_pkt_seen: Optional[int] = None   # letzter erkannter packet_counter
        self._last_pkt_time: float = 0.0            # Zeitstempel des letzten Anstiegs
        self._stale_logged: bool = False            # 1x Warnung je Stale-Phase

        # Auto-Stop / Recovery / User-Pause
        self._user_paused: bool = False
        self._last_pkt_at_stop: Optional[int] = None
        self._recovery_event = None                 # Clock-Event für Recovery-Timer

        # Status/Cache
        self.ext_present: Optional[bool] = None
        self._header_cache: Dict[str, Any] = {"mac": None, "rssi": None}

        # Konfiguration
        self.cfg: Dict[str, Any] = config.load_config() or {}
        self.refresh_interval: float = float(self.cfg.get("refresh_interval", 4.0))
        self.chart_window: int = int(self.cfg.get("chart_window", 120))
        # NEU: stale_timeout aus config, sonst dynamisch berechnen
        self.stale_timeout: Optional[float] = self._coerce_float(self.cfg.get("stale_timeout"))
        self.allow_auto_stop: bool = bool(self.cfg.get("allow_auto_stop", True))

        print(f"🌿 ChartManager init – Poll={self.refresh_interval}s, Window={self.chart_window}, "
              f"Timeout={self._effective_timeout():.1f}s, AutoStop={self.allow_auto_stop}")

        # Tile-Keys
        self._tile_keys_int = ["tile_t_in", "tile_h_in", "tile_vpd_in"]
        self._tile_keys_ext = ["tile_t_out", "tile_h_out", "tile_vpd_out"]

        # Tiles/Plots aufsetzen, Bridge starten, Poll los
        self._init_tiles()
        self._ensure_bridge_started()
        self.start_polling()
        self._ensure_recovery_timer()

    # ------------------------------
    # Helpers (internal)
    # ------------------------------
    @staticmethod
    def _coerce_float(v: Any) -> Optional[float]:
        try:
            if v is None: return None
            return float(v)
        except Exception:
            return None

    def _effective_timeout(self) -> float:
        """Benutzt 'stale_timeout' aus config, sonst dynamisch: max(2*refresh, 3.0)."""
        if isinstance(self.stale_timeout, (int, float)) and self.stale_timeout > 0:
            return float(self.stale_timeout)
        return max(self.refresh_interval * 2.0, 3.0)

    # ------------------------------
    # Tiles/Plots initialisieren
    # ------------------------------
    def _init_tiles(self) -> None:
        for key in self._tile_keys_int + self._tile_keys_ext:
            tile = self.dashboard.ids.get(key)
            if not tile:
                print(f"⚠️ Tile nicht gefunden: {key}")
                continue

            if not hasattr(tile, "base_height") or not getattr(tile, "base_height"):
                tile.base_height = tile.height if tile.height > 0 else dp(160)

            graph = tile.ids.g
            plot = LinePlot(color=(*tile.accent, 1))
            plot.line_width = 4.0
            graph.add_plot(plot)

            self.plots[key] = plot
            self.buffers[key] = []

            if graph.ymax == graph.ymin:
                graph.ymin, graph.ymax = 0, 1

            tile.opacity = 1.0
            tile.disabled = False

    # ------------------------------
    # Android-Bridge (robust)
    # ------------------------------
    def _ensure_bridge_started(self) -> None:
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
                BleBridgePersistent.setActiveMac(dev if dev else None)  # Vollscan, wenn None
                print(f"🎯 Aktive MAC: {dev or 'Vollscan'}")
            except Exception as e:
                print("⚠️ setActiveMac fehlgeschlagen:", e)

            self._bridge_started = True
        except Exception as e:
            print("⚠️ Bridge-Autostart-Fehler:", e)

    # ------------------------------
    # Polling lifecycle + UI-Buttons
    # ------------------------------
    def start_polling(self) -> None:
        """(Re)Start des Poll-Loops (nicht idempotent bzgl. _poll_event)."""
        if self._poll_event:
            Clock.unschedule(self._poll_event)
        self.running = True
        self._poll_event = Clock.schedule_interval(self._poll_json, self.refresh_interval)
        print(f"▶️ Starte Polling ({self.refresh_interval}s)")

    def stop_polling(self) -> None:
        """Internes Stoppen (nur von Auto-Stop genutzt)."""
        if self._poll_event:
            Clock.unschedule(self._poll_event)
            self._poll_event = None
        self.running = False
        print("⏹ Polling gestoppt.")

    def user_stop(self) -> None:
        """Manuell pausieren (Button). Verhindert Auto-Recovery."""
        self._user_paused = True
        self._stale_logged = True  # UI zeigt Freeze
        self._last_pkt_at_stop = None  # Watchdog vollständig entkoppeln
        self._set_no_data_labels()
        self.stop_polling()
        print("⏸️ Manuell pausiert (Charts eingefroren).")

    def user_start(self) -> None:
        """Manuell fortsetzen (Button)."""
        self._user_paused = False
        self._stale_logged = False
        self.start_polling()
        print("▶️ Manuell fortgesetzt.")

    # ------------------------------
    # Recovery-Timer-Verwaltung
    # ------------------------------
    def _ensure_recovery_timer(self) -> None:
        if self._recovery_event is None:
            self._recovery_event = Clock.schedule_interval(self._check_recovery, 1.5)  # etwas schneller

    def _cancel_recovery_timer(self) -> None:
        if self._recovery_event:
            Clock.unschedule(self._recovery_event)
            self._recovery_event = None

    # ------------------------------
    # Header-Update (MAC + RSSI)
    # ------------------------------
    def _update_header(self, d: dict) -> None:
        try:
            app = App.get_running_app()
            dash = app.sm.get_screen("dashboard").children[0]
            header = dash.ids.header
        except Exception:
            return  # Header nicht erreichbar

        # MAC
        mac = d.get("address") or d.get("mac") or self.cfg.get("device_id") or "--"
        if mac and mac != self._header_cache.get("mac"):
            try:
                header.ids.device_label.text = (
                    f"[font=assets/fonts/fa-solid-900.ttf]\uf293[/font] {mac}"
                )
            except Exception:
                header.ids.device_label.text = mac
            self._header_cache["mac"] = mac

        # RSSI
        rssi = d.get("rssi")
        if isinstance(rssi, (int, float)):
            self._header_cache["rssi"] = rssi
        if self._header_cache.get("rssi") is None:
            self._header_cache["rssi"] = -99

        try:
            stable_rssi = self._header_cache["rssi"]
            header.ids.rssi_value.text = f"{stable_rssi:.0f} dBm"
            if stable_rssi > -60:
                col = (0.3, 1.0, 0.3, 1)
            elif stable_rssi > -75:
                col = (0.9, 0.9, 0.3, 1)
            else:
                col = (1.0, 0.4, 0.3, 1)
            header.ids.rssi_value.color = col
        except Exception:
            pass

        # Optional global state
        try:
            app.current_mac = mac
            app.last_rssi = self._header_cache["rssi"]
            app.bt_active = True
        except Exception:
            pass

    # ------------------------------
    # Helper: Counter-Vergleich (inkl. Reset/Wrap)
    # ------------------------------
    @staticmethod
    def _pkt_changed(new_val: Optional[int], ref_val: Optional[int]) -> bool:
        """True, sobald sich der Counter überhaupt verändert hat (Reset, Wrap, Anstieg)."""
        if new_val is None or ref_val is None:
            return False
        return new_val != ref_val  # KEIN '>' – 129→1/Wrap ok

    # ------------------------------
    # Haupt-Poll
    # ------------------------------
    def _poll_json(self, *_):
        if not self.running:
            return
        try:
            device_id = (getattr(config, "load_device_id", lambda: None)() or
                         self.cfg.get("device_id"))

            # Datei lesen
            if not os.path.exists(APP_JSON):
                self._set_no_data_labels();  return
            with open(APP_JSON, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                self._set_no_data_labels();  return

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return
            if not isinstance(data, list) or not data:
                self._set_no_data_labels();  return

            # Device-Fokus
            if device_id:
                data = [d for d in data if (d.get("address") or d.get("mac")) == device_id]
                if not data:
                    self._set_no_data_labels();  return

            d = data[0]
            self._update_header(d)  # MAC/RSSI stets aktuell (auch im Stale-Fall)

            # ------------------------------------------------------
            # Bridge meldet „alive“ explizit?
            # ------------------------------------------------------
            alive_flag = d.get("alive")
            if alive_flag is False:
                # sofort einfrieren
                self._set_no_data_labels()
                if self.allow_auto_stop and not self._user_paused:
                    pkt_stop = d.get("packet_counter") or d.get("pkt") or d.get("counter")
                    try: self._last_pkt_at_stop = int(pkt_stop)
                    except Exception: self._last_pkt_at_stop = self._last_pkt_seen
                    self.stop_polling()
                    print("⏹ Polling auto-gestoppt (Bridge alive=false). Warte auf Counter-Änderung…")
                return

            # ------------------------------------------------------
            # Watchdog (Counter-Logik)
            # ------------------------------------------------------
            pkt = d.get("packet_counter") or d.get("pkt") or d.get("counter")
            try:
                pkt_val = int(pkt) if pkt is not None else None
            except Exception:
                pkt_val = None

            now = time.time()

            # dynamischer/konfigurierter Timeout
            dyn_timeout = self._effective_timeout()
            stale_for = now - self._last_pkt_time

            if pkt_val is not None:
                if self._last_pkt_seen is None or pkt_val != self._last_pkt_seen:
                    # ✅ Neues Paket erkannt
                    self._last_pkt_seen = pkt_val
                    self._last_pkt_time = now
                    if self._stale_logged:
                        print("✅ Neuer Datenstrom erkannt – Charts reaktiviert")
                    self._stale_logged = False
                elif stale_for >= dyn_timeout:
                    # ⚠️ zu lange keine Bewegung
                    if not self._stale_logged:
                        print(f"⚠️ Keine neuen Pakete seit {stale_for:.1f}s")
                        self._stale_logged = True
                    self._set_no_data_labels()
                    if self.allow_auto_stop and not self._user_paused:
                        self._last_pkt_at_stop = self._last_pkt_seen
                        self.stop_polling()
                        print("⏹ Polling auto-gestoppt (Stille). Warte auf Counter-Änderung…")
                    return
            else:
                # Kein Counter → wie Stille behandeln
                if stale_for >= dyn_timeout:
                    if not self._stale_logged:
                        print(f"⚠️ Keine neuen Pakete seit {stale_for:.1f}s (kein counter)")
                        self._stale_logged = True
                    self._set_no_data_labels()
                    if self.allow_auto_stop and not self._user_paused:
                        self._last_pkt_at_stop = self._last_pkt_seen if (self._last_pkt_seen is not None) else -1
                        self.stop_polling()
                        print("⏹ Polling auto-gestoppt (kein counter).")
                    return

            # ------------------------------------------------------
            # Werte extrahieren & anzeigen
            # ------------------------------------------------------
            t_int_c = d.get("temperature_int", 0.0)
            t_ext_c = d.get("temperature_ext", 0.0)
            h_int   = d.get("humidity_int", 0.0)
            h_ext   = d.get("humidity_ext", 0.0)

            # externen Fühler erkennen (vor Umrechnung)
            ext_now = self._detect_external_present(t_ext_c, h_ext)
            if self.ext_present is None or ext_now != self.ext_present:
                self.ext_present = ext_now
                self._apply_layout(ext_now)

            # VPD (immer in °C rechnen)
            vpd_in  = utils.calc_vpd(t_int_c, h_int)
            vpd_out = utils.calc_vpd(t_ext_c, h_ext)

            # Anzeigeeinheit °C/°F
            try:
                unit_str = str((config.load_config() or {}).get("unit", "°C"))
                is_f = "F" in unit_str.upper()
            except Exception:
                is_f = False
            from utils import convert_temperature
            t_int_disp = convert_temperature(t_int_c, "F") if is_f else t_int_c
            t_ext_disp = convert_temperature(t_ext_c, "F") if is_f else t_ext_c

            # Charts + Labels
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
                    unit = get_unit_for_key(key)
                    tile.ids.big.text = f"{val:.2f} {unit}" if unit else f"{val:.2f}"
                    self._auto_scale_y(tile.ids.g, key)

            # Scatter, falls offen
            try:
                app = App.get_running_app()
                if getattr(app, "scatter_window", None):
                    Clock.schedule_once(lambda dt: app.scatter_window.update_values(
                        t_int_c, h_int, t_ext_c, h_ext))
            except Exception:
                pass

        except Exception as e:
            print("⚠️ Polling-Fehler:", e)
            self._set_no_data_labels()

    # ------------------------------
    # Auto-Recovery (nur wenn auto-gestoppt & nicht user-paused)
    # ------------------------------
    def _check_recovery(self, *_):
        if self.running or self._user_paused:
            return
        try:
            if not os.path.exists(APP_JSON):
                return
            with open(APP_JSON, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                return
            data = json.loads(raw)
            if not isinstance(data, list) or not data:
                return

            d = data[0]
            # a) Explizites Bridge-Alive?
            alive_flag = d.get("alive")

            # b) Counter-Änderung (egal ob größer/kleiner/reset/wrap)
            pkt = d.get("packet_counter") or d.get("pkt") or d.get("counter")
            try:
                pkt_val = int(pkt) if pkt is not None else None
            except Exception:
                pkt_val = None

            cond_alive = (alive_flag is True)
            cond_counter = (self._last_pkt_at_stop is not None) and self._pkt_changed(pkt_val, self._last_pkt_at_stop)

            if cond_alive or cond_counter:
                print("✅ Auto-Recovery: Änderung erkannt → Polling neu gestartet")
                if pkt_val is not None:
                    self._last_pkt_seen = pkt_val
                self._last_pkt_time = time.time()
                self._stale_logged = False
                self._last_pkt_at_stop = None
                self.start_polling()
        except Exception as e:
            print("⚠️ Recovery-Check-Fehler:", e)

    # ------------------------------
    # Externen Sensor erkennen
    # ------------------------------
    def _detect_external_present(self, t_ext, h_ext) -> bool:
        try:
            if t_ext is None or h_ext is None:
                return False
            if (t_ext == -99) or (h_ext == -99):
                return False
            if (isinstance(t_ext, (int, float)) and t_ext < -50) or \
               (isinstance(h_ext, (int, float)) and h_ext < 0):
                return False
            return True
        except Exception:
            return False

    # ------------------------------
    # Layout weich umschalten (6 ↔ 3 Tiles)
    # ------------------------------
    def _apply_layout(self, ext_visible: bool) -> None:
        grid = self.dashboard.ids.get("grid")
        if not grid:
            return

        if ext_visible:
            grid.rows, grid.cols = 2, 3
        else:
            grid.rows, grid.cols = 1, 3

        self._toggle_external_tiles(ext_visible)
        Clock.schedule_once(lambda dt: grid.do_layout(), 0.4)

    def _toggle_external_tiles(self, visible: bool) -> None:
        # externe
        for key in self._tile_keys_ext:
            tile = self.dashboard.ids.get(key)
            if not tile: continue
            Animation.cancel_all(tile)
            if visible:
                tile.disabled = False
                anim = Animation(opacity=1.0, height=tile.base_height, d=0.35)
            else:
                tile.disabled = True
                anim = Animation(opacity=0.0, height=0, d=0.35)
            anim.start(tile)
        # interne leicht „atmen“
        for key in self._tile_keys_int:
            tile = self.dashboard.ids.get(key)
            if not tile: continue
            Animation.cancel_all(tile)
            h = tile.height if tile.height > 0 else tile.base_height
            Animation(height=h + dp(1), d=0.05).start(tile)
            Clock.schedule_once(lambda *_t, t=tile: setattr(t, "height", t.base_height), 0.08)

    # ------------------------------
    # Helpers
    # ------------------------------
    def _append_value(self, key: str, val: float) -> None:
        buf = self.buffers.setdefault(key, [])
        self.counter += 1
        buf.append((self.counter, val))
        if len(buf) > self.chart_window:
            buf.pop(0)
        plot = self.plots.get(key)
        if plot:
            plot.points = buf

    def _auto_scale_y(self, graph, key: str) -> None:
        try:
            vals = [v for _, v in self.buffers.get(key, []) if isinstance(v, (int, float))]
            if not vals:
                return
            y_min, y_max = min(vals), max(vals)
            if abs(y_max - y_min) < 1e-6:
                y_min, y_max = y_min - 0.5, y_max + 0.5
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

    def _set_no_data_labels(self) -> None:
        # Text leeren
        for key in ["tile_t_in", "tile_h_in", "tile_vpd_in",
                    "tile_t_out", "tile_h_out", "tile_vpd_out"]:
            tile = self.dashboard.ids.get(key)
            if tile:
                tile.ids.big.text = "--"
        # Linien leeren (optischer Freeze)
        for p in self.plots.values():
            p.points = []

    # ------------------------------
    # Reset & Config-Reload
    # ------------------------------
    def reset_data(self) -> None:
        for buf in self.buffers.values():
            buf.clear()
        for p in self.plots.values():
            p.points = []
        for key in ["tile_t_in","tile_h_in","tile_vpd_in","tile_t_out","tile_h_out","tile_vpd_out"]:
            tile = self.dashboard.ids.get(key)
            if tile and hasattr(tile, "ids") and "big" in tile.ids:
                tile.ids.big.text = "--"
        self.counter = 0
        print("🧹 Charts & Werte zurückgesetzt")

    def reload_config(self) -> None:
        new_cfg = config.load_config() or {}
        self.refresh_interval = float(new_cfg.get("refresh_interval", self.refresh_interval))
        self.chart_window     = int(new_cfg.get("chart_window", self.chart_window))
        self.allow_auto_stop  = bool(new_cfg.get("allow_auto_stop", self.allow_auto_stop))
        self.stale_timeout    = self._coerce_float(new_cfg.get("stale_timeout"))
        self.cfg.update(new_cfg)
        print(f"♻️ Config neu geladen: Poll={self.refresh_interval}, Window={self.chart_window}, "
              f"Timeout={self._effective_timeout():.1f}s, AutoStop={self.allow_auto_stop}")
        if self.running:
            self.start_polling()
