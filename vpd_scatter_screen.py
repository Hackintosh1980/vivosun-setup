from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel


class SimpleScatter(Widget):
    """Einfacher, performanter VPD-Scatter mit 2 Sensorpunkten + Skala."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.vpd_in = 0.0
        self.vpd_out = 0.0
        self.bind(size=self._trigger_redraw, pos=self._trigger_redraw)
        Clock.schedule_interval(self.redraw, 1)

    def set_values(self, vin, vout):
        self.vpd_in = vin
        self.vpd_out = vout
        self.redraw()

    def _trigger_redraw(self, *a):
        self.redraw()

    def redraw(self, *a):
        if self.width <= 0 or self.height <= 0:
            return

        self.canvas.clear()
        with self.canvas:
            # ---- Farb-Zonen (Hintergrund)
            zones = [
                (0.0, (0.0, 0.3, 0.1)),
                (1.2, (0.2, 0.6, 0.1)),
                (2.3, (0.8, 0.5, 0.0)),
                (3.5, (0.8, 0.1, 0.1)),
            ]
            step = self.height / len(zones)
            for i, z in enumerate(zones):
                Color(*z[1], 1)
                Rectangle(pos=(self.x, self.y + i * step), size=(self.width, step))

            # ---- Achsen + Skala
            Color(0.4, 0.4, 0.4)
            Line(points=[self.x + 50, self.y + 50, self.right - 30, self.y + 50], width=1.2)
            Line(points=[self.x + 50, self.y + 50, self.x + 50, self.top - 30], width=1.2)

            for i in range(8):
                x = self.x + 50 + i * (self.width - 100) / 7
                Line(points=[x, self.y + 45, x, self.y + 55], width=1)
                lbl = CoreLabel(text=f"{0.5*i:.1f}", font_size=18)
                lbl.refresh()
                Rectangle(texture=lbl.texture, pos=(x - 10, self.y + 20), size=lbl.texture.size)

            # ---- Legende (oben rechts)
            legend_y = self.top - 40
            Color(0.2, 1.0, 0.3)
            Ellipse(pos=(self.right - 140, legend_y), size=(18, 18))
            Color(1, 1, 1)
            Rectangle(texture=CoreLabel(text="IN", font_size=18).texture,
                      pos=(self.right - 110, legend_y - 2), size=(20, 20))

            Color(1.0, 0.6, 0.2)
            Ellipse(pos=(self.right - 70, legend_y), size=(18, 18))
            Color(1, 1, 1)
            Rectangle(texture=CoreLabel(text="OUT", font_size=18).texture,
                      pos=(self.right - 40, legend_y - 2), size=(40, 20))

            # ---- Punkte (nur wenn Werte > 0)
            if self.vpd_in > 0 or self.vpd_out > 0:
                self._draw_point(self.vpd_in, (0.2, 1.0, 0.3), "IN")
                self._draw_point(self.vpd_out, (1.0, 0.6, 0.2), "OUT")

    def _draw_point(self, val, color, label):
        """Zeichnet einen Punkt im 2D-VPD-Koordinatensystem."""
        from kivy.core.text import Label as CoreLabel

        max_vpd = 3.5
        # clamp: Werte zwischen 0 und 1
        ratio_x = min(max(self.vpd_in / max_vpd, 0), 1)
        ratio_y = min(max(self.vpd_out / max_vpd, 0), 1)

        # beide Achsen unterschiedlich – echter 2D Scatter
        if label == "IN":
            x = self.x + 50 + ratio_x * (self.width - 100)
            y = self.y + 50 + ratio_y * (self.height - 100)
        else:
            # OUT leicht versetzt, um Überdeckung zu vermeiden
            x = self.x + 50 + ratio_y * (self.width - 100)
            y = self.y + 50 + ratio_x * (self.height - 100)

        # Punkt zeichnen
        Color(*color)
        Ellipse(pos=(x - 12, y - 12), size=(24, 24))

        # Beschriftung direkt daneben
        Color(1, 1, 1)
        lbl = CoreLabel(text=f"{label} {val:.2f}", font_size=18)
        lbl.refresh()
        Rectangle(texture=lbl.texture, pos=(x + 15, y - 10), size=lbl.texture.size)

class VpdScatterScreen(Screen):
    """Scatter-Fenster mit Rückkehr-Button zum Dashboard."""
    def on_enter(self):
        self.build_ui()

    def build_ui(self):
        self.clear_widgets()
        layout = BoxLayout(orientation="vertical", padding=20, spacing=10)

        title = Label(
            text="[b][color=#ffaa33]🌿 VPD Scatter Chart[/color][/b]",
            markup=True, font_size="30sp", size_hint_y=0.1
        )

        self.chart = SimpleScatter(size_hint=(1, 0.8))

        back_btn = Button(
            text="← Zurück zum Dashboard",
            size_hint=(1, 0.1),
            background_color=(0.2, 0.6, 0.2, 1),
            font_size="22sp",
            on_release=lambda *_: self.go_back()
        )

        layout.add_widget(title)
        layout.add_widget(self.chart)
        layout.add_widget(back_btn)
        self.add_widget(layout)

    def go_back(self):
        self.manager.current = "dashboard"

    def update_points(self, vpd_in, vpd_out):
        """Vom Dashboard aufgerufen – aktualisiert Scatter-Werte."""
        if hasattr(self, "chart"):
            self.chart.set_values(vpd_in, vpd_out)
