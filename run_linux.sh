#!/usr/bin/env bash
# Mind Map Viewer - first run creates a virtual environment and installs PySide6.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv || { echo "Install venv first:  sudo apt install python3-venv"; exit 1; }
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi
# Qt 6 on Ubuntu needs libxcb-cursor0 for the X11/XWayland platform plugin
if command -v dpkg >/dev/null && ! dpkg -s libxcb-cursor0 >/dev/null 2>&1; then
  echo "Note: if the window does not open, run:  sudo apt install libxcb-cursor0"
fi
exec .venv/bin/python app.py "$@"
