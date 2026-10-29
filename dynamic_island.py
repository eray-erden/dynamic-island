#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apple Dynamic Island (Dinamik Ada) for Linux / XFCE
Ultra-lightweight, 60fps smooth PyQt5 desktop widget.
Flushed to screen top (0px), flat top corners, curved bottom corners.
Fixed width notch with drop-down drawer, live sound wave equalizer,
album art thumbnail, ambient glow border, seek bar, volume, and color app dock.
"""

import sys
import os
import subprocess
import psutil
import math
import urllib.request
from urllib.parse import urlparse, unquote
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QSlider, QMenu, QAction, QFrame
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QSize
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath, QGuiApplication,
    QFont, QPixmap, QImage, QLinearGradient, QIcon
)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, "icons")

from backends import get_backend


class SoundWave(QWidget):
    """Müzik çaldığında dalgalanan Apple/Spotify tarzı dinamik ekolayzer dalgası"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 16)
        self.is_playing = False
        self.tick = 0
        self.bars = [0.3, 0.7, 0.5, 0.85]

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(75)
        self.anim_timer.timeout.connect(self._step)

    def set_playing(self, playing):
        if self.is_playing != playing:
            self.is_playing = playing
            if playing:
                self.setVisible(True)
                self.anim_timer.start()
            else:
                self.anim_timer.stop()
                self.setVisible(False)
                self.update()

    def _step(self):
        self.tick += 1
        self.bars[0] = 0.25 + 0.65 * abs(math.sin(self.tick * 0.38))
        self.bars[1] = 0.20 + 0.75 * abs(math.sin(self.tick * 0.52 + 1.1))
        self.bars[2] = 0.25 + 0.70 * abs(math.sin(self.tick * 0.34 + 2.1))
        self.bars[3] = 0.20 + 0.72 * abs(math.sin(self.tick * 0.58 + 0.6))
        self.update()

    def paintEvent(self, event):
        if not self.is_playing:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor("#10B981")))  # Canlı Yeşil (Apple Music / Spotify Stili)
        p.setPen(Qt.NoPen)

        w = self.width()
        h = self.height()
        bar_w = 2.5
        gap = 2.0
        start_x = (w - (4 * bar_w + 3 * gap)) / 2.0

        for i, val in enumerate(self.bars):
            bh = max(3.0, h * val)
            bx = start_x + i * (bar_w + gap)
            by = (h - bh) / 2.0
            p.drawRoundedRect(QRectF(bx, by, bar_w, bh), 1.2, 1.2)


class DynamicIsland(QWidget):
    # Tipografi: Apple SF Pro Display (Birincil) + Inter (Modern UI Yedeği)
    UI_FONT = "'SF Pro Display', 'Inter', -apple-system, sans-serif"
    MONO_FONT = UI_FONT

    # Sabit Genişlik & Yükseklik Değerleri (Göz Alıcı & Okunaklı Boyutlar)
    ISLAND_W = 420
    IDLE_H = 36
    EXP_H = 170
    TOP_Y = 0  # Tam ekrana yapışık (0 px)

    def __init__(self):
        super().__init__(None, Qt.Window)
        self.setWindowTitle("Dynamic Island")

        screen = QGuiApplication.primaryScreen().geometry()
        self.screen_w = screen.width()
        self.screen_h = screen.height()

        # Tool penceresi: Görev çubuğunda görünmez, pencerelerin üstünde kalır
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._progress = 0.0
        self.is_expanded = False
        self.is_seeking = False
        self.current_media = {
            "player": None, "title": "", "artist": "", "status": "Stopped",
            "trackid": "", "length": 0, "position": 0, "art_url": ""
        }
        self.backend = get_backend()
        self.volume_val = self.backend.get_volume()

        # Animasyon motoru: 0.0 (Idle) -> 1.0 (Expanded)
        self.anim = QPropertyAnimation(self, b"progress")
        self.anim.setDuration(240)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        # Kapanma geciktirme zamanlayıcısı (kullanıcı fareyi çekince hemen kapanmasın)
        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.setInterval(400)
        self.collapse_timer.timeout.connect(self.collapse_island)

        # Periyodik sistem & medya kontrol zamanlayıcısı (1 saniye)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(1000)
        self.update_timer.timeout.connect(self.on_periodic_update)

        self.init_ui()

        # İlk konumlandırma (tam ortalı, y=0)
        x = (self.screen_w - self.ISLAND_W) // 2
        self.setGeometry(x, self.TOP_Y, self.ISLAND_W, self.IDLE_H)
        self.update_timer.start()

    @pyqtProperty(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, val):
        self._progress = val
        h = int(self.IDLE_H + (self.EXP_H - self.IDLE_H) * val)
        self.setFixedHeight(h)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        x = (self.screen_w - self.ISLAND_W) // 2
        self.move(x, self.TOP_Y)

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 6, 15, 8)
        self.main_layout.setSpacing(5)

        # ==========================================
        # 1. ÜST HEADER BAR (Idle & Açıkken Ortak Başlık)
        # ==========================================
        self.header_widget = QWidget(self)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        # Sol taraf: Durum noktası + Bağlantı Simgesi (Wi-Fi / LAN) + Canlı Ses Dalgası
        left_box = QHBoxLayout()
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(7)

        self.dot_label = QLabel("●")
        self.dot_label.setStyleSheet("color: #10B981; font-size: 10px;")

        self.net_icon_label = QLabel()
        self.net_icon_label.setToolTip("İnternet Bağlantısı")

        self.sound_wave = SoundWave(self)
        self.sound_wave.setVisible(False)

        left_box.addWidget(self.dot_label)
        left_box.addWidget(self.net_icon_label)
        left_box.addWidget(self.sound_wave)
        left_box.addStretch()

        # Orta: Tam Ortalanmış Saat (Büyük & Belirgin Monospace)
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"color: #FFFFFF; font-weight: bold; font-size: 14px; font-family: {self.MONO_FONT};")
        self.clock_label.setAlignment(Qt.AlignCenter)

        # Sağ taraf: Tarih (Okunaklı Monospace)
        right_box = QHBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(7)

        self.date_label = QLabel()
        self.date_label.setStyleSheet(f"color: #9CA3AF; font-size: 11.5px; font-weight: 500; font-family: {self.MONO_FONT};")
        right_box.addStretch()
        right_box.addWidget(self.date_label)

        header_layout.addLayout(left_box, 1)
        header_layout.addWidget(self.clock_label, 0, Qt.AlignCenter)
        header_layout.addLayout(right_box, 1)

        self.main_layout.addWidget(self.header_widget)

        # ==========================================
        # 2. ALT ÇEKMECE / DRAWER (Aşağıya doğru açılan alan)
        # ==========================================
        self.drawer_widget = QWidget(self)
        self.drawer_widget.setVisible(False)
        drawer_layout = QVBoxLayout(self.drawer_widget)
        drawer_layout.setContentsMargins(0, 2, 0, 0)
        drawer_layout.setSpacing(4)

        # İnce Ayrım Çizgisi
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); max-height: 1px;")
        drawer_layout.addWidget(sep)

        # 1. Satır: Medya Çalar (Albüm Kapağı + Şarkı & Sanatçı + Kontroller)
        media_box = QHBoxLayout()
        media_box.setContentsMargins(0, 0, 0, 0)
        media_box.setSpacing(8)

        # Albüm Kapağı Thumbnail
        self.art_label = QLabel()
        self.art_label.setFixedSize(38, 38)
        self.set_default_album_art()
        media_box.addWidget(self.art_label)

        # Şarkı & Sanatçı Başlığı (Monospace)
        track_info = QVBoxLayout()
        track_info.setSpacing(2)
        self.track_title = QLabel("Medya Çalınmıyor")
        self.track_title.setStyleSheet(f"color: #FFFFFF; font-weight: bold; font-size: 11.5px; font-family: {self.MONO_FONT};")
        self.track_artist = QLabel("Opera / Spotify açık değil")
        self.track_artist.setStyleSheet(f"color: #9CA3AF; font-size: 10px; font-family: {self.MONO_FONT};")
        track_info.addWidget(self.track_title)
        track_info.addWidget(self.track_artist)
        media_box.addLayout(track_info, stretch=1)

        # Kontrol Butonları (Özel Vektör Simgeli & Apple Cam Stili)
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(QIcon(os.path.join(ICON_DIR, "media_prev.png")))
        self.btn_prev.setIconSize(QSize(13, 13))
        self.btn_prev.setFixedSize(26, 26)
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.setToolTip("Önceki Şarkı")
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.22);
                border-color: rgba(255, 255, 255, 0.30);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.35);
            }
        """)

        # Oynat/Duraklat (Öne Çıkan Hero Buton)
        self.btn_play = QPushButton()
        self.btn_play.setIcon(QIcon(os.path.join(ICON_DIR, "media_play.png")))
        self.btn_play.setIconSize(QSize(15, 15))
        self.btn_play.setFixedSize(30, 30)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.setToolTip("Oynat / Duraklat")
        self.btn_play.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.28), stop:1 rgba(255, 255, 255, 0.14));
                border: 1.2px solid rgba(255, 255, 255, 0.40);
                border-radius: 15px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 255, 255, 0.45), stop:1 rgba(255, 255, 255, 0.26));
                border-color: rgba(255, 255, 255, 0.75);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.55);
            }
        """)

        self.btn_next = QPushButton()
        self.btn_next.setIcon(QIcon(os.path.join(ICON_DIR, "media_next.png")))
        self.btn_next.setIconSize(QSize(13, 13))
        self.btn_next.setFixedSize(26, 26)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setToolTip("Sonraki Şarkı")
        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.22);
                border-color: rgba(255, 255, 255, 0.30);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.35);
            }
        """)

        self.btn_prev.clicked.connect(lambda: self.send_media_cmd("Previous"))
        self.btn_play.clicked.connect(lambda: self.send_media_cmd("PlayPause"))
        self.btn_next.clicked.connect(lambda: self.send_media_cmd("Next"))

        media_box.addWidget(self.btn_prev)
        media_box.addWidget(self.btn_play)
        media_box.addWidget(self.btn_next)
        drawer_layout.addLayout(media_box)

        # 2. Satır: Şarkı İlerleme (Seek) Çubuğu & Süre
        seek_box = QHBoxLayout()
        seek_box.setContentsMargins(0, 0, 0, 0)
        seek_box.setSpacing(7)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setFixedHeight(10)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 3.5px;
                background: rgba(255, 255, 255, 0.12);
                border-radius: 1.75px;
            }
            QSlider::sub-page:horizontal {
                background: #10B981;
                border-radius: 1.75px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 9px;
                height: 9px;
                margin-top: -2.75px;
                margin-bottom: -2.75px;
                border-radius: 4.5px;
            }
        """)
        self.seek_slider.sliderPressed.connect(self.on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self.on_seek_released)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet(f"color: #9CA3AF; font-size: 9.5px; font-weight: bold; font-family: {self.MONO_FONT};")

        seek_box.addWidget(self.seek_slider, stretch=1)
        seek_box.addWidget(self.time_label)
        drawer_layout.addLayout(seek_box)

        # 3. Satır: Ses Düzeyi Kaydırıcısı + Ada Açılınca CPU & RAM Göstergeleri
        vol_box = QHBoxLayout()
        vol_box.setSpacing(6)
        self.vol_icon = QLabel("🔊")
        self.vol_icon.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self.volume_val)
        self.vol_slider.setFixedHeight(10)
        self.update_volume_slider_style(self.volume_val)
        self.vol_slider.valueChanged.connect(self.set_system_volume)
        vol_box.addWidget(self.vol_icon)
        vol_box.addWidget(self.vol_slider, stretch=1)

        # Ada Açılınca Görünen CPU ve RAM İkonları & Değerleri (Monospace)
        self.cpu_icon_label = QLabel()
        cpu_pix = QPixmap(os.path.join(ICON_DIR, "cpu.png")).scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.cpu_icon_label.setPixmap(cpu_pix)
        self.cpu_icon_label.setToolTip("İşlemci (CPU)")

        self.cpu_val_label = QLabel("%0")
        self.cpu_val_label.setStyleSheet(f"color: #D1D5DB; font-size: 10.5px; font-weight: bold; font-family: {self.MONO_FONT};")
        self.cpu_val_label.setToolTip("İşlemci Kullanımı")

        self.ram_icon_label = QLabel()
        ram_pix = QPixmap(os.path.join(ICON_DIR, "ram.png")).scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ram_icon_label.setPixmap(ram_pix)
        self.ram_icon_label.setToolTip("Bellek (RAM)")

        self.ram_val_label = QLabel("0.0G")
        self.ram_val_label.setStyleSheet(f"color: #D1D5DB; font-size: 10.5px; font-weight: bold; font-family: {self.MONO_FONT};")
        self.ram_val_label.setToolTip("RAM Kullanımı")

        vol_box.addWidget(self.cpu_icon_label)
        vol_box.addWidget(self.cpu_val_label)
        vol_box.addWidget(self.ram_icon_label)
        vol_box.addWidget(self.ram_val_label)

        drawer_layout.addLayout(vol_box)

        # 4. Satır: Gerçek Renkli Sistem Simgeli Hızlı Başlatıcılar (Monospace)
        dock_box = QHBoxLayout()
        dock_box.setContentsMargins(0, 1, 0, 0)
        dock_box.setSpacing(6)

        quick_apps = self.backend.get_quick_apps()

        for label, icon_name, cmd in quick_apps:
            qbtn = QPushButton(f" {label}")
            qbtn.setIcon(QIcon.fromTheme(icon_name))
            qbtn.setIconSize(QSize(13, 13))
            qbtn.setFixedHeight(23)
            qbtn.setCursor(Qt.PointingHandCursor)
            qbtn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(255, 255, 255, 0.06);
                    color: #D1D5DB;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 6px;
                    padding: 0 7px;
                    font-size: 9.5px;
                    font-weight: bold;
                    font-family: {self.MONO_FONT};
                }}
                QPushButton:hover {{
                    background-color: #2563EB;
                    color: white;
                    border-color: #3B82F6;
                }}
            """)
            qbtn.clicked.connect(lambda checked, c=cmd: self.launch_app(c))
            dock_box.addWidget(qbtn)

        drawer_layout.addLayout(dock_box)
        self.main_layout.addWidget(self.drawer_widget)

        # İlk veri çekimi
        self.update_clock_and_date()
        self.update_network_status()
        self.update_system_stats()
        self.update_media_status()

    def set_default_album_art(self):
        art_img = QImage(38, 38, QImage.Format_ARGB32_Premultiplied)
        art_img.fill(Qt.transparent)
        p = QPainter(art_img)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 38, 38)
        grad.setColorAt(0.0, QColor("#8B5CF6"))
        grad.setColorAt(1.0, QColor("#EC4899"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, 38, 38), 7, 7)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 180), 1.0))
        p.drawEllipse(QRectF(7, 7, 24, 24))
        p.drawEllipse(QRectF(13, 13, 12, 12))
        p.setBrush(QBrush(QColor(255, 255, 255, 230)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(16.5, 16.5, 5, 5))
        p.end()
        self.art_label.setPixmap(QPixmap.fromImage(art_img))

    def set_album_art_from_path(self, path):
        try:
            pix = QPixmap(path)
            if not pix.isNull():
                scaled = pix.scaled(38, 38, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                rounded = QImage(38, 38, QImage.Format_ARGB32_Premultiplied)
                rounded.fill(Qt.transparent)
                p = QPainter(rounded)
                p.setRenderHint(QPainter.Antialiasing)
                clip = QPainterPath()
                clip.addRoundedRect(QRectF(0, 0, 38, 38), 7, 7)
                p.setClipPath(clip)
                p.drawPixmap(0, 0, scaled)
                p.end()
                self.art_label.setPixmap(QPixmap.fromImage(rounded))
                return
        except Exception:
            pass
        self.set_default_album_art()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        # Sadece alt köşeler kavisli (r), üst köşeler dümdüz (0)
        # Idle iken r=18 (36px yüksekliğe tam yarım daire kavis), expanded iken r=22
        r = min(18.0 + (22.0 - 18.0) * self._progress, h / 2.0)

        # Gövde Yolu: Üstü düz (0,0 -> w,0), alt köşeler kavisli
        fill_path = QPainterPath()
        fill_path.moveTo(0.0, 0.0)
        fill_path.lineTo(w, 0.0)
        fill_path.lineTo(w, h - r)
        fill_path.arcTo(w - 2.0 * r, h - 2.0 * r, 2.0 * r, 2.0 * r, 0.0, -90.0)
        fill_path.lineTo(r, h)
        fill_path.arcTo(0.0, h - 2.0 * r, 2.0 * r, 2.0 * r, 270.0, -90.0)
        fill_path.closeSubpath()

        # Derin Obsidyen Siyahı
        painter.fillPath(fill_path, QBrush(QColor(11, 11, 15, 252)))

        # Çerçeve Kenarlığı: Sol, alt kavisler ve sağ kenara Ambient Glow
        stroke_path = QPainterPath()
        stroke_path.moveTo(w - 0.5, 0.0)
        stroke_path.lineTo(w - 0.5, h - r)
        stroke_path.arcTo(w - 2.0 * r, h - 2.0 * r, 2.0 * r, 2.0 * r, 0.0, -90.0)
        stroke_path.lineTo(r, h - 0.5)
        stroke_path.arcTo(0.0, h - 2.0 * r, 2.0 * r, 2.0 * r, 270.0, -90.0)
        stroke_path.lineTo(0.5, 0.0)

        # Ambient Glow: Müzik çalarken mor/eflatun şık neon ışıma, durunca klasik ince beyaz
        if self.current_media.get("status") == "Playing":
            pen = QPen(QColor(168, 85, 247, 85), 1.2)
        else:
            pen = QPen(QColor(255, 255, 255, 28), 1.0)

        painter.strokePath(stroke_path, pen)

    def enterEvent(self, event):
        self.collapse_timer.stop()
        if not self.is_expanded:
            self.expand_island()

    def leaveEvent(self, event):
        self.collapse_timer.start()

    def expand_island(self):
        self.is_expanded = True
        self.drawer_widget.setVisible(True)
        self.anim.stop()
        self.anim.setStartValue(self._progress)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def collapse_island(self):
        self.is_expanded = False
        self.anim.stop()
        self.anim.setStartValue(self._progress)
        self.anim.setEndValue(0.0)
        self.anim.start()
        QTimer.singleShot(250, self._finish_collapse)

    def _finish_collapse(self):
        if not self.is_expanded:
            self.drawer_widget.setVisible(False)

    def on_periodic_update(self):
        try:
            self.update_clock_and_date()
            self.update_network_status()
            self.update_system_stats()
            self.update_media_status()
            # Dışarıdan (klavye vs.) gelen ses değişikliklerini yakala
            if not self.vol_slider.isSliderDown():
                curr_vol = self.get_current_volume()
                if curr_vol != self.volume_val:
                    self.volume_val = curr_vol
                    self.vol_slider.blockSignals(True)
                    self.vol_slider.setValue(curr_vol)
                    self.vol_slider.blockSignals(False)
                    self.update_volume_slider_style(curr_vol)
        except Exception:
            pass

    def update_clock_and_date(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M"))
        tr_months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
        tr_days = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        
        day_str = tr_days[now.weekday()]
        month_str = tr_months[now.month - 1]
        self.date_label.setText(f"{now.day} {month_str} {day_str}")

    def update_network_status(self):
        net_type, tooltip = self.backend.get_network_status()
        icon_map = {
            "wifi": "net_wifi.png",
            "lan": "net_lan.png",
            "off": "net_off.png"
        }
        icon_file = icon_map.get(net_type, "net_off.png")
        pix = QPixmap(os.path.join(ICON_DIR, icon_file)).scaled(15, 15, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.net_icon_label.setPixmap(pix)
        self.net_icon_label.setToolTip(tooltip)

    def update_system_stats(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        ram_gb = ram.used / (1024 ** 3)
        self.cpu_val_label.setText(f"%{int(cpu)}")
        self.cpu_val_label.setToolTip(f"İşlemci Kullanımı: %{int(cpu)}")
        self.ram_val_label.setText(f"{ram_gb:.1f}G")
        self.ram_val_label.setToolTip(f"RAM: {ram_gb:.1f}G / {ram.total / (1024 ** 3):.0f}G (%{int(ram.percent)})")

    def update_media_status(self):
        try:
            info = self.backend.get_media_info()
            self.current_media = info
            status = info.get("status", "Stopped")
            title = info.get("title", "Medya Çalınmıyor")
            artist = info.get("artist", "")
            length_us = info.get("length", 0)
            pos_us = info.get("position", 0)
            art_url = info.get("art_url", "")

            short_title = title if len(title) <= 32 else title[:30] + ".."
            self.track_title.setText(short_title)
            self.track_artist.setText(artist if len(artist) <= 34 else artist[:32] + "..")
            icon_file = "media_pause.png" if status == "Playing" else "media_play.png"
            self.btn_play.setIcon(QIcon(os.path.join(ICON_DIR, icon_file)))
            self.sound_wave.set_playing(status == "Playing")

            # Şarkı İlerleme ve Süre Güncelleme
            if length_us > 0:
                pos_sec = pos_us // 1_000_000
                len_sec = length_us // 1_000_000
                if not self.is_seeking:
                    progress_val = int((pos_us / length_us) * 1000)
                    self.seek_slider.setValue(progress_val)
                self.time_label.setText(f"{pos_sec // 60:02d}:{pos_sec % 60:02d} / {len_sec // 60:02d}:{len_sec % 60:02d}")
            else:
                self.time_label.setText("00:00 / 00:00")
                if not self.is_seeking:
                    self.seek_slider.setValue(0)

            # Albüm Kapağı Güncelleme
            if art_url and art_url.startswith("file://"):
                file_path = unquote(urlparse(art_url).path)
                self.set_album_art_from_path(file_path)
            elif art_url and os.path.exists(art_url):
                self.set_album_art_from_path(art_url)
            else:
                self.set_default_album_art()

            self.update()
        except Exception:
            pass

    def on_seek_pressed(self):
        self.is_seeking = True

    def on_seek_released(self):
        self.is_seeking = False
        length_us = self.current_media.get("length", 0)
        if length_us > 0:
            val = self.seek_slider.value() / 1000.0
            target_us = int(length_us * val)
            self.backend.set_media_position(target_us)

    def send_media_cmd(self, cmd):
        self.backend.send_media_command(cmd)
        QTimer.singleShot(150, self.update_media_status)

    def get_current_volume(self):
        return self.backend.get_volume()

    def get_volume_color(self, val):
        """Ses seviyesine göre dinamik neon gradyan:
           %0-%30: Turkuaz / Nane Yeşili (#06B6D4 -> #10B981)
           %30-%60: Elektrik Mavisi (#3B82F6)
           %60-%80: Neon Mor (#A855F7)
           %80-%100: Ateş Kırmızısı / Mercan (#F43F5E)
        """
        stops = [
            (0,   (6,   182, 212)),  # #06B6D4 Turkuaz
            (30,  (16,  185, 129)),  # #10B981 Zümrüt Yeşili
            (60,  (59,  130, 246)),  # #3B82F6 Canlı Mavi
            (80,  (168, 85,  247)),  # #A855F7 Neon Mor
            (100, (244, 63,  94))    # #F43F5E Ateş Mercanı/Kırmızı
        ]
        val = max(0, min(100, val))
        for i in range(len(stops) - 1):
            v0, c0 = stops[i]
            v1, c1 = stops[i+1]
            if v0 <= val <= v1:
                t = (val - v0) / float(v1 - v0) if v1 > v0 else 0
                r = int(c0[0] + (c1[0] - c0[0]) * t)
                g = int(c0[1] + (c1[1] - c0[1]) * t)
                b = int(c0[2] + (c1[2] - c0[2]) * t)
                return f"#{r:02x}{g:02x}{b:02x}"
        return "#F43F5E"

    def update_volume_slider_style(self, val):
        col = self.get_volume_color(val)
        self.vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 3.5px;
                background: rgba(255, 255, 255, 0.12);
                border-radius: 1.75px;
            }}
            QSlider::sub-page:horizontal {{
                background: {col};
                border-radius: 1.75px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                width: 9px;
                height: 9px;
                margin-top: -2.75px;
                margin-bottom: -2.75px;
                border-radius: 4.5px;
            }}
        """)
        self.vol_slider.setToolTip(f"Ses Düzeyi: %{val}")
        if val == 0:
            self.vol_icon.setText("🔇")
        elif val < 40:
            self.vol_icon.setText("🔉")
        else:
            self.vol_icon.setText("🔊")

    def set_system_volume(self, val):
        self.volume_val = val
        self.update_volume_slider_style(val)
        self.backend.set_volume(val)

    def launch_app(self, cmd):
        self.backend.launch_app(cmd)
        self.collapse_island()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            menu = QMenu(self)
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: #111116;
                    color: #F3F4F6;
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 8px;
                    padding: 4px;
                    font-family: {self.MONO_FONT};
                }}
                QMenu::item {{
                    padding: 5px 12px;
                    border-radius: 4px;
                    font-size: 11px;
                }}
                QMenu::item:selected {{
                    background-color: #2563EB;
                }}
            """)
            act_search = QAction("🔍 Spotlight Arama", self)
            act_search.triggered.connect(lambda: self.launch_app("rofi -show drun -show-icons -theme Arc-Dark" if sys.platform != "win32" else "explorer.exe shell:::{2559a160-21d7-11d4-bdaf-00c04f60b9f0}"))
            menu.addAction(act_search)

            if sys.platform != "win32":
                act_toggle_panel = QAction("📌 XFCE Paneli Göster / Gizle", self)
                act_toggle_panel.triggered.connect(self.toggle_xfce_panel)
                menu.addAction(act_toggle_panel)

            menu.addSeparator()
            act_exit = QAction("❌ Dinamik Ada'yı Kapat", self)
            act_exit.triggered.connect(QApplication.instance().quit)
            menu.addAction(act_exit)

            menu.exec_(self.mapToGlobal(event.pos()))
        else:
            if not self.is_expanded:
                self.expand_island()
            else:
                self.collapse_island()

    def toggle_xfce_panel(self):
        try:
            out = subprocess.check_output(["xfconf-query", "-c", "xfce4-panel", "-p", "/panels/panel-1/autohide-behavior"], text=True).strip()
            new_val = "0" if out == "2" else "2"
            subprocess.run(["xfconf-query", "-c", "xfce4-panel", "-p", "/panels/panel-1/autohide-behavior", "-s", new_val])
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DynamicIsland")
    app.setQuitOnLastWindowClosed(False)
    island = DynamicIsland()
    island.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
