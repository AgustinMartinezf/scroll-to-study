"""progreso.js (la lógica del progreso de la lista) probado con node, suelto, sin navegador.

Cada test arma un programa chico que carga progreso.js, lo corre con `node` y compara en Python lo que
imprime (JSON). Si node no está instalado, se saltean."""
import json
import shutil
import subprocess

import pytest

from conftest import SKILL

PROGRESO = SKILL / "scripts" / "progreso.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node no está instalado")

TEMAS = [{"id": "t01"}, {"id": "t02"}, {"id": "t03"}]


def correr(cuerpo: str):
    """cuerpo: JS que usa P (el módulo) y TEMAS, y termina con `return <valor>`."""
    prog = (f"const P = require({json.dumps(str(PROGRESO))});\n"
            f"const TEMAS = {json.dumps(TEMAS)};\n"
            f"console.log(JSON.stringify((() => {{ {cuerpo} }})()));\n")
    r = subprocess.run([NODE], input=prog, capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_marcar_visto_guarda_cada_dia_aparte_sin_tocar_el_original():
    r = correr("""
      const a = P.cargar(null, TEMAS);
      const b = P.marcarVisto(a, "t01", "2026-11-11");
      const c = P.marcarVisto(P.marcarVisto(b, "t02", "2026-11-12"), "t02", "2026-11-12");
      return { a, b, c };
    """)
    assert r["a"] == {"v": 2, "cur": "t01", "dias": {}}
    assert r["b"]["dias"] == {"2026-11-11": ["t01"]}
    # el cambio de día no borra lo de ayer, y repetir un tema el mismo día no lo duplica
    assert r["c"]["dias"] == {"2026-11-11": ["t01"], "2026-11-12": ["t02"]}


def test_migra_v1_sin_perder_cur_ni_lo_visto_ese_dia():
    viejo = json.dumps({"dia": "2026-11-12", "vistos": [0, 2, 2, 9], "cur": 1})
    r = correr(f"return P.cargar({json.dumps(viejo)}, TEMAS);")
    assert r == {"v": 2, "cur": "t02", "dias": {"2026-11-12": ["t01", "t03"]}}   # el índice 9 no existe


def test_cargar_descarta_lo_que_no_entiende():
    r = correr("""
      return [
        P.cargar("{roto", TEMAS),
        P.cargar(JSON.stringify({ v: 2, cur: "t99", dias: { "ayer": ["t01"], "2026-11-10": ["t01", 3, "t01", "viejo"] } }), TEMAS),
        P.cargar(null, []),
      ];
    """)
    assert r[0] == {"v": 2, "cur": "t01", "dias": {}}
    # cur desconocido vuelve al primero; los ids que ya no están en la lista se conservan como historia
    assert r[1] == {"v": 2, "cur": "t01", "dias": {"2026-11-10": ["t01", "viejo"]}}
    assert r[2] == {"v": 2, "cur": None, "dias": {}}


def test_que_toca_hoy():
    r = correr("""
      const e = P.cargar(null, TEMAS);
      const uno = P.marcarVisto(e, "t01", "2026-11-10");
      const todos = P.marcarVisto(P.marcarVisto(P.marcarVisto(uno, "t02", "2026-11-11"), "t03", "2026-11-11"), "t02", "2026-11-12");
      const otraVez = P.marcarVisto(todos, "t01", "2026-11-12");
      const futuro = P.marcarVisto(e, "t01", "2026-12-01");
      return [P.queTocaHoy(e, TEMAS, "2026-11-12"), P.queTocaHoy(uno, TEMAS, "2026-11-12"),
              P.queTocaHoy(todos, TEMAS, "2026-11-12"), P.queTocaHoy(otraVez, TEMAS, "2026-11-12"),
              P.queTocaHoy(futuro, TEMAS, "2026-11-12"), P.queTocaHoy(e, [], "2026-11-12")];
    """)
    # nada visto -> el primero; uno visto -> el primero nunca visto; todos vistos -> el visto hace más tiempo
    # (t01 el 10); después t03 (11; t02 se volvió a ver el 12); un día futuro no cuenta; sin temas, null
    assert r == ["t01", "t02", "t01", "t03", "t01", None]


def test_racha_con_un_dia_salteado():
    r = correr("""
      let e = P.cargar(null, TEMAS);
      for (const f of ["2026-11-07", "2026-11-08", "2026-11-10", "2026-11-11", "2026-11-12"]) e = P.marcarVisto(e, "t01", f);
      const finDeMes = ["2026-02-27", "2026-02-28", "2026-03-01"].reduce((s, f) => P.marcarVisto(s, "t01", f), P.cargar(null, TEMAS));
      return { hoy: P.racha(e, "2026-11-12"), antes: P.racha(e, "2026-11-08"),
               sinVerHoy: P.racha(e, "2026-11-13"), cortada: P.racha(e, "2026-11-14"),
               nada: P.racha(P.cargar(null, TEMAS), "2026-11-12"), finDeMes: P.racha(finDeMes, "2026-03-01") };
    """)
    assert r["hoy"] == 3          # el 9 no se vio: cuentan 10, 11 y 12
    assert r["antes"] == 2
    assert r["sinVerHoy"] == 3    # hoy todavía no vio nada: la racha hasta ayer sigue viva
    assert r["cortada"] == 0      # pasó un día entero (el 13) sin ver nada
    assert r["nada"] == 0
    assert r["finDeMes"] == 3     # 27 y 28 de febrero, 1 de marzo


def test_exportar():
    r = correr("""
      let e = P.cargar(null, TEMAS);
      e = P.marcarVisto(e, "t02", "2026-11-12");
      e = P.marcarVisto(e, "t01", "2026-11-11");
      const x = P.exportar(e, { titulo: "Redes", fecha: "2026-11-12", generado: "2026-11-12T10:00:00.000Z" });
      x.dias["2026-11-12"].push("t09");    // la exportación es una copia: no cambia el estado
      return { x, e, sinDatos: Object.keys(P.exportar(e)).sort() };
    """)
    assert list(r["x"]["dias"]) == ["2026-11-11", "2026-11-12"]          # en orden de fecha
    assert r["x"] == {"titulo": "Redes", "generado": "2026-11-12T10:00:00.000Z",
                      "dias": {"2026-11-11": ["t01"], "2026-11-12": ["t02", "t09"]}, "racha": 2}
    assert r["e"]["dias"]["2026-11-12"] == ["t02"]
    assert r["sinDatos"] == ["dias", "generado", "racha", "titulo"]


def test_funciona_suelto_como_script_de_navegador():
    """Sin module/require (como en un <script> o en otra app): deja las funciones en Progreso."""
    prog = (f"const fs = require('fs'), vm = require('vm');\n"
            f"const ctx = {{ self: {{}} }};\n"
            f"vm.runInNewContext(fs.readFileSync({json.dumps(str(PROGRESO))}, 'utf8'), ctx);\n"
            f"const P = ctx.self.Progreso;\n"
            f"console.log(JSON.stringify([Object.keys(P).sort(), P.fechaLocal(new Date(2026, 0, 5))]));\n")
    r = subprocess.run([NODE], input=prog, capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    claves, fecha = json.loads(r.stdout)
    assert {"cargar", "marcarVisto", "queTocaHoy", "racha", "exportar"} <= set(claves)
    assert fecha == "2026-01-05"
