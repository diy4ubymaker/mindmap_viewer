"""Left-to-right tidy tree layout (NotebookLM / markmap style).

* Every depth gets its own column; column x is driven by the widest visible
  node in the previous column, so siblings line up neatly.
* Leaves are stacked top-to-bottom; a parent is centred on its children.
* Sibling sub-trees that are expanded get a little extra breathing room.
"""
from __future__ import annotations

from typing import Callable, Dict, Tuple

from .model import Node

Size = Tuple[float, float]


def compute_layout(root: Node, size_of: Callable[[Node], Size],
                   h_gap: float = 64.0, v_gap: float = 10.0, group_gap: float = 18.0,
                   toggle_space: float = 30.0) -> Dict[int, Tuple[float, float]]:
    """Return {node.id: (left_x, centre_y)} for every visible node."""
    base = root.depth
    visible = list(root.visible())
    sizes = {n.id: size_of(n) for n in visible}

    # ---- columns -------------------------------------------------------
    max_w: Dict[int, float] = {}
    for n in visible:
        d = n.depth - base
        max_w[d] = max(max_w.get(d, 0.0), sizes[n.id][0])
    col_x = {0: 0.0}
    for d in range(1, max(max_w) + 1):
        col_x[d] = col_x[d - 1] + max_w[d - 1] + toggle_space + h_gap

    # ---- rows ----------------------------------------------------------
    ys: Dict[int, float] = {}

    def kids(n: Node):
        return [] if n.collapsed else n.children

    def shift(n: Node, dy: float):
        ys[n.id] += dy
        for c in kids(n):
            shift(c, dy)

    def place(n: Node, top: float) -> float:
        h = sizes[n.id][1]
        ks = kids(n)
        if not ks:
            ys[n.id] = top + h / 2
            return top + h
        cur = top
        prev = None
        for c in ks:
            if prev is not None:
                cur += v_gap
                if kids(c) or kids(prev):
                    cur += group_gap
            cur = place(c, cur)
            prev = c
        centre = (ys[ks[0].id] + ys[ks[-1].id]) / 2
        bottom = cur
        if centre - h / 2 < top:  # node taller than its children's span
            dy = top - (centre - h / 2)
            for c in ks:
                shift(c, dy)
            centre += dy
            bottom += dy
        ys[n.id] = centre
        return max(bottom, centre + h / 2)

    place(root, 0.0)
    oy = ys[root.id]
    return {n.id: (col_x[n.depth - base], ys[n.id] - oy) for n in visible}
