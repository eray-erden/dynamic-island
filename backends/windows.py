# -*- coding: utf-8 -*-
"""
Windows Backend Implementation for Dynamic Island.
Handles Windows 10/11 GSMTC (Media Control), Windows Core Audio (pycaw), and Shell Launchers.
"""

import os
import sys
import asyncio
import subprocess
import psutil
from typing import Dict, Any, Tuple, List

# Windows-specific optional imports with graceful fallbacks
HAS_WIN_MEDIA = False
try:
    if sys.platform == "win32":
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus
        )
        from winsdk.windows.storage.streams import DataReader
        HAS_WIN_MEDIA = True
except ImportError:
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus
        )
        HAS_WIN_MEDIA = True
    except ImportError:
        HAS_WIN_MEDIA = False

HAS_PYCAW = False
try:
    if sys.platform == "win32":
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

from .base import BaseBackend


class WindowsBackend(BaseBackend):
    def __init__(self):
        self._loop = None
        self._volume_endpoint = None
        self._init_audio()

    def _init_audio(self):
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._volume_endpoint = cast(interface, POINTER(IAudioEndpointVolume))
            except Exception as e:
                print("Windows audio init error:", e)

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, coro).result(timeout=1.0)
            return loop.run_until_complete(coro)
        except Exception:
            return asyncio.run(coro)

    def get_media_info(self) -> Dict[str, Any]:
        empty = {
            "player": None, "title": "Medya Çalınmıyor", "artist": "Spotify / Tarayıcı açık değil",
            "status": "Stopped", "trackid": "", "length": 0, "position": 0, "art_url": ""
        }
        if not HAS_WIN_MEDIA:
            return empty

        try:
            async def _fetch():
                manager = await MediaManager.request_async()
                session = manager.get_current_session()
                if not session:
                    return empty

                info = session.get_playback_info()
                status_enum = info.playback_status if info else None
                status = "Playing" if status_enum == PlaybackStatus.PLAYING else (
                    "Paused" if status_enum == PlaybackStatus.PAUSED else "Stopped"
                )

                props = await session.try_get_media_properties_async()
                title = props.title if (props and props.title) else "Bilinmeyen Başlık"
                artist = props.artist if (props and props.artist) else "Bilinmeyen Sanatçı"

                timeline = session.get_timeline_properties()
                pos_us = int(timeline.position.total_seconds() * 1_000_000) if (timeline and timeline.position) else 0
                len_us = int(timeline.end_time.total_seconds() * 1_000_000) if (timeline and timeline.end_time) else 0

                art_url = ""
                # Thumbnail stream if present
                if props and props.thumbnail:
                    # Can extract thumbnail stream if needed or save to temp file
                    pass

                app_id = session.source_app_user_model_id or "Media Player"

                return {
                    "player": app_id,
                    "title": title,
                    "artist": artist,
                    "status": status,
                    "trackid": "win_track",
                    "length": len_us,
                    "position": pos_us,
                    "art_url": art_url
                }

            return self._run_async(_fetch())
        except Exception:
            return empty

    def send_media_command(self, cmd: str) -> None:
        if not HAS_WIN_MEDIA:
            return

        async def _send():
            manager = await MediaManager.request_async()
            session = manager.get_current_session()
            if not session:
                return

            if cmd in ("PlayPause", "Toggle"):
                await session.try_toggle_play_pause_async()
            elif cmd == "Play":
                await session.try_play_async()
            elif cmd == "Pause":
                await session.try_pause_async()
            elif cmd == "Next":
                await session.try_skip_next_async()
            elif cmd == "Previous":
                await session.try_skip_previous_async()

        try:
            self._run_async(_send())
        except Exception as e:
            print("Windows media command error:", e)

    def set_media_position(self, pos_us: int) -> None:
        if not HAS_WIN_MEDIA:
            return

        async def _seek():
            manager = await MediaManager.request_async()
            session = manager.get_current_session()
            if session:
                from datetime import timedelta
                await session.try_change_playback_position_async(timedelta(microseconds=pos_us).total_seconds() * 10_000_000)

        try:
            self._run_async(_seek())
        except Exception as e:
            print("Windows seek error:", e)

    def get_volume(self) -> int:
        if self._volume_endpoint:
            try:
                scalar = self._volume_endpoint.GetMasterVolumeLevelScalar()
                return int(scalar * 100)
            except Exception:
                pass
        return 50

    def set_volume(self, val: int) -> None:
        if self._volume_endpoint:
            try:
                scalar = max(0.0, min(1.0, val / 100.0))
                self._volume_endpoint.SetMasterVolumeLevelScalar(scalar, None)
            except Exception as e:
                print("Windows set volume error:", e)

    def get_network_status(self) -> Tuple[str, str]:
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            for iface, stat in stats.items():
                if "loopback" in iface.lower() or not stat.isup:
                    continue
                has_ip = any(a.family == 2 for a in addrs.get(iface, []))
                if has_ip:
                    lower = iface.lower()
                    if any(w in lower for w in ("wi-fi", "wifi", "wireless", "wlan")):
                        return ("wifi", f"İnternet: Wi-Fi ({iface})")
                    else:
                        return ("lan", f"İnternet: Kablolu Ağ ({iface})")
        except Exception:
            pass
        return ("off", "İnternet: Bağlantı Yok")

    def get_quick_apps(self) -> List[Tuple[str, str, str]]:
        return [
            ("Ara", "system-search", "explorer.exe shell:::{2559a160-21d7-11d4-bdaf-00c04f60b9f0}"),
            ("Tarayıcı", "opera", "start http://"),
            ("Terminal", "utilities-terminal", "wt.exe || start cmd.exe"),
            ("Dosyalar", "system-file-manager", "explorer.exe")
        ]

    def launch_app(self, cmd: str) -> None:
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            print("Windows launch app error:", e)
