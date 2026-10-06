"""Main application window."""
from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import QPoint, QFileSystemWatcher, QSettings, QSize, Qt, QThread, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QFont, QFontDatabase, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QDockWidget,
                               QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressDialog,
                               QPushButton, QSizePolicy, QToolBar, QToolButton, QVBoxLayout,
                               QWidget, QCheckBox)

from . import __version__, ai_import, parsers
from .icons import icon
from .model import Node
from .view import DARK, LIGHT, THEMES, MindMapView

APP_NAME = "Mind Map Viewer"
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
if getattr(sys, "frozen", False):  # PyInstaller
    SAMPLES_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), "samples")

OPEN_FILTER = ("Mind maps (*.md *.markdown *.txt *.mmd *.mermaid *.opml *.mm *.json *.xmind "
               "*.png *.jpg *.jpeg *.webp *.gif);;"
               "Markdown (*.md *.markdown);;Text outline (*.txt);;Mermaid (*.mmd *.mermaid);;"
               "OPML (*.opml);;FreeMind / Freeplane (*.mm);;JSON (*.json);;XMind (*.xmind);;"
               "Images - convert with AI (*.png *.jpg *.jpeg *.webp *.gif);;All files (*)")

FORMAT_CHOICES = [("Auto-detect", "auto"), ("Markdown", "markdown"), ("Indented text", "text"),
                  ("Mermaid mindmap", "mermaid"), ("OPML", "opml"), ("FreeMind (.mm)", "freemind"),
                  ("JSON", "json")]


# ----------------------------------------------------------------------------
# Background worker for the AI image import
# ----------------------------------------------------------------------------
class _AIWorker(QObject):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, path, key, model):
        super().__init__()
        self.path, self.key, self.model = path, key, model

    def run(self):
        try:
            self.done.emit(ai_import.image_to_markdown(self.path, self.key, self.model))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = settings
        form = QFormLayout()
        self.key = QLineEdit(settings.value("ai/api_key", "", str))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("sk-ant-...  (or set ANTHROPIC_API_KEY)")
        self.model = QLineEdit(settings.value("ai/model", ai_import.DEFAULT_MODEL, str))
        self.anim = QCheckBox("Animate expand / collapse and camera moves")
        self.anim.setChecked(settings.value("view/animations", True, bool))
        self.watch = QCheckBox("Reload automatically when the open file changes on disk")
        self.watch.setChecked(settings.value("file/watch", True, bool))
        form.addRow("Anthropic API key:", self.key)
        form.addRow("Vision model:", self.model)
        form.addRow("", QLabel("<small>Used only for <b>Import from image</b>. The image is sent to "
                               "the Anthropic API; text files are processed locally.</small>"))
        form.addRow(self.anim)
        form.addRow(self.watch)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(bb)
        self.resize(520, 220)

    def accept(self):
        self.settings.setValue("ai/api_key", self.key.text().strip())
        self.settings.setValue("ai/model", self.model.text().strip() or ai_import.DEFAULT_MODEL)
        self.settings.setValue("view/animations", self.anim.isChecked())
        self.settings.setValue("file/watch", self.watch.isChecked())
        super().accept()


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MindMapViewer", "MindMapViewer")
        self.current_path: Optional[str] = None
        self.root: Optional[Node] = None
        self._suppress_editor = False
        self._ai_thread: Optional[QThread] = None

        self.view = MindMapView(self)
        self.view.animations_enabled = self.settings.value("view/animations", True, bool)
        self.setCentralWidget(self.view)
        self.view.selectionChanged.connect(self._on_selection)
        self.view.mapChanged.connect(self._update_status)
        self.view.exportRequested.connect(self._show_export_menu)
        self.view.isolateChanged.connect(lambda on: self.act_back.setVisible(on))

        self._build_editor_dock()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()

        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._on_file_changed)
        self._reload_timer = QTimer(self, singleShot=True, interval=300, timeout=self._reload_from_disk)

        self.setAcceptDrops(True)
        self.resize(1400, 860)
        geo = self.settings.value("win/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        self.apply_theme(self.settings.value("view/theme", "dark", str))
        self._update_title()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_editor_dock(self):
        self.dock = QDockWidget("Source", self)
        self.dock.setObjectName("SourceDock")
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        top.addWidget(QLabel("Format:"))
        self.fmt_combo = QComboBox()
        for label, key in FORMAT_CHOICES:
            self.fmt_combo.addItem(label, key)
        self.fmt_combo.currentIndexChanged.connect(lambda _: self._schedule_parse())
        top.addWidget(self.fmt_combo, 1)
        self.btn_save_src = QPushButton("Save…")
        self.btn_save_src.clicked.connect(self.save_source_as)
        top.addWidget(self.btn_save_src)
        lay.addLayout(top)
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        mono.setPointSize(max(mono.pointSize(), 10))
        self.editor.setFont(mono)
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(" ") * 4)
        self.editor.setPlaceholderText(
            "# Central topic\n- Branch A\n  - Detail 1\n  - Detail 2\n- Branch B <!-- fold -->\n  - Hidden detail")
        self.editor.textChanged.connect(self._schedule_parse)
        lay.addWidget(self.editor, 1)
        self.parse_msg = QLabel("")
        self.parse_msg.setWordWrap(True)
        lay.addWidget(self.parse_msg)
        self.dock.setWidget(w)
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)
        self.dock.hide()
        w.setMinimumWidth(360)
        self._parse_timer = QTimer(self, singleShot=True, interval=350, timeout=self._parse_editor)

    def _act(self, text, slot, shortcut=None, ic=None, tip=None, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if ic:
            a.setProperty("ic", ic)
        if tip:
            a.setToolTip(tip)
        a.setCheckable(checkable)
        if checkable:
            a.toggled.connect(slot)
        else:
            a.triggered.connect(slot)
        return a

    def _build_actions(self):
        self.act_open = self._act("&Open…", self.open_dialog, QKeySequence.Open, "open",
                                  "Open a mind map file (Markdown, text, Mermaid, OPML, FreeMind, JSON, XMind, image)")
        self.act_image = self._act("Import from &image (AI)…", self.import_image_dialog, "Ctrl+I", "image",
                                   "Convert a mind map picture into an interactive map using Claude vision")
        self.act_paste = self._act("&New from clipboard", self.paste_from_clipboard, "Ctrl+Shift+V", None,
                                   "Create a map from text on the clipboard")
        self.act_new = self._act("&New (type outline)", self.new_map, QKeySequence.New)
        self.act_save_src = self._act("&Save source as…", self.save_source_as, QKeySequence.Save, "save")
        self.act_editor = self._act("Source editor", self._toggle_editor, "Ctrl+E", "edit",
                                    "Show / hide the text source of the map (live preview)", checkable=True)
        self.dock.visibilityChanged.connect(lambda v: (self.act_editor.blockSignals(True),
                                                       self.act_editor.setChecked(v),
                                                       self.act_editor.blockSignals(False)))
        self.act_find = self._act("&Find…", self._focus_search, QKeySequence.Find, "search")
        self.act_expand = self._act("E&xpand all", self.view.expand_all, "Ctrl+Shift+Down")
        self.act_collapse = self._act("&Collapse all", self.view.collapse_all, "Ctrl+Shift+Up")
        self.act_fit = self._act("&Fit to window", lambda: self.view.fit(True), "Ctrl+0")
        self.act_zin = self._act("Zoom &in", self.view.zoom_in, QKeySequence.ZoomIn)
        self.act_zout = self._act("Zoom &out", self.view.zoom_out, QKeySequence.ZoomOut)
        self.act_z100 = self._act("Actual size (100%)", self.view.reset_zoom, "Ctrl+1")
        self.act_theme = self._act("Theme", self.toggle_theme, "Ctrl+T", "theme",
                                   "Toggle dark / light theme")
        self.act_full = self._act("F&ull screen", self._toggle_full, "F11")
        self.act_back = self._act("Back to full map", self.view.show_full_map, None, "back",
                                  "Leave branch focus and show the whole map (Esc)")
        self.act_back.setVisible(False)
        self.act_settings = self._act("&Settings…", self.open_settings, "Ctrl+,")
        self.act_quit = self._act("&Quit", self.close, QKeySequence.Quit)

    def _build_menus(self):
        mb = self.menuBar()
        f = mb.addMenu("&File")
        f.addAction(self.act_open)
        self.recent_menu = f.addMenu("Open &recent")
        self._rebuild_recent()
        smp = f.addMenu("Open &sample")
        if os.path.isdir(SAMPLES_DIR):
            for fn in sorted(os.listdir(SAMPLES_DIR)):
                p = os.path.join(SAMPLES_DIR, fn)
                smp.addAction(fn, lambda p=p: self.open_path(p))
        f.addSeparator()
        f.addAction(self.act_image)
        f.addAction(self.act_paste)
        f.addAction(self.act_new)
        f.addSeparator()
        f.addAction(self.act_save_src)
        self.export_menu = f.addMenu("&Export")
        self._fill_export_menu(self.export_menu)
        f.addSeparator()
        f.addAction(self.act_settings)
        f.addAction(self.act_quit)

        v = mb.addMenu("&View")
        v.addAction(self.act_editor)
        v.addAction(self.act_find)
        v.addSeparator()
        v.addAction(self.act_expand)
        v.addAction(self.act_collapse)
        lv = v.addMenu("Show &levels")
        for i in range(1, 7):
            lv.addAction(f"{i} level{'s' if i > 1 else ''}", lambda i=i: self.view.expand_to_level(i),
                         QKeySequence(f"Alt+{i}"))
        v.addAction(self.act_back)
        v.addSeparator()
        v.addAction(self.act_fit)
        v.addAction(self.act_zin)
        v.addAction(self.act_zout)
        v.addAction(self.act_z100)
        v.addSeparator()
        v.addAction(self.act_theme)
        v.addAction(self.act_full)

        h = mb.addMenu("&Help")
        h.addAction("Mouse && keyboard shortcuts", self.show_shortcuts, "F1")
        h.addAction("Supported formats", self.show_formats)
        h.addAction(f"About {APP_NAME}", self.show_about)

    def _fill_export_menu(self, m: QMenu):
        m.addAction("PNG image…", lambda: self.export("png"))
        m.addAction("PNG image (transparent)…", lambda: self.export("png-t"))
        m.addAction("SVG vector…", lambda: self.export("svg"))
        m.addAction("PDF…", lambda: self.export("pdf"))
        m.addSeparator()
        for name in parsers.WRITERS:
            m.addAction(name.split(" (")[0] + "…", lambda n=name: self.export_text(n))

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setObjectName("MainToolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, tb)
        self.toolbar = tb
        tb.addAction(self.act_open)
        tb.addAction(self.act_image)
        tb.addAction(self.act_editor)
        tb.addSeparator()
        lv_btn = QToolButton(self)
        lv_btn.setText("Levels")
        lv_btn.setProperty("ic", "levels")
        lv_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        lv_btn.setPopupMode(QToolButton.InstantPopup)
        lvm = QMenu(lv_btn)
        for i in range(1, 7):
            lvm.addAction(f"Show {i} level{'s' if i > 1 else ''}", lambda i=i: self.view.expand_to_level(i))
        lvm.addSeparator()
        lvm.addAction("Expand all", self.view.expand_all)
        lvm.addAction("Collapse all", self.view.collapse_all)
        lv_btn.setMenu(lvm)
        tb.addWidget(lv_btn)
        self.lv_btn = lv_btn
        tb.addAction(self.act_back)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search topics…  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self._on_search_changed)
        self.search.returnPressed.connect(lambda: self._next_match(
            -1 if QGuiApplication.keyboardModifiers() & Qt.ShiftModifier else 1))
        self._search_timer = QTimer(self, singleShot=True, interval=250, timeout=self._run_search)
        tb.addWidget(self.search)
        self.search_count = QLabel("")
        self.search_count.setMinimumWidth(64)
        self.search_count.setAlignment(Qt.AlignCenter)
        tb.addWidget(self.search_count)
        tb.addSeparator()
        tb.addAction(self.act_theme)
        exp_btn = QToolButton(self)
        exp_btn.setText("Export")
        exp_btn.setProperty("ic", "download")
        exp_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        exp_btn.setPopupMode(QToolButton.InstantPopup)
        em = QMenu(exp_btn)
        self._fill_export_menu(em)
        exp_btn.setMenu(em)
        tb.addWidget(exp_btn)
        self.exp_btn = exp_btn

    def _build_statusbar(self):
        sb = self.statusBar()
        self.path_label = QLabel("")
        self.path_label.setTextFormat(Qt.PlainText)
        sb.addWidget(self.path_label, 1)
        self.count_label = QLabel("")
        sb.addPermanentWidget(self.count_label)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def apply_theme(self, name: str):
        th = THEMES.get(name, DARK)
        self.view.apply_theme(th)
        self.settings.setValue("view/theme", th.name)
        if th.name == "dark":
            ss = """
            QMainWindow, QDockWidget, QMenuBar, QStatusBar, QToolBar { background:#25262a; color:#d9dce1; }
            QToolBar { border:0; border-bottom:1px solid #34363b; padding:4px; spacing:4px; }
            QToolButton { color:#d9dce1; padding:4px 8px; border-radius:6px; }
            QToolButton:hover { background:#34363b; }
            QToolButton:checked { background:#3b4252; }
            QToolButton[popupMode="2"] { padding-right:18px; }
            QToolButton::menu-indicator { subcontrol-origin:padding; subcontrol-position:center right; right:4px; }
            QToolBar::separator { background:#3a3d43; width:1px; margin:6px 6px; }
            QMenuBar::item:selected, QMenu::item:selected { background:#3b4252; }
            QMenu { background:#2b2d31; color:#d9dce1; border:1px solid #3a3d43; }
            QMenu::separator { height:1px; background:#3a3d43; margin:4px 8px; }
            QLineEdit, QPlainTextEdit, QComboBox { background:#1e1f22; color:#e3e5e8; border:1px solid #3a3d43;
                border-radius:6px; padding:4px 6px; selection-background-color:#3d5a80; }
            QLabel { color:#c3c6cc; } QStatusBar QLabel { color:#9da1a8; padding:0 6px; }
            QPushButton { background:#34363b; color:#e3e5e8; border:1px solid #44474d; border-radius:6px; padding:4px 10px; }
            QPushButton:hover { background:#3d4046; }
            QDockWidget::title { padding:6px; background:#2b2d31; }
            QToolTip { background:#2b2d31; color:#e3e5e8; border:1px solid #44474d; padding:6px; }
            QDialog { background:#25262a; color:#d9dce1; } QCheckBox { color:#d9dce1; }
            """
            fg = "#d6d9de"
        else:
            ss = """
            QMainWindow, QDockWidget, QMenuBar, QStatusBar, QToolBar { background:#ffffff; color:#2b2f36; }
            QToolBar { border:0; border-bottom:1px solid #e3e5e9; padding:4px; spacing:4px; }
            QToolButton { color:#2b2f36; padding:4px 8px; border-radius:6px; }
            QToolButton:hover { background:#eef0f3; }
            QToolButton:checked { background:#e2e8f5; }
            QToolButton[popupMode="2"] { padding-right:18px; }
            QToolButton::menu-indicator { subcontrol-origin:padding; subcontrol-position:center right; right:4px; }
            QToolBar::separator { background:#e3e5e9; width:1px; margin:6px 6px; }
            QMenuBar::item:selected, QMenu::item:selected { background:#e2e8f5; color:#1b1f26; }
            QMenu { background:#ffffff; color:#2b2f36; border:1px solid #d9dce1; }
            QMenu::separator { height:1px; background:#e3e5e9; margin:4px 8px; }
            QLineEdit, QPlainTextEdit, QComboBox { background:#ffffff; color:#1f2329; border:1px solid #cfd3d9;
                border-radius:6px; padding:4px 6px; }
            QStatusBar QLabel { color:#5b616b; padding:0 6px; }
            QPushButton { background:#f3f4f6; border:1px solid #cfd3d9; border-radius:6px; padding:4px 10px; }
            QDockWidget::title { padding:6px; background:#f3f4f6; }
            QToolTip { background:#ffffff; color:#1f2329; border:1px solid #cfd3d9; padding:6px; }
            """
            fg = "#3b4049"
        self.setStyleSheet(ss)
        for a in self.findChildren(QAction):
            if a.property("ic"):
                a.setIcon(icon(a.property("ic"), fg))
        for b in (getattr(self, "lv_btn", None), getattr(self, "exp_btn", None)):
            if b is not None:
                b.setIcon(icon(b.property("ic"), fg))

    def toggle_theme(self):
        self.apply_theme("light" if self.view.theme.name == "dark" else "dark")

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def open_dialog(self):
        start = os.path.dirname(self.current_path) if self.current_path else self.settings.value("file/last_dir", "", str)
        path, _ = QFileDialog.getOpenFileName(self, "Open mind map", start, OPEN_FILTER)
        if path:
            self.open_path(path)

    def open_path(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext in parsers.IMAGE_EXTS:
            return self.import_image(path)
        try:
            root, text, fmt = parsers.parse_file(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, APP_NAME, f"Could not open\n{path}\n\n{e}")
            return
        self.settings.setValue("file/last_dir", os.path.dirname(path))
        self._add_recent(path)
        self._set_watch(path if ext != ".xmind" else None)
        self.current_path = path
        self._load_editor(text, fmt)
        self._show_root(root, fit=True, initial=True)
        self._update_title()
        self.statusBar().showMessage(f"Opened {os.path.basename(path)} ({fmt})", 4000)

    def _load_editor(self, text: str, fmt: str):
        self._suppress_editor = True
        idx = next((i for i, (_, k) in enumerate(FORMAT_CHOICES) if k == fmt), 0)
        self.fmt_combo.setCurrentIndex(idx)
        self.editor.setPlainText(text)
        self.parse_msg.setText("")
        self._suppress_editor = False

    def _show_root(self, root: Node, fit: bool, initial: bool = False, keep_state_from: Optional[Node] = None):
        if keep_state_from is not None:
            old_branch = {n.path_key() for n in keep_state_from.walk() if n.children}
            old_col = keep_state_from.collapsed_keys()
            for n in root.walk():
                k = n.path_key()
                if n.children and k in old_branch:
                    n.collapsed = k in old_col
        elif initial and not any(n.collapsed for n in root.walk()):
            if root.count() > 300:
                root.expand_to_level(2)
        root.collapsed = False
        self.root = root
        self.view.set_root(root, fit=fit, keep_view=not fit)
        if self.search.text().strip():
            self._run_search()
        self._update_status()

    def import_image_dialog(self):
        start = self.settings.value("file/last_dir", "", str)
        path, _ = QFileDialog.getOpenFileName(self, "Import mind map image", start,
                                              "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)")
        if path:
            self.import_image(path)

    def import_image(self, path: str):
        key = self.settings.value("ai/api_key", "", str) or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            r = QMessageBox.question(
                self, APP_NAME,
                "Converting an image into an interactive mind map uses Claude's vision API "
                "and needs an Anthropic API key.\n\nOpen Settings to add one now?")
            if r == QMessageBox.Yes:
                self.open_settings()
                key = self.settings.value("ai/api_key", "", str)
            if not key:
                return
        model = self.settings.value("ai/model", ai_import.DEFAULT_MODEL, str)
        self._progress = QProgressDialog("Reading the mind map image with Claude…", None, 0, 0, self)
        self._progress.setWindowTitle(APP_NAME)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.show()
        th = QThread(self)
        wk = _AIWorker(path, key, model)
        wk.moveToThread(th)
        th.started.connect(wk.run)
        self._ai_path = path
        wk.done.connect(self._ai_text_ready)  # bound slot -> queued to GUI thread
        wk.failed.connect(self._ai_failed)
        wk.done.connect(th.quit)
        wk.failed.connect(th.quit)
        th.finished.connect(wk.deleteLater)
        th.finished.connect(th.deleteLater)
        self._ai_thread, self._ai_worker = th, wk
        th.start()

    def _ai_text_ready(self, md: str):
        self._ai_done(self._ai_path, md)

    def _ai_done(self, path: str, md: str):
        self._progress.close()
        try:
            root = parsers.parse_text(md, "markdown", os.path.splitext(os.path.basename(path))[0])
        except Exception as e:  # noqa: BLE001
            return self._ai_failed(f"Could not parse the model's outline: {e}")
        self._set_watch(None)
        self.current_path = None
        self._image_origin = path
        self._load_editor(md, "markdown")
        self._show_root(root, fit=True, initial=True)
        self.dock.show()
        self._update_title(f"{os.path.basename(path)} (from image)")
        self.statusBar().showMessage(
            "Converted from image. Check the outline in the Source panel and use File › Save source to keep it.", 10000)

    def _ai_failed(self, msg: str):
        if getattr(self, "_progress", None):
            self._progress.close()
        QMessageBox.warning(self, APP_NAME, f"Image import failed:\n\n{msg}")

    def paste_from_clipboard(self):
        text = QGuiApplication.clipboard().text()
        if not text.strip():
            QMessageBox.information(self, APP_NAME, "The clipboard does not contain any text.")
            return
        self._set_watch(None)
        self.current_path = None
        self._load_editor(text, "auto")
        self._parse_editor(fit=True)
        self.dock.show()
        self._update_title("Clipboard")

    def new_map(self):
        self._set_watch(None)
        self.current_path = None
        self._load_editor("# Central topic\n\n- Branch A\n  - Detail 1\n  - Detail 2\n- Branch B\n  - Detail 3\n",
                          "markdown")
        self._parse_editor(fit=True)
        self.dock.show()
        self.editor.setFocus()
        self._update_title("Untitled")

    # ---- live editor ---------------------------------------------------
    def _schedule_parse(self):
        if not self._suppress_editor:
            self._parse_timer.start()

    def _parse_editor(self, fit: bool = False):
        text = self.editor.toPlainText()
        if not text.strip():
            self.parse_msg.setText("")
            return
        fmt = self.fmt_combo.currentData()
        title = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else "Mind Map"
        try:
            root = parsers.parse_text(text, fmt, title)
        except Exception as e:  # noqa: BLE001
            self.parse_msg.setText(f"<span style='color:#e57373'>⚠ {e}</span>")
            return
        detected = parsers.detect_format(text) if fmt == "auto" else fmt
        self.parse_msg.setText(f"<span style='color:#7fbf9f'>✓ {root.count()} topics · {detected}</span>")
        first = self.root is None or fit
        self._show_root(root, fit=first, keep_state_from=None if first else self.root)

    def _toggle_editor(self, on: bool):
        self.dock.setVisible(on)

    def save_source_as(self):
        start = self.current_path or os.path.join(self.settings.value("file/last_dir", "", str),
                                                  (self.root.text if self.root else "mindmap") + ".md")
        path, _ = QFileDialog.getSaveFileName(self, "Save source", start,
                                              "Markdown (*.md);;Text (*.txt);;Mermaid (*.mmd);;All files (*)")
        if not path:
            return
        text = self.editor.toPlainText()
        if not text.strip() and self.root:
            text = parsers.to_markdown(self.root)
        self._set_watch(None)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.current_path = path
        self._add_recent(path)
        self._set_watch(path)
        self._update_title()
        self.statusBar().showMessage(f"Saved {path}", 4000)

    # ---- file watching -------------------------------------------------
    def _set_watch(self, path: Optional[str]):
        if self.watcher.files():
            self.watcher.removePaths(self.watcher.files())
        if path and self.settings.value("file/watch", True, bool):
            self.watcher.addPath(path)

    def _on_file_changed(self, path):
        self._reload_timer.start()

    def _reload_from_disk(self):
        p = self.current_path
        if not p or not os.path.exists(p):
            return
        if p not in self.watcher.files():
            self.watcher.addPath(p)   # editors that replace the file drop the watch
        try:
            root, text, fmt = parsers.parse_file(p)
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(f"Reload failed: {e}", 6000)
            return
        self._load_editor(text, fmt)
        self._show_root(root, fit=False, keep_state_from=self.root)
        self.statusBar().showMessage(f"Reloaded {os.path.basename(p)}", 3000)

    # ---- recent files --------------------------------------------------
    def _add_recent(self, path):
        rec = [p for p in (self.settings.value("file/recent", [], list) or []) if p != path]
        rec.insert(0, path)
        self.settings.setValue("file/recent", rec[:10])
        self._rebuild_recent()

    def _rebuild_recent(self):
        self.recent_menu.clear()
        rec = self.settings.value("file/recent", [], list) or []
        for p in rec:
            if os.path.exists(p):
                self.recent_menu.addAction(p, lambda p=p: self.open_path(p))
        self.recent_menu.setEnabled(bool(self.recent_menu.actions()))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _base_name(self):
        if self.current_path:
            return os.path.splitext(self.current_path)[0]
        d = self.settings.value("file/last_dir", "", str)
        name = (self.view.layout_root.text if self.view.layout_root else "mindmap")
        name = "".join(c for c in name if c.isalnum() or c in " -_").strip() or "mindmap"
        return os.path.join(d, name)

    def _show_export_menu(self):
        m = QMenu(self)
        self._fill_export_menu(m)
        btn = self.view.controls.btn_dl
        sh = m.sizeHint()
        m.exec(btn.mapToGlobal(QPoint(-sh.width() - 8, btn.height() - sh.height())))

    def export(self, kind: str):
        if not self.root:
            return
        ext, filt = {"png": (".png", "PNG image (*.png)"), "png-t": (".png", "PNG image (*.png)"),
                     "svg": (".svg", "SVG (*.svg)"), "pdf": (".pdf", "PDF (*.pdf)")}[kind]
        path, _ = QFileDialog.getSaveFileName(self, "Export", self._base_name() + ext, filt)
        if not path:
            return
        if not path.lower().endswith(ext):
            path += ext
        try:
            if kind == "png":
                ok = self.view.export_png(path)
            elif kind == "png-t":
                ok = self.view.export_png(path, transparent=True)
            elif kind == "svg":
                ok = self.view.export_svg(path)
            else:
                ok = self.view.export_pdf(path)
        except Exception as e:  # noqa: BLE001
            ok, path = False, f"{path}\n{e}"
        if ok:
            self.statusBar().showMessage(f"Exported {path} (as currently expanded)", 5000)
        else:
            QMessageBox.warning(self, APP_NAME, f"Export failed: {path}")

    def export_text(self, writer_name: str):
        if not self.root:
            return
        ext, fn = parsers.WRITERS[writer_name]
        path, _ = QFileDialog.getSaveFileName(self, "Export", self._base_name() + ext, writer_name)
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(fn(self.view.layout_root or self.root))
        self.statusBar().showMessage(f"Exported {path}", 5000)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _on_search_changed(self, _):
        self._search_timer.start()

    def _run_search(self):
        n = self.view.search(self.search.text())
        q = self.search.text().strip()
        self.search_count.setText("" if not q else (f"{n} found" if n else "no match"))
        if n:
            self.view.match_index = -1

    def _next_match(self, step=1):
        if self._search_timer.isActive():
            self._search_timer.stop()
            self._run_search()
        i = self.view.next_match(step)
        if i >= 0:
            self.search_count.setText(f"{i + 1} / {len(self.view.match_list)}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def _on_selection(self, node):
        if node is None:
            self.path_label.setText("")
        else:
            txt = "  ›  ".join(n.text for n in node.path())
            if node.note:
                txt += f"    —  {node.note}"
            self.path_label.setText(txt)

    def _update_status(self):
        if not self.root:
            self.count_label.setText("")
            return
        total = self.root.count()
        shown = len(self.view.shown)
        self.count_label.setText(f"{shown} of {total} topics shown · depth {self.root.max_depth()}")

    def _update_title(self, name: Optional[str] = None):
        if name is None:
            name = os.path.basename(self.current_path) if self.current_path else None
        self.setWindowTitle(f"{name} — {APP_NAME}" if name else APP_NAME)

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def open_settings(self):
        d = SettingsDialog(self.settings, self)
        if d.exec():
            self.view.animations_enabled = self.settings.value("view/animations", True, bool)
            self._set_watch(self.current_path)

    def _toggle_full(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def show_shortcuts(self):
        QMessageBox.information(self, "Mouse & keyboard", """<table cellpadding=3>
<tr><td><b>Drag</b> background or node</td><td>Pan</td></tr>
<tr><td><b>Mouse wheel</b></td><td>Zoom at cursor (Shift+wheel / trackpad = pan)</td></tr>
<tr><td><b>Click</b> the ‹ › circle</td><td>Collapse / expand a branch</td></tr>
<tr><td><b>Double-click</b> a topic</td><td>Collapse / expand (leaf: centre on it)</td></tr>
<tr><td><b>Click</b> a topic</td><td>Select it (path shown in status bar)</td></tr>
<tr><td><b>Right-click</b></td><td>Branch actions: expand/collapse branch, focus on branch, copy…</td></tr>
<tr><td><b>Ctrl+click</b></td><td>Open a topic's link</td></tr>
<tr><td><b>Arrow keys</b></td><td>Move selection (→ expands, ← goes to parent)</td></tr>
<tr><td><b>Space / Enter</b></td><td>Toggle selected branch</td></tr>
<tr><td><b>+ / −</b>, <b>F</b> or <b>0</b></td><td>Zoom in / out, fit to window</td></tr>
<tr><td><b>E</b></td><td>Expand all / collapse all</td></tr>
<tr><td><b>Alt+1…6</b></td><td>Show 1–6 levels</td></tr>
<tr><td><b>Ctrl+F</b>, Enter / Shift+Enter</td><td>Search, next / previous match</td></tr>
<tr><td><b>Ctrl+E</b></td><td>Source editor with live preview</td></tr>
<tr><td><b>Esc</b></td><td>Leave branch focus / clear selection</td></tr>
</table>""")

    def show_formats(self):
        QMessageBox.information(self, "Supported formats", """<b>Text formats</b> (processed locally)<br>
• <b>Markdown</b>: <code>#</code> headings and <code>-</code> bullets (markmap style)<br>
• <b>Indented text</b>: one topic per line, tabs/spaces give the hierarchy<br>
• <b>Mermaid</b> <code>mindmap</code> diagrams (.mmd)<br>
• <b>OPML</b>, <b>FreeMind/Freeplane</b> (.mm), <b>XMind</b> (.xmind), <b>JSON</b><br><br>
Add <code>&lt;!-- fold --&gt;</code> to a line to start that branch collapsed.<br><br>
<b>Images</b> (PNG/JPG/WebP): converted to an outline with Claude's vision API
(needs an API key in Settings). The resulting outline opens in the Source panel so you can
check and save it.""")

    def show_about(self):
        QMessageBox.about(self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}<br>"
                          "Interactive, collapsible mind map viewer for Windows and Linux.<br>"
                          f"Python {sys.version.split()[0]} · Qt (PySide6)")

    # ---- drag & drop ---------------------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        if md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    self.open_path(u.toLocalFile())
                    return
        if md.hasText():
            self._set_watch(None)
            self.current_path = None
            self._load_editor(md.text(), "auto")
            self._parse_editor(fit=True)
            self._update_title("Dropped text")

    def closeEvent(self, e):
        self.settings.setValue("win/geometry", self.saveGeometry())
        super().closeEvent(e)
