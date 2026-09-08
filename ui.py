"""Dibujado: tablero, HUD, escena (sprite + pokebolas) y barra de la frase."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2

import config as cfg
import gfx
import sprites as spr
import text_render as T
from board import build_cells

# Paleta base (BGR)
WHITE = (245, 245, 245)
GREY = (155, 150, 148)
PANEL = (34, 30, 28)
BOX = (62, 55, 52)
DONE = (90, 200, 110)
POINTER = (255, 200, 80)
BALL_RED = (58, 58, 220)
BALL_WHITE = (238, 238, 238)
BALL_BLACK = (24, 22, 22)


def word_color(word: str) -> tuple:
    """Color de acento de un recuadro segun su papel."""
    if word in cfg.POKEMON:
        return cfg.COLOR_POKEMON
    if word in cfg.COMMANDS:
        return cfg.COLOR_COMMAND
    return cfg.TYPE_COLORS.get(cfg.MOVES.get(word, ""), BOX)


@dataclass
class Layout:
    """Geometria de la pantalla, recalculada solo si cambia el tamano."""

    w: int
    h: int
    grid_top: int
    grid_bottom: int
    stage_top: int
    stage_bottom: int
    bar_top: int
    cells: list = field(default_factory=list)
    sprite_anchor: tuple = (0, 0)      # (x izquierdo, y de la base)
    sprite_center: tuple = (0, 0)
    banner_pos: tuple = (0, 0)
    toast_pos: tuple = (0, 0)
    ball_centers: list = field(default_factory=list)


def build_layout(w: int, h: int) -> Layout:
    bar_top = h - cfg.BAR_HEIGHT
    stage_bottom = bar_top
    stage_top = stage_bottom - cfg.STAGE_HEIGHT
    lay = Layout(w, h, cfg.HUD_HEIGHT, stage_top, stage_top, stage_bottom, bar_top)
    lay.cells = build_cells(w, cfg.HUD_HEIGHT, stage_top, cfg.WORD_ROWS)
    lay.sprite_anchor = (38, stage_bottom - 6)
    lay.sprite_center = (38 + 82, stage_bottom - 6 - 78)
    lay.banner_pos = (int(w * 0.52), stage_top + 48)
    lay.toast_pos = (int(w * 0.52), stage_top + 114)
    lay.ball_centers = [(w - 56 - 90 * (2 - i), stage_top + 58) for i in range(3)]
    return lay


# --------------------------------------------------------------------------
# Tablero
# --------------------------------------------------------------------------
def draw_cells(frame, layout: Layout, active_index=None, progress=0.0, confirmed=False):
    for cell in layout.cells:
        accent = word_color(cell.word)
        is_active = cell.index == active_index
        gfx.rounded_rect(frame, cell.box, PANEL if not is_active else BOX, 0.66, 14)

        if is_active and progress > 0:
            # Relleno que sube desde abajo durante los 3 segundos.
            fill_top = cell.y2 - int((cell.y2 - cell.y1) * min(1.0, progress))
            gfx.rounded_rect(frame, (cell.x1, fill_top, cell.x2, cell.y2),
                             DONE if confirmed else accent, 0.5, 14)

        border = DONE if (is_active and confirmed) else accent
        gfx.rounded_border(frame, cell.box, border, 3 if is_active else 1, 14)
        T.draw_block(frame, cell.word, cell.box, WHITE, max_size=40)


def draw_pointer(frame, point, progress=0.0):
    if point is None:
        return
    x, y = point
    cv2.circle(frame, (x, y), 16, (25, 25, 25), 2, cv2.LINE_AA)
    cv2.circle(frame, (x, y), 8, POINTER, -1, cv2.LINE_AA)
    if progress > 0:
        cv2.ellipse(frame, (x, y), (22, 22), -90, 0, int(360 * progress),
                    POINTER, 3, cv2.LINE_AA)


def draw_arm(frame, arm, ok):
    if arm is None:
        return
    h, w = frame.shape[:2]
    pts = [(int(p[0] * w), int(p[1] * h)) for p in (arm.shoulder, arm.elbow, arm.wrist)]
    color = DONE if ok else GREY
    cv2.line(frame, pts[0], pts[1], color, 4, cv2.LINE_AA)
    cv2.line(frame, pts[1], pts[2], color, 4, cv2.LINE_AA)
    for p in pts:
        cv2.circle(frame, p, 6, color, -1, cv2.LINE_AA)
    T.draw(frame, f"{arm.angle:0.0f}", (pts[1][0] + 14, pts[1][1] - 22), 20, color)


# --------------------------------------------------------------------------
# Escena: sprite, pokebolas, mensajes
# --------------------------------------------------------------------------
def draw_pokeball(frame, center, r, openness=0.0, glow_color=None):
    """Pokebola dibujada a mano. `openness` 0 = cerrada, 1 = abierta."""
    cx, cy = int(center[0]), int(center[1])
    sep = int(openness * r * 0.55)

    if sep >= 2:
        # Luz entre las dos mitades: es lo que se ve cuando la bola esta abierta.
        gfx.ellipse_blend(frame, (cx, cy), (int(r * 0.8), sep + 2),
                          (255, 255, 255), 0.65 * openness)
        if glow_color is not None:
            gfx.ellipse_blend(frame, (cx, cy), (int(r * 0.95), sep + 5),
                              glow_color, 0.8 * openness, thickness=2)

    cv2.ellipse(frame, (cx, cy - sep), (r, r), 0, 180, 360, BALL_RED, -1, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy + sep), (r, r), 0, 0, 180, BALL_WHITE, -1, cv2.LINE_AA)
    cv2.line(frame, (cx - r, cy - sep), (cx + r, cy - sep), BALL_BLACK, 4, cv2.LINE_AA)
    cv2.line(frame, (cx - r, cy + sep), (cx + r, cy + sep), BALL_BLACK, 4, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy - sep), (r, r), 0, 180, 360, BALL_BLACK, 2, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy + sep), (r, r), 0, 0, 180, BALL_BLACK, 2, cv2.LINE_AA)

    if openness < 0.5:                      # el boton solo se ve cerrada
        button = int(r * 0.3)
        cv2.circle(frame, (cx, cy), button + 3, BALL_BLACK, -1, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), button, BALL_WHITE, -1, cv2.LINE_AA)


def draw_stage(frame, layout: Layout, game, sprite_bank: dict, now: float):
    """Sprite del pokemon en escena, cinturon de pokebolas y mensaje."""
    gfx.rounded_rect(frame, (0, layout.stage_top, layout.w, layout.stage_bottom),
                     (16, 14, 13), 0.35, 0)

    # --- Pokebolas
    for ball, center in zip(game.balls, layout.ball_centers):
        openness = ball.openness(now)
        accent = cfg.COLOR_POKEMON if ball.pokemon == game.active else None
        draw_pokeball(frame, center, cfg.BALL_RADIUS, openness, accent)
        color = cfg.COLOR_POKEMON if ball.pokemon == game.active else GREY
        T.draw(frame, ball.pokemon, (center[0], center[1] + cfg.BALL_RADIUS + 12),
               13, color, True, "ct")
    T.draw(frame, "EQUIPO", (layout.ball_centers[0][0] - cfg.BALL_RADIUS - 14,
                             layout.ball_centers[0][1]), 15, GREY, True, "rm")

    # --- Sprite en escena
    state = game.sprite_state(now)
    if state.visible and game.active:
        sprite = sprite_bank.get(game.active)
        base_x, base_y = layout.sprite_anchor
        if sprite is not None:
            frame_bgra = sprite.frame_at(now)
        else:
            frame_bgra = spr.placeholder(140, cfg.COLOR_POKEMON, game.active[0])

        if state.flash > 0:
            frame_bgra = gfx.tint_bgra(frame_bgra, state.flash_color, state.flash)
        if abs(state.scale - 1.0) > 0.01:
            frame_bgra = spr.scaled(frame_bgra, state.scale)

        sh, sw = frame_bgra.shape[:2]
        x = base_x + state.dx
        y = base_y - sh + state.dy

        shadow_w = int(sw * 0.42)
        gfx.ellipse_blend(frame, (int(x + sw / 2), int(base_y + 2)),
                          (shadow_w, max(5, int(shadow_w * 0.22))),
                          (10, 10, 10), 0.45 * state.alpha)

        gfx.blit_bgra(frame, frame_bgra, x, y, state.alpha)

        # Placa con el nombre y los tipos que conoce
        plate_x = base_x + 190
        T.draw(frame, game.active, (plate_x, layout.stage_bottom - 34), 26,
               cfg.COLOR_POKEMON, True, "lt")
        chip_x = plate_x
        for move in cfg.POKEMON[game.active]["moves"]:
            tipo = cfg.MOVES[move]
            color = cfg.TYPE_COLORS[tipo]
            w_chip = T.measure(tipo, 13)[0] + 18
            gfx.rounded_rect(frame, (chip_x, layout.stage_bottom - 60,
                                     chip_x + w_chip, layout.stage_bottom - 40), color, 0.85, 8)
            T.draw(frame, tipo, (chip_x + w_chip / 2, layout.stage_bottom - 50), 13,
                   (25, 25, 25), True, "cm")
            chip_x += w_chip + 8
    else:
        x0 = layout.sprite_anchor[0]
        T.draw(frame, "sin Pokémon en combate", (x0, layout.stage_bottom - 62),
               22, GREY, True, "lt")
        T.draw(frame, f"arma «{cfg.CMD_CHOOSE} + nombre» (o al revés) y envíala",
               (x0, layout.stage_bottom - 32), 17, GREY, False, "lt")

    # --- Mensaje de la accion
    msg = game.message_now(now)
    if msg:
        text, color = msg
        w_txt = T.measure(text, 22)[0]
        box = (layout.toast_pos[0] - w_txt / 2 - 16, layout.toast_pos[1] - 18,
               layout.toast_pos[0] + w_txt / 2 + 16, layout.toast_pos[1] + 18)
        gfx.rounded_rect(frame, box, (18, 16, 15), 0.7, 12)
        gfx.rounded_border(frame, box, color, 2, 12)
        T.draw(frame, text, layout.toast_pos, 22, color, True, "cm")


# --------------------------------------------------------------------------
# HUD y barra de la frase
# --------------------------------------------------------------------------
def draw_hud(frame, lines, fps):
    w = frame.shape[1]
    gfx.rounded_rect(frame, (0, 0, w, cfg.HUD_HEIGHT), (18, 16, 15), 0.74, 0)
    T.draw(frame, "POKÉDEX GESTUAL", (22, 12), 26, cfg.COLOR_POKEMON)
    T.draw(frame, "   ".join(lines), (22, 44), 16, WHITE, False)
    T.draw(frame, f"{fps:0.0f} FPS", (w - 22, 20), 17, GREY, False, "rt")


def draw_sentence_bar(frame, sentence, hint, layout: Layout):
    h, w = frame.shape[:2]
    top = layout.bar_top
    gfx.rounded_rect(frame, (0, top, w, h), (16, 14, 13), 0.82, 0)
    cv2.line(frame, (0, top), (w, top), cfg.COLOR_POKEMON, 2, cv2.LINE_AA)

    T.draw(frame, "FRASE", (22, top + 10), 15, cfg.COLOR_POKEMON)

    if sentence.words:
        size = 34 if len(sentence.words) <= 5 else 26
        text = sentence.text
        while T.measure(text, size)[0] > w - 60 and size > 14:
            size -= 2
        T.draw(frame, text, (22, top + 34), size, WHITE)
    else:
        T.draw(frame, "apunta un recuadro 3 segundos...", (22, top + 38), 22, GREY, False)

    T.draw(frame, hint, (22, h - 22), 14, GREY, False)


def draw_progress_hint(frame, layout: Layout, trigger_progress: float):
    """Barrita a la derecha de la barra inferior mientras se sostiene el brazo."""
    if trigger_progress <= 0:
        return
    h, w = frame.shape[:2]
    x1, x2 = w - 250, w - 30
    y = layout.bar_top + 26
    gfx.rounded_rect(frame, (x1, y, x2, y + 16), (60, 55, 52), 0.9, 8)
    gfx.rounded_rect(frame, (x1, y, x1 + (x2 - x1) * trigger_progress, y + 16),
                     DONE, 0.95, 8)
    T.draw(frame, "enviando frase", ((x1 + x2) / 2, y + 30), 14, DONE, True, "ct")
