#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_charts.py – FINAL ONE-FILE DROP-IN (Nov 2025)
VIVOSUN Dashboard – Cross-Platform BLE Monitor
© 2025 Dominik Rosenthal (Hackintosh1980)
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
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image

import config, utils


# ======================================================================
# Einheiten
# ======================================================================

def get_unit_for_key(key: str) -> str:
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
# APP_JSON Pfad
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
    Erwartete Dashboard-IDs:
      - root.ids["grid"]             → GridLayout mit 6 Kacheln
      - tile.ids["g"]                → kivy_garden.graph.Graph
      - tile.ids["big"]              → Label (Großwert)
      - screen('dashboard').ids.header.{device_label, rssi_value}
    """

    def __init__(self, dashboard):
        self.dashboard = dashboard

        self.buffers: Dict[str, List[Tuple[int, float]]] = {}
        self.plots: Dict[str, LinePlot] = {}
        self.counter: int = 0

        self.running: bool = True
        self._poll_event = None
        self._bridge_started: bool = False

        self._last_pkt_seen: Optional[int] = None
        self._last_pkt_time: float = 0.0
        self._stale_logged: bool = False

        self._user_paused: bool = False
        self._last_pkt_at_stop: Optional[int] = None
        self._recovery_event = None

        self.ext_present: Optional[bool] = None
        self._header_cache: Dict[str, Any] = {"mac": None, "rssi": None}

        self.cfg: Dict[str, Any] = config.load_config() or {}
        self.refresh_interval: float = float(self.cfg.get("refresh_interval", 4.0))
        self.chart_window: int = int(self.cfg.get("chart_window", 120))
        self.stale_timeout: Optional[float] = self._coerce_float(self.cfg.get("stale_timeout"))
        self.allow_auto_stop: bool = bool(self.cfg.get("allow_auto_stop", True))

        print(f"🌿 ChartManager init – Poll={self.refresh_interval}s, Window={self.chart_window}, "
              f"Timeout={self._effective_timeout():.1f}s, AutoStop={self.allow_auto_stop}")

        self._tile_keys_int = ["tile_t_in", "tile_h_in", "tile_vpd_in"]
        self._tile_keys_ext = ["tile_t_out", "tile_h_out", "tile_vpd_out"]

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
        if isinstance(self.stale_timeout, (int, float)) and self.stale_timeout > 0:
            return float(self.stale_timeout)
        return max(self.refresh_interval * 2.0, 3.0)

    # ------------------------------
    # Safe helpers for weakproxy widgets
    # ------------------------------
    @staticmethod
    def _safe_ids(tile, name: str):
        try:
            return getattr(tile, "ids", {}).get(name)
        except ReferenceError:
            return None
        except Exception:
            return None

    @staticmethod
    def _safe_set_text(lbl, txt: str):
        try:
            if lbl:
                lbl.text = txt
        except ReferenceError:
            pass
        except Exception:
            pass

# --- Canvas-Hintergrund pro Tile: kein Reparent, null Risiko ---
    def _apply_tile_bg(self, tile, path: str):
        if not os.path.exists(path):
            return
        from kivy.graphics import Color, Rectangle

        # einmalig aufbauen
        with tile.canvas.before:
            Color(1, 1, 1, 1)
            rect = Rectangle(source=path, pos=tile.pos, size=tile.size)

        # bei Resize/Move synchron halten
        def _sync_bg(*_):
            rect.pos = tile.pos
            rect.size = tile.size
        tile.bind(pos=_sync_bg, size=_sync_bg)

    # ------------------------------
    # Tiles/Plots initialisieren – stabil (Canvas-BG, kein Reparent)
    # ------------------------------
    def _init_tiles(self) -> None:
        base_dir = os.path.join(os.path.dirname(__file__), "assets")
        default_bg = os.path.join(base_dir, "tiles_bg.png")

        # kleine Map, falls du später pro Tile andere BGs willst
        bg_map = {
            "tile_t_in":   os.path.join(base_dir, "tile_bg_temp_in.png"),
            "tile_h_in":   os.path.join(base_dir, "tile_bg_hum_in.png"),
            "tile_vpd_in": os.path.join(base_dir, "tile_bg_vpd_in.png"),
            "tile_t_out":  os.path.join(base_dir, "tile_bg_temp_out.png"),
            "tile_h_out":  os.path.join(base_dir, "tile_bg_hum_out.png"),
            "tile_vpd_out":os.path.join(base_dir, "tile_bg_vpd_out.png"),
        }

        # stash für direkten Zugriff im Append
        if not hasattr(self, "graphs"):
            self.graphs: Dict[str, Any] = {}

        for key in self._tile_keys_int + self._tile_keys_ext:
            tile = self.dashboard.ids.get(key)
            if not tile:
                print(f"⚠️ Tile nicht gefunden: {key}")
                continue

            graph = getattr(tile.ids, "g", None)
            if graph is None:
                print(f"⚠️ Kein Graph in {key}")
                continue

            # Hintergrund über Canvas (keine Widgets)
            bg_path = bg_map.get(key, default_bg)
            if os.path.exists(bg_path):
                self._apply_tile_bg(tile, bg_path)
                print(f"🖼️ {key}: BG aktiv → {os.path.basename(bg_path)}")

            # Graph-Style vereinheitlichen
            try:
                graph.draw_ticks = False
                graph.draw_labels = False
                graph.draw_border = False
                graph.tick_color = (0, 0, 0, 0)
                graph.background_color = (0, 0, 0, 0)
                graph.size_hint = (1, 1)
                graph.pos_hint = {"x": 0, "y": 0}
            except Exception:
                pass

            # Plot initialisieren (nur einmal)
            if key not in self.plots:
                accent = getattr(tile, "accent", (0.7, 1.0, 0.7))
                plot = LinePlot(color=(*accent, 1), line_width=3.0)
                graph.add_plot(plot)
                self.plots[key] = plot
                self.buffers[key] = []

            # Grundachsen vorbereiten
            graph.ymin, graph.ymax = 0, 1
            graph.xmin, graph.xmax = 0, max(1, self.chart_window)

            # Sync Graph auf Tile-Größe
            def _sync_graph(*_):
                graph.size = tile.size
                graph.pos = tile.pos

            tile.bind(size=_sync_graph, pos=_sync_graph)
            Clock.schedule_once(_sync_graph, 0)

            # Merker für später
            self.graphs[key] = graph
             
        # stash für direkten Zugriff im Append
        if not hasattr(self, "graphs"):
            self.graphs: Dict[str, Any] = {}

        for key in self._tile_keys_int + self._tile_keys_ext:
            tile  = self.dashboard.ids.get(key)
            if not tile:
                print(f"⚠️ Tile nicht gefunden: {key}")
                continue

            graph = getattr(tile.ids, "g", None)
            if graph is None:
                print(f"⚠️ Kein Graph in {key}")
                continue

            # 1) Hintergrund nur über Canvas (kein Widget anfassen)
            bg_path = bg_map.get(key) or default_bg
            if os.path.exists(bg_path):
                self._apply_tile_bg(tile, bg_path)
                print(f"🖼️ {key}: BG aktiv → {os.path.basename(bg_path)}")

            # 2) Graph optisch ruhigstellen & vollflächig machen
            try:
                graph.draw_ticks = False
                graph.draw_labels = False
                graph.draw_border = False
                graph.tick_color = (0, 0, 0, 0)
                graph.background_color = (0, 0, 0, 0)
                graph.size_hint = (1, 1)
                graph.pos_hint = {"x": 0, "y": 0}
            except Exception:
                pass

            # 3) Plot anlegen, wenn nicht vorhanden
            if key not in self.plots:
                accent = getattr(tile, "accent", (0.7, 1.0, 0.7))
                plot = LinePlot(color=(*accent, 1), line_width=3.0)
                graph.add_plot(plot)
                self.plots[key] = plot
                self.buffers[key] = []

            # 4) Grundachsen
            graph.ymin, graph.ymax = 0, 1
            graph.xmin, graph.xmax = 0, max(1, self.chart_window)

            # 5) Sync Graph auf Tile-Größe (ohne Reparent)
            def _sync_graph(*_):
                graph.size = tile.size
                graph.pos  = tile.pos
            tile.bind(size=_sync_graph, pos=_sync_graph)
            Clock.schedule_once(_sync_graph, 0)

            # 6) Merker
            self.graphs[key] = graph

    # ------------------------------
    # Android-Bridge
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
                BleBridgePersistent.setActiveMac(dev if dev else None)
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
        if self._poll_event:
            Clock.unschedule(self._poll_event)
        self.running = True
        self._poll_event = Clock.schedule_interval(self._poll_json, self.refresh_interval)
        print(f"▶️ Starte Polling ({self.refresh_interval}s)")

    def stop_polling(self) -> None:
        if self._poll_event:
            Clock.unschedule(self._poll_event)
            self._poll_event = None
        self.running = False
        print("⏹ Polling gestoppt.")

    def user_stop(self) -> None:
        self._user_paused = True
        self._stale_logged = True
        self._last_pkt_at_stop = None
        self.stop_polling()
        print("⏸️ Manuell pausiert – Charts bleiben sichtbar.")

    def user_start(self) -> None:
        self._user_paused = False
        self._stale_logged = False
        self._ensure_recovery_timer()
        self.start_polling()
        print("▶️ Manuell fortgesetzt.")

    # ------------------------------
    # Recovery-Timer
    # ------------------------------
    def _ensure_recovery_timer(self) -> None:
        if self._recovery_event is None:
            self._recovery_event = Clock.schedule_interval(self._check_recovery, 1.5)

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
            return

        mac = d.get("address") or d.get("mac") or self.cfg.get("device_id") or "--"
        if mac and mac != self._header_cache.get("mac"):
            try:
                header.ids.device_label.text = (
                    f"[font=assets/fonts/fa-solid-900.ttf]\uf293[/font] {mac}"
                )
            except Exception:
                header.ids.device_label.text = mac
            self._header_cache["mac"] = mac

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
        if new_val is None or ref_val is None:
            return False
        return new_val != ref_val

    # ------------------------------
    # Haupt-Poll (mit Auto-Cleanup)
    # ------------------------------
    def _poll_json(self, *_):
        if not self.running:
            return
        try:
            device_id = (getattr(config, "load_device_id", lambda: None)() or
                         self.cfg.get("device_id"))

            if not os.path.exists(APP_JSON):
                self._set_no_data_labels()
                return
            with open(APP_JSON, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                self._set_no_data_labels()
                return

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return
            if not isinstance(data, list) or not data:
                self._set_no_data_labels()
                return

            if device_id:
                data = [d for d in data if (d.get("address") or d.get("mac")) == device_id]
                if not data:
                    self._set_no_data_labels()
                    return

            d = data[0]
            self._update_header(d)

            # alive=false → Freeze + optional Auto-Stop
            alive_flag = d.get("alive")
            if alive_flag is False:
                self._set_no_data_labels()
                if self.allow_auto_stop and not self._user_paused:
                    pkt_stop = d.get("packet_counter") or d.get("pkt") or d.get("counter")
                    try:
                        self._last_pkt_at_stop = int(pkt_stop)
                    except Exception:
                        self._last_pkt_at_stop = self._last_pkt_seen
                    self.stop_polling()
                    print("⏹ Polling auto-gestoppt (Bridge alive=false). Warte auf Counter-Änderung…")
                try:
                    if os.path.exists(APP_JSON):
                        os.remove(APP_JSON)
                        print("🧹 JSON gelöscht – alive=false erkannt")
                except Exception as e:
                    print(f"⚠️ JSON-Löschung fehlgeschlagen: {e}")
                return

            # Watchdog
            pkt = d.get("packet_counter") or d.get("pkt") or d.get("counter")
            try:
                pkt_val = int(pkt) if pkt is not None else None
            except Exception:
                pkt_val = None

            now = time.time()
            dyn_timeout = self._effective_timeout()
            stale_for = now - self._last_pkt_time

            if pkt_val is not None:
                if self._last_pkt_seen is None or pkt_val != self._last_pkt_seen:
                    self._last_pkt_seen = pkt_val
                    self._last_pkt_time = now
                    if self._stale_logged:
                        print("✅ Neuer Datenstrom erkannt – Charts reaktiviert")
                    self._stale_logged = False
                elif stale_for >= dyn_timeout:
                    if not self._stale_logged:
                        print(f"⚠️ Keine neuen Pakete seit {stale_for:.1f}s")
                        self._stale_logged = True
                    self._set_no_data_labels()
                    if self.allow_auto_stop and not self._user_paused:
                        self._last_pkt_at_stop = self._last_pkt_seen
                        self.stop_polling()
                        print("⏹ Polling auto-gestoppt (Stille). Warte auf Counter-Änderung…")
                    try:
                        if os.path.exists(APP_JSON):
                            os.remove(APP_JSON)
                            print("🧹 JSON gelöscht – Timeout ohne Daten")
                    except Exception as e:
                        print(f"⚠️ JSON-Löschung fehlgeschlagen: {e}")
                    return
            else:
                if stale_for >= dyn_timeout:
                    if not self._stale_logged:
                        print(f"⚠️ Keine neuen Pakete seit {stale_for:.1f}s (kein counter)")
                        self._stale_logged = True
                    self._set_no_data_labels()
                    if self.allow_auto_stop and not self._user_paused:
                        self._last_pkt_at_stop = self._last_pkt_seen if (self._last_pkt_seen is not None) else -1
                        self.stop_polling()
                        print("⏹ Polling auto-gestoppt (kein counter).")
                    try:
                        if os.path.exists(APP_JSON):
                            os.remove(APP_JSON)
                            print("🧹 JSON gelöscht – kein Counter erkannt")
                    except Exception as e:
                        print(f"⚠️ JSON-Löschung fehlgeschlagen: {e}")
                    return

            # Werte
            t_int_c = d.get("temperature_int", 0.0)
            t_ext_c = d.get("temperature_ext", 0.0)
            h_int   = d.get("humidity_int", 0.0)
            h_ext   = d.get("humidity_ext", 0.0)

            ext_now = self._detect_external_present(t_ext_c, h_ext)
            if self.ext_present is None or ext_now != self.ext_present:
                self.ext_present = ext_now
                self._apply_layout(ext_now)

            vpd_in  = utils.calc_vpd(t_int_c, h_int)
            vpd_out = utils.calc_vpd(t_ext_c, h_ext)

            try:
                unit_str = str((config.load_config() or {}).get("unit", "°C"))
                is_f = "F" in unit_str.upper()
            except Exception:
                is_f = False
            from utils import convert_temperature
            t_int_disp = convert_temperature(t_int_c, "F") if is_f else t_int_c
            t_ext_disp = convert_temperature(t_ext_c, "F") if is_f else t_ext_c

            values = {
                "tile_t_in":   t_int_disp,
                "tile_h_in":   h_int,
                "tile_vpd_in": vpd_in,
                "tile_t_out":  t_ext_disp,
                "tile_h_out":  h_ext,
                "tile_vpd_out": vpd_out,
            }

            # UI-Update – weakproxy-safe
            for key, val in values.items():
                self._append_value(key, val)

                tile = self.dashboard.ids.get(key)
                if not tile:
                    continue
                big  = self._safe_ids(tile, "big")
                graph = self._safe_ids(tile, "g")
                if graph is None:
                    continue

                try:
                    unit = get_unit_for_key(key)
                    if big:
                        big.text = f"{val:.2f} {unit}" if unit else f"{val:.2f}"
                    self._auto_scale_y(graph, key)
                except ReferenceError:
                    # Layout wurde rekonstruiert; nächster Poll repariert es automatisch
                    continue
                except Exception:
                    continue

            # Scatter update (optional)
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
    # Recovery
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
            alive_flag = d.get("alive")

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

        was_running = bool(getattr(self, "running", False))
        if was_running:
            try:
                self.stop_polling()
            except Exception:
                pass

        if ext_visible:
            grid.rows, grid.cols = 2, 3
        else:
            grid.rows, grid.cols = 1, 3

        self._toggle_external_tiles(ext_visible)
        Clock.schedule_once(lambda dt: grid.do_layout(), 0.4)

        if was_running:
            Clock.schedule_once(lambda dt: self.start_polling(), 0.6)

    # Nach Layoutwechsel komplette Tile-Canvas refreshen
        def _refresh_all(*_):
            for key in self._tile_keys_int + self._tile_keys_ext:
                tile = self.dashboard.ids.get(key)
                if not tile:
                    continue
                wrapper = next((w for w in tile.children if isinstance(w, FloatLayout)), None)
                graph = tile.ids.get("g") if hasattr(tile, "ids") else None
                if graph and wrapper:
                    graph.size = wrapper.size
                    graph.pos = wrapper.pos
        Clock.schedule_once(_refresh_all, 0.2)
    # ------------------------------
    # Helper: Basis-Höhe sicherstellen
    # ------------------------------
    def _ensure_base_height(self, tile):
        """Guarantees a sane base_height for animations/layout."""
        if not hasattr(tile, "base_height") or not getattr(tile, "base_height", 0):
            tile.base_height = tile.height if tile.height > 0 else dp(160)

    # ------------------------------
    # Sichtbarkeit externer Tiles anpassen
    # ------------------------------
    def _toggle_external_tiles(self, visible: bool) -> None:
        for key in self._tile_keys_ext:
            tile = self.dashboard.ids.get(key)
            if not tile:
                continue
            self._ensure_base_height(tile)
            Animation.cancel_all(tile)
            if visible:
                tile.disabled = False
                Animation(opacity=1.0, height=tile.base_height, d=0.35).start(tile)
            else:
                tile.disabled = True
                Animation(opacity=0.0, height=0, d=0.35).start(tile)

        for key in self._tile_keys_int:
            tile = self.dashboard.ids.get(key)
            if not tile:
                continue
            self._ensure_base_height(tile)
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
        buf.append((self.counter, float(val)))

        # begrenzen (inplace)
        if len(buf) > self.chart_window:
            del buf[:-self.chart_window]

        plot = self.plots.get(key)
        if plot:
            # neue Liste zuweisen → GPU-Leak-Fix
            plot.points = buf[:]

        # Fenster gleiten lassen, unabhängig von counter-Start
        graph = getattr(self, "graphs", {}).get(key)
        if graph:
            n = len(buf)
            if n >= 2:
                x_max = buf[-1][0]
                x_min = x_max - (self.chart_window - 1)
                if x_min < 0:
                    x_min = 0
                graph.xmin = x_min
                graph.xmax = max(graph.xmin + 1, x_max)

            # Y automatisch skalieren
            self._auto_scale_y(graph, key)
    # ------------------------------
    # Reset & Config-Reload
    # ------------------------------
    def reset_data(self) -> None:
        for buf in self.buffers.values():
            buf.clear()
        for p in self.plots.values():
            try:
                p.points = []
            except ReferenceError:
                pass
        for key in ["tile_t_in","tile_h_in","tile_vpd_in","tile_t_out","tile_h_out","tile_vpd_out"]:
            tile = self.dashboard.ids.get(key)
            if not tile:
                continue
            big = self._safe_ids(tile, "big")
            self._safe_set_text(big, "--")
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

    # ------------------------------
    # Auto-Scaling Y-Achse
    # ------------------------------
    def _auto_scale_y(self, graph, key: str) -> None:
        try:
            vals = [v for _, v in self.buffers.get(key, []) if isinstance(v, (int, float))]
            if not vals:
                return
            y_min, y_max = min(vals), max(vals)

            # Falls alle Werte gleich → minimaler Bereich
            if abs(y_max - y_min) < 1e-6:
                y_min, y_max = y_min - 0.5, y_max + 0.5

            # 20 % Sicherheitsabstand oben/unten
            margin = max((y_max - y_min) * 0.2, 0.2)
            graph.ymin = round(y_min - margin, 1)
            graph.ymax = round(y_max + margin, 1)

            # X-Achse gleitend halten
            if self.counter >= self.chart_window:
                graph.xmin = self.counter - self.chart_window
                graph.xmax = self.counter
            else:
                graph.xmin = 0
                graph.xmax = self.chart_window
        except Exception as e:
            print(f"⚠️ Auto-Scale-Fehler ({key}): {e}")

    # ------------------------------
    # Kein-Daten-Labels (Fallback)
    # ------------------------------
    def _set_no_data_labels(self) -> None:
        keys = [
            "tile_t_in", "tile_h_in", "tile_vpd_in",
            "tile_t_out", "tile_h_out", "tile_vpd_out"
        ]
        for key in keys:
            tile = self.dashboard.ids.get(key)
            if not tile:
                continue
            big = getattr(tile.ids, "big", None)
            if big:
                try:
                    big.text = "--"
                except Exception:
                    pass

        for plot in self.plots.values():
            try:
                plot.points = []
            except Exception:
                pass
            
