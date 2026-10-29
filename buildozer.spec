[app]
title = YT Loader
package.name = ytloader
package.domain = org.ytloader
source.dir = .
source.include_exts = py,png,jpg,kv
version = 0.1
requirements = python3,kivy==2.3.0,pyjnius,android,openssl,certifi,yt-dlp
orientation = portrait
fullscreen = 0
services = downloader:service.py:foreground
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC,POST_NOTIFICATIONS,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
