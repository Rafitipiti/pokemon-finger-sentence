"""Texto con acentos y signos de apertura, usando PIL con cache.

cv2.putText solo dibuja ASCII (escribiria "TAJO A?REO"), asi que el texto se
rasteriza una vez con PIL a BGRA y luego se reutiliza desde un cache.
Los colores entran en BGR, como en el resto del proyecto.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from gfx import blit_bgra

_FONT_BOLD = (
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
_FONT_REGULAR = (
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

_fonts: dict[tuple[int, bool], ImageFont.ImageFont] = {}
_cache: dict[tuple, np.ndarray] = {}
_CACHE_MAX = 500


def font(size: int, bold=True):
    key = (int(size), bold)
    got = _fonts.get(key)
    if got is None:
        for path in (_FONT_BOLD if bold else _FONT_REGULAR + _FONT_BOLD):
            try:
                got = ImageFont.truetype(path, int(size))
                break
            except OSError:
                continue
        if got is None:
            got = ImageFont.load_default()
        _fonts[key] = got
    return got


def measure(text: str, size: int, bold=True) -> tuple[int, int]:
    x1, y1, x2, y2 = font(size, bold).getbbox(text)
    return x2 - x1, y2 - y1


def fit_size(text: str, max_w: int, max_h: int, start=48, minimum=9, bold=True) -> int:
    """Mayor tamano de fuente con el que el texto entra en la caja."""
    size = int(start)
    while size > minimum:
        w, h = measure(text, size, bold)
        if w <= max_w and h <= max_h:
            break
        size -= 1
    return size


def render(text: str, size: int, color, bold=True, shadow=True) -> np.ndarray:
    """Rasteriza el texto a BGRA (con cache)."""
    key = (text, int(size), tuple(color), bold, shadow)
    got = _cache.get(key)
    if got is not None:
        return got

    f = font(size, bold)
    x1, y1, x2, y2 = f.getbbox(text)
    pad = 4 if shadow else 2
    w, h = max(1, x2 - x1 + pad * 2), max(1, y2 - y1 + pad * 2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_pil = ImageDraw.Draw(img)
    if shadow:
        draw_pil.text((pad - x1 + 2, pad - y1 + 2), text, font=f, fill=(0, 0, 0, 150))
    rgb = (int(color[2]), int(color[1]), int(color[0]), 255)
    draw_pil.text((pad - x1, pad - y1), text, font=f, fill=rgb)

    bgra = np.array(img)[:, :, [2, 1, 0, 3]].copy()
    if len(_cache) > _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[key] = bgra
    return bgra


def draw(frame, text, pos, size=24, color=(245, 245, 245), bold=True,
         anchor="lt", alpha=1.0, shadow=True):
    """Dibuja texto. `anchor` combina l/c/r con t/m/b (por ejemplo cm = centrado)."""
    if not text:
        return
    bgra = render(text, size, color, bold, shadow)
    h, w = bgra.shape[:2]
    x, y = pos
    if anchor[0] == "c":
        x -= w / 2
    elif anchor[0] == "r":
        x -= w
    if anchor[1] == "m":
        y -= h / 2
    elif anchor[1] == "b":
        y -= h
    blit_bgra(frame, bgra, x, y, alpha)


def split_two_lines(text: str) -> list[str]:
    """Parte un texto de varias palabras en dos lineas lo mas parejas posible."""
    words = text.split()
    if len(words) < 2:
        return [text]
    best, best_score = None, None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = abs(len(a) - len(b))
        if best_score is None or score < best_score:
            best, best_score = [a, b], score
    return best


_plans: dict[tuple, tuple] = {}


def plan_block(text: str, bw: int, bh: int, max_size=44, bold=True, allow_wrap=True):
    """Decide lineas y tamano para una caja. Memoizado: buscar el tamano que
    encaja cuesta varias medidas de fuente y el tablero no cambia de tamano."""
    key = (text, int(bw), int(bh), int(max_size), bold, allow_wrap)
    got = _plans.get(key)
    if got is not None:
        return got

    size = fit_size(text, bw, bh, max_size, bold=bold)
    lines = [text]
    if allow_wrap and " " in text:
        candidate = split_two_lines(text)
        widest = max(candidate, key=lambda s: measure(s, 20, bold)[0])
        two = fit_size(widest, bw, int(bh * 0.46), max_size, bold=bold)
        if two > size:
            lines, size = candidate, two

    if len(_plans) > _CACHE_MAX:
        _plans.clear()
    _plans[key] = (lines, size)
    return lines, size


def draw_block(frame, text, box, color=(245, 245, 245), max_size=44, alpha=1.0,
               bold=True, allow_wrap=True):
    """Texto centrado en la caja, en una o dos lineas (la que permita mas tamano)."""
    x1, y1, x2, y2 = box
    bw, bh = int((x2 - x1) - 16), int((y2 - y1) - 12)
    lines, size = plan_block(text, bw, bh, max_size, bold, allow_wrap)

    line_h = int(size * 1.16)
    cy = (y1 + y2) / 2 - (line_h * len(lines)) / 2 + line_h / 2
    for line in lines:
        draw(frame, line, ((x1 + x2) / 2, cy), size, color, bold, "cm", alpha)
        cy += line_h
