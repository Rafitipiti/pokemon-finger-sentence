"""Sonido: gritos reales de los Pokemon y efectos sintetizados por tipo.

Los gritos son los .ogg de PokeAPI. Los efectos se generan con numpy al
arrancar (no hay que descargar nada) y todo se mezcla en un solo stream de
sounddevice, para que un grito y un ataque puedan sonar a la vez.
"""

from __future__ import annotations

import threading

import numpy as np

SR = 44100
_MAX_VOICES = 8


# --------------------------------------------------------------------------
# Sintesis
# --------------------------------------------------------------------------
def _t(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur), dtype=np.float32) / SR


def _env(n: int, attack=0.005, release=0.25) -> np.ndarray:
    """Envolvente simple: subida rapida y caida exponencial."""
    if n <= 0:
        return np.zeros(0, np.float32)
    e = np.ones(n, np.float32)
    a = min(n, max(1, int(SR * attack)))
    e[:a] = np.linspace(0, 1, a, dtype=np.float32)
    d = min(n, max(1, int(SR * release)))   # en sonidos cortos la caida ocupa todo
    e[-d:] *= np.exp(-np.linspace(0, 4, d, dtype=np.float32))
    return e


def _sine(freq, dur, amp=0.5) -> np.ndarray:
    t = _t(dur)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32) * _env(len(t))


def _sweep(f0, f1, dur, amp=0.5, wave="sine") -> np.ndarray:
    t = _t(dur)
    freq = np.linspace(f0, f1, len(t), dtype=np.float32)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    if wave == "saw":
        raw = 2 * ((phase / (2 * np.pi)) % 1.0) - 1
    elif wave == "square":
        raw = np.sign(np.sin(phase))
    else:
        raw = np.sin(phase)
    return (amp * raw).astype(np.float32) * _env(len(t))


def _noise(dur, amp=0.5) -> np.ndarray:
    n = int(SR * dur)
    rng = np.random.default_rng(7)
    return (amp * rng.standard_normal(n).astype(np.float32)) * _env(n)


def _lowpass(x: np.ndarray, k: int) -> np.ndarray:
    """Paso bajo barato: media movil de k muestras."""
    if k <= 1:
        return x
    kernel = np.ones(k, np.float32) / k
    return np.convolve(x, kernel, mode="same").astype(np.float32)


def _mix(*parts: np.ndarray) -> np.ndarray:
    n = max(len(p) for p in parts)
    out = np.zeros(n, np.float32)
    for p in parts:
        out[:len(p)] += p
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * 0.9).astype(np.float32)


def build_sfx() -> dict[str, np.ndarray]:
    """Banco de efectos. Todo se genera una vez, en milisegundos."""
    sfx = {}

    # Interfaz
    sfx["hover"] = _sine(1180, 0.05, 0.25)
    sfx["word"] = _mix(_sine(880, 0.07, 0.35), np.concatenate(
        [np.zeros(int(SR * 0.05), np.float32), _sine(1320, 0.08, 0.3)]))
    sfx["send"] = _mix(_sine(523, 0.5, 0.25), _sine(659, 0.5, 0.22), _sine(784, 0.5, 0.18))
    sfx["error"] = _mix(_sweep(220, 150, 0.14, 0.35, "square"), np.concatenate(
        [np.zeros(int(SR * 0.16), np.float32), _sweep(190, 120, 0.16, 0.3, "square")]))

    # Pokebolas
    sfx["ball_open"] = _mix(
        _sweep(420, 1500, 0.22, 0.4),
        _lowpass(_noise(0.3, 0.35), 6),
        np.concatenate([np.zeros(int(SR * 0.12), np.float32), _sine(1760, 0.25, 0.22)]),
    )
    sfx["ball_return"] = _mix(
        _sweep(1500, 320, 0.32, 0.4),
        np.concatenate([np.zeros(int(SR * 0.28), np.float32), _sine(240, 0.18, 0.3)]),
    )
    sfx["dodge"] = _mix(_lowpass(_noise(0.28, 0.55), 14), _sweep(900, 1800, 0.18, 0.12))

    # Ataques por tipo
    rng = np.random.default_rng(11)
    crackle = np.zeros(int(SR * 0.55), np.float32)
    idx = rng.integers(0, len(crackle) - 200, 90)
    for i in idx:
        crackle[i:i + 120] += rng.standard_normal(120).astype(np.float32) * 0.5
    sfx["FUEGO"] = _mix(_lowpass(_noise(0.6, 0.6), 8), crackle * _env(len(crackle)),
                        _sine(70, 0.4, 0.4))
    sfx["TIERRA"] = _mix(_lowpass(_noise(0.85, 1.0), 60), _sine(45, 0.8, 0.6),
                         _sweep(90, 40, 0.8, 0.35))
    sfx["DRAGÓN"] = _mix(_sweep(420, 70, 0.7, 0.5, "saw"), _lowpass(_noise(0.7, 0.4), 20),
                         _sine(110, 0.6, 0.25))
    sfx["HADA"] = _mix(
        _sine(1046, 0.45, 0.28),
        np.concatenate([np.zeros(int(SR * 0.08), np.float32), _sine(1318, 0.42, 0.26)]),
        np.concatenate([np.zeros(int(SR * 0.16), np.float32), _sine(1568, 0.45, 0.24)]),
        np.concatenate([np.zeros(int(SR * 0.24), np.float32), _sine(2093, 0.4, 0.18)]),
    )
    sfx["VOLADOR"] = _mix(_lowpass(_noise(0.5, 0.7), 10), _sweep(700, 2200, 0.35, 0.15),
                          _sweep(2200, 600, 0.3, 0.12))
    sfx["attack"] = sfx["VOLADOR"]        # por si algun tipo no tiene sonido propio
    return sfx


def _resample(x: np.ndarray, src_sr: int) -> np.ndarray:
    if src_sr == SR:
        return x.astype(np.float32)
    n = int(len(x) * SR / src_sr)
    return np.interp(np.linspace(0, len(x) - 1, n),
                     np.arange(len(x)), x).astype(np.float32)


# --------------------------------------------------------------------------
# Mezclador
# --------------------------------------------------------------------------
class _Voice:
    """Un sonido en curso. Es una clase (y no un dict) a proposito: las listas
    de dicts con arrays dentro no se pueden comparar, y list.remove() falla."""

    __slots__ = ("samples", "pos", "gain")

    def __init__(self, samples, gain):
        self.samples = samples
        self.pos = 0
        self.gain = float(gain)


class Mixer:
    """Suma varias voces en un unico stream de salida."""

    def __init__(self, volume=0.8):
        self.volume = volume
        self.ok = False
        self._voices: list[_Voice] = []
        self._lock = threading.Lock()
        self._stream = None
        try:
            import sounddevice as sd

            self._stream = sd.OutputStream(samplerate=SR, channels=1, dtype="float32",
                                           blocksize=512, callback=self._callback)
            self._stream.start()
            self.ok = True
        except Exception as exc:                     # sin tarjeta, sin driver, etc.
            print(f"Audio desactivado ({type(exc).__name__}: {exc})")

    def _callback(self, outdata, frames, time_info, status):
        out = np.zeros(frames, np.float32)
        with self._lock:
            vivas = []
            for voice in self._voices:
                chunk = voice.samples[voice.pos:voice.pos + frames]
                out[:len(chunk)] += chunk * voice.gain
                voice.pos += frames
                if voice.pos < len(voice.samples):
                    vivas.append(voice)
            self._voices = vivas
        np.clip(out * self.volume, -1.0, 1.0, out=out)
        outdata[:, 0] = out

    def play(self, samples: np.ndarray | None, gain=1.0):
        if not self.ok or samples is None or not len(samples):
            return
        with self._lock:
            if len(self._voices) >= _MAX_VOICES:
                self._voices.pop(0)
            self._voices.append(_Voice(samples, gain))

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass


class SoundBank:
    """Efectos + gritos, con una API corta: play("word"), cry(468)."""

    def __init__(self, pokemon_ids=(), volume=0.8, enabled=True):
        self.mixer = Mixer(volume) if enabled else None
        self.sfx = build_sfx() if enabled else {}
        self.cries: dict[int, np.ndarray] = {}
        if enabled:
            self._load_cries(pokemon_ids)

    @property
    def ok(self) -> bool:
        return bool(self.mixer and self.mixer.ok)

    def _load_cries(self, pokemon_ids):
        try:
            import soundfile as sf
        except ImportError:
            print("soundfile no esta instalado: los gritos se reemplazan por un efecto.")
            return
        import assets

        for pid in pokemon_ids:
            path = assets.cry_path(pid)
            if not path.exists():
                continue
            try:
                data, sr = sf.read(path, dtype="float32", always_2d=True)
            except Exception as exc:
                print(f"  no pude leer el grito {path.name}: {exc}")
                continue
            mono = data.mean(axis=1)
            mono = _resample(mono, sr)
            peak = float(np.max(np.abs(mono))) or 1.0
            self.cries[pid] = (mono / peak * 0.85).astype(np.float32)

    def play(self, name: str, gain=1.0):
        if self.mixer:
            self.mixer.play(self.sfx.get(name), gain)

    def cry(self, pokemon_id: int, gain=1.0):
        if not self.mixer:
            return
        sample = self.cries.get(pokemon_id)
        if sample is None:
            self.play("ball_open", gain)          # reserva si falto el .ogg
        else:
            self.mixer.play(sample, gain)

    def close(self):
        if self.mixer:
            self.mixer.close()
