"""Efectos de pantalla: impacto de ataque, texto grande y tinte."""

from __future__ import annotations

import cv2
import numpy as np

import text_render as T


class Effect:
    """Base: vive un tiempo y sabe dibujarse segun su progreso 0..1."""

    def __init__(self, start: float, dur: float):
        self.start = start
        self.dur = max(0.01, dur)

    def progress(self, now: float) -> float:
        return min(1.0, max(0.0, (now - self.start) / self.dur))

    def alive(self, now: float) -> bool:
        return now < self.start + self.dur

    def draw(self, frame, now: float):
        raise NotImplementedError


class Impact(Effect):
    """Anillo que se expande + particulas, en el color del tipo del ataque."""

    def __init__(self, start, origin, color, dur=0.75, particles=34, spread=1.0, seed=0):
        super().__init__(start, dur)
        self.origin = origin
        self.color = color
        rng = np.random.default_rng(seed)
        # El pokemon esta en la esquina inferior izquierda, asi que las
        # particulas salen hacia la derecha y arriba: si fueran radiales
        # taparian al propio sprite.
        ang = rng.uniform(-1.35, 1.15, particles)
        self.dirs = np.stack([np.cos(ang) * 1.3, np.sin(ang) * 0.9], axis=1)
        self.speed = rng.uniform(180, 560, particles) * spread
        self.radius = rng.integers(3, 9, particles)

    def draw(self, frame, now):
        p = self.progress(now)
        alpha = (1 - p) ** 1.4
        if alpha <= 0.02:
            return
        overlay = frame.copy()
        ox, oy = self.origin

        ring = int(30 + p * 190)
        cv2.circle(overlay, (int(ox), int(oy)), ring, self.color,
                   max(2, int(12 * (1 - p))), cv2.LINE_AA)

        t = p * self.dur
        for d, sp, r in zip(self.dirs, self.speed, self.radius):
            x = int(ox + d[0] * sp * t)
            y = int(oy + d[1] * sp * t - 90 * t * t)      # un poco de gravedad
            cv2.circle(overlay, (x, y), int(r * (1 - p * 0.6)) + 1, self.color, -1, cv2.LINE_AA)

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


class BigText(Effect):
    """Texto grande que entra creciendo y se desvanece."""

    def __init__(self, start, text, pos, color, dur=1.5, size=58):
        super().__init__(start, dur)
        self.text = text
        self.pos = pos
        self.color = color
        self.size = size

    def draw(self, frame, now):
        p = self.progress(now)
        grow = min(1.0, p / 0.18)                       # 0..1 en el primer 18%
        size = int(self.size * (0.72 + 0.28 * grow))
        alpha = 1.0 if p < 0.65 else max(0.0, 1 - (p - 0.65) / 0.35)
        y = self.pos[1] - int(18 * p)
        T.draw(frame, self.text, (self.pos[0], y), size, self.color, True, "cm", alpha)


class Tint(Effect):
    """Destello de pantalla completa que se apaga."""

    def __init__(self, start, color, dur=0.35, strength=0.35):
        super().__init__(start, dur)
        self.color = color
        self.strength = strength

    def draw(self, frame, now):
        from gfx import screen_tint

        screen_tint(frame, self.color, self.strength * (1 - self.progress(now)) ** 2)
