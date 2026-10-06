"""Tree model for mind maps (Qt-free, so it can be unit tested anywhere)."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

_ids = itertools.count(1)


@dataclass(eq=False)
class Node:
    text: str
    children: List["Node"] = field(default_factory=list)
    collapsed: bool = False
    note: str = ""
    link: str = ""
    parent: Optional["Node"] = field(default=None, repr=False)
    id: int = field(default_factory=lambda: next(_ids))

    # ---- construction -------------------------------------------------
    def add(self, child: "Node | str") -> "Node":
        if isinstance(child, str):
            child = Node(child)
        child.parent = self
        self.children.append(child)
        return child

    def relink(self) -> "Node":
        """Make sure every child's parent pointer is correct."""
        for c in self.children:
            c.parent = self
            c.relink()
        return self

    # ---- queries ------------------------------------------------------
    @property
    def depth(self) -> int:
        d, n = 0, self.parent
        while n is not None:
            d, n = d + 1, n.parent
        return d

    @property
    def has_children(self) -> bool:
        return bool(self.children)

    def walk(self) -> Iterator["Node"]:
        yield self
        for c in self.children:
            yield from c.walk()

    def visible(self) -> Iterator["Node"]:
        """Nodes that are shown given the current collapsed state."""
        yield self
        if not self.collapsed:
            for c in self.children:
                yield from c.visible()

    def ancestors(self) -> List["Node"]:
        out, n = [], self.parent
        while n is not None:
            out.append(n)
            n = n.parent
        return out

    def path(self) -> List["Node"]:
        return list(reversed(self.ancestors())) + [self]

    def path_key(self) -> tuple:
        return tuple(n.text for n in self.path())

    def count(self) -> int:
        return sum(1 for _ in self.walk())

    def max_depth(self) -> int:
        return max(n.depth for n in self.walk())

    # ---- state helpers ------------------------------------------------
    def set_collapsed_recursive(self, collapsed: bool, include_self: bool = True):
        for n in self.walk():
            if n is self and not include_self:
                continue
            if n.children:
                n.collapsed = collapsed

    def expand_to_level(self, level: int):
        """Show nodes up to depth `level` (root = 0)."""
        base = self.depth
        for n in self.walk():
            if n.children:
                n.collapsed = (n.depth - base) >= level

    def reveal(self):
        """Expand all ancestors so this node becomes visible."""
        for a in self.ancestors():
            a.collapsed = False

    def collapsed_keys(self) -> set:
        return {n.path_key() for n in self.walk() if n.collapsed}

    def apply_collapsed_keys(self, keys: set):
        for n in self.walk():
            if n.children:
                n.collapsed = n.path_key() in keys
