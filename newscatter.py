#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIVOSUN Neon VPD Scatter – Static Comfort Map
Fixe Zonen + Neon Dots (kein Redraw, kein Verlauf)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

import os, sys, math, random, time
from collections import deque
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, BooleanProperty
from kivy.garden.graph import Graph
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, Ellipse, InstructionGroup
from kivy.core.text import LabelBase
from kivy.uix.label import Label
from kivy.metrics import dp

sys.path.append(os.path.join(os.path.dirname(__file__), "garden", "graph"))

try:
    LabelBase.register(
        name="Emoji",
        fn_regular="/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
    )
except Exception:
    pass

Window.size = (1280, 720)

KV = """
<Header@BoxLayout>:
    size_hint_y: None
    height: "86dp"
    padding: 12
    spacing: 12
    canvas.before:
        Color:
            rgba: 0.06, 0.10, 0.07, 1
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: "🌿  VIVOSUN Neon VPD Comfort Scatter"
        bold: True
        font_size: "28sp"
        color: 0.9, 1, 0.9, 1
    Label:
        text: app.header_right
        size_hint_x: None
        width: self.texture_size[0] + dp(12)
        color: 0.8, 1, 0.8, 1

<Footer>:
    size_hint_y: None
    height: "64dp"
    padding: 10
    spacing: 10
    canvas.before:
        Color:
            rgba: 0.05, 0.09, 0.06, 1
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: root.status_text
        color: 1,1,1,1
        font_size: "18sp"

<RootPane>:
    orientation: "vertical"
    padding: 12
    spacing: 12
    canvas.before:
        Color:
            rgba: 0.02, 0.04, 0.03, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Header:
    BoxLayout:
        size_hint_y: 1
        padding: 8
        spacing: 8
        canvas.before:
            Color:
                rgba: 0.07, 0.11, 0.08, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [16,16,16,16]

        Graph:
            id: graph
            xlabel: "Temperature (°C)"
            ylabel: "Relative Humidity (%)"
            xmin: 10
            xmax: 40
            ymin: 20
            ymax: 100
            x_ticks_major: 5
            y_ticks_major: 10
            precision: "0"
            draw_border: False
            background_color: 0.05, 0.07, 0.06, 1
            tick_color: 0.35, 0.8, 0.45, 1
            label_options: {'color': (0.78, 1, 0.82, 1), 'bold': False}

    Footer:
        id: footer

RootPane:
"""

# ------------- Static Background Zones -------------
class StaticVPDZones:
    """Draws fixed comfort zones once, stays under dots."""
    def __init__(self, graph):
        self.graph = graph
        self.group = InstructionGroup()
        graph.canvas.before.add(self.group)
        self.draw()

    def _map(self, x, y):
        g = self.graph
        px = (x - g.xmin) / (g.xmax - g.xmin) * g.width + g.x
        py = (y - g.ymin) / (g.ymax - g.ymin) * g.height + g.y
        return px, py

    def _rect(self, x0, x1, y0, y1, color):
        g = self.graph
        px, py = self._map(x0, y0)
        px2, py2 = self._map(x1, y1)
        w, h = px2 - px, py2 - py
        self.group.add(Color(*color))
        self.group.add(Rectangle(pos=(px, py), size=(w, h)))

    def draw(self):
        g = self.graph
        # Zonen
        self._rect(10, 40, 20, 40, (1.0, 0.45, 0.45, 0.25))  # Dry
        self._rect(10, 40, 40, 60, (1.0, 0.8, 0.4, 0.25))    # Warm
        self._rect(10, 40, 60, 80, (0.4, 1.0, 0.7, 0.28))    # Optimal
        self._rect(10, 40, 80, 100,(0.4, 0.7, 1.0, 0.25))    # Humid
        # Zone Labels (Neon Schrift)
        lbls = [
            ("Too Dry",    15, 30, (1.0,0.7,0.7,1)),
            ("Warm Zone",  15, 50, (1.0,0.9,0.6,1)),
            ("Optimal",    15, 68, (0.8,1.0,0.8,1)),
            ("Too Humid",  15, 88, (0.6,0.9,1.0,1)),
        ]
        for text, tx, ty, col in lbls:
            px, py = self._map(tx, ty)
            lbl = Label(text=text, color=col, font_size="16sp", bold=True)
            lbl.texture_update()
            Rectangle(texture=lbl.texture, pos=(px, py), size=lbl.texture.size)

# ------------- Overlay for Dots -------------
class NeonDotsOverlay:
    def __init__(self, graph, radius=4.0):
        self.graph = graph
        self.radius = radius
        self.group = InstructionGroup()
        graph.canvas.after.add(self.group)

    def clear(self): self.group.clear()

    def _map(self, x, y):
        g = self.graph
        px = (x - g.xmin) / (g.xmax - g.xmin) * g.width + g.x
        py = (y - g.ymin) / (g.ymax - g.ymin) * g.height + g.y
        return px, py

    def add_points(self, pts, color=(0.4,1.0,0.7,0.95)):
        r=self.radius
        cr,cg,cb,ca=color
        for (x,y) in pts:
            px,py=self._map(x,y)
            self.group.add(Color(cr,cg,cb,ca*0.2))
            self.group.add(Ellipse(pos=(px-r*1.8,py-r*1.8),size=(r*3.6,r*3.6)))
            self.group.add(Color(cr,cg,cb,ca))
            self.group.add(Ellipse(pos=(px-r,py-r),size=(r*2,r*2)))

# ------------- Root Widgets -------------
class Footer(BoxLayout):
    status_text = StringProperty("🟢 Neon VPD Scatter Live")

class RootPane(BoxLayout):
    pass

# ------------- App -------------
class VPDStaticScatterApp(App):
    running = BooleanProperty(True)
    header_right = StringProperty("")

    def build(self):
        self.root = Builder.load_string(KV)
        self.footer = self.root.ids.footer
        self.graph = self.root.ids.graph

        # einmalige Hintergrund-Zonen
        self.zones = StaticVPDZones(self.graph)
        # Punkt-Overlay
        self.overlay = NeonDotsOverlay(self.graph, radius=4.0)
        self.points = deque(maxlen=900)

        Clock.schedule_interval(self._update, 0.33)
        return self.root

    def _synth_point(self):
        t = 25 + 7 * math.sin(time.time() * 0.10 + 0.5) + random.uniform(-0.8,0.8)
        rh = 60 - 15 * math.sin(time.time()*0.07) + random.uniform(-18,18)
        t = max(self.graph.xmin,min(self.graph.xmax,t))
        rh= max(self.graph.ymin,min(self.graph.ymax,rh))
        return t,rh

    def _update(self,*_):
        if not self.running: return
        for _ in range(4):
            self.points.append(self._synth_point())

        self.overlay.clear()
        self.overlay.add_points(self.points, (0.4,1.0,0.7,0.95))
        sec=int(time.time())%60
        self.header_right=time.strftime("%H:%M:")+f"[b]{sec:02d}[/b]"
        if sec%20==0:self.footer.status_text="🟡 Refresh…"
        elif sec%23==0:self.footer.status_text="🟢 Neon VPD Scatter Live"

if __name__=="__main__":
    VPDStaticScatterApp().run()
