# =============================================================================
# REAL-LIFE MANHUNT & BATTLE ROYALE ZONE
# Python 3 + Kivy + KivyMD + Firebase REST API + plyer GPS
# =============================================================================

import math
import threading
import time
import webbrowser
import json

import requests
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    NumericProperty,
    StringProperty,
    BooleanProperty,
    ObjectProperty,
)
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.snackbar import MDSnackbar

# =============================================================================
# FIREBASE YAPILANDIRMASI
# Kendi Firebase projenizin bilgilerini buraya girin.
# Firebase Console → Proje Ayarları → Web API Anahtarı
# =============================================================================
FIREBASE_BASE_URL = "https://manhunt-6f475-default-rtdb.firebaseio.com/game.json"
# Örnek: "https://manhunt-game-12345-default-rtdb.firebaseio.com"

RUNNER_NODE  = "/game/runner.json"
HUNTER_NODE  = "/game/hunter.json"
ZONE_NODE    = "/game/zone.json"

# =============================================================================
# OYUN SABİTLERİ
# =============================================================================
ZONE_SHRINK_INTERVAL   = 180        # saniye (3 dakika)
ZONE_SHRINK_FACTOR     = 0.75       # her döngüde %25 küçül
ZONE_INITIAL_RADIUS_M  = 500.0      # başlangıç yarıçapı (metre)
GPS_UPDATE_INTERVAL    = 10.0       # saniye — Firebase güncelleme periyodu
HAVERSINE_EARTH_RADIUS = 6_371_000  # Dünya yarıçapı metre


# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """İki GPS koordinatı arasındaki düzlem mesafeyi metre cinsinden döndürür."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return 2 * HAVERSINE_EARTH_RADIUS * math.asin(math.sqrt(a))


def vibrate(duration_ms: int = 500) -> None:
    """Cihazı titreştir; Android dışı platformlarda sessizce geç."""
    try:
        from plyer import vibrator
        vibrator.vibrate(duration_ms / 1000.0)
    except Exception:
        pass  # masaüstü/emülatör için sessiz geç


def firebase_put(node: str, data: dict) -> bool:
    """Firebase REST PUT isteği. Başarı durumunda True döner."""
    try:
        url = FIREBASE_BASE_URL + node
        resp = requests.put(url, json=data, timeout=8)
        return resp.status_code == 200
    except Exception:
        return False


def firebase_get(node: str) -> dict | None:
    """Firebase REST GET isteği. Veri dict'ini veya None döner."""
    try:
        url = FIREBASE_BASE_URL + node
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


# =============================================================================
# KV ARAYÜZ TANIMI
# =============================================================================
KV = """
#:import dp kivy.metrics.dp

<RoleScreen>:
    name: "role"
    MDBoxLayout:
        orientation: "vertical"
        padding: dp(32)
        spacing: dp(24)

        MDLabel:
            text: "🏹 MANHUNT"
            halign: "center"
            font_style: "H3"
            theme_text_color: "Primary"
            size_hint_y: None
            height: dp(72)

        MDLabel:
            text: "Battle Royale Zone"
            halign: "center"
            font_style: "H5"
            theme_text_color: "Secondary"
            size_hint_y: None
            height: dp(48)

        Widget:
            size_hint_y: None
            height: dp(32)

        MDLabel:
            text: "Rolünü Seç"
            halign: "center"
            font_style: "H6"
            theme_text_color: "Hint"
            size_hint_y: None
            height: dp(40)

        MDRaisedButton:
            id: runner_btn
            text: "🏃  RUNNER  (Kaçan)"
            pos_hint: {"center_x": .5}
            size_hint_x: .85
            height: dp(60)
            font_size: "18sp"
            md_bg_color: app.theme_cls.primary_color
            on_release: root.select_role("runner")

        MDRaisedButton:
            id: hunter_btn
            text: "🎯  HUNTER  (Avcı)"
            pos_hint: {"center_x": .5}
            size_hint_x: .85
            height: dp(60)
            font_size: "18sp"
            md_bg_color: 1, 0.3, 0.1, 1
            on_release: root.select_role("hunter")

        Widget:

<GameScreen>:
    name: "game"

    MDBoxLayout:
        orientation: "vertical"
        padding: dp(16)
        spacing: dp(10)

        # ── Üst başlık ──────────────────────────────────────────────────
        MDCard:
            padding: dp(12)
            radius: [dp(12)]
            md_bg_color: app.theme_cls.bg_dark
            size_hint_y: None
            height: dp(72)

            MDBoxLayout:
                orientation: "horizontal"
                spacing: dp(8)

                MDLabel:
                    id: role_label
                    text: "ROL: —"
                    font_style: "H6"
                    theme_text_color: "Primary"
                    size_hint_x: .5

                MDLabel:
                    id: timer_label
                    text: "Alan Küçülmesine: —"
                    halign: "right"
                    font_style: "Body1"
                    theme_text_color: "Secondary"
                    size_hint_x: .5

        # ── Bölge bilgisi ────────────────────────────────────────────────
        MDCard:
            padding: dp(12)
            radius: [dp(12)]
            md_bg_color: app.theme_cls.bg_dark
            size_hint_y: None
            height: dp(56)

            MDLabel:
                id: zone_label
                text: "🔵 Güvenli Alan Yarıçapı: 500 m"
                halign: "center"
                font_style: "Body1"
                theme_text_color: "Secondary"

        # ── Durum kartı ──────────────────────────────────────────────────
        MDCard:
            id: status_card
            padding: dp(20)
            radius: [dp(16)]
            md_bg_color: app.theme_cls.bg_dark
            size_hint_y: None
            height: dp(120)

            MDLabel:
                id: status_label
                text: "GPS bekleniyor..."
                halign: "center"
                valign: "middle"
                font_style: "H5"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1

        # ── Koordinat bilgisi ────────────────────────────────────────────
        MDCard:
            padding: dp(12)
            radius: [dp(12)]
            md_bg_color: app.theme_cls.bg_dark
            size_hint_y: None
            height: dp(80)

            MDBoxLayout:
                orientation: "vertical"
                spacing: dp(4)

                MDLabel:
                    id: my_loc_label
                    text: "📍 Konumun: —"
                    font_style: "Caption"
                    theme_text_color: "Hint"

                MDLabel:
                    id: center_label
                    text: "🎯 Merkez: —"
                    font_style: "Caption"
                    theme_text_color: "Hint"

                MDLabel:
                    id: target_label
                    text: ""
                    font_style: "Caption"
                    theme_text_color: "Hint"

        # ── Firebase durumu ──────────────────────────────────────────────
        MDLabel:
            id: sync_label
            text: "☁️ Senkronizasyon bekleniyor..."
            halign: "center"
            font_style: "Caption"
            theme_text_color: "Hint"
            size_hint_y: None
            height: dp(24)

        Widget:

        # ── Harita butonu ────────────────────────────────────────────────
        MDRaisedButton:
            id: map_btn
            text: "🗺️  Haritada Göster"
            pos_hint: {"center_x": .5}
            size_hint_x: .9
            height: dp(52)
            font_size: "16sp"
            on_release: root.open_map()

        # ── Yeniden Başla ────────────────────────────────────────────────
        MDFlatButton:
            text: "Ana Menüye Dön"
            pos_hint: {"center_x": .5}
            on_release: root.go_home()
"""


# =============================================================================
# EKRANLAR
# =============================================================================

class RoleScreen(MDScreen):
    """Rol seçim ekranı."""

    def select_role(self, role: str) -> None:
        app = MDApp.get_running_app()
        app.role = role
        app.start_game()


class GameScreen(MDScreen):
    """Ana oyun ekranı — GPS, Zone, Firebase, Haversine."""

    # ── State ──────────────────────────────────────────────────────────
    role: str             = ""
    center_lat: float     = 0.0
    center_lng: float     = 0.0
    my_lat: float         = 0.0
    my_lng: float         = 0.0
    target_lat: float     = 0.0
    target_lng: float     = 0.0
    zone_radius: float    = ZONE_INITIAL_RADIUS_M
    zone_countdown: int   = ZONE_SHRINK_INTERVAL
    gps_ready: bool       = False
    _gps_event            = None
    _zone_event           = None
    _firebase_event       = None

    # ── Başlatma ────────────────────────────────────────────────────────

    def setup(self, role: str) -> None:
        """GameScreen kurulumunu yapar; role atanır, GPS/zamanlayıcılar başlar."""
        self.role = role
        self.zone_radius    = ZONE_INITIAL_RADIUS_M
        self.zone_countdown = ZONE_SHRINK_INTERVAL
        self.gps_ready      = False

        # Rol etiketi
        role_text = "🏃 RUNNER (Kaçan)" if role == "runner" else "🎯 HUNTER (Avcı)"
        self.ids.role_label.text = f"ROL: {role_text}"

        # Zone etiketi
        self._update_zone_label()

        # GPS başlat
        self._start_gps()

        # Zamanlayıcılar
        self._zone_event     = Clock.schedule_interval(self._zone_tick,     1.0)
        self._firebase_event = Clock.schedule_interval(self._firebase_sync, GPS_UPDATE_INTERVAL)
        self._gps_event      = Clock.schedule_interval(self._check_gps_fallback, 2.0)

    def cleanup(self) -> None:
        """Ekrandan çıkarken tüm zamanlayıcıları durdur ve GPS'i kapat."""
        for ev in (self._zone_event, self._firebase_event, self._gps_event):
            if ev:
                ev.cancel()
        self._stop_gps()

    # ── GPS ─────────────────────────────────────────────────────────────

    def _start_gps(self) -> None:
        try:
            from plyer import gps
            gps.configure(on_location=self._on_gps_location, on_status=self._on_gps_status)
            gps.start(minTime=5000, minDistance=0)
        except Exception as exc:
            self._set_sync("⚠️ GPS başlatılamadı: " + str(exc))

    def _stop_gps(self) -> None:
        try:
            from plyer import gps
            gps.stop()
        except Exception:
            pass

    def _on_gps_location(self, **kwargs) -> None:
        """plyer GPS konumu geri çağrımı — ana thread'de güvenle çağrılır."""
        lat = kwargs.get("lat") or kwargs.get("latitude", 0.0)
        lng = kwargs.get("lon") or kwargs.get("longitude", 0.0)
        Clock.schedule_once(lambda dt: self._update_location(lat, lng), 0)

    def _on_gps_status(self, stype: str, status: str) -> None:
        Clock.schedule_once(
            lambda dt: self._set_sync(f"📡 GPS Durumu: {stype} — {status}"), 0
        )

    def _check_gps_fallback(self, dt) -> None:
        """GPS gelmezse 10 saniye sonra fake konum yükle (masaüstü testleri için)."""
        if not self.gps_ready:
            if platform not in ("android", "ios"):
                # Masaüstü/emülatörde: İstanbul koordinatlarını simüle et
                self._update_location(41.0082, 28.9784)

    def _update_location(self, lat: float, lng: float) -> None:
        """Konum güncelleme — tüm hesaplamalar burada."""
        self.my_lat, self.my_lng = lat, lng

        if not self.gps_ready:
            # İlk konum = oyun merkezi
            self.gps_ready   = True
            self.center_lat  = lat
            self.center_lng  = lng
            self._set_center_label()
            self._gps_event.cancel()   # fallback kontrolünü durdur
            self._set_sync("✅ GPS hazır — oyun başladı!")

        self.ids.my_loc_label.text = (
            f"📍 Konumun: {lat:.6f}, {lng:.6f}"
        )
        self._check_game_status()

    # ── Alan (Zone) Mekaniği ────────────────────────────────────────────

    def _zone_tick(self, dt) -> None:
        """Her saniye bir kez çağrılır; sayacı günceller ve alanı küçültür."""
        self.zone_countdown -= 1
        mins = self.zone_countdown // 60
        secs = self.zone_countdown % 60
        self.ids.timer_label.text = f"Alan Küçülmesine: {mins:02d}:{secs:02d}"

        if self.zone_countdown <= 0:
            self.zone_radius    = max(10, self.zone_radius * ZONE_SHRINK_FACTOR)
            self.zone_countdown = ZONE_SHRINK_INTERVAL
            self._update_zone_label()
            vibrate(800)
            self._notify_zone_shrink()
            self._push_zone_to_firebase()

    def _update_zone_label(self) -> None:
        self.ids.zone_label.text = (
            f"🔵 Güvenli Alan Yarıçapı: {self.zone_radius:.0f} m"
        )

    def _notify_zone_shrink(self) -> None:
        try:
            MDSnackbar(
                MDLabel(text=f"⚠️ Alan küçüldü! Yeni yarıçap: {self.zone_radius:.0f} m"),
                y=dp(24),
                pos_hint={"center_x": .5},
                size_hint_x=.9,
                duration=3,
            ).open()
        except Exception:
            pass

    def _push_zone_to_firebase(self) -> None:
        def _push():
            firebase_put(ZONE_NODE, {
                "radius": self.zone_radius,
                "timestamp": time.time(),
            })
        threading.Thread(target=_push, daemon=True).start()

    # ── Firebase Senkronizasyonu ────────────────────────────────────────

    def _firebase_sync(self, dt) -> None:
        """GPS_UPDATE_INTERVAL saniyede bir Firebase ile konuşur."""
        if not self.gps_ready:
            return
        if self.role == "runner":
            threading.Thread(target=self._push_runner_location, daemon=True).start()
        else:
            threading.Thread(target=self._fetch_runner_location, daemon=True).start()

    def _push_runner_location(self) -> None:
        success = firebase_put(RUNNER_NODE, {
            "lat": self.my_lat,
            "lng": self.my_lng,
            "timestamp": time.time(),
        })
        msg = "☁️ Konum Firebase'e gönderildi ✅" if success else "☁️ Firebase gönderilemedi ⚠️"
        Clock.schedule_once(lambda dt: self._set_sync(msg), 0)

    def _fetch_runner_location(self) -> None:
        data = firebase_get(RUNNER_NODE)
        if data and "lat" in data and "lng" in data:
            lat, lng = float(data["lat"]), float(data["lng"])
            Clock.schedule_once(
                lambda dt: self._update_target(lat, lng), 0
            )
            Clock.schedule_once(
                lambda dt: self._set_sync("☁️ Runner konumu alındı ✅"), 0
            )
        else:
            Clock.schedule_once(
                lambda dt: self._set_sync("☁️ Runner verisi bulunamadı ⚠️"), 0
            )

    def _update_target(self, lat: float, lng: float) -> None:
        self.target_lat = lat
        self.target_lng = lng
        self.ids.target_label.text = (
            f"🎯 Runner Konumu: {lat:.6f}, {lng:.6f}"
        )
        self._check_game_status()

    # ── Oyun Durum Kontrolü ─────────────────────────────────────────────

    def _check_game_status(self) -> None:
        if not self.gps_ready:
            return

        status_lbl  = self.ids.status_label
        status_card = self.ids.status_card

        if self.role == "runner":
            dist = haversine(
                self.my_lat, self.my_lng,
                self.center_lat, self.center_lng
            )
            if dist > self.zone_radius:
                status_lbl.text        = f"⚠️ ALAN DIŞINDASIN!\nELENDİN!\n({dist:.0f} m)"
                status_lbl.text_color  = (1, 0.15, 0.15, 1)
                status_card.md_bg_color = (0.5, 0.05, 0.05, 1)
                vibrate(1000)
            else:
                remaining = self.zone_radius - dist
                status_lbl.text        = f"✅ Güvenli Alandasın\n{dist:.0f} m merkeze\n({remaining:.0f} m payın var)"
                status_lbl.text_color  = (0.2, 0.9, 0.3, 1)
                status_card.md_bg_color = (0.05, 0.3, 0.1, 1)

        else:  # hunter
            if self.target_lat == 0.0 and self.target_lng == 0.0:
                status_lbl.text       = "🔍 Runner bekleniyor..."
                status_lbl.text_color = (1, 1, 1, 1)
                return
            dist = haversine(
                self.my_lat, self.my_lng,
                self.target_lat, self.target_lng
            )
            if dist < 20:
                status_lbl.text        = f"🔥 YAKALADIN!\n{dist:.0f} m mesafede!"
                status_lbl.text_color  = (1, 0.6, 0, 1)
                status_card.md_bg_color = (0.5, 0.25, 0, 1)
                vibrate(1200)
            elif dist < 100:
                status_lbl.text        = f"🎯 Runner Yakın!\n{dist:.0f} m"
                status_lbl.text_color  = (1, 0.85, 0.2, 1)
                status_card.md_bg_color = (0.4, 0.3, 0.0, 1)
            else:
                status_lbl.text        = f"🎯 Runner'ın Uzaklığı:\n{dist:.0f} m"
                status_lbl.text_color  = (0.6, 0.85, 1, 1)
                status_card.md_bg_color = app_instance.theme_cls.bg_dark

    # ── Yardımcılar ─────────────────────────────────────────────────────

    def _set_sync(self, text: str) -> None:
        self.ids.sync_label.text = text

    def _set_center_label(self) -> None:
        self.ids.center_label.text = (
            f"🎯 Merkez: {self.center_lat:.6f}, {self.center_lng:.6f}"
        )

    def open_map(self) -> None:
        """Haritada hedef veya kendi konumunu aç."""
        if self.role == "hunter" and (self.target_lat or self.target_lng):
            url = (
                f"https://www.google.com/maps/dir/"
                f"{self.my_lat},{self.my_lng}/"
                f"{self.target_lat},{self.target_lng}"
            )
        else:
            url = (
                f"https://www.google.com/maps/search/?api=1"
                f"&query={self.my_lat},{self.my_lng}"
            )
        webbrowser.open(url)

    def go_home(self) -> None:
        self.cleanup()
        MDApp.get_running_app().root.current = "role"


# Uygulama nesnesine global erişim (status_card bg güncelleme için)
app_instance = None


# =============================================================================
# UYGULAMA
# =============================================================================

class ManhuntApp(MDApp):
    role: str = ""

    def build(self):
        global app_instance

        # Dark mode + Material renk şeması
        self.theme_cls.theme_style    = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.accent_palette  = "Red"

        Builder.load_string(KV)

        sm = MDScreenManager()
        sm.add_widget(RoleScreen(name="role"))
        sm.add_widget(GameScreen(name="game"))

        app_instance = self
        return sm

    def start_game(self) -> None:
        """Rol seçildikten sonra oyun ekranını kurar ve geçiş yapar."""
        game_screen: GameScreen = self.root.get_screen("game")
        game_screen.setup(self.role)
        self.root.current = "game"


# =============================================================================
# GİRİŞ NOKTASI
# =============================================================================
if __name__ == "__main__":
    ManhuntApp().run()
