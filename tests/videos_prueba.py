"""Videos de prueba con voz falsa: un guion, un estilo y lo que decide la animación (formato, semilla o lo que
se fuerce con S2S_ANIMACION). Los usan los tests de movimiento y la revisión visual (un video por formato)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import reproductor
from conftest import SKILL
from etapas import FORMATOS, escribir_salidas, validar_guion
from voz_falsa import generar

FIXTURES = SKILL.parents[1] / "tests" / "fixtures"
TITULO_REVISION = "Revisión 0.7.0"


def guion_de_formato(formato: str) -> dict:
    """El ejemplo de ese formato (es). El de avsb no tiene un bloque con dos elementos del mismo tipo, así que
    para ver la pantalla partida se usa una variante con dos fórmulas y dos chips en el mismo bloque."""
    if formato == "avsb":
        return json.loads((FIXTURES / "guion_avsb_partida.json").read_text(encoding="utf-8"))
    return json.loads((SKILL / "prompts" / "ejemplos" / f"{formato}.es.json").read_text(encoding="utf-8"))


def compilar_guion(g: dict) -> dict:
    fuentes = sorted({f for b in g["bloques"] for f in b["fuentes"]})
    inv = {"afirmaciones": [{"id": f, "texto": "", "cita": "", "estado": "ok"} for f in fuentes]}
    spec, errores, _ = validar_guion(g, inv, "es", "materia")
    assert errores == [], errores
    return spec


def motor(d: Path, estilo: str, semilla: str = "", formato: str = "", animacion: dict | None = None) -> Path:
    """Corre engine.py sobre la carpeta (ya con spec, timing y voz) y devuelve su index.html."""
    env = {**os.environ, "S2S_DATOS": str(d.parent / "datos")}
    for k in ("S2S_SEMILLA", "S2S_FORMATO", "S2S_ANIMACION"):
        env.pop(k, None)
    if semilla:
        env["S2S_SEMILLA"] = semilla
    if formato:
        env["S2S_FORMATO"] = formato
    if animacion:
        env["S2S_ANIMACION"] = json.dumps(animacion)
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d), estilo],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr[-3000:]
    return d / "index.html"


def video(spec: dict, d: Path, estilo: str = "cuaderno", semilla: str = "", formato: str = "",
          animacion: dict | None = None) -> Path:
    """El .html autocontenido del video."""
    escribir_salidas(d, spec)
    generar(d)
    motor(d, estilo, semilla, formato, animacion)
    return reproductor.construir(d, d.parent / f"{d.name}.html", d.name)


def video_de_formato(formato: str, estilo: str, carpeta: Path) -> Path:
    """El video de revisión de un formato en un estilo (el mismo que la revisión visual de la 0.7.0)."""
    assert formato in FORMATOS
    d = carpeta / f"{formato}-{estilo}" / f"t-{formato}"
    return video(compilar_guion(guion_de_formato(formato)), d, estilo, f"t-{formato}\n{TITULO_REVISION}", formato)


def estado(index_html: Path) -> dict:
    """El objeto S que engine.py le pasa a engine.js."""
    return json.loads(re.search(r"<script>const S = (\{.*?\});</script>", index_html.read_text(encoding="utf-8"))[1])
