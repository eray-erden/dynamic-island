# -*- coding: utf-8 -*-
import sys
from .base import BaseBackend

def get_backend() -> BaseBackend:
    if sys.platform == "win32":
        from .windows import WindowsBackend
        return WindowsBackend()
    else:
        from .linux import LinuxBackend
        return LinuxBackend()
