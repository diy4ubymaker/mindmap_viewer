"""Parsers and writers for the supported mind map text formats.

Supported inputs
----------------
* Markdown  - ``#`` headings and/or ``-`` / ``*`` / ``+`` / ``1.`` bullets (markmap style)
* Plain text - one topic per line, hierarchy given by indentation (tabs or spaces)
* Mermaid    - ``mindmap`` diagrams (``root((Title))``, ``id[Text]`` ...)
* OPML       - ``<outline text="...">`` (exported by most outliners / mind map tools)
* FreeMind / Freeplane ``.mm``
* XMind ``.xmind`` (XMind Zen ``content.json`` and legacy ``content.xml``)
* JSON       - ``{"text"/"name"/"title"/"topic": ..., "children": [...]}``, jsMind
               ``{"data": {...}}``, or plain nested dicts / lists

Fold markers: a line containing ``<!-- fold -->`` or ``<!-- markmap: fold -->``
starts that branch collapsed.
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Callable, Dict, List, Optional, Tuple

from .model import Node

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


class ParseError(ValueError):
    pass


# ----------------------------------------------------------------------------
# Inline markdown clean-up
# ----------------------------------------------------------------------------
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_FOLD_RE = re.compile(r"<!--\s*(?:markmap:\s*)?fold(?:All)?\s*-->", re.I)
_COMMENT_RE = re.compile(r"<!--.*?-->")
_TAG_RE = re.compile(r"<[^>]+>")


def clean_inline(text: str) -> Tuple[str, str]:
    """Strip inline markdown. Returns (plain_text, first_link_url)."""
    link = ""
    m = _LINK_RE.search(text)
    if m:
        link = m.group(2)
    text = _LINK_RE.sub(r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)  # images
    text = _COMMENT_RE.sub("", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    if not link:
        m = re.search(r"https?://\S+", text)
        if m:
            link = m.group(0).rstrip(").,;")
    return re.sub(r"\s+", " ", text).strip(), link


# ----------------------------------------------------------------------------
# Generic tree builder from (level, text) entries
# ----------------------------------------------------------------------------
class _Builder:
    def __init__(self):
        self.top: List[Node] = []
        self.stack: List[Tuple[float, Node]] = []

    def add(self, level: float, raw: str, fold: bool = False) -> Optional[Node]:
        text, link = clean_inline(raw)
        if not text:
            return None
        node = Node(text, link=link, collapsed=fold)
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        if self.stack:
            self.stack[-1][1].add(node)
        else:
            self.top.append(node)
        self.stack.append((level, node))
        return node

    def add_note(self, raw: str):
        if self.stack:
            n = self.stack[-1][1]
            t, _ = clean_inline(raw)
            if t:
                n.note = (n.note + "\n" + t).strip()

    def root(self, title: str = "Mind Map") -> Node:
        if not self.top:
            raise ParseError("No topics were found in the input.")
        if len(self.top) == 1:
            r = self.top[0]
        else:
            r = Node(title)
            for t in self.top:
                r.add(t)
        r.parent = None
        return r.relink()


# ----------------------------------------------------------------------------
# Markdown / indented outline
# ----------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET_RE = re.compile(r"^([-*+•▪●◦‣⁃]|\d+[.)]|[a-zA-Z][.)](?=\s))\s+(.*)$")
_HR_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_TABLE_RE = re.compile(r"^\s*\|")


def _indent_width(line: str) -> int:
    w = 0
    for ch in line:
        if ch == " ":
            w += 1
        elif ch == "\t":
            w += 4
        else:
            break
    return w


def parse_outline(text: str, title: str = "Mind Map") -> Node:
    """Markdown headings + bullets, or plain indented text."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # YAML front matter
    fm_title = None
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                for fl in lines[1:i]:
                    m = re.match(r"\s*title\s*:\s*(.+)", fl)
                    if m:
                        fm_title = m.group(1).strip().strip("'\"")
                lines = lines[i + 1:]
                break

    b = _Builder()
    heading_level = 0           # level of last heading (0 = none)
    indent_stack: List[int] = []  # indentation columns of the current list block
    in_fence = False
    in_comment = False
    prev_blank = True
    last_kind = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if stripped.startswith("<!--") and "-->" not in stripped:
            in_comment = True
            continue
        if not stripped:
            prev_blank = True
            continue
        if _HR_RE.match(line) or _TABLE_RE.match(line):
            continue
        fold = bool(_FOLD_RE.search(line))
        if fold:
            line = _FOLD_RE.sub("", line)
            stripped = line.strip()
            if not stripped:
                # a standalone fold marker applies to the last node
                if b.stack:
                    b.stack[-1][1].collapsed = True
                continue

        m = _HEADING_RE.match(stripped)
        if m and _indent_width(line) < 4:
            heading_level = len(m.group(1))
            indent_stack = []
            b.add(heading_level * 1000, m.group(2), fold)
            last_kind = "heading"
            prev_blank = False
            continue

        ind = _indent_width(line)
        bm = _BULLET_RE.match(stripped)
        content = bm.group(2) if bm else stripped
        # task-list checkboxes
        content = re.sub(r"^\[[ xX]\]\s+", "", content)

        # A non-bullet line directly continuing a bullet (no blank line, deeper or equal
        # indentation) in a markdown document is treated as a note on that bullet.
        if (not bm and last_kind == "bullet" and not prev_blank
                and indent_stack and ind > indent_stack[-1]):
            b.add_note(content)
            continue

        while indent_stack and indent_stack[-1] > ind:
            indent_stack.pop()
        if not indent_stack or indent_stack[-1] < ind:
            indent_stack.append(ind)
        level = heading_level * 1000 + len(indent_stack)
        b.add(level, content, fold)
        last_kind = "bullet" if bm else "plain"
        prev_blank = False

    return b.root(fm_title or title)


# ----------------------------------------------------------------------------
# Mermaid mindmap
# ----------------------------------------------------------------------------
_MERMAID_SHAPE = re.compile(
    r"^(?:[\w-]+)?\s*(\(\(\(|\(\(|\)\)|\[|\(-|\(|\)|\{\{|>)(.*?)(\)\)\)|\)\)|\(\(|\]|-\)|\)|\(|\}\})\s*$"
)


def parse_mermaid(text: str, title: str = "Mind Map") -> Node:
    lines = text.replace("\r\n", "\n").split("\n")
    b = _Builder()
    started = False
    for line in lines:
        s = line.strip()
        if not s or s.startswith("%%"):
            continue
        if not started:
            if s.lower().startswith("mindmap"):
                started = True
            continue
        if s.startswith("::icon") or s.startswith(":::"):
            continue
        s = re.sub(r":::\S+.*$", "", s).strip()
        m = _MERMAID_SHAPE.match(s)
        label = m.group(2) if m else s
        label = label.strip()
        if len(label) >= 2 and label[0] == label[-1] and label[0] in "\"'":
            label = label[1:-1]
        if label.startswith("`") and label.endswith("`"):
            label = label[1:-1]
        label = label.replace("<br/>", " ").replace("<br>", " ")
        b.add(_indent_width(line), label)
    if not started:
        raise ParseError("Not a Mermaid mindmap (missing 'mindmap' line).")
    return b.root(title)


# ----------------------------------------------------------------------------
# XML based: OPML, FreeMind / Freeplane
# ----------------------------------------------------------------------------
def _xml_text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", s or ""))).strip()


def parse_opml(text: str, title: str = "Mind Map") -> Node:
    try:
        root_el = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError as e:
        raise ParseError(f"Invalid OPML: {e}")
    body = root_el.find("body")
    if body is None:
        raise ParseError("OPML has no <body>.")
    t = root_el.findtext("head/title") or title

    def conv(el) -> Node:
        n = Node(_xml_text(el.get("text") or el.get("title") or ""),
                 note=_xml_text(el.get("_note") or ""),
                 link=el.get("url") or el.get("htmlUrl") or "")
        for c in el.findall("outline"):
            n.add(conv(c))
        return n

    tops = [conv(o) for o in body.findall("outline")]
    if not tops:
        raise ParseError("OPML has no outlines.")
    if len(tops) == 1:
        return tops[0].relink()
    r = Node(t)
    for x in tops:
        r.add(x)
    return r.relink()


def parse_freemind(text: str, title: str = "Mind Map") -> Node:
    try:
        root_el = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError as e:
        raise ParseError(f"Invalid FreeMind file: {e}")
    top = root_el.find("node")
    if top is None:
        raise ParseError("FreeMind map has no <node>.")

    def conv(el) -> Node:
        txt = el.get("TEXT") or el.get("LOCALIZED_TEXT") or ""
        note = ""
        for rc in el.findall("richcontent"):
            content = _xml_text(ET.tostring(rc, encoding="unicode", method="html"))
            if (rc.get("TYPE") or "").upper() == "NODE" and not txt:
                txt = content
            elif content:
                note = content
        n = Node(_xml_text(txt), note=note, link=el.get("LINK") or "",
                 collapsed=(el.get("FOLDED") == "true"))
        for c in el.findall("node"):
            n.add(conv(c))
        return n

    return conv(top).relink()


# ----------------------------------------------------------------------------
# JSON (generic)
# ----------------------------------------------------------------------------
_TEXT_KEYS = ("text", "name", "title", "topic", "label", "content", "value", "id")
_CHILD_KEYS = ("children", "nodes", "items", "subtopics", "subTopics", "topics", "branches")


def _json_to_node(obj, name: Optional[str] = None) -> Node:
    if isinstance(obj, dict):
        tk = next((k for k in _TEXT_KEYS if isinstance(obj.get(k), (str, int, float))), None)
        ck = next((k for k in _CHILD_KEYS if k in obj), None)
        if tk or ck:
            n = Node(str(obj.get(tk, name or "")) if tk else (name or ""))
            n.note = str(obj.get("note") or obj.get("notes") or "")
            n.link = str(obj.get("link") or obj.get("url") or obj.get("href") or "")
            n.collapsed = bool(obj.get("collapsed") or obj.get("folded")
                               or obj.get("expanded") is False)
            kids = obj.get(ck) if ck else []
            if isinstance(kids, dict) and "attached" in kids:  # XMind
                kids = kids["attached"]
            if isinstance(kids, dict):
                for k, v in kids.items():
                    n.add(_json_to_node(v, k))
            elif isinstance(kids, list):
                for v in kids:
                    n.add(_json_to_node(v))
            return n
        # plain mapping {"Topic": {...} | [...] | "leaf"}
        n = Node(name or "Mind Map")
        for k, v in obj.items():
            if v is None or v == {} or v == []:
                n.add(Node(str(k)))
            elif isinstance(v, (str, int, float, bool)):
                c = n.add(Node(str(k)))
                c.add(Node(str(v)))
            else:
                n.add(_json_to_node(v, str(k)))
        return n
    if isinstance(obj, list):
        n = Node(name or "Mind Map")
        for v in obj:
            n.add(_json_to_node(v))
        return n
    return Node(str(obj))


def parse_json(text: str, title: str = "Mind Map") -> Node:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}")
    if isinstance(data, dict) and isinstance(data.get("data"), dict) and "meta" in data:
        data = data["data"]  # jsMind
    if isinstance(data, dict) and isinstance(data.get("rootTopic"), dict):
        data = data["rootTopic"]
    if isinstance(data, list) and data and isinstance(data[0], dict) and "rootTopic" in data[0]:
        data = data[0]["rootTopic"]  # XMind content.json
    if isinstance(data, dict) and len(data) == 1 and not any(k in data for k in _TEXT_KEYS + _CHILD_KEYS):
        (k, v), = data.items()
        root = _json_to_node(v, k)
    else:
        root = _json_to_node(data, title)
    if not root.text:
        root.text = title
    return root.relink()


# ----------------------------------------------------------------------------
# XMind
# ----------------------------------------------------------------------------
def parse_xmind(data: bytes, title: str = "Mind Map") -> Node:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ParseError("Not a valid .xmind file.")
    names = z.namelist()
    if "content.json" in names:
        sheets = json.loads(z.read("content.json").decode("utf-8"))
        rt = sheets[0]["rootTopic"]

        def conv(t) -> Node:
            n = Node(_xml_text(t.get("title", "")), collapsed=t.get("branch") == "folded",
                     link=t.get("href", "") or "")
            for c in (t.get("children") or {}).get("attached", []) or []:
                n.add(conv(c))
            return n
        return conv(rt).relink()
    if "content.xml" in names:
        x = z.read("content.xml").decode("utf-8")
        x = re.sub(r'\sxmlns(:\w+)?="[^"]+"', "", x)
        x = re.sub(r"<(/?)\w+:", r"<\1", x)
        root_el = ET.fromstring(x)
        topic = root_el.find(".//sheet/topic")

        def conv_x(el) -> Node:
            n = Node(_xml_text(el.findtext("title") or ""), collapsed=el.get("branch") == "folded")
            for c in el.findall("children/topics/topic"):
                n.add(conv_x(c))
            return n
        if topic is None:
            raise ParseError("XMind file has no topics.")
        return conv_x(topic).relink()
    raise ParseError("Unsupported .xmind file layout.")


# ----------------------------------------------------------------------------
# Detection / dispatch
# ----------------------------------------------------------------------------
FORMATS: Dict[str, Callable[[str, str], Node]] = {
    "markdown": parse_outline,
    "text": parse_outline,
    "mermaid": parse_mermaid,
    "opml": parse_opml,
    "freemind": parse_freemind,
    "json": parse_json,
}

EXT_FORMAT = {
    ".md": "markdown", ".markdown": "markdown", ".mdown": "markdown",
    ".txt": "text", ".text": "text", ".outline": "text",
    ".mmd": "mermaid", ".mermaid": "mermaid",
    ".opml": "opml", ".mm": "freemind", ".json": "json",
}


def detect_format(text: str) -> str:
    s = text.lstrip("﻿ \t\r\n")
    head = s[:500].lower()
    if s.startswith("{") or s.startswith("["):
        return "json"
    if "<opml" in head:
        return "opml"
    if "<map" in head and "<node" in s[:4000].lower():
        return "freemind"
    first = next((l.strip() for l in s.splitlines() if l.strip() and not l.strip().startswith("%%")), "")
    if first.lower().startswith("mindmap"):
        return "mermaid"
    if first.startswith("```mermaid"):
        return "mermaid"
    return "markdown"


def parse_text(text: str, fmt: str = "auto", title: str = "Mind Map") -> Node:
    text = text.lstrip("﻿")
    if fmt == "auto":
        fmt = detect_format(text)
    if fmt == "mermaid":
        text = re.sub(r"^\s*```mermaid\s*\n|```\s*$", "", text.strip())
    parser = FORMATS.get(fmt)
    if parser is None:
        raise ParseError(f"Unknown format: {fmt}")
    root = parser(text, title)
    _drop_empty(root)
    return root


def _drop_empty(n: Node):
    n.children = [c for c in n.children if c.text or c.children]
    for c in n.children:
        if not c.text:
            c.text = "(untitled)"
        _drop_empty(c)


def read_text_file(path: str) -> str:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            txt = raw.decode(enc)
            if enc == "utf-16" and not raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
                continue
            return txt
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def parse_file(path: str) -> Tuple[Node, str, str]:
    """Parse a file. Returns (root, source_text, format)."""
    ext = os.path.splitext(path)[1].lower()
    title = os.path.splitext(os.path.basename(path))[0]
    if ext == ".xmind":
        root = parse_xmind(open(path, "rb").read(), title)
        return root, to_markdown(root), "markdown"
    if ext in IMAGE_EXTS:
        raise ParseError("Images must be converted with 'Import from image (AI)'.")
    text = read_text_file(path)
    fmt = EXT_FORMAT.get(ext, "auto")
    if fmt in ("markdown", "text", "json") and detect_format(text) in ("mermaid", "opml", "freemind", "json"):
        fmt = detect_format(text)
    root = parse_text(text, fmt, title)
    return root, text, (detect_format(text) if fmt == "auto" else fmt)


# ----------------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------------
def to_markdown(root: Node, keep_folds: bool = True) -> str:
    out = [f"# {root.text}", ""]

    def rec(n: Node, lvl: int):
        fold = " <!-- fold -->" if keep_folds and n.collapsed and n.children else ""
        out.append("  " * lvl + f"- {n.text}{fold}")
        for c in n.children:
            rec(c, lvl + 1)
    for c in root.children:
        rec(c, 0)
    return "\n".join(out) + "\n"


def to_indented_text(root: Node) -> str:
    out = []

    def rec(n: Node, lvl: int):
        out.append("\t" * lvl + n.text)
        for c in n.children:
            rec(c, lvl + 1)
    rec(root, 0)
    return "\n".join(out) + "\n"


def to_mermaid(root: Node) -> str:
    def esc(t: str) -> str:
        return t.replace("(", "&#40;").replace(")", "&#41;").replace("[", "&#91;").replace("]", "&#93;")
    out = ["mindmap", f"  root(({esc(root.text)}))"]

    def rec(n: Node, lvl: int):
        out.append("  " * lvl + esc(n.text))
        for c in n.children:
            rec(c, lvl + 1)
    for c in root.children:
        rec(c, 2)
    return "\n".join(out) + "\n"


def to_opml(root: Node) -> str:
    def rec(n: Node, lvl: int) -> str:
        attrs = f'text="{html.escape(n.text, quote=True)}"'
        if n.note:
            attrs += f' _note="{html.escape(n.note, quote=True)}"'
        pad = "  " * lvl
        if not n.children:
            return f"{pad}<outline {attrs}/>"
        inner = "\n".join(rec(c, lvl + 1) for c in n.children)
        return f"{pad}<outline {attrs}>\n{inner}\n{pad}</outline>"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<opml version="2.0">\n'
            f"  <head><title>{html.escape(root.text)}</title></head>\n  <body>\n"
            f"{rec(root, 2)}\n  </body>\n</opml>\n")


def to_json(root: Node) -> str:
    def rec(n: Node) -> dict:
        d = {"text": n.text}
        if n.note:
            d["note"] = n.note
        if n.link:
            d["link"] = n.link
        if n.collapsed and n.children:
            d["collapsed"] = True
        if n.children:
            d["children"] = [rec(c) for c in n.children]
        return d
    return json.dumps(rec(root), indent=2, ensure_ascii=False) + "\n"


def to_freemind(root: Node) -> str:
    def rec(n: Node, lvl: int) -> str:
        pad = "  " * lvl
        folded = ' FOLDED="true"' if n.collapsed and n.children else ""
        attrs = f'TEXT="{html.escape(n.text, quote=True)}"{folded}'
        if not n.children:
            return f"{pad}<node {attrs}/>"
        inner = "\n".join(rec(c, lvl + 1) for c in n.children)
        return f"{pad}<node {attrs}>\n{inner}\n{pad}</node>"
    return f'<map version="1.0.1">\n{rec(root, 1)}\n</map>\n'


WRITERS = {
    "Markdown (*.md)": (".md", to_markdown),
    "Indented text (*.txt)": (".txt", to_indented_text),
    "Mermaid mindmap (*.mmd)": (".mmd", to_mermaid),
    "OPML (*.opml)": (".opml", to_opml),
    "FreeMind (*.mm)": (".mm", to_freemind),
    "JSON (*.json)": (".json", to_json),
}
