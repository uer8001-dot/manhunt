[app]

# ── Temel Bilgiler ────────────────────────────────────────────────────────────
title        = Manhunt Battle Royale
package.name = manhuntbattleroyale
package.domain = com.yourdomain

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0.0

# ── Bağımlılıklar (Requirements) ──────────────────────────────────────────────
requirements = python3==3.11.0,kivy==2.3.0,kivymd==1.2.0,plyer,requests,urllib3,certifi,idna,charset-normalizer,pillow

# ── Android İzinleri ──────────────────────────────────────────────────────────
android.permissions = android.permission.ACCESS_FINE_LOCATION,android.permission.ACCESS_COARSE_LOCATION,android.permission.INTERNET,android.permission.VIBRATE,android.permission.ACCESS_NETWORK_STATE

# ── Android SDK / NDK ─────────────────────────────────────────────────────────
android.minapi    = 21
android.ndk       = 25b
android.sdk       = 33
android.ndk_api   = 21
android.arch      = arm64-v8a

# ── Buildozer Ayarları ────────────────────────────────────────────────────────
[buildozer]
log_level = 2
warn_on_root = 1
