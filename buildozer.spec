[app]
# -------------------------------------------------
title = VIVOSUN Bridge Test
package.name = vivosunreader
package.domain = org.hackintosh1980
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,ico,json,txt,ttf,mp3,mp4,ogg,wav,svg
main.py = main.py
icon.filename = Logo.png
presplash.filename = Logo.png
orientation = landscape
fullscreen = 1

# -------------------------------------------------
# BLE-Scan + Android 10-kompatibel
requirements = python3,kivy,bleak,pyjnius,android,sdl2,pillow,certifi

# 👆 bleak hinzufügen (Pflicht für BLE-Scanning!)
# (ohne bleak nutzt dein Code zwar pyjnius, aber nicht das Python-BLE-Interface)

# -------------------------------------------------
version = 1.1
package.version = 1
package.version_code = 1


# Java-Quellcode ins APK einbauen
android.add_src = src/main/java/


# -------------------------------------------------
# -------------------------------------------------
# Android permissions (BLE-Scan + Standort + Speicher)
android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, ACCESS_BACKGROUND_LOCATION, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
# -------------------------------------------------
# API-Kombination → stabil unter Colab / Android 10-Geräten
android.api = 33
android.minapi = 33
android.ndk_api = 33
android.archs = arm64-v8a
android.debug = True

android.sdk_path = /home/domi/.buildozer/android/platform/android-sdk
android.ndk_path = /home/domi/.buildozer/android/platform/android-ndk-r28c
#android.manifest_path = ./src/main/AndroidManifest.tmpl.xml
# -------------------------------------------------
# Gradle + p4a
p4a.source_dir = ~/python-for-android
p4a.build_threads = 6
p4a.extra_args = --allow-minsdk-ndkapi-mismatch
android.gradle_dependencies = com.android.support:support-v4:28.0.0, com.google.android.material:material:1.9.0
android.gradle_version = 8.0.2
android.build_tools_version = 34.0.0

[buildozer]
log_level = 2
warn_on_root = 1
