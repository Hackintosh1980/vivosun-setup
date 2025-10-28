from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from jnius import autoclass
import json, os, time, config


APP_JSON = "/data/user/0/org.hackintosh1980.vivosunreader/files/ble_scan.json"


class SetupScreen(Screen):
    """
    Geräte-Setup – startet die dauerhafte BleBridgePersistent,
    listet gefundene Geräte, speichert Auswahl in config.json.
    Bridge bleibt aktiv (kein Stop beim Verlassen!).
    """

    # -------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------
    def on_enter(self, *a):
        self._cancel_evt = False
        self._bridge_started = False
        self.build_ui()
        Clock.schedule_once(self.start_bridge_once, 0.5)

    def on_leave(self, *a):
        """Bridge weiterlaufen lassen."""
        self._cancel_evt = True

    # -------------------------------------------------------------
    # UI
    # -------------------------------------------------------------
    def build_ui(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", spacing=8, padding=12)

        self.title = Label(
            text="[b][color=#00ffaa]🌿 Geräte-Setup[/color][/b]",
            markup=True, font_size="28sp"
        )
        self.status = Label(
            text="[color=#aaaaaa]Initialisiere Bridge…[/color]",
            markup=True, font_size="18sp"
        )

        self.list_container = GridLayout(
            cols=1, size_hint_y=None, spacing=6, padding=[0, 4, 0, 12]
        )
        self.list_container.bind(minimum_height=self.list_container.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.list_container)

        btn_row = BoxLayout(size_hint=(1, 0.18), spacing=8)
        self.btn_reload = Button(
            text="🔁 Neu laden", on_release=lambda *_: self.load_device_list()
        )
        self.btn_dashboard = Button(
            text="➡️ Zum Dashboard", on_release=lambda *_: self.to_dashboard()
        )
        btn_row.add_widget(self.btn_reload)
        btn_row.add_widget(self.btn_dashboard)

        root.add_widget(self.title)
        root.add_widget(self.status)
        root.add_widget(scroll)
        root.add_widget(btn_row)
        self.add_widget(root)

    # -------------------------------------------------------------
    # BLE-Bridge starten (nur 1x)
    # -------------------------------------------------------------
    def start_bridge_once(self, *a):
        """Startet BridgePersistent einmalig – kein mehrfacher Start."""
        if self._bridge_started:
            return
        self._bridge_started = True
        try:
            ctx = autoclass("org.kivy.android.PythonActivity").mActivity
            BleBridgePersistent = autoclass("org.hackintosh1980.blebridge.BleBridgePersistent")
            ret = BleBridgePersistent.start(ctx, "ble_scan.json")
            print("BleBridgePersistent.start() →", ret)
            self.status.text = "[color=#00ffaa]🌿 Bridge aktiv – Scan läuft dauerhaft[/color]"
            # Erstes Laden nach kurzer Zeit
            Clock.schedule_once(self.load_device_list, 3)
            # Danach regelmäßig aktualisieren
            Clock.schedule_interval(self.load_device_list, 10)
        except Exception as e:
            self.status.text = f"[color=#ff5555]❌ Bridge-Startfehler:[/color] {e}"

    # -------------------------------------------------------------
    # JSON lesen + Liste erzeugen
    # -------------------------------------------------------------
    def load_device_list(self, *a):
        """Liest aktuelle JSON und zeigt erkannte Thermo-Geräte."""
        if self._cancel_evt:
            return
        try:
            if not os.path.exists(APP_JSON):
                self.status.text = "[color=#ffaa00]Noch keine JSON-Daten...[/color]"
                return

            # Datei lesen
            with open(APP_JSON, "r") as f:
                data = json.load(f)

            if not data:
                self.status.text = "[color=#ffaa00]Keine Geräte erkannt...[/color]"
                return

            self.list_container.clear_widgets()
            devices = {}

            for d in data:
                name = (d.get("name") or "").strip()
                addr = (d.get("address") or "").strip()
                if not addr:
                    continue
                lname = name.lower()
                if any(x in lname for x in ["thermo", "vivosun", "beacon"]):
                    devices[addr] = name or "ThermoBeacon"

            if not devices:
                self.status.text = "[color=#ffaa00]Noch keine passenden Geräte...[/color]"
                return

            self.status.text = f"[color=#00ffaa]{len(devices)} Gerät(e)[/color] – zum Speichern tippen:"
            for addr, name in sorted(devices.items()):
                btn = Button(
                    text=f"{name}\n[b]{addr}[/b]",
                    markup=True,
                    size_hint_y=None,
                    height="68dp",
                )
                btn.bind(on_release=lambda _b, a=addr: self.select_device(a))
                self.list_container.add_widget(btn)

        except Exception as e:
            self.status.text = f"[color=#ff8888]Fehler beim Lesen:[/color] {e}"

    # -------------------------------------------------------------
    # Auswahl + Wechsel zum Dashboard
    # -------------------------------------------------------------
    def select_device(self, addr):
        """Speichert die Device-ID in config.json und wechselt zum Dashboard."""
        try:
            config.save_device_id(addr)
            self.status.text = f"[color=#00ffaa]✅ Gespeichert:[/color] {addr}"
            if self.manager and "dashboard" in self.manager.screen_names:
                Clock.schedule_once(lambda *_: self.to_dashboard(), 0.3)
        except Exception as e:
            self.status.text = f"[color=#ff8888]Fehler beim Speichern:[/color] {e}"

    def to_dashboard(self):
        """Wechselt direkt ins Dashboard."""
        if self.manager and "dashboard" in self.manager.screen_names:
            self.manager.current = "dashboard"
