# --- Garden Graph Import Fix für Android ---
import os, sys
base = os.path.dirname(__file__)
garden_path = os.path.join(base, "garden")
if garden_path not in sys.path:
    sys.path.append(garden_path)
# -------------------------------------------

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy_garden.graph import Graph, MeshLinePlot
import math, random


class GraphBox(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.graph = Graph(
            xlabel='Zeit', ylabel='Wert',
            xmin=0, xmax=50, ymin=-1, ymax=1,
            background_color=[0.02, 0.05, 0.06, 1],
            border_color=[0.4, 0.8, 0.5, 1],
            tick_color=[0.2, 0.7, 0.3, 1]
        )
        self.plot = MeshLinePlot(color=[0.3, 1.0, 0.6, 1])
        self.graph.add_plot(self.plot)
        self.add_widget(self.graph)
        Clock.schedule_interval(self.update, 0.05)
        self.x = 0

    def update(self, dt):
        self.x += 1
        self.plot.points.append((self.x, math.sin(self.x / 5) + random.uniform(-0.05, 0.05)))
        if len(self.plot.points) > 50:
            self.plot.points = self.plot.points[-50:]


class DummyApp(App):
    def build(self):
        return GraphBox()


if __name__ == "__main__":
    DummyApp().run()
