"""Pokédex gestual: da órdenes Pokémon apuntando recuadros con el dedo.

- La punta del índice derecho es el cursor.
- Mantenerlo 3 segundos sobre un recuadro agrega esa palabra a la frase.
- Poner el brazo izquierdo en 90 grados envía la frase, y esta se ejecuta:
  YO TE ELIJO <pokemon>, USA <ataque>, ¡ESQUIVA!, ¡REGRESA!
"""

from __future__ import annotations

import argparse
import time

import cv2

import assets
import config as cfg
import gfx
import sprites as spr
import ui
from audio import SoundBank
from board import DwellSelector, Sentence, cell_at
from camera import CameraStream
from game import Game
from tracking import AngleHoldTrigger, ArmAngleTracker, IndexFingerTracker, arm_gesture_ok

WINDOW = "Pokédex gestual"
HINT = ("3 s sobre un recuadro = palabra   |   brazo IZQUIERDO en 90 grados = enviar   |   "
        "[BACKSPACE] borrar   [C] limpiar   [B] gesto estricto   [M] cambiar brazo   "
        "[S] silencio   [F] pantalla completa   [Q] salir")


def parse_args():
    p = argparse.ArgumentParser(description="Órdenes Pokémon con el dedo índice.")
    p.add_argument("--camera", type=int, default=cfg.CAMERA_INDEX, help="índice de la cámara")
    p.add_argument("--dwell", type=float, default=cfg.DWELL_SECONDS, help="segundos por palabra")
    p.add_argument("--arm-angle", type=float, default=cfg.ARM_TARGET_ANGLE)
    p.add_argument("--tolerance", type=float, default=cfg.ARM_TOLERANCE)
    p.add_argument("--width", type=int, default=cfg.FRAME_WIDTH)
    p.add_argument("--height", type=int, default=cfg.FRAME_HEIGHT)
    p.add_argument("--no-mirror", action="store_true", help="sin vista espejo")
    p.add_argument("--no-sound", action="store_true", help="arranca en silencio")
    p.add_argument("--fullscreen", action="store_true")
    p.add_argument("--loose-arm", action="store_true",
                   help="basta el codo en 90 grados, sin exigir el brazo horizontal")
    return p.parse_args()


def load_sprites() -> dict:
    """Carga los GIF animados de cada Pokémon del equipo."""
    bank = {}
    for name, data in cfg.POKEMON.items():
        sprite = spr.load_animated(assets.sprite_path(data["id"]), cfg.SPRITE_SCALE, name)
        if sprite is None:
            print(f"  sin sprite para {name} (se usa una silueta)")
        bank[name] = sprite
    return bank


def set_fullscreen(enabled):
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN,
                          cv2.WINDOW_FULLSCREEN if enabled else cv2.WINDOW_NORMAL)


def main():
    args = parse_args()
    mirror = cfg.MIRROR and not args.no_mirror
    pokemon_ids = [data["id"] for data in cfg.POKEMON.values()]

    assets.ensure_assets(pokemon_ids)
    sprite_bank = load_sprites()
    sounds = SoundBank(pokemon_ids, cfg.VOLUME, cfg.AUDIO_ENABLED and not args.no_sound)

    cap = CameraStream(args.camera, args.width, args.height)
    if not cap.ok:
        raise SystemExit(
            f"No pude abrir la cámara {args.camera}. "
            "Cierra otras apps que la usen (Teams, Zoom, Chrome) o prueba --camera 1."
        )

    hand_tracker = IndexFingerTracker(cfg.HAND_SIDE, cfg.STRICT_HAND_SIDE,
                                      cfg.HAND_MIN_DETECTION, cfg.HAND_MIN_TRACKING)
    arm_tracker = ArmAngleTracker(cfg.ARM_SIDE, mirrored=mirror)
    trigger = AngleHoldTrigger(args.arm_angle, args.tolerance, cfg.ARM_HOLD_SECONDS)
    dwell = DwellSelector(args.dwell, cfg.LOST_GRACE_SECONDS)
    sentence = Sentence(output_file=cfg.OUTPUT_FILE)
    game = Game(sounds)
    strict_pose = cfg.ARM_STRICT_POSE and not args.loose_arm

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    fullscreen = args.fullscreen
    if fullscreen:
        set_fullscreen(True)

    layout = None
    frame_shape = None
    frame_idx = 0
    arm = None
    arm_time = 0.0
    confirm_until = 0.0
    fps = 0.0
    last_tick = time.perf_counter()

    try:
        while True:
            frame = cap.read()
            if frame is None:
                print("La cámara dejó de entregar frames.")
                break
            if mirror:
                frame = cv2.flip(frame, 1)

            h, w = frame.shape[:2]
            if frame_shape != (h, w):
                frame_shape = (h, w)
                layout = ui.build_layout(w, h)
                game.layout = layout

            # Los modelos trabajan sobre una copia reducida (los landmarks son
            # normalizados, así que las coordenadas sirven para el frame grande).
            if cfg.DETECT_WIDTH and w > cfg.DETECT_WIDTH:
                small = cv2.resize(frame, (cfg.DETECT_WIDTH, int(h * cfg.DETECT_WIDTH / w)))
            else:
                small = frame
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False

            hand = hand_tracker.find(rgb)
            if frame_idx % max(1, cfg.POSE_EVERY_N_FRAMES) == 0:
                reading = arm_tracker.read(rgb)
                if reading is not None:
                    arm, arm_time = reading, time.perf_counter()
            frame_idx += 1

            now = time.perf_counter()
            if arm is not None and now - arm_time > cfg.POSE_MAX_AGE_SECONDS:
                arm = None

            point = None
            if hand is not None:
                point = (int(hand.tip[0] * w), int(hand.tip[1] * h))

            over = cell_at(layout.cells, point)
            chosen = dwell.update(over, now)
            if chosen is not None:
                word = layout.cells[chosen].word
                sentence.add(word)
                game.word_added(word, now)
                confirm_until = now + 0.6
                print(f"+ {word}   ->  {sentence.text}")

            angle = arm.angle if arm is not None else None
            elbow_ok, pose_ok = arm_gesture_ok(arm, trigger, strict_pose,
                                               cfg.ARM_UPPER_TOLERANCE)
            if trigger.update(angle if pose_ok else None, now):
                words = list(sentence.words)
                game.send(words, now)
                enviada = sentence.finish()
                if enviada:
                    print(f"== FRASE: {enviada}")
            game.update(now)

            # --- Dibujo ---
            ui.draw_cells(frame, layout, dwell.active, dwell.progress,
                          confirmed=now < confirm_until)
            ui.draw_arm(frame, arm, pose_ok)
            ui.draw_stage(frame, layout, game, sprite_bank, now)
            game.draw_effects(frame, now)

            dt = now - last_tick
            last_tick = now
            if dt > 0:
                fps = fps * 0.9 + (1 / dt) * 0.1 if fps else 1 / dt

            hand_state = "índice derecho detectado" if hand is not None else "sin mano"
            if angle is None:
                arm_state = f"brazo {cfg.ARM_SIDE[:3]}. no visible"
            elif pose_ok:
                arm_state = f"90 grados ({angle:0.0f}) mantén..."
            elif elbow_ok:
                arm_state = f"codo {angle:0.0f} ok, sube el brazo ({arm.upper_tilt:0.0f})"
            else:
                banda = f"{args.arm_angle - args.tolerance:0.0f}-{args.arm_angle + args.tolerance:0.0f}"
                arm_state = f"codo izq. {angle:0.0f} grados (busca {banda})"
            ui.draw_hud(frame, [hand_state, arm_state,
                                f"palabras: {len(sentence.words)}",
                                f"frases: {len(sentence.history)}",
                                "audio: on" if sounds.ok else "audio: off"], fps)
            ui.draw_sentence_bar(frame, sentence, HINT, layout)
            ui.draw_progress_hint(frame, layout, trigger.progress)
            ui.draw_pointer(frame, point, dwell.progress if over is not None else 0.0)

            dx, dy = game.shake_offset(now)
            if dx or dy:
                frame = gfx.shake(frame, dx, dy)

            cv2.imshow(WINDOW, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("c"):
                sentence.clear()
            elif key in (8, 127):
                sentence.undo()
            elif key == ord("b"):
                strict_pose = not strict_pose
                print(f"Gesto del brazo: {'estricto' if strict_pose else 'solo codo a 90'}")
            elif key == ord("m"):
                arm_tracker.toggle_mirror()
                print(f"Brazo leído: lado {arm_tracker.effective_side} del modelo")
            elif key == ord("s") and sounds.mixer is not None:
                sounds.mixer.volume = 0.0 if sounds.mixer.volume else cfg.VOLUME
                print(f"Volumen: {sounds.mixer.volume}")
            elif key == ord("f"):
                fullscreen = not fullscreen
                set_fullscreen(fullscreen)
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        hand_tracker.close()
        arm_tracker.close()
        sounds.close()
        cv2.destroyAllWindows()

    if sentence.history:
        print("\nFrases de la sesión:")
        for i, text in enumerate(sentence.history, 1):
            print(f"  {i}. {text}")
        print(f"\nGuardadas en {cfg.OUTPUT_FILE}")


if __name__ == "__main__":
    main()
