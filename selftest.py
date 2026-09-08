"""Prueba sin cámara: valida la lógica y genera vistas previas.

    python selftest.py     ->  imprime resultados y escribe preview*.png
"""

from __future__ import annotations

import numpy as np

import config as cfg
import ui
from board import DwellSelector, Sentence, build_cells, cell_at
from game import Game
from tracking import AngleHoldTrigger, ArmReading, angle_between, arm_gesture_ok, horizontal_tilt

W, H = cfg.FRAME_WIDTH, cfg.FRAME_HEIGHT


class FakeSounds:
    """Registra lo que se habría reproducido, sin abrir la tarjeta de sonido."""

    ok = False
    mixer = None

    def __init__(self):
        self.played: list[str] = []
        self.cries: list[int] = []

    def play(self, name, gain=1.0):
        self.played.append(name)

    def cry(self, pokemon_id, gain=1.0):
        self.cries.append(pokemon_id)

    def close(self):
        pass


def run(game, sounds, words, t0, steps=8):
    """Envía una frase y deja correr el reloj para que se ejecute la cadena."""
    game.send(words, t0)
    for i in range(steps):
        game.update(t0 + 0.2 + i * 1.0)
    return t0 + 0.2 + steps * 1.0


# --------------------------------------------------------------------------
def test_words():
    assert len(cfg.WORDS) == 13, cfg.WORDS
    esperadas = {"TOGEKISS", "TYPHLOSION", "GARCHOMP", "USA", "YO TE ELIJO",
                 "¡ESQUIVA!", "¡REGRESA!", "BRILLO LUNAR", "ESTALLIDO",
                 "TERREMOTO", "TAJO AÉREO", "LLAMARADA", "GARRA DRAGÓN"}
    assert set(cfg.WORDS) == esperadas, set(cfg.WORDS) ^ esperadas
    # Cada ataque tiene tipo y color, y pertenece a algún Pokémon del equipo.
    for move, tipo in cfg.MOVES.items():
        assert tipo in cfg.TYPE_COLORS, move
    de_alguien = {m for p in cfg.POKEMON.values() for m in p["moves"]}
    assert de_alguien == set(cfg.MOVES), de_alguien ^ set(cfg.MOVES)
    print(f"palabras .. ok (13 recuadros, {len(cfg.MOVES)} ataques con tipo)")


def test_grid():
    cells = build_cells(W, cfg.HUD_HEIGHT, H - cfg.BAR_HEIGHT - cfg.STAGE_HEIGHT,
                        cfg.WORD_ROWS)
    assert len(cells) == 13
    assert [sum(1 for c in cells if c.row == r) for r in range(3)] == [3, 4, 6]
    limite = H - cfg.BAR_HEIGHT - cfg.STAGE_HEIGHT
    for c in cells:
        assert 0 <= c.x1 < c.x2 <= W, c
        assert cfg.HUD_HEIGHT <= c.y1 < c.y2 <= limite, c
    # Las celdas de una misma fila no se solapan.
    for r in range(3):
        fila = sorted((c for c in cells if c.row == r), key=lambda c: c.x1)
        for a, b in zip(fila, fila[1:]):
            assert a.x2 < b.x1, (a.word, b.word)
    assert cell_at(cells, cells[7].center) == 7
    assert cell_at(cells, (5, H - 20)) is None      # la barra inferior no selecciona
    print("tablero ... ok (3+4+6 recuadros sin solaparse)")
    return cells


def test_dwell(cells):
    dwell = DwellSelector(3.0, 0.35)
    t = 100.0
    for step in (0.0, 1.0, 2.0, 2.9):
        assert dwell.update(5, t + step) is None
    assert 0.9 < dwell.progress < 1.0
    assert dwell.update(5, t + 3.01) == 5
    assert dwell.update(5, t + 4.0) is None, "no debe repetir la misma palabra"
    dwell.update(None, t + 4.1)
    assert dwell.active == 5, "una pérdida breve no reinicia el conteo"
    dwell.update(None, t + 5.0)
    assert dwell.active is None
    assert dwell.update(2, t + 5.1) is None
    assert dwell.update(2, t + 8.2) == 2
    print("dwell ..... ok (3 s exactos, sin repeticiones)")


def test_pose_math():
    # Este brazo forma 90 grados exactos en píxeles, pero medido sobre
    # coordenadas normalizadas 16:9 da ~70: hay que reescalar la x.
    aspect = 16 / 9
    px = [(400, 400), (700, 300), (800, 600)]
    norm = [(x / 1280, y / 720) for x, y in px]
    crudo = angle_between(*norm)
    corregido = angle_between(*[(x * aspect, y) for x, y in norm])
    assert abs(angle_between(*px) - 90) < 0.01
    assert abs(crudo - 90) > 10 and abs(corregido - 90) < 0.5, (crudo, corregido)
    assert round(horizontal_tilt((0, 0), (1, 0))) == 0
    assert round(horizontal_tilt((0, 0), (0, 1))) == 90

    # El puntero va con una mano y el envío con el brazo contrario.
    assert cfg.HAND_SIDE == "right" and cfg.ARM_SIDE == "left", (cfg.HAND_SIDE, cfg.ARM_SIDE)
    assert cfg.ARM_TOLERANCE == 8.0, cfg.ARM_TOLERANCE
    banda = AngleHoldTrigger(cfg.ARM_TARGET_ANGLE, cfg.ARM_TOLERANCE, cfg.ARM_HOLD_SECONDS)
    assert banda.in_band(90.0) and banda.in_band(82.0) and banda.in_band(98.0)
    assert not banda.in_band(81.0) and not banda.in_band(99.0)

    trigger = AngleHoldTrigger(90.0, 20.0, 0.8)
    flex = ArmReading(91.0, 6.0, (0.40, 0.40), (0.60, 0.40), (0.60, 0.10))
    senalando = ArmReading(91.0, 62.0, (0.4, 0.4), (0.45, 0.62), (0.6, 0.45))
    estirado = ArmReading(172.0, 4.0, (0.40, 0.40), (0.60, 0.40), (0.9, 0.40))
    assert arm_gesture_ok(flex, trigger) == (True, True)
    assert arm_gesture_ok(senalando, trigger) == (True, False), "señalar no debe enviar"
    assert arm_gesture_ok(senalando, trigger, strict=False) == (True, True)
    assert arm_gesture_ok(estirado, trigger) == (False, False)
    assert arm_gesture_ok(None, trigger) == (False, False)

    t = 200.0
    assert trigger.update(170.0, t) is False
    assert trigger.update(95.0, t + 0.1) is False
    assert trigger.update(92.0, t + 1.0) is True
    assert trigger.update(92.0, t + 2.0) is False, "no repite sin salir de la banda"
    assert trigger.update(160.0, t + 2.5) is False
    assert trigger.update(90.0, t + 2.6) is False
    assert trigger.update(90.0, t + 3.5) is True
    print("brazo ..... ok (envío con el izquierdo, banda 82-98; señalar no dispara)")


def test_game():
    sounds = FakeSounds()
    game = Game(sounds)
    game.layout = ui.build_layout(W, H)
    assert len(game.balls) == 3 and not any(b.is_open for b in game.balls)

    t = run(game, sounds, ["YO TE ELIJO", "TOGEKISS"], 10.0, steps=2)
    assert game.active == "TOGEKISS"
    assert game.ball_of("TOGEKISS").is_open
    assert 468 in sounds.cries and "ball_open" in sounds.played
    assert game.ball_of("TOGEKISS").openness(t) == 1.0

    # Un ataque que no conoce se rechaza.
    t = run(game, sounds, ["USA", "TERREMOTO"], t, steps=2)
    msg = game.message_now(t - 0.5)
    assert msg and "no aprende" in msg[0], msg
    assert "error" in sounds.played

    # Un ataque propio dispara efectos y el color del tipo.
    t = run(game, sounds, ["USA", "BRILLO LUNAR"], t, steps=2)
    assert "HADA" in sounds.played
    assert game.effects, "el ataque debe dejar efectos en pantalla"
    assert game.type_color("BRILLO LUNAR") == cfg.TYPE_COLORS["HADA"]

    # Cambio de Pokémon: se cierra una pokébola y se abre otra.
    t = run(game, sounds, ["YO TE ELIJO", "GARCHOMP"], t, steps=2)
    assert game.active == "GARCHOMP"
    assert not game.ball_of("TOGEKISS").is_open and game.ball_of("GARCHOMP").is_open

    # Terremoto: además sacude la pantalla.
    game.send(["USA", "TERREMOTO"], t)
    game.update(t + 0.2)
    dx, dy = game.shake_offset(t + 0.3)
    assert dx or dy, "TERREMOTO debe sacudir la pantalla"
    assert "TIERRA" in sounds.played

    # ¡REGRESA! guarda al Pokémon y cierra su pokébola.
    t = run(game, sounds, ["¡REGRESA!"], t + 1.5, steps=2)
    assert game.active is None
    assert not any(b.is_open for b in game.balls)
    assert "ball_return" in sounds.played

    # Sin nadie fuera, esquivar o atacar avisa en vez de fallar.
    t = run(game, sounds, ["¡ESQUIVA!"], t, steps=2)
    assert game.message_now(t - 0.5)[0].startswith("saca a un")
    t = run(game, sounds, ["TYPHLOSION"], t, steps=2)
    assert "YO TE ELIJO" in game.message_now(t - 0.5)[0]

    # Frase encadenada: elegir y atacar de una sola vez.
    game2 = Game(FakeSounds())
    game2.layout = game.layout
    t = run(game2, game2.sounds, ["YO TE ELIJO", "TYPHLOSION", "USA", "LLAMARADA"], 500.0, 3)
    assert game2.active == "TYPHLOSION"
    assert "FUEGO" in game2.sounds.played and 157 in game2.sounds.cries
    assert not game2._queue, "la cadena debe haberse consumido"

    # El nombre puede ir antes del comando: "TOGEKISS YO TE ELIJO".
    game3 = Game(FakeSounds())
    game3.layout = game.layout
    t3 = run(game3, game3.sounds, ["TOGEKISS", "YO TE ELIJO"], 900.0, 2)
    assert game3.active == "TOGEKISS", game3.log
    assert game3.ball_of("TOGEKISS").is_open
    t3 = run(game3, game3.sounds, ["TAJO AÉREO", "USA"], t3, 2)
    assert "VOLADOR" in game3.sounds.played, game3.log
    t3 = run(game3, game3.sounds, ["TOGEKISS", "¡REGRESA!"], t3, 2)
    assert game3.active is None, game3.log

    # Frase vacía.
    game2.send([], t)
    assert game2.message_now(t)[0] == "no hay nada que enviar"
    print("juego ..... ok (elegir, atacar, tipos, regresar y frases encadenadas)")


def test_render():
    import cv2

    layout = ui.build_layout(W, H)
    sounds = FakeSounds()
    game = Game(sounds)
    game.layout = layout

    import assets
    import sprites as spr
    bank = {n: spr.load_animated(assets.sprite_path(d["id"]), cfg.SPRITE_SCALE, n)
            for n, d in cfg.POKEMON.items()}
    assert all(v is not None for v in bank.values()), "faltan sprites: corre assets.py"

    # 1) Escena en reposo, con una palabra a medio seleccionar.
    frame = np.full((H, W, 3), (52, 46, 42), np.uint8)
    sentence = Sentence(words=["YO TE ELIJO", "GARCHOMP"])
    ui.draw_cells(frame, layout, active_index=6, progress=0.62)
    ui.draw_stage(frame, layout, game, bank, 0.0)
    ui.draw_hud(frame, ["índice detectado", "codo 148 grados", "palabras: 2",
                        "frases: 0", "audio: on"], 27.0)
    ui.draw_sentence_bar(frame, sentence, "3 s sobre un recuadro = palabra", layout)
    ui.draw_pointer(frame, layout.cells[6].center, 0.62)
    cv2.imwrite("preview.png", frame)

    # 2) Escena en combate: Garchomp fuera usando TERREMOTO.
    t = 100.0
    game.send(["YO TE ELIJO", "GARCHOMP"], t)
    game.update(t + 0.2)
    game.update(t + 1.0)
    game.send(["USA", "GARRA DRAGÓN"], t + 1.2)
    game.update(t + 1.5)
    frame2 = np.full((H, W, 3), (52, 46, 42), np.uint8)
    ui.draw_cells(frame2, layout, active_index=12, progress=1.0, confirmed=True)
    ui.draw_stage(frame2, layout, game, bank, t + 1.62)
    game.draw_effects(frame2, t + 1.62)
    ui.draw_hud(frame2, ["índice detectado", "90 grados (91) mantén...", "palabras: 2",
                         "frases: 2", "audio: on"], 26.0)
    ui.draw_sentence_bar(frame2, Sentence(words=["USA", "GARRA DRAGÓN"]), "enviando...", layout)
    ui.draw_progress_hint(frame2, layout, 0.7)
    cv2.imwrite("preview_combate.png", frame2)
    print("render .... ok (preview.png y preview_combate.png)")


def test_film():
    """Corre una secuencia completa cuadro a cuadro y arma una tira de imágenes.

    Sirve para ver cómo evolucionan sprite y efectos sin encender la cámara, y
    para medir cuánto cuesta dibujar un frame.
    """
    import time

    import cv2

    import assets
    import sprites as spr

    layout = ui.build_layout(W, H)
    game = Game(FakeSounds())
    game.layout = layout
    bank = {n: spr.load_animated(assets.sprite_path(d["id"]), cfg.SPRITE_SCALE, n)
            for n, d in cfg.POKEMON.items()}
    sentence = Sentence()

    guion = [                                    # (instante, frase)
        (0.1, ["YO TE ELIJO", "TYPHLOSION"]),
        (1.5, ["USA", "LLAMARADA"]),
        (3.0, ["¡ESQUIVA!"]),
        (4.0, ["¡REGRESA!"]),
    ]
    capturas = [0.55, 1.2, 1.95, 2.45, 3.35, 4.4]
    fondo = np.full((H, W, 3), (52, 46, 42), np.uint8)
    tiras, costes = [], []

    t = 0.0
    while t < 5.0:
        while guion and guion[0][0] <= t:
            _, frase = guion.pop(0)
            sentence.words[:] = frase
            game.send(frase, t)
            sentence.clear()
        game.update(t)

        t0 = time.perf_counter()
        frame = fondo.copy()
        ui.draw_cells(frame, layout, active_index=None, progress=0.0)
        ui.draw_stage(frame, layout, game, bank, t)
        game.draw_effects(frame, t)
        ui.draw_hud(frame, ["índice detectado", "codo 150 grados", "palabras: 0",
                            "frases: 2", "audio: on"], 25.0)
        ui.draw_sentence_bar(frame, sentence, "secuencia de prueba", layout)
        costes.append(time.perf_counter() - t0)

        if capturas and t >= capturas[0]:
            capturas.pop(0)
            tiras.append(cv2.resize(frame, (W // 2, H // 2)))
        t += 0.05

    filas = [np.hstack(tiras[i:i + 2]) for i in range(0, len(tiras) - 1, 2)]
    cv2.imwrite("preview_secuencia.png", np.vstack(filas))
    medio = sum(costes) / len(costes) * 1000
    print(f"secuencia . ok (preview_secuencia.png, dibujado {medio:0.1f} ms/frame)")


if __name__ == "__main__":
    test_words()
    cells = test_grid()
    test_dwell(cells)
    test_pose_math()
    test_game()
    test_render()
    test_film()
    print("\nTodo en orden. Ahora corre:  python main.py")
