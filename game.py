"""Logica del combate: pokebolas, pokemon activo, animaciones y feedback.

La frase enviada se lee como una orden: YO TE ELIJO <pokemon>, USA <ataque>,
¡ESQUIVA! o ¡REGRESA!. El nombre puede ir antes o despues del comando, asi que
"YO TE ELIJO TOGEKISS" y "TOGEKISS YO TE ELIJO" hacen lo mismo. Una misma frase
puede encadenar varias ordenes y se ejecutan en secuencia.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import config as cfg
from effects import BigText, Impact, Tint

BALL_ANIM = 0.35          # cuanto tarda una pokebola en abrirse o cerrarse
CHAIN_DELAY = 0.95        # separacion entre ordenes de una misma frase

COLOR_OK = (245, 245, 245)
COLOR_ERROR = (110, 110, 250)
COLOR_GOLD = (90, 210, 255)


@dataclass
class Ball:
    """Una de las tres pokebolas del cinturon."""

    pokemon: str
    pokemon_id: int
    is_open: bool = False
    anim_start: float = -99.0

    def openness(self, now: float) -> float:
        """0 = cerrada, 1 = abierta (animado)."""
        t = min(1.0, max(0.0, (now - self.anim_start) / BALL_ANIM))
        return t if self.is_open else 1.0 - t

    def set_open(self, value: bool, now: float):
        if value != self.is_open:
            self.is_open = value
            self.anim_start = now


@dataclass
class Anim:
    """Animacion del sprite en escena."""

    kind: str
    start: float
    dur: float
    color: tuple = (255, 255, 255)

    def t(self, now: float) -> float:
        return min(1.0, max(0.0, (now - self.start) / self.dur))

    def done(self, now: float) -> bool:
        return now >= self.start + self.dur


@dataclass
class SpriteState:
    """Como dibujar el sprite este frame."""

    visible: bool = False
    scale: float = 1.0
    dx: float = 0.0
    dy: float = 0.0
    alpha: float = 1.0
    flash: float = 0.0
    flash_color: tuple = (255, 255, 255)


@dataclass
class Game:
    sounds: object
    layout: object = None                      # se asigna desde main
    active: str | None = None
    anim: Anim | None = None
    effects: list = field(default_factory=list)
    message: tuple = ("", COLOR_OK, 0.0)       # texto, color, hasta cuando
    log: list[str] = field(default_factory=list)
    balls: list[Ball] = field(default_factory=list)
    _queue: list = field(default_factory=list)
    _shake: tuple = (0.0, 0.0)                 # amplitud, hasta cuando

    def __post_init__(self):
        if not self.balls:
            self.balls = [Ball(name, data["id"])
                          for name, data in cfg.POKEMON.items()]

    # ------------------------------------------------------------------ util
    def ball_of(self, name: str) -> Ball | None:
        return next((b for b in self.balls if b.pokemon == name), None)

    def pokemon_id(self, name: str) -> int:
        return cfg.POKEMON[name]["id"]

    def type_color(self, move: str) -> tuple:
        return cfg.TYPE_COLORS.get(cfg.MOVES.get(move, ""), COLOR_GOLD)

    def _say(self, text: str, color=COLOR_OK, now=0.0):
        self.message = (text, color, now + cfg.MESSAGE_SECONDS)
        self.log.append(text)

    def _origin(self) -> tuple[int, int]:
        """Punto desde donde salen los efectos (el sprite en escena)."""
        if self.layout is None:
            return (240, 420)
        return self.layout.sprite_center

    def _schedule(self, fn, at: float):
        self._queue.append((at, fn))
        self._queue.sort(key=lambda item: item[0])

    def _announce(self, effect):
        """Agrega un cartel, quitando el anterior para que no se superpongan."""
        self.effects = [e for e in self.effects if not isinstance(e, BigText)]
        self.effects.append(effect)

    # ------------------------------------------------------------- reacciones
    def word_added(self, word: str, now: float):
        """Sonido corto al confirmar una palabra."""
        self.sounds.play("word", 0.7)

    def _pair_up(self, words: list[str]) -> list[tuple]:
        """Empareja cada comando con su argumento, este antes o despues.

        Asi valen las dos formas de decir lo mismo: "YO TE ELIJO TOGEKISS" y
        "TOGEKISS YO TE ELIJO". Devuelve una lista de (comando, argumento),
        y cualquiera de los dos puede venir en None.
        """

        def encaja(command: str, arg: str | None) -> bool:
            if arg is None:
                return False
            if command in (cfg.CMD_CHOOSE, cfg.CMD_RECALL):
                return arg in cfg.POKEMON
            if command == cfg.CMD_USE:
                return arg in cfg.MOVES
            return False

        pairs: list[tuple] = []
        i = 0
        while i < len(words):
            word = words[i]
            nxt = words[i + 1] if i + 1 < len(words) else None
            if word == cfg.CMD_DODGE:
                pairs.append((word, None))
                i += 1
            elif word in cfg.COMMANDS:                       # comando y argumento
                if encaja(word, nxt):
                    pairs.append((word, nxt))
                    i += 2
                else:
                    pairs.append((word, None))
                    i += 1
            elif nxt in cfg.COMMANDS and encaja(nxt, word):  # argumento y comando
                pairs.append((nxt, word))
                i += 2
            else:
                pairs.append((None, word))
                i += 1
        return pairs

    def send(self, words: list[str], now: float):
        """Interpreta la frase enviada y agenda las ordenes que contiene."""
        if not words:
            self.sounds.play("error")
            self._say("no hay nada que enviar", COLOR_ERROR, now)
            return

        self.sounds.play("send", 0.55)

        def at(i):
            return now + 0.15 + i * CHAIN_DELAY

        for step, (command, arg) in enumerate(self._pair_up(words)):
            if command == cfg.CMD_DODGE:
                self._schedule(self._dodge, at(step))
            elif command == cfg.CMD_CHOOSE:
                if arg is None:
                    self._schedule(
                        lambda t: self._fail(f"{cfg.CMD_CHOOSE}... ¿a quién?", t),
                        at(step))
                else:
                    self._schedule(lambda t, n=arg: self._summon(n, t), at(step))
            elif command == cfg.CMD_RECALL:
                self._schedule(lambda t, n=arg: self._recall(n, t), at(step))
            elif command == cfg.CMD_USE:
                if arg is None:
                    self._schedule(lambda t: self._fail("¿qué ataque?", t), at(step))
                else:
                    self._schedule(lambda t, m=arg: self._attack(m, t), at(step))
            elif arg in cfg.POKEMON:                         # nombre suelto
                self._schedule(lambda t, n=arg: self._mention(n, t), at(step))
            elif arg in cfg.MOVES:                           # ataque sin USA
                self._schedule(lambda t, m=arg: self._needs_use(m, t), at(step))

    # --------------------------------------------------------------- acciones
    def _fail(self, text: str, now: float):
        self.sounds.play("error", 0.8)
        self._say(text, COLOR_ERROR, now)

    def _summon(self, name: str, now: float):
        if self.active == name:
            self._mention(name, now)
            return
        if self.active is not None:                     # cambio de pokemon
            ball = self.ball_of(self.active)
            if ball:
                ball.set_open(False, now)
        ball = self.ball_of(name)
        if ball:
            ball.set_open(True, now)
        self.active = name
        self.anim = Anim("summon", now, 0.6)
        self.effects.append(Tint(now, (255, 255, 255), 0.3, 0.30))
        self.effects.append(Impact(now, self._origin(), COLOR_GOLD, 0.6, 22, 0.7, seed=1))
        self._announce(BigText(now, f"¡{name}, YO TE ELIJO!",
                               self._banner_pos(), COLOR_GOLD, 1.6, 52))
        self.sounds.play("ball_open", 0.9)
        self.sounds.cry(self.pokemon_id(name), 0.85)
        self._say(f"{name} entra en combate", COLOR_GOLD, now)

    def _recall(self, name: str | None, now: float):
        target = name or self.active
        if target is None or self.active != target:
            self._fail("no hay ningún Pokémon fuera", now)
            return
        ball = self.ball_of(target)
        if ball:
            ball.set_open(False, now)
        self.anim = Anim("recall", now, 0.5, (90, 90, 255))
        self._announce(BigText(now, f"¡REGRESA, {target}!",
                               self._banner_pos(), (120, 120, 255), 1.4, 46))
        self.sounds.play("ball_return", 0.9)
        self._say(f"{target} vuelve a su pokébola", (150, 150, 255), now)
        self.active = None

    def _attack(self, move: str, now: float):
        if self.active is None:
            self._fail(f"saca a un Pokémon con {cfg.CMD_CHOOSE}", now)
            return
        if move not in cfg.POKEMON[self.active]["moves"]:
            self._fail(f"{self.active} no aprende {move}", now)
            return

        tipo = cfg.MOVES[move]
        color = cfg.TYPE_COLORS[tipo]
        self.anim = Anim("attack", now, 0.55, color)
        self.effects.append(Impact(now, self._origin(), color, 0.8, 40,
                                   1.2, seed=random.randrange(1000)))
        self.effects.append(Tint(now, color, 0.4, 0.22))
        self._announce(BigText(now, move, self._banner_pos(), color, 1.5, 62))
        self.sounds.play(tipo, 1.0)
        if tipo == "TIERRA":                             # el terremoto sacude todo
            self._shake = (14.0, now + 0.8)
        self._say(f"{self.active} usa {move} ({tipo})", color, now)

    def _dodge(self, now: float):
        if self.active is None:
            self._fail(f"saca a un Pokémon con {cfg.CMD_CHOOSE}", now)
            return
        self.anim = Anim("dodge", now, 0.5)
        self._announce(BigText(now, "¡ESQUIVA!", self._banner_pos(),
                               (240, 240, 240), 1.2, 48))
        self.sounds.play("dodge", 0.9)
        self._say(f"{self.active} esquiva el ataque", COLOR_OK, now)

    def _mention(self, name: str, now: float):
        if self.active != name:
            self._fail(f"usa {cfg.CMD_CHOOSE} para sacar a {name}", now)
            return
        self.anim = Anim("cheer", now, 0.6)
        self.sounds.cry(self.pokemon_id(name), 0.8)
        self._say(f"{name} responde a su nombre", COLOR_GOLD, now)

    def _needs_use(self, move: str, now: float):
        self._fail(f"di {cfg.CMD_USE} antes de {move}", now)

    # ----------------------------------------------------------------- estado
    def _banner_pos(self) -> tuple[int, int]:
        if self.layout is None:
            return (640, 300)
        return self.layout.banner_pos

    def update(self, now: float):
        while self._queue and self._queue[0][0] <= now:
            _, fn = self._queue.pop(0)
            fn(now)
        self.effects = [e for e in self.effects if e.alive(now)]
        if self.anim is not None and self.anim.done(now):
            self.anim = None

    def shake_offset(self, now: float) -> tuple[int, int]:
        amp, until = self._shake
        if now >= until:
            return 0, 0
        left = (until - now) / 0.8
        a = amp * left
        return (int(math.sin(now * 60) * a), int(math.sin(now * 47 + 1.3) * a * 0.6))

    def sprite_state(self, now: float) -> SpriteState:
        """Escala, desplazamiento y destello del sprite para este frame."""
        st = SpriteState(visible=self.active is not None)
        anim = self.anim
        if anim is None:
            if st.visible:                                # respiracion suave
                st.dy = math.sin(now * 2.2) * 3
            return st

        t = anim.t(now)
        if anim.kind == "summon":
            st.visible = True
            st.scale = 0.25 + 0.9 * min(1.0, t / 0.55) - 0.15 * math.sin(math.pi * t)
            st.alpha = min(1.0, t / 0.25)
            st.flash = max(0.0, 1 - t / 0.45)
        elif anim.kind == "recall":
            st.visible = True
            st.scale = max(0.05, 1 - t)
            st.alpha = max(0.0, 1 - t * 0.9)
            st.flash = 0.55
            st.flash_color = anim.color
            st.dy = -20 * t
        elif anim.kind == "attack":
            st.dx = math.sin(math.pi * t) * 46
            st.dy = -math.sin(math.pi * t) * 14
            st.flash = max(0.0, 0.6 - t)
            st.flash_color = anim.color
        elif anim.kind == "dodge":
            # Hacia la derecha: el sprite esta pegado al borde izquierdo.
            st.dx = math.sin(math.pi * t) * 80
            st.dy = -abs(math.sin(2 * math.pi * t)) * 18
            st.alpha = 0.45 if 0.2 < t < 0.7 else 1.0
        elif anim.kind == "cheer":
            st.dy = -abs(math.sin(math.pi * t)) * 34
        return st

    def message_now(self, now: float) -> tuple[str, tuple] | None:
        text, color, until = self.message
        if not text or now >= until:
            return None
        return text, color

    def draw_effects(self, frame, now: float):
        for effect in self.effects:
            effect.draw(frame, now)
