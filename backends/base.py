# -*- coding: utf-8 -*-
"""
Base Backend Interface for Dynamic Island.
Defines system interaction contracts for Linux and Windows.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List


class BaseBackend(ABC):
    """Platform-agnostic base backend interface."""

    @abstractmethod
    def get_media_info(self) -> Dict[str, Any]:
        """
        Returns media playback state:
        {
            "player": str or None,
            "title": str,
            "artist": str,
            "status": "Playing" | "Paused" | "Stopped",
            "trackid": str,
            "length": int,       # in microseconds
            "position": int,     # in microseconds
            "art_url": str       # file:// or http:// URL or local path
        }
        """
        pass

    @abstractmethod
    def send_media_command(self, cmd: str) -> None:
        """Sends playback commands: 'PlayPause', 'Next', 'Previous', 'Play', 'Pause'"""
        pass

    @abstractmethod
    def set_media_position(self, pos_us: int) -> None:
        """Seek to position in microseconds"""
        pass

    @abstractmethod
    def get_volume(self) -> int:
        """Returns system master volume percentage (0 - 100)"""
        pass

    @abstractmethod
    def set_volume(self, val: int) -> None:
        """Sets system master volume percentage (0 - 100)"""
        pass

    @abstractmethod
    def get_network_status(self) -> Tuple[str, str]:
        """
        Returns (net_type, tooltip)
        net_type: 'wifi' | 'lan' | 'off'
        """
        pass

    @abstractmethod
    def get_quick_apps(self) -> List[Tuple[str, str, str]]:
        """
        Returns quick launcher apps list:
        [(label, theme_or_icon_name, command_to_execute), ...]
        """
        pass

    @abstractmethod
    def launch_app(self, cmd: str) -> None:
        """Launches a desktop application asynchronously"""
        pass
