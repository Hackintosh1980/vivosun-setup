[app]
title = VIVOSUN Reader
package.name = vivosunreader
package.domain = org.hackintosh1980
source.dir = .
source.include_exts = py,png,jpg,kv,json,ttf

version = 1.1
package.version = 1
package.version_code = 1

icon.filename = Logo.png
presplash.filename = Logo.png
orientation = landscape
fullscreen = 1

requirements = python3,kivy,pyjnius,pillow,certifi,six,bleak

android.add_src = src/main/java/

# -------------------------------------------------
# Android permissions (BLE-Scan + Standort + Speicher)
android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, ACCESS_BACKGROUND_LOCATION, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# -------------------------------------------------
# Build-Targets
# -------------------------------------------------
android.api = 33
android.minapi = 33
android.ndk_api = 33
android.debug = True
android.archs = arm64-v8a

# -------------------------------------------------
# SDK/NDK Paths (lokal)
# -------------------------------------------------
android.sdk_path = /home/domi/.buildozer/android/platform/android-sdk
android.ndk_path = /home/domi/.buildozer/android/platform/android-ndk-r28c

# -------------------------------------------------
# Gradle / p4a Settings
# -------------------------------------------------
p4a.source_dir = ~/python-for-android
p4a.build_threads = 6
p4a.extra_args = --allow-minsdk-ndkapi-mismatch
android.gradle_dependencies = com.android.support:support-v4:28.0.0, com.google.android.material:material:1.9.0
android.gradle_version = 8.0.2
android.build_tools_version = 34.0.0
