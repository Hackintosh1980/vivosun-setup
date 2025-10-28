from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition
from setup_screen import SetupScreen
from dashboard_screen import DashboardScreen
from vpd_scatter_screen import VpdScatterScreen  # <- NEU
from kivy.config import Config
Config.set('graphics', 'dpi', '160')
Config.set('graphics', 'resizable', False)
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
class Root(App):
    def build(self):
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(SetupScreen(name="setup"))
        sm.add_widget(DashboardScreen(name="dashboard"))
        sm.add_widget(VpdScatterScreen(name="vpd"))   # <- NEU
        sm.current = "setup"
        return sm

if __name__ == "__main__":
    Root().run()
