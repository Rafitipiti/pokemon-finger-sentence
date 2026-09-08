"""Rastreo con MediaPipe: punta del indice y angulo del codo."""

from __future__ import annotations

import math
from dataclasses import dataclass

import mediapipe as mp

mp_hands = mp.solutions.hands
mp_pose = mp.solutions.pose

INDEX_TIP = mp_hands.HandLandmark.INDEX_FINGER_TIP.value


@dataclass
class HandReading:
    """Lectura de una mano: punta del indice normalizada (0-1) + landmarks crudos."""

    tip: tuple[float, float]
    side: str
    score: float
    landmarks: object


@dataclass
class ArmReading:
    """Postura del brazo: angulo del codo, inclinacion del brazo y sus puntos.

    `angle`      : grados en el codo (hombro-codo-muneca). 180 = estirado, 90 = en L.
    `upper_tilt` : cuanto se desvia el brazo (hombro-codo) de la horizontal.
                   0 = brazo extendido al costado, 90 = brazo colgando.
    Los puntos van normalizados (0-1) para poder dibujarlos sobre el frame.
    """

    angle: float
    upper_tilt: float
    shoulder: tuple[float, float]
    elbow: tuple[float, float]
    wrist: tuple[float, float]

    @property
    def wrist_above_elbow(self) -> bool:
        return self.wrist[1] < self.elbow[1]


class IndexFingerTracker:
    """Devuelve la punta del dedo indice de la mano elegida."""

    def __init__(self, side="right", strict=True, min_detection=0.6, min_tracking=0.5):
        self.side = side.capitalize()
        self.strict = strict
        self._hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,          # rapido: nos basta la punta del indice
            min_detection_confidence=min_detection,
            min_tracking_confidence=min_tracking,
        )

    def find(self, rgb) -> HandReading | None:
        result = self._hands.process(rgb)
        hands = result.multi_hand_landmarks
        if not hands:
            return None

        handedness = result.multi_handedness or []
        wanted: HandReading | None = None
        fallback: HandReading | None = None

        for i, landmarks in enumerate(hands):
            label, score = "Unknown", 0.0
            if i < len(handedness):
                cls = handedness[i].classification[0]
                label, score = cls.label, cls.score
            tip = landmarks.landmark[INDEX_TIP]
            reading = HandReading((tip.x, tip.y), label, score, landmarks)

            if label == self.side:
                if wanted is None or score > wanted.score:
                    wanted = reading
            elif fallback is None or score > fallback.score:
                fallback = reading

        if wanted is not None:
            return wanted
        return None if self.strict else fallback

    def close(self):
        self._hands.close()


class ArmAngleTracker:
    """Angulo del codo (hombro-codo-muneca) con MediaPipe Pose."""

    def __init__(self, side="right", mirrored=True, min_visibility=0.5):
        self.side = side.lower()
        # La imagen espejada invierte la anatomia que ve el modelo: lo que el
        # llama "left" es en realidad tu lado derecho. Se puede alternar en vivo.
        self.mirrored = mirrored
        self.min_visibility = min_visibility
        self._pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def toggle_mirror(self):
        self.mirrored = not self.mirrored

    @property
    def effective_side(self) -> str:
        if not self.mirrored:
            return self.side
        return "left" if self.side == "right" else "right"

    def _ids(self):
        P = mp_pose.PoseLandmark
        if self.effective_side == "right":
            return P.RIGHT_SHOULDER, P.RIGHT_ELBOW, P.RIGHT_WRIST
        return P.LEFT_SHOULDER, P.LEFT_ELBOW, P.LEFT_WRIST

    def read(self, rgb) -> ArmReading | None:
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return None
        lms = result.pose_landmarks.landmark
        points = []
        for lm_id in self._ids():
            lm = lms[lm_id.value]
            if lm.visibility < self.min_visibility:
                return None
            points.append((lm.x, lm.y))
        shoulder, elbow, wrist = points

        # Los landmarks vienen normalizados 0-1 en cada eje, asi que en una imagen
        # 16:9 los angulos salen deformados: hay que reescalar x por el aspecto.
        aspect = rgb.shape[1] / rgb.shape[0]
        sq = [(x * aspect, y) for x, y in points]
        angle = angle_between(*sq)
        upper_tilt = abs(horizontal_tilt(sq[0], sq[1]))
        return ArmReading(angle, upper_tilt, shoulder, elbow, wrist)

    def close(self):
        self._pose.close()


class AngleHoldTrigger:
    """Se dispara una vez cuando el angulo se mantiene en la banda objetivo.

    Para volver a dispararse hay que salir de la banda (asi un brazo quieto
    en 90 grados no cierra oraciones en cadena).
    """

    def __init__(self, target=90.0, tolerance=20.0, hold_seconds=0.8):
        self.target = target
        self.tolerance = tolerance
        self.hold_seconds = hold_seconds
        self._since: float | None = None
        self._armed = True

    @property
    def progress(self) -> float:
        if self._since is None:
            return 0.0
        return min(1.0, self._elapsed / self.hold_seconds) if self.hold_seconds else 1.0

    def in_band(self, angle: float | None) -> bool:
        return angle is not None and abs(angle - self.target) <= self.tolerance

    def update(self, angle: float | None, now: float) -> bool:
        if not self.in_band(angle):
            self._since = None
            self._armed = True
            self._elapsed = 0.0
            return False
        if not self._armed:
            return False
        if self._since is None:
            self._since = now
        self._elapsed = now - self._since
        if self._elapsed >= self.hold_seconds:
            self._since = None
            self._elapsed = 0.0
            self._armed = False
            return True
        return False

    _elapsed = 0.0


def arm_gesture_ok(arm, trigger, strict=True, upper_tolerance=35.0) -> tuple[bool, bool]:
    """Evalua el gesto de cierre. Devuelve (codo_ok, gesto_completo).

    En modo estricto no basta el codo en 90 grados (algo que pasa solo al
    senalar): el brazo tiene que estar horizontal y el antebrazo hacia arriba.
    """
    if arm is None:
        return False, False
    elbow_ok = trigger.in_band(arm.angle)
    if not elbow_ok:
        return False, False
    if not strict:
        return True, True
    return True, arm.upper_tilt <= upper_tolerance and arm.wrist_above_elbow


def horizontal_tilt(a, b) -> float:
    """Inclinacion en grados del segmento a-b respecto a la horizontal (-90..90)."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(dy, abs(dx)))


def angle_between(a, b, c) -> float:
    """Angulo en grados del vertice b, formado por los puntos a-b-c."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))
