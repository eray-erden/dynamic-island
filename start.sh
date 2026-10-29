#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
pkill -f "dynamic_island.py" 2>/dev/null
nohup python3 "$DIR/dynamic_island.py" >/dev/null 2>&1 &
echo "[+] Dinamik Ada arka planda başlatıldı!"
