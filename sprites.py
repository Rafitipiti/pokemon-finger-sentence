"""Sprites animados: carga los GIF de PokeAPI y devuelve el frame que toca."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageSequence


@dataclass
class AnimatedSprite:
    """Frames BGRA ya escalados, con el tiempo acumulado de cada uno."""

    frames: list[np.ndarray]
    ends: list[float]                      # instante en que termina cada frame
    total: float
    name: str = ""
    _shadow: np.ndarray | None = field(default=None, repr=False)

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.frames[0].shape[:2]
        return w, h

    def frame_at(self, t: float) -> np.ndarray:
        """Frame correspondiente al tiempo t (en bucle)."""
        if self.total <= 0:
            return self.frames[0]
        t = t % self.total
        for end, frame in zip(self.ends, self.frames):
            if t < end:
                return frame
        return self.frames[-1]


def load_animated(path, scale=2.0, name="") -> AnimatedSprite | None:
    """Carga un GIF animado a frames BGRA escalados con vecino mas cercano."""
    try:
        img = Image.open(path)
    except (OSError, ValueError):
        return None

    frames: list[np.ndarray] = []
    ends: list[float] = []
    clock = 0.0
    for pil_frame in ImageSequence.Iterator(img):
        rgba = pil_frame.convert("RGBA")
        if scale != 1:
            rgba = rgba.resize((max(1, int(rgba.width * scale)),
                                max(1, int(rgba.height * scale))), Image.NEAREST)
        arr = np.array(rgba)[:, :, [2, 1, 0, 3]].copy()      # RGBA -> BGRA
        frames.append(arr)
        clock += max(0.02, pil_frame.info.get("duration", 100) / 1000.0)
        ends.append(clock)

    if not frames:
        return None
    return AnimatedSprite(frames, ends, clock, name or str(path))


def scaled(frame_bgra: np.ndarray, factor: float) -> np.ndarray:
    """Escala un frame BGRA (para el efecto de salir de la pokebola)."""
    if abs(factor - 1.0) < 0.01:
        return frame_bgra
    import cv2

    h, w = frame_bgra.shape[:2]
    nw, nh = max(1, int(w * factor)), max(1, int(h * factor))
    interp = cv2.INTER_NEAREST if factor >= 1 else cv2.INTER_AREA
    return cv2.resize(frame_bgra, (nw, nh), interpolation=interp)


def placeholder(size=140, color=(120, 120, 120), label="?") -> np.ndarray:
    """Silueta de reserva si no se pudo descargar el sprite."""
    import cv2

    img = np.zeros((size, size, 4), np.uint8)
    cv2.circle(img, (size // 2, size // 2), size // 2 - 4, (*color, 200), -1, cv2.LINE_AA)
    cv2.putText(img, label, (size // 2 - 12, size // 2 + 14),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255, 255), 2, cv2.LINE_AA)
    return img
