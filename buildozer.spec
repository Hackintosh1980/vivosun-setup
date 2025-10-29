[app]
title = VIVOSUN Dummy
package.name = dummyreader
package.domain = org.hackintosh1980

source.include_exts = py,kv,png,jpg,json,ttf
include_patterns = garden/**/*

version = 1.1
package.version = 1
package.version_code = 1

icon.filename = Logo.png
presplash.filename = Logo.png
orientation = landscape
fullscreen = 1



requirements = python3,kivy,pyjnius,pillow,certifi,six
source.dir = .
source.include_dirs = garden
garden_requirements =
# KEIN garden_requirements verwenden



android.add_src = src/main/java

android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, ACCESS_BACKGROUND_LOCATION, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

android.api = 33
android.minapi = 29
android.ndk_api = 29
android.debug = True
android.archs = arm64-v8a

android.sdk_path = /home/domi/.buildozer/android/platform/android-sdk
android.ndk_path = /home/domi/.buildozer/android/platform/android-ndk-r28c

p4a.source_dir = ~/python-for-android
p4a.build_threads = 6
p4a.extra_args = --allow-minsdk-ndkapi-mismatch
android.gradle_dependencies = com.android.support:support-v4:28.0.0, com.google.android.material:material:1.9.0
android.gradle_version = 8.0.2
android.build_tools_version = 34.0.0
