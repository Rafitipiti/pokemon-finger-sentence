"""Cámara en un hilo aparte.

Leer un frame cuesta bastante (con poca luz la exposición sube y la cámara baja
a ~17 FPS). Si se lee en el hilo principal, ese tiempo se suma al de los
modelos y el dibujado; leyendo en paralelo, el bucle va al ritmo del más lento
de los dos en vez de a la suma.
"""

from __future__ import annotations

import threading

import cv2


def open_capture(index: int, width: int, height: int):
    """Abre la cámara probando primero el backend nativo de Windows."""
    for backend in (cv2.CAP_DSHOW, cv2.CAP_ANY):
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap
        cap.release()
    return None


class CameraStream:
    """Mantiene siempre disponible el último frame capturado."""

    def __init__(self, index=0, width=1280, height=720):
        self.cap = open_capture(index, width, height)
        self._frame = None
        self._lock = threading.Lock()
        self._new = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        if self.ok:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    @property
    def ok(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def _loop(self):
        while not self._stop.is_set():
            got, frame = self.cap.read()
            if not got:
                break
            with self._lock:
                self._frame = frame          # cap.read() ya devuelve un array nuevo
            self._new.set()
        self._stop.set()
        self._new.set()                      # despierta a quien esté esperando

    def read(self, timeout=2.0):
        """Espera a que haya un frame nuevo y lo devuelve (None si se acabó)."""
        if not self._new.wait(timeout):
            return None
        self._new.clear()
        if self._stop.is_set() and self._frame is None:
            return None
        with self._lock:
            return self._frame

    def release(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()
