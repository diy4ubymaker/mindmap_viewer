"""Convert a mind map *image* into a Markdown outline using Claude's vision API.

Only the Python standard library is used (urllib), so no extra packages are
required. The API key is read from the app settings or the ANTHROPIC_API_KEY
environment variable.
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"

PROMPT = """This image is a mind map (or a tree / outline diagram).
Transcribe it into a nested Markdown outline that reproduces the hierarchy exactly.

Rules:
- First line: "# " followed by the central / root topic.
- Every other topic is a "- " bullet, indented by two spaces per level below the root.
- Copy the wording of every node exactly as written; do not summarise, merge or invent topics.
- Keep the top-to-bottom order of siblings as they appear in the image.
- If a branch is shown collapsed (e.g. a ">" or "+" marker with no visible children),
  write the node and append " <!-- fold -->" to it.
- Output ONLY the Markdown outline, with no explanations and no code fences."""


class AIImportError(RuntimeError):
    pass


def _prepare_image(path: str, max_side: int = 3000):
    """Return (media_type, base64_data); downscale/re-encode large images with Qt if available."""
    ext = os.path.splitext(path)[1].lower()
    media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".webp": "image/webp", ".gif": "image/gif"}.get(ext)
    raw = open(path, "rb").read()
    needs_qt = media is None or len(raw) > 3_700_000
    try:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
        from PySide6.QtGui import QImage
        img = QImage(path)
        if not img.isNull() and max(img.width(), img.height()) > max_side:
            needs_qt = True
        if needs_qt and not img.isNull():
            if max(img.width(), img.height()) > max_side:
                img = img.scaled(max_side, max_side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            for fmt, mt, q in (("PNG", "image/png", -1), ("JPG", "image/jpeg", 92), ("JPG", "image/jpeg", 80)):
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QIODevice.WriteOnly)
                img.save(buf, fmt, q)
                buf.close()
                if ba.size() <= 3_700_000:
                    return mt, base64.b64encode(bytes(ba)).decode("ascii")
    except ImportError:
        pass
    if media is None:
        raise AIImportError(f"Unsupported image type: {ext}")
    if len(raw) > 3_700_000:
        raise AIImportError("Image is larger than the 3.7 MB the API accepts; please resize it.")
    return media, base64.b64encode(raw).decode("ascii")


def _encode_qimage(img, max_side: int = 1568):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    if max(img.width(), img.height()) > max_side:
        img = img.scaled(max_side, max_side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    for fmt, mt, q in (("PNG", "image/png", -1), ("JPG", "image/jpeg", 90), ("JPG", "image/jpeg", 75)):
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        img.save(buf, fmt, q)
        buf.close()
        if ba.size() <= 3_700_000:
            return mt, base64.b64encode(bytes(ba)).decode("ascii")
    raise AIImportError("Could not encode image small enough for the API.")


def prepare_images(path: str):
    """Return a list of (media_type, b64) images: an overview plus, for large
    pictures, overlapping zoomed-in slices so small node text stays legible."""
    try:
        from PySide6.QtGui import QImage
    except ImportError:
        return [_prepare_image(path)]
    img = QImage(path)
    if img.isNull():
        return [_prepare_image(path)]
    out = [_encode_qimage(img)]
    w, h = img.width(), img.height()
    long_side, short_side = max(w, h), min(w, h)
    if long_side <= 2000:
        return out
    tile_len = max(int(short_side * 0.7), 1200)
    overlap = int(tile_len * 0.12)
    step = tile_len - overlap
    pos = 0
    while pos < long_side and len(out) < 12:
        end = min(pos + tile_len, long_side)
        crop = img.copy(0, pos, w, end - pos) if h >= w else img.copy(pos, 0, end - pos, h)
        out.append(_encode_qimage(crop))
        if end >= long_side:
            break
        pos += step
    return out


TILE_NOTE = """

Image 1 shows the whole mind map; use it for the overall structure.
Images 2-{n} are overlapping zoomed-in slices of the same picture, in order from {dir}.
Use them to read small text accurately. Topics that appear in two neighbouring slices are the
same topic - list each topic only once."""


def image_to_markdown(path: str, api_key: str, model: str = DEFAULT_MODEL, timeout: int = 240) -> str:
    if not api_key:
        raise AIImportError("No API key configured. Add your Anthropic API key in Settings "
                            "or set the ANTHROPIC_API_KEY environment variable.")
    images = prepare_images(path)
    prompt = PROMPT
    if len(images) > 1:
        try:
            from PySide6.QtGui import QImageReader
            sz = QImageReader(path).size()
            tall = sz.height() >= sz.width()
        except Exception:
            tall = True
        prompt += TILE_NOTE.format(n=len(images), dir="top to bottom" if tall else "left to right")
    content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": d}}
               for mt, d in images]
    content.append({"type": "text", "text": prompt})
    body = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": 16000,
        "messages": [{"role": "user", "content": content}],
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise AIImportError(f"API error {e.code}: {msg or e.reason}")
    except urllib.error.URLError as e:
        raise AIImportError(f"Could not reach the API: {e.reason}")
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    text = re.sub(r"^```(?:markdown|md)?\s*\n|\n```\s*$", "", text.strip())
    if not text.strip():
        raise AIImportError("The model returned an empty response.")
    return text.strip() + "\n"
