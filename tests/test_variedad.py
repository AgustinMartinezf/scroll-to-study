"""Que los videos no salgan todos iguales ni con el sesgo de Bases de Datos con el que nació la herramienta."""
import json
import os
import re
import subprocess
import sys

from compile import compilar
from conftest import SKILL
from etapas import escribir_salidas
from voz_falsa import generar

LEX = json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8"))


def _cabeceras(html: str, elemento_id: str) -> str:
    """El html de la cabecera (div chead / lhead) del elemento con ese id."""
    m = re.search(rf'id="{elemento_id}"[^>]*>(<div class="(?:chead|lhead)".*?</div>)', html)
    assert m, f"no encontré la cabecera de {elemento_id}"
    return m[1]


def test_sin_icon_no_hay_icono_por_defecto(tmp_path):
    guion = {
        "bloques": [{"fuentes": ["A1"], "comprobar": [], "elementos": [
            {"type": "table", "id": "k", "title": "claves", "cols": ["clave", "firma"], "rows": [["KSK", "ZSK"]]},
            {"type": "list", "id": "l", "title": "pasos", "items": [["l1", "uno"]]},
            {"type": "chart", "id": "g", "title": "tiempos", "bars": [["a", 1], ["b", 2]]},
            {"type": "venn", "id": "v", "title": "conjuntos", "sets": ["A", "B"]},
            {"type": "table", "id": "c", "title": "con ícono", "icon": "key", "cols": ["a"], "rows": [["1"]]}],
            "frases": ["La {show k}tabla, la {show l}lista, el {show g}gráfico y el {show v}diagrama.",
                       "Y una {show c}tabla con ícono."]}],
        "final": {"frases": ["Acordate: {show fl1}uno.", "{show fnext}Mañana: dos."], "lineas": ["uno"], "mañana": "dos"},
    }
    spec, rep = compilar(guion, LEX, SKILL / "scripts" / "iconos")
    assert rep.errores == []
    d = tmp_path / "t01"
    escribir_salidas(d, spec)
    generar(d)
    subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d)], check=True,
                   capture_output=True, env={**os.environ, "S2S_DATOS": str(tmp_path / "datos")})
    html = (d / "index.html").read_text(encoding="utf-8")
    for i in ("k", "l", "g", "v"):
        cabeza = _cabeceras(html, i)
        assert "<svg" not in cabeza and "<span>" in cabeza     # el título solo
    assert "<svg" in _cabeceras(html, "c")                     # con «icon», el ícono sigue
