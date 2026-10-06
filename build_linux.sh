#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Build Mind Map Viewer for Ubuntu / Debian.
#    ./build_linux.sh             folder build + release/*.tar.gz + release/*.deb
#    ./build_linux.sh --onefile   single MindMapViewer binary
#    ./build_linux.sh --clean     clean rebuild
#  Prerequisites (once):  sudo apt install python3-venv libxcb-cursor0
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "python3 not found: sudo apt install python3 python3-venv"; exit 1; }
python3 -c "import venv, ensurepip" 2>/dev/null || { echo "Missing venv support: sudo apt install python3-venv"; exit 1; }
python3 build.py "$@"
