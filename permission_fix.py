#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
permission_fix.py – zentrale Rechte- und Statusprüfungen
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

from kivy.utils import platform

def check_permissions():
    """
    Prüft Bluetooth-Verfügbarkeit und ggf. weitere Systemrechte.
    Rückgabe: True = alles ok, False = Problem.
    """
    try:
        if platform == "android":
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            adapter = BluetoothAdapter.getDefaultAdapter()

            if adapter is None:
                print("❌ Kein Bluetooth-Adapter erkannt!")
                return False
            if not adapter.isEnabled():
                print("⚠️ Bluetooth deaktiviert – bitte einschalten!")
                return False

            # Android Runtime-Permissions prüfen
            ContextCompat = autoclass("androidx.core.content.ContextCompat")
            ActivityCompat = autoclass("androidx.core.app.ActivityCompat")
            Manifest = autoclass("android.Manifest")
            activity = PythonActivity.mActivity

            permissions = [
                Manifest.permission.BLUETOOTH,
                Manifest.permission.BLUETOOTH_ADMIN,
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
            ]

            missing = []
            for p in permissions:
                granted = ContextCompat.checkSelfPermission(activity, p)
                if granted != 0:
                    missing.append(p)

            if missing:
                print(f"⚠️ Fehlende Berechtigungen: {missing}")
                ActivityCompat.requestPermissions(activity, permissions, 1)
                return False

            print("✅ Bluetooth-/Location-Rechte vorhanden und aktiv.")
            return True

        else:
            # Desktop / VM – Basischeck
            import subprocess
            out = subprocess.run(["hciconfig"], capture_output=True, text=True)
            if "hci0" in out.stdout:
                print("✅ Desktop-Bluetooth-Adapter erkannt.")
                return True
            print("⚠️ Kein Bluetooth-Adapter (hci0) gefunden.")
            return False

    except Exception as e:
        print(f"⚠️ Permission-Check-Fehler: {e}")
        return False
