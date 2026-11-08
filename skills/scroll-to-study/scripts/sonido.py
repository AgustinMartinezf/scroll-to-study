"""Audio sin ffmpeg: música de fondo sintetizada y mezcla de todas las pistas en una.

Todo con numpy + soundfile (libsndfile lee y escribe MP3), para que la herramienta no dependa de
programas externos en Windows, Mac o Linux.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100


def a_estereo(a: np.ndarray, sr: int) -> np.ndarray:
    """Cualquier audio -> float32 estéreo a 44,1 kHz (interpolación lineal; la voz llega a 22 kHz)."""
    a = np.asarray(a, dtype=np.float32)
    if a.ndim == 1:
        a = a[:, None]
    if a.shape[1] == 1:
        a = np.repeat(a, 2, axis=1)
    a = a[:, :2]
    if sr != SR and len(a):
        n = int(round(len(a) * SR / sr))
        x = np.linspace(0, len(a) - 1, n)
        a = np.stack([np.interp(x, np.arange(len(a)), a[:, c]) for c in range(2)], axis=1).astype(np.float32)
    return a


def musica(dur: float) -> np.ndarray:
    """Pad suave en La menor, del largo del video, con entrada y salida en fundido."""
    t = np.arange(int(dur * SR)) / SR
    # pasabajos de un polo a 1200 Hz: sobre una suma de senos equivale a escalar cada uno por |H(f)|
    k = 1 - np.exp(-2 * np.pi * 1200 / SR)
    g = lambda f: abs(k / (1 - (1 - k) * np.exp(-2j * np.pi * f / SR)))
    def voz(f1, f2, f3, mod):
        return (0.25 * g(f1) * np.sin(2 * np.pi * f1 * t) + 0.18 * g(f2) * np.sin(2 * np.pi * f2 * t)
                + 0.15 * g(f3) * np.sin(2 * np.pi * f3 * t) + 0.08 * g(261.63) * np.sin(2 * np.pi * 261.63 * t) * mod)
    a = np.stack([voz(110, 164.81, 220, 0.5 + 0.5 * np.sin(2 * np.pi * 0.125 * t)),
                  voz(110.4, 165.2, 220.6, 0.5 + 0.5 * np.cos(2 * np.pi * 0.125 * t))], axis=1)
    env = np.minimum(1, np.minimum(t / 1.5, np.maximum(0, (dur - t) / 2)))
    return (a * env[:, None]).astype(np.float32)


def mezclar(pistas: list[tuple[np.ndarray, float, float, float]], dur: float) -> np.ndarray:
    """pistas: (audio estéreo 44,1 kHz, inicio, duración, volumen). Suma sin normalizar."""
    total = np.zeros((int(round(dur * SR)), 2), dtype=np.float32)
    for a, ini, d, vol in pistas:
        i = int(round(ini * SR))
        trozo = a[:max(0, min(int(round(d * SR)), len(total) - i))] * vol
        total[i:i + len(trozo)] += trozo
    pico = float(np.abs(total).max()) if len(total) else 0
    if pico > 0.99:                                 # nunca saturar
        total *= 0.99 / pico
    return total


def leer(p: Path) -> np.ndarray:
    a, sr = sf.read(str(p), dtype="float32", always_2d=True)
    return a_estereo(a, sr)


def escribir_mp3(a: np.ndarray, p: Path) -> None:
    sf.write(str(p), a, SR, format="MP3", subtype="MPEG_LAYER_III")
