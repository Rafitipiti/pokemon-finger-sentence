"""Tablero de palabras, seleccion por permanencia y armado de la frase."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import config as cfg


@dataclass
class Cell:
    index: int
    word: str
    x1: int
    y1: int
    x2: int
    y2: int
    row: int = 0

    @property
    def box(self) -> tuple[int, int, int, int]:
        return self.x1, self.y1, self.x2, self.y2

    @property
    def center(self) -> tuple[int, int]:
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2

    def contains(self, px: int, py: int) -> bool:
        return self.x1 <= px <= self.x2 and self.y1 <= py <= self.y2


def build_cells(width, top, bottom, rows: list[list[str]], pad=13,
                scale=None) -> list[Cell]:
    """Reparte las filas de palabras entre `top` y `bottom`.

    Cada fila puede tener distinta cantidad de recuadros (3 pokemon, 4 comandos,
    6 ataques), asi que el ancho se calcula fila por fila. `scale` encoge cada
    recuadro desde su centro sin mover la grilla.
    """
    if scale is None:
        scale = getattr(cfg, "CELL_SCALE", 1.0)
    area_h = max(1, bottom - top)
    row_h = (area_h - pad * (len(rows) + 1)) / max(1, len(rows))

    cells: list[Cell] = []
    index = 0
    for r, words in enumerate(rows):
        cols = max(1, len(words))
        cell_w = (width - pad * (cols + 1)) / cols
        y1 = top + pad + r * (row_h + pad)
        mx = cell_w * (1 - scale) / 2          # margen que se recorta a cada lado
        my = row_h * (1 - scale) / 2
        for c, word in enumerate(words):
            x1 = pad + c * (cell_w + pad)
            cells.append(Cell(index, word, int(x1 + mx), int(y1 + my),
                              int(x1 + cell_w - mx), int(y1 + row_h - my), r))
            index += 1
    return cells


def cell_at(cells: list[Cell], point: tuple[int, int] | None) -> int | None:
    if point is None:
        return None
    for cell in cells:
        if cell.contains(*point):
            return cell.index
    return None


class DwellSelector:
    """Cuenta cuanto tiempo lleva el dedo sobre un recuadro y confirma."""

    def __init__(self, dwell_seconds=3.0, lost_grace=0.35):
        self.dwell_seconds = dwell_seconds
        self.lost_grace = lost_grace
        self.active: int | None = None
        self._started: float | None = None
        self._last_seen: float | None = None
        self._locked: int | None = None      # ya elegido: no repetir sin salir
        self.progress = 0.0

    def _reset(self):
        self.active = None
        self._started = None
        self.progress = 0.0
        self._locked = None

    def update(self, cell_index: int | None, now: float) -> int | None:
        """Devuelve el indice del recuadro confirmado, o None."""
        if cell_index is None:
            # Perdida momentanea del dedo: se conserva el conteo un instante.
            if (self.active is not None and self._last_seen is not None
                    and now - self._last_seen <= self.lost_grace):
                return None
            self._reset()
            return None

        self._last_seen = now

        if cell_index != self.active:
            self.active = cell_index
            self._started = now
            self.progress = 0.0
            self._locked = None
            return None

        if self._locked == cell_index:
            self.progress = 1.0
            return None

        elapsed = now - (self._started or now)
        self.progress = min(1.0, elapsed / self.dwell_seconds) if self.dwell_seconds else 1.0
        if self.progress >= 1.0:
            self._locked = cell_index
            return cell_index
        return None


@dataclass
class Sentence:
    """La frase en construccion y las ya enviadas."""

    words: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    output_file: str | None = None

    @property
    def text(self) -> str:
        return " ".join(self.words)

    def add(self, word: str):
        self.words.append(word)

    def undo(self) -> str | None:
        return self.words.pop() if self.words else None

    def clear(self):
        self.words.clear()

    def finish(self) -> str | None:
        """Cierra la frase: la guarda, la limpia y devuelve el texto."""
        text = self.text.strip()
        if not text:
            return None
        self.history.append(text)
        if self.output_file:
            stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with Path(self.output_file).open("a", encoding="utf-8") as fh:
                fh.write(f"[{stamp}] {text}\n")
        self.clear()
        return text
