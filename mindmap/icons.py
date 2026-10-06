"""Tiny vector icon set drawn with QPainter (no image assets needed)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _pix(draw, color: str, size: int = 48) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), size * 0.085, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.scale(size / 24.0, size / 24.0)
    pen.setWidthF(2.0)
    p.setPen(pen)
    draw(p)
    p.end()
    return pm


def _poly(p, *pts):
    path = QPainterPath(QPointF(*pts[0]))
    for pt in pts[1:]:
        path.lineTo(QPointF(*pt))
    p.drawPath(path)


DRAW = {
    "plus": lambda p: (p.drawLine(12, 5, 12, 19), p.drawLine(5, 12, 19, 12)),
    "minus": lambda p: p.drawLine(5, 12, 19, 12),
    "expand": lambda p: (_poly(p, (7, 9), (12, 4), (17, 9)), _poly(p, (7, 15), (12, 20), (17, 15))),
    "collapse": lambda p: (_poly(p, (7, 4), (12, 9), (17, 4)), _poly(p, (7, 20), (12, 15), (17, 20))),
    "fit": lambda p: (_poly(p, (4, 9), (4, 4), (9, 4)), _poly(p, (15, 4), (20, 4), (20, 9)),
                      _poly(p, (20, 15), (20, 20), (15, 20)), _poly(p, (9, 20), (4, 20), (4, 15))),
    "download": lambda p: (p.drawLine(12, 4, 12, 15), _poly(p, (7, 10), (12, 15), (17, 10)),
                           _poly(p, (4, 16), (4, 20), (20, 20), (20, 16))),
    "open": lambda p: _poly(p, (3, 19), (3, 5), (9, 5), (11, 7), (20, 7), (20, 10),
                            (7, 10), (3, 19), (18, 19), (21, 10)),
    "edit": lambda p: (_poly(p, (4, 20), (4, 16), (15, 5), (19, 9), (8, 20), (4, 20)),
                       p.drawLine(13, 7, 17, 11)),
    "image": lambda p: (p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2),
                        _poly(p, (3, 17), (9, 11), (14, 16), (16, 14), (21, 18)),
                        p.drawEllipse(QPointF(16, 9), 1.5, 1.5)),
    "theme": lambda p: (p.drawEllipse(QPointF(12, 12), 7, 7), p.save(),
                        p.setBrush(p.pen().color()), p.drawPie(QRectF(5, 5, 14, 14), 90 * 16, 180 * 16),
                        p.restore()),
    "search": lambda p: (p.drawEllipse(QPointF(10.5, 10.5), 6, 6), p.drawLine(15, 15, 20, 20)),
    "save": lambda p: (_poly(p, (4, 4), (17, 4), (20, 7), (20, 20), (4, 20), (4, 4)),
                       _poly(p, (8, 4), (8, 9), (15, 9), (15, 4)), p.drawRect(QRectF(8, 13, 8, 7))),
    "back": lambda p: (_poly(p, (10, 6), (4, 12), (10, 18)), p.drawLine(4, 12, 20, 12)),
    "levels": lambda p: (p.drawLine(4, 6, 9, 6), p.drawLine(9, 12, 14, 12), p.drawLine(14, 18, 20, 18),
                         _poly(p, (6, 6), (6, 12), (9, 12)), _poly(p, (11, 12), (11, 18), (14, 18))),
}


def icon(name: str, color: str = "#d6d9de") -> QIcon:
    ic = QIcon()
    ic.addPixmap(_pix(DRAW[name], color), QIcon.Normal)
    ic.addPixmap(_pix(DRAW[name], "#7d828a"), QIcon.Disabled)
    return ic
