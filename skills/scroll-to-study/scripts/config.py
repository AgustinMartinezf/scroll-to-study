"""Dónde están los recursos que usan engine.py, voice.py y reproductor.py.

Lo que viene con el skill (íconos, efectos, fuentes, estilos) está junto a este archivo.
Lo que se descarga una vez con `s2s.py instalar` (la voz y gsap) va a una carpeta de datos:
  1. S2S_DATOS, si está definida;
  2. ~/.scroll-to-study
(CLAUDE_PLUGIN_DATA no sirve: Claude Code no la pasa a los comandos que corre Claude.)
Un config.json en la carpeta de datos puede pisar cualquier ruta (relativas a esa carpeta).
"""
import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# En Windows la consola (y la tubería por la que Claude lee la salida) suele ser cp1252: «, → o ñ
# harían fallar un print. Todo lo que imprimen los scripts sale en UTF-8.
for _flujo in (sys.stdout, sys.stderr):
    if hasattr(_flujo, "reconfigure") and (_flujo.encoding or "").lower().replace("-", "") != "utf8":
        _flujo.reconfigure(encoding="utf-8", errors="replace")


def carpeta_datos() -> Path:
    for var in ("S2S_DATOS",):
        if os.environ.get(var):
            return Path(os.environ[var]).expanduser()
    return Path.home() / ".scroll-to-study"


DATOS = carpeta_datos()
VOZ_DEFECTO = "davefx"
VOCES = {   # nombre -> carpeta dentro de DATOS/voces, como la publica sherpa-onnx en GitHub
    "davefx": "vits-piper-es_ES-davefx-medium/es_ES-davefx-medium.onnx",          # español
    "hfc_male": "vits-piper-en_US-hfc_male-medium/en_US-hfc_male-medium.onnx",    # inglés (dataset CC BY-NC-SA)
}


def _cargar() -> dict:
    cfg = {
        "iconos": AQUI / "iconos",
        "sfx": AQUI / "sfx",
        "fuentes": AQUI / "fuentes",
        "css": AQUI / "engine.css",
        "js": AQUI / "engine.js",
        "gsap": DATOS / "gsap.min.js",
        "katex": DATOS / "katex",
        "voces": {n: DATOS / "voces" / r for n, r in VOCES.items()},
    }
    extra = DATOS / "config.json"
    if extra.exists():
        datos = json.loads(extra.read_text(encoding="utf-8"))
        desconocidas = set(datos) - set(cfg)
        if desconocidas:
            raise SystemExit(f"{extra}: claves desconocidas {sorted(desconocidas)}")
        for k, v in datos.items():
            cfg[k] = {n: DATOS / p for n, p in v.items()} if k == "voces" else DATOS / v
    return cfg


CFG = _cargar()
