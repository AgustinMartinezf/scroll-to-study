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
# los mismos, con preguntas: entran al repaso
Q = [{"texto": "¿?", "opciones": ["a", "b", "c"], "correcta": 0, "explicacion": "a", "general": False}]
CON_PREGUNTAS = [{"id": "t01", "preguntas": Q}, {"id": "t02", "preguntas": Q}, {"id": "t03", "preguntas": Q}]


def correr(cuerpo: str):
    """cuerpo: JS que usa P (el módulo) y TEMAS, y termina con `return <valor>`."""
    prog = (f"const P = require({json.dumps(str(PROGRESO))});\n"
            f"const TEMAS = {json.dumps(TEMAS)}, CQ = {json.dumps(CON_PREGUNTAS)};\n"
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
    assert r["a"] == {"v": 3, "cur": "t01", "dias": {}, "repaso": {}}
    assert r["b"]["dias"] == {"2026-11-11": ["t01"]}
    # el cambio de día no borra lo de ayer, y repetir un tema el mismo día no lo duplica
    assert r["c"]["dias"] == {"2026-11-11": ["t01"], "2026-11-12": ["t02"]}


def test_migra_v1_sin_perder_cur_ni_lo_visto_ese_dia():
    viejo = json.dumps({"dia": "2026-11-12", "vistos": [0, 2, 2, 9], "cur": 1})
    r = correr(f"return P.cargar({json.dumps(viejo)}, TEMAS);")
    assert r == {"v": 3, "cur": "t02", "dias": {"2026-11-12": ["t01", "t03"]}, "repaso": {}}   # el índice 9 no existe


def test_migra_v2_a_v3_sin_perder_nada():
    v2 = {"v": 2, "cur": "t03", "dias": {"2026-11-10": ["t01", "viejo"], "2026-11-12": ["t02", "t03"]}}
    r = correr(f"""
      const e = P.cargar({json.dumps(json.dumps(v2))}, TEMAS);
      return {{ e, otraVez: P.cargar(JSON.stringify(e), TEMAS) }};
    """)
    assert r["e"] == {**v2, "v": 3, "repaso": {}}
    assert r["otraVez"] == r["e"]            # guardar y volver a cargar v3 no cambia nada


def test_cargar_descarta_lo_que_no_entiende():
    r = correr("""
      return [
        P.cargar("{roto", TEMAS),
        P.cargar(JSON.stringify({ v: 2, cur: "t99", dias: { "ayer": ["t01"], "2026-11-10": ["t01", 3, "t01", "viejo"] } }), TEMAS),
        P.cargar(null, []),
      ];
    """)
    assert r[0] == {"v": 3, "cur": "t01", "dias": {}, "repaso": {}}
    # cur desconocido vuelve al primero; los ids que ya no están en la lista se conservan como historia
    assert r[1] == {"v": 3, "cur": "t01", "dias": {"2026-11-10": ["t01", "viejo"]}, "repaso": {}}
    assert r[2] == {"v": 3, "cur": None, "dias": {}, "repaso": {}}


def test_cargar_descarta_el_repaso_que_no_entiende():
    bueno = {"nivel": 1, "proxima": "2026-11-15", "historial": [{"fecha": "2026-11-12", "aciertos": 3, "total": 3}]}
    guardado = {"v": 3, "cur": "t01", "dias": {}, "repaso": {
        "t01": bueno, "viejo": bueno,                                   # un tema que ya no está: es historia
        "t02": {"nivel": 3, "proxima": "2026-11-15", "historial": []},  # nivel fuera de rango
        "t03": {"nivel": 0, "proxima": "mañana", "historial": []},
        "t04": {"nivel": 0, "proxima": "2026-11-13",
                "historial": [{"fecha": "2026-11-12", "aciertos": 4, "total": 3}, "x",
                              {"fecha": "2026-11-12", "aciertos": 0, "total": 2, "extra": 1}]},
    }}
    r = correr(f"return [P.cargar({json.dumps(json.dumps(guardado))}, TEMAS), "
               f"P.cargar(JSON.stringify({{ v: 3, dias: {{}}, repaso: [1] }}), TEMAS).repaso];")
    assert r[0]["repaso"] == {"t01": bueno, "viejo": bueno, "t04": {
        "nivel": 0, "proxima": "2026-11-13", "historial": [{"fecha": "2026-11-12", "aciertos": 0, "total": 2}]}}
    assert r[1] == {}


def test_que_toca_hoy_sin_preguntas():
    r = correr("""
      const e = P.cargar(null, TEMAS);
      const uno = P.marcarVisto(e, "t01", "2026-11-10");
      const todos = P.marcarVisto(P.marcarVisto(uno, "t02", "2026-11-11"), "t03", "2026-11-11");
      const futuro = P.marcarVisto(e, "t01", "2026-12-01");
      return [P.queTocaHoy(e, TEMAS, "2026-11-12"), P.queTocaHoy(uno, TEMAS, "2026-11-12"),
              P.queTocaHoy(todos, TEMAS, "2026-11-12"), P.queTocaHoy(futuro, TEMAS, "2026-11-12"),
              P.queTocaHoy(e, [], "2026-11-12"), P.queTocaHoy(todos, ["t01", "t02", "t03"], "2026-11-12")];
    """)
    # nada visto -> el primero; uno visto -> el primero nunca visto; todos vistos -> nada pendiente (null);
    # un día futuro no cuenta; sin temas, null; los temas pueden venir como ids sueltos
    assert r == ["t01", "t02", None, "t01", None, None]


def test_responder_no_toca_el_estado_ni_marca_visto():
    r = correr("""
      const a = P.cargar(null, CQ);
      const b = P.responder(a, "t02", 2, 3, "2026-11-12");
      const malos = [[-1, 3], [4, 3], [1, 0], [1.5, 3], ["2", 3]].map(([x, n]) => {
        try { P.responder(a, "t02", x, n, "2026-11-12"); return "aceptó"; } catch (e) { return e.name; } });
      let fecha; try { P.responder(a, "t02", 1, 1, "12/11/2026"); } catch (e) { fecha = e.name; }
      return { a, b, malos, fecha };
    """)
    assert r["a"]["repaso"] == {}
    assert r["b"]["repaso"] == {"t02": {"nivel": 0, "proxima": "2026-11-13",
                                        "historial": [{"fecha": "2026-11-12", "aciertos": 2, "total": 3}]}}
    assert r["b"]["dias"] == {}                   # visto lo marca marcarVisto, no responder
    assert r["malos"] == ["RangeError"] * 5 and r["fecha"] == "TypeError"


def test_leitner_fallo_acierto_acierto_fallo():
    r = correr("""
      let e = P.cargar(null, CQ); const pasos = [];
      for (const [fecha, a] of [["2026-11-12", 1], ["2026-11-13", 3], ["2026-11-16", 3], ["2026-11-23", 2],
                                ["2026-11-24", 3], ["2026-11-27", 3], ["2026-12-04", 3]]) {
        e = P.responder(e, "t01", a, 3, fecha);
        pasos.push([e.repaso.t01.nivel, e.repaso.t01.proxima]);
      }
      return { pasos, historial: e.repaso.t01.historial.length };
    """)
    assert r["pasos"] == [
        [0, "2026-11-13"],   # falló: nivel 0, vuelve mañana
        [1, "2026-11-16"],   # todo bien: nivel 1, a los 3 días
        [2, "2026-11-23"],   # todo bien: nivel 2, a los 7 días
        [0, "2026-11-24"],   # falló: vuelve a 0, mañana
        [1, "2026-11-27"],
        [2, "2026-12-04"],
        [2, "2026-12-11"],   # el nivel máximo es 2: sigue a los 7 días
    ]
    assert r["historial"] == 7


def test_leitner_cruza_meses_y_anios():
    r = correr("""
      const e = P.cargar(null, CQ);
      return [P.responder(e, "t01", 3, 3, "2026-12-30").repaso.t01.proxima,
              P.responder(P.responder(e, "t01", 3, 3, "2027-02-20"), "t01", 3, 3, "2027-02-23").repaso.t01.proxima,
              P.diasEntre("2026-12-30", "2027-01-02"), P.diasEntre("2026-11-13", "2026-11-12")];
    """)
    assert r == ["2027-01-02", "2027-03-02", 3, -1]


def test_que_toca_hoy_con_repasos_vencidos_y_nuevos():
    r = correr("""
      const temas = CQ.concat([{ id: "t04", preguntas: [] }, { id: "t05", preguntas: CQ[0].preguntas }]);
      let e = P.cargar(null, temas);
      // t01: falló el 10 (vencía el 11); t03: acertó todo el 9 (vence el 12, hoy); t02: acertó el 11 (vence el 14)
      for (const [id, a, f] of [["t01", 1, "2026-11-10"], ["t03", 3, "2026-11-09"], ["t02", 3, "2026-11-11"]]) {
        e = P.marcarVisto(e, id, f); e = P.responder(e, id, a, 3, f);
      }
      e = P.marcarVisto(e, "t04", "2026-11-11");            // sin preguntas: visto, queda al día
      const hoy = "2026-11-12";
      const salteado = P.marcarVisto(e, "t05", hoy);       // salteó las preguntas: visto, sin repaso
      return {
        pend: P.pendientesHoy(e, temas, hoy), toca: P.queTocaHoy(e, temas, hoy),
        salteado: P.pendientesHoy(salteado, temas, hoy),
        despues: P.pendientesHoy(salteado, temas, "2026-11-14"),
        nada: P.queTocaHoy(P.responder(P.responder(salteado, "t01", 3, 3, hoy), "t03", 3, 3, hoy), temas, hoy),
        estados: temas.map(t => P.estadoTema(salteado, t, hoy)),
        sinPreguntas: P.pendientesHoy(e, TEMAS.concat([{ id: "t04" }, { id: "t05" }]), hoy),
      };
    """)
    # vencidos primero, el más atrasado antes (t01 vencía el 11, t03 hoy); después los nunca vistos, en orden
    assert r["pend"] == ["t01", "t03", "t05"] and r["toca"] == "t01"
    assert r["salteado"] == ["t01", "t03"]
    assert r["despues"] == ["t01", "t03", "t02"]          # el 14 también vence t02; a igual atraso, el de la lista
    assert r["nada"] is None
    assert r["estados"] == [{"estado": "pendiente", "proxima": "2026-11-11"}, {"estado": "aldia", "proxima": "2026-11-14"},
                            {"estado": "pendiente", "proxima": "2026-11-12"}, {"estado": "aldia"}, {"estado": "aldia"}]
    # si la lista ya no trae preguntas (p. ej. se rehicieron sin validar), el repaso guardado no se usa: visto o no visto
    assert r["sinPreguntas"] == ["t05"]


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
      const r = P.responder(e, "t02", 1, 2, "2026-11-12");
      const y = P.exportar(r, { fecha: "2026-11-12" });
      y.repaso.t02.historial[0].aciertos = 9;            // también una copia
      return { x, e, r, y, sinDatos: Object.keys(P.exportar(e)).sort() };
    """)
    assert list(r["x"]["dias"]) == ["2026-11-11", "2026-11-12"]          # en orden de fecha
    assert r["x"] == {"titulo": "Redes", "generado": "2026-11-12T10:00:00.000Z",
                      "dias": {"2026-11-11": ["t01"], "2026-11-12": ["t02", "t09"]}, "racha": 2, "repaso": {}}
    assert r["e"]["dias"]["2026-11-12"] == ["t02"]
    assert r["sinDatos"] == ["dias", "generado", "racha", "repaso", "titulo"]
    assert r["y"]["repaso"]["t02"]["nivel"] == 0 and r["y"]["repaso"]["t02"]["proxima"] == "2026-11-13"
    assert r["r"]["repaso"]["t02"]["historial"] == [{"fecha": "2026-11-12", "aciertos": 1, "total": 2}]


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
    assert {"cargar", "marcarVisto", "responder", "queTocaHoy", "pendientesHoy", "estadoTema", "racha",
            "exportar"} <= set(claves)
    assert fecha == "2026-01-05"
