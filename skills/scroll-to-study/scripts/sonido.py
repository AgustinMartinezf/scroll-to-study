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


# ---------------------------------------------------------------------------
# Volumen: −14 LUFS (lo que piden TikTok, Reels y Shorts) sin pasarse de −1 dBFS de pico
# ---------------------------------------------------------------------------

# filtros K de la ITU-R BS.1770 (coeficientes para 48 kHz); se aplican en frecuencia, solo para medir
_K = [([1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]),
      ([1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621])]


def _respuesta_k(n: int, sr: int) -> np.ndarray:
    f = np.fft.rfftfreq(n, 1 / sr)
    z = np.exp(-2j * np.pi * f / 48000)
    h = np.ones_like(z)
    for b, a in _K:
        h *= (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)
    return np.abs(h)


def lufs(a: np.ndarray, sr: int = SR) -> float:
    """Sonoridad integrada (BS.1770: filtro K, bloques de 400 ms, compuertas de −70 LUFS y −10 LU)."""
    n = len(a)
    if n < int(0.4 * sr):
        return -70.0
    k = _respuesta_k(n, sr)
    y = np.stack([np.fft.irfft(np.fft.rfft(a[:, c]) * k, n) for c in range(a.shape[1])], axis=1)
    blk, paso = int(0.4 * sr), int(0.1 * sr)
    p2 = np.concatenate([[0.0], np.cumsum((y ** 2).sum(axis=1))])
    inicios = np.arange(0, n - blk + 1, paso)
    z = (p2[inicios + blk] - p2[inicios]) / blk
    l = -0.691 + 10 * np.log10(np.maximum(z, 1e-12))
    z = z[l > -70]
    if not len(z):
        return -70.0
    rel = -0.691 + 10 * np.log10(z.mean()) - 10
    z = z[-0.691 + 10 * np.log10(z) > rel]
    return float(-0.691 + 10 * np.log10(z.mean()))


def limitar(a: np.ndarray, techo: float = 0.84) -> np.ndarray:
    """Limitador simple: baja la ganancia solo alrededor de los picos que pasan el techo (−1,5 dBFS: el MP3 sube un poco los picos)."""
    ven = int(0.005 * SR)
    n = len(a) // ven * ven
    if n == 0:
        return a
    pico = np.abs(a[:n]).max(axis=1).reshape(-1, ven).max(axis=1)
    g = np.minimum(1.0, techo / np.maximum(pico, 1e-9))
    pad = 6                                                   # ±30 ms alrededor de cada pico
    g = np.lib.stride_tricks.sliding_window_view(np.pad(g, pad, mode="edge"), 2 * pad + 1).min(axis=1)
    g = np.convolve(np.pad(g, 2, mode="edge"), np.ones(5) / 5, mode="valid")   # sin saltos
    gs = np.interp(np.arange(len(a)), np.arange(len(g)) * ven + ven / 2, g)
    out = a * gs[:, None]
    return np.clip(out, -techo, techo)


def normalizar(a: np.ndarray, objetivo: float = -14.0) -> np.ndarray:
    actual = lufs(a)
    if actual <= -69:
        return a
    return limitar(a * 10 ** ((objetivo - actual) / 20)).astype(np.float32)
