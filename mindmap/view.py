"""Interactive mind map canvas built on QGraphicsView."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, QSize, QSizeF, Qt, QTimer,
                            QVariantAnimation, Signal, QUrl, QMarginsF)
from PySide6.QtGui import (QBrush, QColor, QCursor, QDesktopServices, QFont, QFontMetricsF,
                           QGuiApplication, QImage, QKeySequence, QPainter, QPainterPath,
                           QPageSize, QPdfWriter, QPen, QTextOption, QTransform)
from PySide6.QtWidgets import (QFrame, QGraphicsItem, QGraphicsObject, QGraphicsPathItem,
                               QGraphicsScene, QGraphicsView, QMenu, QToolButton,
                               QVBoxLayout, QWidget)

from . import parsers
from .icons import icon
from .layout import compute_layout
from .model import Node


# ----------------------------------------------------------------------------
# Themes
# ----------------------------------------------------------------------------
@dataclass
class Theme:
    name: str
    background: str
    node_fill: List[str]        # by depth (last entry repeats)
    node_text: List[str]
    edge: List[str]             # by parent depth
    toggle_fill: str
    toggle_fg: str
    accent: str
    match: str
    hover_lighten: int
    ctrl_bg: str
    ctrl_fg: str


DARK = Theme(
    name="dark",
    background="#1e1f22",
    node_fill=["#4a5066", "#43495a", "#353f3b", "#2f4a3b"],
    node_text=["#eef0f6", "#e6e8ef", "#e3ebe6", "#e3efe7"],
    edge=["#8b8fd8", "#8fa3bf", "#6fb495", "#6fb495"],
    toggle_fill="#3a3d44",
    toggle_fg="#c9ccd3",
    accent="#8ab4f8",
    match="#f2c94c",
    hover_lighten=118,
    ctrl_bg="#2b2d31",
    ctrl_fg="#d6d9de",
)

LIGHT = Theme(
    name="light",
    background="#f6f7f9",
    node_fill=["#d9ddf2", "#e1e5ee", "#dcebe2", "#e5f3ea"],
    node_text=["#1c2033", "#1f2430", "#1d2b23", "#1d2b23"],
    edge=["#7a80d0", "#8395b1", "#58a382", "#58a382"],
    toggle_fill="#e3e5e9",
    toggle_fg="#3b4049",
    accent="#1a73e8",
    match="#d49b00",
    hover_lighten=94,
    ctrl_bg="#ffffff",
    ctrl_fg="#3b4049",
)

THEMES = {"dark": DARK, "light": LIGHT}


def _pick(lst, i):
    return lst[min(i, len(lst) - 1)]


# ----------------------------------------------------------------------------
# Geometry constants (scene units)
# ----------------------------------------------------------------------------
PAD_X, PAD_Y = 11.0, 7.0
MAX_TEXT_W = 360.0
RADIUS = 6.0
TOGGLE_R = 9.0
TOGGLE_DX = 15.0     # distance from node's right edge to toggle centre
FONT_PX = 13


class NodeItem(QGraphicsObject):
    def __init__(self, node: Node, canvas: "MindMapView"):
        super().__init__()
        self.node = node
        self.canvas = canvas
        self.hover = False
        self.hover_toggle = False
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        self.relayout_text()

    # ---- geometry -----------------------------------------------------
    def relayout_text(self):
        self.prepareGeometryChange()
        f = self.canvas.node_font(self.node)
        fm = QFontMetricsF(f)
        br = fm.boundingRect(QRectF(0, 0, MAX_TEXT_W, 10000),
                             Qt.TextWordWrap | Qt.AlignLeft, self.node.text)
        self.text_w = max(br.width(), 8.0)
        self.text_h = max(br.height(), fm.height())
        self.w = math.ceil(self.text_w + 2 * PAD_X)
        self.h = math.ceil(self.text_h + 2 * PAD_Y)
        self.setTransformOriginPoint(0, self.h / 2)
        tip = self.node.text
        if self.node.note:
            tip += "\n\n" + self.node.note
        if self.node.children and self.node.collapsed:
            tip += f"\n\n({len(self.node.children)} hidden sub-topics)"
        if self.node.link:
            tip += f"\n\nCtrl+click to open: {self.node.link}"
        self.setToolTip(tip if (len(tip) > 60 or "\n" in tip) else "")

    def size(self):
        return self.w, self.h

    def boundingRect(self) -> QRectF:
        extra = (TOGGLE_DX + TOGGLE_R + 3) if self.node.children else 3
        return QRectF(-3, -3, self.w + extra + 3, self.h + 6)

    def toggle_center(self) -> QPointF:
        return QPointF(self.w + TOGGLE_DX, self.h / 2)

    def anchor_out(self) -> QPointF:
        """Scene point where edges to children start."""
        p = self.pos()
        if self.node.children:
            return QPointF(p.x() + self.w + TOGGLE_DX + TOGGLE_R, p.y() + self.h / 2)
        return QPointF(p.x() + self.w, p.y() + self.h / 2)

    def anchor_in(self) -> QPointF:
        p = self.pos()
        return QPointF(p.x(), p.y() + self.h / 2)

    def hit_toggle(self, scene_pt: QPointF) -> bool:
        if not self.node.children:
            return False
        lp = self.mapFromScene(scene_pt)
        c = self.toggle_center()
        return (lp.x() - c.x()) ** 2 + (lp.y() - c.y()) ** 2 <= (TOGGLE_R + 4) ** 2

    def hit_body(self, scene_pt: QPointF) -> bool:
        lp = self.mapFromScene(scene_pt)
        return 0 <= lp.x() <= self.w and 0 <= lp.y() <= self.h

    # ---- painting -----------------------------------------------------
    def paint(self, p: QPainter, option, widget=None):
        th = self.canvas.theme
        d = self.node.depth - self.canvas.layout_root.depth
        fill = QColor(_pick(th.node_fill, d))
        if self.hover and not self.hover_toggle:
            fill = fill.lighter(th.hover_lighten)
        p.setRenderHint(QPainter.Antialiasing)
        pen = Qt.NoPen
        if self.node is self.canvas.selected:
            pen = QPen(QColor(th.accent), 2)
        elif self.node.id in self.canvas.matches:
            pen = QPen(QColor(th.match), 2)
        p.setPen(pen)
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(0, 0, self.w, self.h), RADIUS, RADIUS)

        p.setPen(QColor(_pick(th.node_text, d)))
        p.setFont(self.canvas.node_font(self.node))
        opt = QTextOption()
        opt.setWrapMode(QTextOption.WordWrap)
        p.drawText(QRectF(PAD_X, PAD_Y, self.text_w + 1, self.text_h + 1), self.node.text, opt)

        if self.node.children:
            c = self.toggle_center()
            tf = QColor(th.toggle_fill)
            if self.hover_toggle:
                tf = tf.lighter(140 if th.name == "dark" else 92)
            p.setPen(Qt.NoPen)
            p.setBrush(tf)
            p.drawEllipse(c, TOGGLE_R, TOGGLE_R)
            pen = QPen(QColor(th.toggle_fg), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            s = 3.0
            path = QPainterPath()
            if self.node.collapsed:   # ">"
                path.moveTo(c.x() - s / 2, c.y() - s)
                path.lineTo(c.x() + s / 2 + 0.5, c.y())
                path.lineTo(c.x() - s / 2, c.y() + s)
            else:                     # "<"
                path.moveTo(c.x() + s / 2, c.y() - s)
                path.lineTo(c.x() - s / 2 - 0.5, c.y())
                path.lineTo(c.x() + s / 2, c.y() + s)
            p.drawPath(path)

    # ---- hover --------------------------------------------------------
    def hoverMoveEvent(self, e):
        ht = self.hit_toggle(e.scenePos())
        if ht != self.hover_toggle or not self.hover:
            self.hover, self.hover_toggle = True, ht
            self.update()
        self.setCursor(Qt.PointingHandCursor)

    def hoverEnterEvent(self, e):
        self.hover = True
        self.hover_toggle = self.hit_toggle(e.scenePos())
        self.update()

    def hoverLeaveEvent(self, e):
        self.hover = self.hover_toggle = False
        self.unsetCursor()
        self.update()


class EdgeItem(QGraphicsPathItem):
    def __init__(self, child: NodeItem, canvas: "MindMapView"):
        super().__init__()
        self.child = child
        self.canvas = canvas
        self.setZValue(1)

    def refresh(self):
        parent_node = self.child.node.parent
        pitem = self.canvas.items_by_id.get(parent_node.id) if parent_node else None
        if pitem is None or not self.child.isVisible():
            self.setVisible(False)
            return
        a = pitem.anchor_out()
        b = self.child.anchor_in()
        dx = max((b.x() - a.x()) * 0.5, 10)
        path = QPainterPath(a)
        path.cubicTo(QPointF(a.x() + dx, a.y()), QPointF(b.x() - dx, b.y()), b)
        self.setPath(path)
        th = self.canvas.theme
        d = parent_node.depth - self.canvas.layout_root.depth
        on_path = self.canvas.selected is not None and self.child.node in self.canvas.selected_path
        col = QColor(th.accent if on_path else _pick(th.edge, d))
        pen = QPen(col, 2.4 if on_path else 1.5)
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)
        self.setOpacity(self.child.opacity())
        self.setVisible(True)


# ----------------------------------------------------------------------------
# Floating controls (bottom-right, like NotebookLM)
# ----------------------------------------------------------------------------
class FloatingControls(QFrame):
    def __init__(self, view: "MindMapView"):
        super().__init__(view)
        self.view = view
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.btn_all = self._btn("expand", "Expand all / collapse all  (E)", view.toggle_all)
        lay.addWidget(self.btn_all)
        lay.addSpacing(6)
        lay.addWidget(self._btn("plus", "Zoom in  (+)", view.zoom_in))
        lay.addWidget(self._btn("minus", "Zoom out  (-)", view.zoom_out))
        lay.addWidget(self._btn("fit", "Fit to window  (F)", lambda: view.fit(animate=True)))
        lay.addSpacing(6)
        self.btn_dl = self._btn("download", "Download / export", view.exportRequested.emit)
        lay.addWidget(self.btn_dl)
        self.apply_theme()

    def _btn(self, ic, tip, slot):
        b = QToolButton(self)
        b.setProperty("ic", ic)
        b.setToolTip(tip)
        b.setFixedSize(40, 40)
        b.setIconSize(QSize(20, 20))
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def apply_theme(self):
        th = self.view.theme
        border = "#3a3d43" if th.name == "dark" else "#d9dce1"
        hover = "#3a3d43" if th.name == "dark" else "#eef0f3"
        self.setStyleSheet(
            f"QToolButton {{ background:{th.ctrl_bg}; border:1px solid {border}; border-radius:20px; }}"
            f"QToolButton:hover {{ background:{hover}; }}")
        for b in self.findChildren(QToolButton):
            b.setIcon(icon(b.property("ic"), th.ctrl_fg))
        self.update_all_icon()

    def update_all_icon(self):
        root = self.view.root
        all_open = root is not None and not any(n.collapsed for n in self.view.layout_root.walk() if n.children)
        self.btn_all.setProperty("ic", "collapse" if all_open else "expand")
        self.btn_all.setIcon(icon(self.btn_all.property("ic"), self.view.theme.ctrl_fg))
        self.btn_all.setToolTip("Collapse all  (E)" if all_open else "Expand all  (E)")


# ----------------------------------------------------------------------------
# The canvas
# ----------------------------------------------------------------------------
class MindMapView(QGraphicsView):
    selectionChanged = Signal(object)        # Node | None
    mapChanged = Signal()                    # collapse state / isolation changed
    exportRequested = Signal()
    isolateChanged = Signal(bool)

    MIN_ZOOM, MAX_ZOOM = 0.08, 4.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme: Theme = DARK
        self.root: Optional[Node] = None
        self.layout_root: Optional[Node] = None   # == root unless a branch is isolated
        self.items_by_id: Dict[int, NodeItem] = {}
        self.edges_by_id: Dict[int, EdgeItem] = {}
        self.shown: set = set()
        self.selected: Optional[Node] = None
        self.selected_path: set = set()
        self.matches: Dict[int, Node] = {}
        self.match_list: List[Node] = []
        self.match_index = -1
        self.animations_enabled = True
        self._font_cache: Dict[bool, QFont] = {}

        self.scene_ = QGraphicsScene(self)
        self.scene_.setSceneRect(-500000, -500000, 1000000, 1000000)
        self.setScene(self.scene_)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self._press_pos = None
        self._last_pos = None
        self._dragging = False
        self._press_item: Optional[NodeItem] = None

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(320)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._anim_step)
        self._anim.finished.connect(self._anim_done)
        self._tracks = {}

        self._cam = QVariantAnimation(self)
        self._cam.setDuration(380)
        self._cam.setEasingCurve(QEasingCurve.InOutCubic)
        self._cam.setStartValue(0.0)
        self._cam.setEndValue(1.0)
        self._cam.valueChanged.connect(self._cam_step)
        self._cam_from = self._cam_to = None

        self.controls = FloatingControls(self)
        self.apply_theme(DARK)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def node_font(self, node: Node) -> QFont:
        is_root = node is self.layout_root
        f = self._font_cache.get(is_root)
        if f is None:
            f = QFont(QGuiApplication.font())
            f.setPixelSize(FONT_PX + (1 if is_root else 0))
            if is_root:
                f.setWeight(QFont.DemiBold)
            self._font_cache[is_root] = f
        return f

    def set_root(self, root: Optional[Node], fit: bool = True, keep_view: bool = False):
        self._anim.stop()
        self._cam.stop()
        self.scene_.clear()
        self.items_by_id.clear()
        self.edges_by_id.clear()
        self.shown.clear()
        self.matches.clear()
        self.match_list = []
        self.root = root
        self.layout_root = root
        self.selected = None
        self.selected_path = set()
        self.isolateChanged.emit(False)
        if root is None:
            self.controls.update_all_icon()
            return
        old_center = self.mapToScene(self.viewport().rect().center())
        self._relayout(animate=False)
        if fit and not keep_view:
            self.fit(animate=False)
        elif keep_view:
            self.centerOn(old_center)
        self.selectionChanged.emit(None)
        self.mapChanged.emit()

    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.setBackgroundBrush(QColor(theme.background))
        self.controls.apply_theme()
        for it in self.items_by_id.values():
            it.update()
        self._refresh_edges()

    def toggle(self, node: Node):
        if not node.children:
            return
        node.collapsed = not node.collapsed
        self._relayout(anchor=node)
        if not node.collapsed:
            QTimer.singleShot(self._anim.duration() + 20, lambda: self.ensure_branch_visible(node))

    def set_collapsed(self, node: Node, collapsed: bool, recursive: bool = False):
        if recursive:
            node.set_collapsed_recursive(collapsed)
            if collapsed and node is not self.layout_root:
                pass
            elif not collapsed:
                node.collapsed = False
        elif node.children:
            node.collapsed = collapsed
        if node is self.layout_root:
            node.collapsed = False
        self._relayout(anchor=node)

    def expand_all(self):
        if self.layout_root:
            self.layout_root.set_collapsed_recursive(False)
            self._relayout(anchor=self.layout_root, after=lambda: self.fit(animate=True))

    def collapse_all(self):
        if self.layout_root:
            self.layout_root.set_collapsed_recursive(True)
            self.layout_root.collapsed = False
            self._select(None)
            self._relayout(anchor=self.layout_root, after=lambda: self.fit(animate=True))

    def toggle_all(self):
        if not self.layout_root:
            return
        if any(n.collapsed for n in self.layout_root.walk() if n.children):
            self.expand_all()
        else:
            self.collapse_all()

    def expand_to_level(self, level: int):
        if self.layout_root:
            self.layout_root.expand_to_level(level)
            self.layout_root.collapsed = False
            self._relayout(anchor=self.layout_root, after=lambda: self.fit(animate=True))

    def isolate(self, node: Node):
        """Show only the branch rooted at `node`."""
        if node is self.root:
            return self.show_full_map()
        node.collapsed = False
        self.layout_root = node
        self._font_cache.clear()
        self._hide_all()
        self._relayout(animate=False)
        for it in self.items_by_id.values():
            it.relayout_text()
        self._relayout(animate=False)
        self.fit(animate=True)
        self.isolateChanged.emit(True)
        self.mapChanged.emit()

    def show_full_map(self):
        if self.root is None or self.layout_root is self.root:
            return
        focus = self.layout_root
        self.layout_root = self.root
        self._font_cache.clear()
        focus.reveal()
        self._hide_all()
        for it in self.items_by_id.values():
            it.relayout_text()
        self._relayout(animate=False)
        self.fit(animate=True)
        self.isolateChanged.emit(False)
        self.mapChanged.emit()

    @property
    def is_isolated(self) -> bool:
        return self.root is not None and self.layout_root is not self.root

    # ---- zoom / camera -------------------------------------------------
    def current_scale(self) -> float:
        return self.transform().m11()

    def zoom_by(self, factor: float, anchor_view_pt=None, animate=True):
        s = self.current_scale()
        ns = max(self.MIN_ZOOM, min(self.MAX_ZOOM, s * factor))
        if anchor_view_pt is None:
            center = self.mapToScene(self.viewport().rect().center())
            if animate:
                self._animate_camera(ns, center)
            else:
                self._set_camera(ns, center)
            return
        # keep the scene point under the cursor fixed
        before = self.mapToScene(anchor_view_pt)
        self._set_camera(ns, self.mapToScene(self.viewport().rect().center()))
        after = self.mapToScene(anchor_view_pt)
        c = self.mapToScene(self.viewport().rect().center()) + (before - after)
        self._set_camera(ns, c)

    def zoom_in(self):
        self.zoom_by(1.25)

    def zoom_out(self):
        self.zoom_by(0.8)

    def reset_zoom(self):
        self._animate_camera(1.0, self.mapToScene(self.viewport().rect().center()))

    def content_rect(self) -> QRectF:
        r = QRectF()
        for nid in self.shown:
            it = self.items_by_id[nid]
            r = r.united(it.sceneBoundingRect())
        return r

    def fit(self, animate=True, max_scale: float = 1.6):
        if not self.shown:
            return
        r = self.content_rect()
        vp = self.viewport().rect()
        m = 40
        sx = (vp.width() - 2 * m - 60) / max(r.width(), 1)
        sy = (vp.height() - 2 * m) / max(r.height(), 1)
        s = max(self.MIN_ZOOM, min(max_scale, sx, sy))
        c = r.center()
        # leave room for the floating controls on the right
        c.setX(c.x() + 30 / s)
        if animate and self.animations_enabled:
            self._animate_camera(s, c)
        else:
            self._set_camera(s, c)

    def center_on_node(self, node: Node, animate=True, zoom: Optional[float] = None):
        it = self.items_by_id.get(node.id)
        if not it or node.id not in self.shown:
            return
        s = zoom or max(self.current_scale(), 0.8)
        c = it.sceneBoundingRect().center()
        if animate and self.animations_enabled:
            self._animate_camera(s, c)
        else:
            self._set_camera(s, c)

    def ensure_node_visible(self, node: Node):
        it = self.items_by_id.get(node.id)
        if not it:
            return
        vr = self.mapToScene(self.viewport().rect().adjusted(30, 30, -90, -30)).boundingRect()
        r = it.sceneBoundingRect()
        if not vr.contains(r):
            c = self.mapToScene(self.viewport().rect().center())
            dx = dy = 0.0
            if r.left() < vr.left():
                dx = r.left() - vr.left()
            elif r.right() > vr.right():
                dx = r.right() - vr.right()
            if r.top() < vr.top():
                dy = r.top() - vr.top()
            elif r.bottom() > vr.bottom():
                dy = r.bottom() - vr.bottom()
            self._animate_camera(self.current_scale(), c + QPointF(dx, dy))

    def ensure_branch_visible(self, node: Node):
        """After expanding, nudge the camera so the new children are on screen."""
        ids = [c.id for c in node.children if c.id in self.shown]
        if not ids:
            return
        r = self.items_by_id[node.id].sceneBoundingRect()
        for i in ids:
            r = r.united(self.items_by_id[i].sceneBoundingRect())
        vr = self.mapToScene(self.viewport().rect().adjusted(20, 20, -80, -20)).boundingRect()
        if vr.contains(r):
            return
        s = self.current_scale()
        c = self.mapToScene(self.viewport().rect().center())
        dx = dy = 0.0
        if r.width() <= vr.width():
            if r.right() > vr.right():
                dx = r.right() - vr.right()
            elif r.left() < vr.left():
                dx = r.left() - vr.left()
        if r.height() <= vr.height():
            if r.bottom() > vr.bottom():
                dy = r.bottom() - vr.bottom()
            elif r.top() < vr.top():
                dy = r.top() - vr.top()
        if dx or dy:
            self._animate_camera(s, c + QPointF(dx, dy))

    def _set_camera(self, scale: float, center: QPointF):
        self.setTransform(QTransform.fromScale(scale, scale))
        self.centerOn(center)

    def _animate_camera(self, scale: float, center: QPointF):
        if not self.animations_enabled:
            return self._set_camera(scale, center)
        self._cam.stop()
        self._cam_from = (self.current_scale(), self.mapToScene(self.viewport().rect().center()))
        self._cam_to = (scale, QPointF(center))
        self._cam.start()

    def _cam_step(self, t):
        if not self._cam_from:
            return
        (s0, c0), (s1, c1) = self._cam_from, self._cam_to
        # interpolate zoom geometrically for a natural feel
        s = s0 * (s1 / s0) ** t if s0 > 0 else s1
        c = c0 + (c1 - c0) * t
        self._set_camera(s, c)

    # ---- search --------------------------------------------------------
    def search(self, query: str) -> int:
        self.matches.clear()
        self.match_list = []
        self.match_index = -1
        q = query.strip().lower()
        if q and self.layout_root:
            for n in self.layout_root.walk():
                if q in n.text.lower() or (n.note and q in n.note.lower()):
                    self.matches[n.id] = n
                    self.match_list.append(n)
            for n in self.match_list:
                n.reveal()
                if self.layout_root in n.ancestors() or n is self.layout_root:
                    pass
            self._relayout(anchor=self.layout_root)
        for it in self.items_by_id.values():
            it.update()
        return len(self.match_list)

    def next_match(self, step: int = 1) -> int:
        if not self.match_list:
            return -1
        self.match_index = (self.match_index + step) % len(self.match_list)
        n = self.match_list[self.match_index]
        self._select(n)
        self.center_on_node(n, zoom=max(self.current_scale(), 1.0))
        return self.match_index

    # ---- selection -----------------------------------------------------
    def _select(self, node: Optional[Node]):
        prev = self.selected
        self.selected = node
        self.selected_path = set(node.path()) if node else set()
        for n in (prev, node):
            if n is not None and n.id in self.items_by_id:
                self.items_by_id[n.id].update()
        self._refresh_edges()
        self.selectionChanged.emit(node)

    def select(self, node: Optional[Node]):
        if node is not None:
            node.reveal()
            if node.id not in self.shown:
                self._relayout(anchor=self.layout_root)
        self._select(node)

    # ------------------------------------------------------------------
    # Layout + animation
    # ------------------------------------------------------------------
    def _item(self, node: Node) -> NodeItem:
        it = self.items_by_id.get(node.id)
        if it is None:
            it = NodeItem(node, self)
            it.setVisible(False)
            self.scene_.addItem(it)
            self.items_by_id[node.id] = it
            if node.parent is not None:
                e = EdgeItem(it, self)
                e.setVisible(False)
                self.scene_.addItem(e)
                self.edges_by_id[node.id] = e
        return it

    def _hide_all(self):
        self._anim.stop()
        for nid in list(self.shown):
            self.items_by_id[nid].setVisible(False)
        for e in self.edges_by_id.values():
            e.setVisible(False)
        self.shown.clear()

    def _relayout(self, anchor: Optional[Node] = None, animate: bool = True, after=None):
        if self.layout_root is None:
            return
        self._anim.stop()
        self._after = after
        visible = list(self.layout_root.visible())
        for n in visible:
            self._item(n)
        pos = compute_layout(self.layout_root, lambda n: self.items_by_id[n.id].size())

        # keep the anchor node fixed on screen (NotebookLM behaviour)
        off = QPointF(0, 0)
        if anchor is not None and anchor.id in self.shown and anchor.id in pos:
            cur = self.items_by_id[anchor.id].pos()
            nx, ncy = pos[anchor.id]
            off = QPointF(cur.x() - nx, cur.y() - (ncy - self.items_by_id[anchor.id].h / 2))
        elif self.shown and self.layout_root.id in self.shown:
            cur = self.items_by_id[self.layout_root.id].pos()
            nx, ncy = pos[self.layout_root.id]
            off = QPointF(cur.x() - nx, cur.y() - (ncy - self.items_by_id[self.layout_root.id].h / 2))

        target = {}
        for n in visible:
            it = self.items_by_id[n.id]
            x, cy = pos[n.id]
            target[n.id] = QPointF(x, cy - it.h / 2) + off

        new_ids = set(target)
        tracks = {}
        do_anim = animate and self.animations_enabled and bool(self.shown)
        for nid, tgt in target.items():
            it = self.items_by_id[nid]
            if nid in self.shown:
                tracks[nid] = (it.pos(), tgt, it.opacity(), 1.0, it.scale(), 1.0)
            else:
                # grow out of the nearest ancestor that is currently on screen
                src = tgt
                anc = next((a for a in it.node.ancestors() if a.id in self.shown), None)
                if anc is not None:
                    ai = self.items_by_id[anc.id]
                    o = ai.anchor_out()
                    src = QPointF(o.x() - 8, o.y() - it.h / 2)
                tracks[nid] = (src, tgt, 0.0, 1.0, 0.4, 1.0)
                it.setVisible(True)
        for nid in self.shown - new_ids:
            it = self.items_by_id[nid]
            anc = next((a for a in it.node.ancestors() if a.id in new_ids), None)
            dst = it.pos()
            if anc is not None:
                ap = target[anc.id]
                ai = self.items_by_id[anc.id]
                dst = QPointF(ap.x() + ai.w + TOGGLE_DX - 4, ap.y() + ai.h / 2 - it.h / 2)
            tracks[nid] = (it.pos(), dst, it.opacity(), 0.0, it.scale(), 0.4)

        self.shown = new_ids
        self._tracks = tracks
        for it in self.items_by_id.values():
            it.update()
        if do_anim:
            self._anim.start()
        else:
            self._anim_step(1.0)
            self._anim_done()
        self.controls.update_all_icon()

    def _anim_step(self, t):
        t = float(t)
        for nid, (p0, p1, o0, o1, s0, s1) in self._tracks.items():
            it = self.items_by_id[nid]
            it.setPos(p0 + (p1 - p0) * t)
            it.setOpacity(o0 + (o1 - o0) * t)
            it.setScale(s0 + (s1 - s0) * t)
        self._refresh_edges()

    def _anim_done(self):
        for nid, tr in self._tracks.items():
            it = self.items_by_id[nid]
            if nid not in self.shown:
                it.setVisible(False)
            it.setOpacity(1.0 if nid in self.shown else 0.0)
            it.setScale(1.0)
        self._tracks = {}
        self._refresh_edges()
        self.mapChanged.emit()
        cb, self._after = getattr(self, "_after", None), None
        if cb:
            cb()

    def _refresh_edges(self):
        for nid, e in self.edges_by_id.items():
            if self.items_by_id[nid].node is self.layout_root:
                e.setVisible(False)
                continue
            e.refresh()

    # ------------------------------------------------------------------
    # Mouse & keyboard
    # ------------------------------------------------------------------
    def _node_item_at(self, view_pt) -> Optional[NodeItem]:
        sp = self.mapToScene(view_pt)
        for it in self.scene_.items(sp):
            if isinstance(it, NodeItem) and it.isVisible() and it.node.id in self.shown:
                if it.hit_body(sp) or it.hit_toggle(sp):
                    return it
        return None

    def mousePressEvent(self, e):
        if e.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._press_pos = e.position()
            self._last_pos = e.position()
            self._dragging = False
            self._press_item = self._node_item_at(e.position().toPoint()) if e.button() == Qt.LeftButton else None
            self.setFocus()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press_pos is not None:
            if not self._dragging and (e.position() - self._press_pos).manhattanLength() > 4:
                self._dragging = True
                self._cam.stop()
                self.viewport().setCursor(Qt.ClosedHandCursor)
            if self._dragging:
                d = e.position() - self._last_pos
                self._last_pos = e.position()
                hb, vb = self.horizontalScrollBar(), self.verticalScrollBar()
                hb.setValue(hb.value() - round(d.x()))
                vb.setValue(vb.value() - round(d.y()))
                e.accept()
                return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._press_pos is None:
            return super().mouseReleaseEvent(e)
        was_drag = self._dragging
        self._press_pos = None
        self._dragging = False
        self.viewport().unsetCursor()
        if was_drag or e.button() != Qt.LeftButton:
            return
        it = self._press_item
        if it is None:
            self._select(None)
            return
        sp = self.mapToScene(e.position().toPoint())
        if it.hit_toggle(sp):
            self._select(it.node)
            self.toggle(it.node)
        elif it.hit_body(sp):
            if e.modifiers() & Qt.ControlModifier and it.node.link:
                QDesktopServices.openUrl(QUrl(it.node.link))
            self._select(it.node)

    def mouseDoubleClickEvent(self, e):
        it = self._node_item_at(e.position().toPoint())
        if it is not None and it.hit_body(self.mapToScene(e.position().toPoint())):
            if it.node.children:
                self.toggle(it.node)
            else:
                self.center_on_node(it.node)
            e.accept()
            return
        if it is None:
            self.fit(animate=True)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ShiftModifier or (
                not e.pixelDelta().isNull() and not (e.modifiers() & Qt.ControlModifier)
                and abs(e.angleDelta().y()) < 60 and e.angleDelta().x() != 0):
            # trackpad two-finger scroll / shift+wheel pans
            d = e.pixelDelta() if not e.pixelDelta().isNull() else e.angleDelta() / 4
            hb, vb = self.horizontalScrollBar(), self.verticalScrollBar()
            if e.modifiers() & Qt.ShiftModifier and d.x() == 0:
                hb.setValue(hb.value() - d.y())
            else:
                hb.setValue(hb.value() - d.x())
                vb.setValue(vb.value() - d.y())
            return
        delta = e.angleDelta().y()
        if delta == 0:
            return
        self._cam.stop()
        self.zoom_by(math.pow(1.0015, delta), e.position().toPoint(), animate=False)

    def contextMenuEvent(self, e):
        it = self._node_item_at(e.pos())
        m = QMenu(self)
        if it is not None:
            n = it.node
            self._select(n)
            if n.children:
                m.addAction("Collapse" if not n.collapsed else "Expand", lambda: self.toggle(n))
                m.addAction("Expand whole branch", lambda: self.set_collapsed(n, False, recursive=True))
                m.addAction("Collapse whole branch", lambda: self.set_collapsed(n, True, recursive=True))
                m.addSeparator()
                m.addAction("Focus on this branch only", lambda: self.isolate(n))
            m.addAction("Centre on this topic", lambda: self.center_on_node(n))
            m.addSeparator()
            m.addAction("Copy text", lambda: QGuiApplication.clipboard().setText(n.text))
            m.addAction("Copy path", lambda: QGuiApplication.clipboard().setText(
                " > ".join(x.text for x in n.path())))
            m.addAction("Copy branch as Markdown",
                        lambda: QGuiApplication.clipboard().setText(parsers.to_markdown(n, keep_folds=False)))
            if n.link:
                m.addAction("Open link", lambda: QDesktopServices.openUrl(QUrl(n.link)))
        else:
            m.addAction("Fit to window", lambda: self.fit(animate=True))
            m.addAction("Expand all", self.expand_all)
            m.addAction("Collapse all", self.collapse_all)
            lv = m.addMenu("Show levels")
            for i in range(1, 6):
                lv.addAction(f"{i} level{'s' if i > 1 else ''}", lambda i=i: self.expand_to_level(i))
        if self.is_isolated:
            m.addSeparator()
            m.addAction("Back to full map", self.show_full_map)
        m.exec(e.globalPos())

    def keyPressEvent(self, e):
        k = e.key()
        n = self.selected
        if k in (Qt.Key_Plus, Qt.Key_Equal):
            return self.zoom_in()
        if k in (Qt.Key_Minus, Qt.Key_Underscore):
            return self.zoom_out()
        if k in (Qt.Key_F, Qt.Key_0):
            return self.fit(animate=True)
        if k == Qt.Key_E:
            return self.toggle_all()
        if k == Qt.Key_Escape:
            if self.is_isolated:
                return self.show_full_map()
            return self._select(None)
        if k == Qt.Key_Home:
            self._select(self.layout_root)
            return self.center_on_node(self.layout_root)
        if n is None and k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self._select(self.layout_root)
            return self.ensure_node_visible(self.layout_root)
        if n is None:
            return super().keyPressEvent(e)
        if k in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            return self.toggle(n)
        target = None
        if k == Qt.Key_Left:
            if n.children and not n.collapsed and e.modifiers() & Qt.ShiftModifier:
                return self.toggle(n)
            if n is not self.layout_root:
                target = n.parent
        elif k == Qt.Key_Right:
            if n.children:
                if n.collapsed:
                    return self.toggle(n)
                target = n.children[0]
        elif k in (Qt.Key_Up, Qt.Key_Down):
            target = self._vertical_neighbour(n, -1 if k == Qt.Key_Up else 1)
        if target is not None:
            self._select(target)
            self.ensure_node_visible(target)
            return
        super().keyPressEvent(e)

    def _vertical_neighbour(self, n: Node, step: int) -> Optional[Node]:
        """Nearest visible node in the same column above/below."""
        if n.id not in self.shown:
            return None
        depth = n.depth
        same = [self.items_by_id[i] for i in self.shown if self.items_by_id[i].node.depth == depth]
        same.sort(key=lambda it: it.y())
        idx = next(i for i, it in enumerate(same) if it.node is n)
        j = idx + step
        if 0 <= j < len(same):
            return same[j].node
        return None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        c = self.controls
        c.adjustSize()
        c.move(self.width() - c.width() - 22, self.height() - c.height() - 22)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_rect(self) -> QRectF:
        r = self.content_rect()
        return r.marginsAdded(QMarginsF(40, 40, 40, 40))

    def _render_into(self, painter: QPainter, target: QRectF, source: QRectF, with_bg=True):
        if with_bg:
            painter.fillRect(target, QColor(self.theme.background))
        sel = self.selected
        self.selected, self.selected_path = None, set()
        hovered = [it for it in self.items_by_id.values() if it.hover]
        for it in hovered:
            it.hover = it.hover_toggle = False
        self._refresh_edges()
        self.scene_.render(painter, target, source)
        self.selected = sel
        self.selected_path = set(sel.path()) if sel else set()
        self._refresh_edges()

    def export_png(self, path: str, scale: float = 2.0, transparent: bool = False) -> bool:
        src = self._export_rect()
        w, h = int(src.width() * scale), int(src.height() * scale)
        # keep memory reasonable for huge maps
        maxdim = 16000
        if max(w, h) > maxdim:
            f = maxdim / max(w, h)
            w, h = int(w * f), int(h * f)
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self._render_into(p, QRectF(0, 0, w, h), src, with_bg=not transparent)
        p.end()
        return img.save(path)

    def export_svg(self, path: str) -> bool:
        from PySide6.QtSvg import QSvgGenerator
        src = self._export_rect()
        gen = QSvgGenerator()
        gen.setFileName(path)
        gen.setSize(QSize(int(src.width()), int(src.height())))
        gen.setViewBox(QRectF(0, 0, src.width(), src.height()))
        gen.setTitle(self.layout_root.text if self.layout_root else "Mind map")
        p = QPainter(gen)
        self._render_into(p, QRectF(0, 0, src.width(), src.height()), src)
        p.end()
        return True

    def export_pdf(self, path: str) -> bool:
        src = self._export_rect()
        w = QPdfWriter(path)
        w.setResolution(96)
        w.setPageSize(QPageSize(QSizeF(src.width(), src.height()), QPageSize.Point))
        w.setPageMargins(QMarginsF(0, 0, 0, 0))
        p = QPainter(w)
        tgt = QRectF(0, 0, w.width(), w.height())
        self._render_into(p, tgt, src)
        p.end()
        return True
