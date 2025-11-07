#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enlarged_chart_window.py – Fullscreen-Chart 🌿 v4.1 Stable
• Swipe + Buttons
• Header links: Wert + Einheit, darunter Titel
• Header rechts: LED (BT aktiv), MAC, RSSI
• Farben = Dashboard-Schema
• LED-Bug behoben (nur 1x Ellipse)
• VM-safe (FBO fallback)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy_garden.graph import Graph, LinePlot
from kivy.utils import platform
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty, ListProperty
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.core.text import LabelBase
from kivy.uix.modalview import ModalView

# -------------------------------------------------------
# Scaling & Font
# -------------------------------------------------------
if platform == "android":
    UI_SCALE = 0.72
else:
    UI_SCALE = 1.0

def sp_scaled(v): return f"{int(v * UI_SCALE)}sp"
def dp_scaled(v): return dp(v * UI_SCALE)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FA_PATH = os.path.join(BASE_DIR, "assets", "fonts", "fa-solid-900.ttf")
if os.path.exists(FA_PATH):
    try:
        LabelBase.register(name="FA", fn_regular=FA_PATH)
    except Exception:
        pass

# -------------------------------------------------------
# Maps
# -------------------------------------------------------
TITLE_MAP = {
    "tile_t_in": ("Internal Temperature", "°C"),
    "tile_h_in": ("Internal Humidity", "%"),
    "tile_vpd_in": ("Internal VPD", "kPa"),
    "tile_t_out": ("External Temperature", "°C"),
    "tile_h_out": ("External Humidity", "%"),
    "tile_vpd_out": ("External VPD", "kPa"),
}
ALL_KEYS = ["tile_t_in","tile_h_in","tile_vpd_in","tile_t_out","tile_h_out","tile_vpd_out"]
INT_KEYS = ["tile_t_in","tile_h_in","tile_vpd_in"]
INVALID_SENTINEL = -90.0

COLOR_MAP = {
    "tile_t_in": (1.00, 0.45, 0.45),
    "tile_t_out": (1.00, 0.70, 0.35),
    "tile_h_in": (0.35, 0.70, 1.00),
    "tile_h_out": (0.45, 0.95, 1.00),
    "tile_vpd_in": (0.85, 1.00, 0.45),
    "tile_vpd_out": (0.60, 1.00, 0.60),
}

# -------------------------------------------------------
# EnlargedChartWindow
# -------------------------------------------------------
class EnlargedChartWindow(BoxLayout):
    tile_key = StringProperty("")
    chart_mgr = ObjectProperty(None)
    _allowed = ListProperty([])
    _index = 0

    def __init__(self, chart_mgr, start_key="tile_t_in", **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.chart_mgr = chart_mgr
        self._allowed = ALL_KEYS if getattr(chart_mgr, "ext_present", True) else INT_KEYS
        self._index = self._safe_index(start_key)
        self.tile_key = self._allowed[self._index]
        self._touch_start_x = None
        self._graph_ok = True

        self._build_ui()
        self._refresh_titles_and_colors()
        self._update_chart()
        self._ev = Clock.schedule_interval(self._update_chart, 1.0)

    # ---------------------------------------------------
    def _safe_index(self, key):
        try: return self._allowed.index(key)
        except Exception: return 0

    def _unit_for_key(self, key):
        try:
            import config
            cfg = config.load_config()
            temp_unit = "°F" if cfg.get("unit", "°C") == "°F" else "°C"
        except Exception:
            temp_unit = "°C"
        if key.startswith("tile_t_"): return temp_unit
        if key.startswith("tile_h_"): return "%"
        if key.startswith("tile_vpd_"): return "kPa"
        return ""

    def _title(self, key): return TITLE_MAP.get(key, (key, ""))[0]

    def _allowed_keys_now(self):
        return ALL_KEYS if getattr(self.chart_mgr, "ext_present", True) else INT_KEYS

    # ---------------------------------------------------
    # UI
    # ---------------------------------------------------
    def _build_ui(self):
        with self.canvas.before:
            Color(0.02, 0.05, 0.03, 1)
            self._bg = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=lambda *_: setattr(self._bg, "size", self.size))
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos))

        # Header
        self._header = BoxLayout(orientation="horizontal", size_hint_y=None,
                                 height=dp_scaled(70), padding=[dp_scaled(12), dp_scaled(8), dp_scaled(12), 0],
                                 spacing=dp_scaled(8))
        # left
        self._left = BoxLayout(orientation="vertical", size_hint_x=0.6, spacing=dp_scaled(2))
        self._value_lbl = Label(text="--", font_size=sp_scaled(28), color=(0.95, 1, 0.95, 1),
                                bold=True, halign="left", valign="middle", size_hint_y=None, height=dp_scaled(36))
        self._title_lbl = Label(markup=True, text="[b]—[/b]", font_size=sp_scaled(16),
                                color=(0.8, 1, 0.85, 1), halign="left", valign="middle",
                                size_hint_y=None, height=dp_scaled(24))
        self._left.add_widget(self._value_lbl)
        self._left.add_widget(self._title_lbl)

        # right
        self._right = BoxLayout(orientation="horizontal", size_hint_x=0.4, spacing=dp_scaled(6))
        self._led_box = BoxLayout(orientation="vertical", size_hint_x=None, width=dp_scaled(28))
        with self._led_box.canvas:
            self._led_color = Color(1, 0, 0, 1)
            self._led_ellipse = Ellipse(size=(dp_scaled(16), dp_scaled(16)))
        def _pos_led(*_):
            self._led_ellipse.pos = (self._led_box.x+dp_scaled(6),
                                     self._led_box.y+(self._led_box.height-dp_scaled(16))/2)
        self._led_box.bind(pos=_pos_led, size=_pos_led)

        self._mac_lbl = Label(text="--", font_size=sp_scaled(13), color=(0.8,1,0.9,1),
                              halign="left", valign="middle")
        self._rssi_lbl = Label(text="-- dBm", font_size=sp_scaled(13), color=(0.8,1,0.9,1),
                               halign="left", valign="middle")
        rbox = BoxLayout(orientation="vertical")
        rbox.add_widget(self._mac_lbl)
        rbox.add_widget(self._rssi_lbl)
        self._right.add_widget(self._led_box)
        self._right.add_widget(rbox)

        self._header.add_widget(self._left)
        self._header.add_widget(self._right)
        self.add_widget(self._header)

        # Graph
        try:
            self.graph = Graph(xlabel="Time", ylabel="", x_ticks_major=10, y_ticks_major=0.5,
                               background_color=(0.05, 0.07, 0.06, 1),
                               tick_color=(0.3, 0.8, 0.4, 1),
                               draw_border=False, xmin=0, xmax=60, ymin=0, ymax=1, size_hint_y=1.0)
            self.plot = LinePlot(line_width=4.0)
            self.graph.add_plot(self.plot)
            self.add_widget(self.graph)
        except Exception as e:
            self._graph_ok = False
            self.add_widget(Label(text="⚠️ Graph not supported (VM FBO error)",
                                  color=(1,0.8,0.6,1)))

        # Controls
        self._controls = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp_scaled(58),
                                   spacing=dp_scaled(8), padding=[dp_scaled(8)]*4)
        def _btn(text,bg,cb,w=None,fs=16):
            b = Button(markup=True, text=text, font_size=sp_scaled(fs),
                       background_normal="", background_color=bg, on_release=lambda *_: cb())
            if w: b.size_hint_x=None; b.width=dp_scaled(w)
            return b
        self._controls.add_widget(_btn("[font=FA]\uf060[/font]",(0.25,0.45,0.28,1),lambda: self._switch(-1),58))
        self._controls.add_widget(_btn("[font=FA]\uf061[/font]",(0.25,0.45,0.28,1),lambda: self._switch(+1),58))
        self._controls.add_widget(_btn("[font=FA]\uf021[/font] Reset",(0.25,0.55,0.25,1),self._do_reset))
        self._controls.add_widget(_btn("[font=FA]\uf015[/font] Dashboard",(0.35,0.28,0.28,1),self._close_view))
        self.add_widget(self._controls)

    # ---------------------------------------------------
    def _refresh_titles_and_colors(self):
        title = self._title(self.tile_key)
        unit = self._unit_for_key(self.tile_key)
        self._title_lbl.text = f"[b]{title}[/b]"
        if self._graph_ok:
            self.graph.ylabel = f"{title} ({unit})"
            rgb = COLOR_MAP.get(self.tile_key, (0.4, 1.0, 0.6))
            try:
                if self.plot in self.graph.plots:
                    self.graph.remove_plot(self.plot)
            except Exception: pass
            self.plot = LinePlot(color=(rgb[0], rgb[1], rgb[2], 1))
            self.plot.line_width = 4.0
            self.graph.add_plot(self.plot)
            self.graph.tick_color = (rgb[0]*0.7, rgb[1]*0.9, rgb[2]*0.7, 1)

    # ---------------------------------------------------
    def _update_chart(self,*_):
        try:
            self._allowed = self._allowed_keys_now()
            buf = self.chart_mgr.buffers.get(self.tile_key, [])
            clean = [(x,y) for x,y in buf if isinstance(y,(int,float)) and y>INVALID_SENTINEL]

            if self._graph_ok:
                if not clean:
                    self.plot.points=[]
                    self._value_lbl.text="--"
                else:
                    self.plot.points=clean
                    ys=[y for _,y in clean]
                    ymin,ymax=min(ys),max(ys)
                    if abs(ymax-ymin)<1e-6: ymax=ymin+0.5; ymin=ymin-0.5
                    m=max((ymax-ymin)*0.2,0.2)
                    self.graph.ymin=round(ymin-m,2)
                    self.graph.ymax=round(ymax+m,2)
                    cw=int(getattr(self.chart_mgr,"chart_window",120) or 120)
                    last_x=clean[-1][0]
                    self.graph.xmax=max(last_x,cw)
                    self.graph.xmin=max(0,self.graph.xmax-cw)
                    unit=self._unit_for_key(self.tile_key)
                    self._value_lbl.text=f"{clean[-1][1]:.2f} {unit}"
            else:
                self._value_lbl.text="--" if not clean else f"{clean[-1][1]:.2f}"

            # Header rechts
            mac=getattr(self._get_app_safe(),"current_mac",None) or getattr(self.chart_mgr,"cfg",{}).get("device_id","--")
            rssi=getattr(self._get_app_safe(),"last_rssi",None)
            self._mac_lbl.text=str(mac)
            self._rssi_lbl.text=f"{int(rssi)} dBm" if isinstance(rssi,(int,float)) else "-- dBm"

            active=bool(getattr(self.chart_mgr,"running",True)) and bool(clean)
            self._led_color.rgba=(0,1,0,1) if active else (1,0,0,1)
        except Exception as e:
            print(f"⚠️ Enlarged update error: {e}")

    def _get_app_safe(self):
        try:
            from kivy.app import App
            return App.get_running_app()
        except Exception:
            return type("X",(),{})()

    # ---------------------------------------------------
    def _switch(self,direction):
        if not self._allowed: return
        if self.tile_key in self._allowed:
            self._index=self._allowed.index(self.tile_key)
        else:
            self._index=0
        self._index=(self._index+direction)%len(self._allowed)
        self.tile_key=self._allowed[self._index]
        self._refresh_titles_and_colors()
        self._update_chart()

    # ---------------------------------------------------
    def _do_reset(self):
        try:
            if hasattr(self.chart_mgr,"reset_data"):
                self.chart_mgr.reset_data()
        except Exception as e:
            print("⚠️ Reset failed:",e)
        if self._graph_ok: self.plot.points=[]
        self._value_lbl.text="--"

    def _close_view(self,*_):
        parent=self.parent
        while parent and not isinstance(parent,ModalView):
            parent=parent.parent
        if parent:
            try: Clock.unschedule(self._update_chart)
            except Exception: pass
            parent.dismiss()
