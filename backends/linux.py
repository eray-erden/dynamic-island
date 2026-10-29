# -*- coding: utf-8 -*-
"""
Linux Backend Implementation for Dynamic Island.
Handles MPRIS (D-Bus), PulseAudio/PipeWire (pactl), and X11/FreeDesktop launchers.
"""

import subprocess
import psutil
from typing import Dict, Any, Tuple, List

try:
    import dbus
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False

from .base import BaseBackend


class LinuxBackend(BaseBackend):
    def __init__(self):
        self._bus = None
        if HAS_DBUS:
            try:
                self._bus = dbus.SessionBus()
            except Exception:
                self._bus = None

    def get_media_info(self) -> Dict[str, Any]:
        empty = {
            "player": None, "title": "Medya Çalınmıyor", "artist": "Opera / Spotify açık değil",
            "status": "Stopped", "trackid": "", "length": 0, "position": 0, "art_url": ""
        }
        if not HAS_DBUS:
            return empty

        try:
            if not self._bus:
                self._bus = dbus.SessionBus()

            players = [n for n in self._bus.list_names() if n.startswith("org.mpris.MediaPlayer2")]
            if not players:
                return empty

            player_name = players[0]
            player_obj = self._bus.get_object(player_name, "/org/mpris/MediaPlayer2")
            props = dbus.Interface(player_obj, "org.freedesktop.DBus.Properties")

            status = str(props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus"))
            meta = props.Get("org.mpris.MediaPlayer2.Player", "Metadata")
            title = str(meta.get("xesam:title", "Bilinmeyen Başlık"))
            artists = meta.get("xesam:artist", ["Bilinmeyen"])
            artist = str(artists[0] if artists else "Bilinmeyen")
            trackid = str(meta.get("mpris:trackid", ""))
            length_us = int(meta.get("mpris:length", 0))
            art_url = str(meta.get("mpris:artUrl", ""))

            pos_us = 0
            try:
                pos_us = int(props.Get("org.mpris.MediaPlayer2.Player", "Position"))
            except Exception:
                pass

            return {
                "player": player_name,
                "title": title,
                "artist": artist,
                "status": status,
                "trackid": trackid,
                "length": length_us,
                "position": pos_us,
                "art_url": art_url
            }
        except Exception:
            return empty

    def send_media_command(self, cmd: str) -> None:
        if not HAS_DBUS:
            return
        try:
            if not self._bus:
                self._bus = dbus.SessionBus()
            players = [n for n in self._bus.list_names() if n.startswith("org.mpris.MediaPlayer2")]
            if players:
                player_obj = self._bus.get_object(players[0], "/org/mpris/MediaPlayer2")
                player_iface = dbus.Interface(player_obj, "org.mpris.MediaPlayer2.Player")
                getattr(player_iface, cmd)()
        except Exception as e:
            print("Linux media command error:", e)

    def set_media_position(self, pos_us: int) -> None:
        if not HAS_DBUS:
            return
        try:
            if not self._bus:
                self._bus = dbus.SessionBus()
            players = [n for n in self._bus.list_names() if n.startswith("org.mpris.MediaPlayer2")]
            if players:
                player_obj = self._bus.get_object(players[0], "/org/mpris/MediaPlayer2")
                props = dbus.Interface(player_obj, "org.freedesktop.DBus.Properties")
                meta = props.Get("org.mpris.MediaPlayer2.Player", "Metadata")
                trackid = str(meta.get("mpris:trackid", ""))
                if trackid:
                    player_iface = dbus.Interface(player_obj, "org.mpris.MediaPlayer2.Player")
                    player_iface.SetPosition(trackid, dbus.Int64(pos_us))
        except Exception as e:
            print("Linux seek error:", e)

    def get_volume(self) -> int:
        try:
            out = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], text=True)
            for part in out.split():
                if part.endswith("%"):
                    return int(part.replace("%", ""))
        except Exception:
            pass
        return 50

    def set_volume(self, val: int) -> None:
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{val}%"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def get_network_status(self) -> Tuple[str, str]:
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            for iface, stat in stats.items():
                if iface.startswith("lo") or iface.startswith("lxc") or not stat.isup:
                    continue
                has_ip = any(a.family == 2 for a in addrs.get(iface, []))
                if has_ip:
                    if iface.startswith("wl") or "wifi" in iface:
                        return ("wifi", f"İnternet: Wi-Fi ({iface})")
                    else:
                        return ("lan", f"İnternet: Kablolu Ağ / LAN ({iface})")
        except Exception:
            pass
        return ("off", "İnternet: Bağlantı Yok")

    def get_quick_apps(self) -> List[Tuple[str, str, str]]:
        return [
            ("Ara", "system-search", "rofi -show drun -show-icons -theme Arc-Dark"),
            ("Opera", "opera", "opera"),
            ("Terminal", "utilities-terminal", "xfce4-terminal"),
            ("Dosyalar", "system-file-manager", "thunar")
        ]

    def launch_app(self, cmd: str) -> None:
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            print("Launch app error:", e)
