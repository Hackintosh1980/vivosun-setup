#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
permission_fix.py – zentrale Rechte- und Statusprüfungen (Android 10–14)
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

from kivy.utils import platform

def check_permissions():
    """
    Prüft Bluetooth-Verfügbarkeit und alle relevanten Runtime-Permissions.
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

            # --- Basis-Permissions (Android 10–14 gültig) ---
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

            # --- Dynamisch erweitern ab Android 12 (API 31) ---
            try:
                BuildVersion = autoclass("android.os.Build$VERSION")
                sdk_int = BuildVersion.SDK_INT
                print(f"📱 Android SDK-Version erkannt: {sdk_int}")

                if sdk_int >= 31:  # Android 12+
                    permissions += [
                        "android.permission.BLUETOOTH_SCAN",
                        "android.permission.BLUETOOTH_CONNECT",
                        "android.permission.BLUETOOTH_ADVERTISE",
                    ]
                    print("➕ Erweiterte BLE-Permissions hinzugefügt")

                if sdk_int >= 33:  # Android 13+
                    permissions += ["android.permission.POST_NOTIFICATIONS"]
                    print("🔔 Notification-Permission hinzugefügt")

            except Exception as e:
                print(f"⚠️ SDK-Version konnte nicht ermittelt werden: {e}")

            # --- Prüfen & ggf. anfordern ---
            missing = []
            for p in permissions:
                granted = ContextCompat.checkSelfPermission(activity, p)
                if granted != 0:
                    missing.append(p)

            if missing:
                print(f"⚠️ Fehlende Berechtigungen: {missing}")
                ActivityCompat.requestPermissions(activity, permissions, 1)
                return False

            print("✅ Alle Bluetooth-/Location-Rechte vorhanden und aktiv.")
            return True

        else:
            # --- Desktop / Linux / VM ---
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
