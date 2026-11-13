"""reproduccion.js (lo compartido entre la lista y la app sobre el iframe del video), sus funciones puras
probadas con node, sin navegador. Si node no está instalado, se saltean."""
import json
import shutil
import subprocess

import pytest

from conftest import SKILL

REPRODUCCION = SKILL / "scripts" / "reproduccion.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node no está instalado")


def correr(cuerpo: str):
    """cuerpo: JS que usa R (el módulo) y termina con `return <valor>`."""
    prog = (f"const R = require({json.dumps(str(REPRODUCCION))});\n"
            f"console.log(JSON.stringify((() => {{ {cuerpo} }})()));\n")
    r = subprocess.run([NODE], input=prog, capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_el_registro_de_cortes_tiene_tope_y_se_van_los_mas_viejos():
    r = correr("""
      let l = [];
      for (let i = 0; i < 60; i++) l = R.sumarCorte(l, { fecha: "2026-11-13T10:00:00Z", video: "t01", t: i, ua: "x" });
      const antes = [];
      R.sumarCorte(antes, { fecha: "f", video: "t01", t: 1, ua: "x" });
      return { tope: R.TOPE_CORTES, n: l.length, primero: l[0].t, ultimo: l[l.length - 1].t, antes };
    """)
    assert r == {"tope": 50, "n": 50, "primero": 10, "ultimo": 59, "antes": []}   # no cambia la lista que recibe


def test_cargar_cortes_descarta_lo_que_no_entiende():
    bueno = {"fecha": "2026-11-13T10:00:00Z", "video": "t02", "t": 12.5, "ua": "iPhone"}
    texto = json.dumps([bueno, {"video": "t01"}, None, dict(bueno, t=-1), dict(bueno, extra=1)])
    r = correr(f"return [R.cargarCortes({json.dumps(texto)}), R.cargarCortes('no es json'), R.cargarCortes(null),"
               f" R.cargarCortes({{}})];")
    assert r == [[bueno, bueno], [], [], []]


def test_cuenta_como_visto_desde_el_70_por_ciento():
    r = correr("""return [R.MINIMO_VISTO, R.contarComoVisto(28, 40), R.contarComoVisto(27.9, 40),
                          R.contarComoVisto(27.96, 40), R.contarComoVisto(0, 40),
                          R.contarComoVisto(undefined, 40), R.contarComoVisto(10, undefined)];""")
    # sin el dato (videos hechos antes) cuenta como siempre
    assert r == [0.7, True, False, True, False, True, True]
