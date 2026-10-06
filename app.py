#!/usr/bin/env python3
"""Mind Map Viewer - interactive, collapsible mind maps from text, Markdown or images.

Usage:
    python app.py [file]
    python app.py --version
    python app.py --selftest      # headless check used by the build script
"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from mindmap.main_window import APP_NAME, SAMPLES_DIR, MainWindow


def _say(msg):
    # windowed (no-console) builds have no stdout on Windows
    try:
        print(msg, flush=True)
    except Exception:
        pass


def selftest() -> int:
    """Open every sample headlessly, render and export it. Returns a process exit code."""
    import tempfile
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv[:1])
    from mindmap import parsers
    win = MainWindow()
    win.view.animations_enabled = False
    win.resize(1200, 800)
    win.show()
    samples = sorted(f for f in os.listdir(SAMPLES_DIR)
                     if os.path.splitext(f)[1].lower() not in parsers.IMAGE_EXTS)
    if not samples:
        _say("selftest: no samples found in " + SAMPLES_DIR)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        for f in samples:
            win.open_path(os.path.join(SAMPLES_DIR, f))
            app.processEvents()
            if win.root is None or not win.view.shown:
                _say(f"selftest: FAILED to render {f}")
                return 1
            out = os.path.join(tmp, "out.png")
            if not win.view.export_png(out) or os.path.getsize(out) < 1000:
                _say(f"selftest: FAILED to export {f}")
                return 1
            _say(f"selftest: ok  {f}  ({win.root.count()} topics)")
        svg = os.path.join(tmp, "out.svg")
        win.view.export_svg(svg)
        if os.path.getsize(svg) < 1000:
            _say("selftest: FAILED svg export")
            return 1
    _say("selftest: PASSED")
    return 0


def main():
    if "--version" in sys.argv:
        from mindmap import __version__
        _say(f"{APP_NAME} {__version__}")
        return 0
    if "--selftest" in sys.argv:
        return selftest()
    if sys.platform.startswith("win"):
        try:  # proper taskbar grouping / icon on Windows
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MindMapViewer.App")
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("MindMapViewer")
    app.setStyle("Fusion")
    here = os.path.dirname(os.path.abspath(__file__))
    ico = os.path.join(here, "assets", "icon.png")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))

    win = MainWindow()
    win.show()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        win.open_path(os.path.abspath(args[0]))
    else:
        sample = os.path.join(SAMPLES_DIR, "amazon_leadership_principles.md")
        if os.path.exists(sample):
            win.open_path(sample)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
