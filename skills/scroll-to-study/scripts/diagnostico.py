"""`s2s.py diagnostico`: qué está instalado y qué falta, una línea por cosa.

Revisa la versión de Python, cada paquete de requirements.txt, la voz de cada idioma, gsap y KaTeX en la
carpeta de datos y, como opcionales (solo para `s2s.py mp4`), Playwright con su Chromium y ffmpeg.
No usa la red: solo mira lo que ya está en esta computadora.
"""
from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

import mp4
from config import CFG, DATOS
from etapas import IDIOMAS

AQUI = Path(__file__).resolve().parent
REQUISITOS = AQUI.parent / "requirements.txt"
PYTHON_MINIMO = (3, 10)


def version_python() -> tuple[int, int]:
    return sys.version_info[:2]


def version_de(paquete: str) -> str | None:
    """La versión instalada de un paquete de pip, o None si no está."""
    try:
        return metadata.version(paquete)
    except metadata.PackageNotFoundError:
        return None


def soundfile_con_mp3() -> bool:
    try:
        import soundfile
        return "MP3" in soundfile.available_formats()
    except Exception:
        return False


def _numeros(v: str) -> tuple[int, ...]:
    """"2.1.0" -> (2, 1, 0); "1.26.0rc1" -> (1, 26, 0): alcanza para comparar contra un mínimo."""
    return tuple(int(re.match(r"\d*", p)[0] or 0) for p in v.split("."))


def requisitos(archivo: Path = REQUISITOS) -> list[tuple[str, str | None]]:
    """[(paquete, versión mínima o None)] de requirements.txt."""
    salida = []
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#")[0].strip()
        if not linea:
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)\s*(?:>=\s*([\w.]+))?", linea)
        if m:
            salida.append((m[1], m[2]))
    return salida


def revisar(archivo: Path = REQUISITOS) -> list[tuple[str, str | None, str | None]]:
    """[(qué, None si está bien o qué hacer, None si es obligatorio o para qué es opcional)]."""
    py = mp4._python()
    filas: list[tuple[str, str | None, str | None]] = []
    v = version_python()
    filas.append((f"python {v[0]}.{v[1]}",
                  None if v >= PYTHON_MINIMO else
                  f"hace falta Python {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} o más nuevo: instalalo desde python.org",
                  None))
    pip = f"{py} -m pip install -r {_comillas(archivo)}"
    for paquete, minimo in requisitos(archivo):
        instalada = version_de(paquete)
        if instalada is None:
            arreglo = f"no está instalado: {pip}"
        elif minimo and _numeros(instalada) < _numeros(minimo):
            arreglo = f"tenés {instalada} y hace falta {minimo} o más: {py} -m pip install -U \"{paquete}>={minimo}\""
        elif paquete == "soundfile" and not soundfile_con_mp3():
            arreglo = f"tu libsndfile no escribe MP3: {py} -m pip install -U \"soundfile>=0.12\""
        else:
            arreglo = None
        filas.append((f"{paquete} {instalada}" if instalada else paquete, arreglo, None))
    s2s = f"{py} {_comillas(AQUI / 's2s.py')}"
    voces = {i: voz_instalada(IDIOMAS[i]["voz"]) for i in sorted(IDIOMAS)}
    for idioma, ok in voces.items():
        # con una voz alcanza: la del otro idioma solo hace falta para videos en ese idioma
        nota = f"solo para videos con --idioma {idioma}" if any(voces.values()) else None
        filas.append((f"voz {idioma} ({IDIOMAS[idioma]['voz']})", None if ok else f"{s2s} instalar --idioma {idioma}",
                      nota))
    filas.append(("gsap", None if Path(CFG["gsap"]).exists() else f"{s2s} instalar", None))
    filas.append(("katex", None if (Path(CFG["katex"]) / "katex.min.js").exists() else f"{s2s} instalar", None))
    for nombre, arreglo in mp4.dependencias():
        filas.append((nombre, arreglo, "para s2s.py mp4"))
    return filas


def voz_instalada(voz: str) -> bool:
    modelo = Path(CFG["voces"][voz])
    return modelo.exists() and Path(str(modelo) + ".json").exists()


def _comillas(p: Path) -> str:
    s = str(p)
    return f'"{s}"' if " " in s else s


def imprimir(filas: list[tuple[str, str | None, str | None]]) -> int:
    """Imprime una línea por cosa y devuelve 1 si falta algo obligatorio (lo opcional no cuenta)."""
    ancho = max(len(n) for n, _, _ in filas)
    for nombre, arreglo, opcional in filas:
        etiqueta = f"{nombre:<{ancho}}"
        if arreglo is None:
            print(f"  {etiqueta}  ok")
        else:
            print(f"  {etiqueta}  {f'(opcional, {opcional}) ' if opcional else ''}{arreglo}")
    obligatorios = [n for n, arreglo, opcional in filas if arreglo and not opcional]
    print(f"datos en {DATOS}")
    if obligatorios:
        print(f"falta arreglar: {', '.join(obligatorios)}")
        return 1
    print("todo lo necesario está instalado")
    return 0
