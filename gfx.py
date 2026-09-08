"""Utilidades de dibujo: blits con alpha, rectangulos redondeados, tintes."""

from __future__ import annotations

import cv2
import numpy as np

_MASKS: dict[tuple[int, int, int], np.ndarray] = {}


def blit_bgra(dst, src, x, y, alpha=1.0):
    """Pega una imagen BGRA sobre el frame BGR, recortando en los bordes."""
    if src is None or alpha <= 0:
        return
    sh, sw = src.shape[:2]
    dh, dw = dst.shape[:2]
    x, y = int(x), int(y)
    sx1, sy1 = max(0, -x), max(0, -y)
    dx1, dy1 = max(0, x), max(0, y)
    w = min(sw - sx1, dw - dx1)
    h = min(sh - sy1, dh - dy1)
    if w <= 0 or h <= 0:
        return
    patch = src[sy1:sy1 + h, sx1:sx1 + w]
    region = dst[dy1:dy1 + h, dx1:dx1 + w]

    # Mezcla en 8 bits: hacerlo en float con numpy cuesta unas cinco veces mas,
    # y aqui se pegan decenas de textos por frame.
    a = patch[:, :, 3]
    if alpha < 0.999:
        a = cv2.convertScaleAbs(a, alpha=float(alpha))
    a3 = cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
    cv2.multiply(region, cv2.bitwise_not(a3), region, scale=1 / 255.0)
    cv2.add(region, cv2.multiply(patch[:, :, :3], a3, scale=1 / 255.0), region)


def rounded_mask(w: int, h: int, radius: int) -> np.ndarray:
    """Mascara de esquinas redondeadas (con cache: el tablero no cambia)."""
    w, h = max(1, int(w)), max(1, int(h))
    r = max(0, min(int(radius), w // 2, h // 2))
    key = (w, h, r)
    cached = _MASKS.get(key)
    if cached is not None:
        return cached
    m = np.zeros((h, w), np.uint8)
    if r == 0:
        m[:] = 255
    else:
        cv2.rectangle(m, (r, 0), (w - r, h), 255, -1)
        cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
        for cx, cy in ((r, r), (w - r - 1, r), (r, h - r - 1), (w - r - 1, h - r - 1)):
            cv2.circle(m, (cx, cy), r, 255, -1)
    if len(_MASKS) > 200:
        _MASKS.clear()
    _MASKS[key] = m
    return m


def rounded_rect(img, box, color, alpha=1.0, radius=14):
    """Rectangulo redondeado translucido.

    Se mezcla con operaciones de OpenCV en 8 bits (unas 50 veces mas rapido
    que hacer la mezcla en float con numpy: importa, son 13 recuadros por frame).
    """
    x1, y1, x2, y2 = (int(v) for v in box)
    x1c, y1c = max(0, x1), max(0, y1)
    x2c, y2c = min(img.shape[1], x2), min(img.shape[0], y2)
    if x2c <= x1c or y2c <= y1c:
        return
    region = img[y1c:y2c, x1c:x2c]
    colored = np.empty_like(region)
    colored[:] = color
    a = min(1.0, max(0.0, alpha))
    blended = colored if a >= 0.999 else cv2.addWeighted(colored, a, region, 1 - a, 0)
    if radius <= 0:
        region[:] = blended
        return
    mask = rounded_mask(x2 - x1, y2 - y1, radius)[y1c - y1:y2c - y1, x1c - x1:x2c - x1]
    cv2.copyTo(blended, mask, region)


def ellipse_blend(img, center, axes, color, alpha=0.5, thickness=-1):
    """Elipse translucida, mezclada solo en su caja (no copia el frame entero)."""
    a = min(1.0, max(0.0, alpha))
    if a <= 0:
        return
    cx, cy = int(center[0]), int(center[1])
    ax, ay = max(1, int(axes[0])), max(1, int(axes[1]))
    pad = max(2, thickness if thickness > 0 else 1)
    x1, y1 = max(0, cx - ax - pad), max(0, cy - ay - pad)
    x2, y2 = min(img.shape[1], cx + ax + pad), min(img.shape[0], cy + ay + pad)
    if x2 <= x1 or y2 <= y1:
        return
    region = img[y1:y2, x1:x2]
    layer = region.copy()
    cv2.ellipse(layer, (cx - x1, cy - y1), (ax, ay), 0, 0, 360, color,
                thickness, cv2.LINE_AA)
    cv2.addWeighted(layer, a, region, 1 - a, 0, region)


def rounded_border(img, box, color, thickness=2, radius=14):
    """Contorno redondeado (cuatro lineas + cuatro arcos)."""
    x1, y1, x2, y2 = (int(v) for v in box)
    r = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness, cv2.LINE_AA)
    for (cx, cy), start in (((x1 + r, y1 + r), 180), ((x2 - r, y1 + r), 270),
                            ((x2 - r, y2 - r), 0), ((x1 + r, y2 - r), 90)):
        cv2.ellipse(img, (cx, cy), (r, r), 0, start, start + 90, color, thickness, cv2.LINE_AA)


def tint_bgra(src: np.ndarray, color, amount: float) -> np.ndarray:
    """Mezcla los pixeles de una imagen BGRA hacia un color (para destellos)."""
    if amount <= 0:
        return src
    out = src.copy()
    a = min(1.0, amount)
    out[:, :, :3] = (src[:, :, :3].astype(np.float32) * (1 - a)
                     + np.array(color, np.float32) * a).astype(np.uint8)
    return out


def screen_tint(img, color, alpha):
    """Tinte de pantalla completa."""
    a = min(1.0, max(0.0, alpha))
    if a <= 0:
        return
    overlay = np.full(img.shape, color, np.uint8)
    cv2.addWeighted(overlay, a, img, 1 - a, 0, img)


def shake(img, dx, dy):
    """Desplaza el frame (temblor de pantalla) replicando los bordes."""
    if not dx and not dy:
        return img
    m = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]),
                          borderMode=cv2.BORDER_REPLICATE)
