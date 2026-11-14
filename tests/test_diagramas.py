"""Diagramas en SVG: secuencia (mensajes entre partes) y árbol (jerarquías y cadenas, con la acción ruta).

La validación y el layout se prueban con compile.py; el dibujo y la animación, con el video de prueba
(tests/fixtures/guion_diagramas.json) en Chromium con Playwright. Sin Playwright o sin gsap esos se saltean;
con S2S_EXIGIR_NAVEGADOR=1 fallan."""
import copy
import json
import os
import re
import subprocess
import sys

import pytest
from compile import ANCHO_MAX, ARBOL_GAP_X, DIAG_ANCHO, FS_MIN, Reporte, compilar, layout_arbol, validar_arbol
from config import CFG
from conftest import SKILL
from datos import EJEMPLO
from etapas import escribir_salidas
from voz_falsa import generar

LEX = json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8"))
FIXTURE = SKILL.parents[1] / "tests" / "fixtures" / "guion_diagramas.json"
EXIGIR = os.environ.get("S2S_EXIGIR_NAVEGADOR") == "1"

SEC = {"type": "secuencia", "id": "s", "partes": ["cliente", "servidor"],
       "mensajes": [["cliente", "servidor", "SYN"], [1, 0, "SYN-ACK"], [0, 1, "ACK"]]}
ARBOL = {"type": "arbol", "id": "t", "nodos": [{"id": "raiz", "text": "raíz"}, {"id": "a", "text": "a", "padre": "raiz"},
                                             {"id": "b", "text": "b", "padre": "raiz"}]}


def compilar_con(elemento, frase):
    """El ejemplo de la biblioteca con un elemento más en el bloque 0 y una frase que lo anima."""
    g = copy.deepcopy(EJEMPLO)
    g["bloques"][0]["elementos"].append(elemento)
    g["bloques"][0]["frases"][0] = frase + " " + g["bloques"][0]["frases"][0]
    spec, rep = compilar(g, LEX, SKILL / "scripts" / "iconos")
    return spec, rep


def errores(elemento, frase="{show s}Mirá."):
    return " | ".join(compilar_con(elemento, frase)[1].errores)


def avisos(elemento, frase):
    return " | ".join(compilar_con(elemento, frase)[1].avisos)


def con(base, **cambios):
    e = copy.deepcopy(base); e.update(cambios); return e


# --- secuencia: validación ---------------------------------------------------------------------

@pytest.mark.parametrize("elemento, esperado", [
    (con(SEC, partes=["solo"]), "entre 2 y 4 partes"),
    (con(SEC, partes=["a", "b", "c", "d", "e"]), "entre 2 y 4 partes"),
    (con(SEC, mensajes=[]), "entre 1 y 7 mensajes"),
    (con(SEC, mensajes=[[0, 1, "x"]] * 8), "entre 1 y 7 mensajes"),
    (con(SEC, partes=["cliente", "un servidor lejano"]), "pasa de 14 caracteres"),
    (con(SEC, mensajes=[["cliente", "proxy", "x"]]), "a='proxy' no es una parte"),
    (con(SEC, mensajes=[[0, 2, "x"]]), "a=2 no es una parte"),
    (con(SEC, mensajes=[[0, 1, "un texto de más de veinte"]]), "pasa de 20 caracteres"),
    (con(SEC, mensajes=[[0, 1, "x", {"kind": "blue"}]]), "kind «blue» no existe"),
    (con(SEC, mensajes=[[0, 0, "x", {"perdido": True}]]), "no puede perderse"),
    (con(SEC, mensajes=[[0, 1]]), "tiene que ser [de, a, texto]"),
    (con(SEC, partes=["cliente", "cliente"]), "mismo nombre"),
    (con(SEC, partes=["resolvedor", "raíz", "autoritativo", "caché local"],
         mensajes=[[0, 1, "consulta"]]), "no entra en su columna"),
    (con(SEC, partes=["a", "b", "c", "d"], mensajes=[[0, 1, "consulta firmada"]]), "no entra en su columna"),
])
def test_secuencia_se_valida(elemento, esperado):
    assert esperado in errores(elemento)


def test_secuencia_ids_repetidos():
    g = copy.deepcopy(EJEMPLO)
    g["bloques"][0]["elementos"] += [copy.deepcopy(SEC), {"type": "chip", "id": "s-m1", "text": "x"}]
    g["bloques"][0]["frases"][0] = "{show s}Mirá " + g["bloques"][0]["frases"][0]
    assert "id repetido o reservado «s-m1»" in " | ".join(compilar(g, LEX)[1].errores)


def test_secuencia_compila_con_ids_implicitos_y_layout():
    spec, rep = compilar_con(con(SEC, partes=[{"nombre": "cliente", "icon": "users"}, "servidor"]),
                             "{show s}Primero {show s-m0}uno, {show s-m1}dos y {show s-m2}tres, {hl s-p1}servidor {strike s-m2}tachado.")
    assert rep.errores == [] and not [a for a in rep.avisos if "s-m" in a]
    sec = next(e for e in spec["STATIONS"][0] if e["type"] == "secuencia")
    assert sec["mensajes"][1] == {"de": 1, "a": 0, "texto": "SYN-ACK"}           # nombres e índices -> índices
    assert sec["partes"][0] == {"nombre": "cliente", "icon": "users"} and sec["partes"][1] == {"nombre": "servidor"}
    assert sec["col"] == DIAG_ANCHO / 2 and FS_MIN <= sec["fs"] <= 40 and sec["fila"] > sec["fs"]
    assert DIAG_ANCHO <= ANCHO_MAX
    assert ["0:uno", "show", "s-m0"] in spec["EVENTS"] and ["0:servidor", "hl", "s-p1"] in spec["EVENTS"]


def test_secuencia_los_textos_largos_bajan_la_letra_y_entran():
    e = con(SEC, partes=["resolver", "raíz", "zona"], mensajes=[[0, 1, "consulta del DS"], [0, 2, "DNSKEY"]])
    spec, rep = compilar_con(e, "{show s}Mirá {show s-m0}uno y {show s-m1}dos.")
    sec = next(x for x in spec["STATIONS"][0] if x["type"] == "secuencia")
    assert rep.errores == [] and FS_MIN <= sec["fs"] < 40
    # el texto más ajustado (de una columna) entra entre sus dos líneas de vida
    assert len("consulta del DS") * sec["fs"] * 0.6 <= sec["col"] - 28


def test_secuencia_avisa_si_un_mensaje_sale_antes_que_el_anterior():
    a = avisos(SEC, "{show s}Mirá {show s-m1}dos, {show s-m0}uno y {show s-m2}tres.")
    assert "s-m1 se muestra antes que s-m0: los mensajes se leen en orden" in a
    assert "s-m2 se muestra antes" not in a


def test_secuencia_avisa_si_un_mensaje_nunca_aparece():
    a = avisos(SEC, "{show s}Mirá {show s-m0}uno y {show s-m1}dos.")
    assert "el mensaje s-m2 nunca se muestra" in a


def test_secuencia_strike_y_send():
    assert errores(SEC, "{show s}Mirá {strike s-p0}esto {strike s-m0}acá.") == ""
    assert "solo flujos" in errores(SEC, "{show s}Mirá {send s}esto.")


# --- árbol: validación y layout ----------------------------------------------------------------

def nodos(*pares):
    """nodos("rz", ("a", "rz"), …): la raíz y después (id, padre)."""
    out = [{"id": pares[0], "text": pares[0]}]
    out += [{"id": i, "text": i, "padre": p} for i, p in pares[1:]]
    return out


@pytest.mark.parametrize("ns, esperado", [
    (nodos("rz"), "entre 2 y 10 nodos"),
    (nodos("rz", *[(f"n{i}", "rz") for i in range(10)]), "entre 2 y 10 nodos"),
    ([{"id": "rz", "text": "rz"}, {"id": "a", "text": "a"}], "exactamente una raíz"),
    ([{"id": "a", "text": "a", "padre": "b"}, {"id": "b", "text": "b", "padre": "a"}], "exactamente una raíz"),
    (nodos("rz", ("a", "nadie")), "el padre «nadie» del nodo «a» no es un nodo"),
    (nodos("rz", ("a", "b"), ("b", "a")), "ciclo"),
    (nodos("rz", ("a", "rz"), ("b", "a"), ("c", "b"), ("d", "c")), "nivel 5"),
    (nodos("rz", *[(f"n{i}", "rz") for i in range(5)]), "tiene 5 hijos (máximo 4)"),
    ([{"id": "rz", "text": "una raíz con nombre largo"}, {"id": "a", "text": "a", "padre": "rz"}], "pasa de 18"),
    ([{"id": "rz", "text": "rz", "kind": "rosa"}, {"id": "a", "text": "a", "padre": "rz"}], "kind «rosa» no existe"),
    ([{"id": "rz", "text": "rz"}, {"id": "rz", "text": "otra", "padre": "rz"}], "id repetido"),
    ([{"id": "rz", "text": "rz"}, {"id": "a", "text": "a", "padre": "rz"},
      *[{"id": f"h{i}", "text": f"hoja larga núm {i:02}", "padre": "a"} for i in range(4)],
      *[{"id": f"g{i}", "text": f"hoja larga núm {i + 4:02}", "padre": "rz"} for i in range(3)]],
     "el árbol no entra en 960px"),
])
def test_arbol_se_valida(ns, esperado):
    assert esperado in errores({"type": "arbol", "id": "t", "nodos": ns}, "{show t}Mirá.")


def test_arbol_que_no_entra_sugiere_que_hacer():
    ns = [{"id": "rz", "text": "rz"}] + [{"id": f"h{i}", "text": "dieciocho letras!!", "padre": "rz"} for i in range(4)]
    e = errores({"type": "arbol", "id": "t", "nodos": ns}, "{show t}Mirá.")
    assert f"ni con letra {FS_MIN}px" in e and "usá menos nodos (menos hojas) o textos más cortos" in e


def arbol_10_profundidad_4():
    #            r
    #     a      b      c
    #   d   e    f      g
    #  h         i
    return nodos("rz", ("a", "rz"), ("b", "rz"), ("c", "rz"), ("d", "a"), ("e", "a"), ("f", "b"), ("g", "c"),
                 ("h", "d"), ("i", "f"))


def test_layout_del_arbol_de_10_nodos_y_profundidad_4():
    ns = [{**n, "text": f"nodo {n['id']}"} for n in arbol_10_profundidad_4()]
    rep = Reporte()
    assert validar_arbol(ns, "t", rep) is not None and rep.errores == []
    L = layout_arbol(ns)
    pos, fs, h = L["pos"], L["fs"], L["caja_h"]
    assert FS_MIN <= fs <= 40 and set(pos) == {n["id"] for n in ns}
    # la raíz centrada en el dibujo y sobre sus hijos; cada padre centrado sobre sus hijos
    assert pos["rz"][0] == pytest.approx(DIAG_ANCHO / 2, abs=1)
    for n in ns:
        hijos = [m["id"] for m in ns if m.get("padre") == n["id"]]
        if hijos:
            assert pos[n["id"]][0] == pytest.approx((pos[hijos[0]][0] + pos[hijos[-1]][0]) / 2, abs=0.2)
    # 4 niveles, de arriba hacia abajo
    ys = sorted({p[1] for p in pos.values()})
    assert len(ys) == 4 and L["alto"] >= ys[-1] + h / 2
    # ninguna caja se superpone con otra ni se sale del dibujo
    cajas = [(x - w / 2, y - h / 2, x + w / 2, y + h / 2) for x, y, w in pos.values()]
    for i, a in enumerate(cajas):
        assert a[0] >= 0 and a[2] <= DIAG_ANCHO
        for b in cajas[i + 1:]:
            separadas = a[2] + ARBOL_GAP_X - 0.5 <= b[0] or b[2] + ARBOL_GAP_X - 0.5 <= a[0] or a[3] <= b[1] or b[3] <= a[1]
            assert separadas, (a, b)
    # sin cruces: las hojas quedan en el orden del recorrido
    assert pos["h"][0] < pos["e"][0] < pos["i"][0] < pos["g"][0]


def test_arbol_ids_aristas_y_eventos():
    spec, rep = compilar_con(ARBOL, "{show t}Mirá {show a}a, {show b}b y {ruta t hasta=b kind=good}recorrelo {hl a}y {strike b}tachá.")
    assert rep.errores == []
    assert ["0:recorrelo", "ruta", "t", {"hasta": "b", "kind": "good"}] in spec["EVENTS"]
    assert errores(ARBOL, "{show t}Mirá {show t-e-a}esta arista.") == ""          # id-e-<nodo> existe
    assert "no existe" in errores(ARBOL, "{show t}Mirá {show t-e-raiz}esta.")      # la raíz no tiene arista


@pytest.mark.parametrize("frase, esperado", [
    ("{show t}Mirá {ruta raiz hasta=a}esto.", "ruta sobre «raiz»: solo árboles"),
    ("{show t}Mirá {ruta t hasta=x}esto.", "hasta=x tiene que ser un nodo de «t»"),
    ("{show t}Mirá {ruta t}esto.", "hasta=None tiene que ser un nodo"),
    ("{show t}Mirá {ruta t hasta=a kind=warn}esto.", "puede ser good o bad"),
    ("{show t}Mirá {hl a hasta=b}esto.", "hasta= solo va con ruta"),
])
def test_ruta_se_valida(frase, esperado):
    assert esperado in errores(ARBOL, frase)


def test_arbol_avisa_nodos_fuera_de_orden_y_nodos_que_nunca_aparecen():
    e = {"type": "arbol", "id": "t", "nodos": nodos("rz", ("a", "rz"), ("b", "a"), ("c", "rz"))}
    a = avisos(e, "{show t}Mirá {show b}b y {show a}a.")
    assert "el nodo b aparece antes que su padre a" in a and "el nodo c nunca aparece" in a
    # una ruta hace aparecer los nodos de su camino
    a = avisos(e, "{show t}Mirá {ruta t hasta=b}esto y {show c}c.")
    assert "nunca aparece" not in a and "antes que su padre" not in a


# --- el video de prueba: compila sin errores y se dibuja --------------------------------------

def test_el_guion_de_prueba_compila_sin_errores_ni_avisos_de_diagramas():
    g = json.loads(FIXTURE.read_text(encoding="utf-8"))
    lex = {**LEX, **g["lexico"]}
    spec, rep = compilar(g, lex, SKILL / "scripts" / "iconos")
    assert rep.errores == []
    assert [a for a in rep.avisos if "sin fuentes" not in a] == []
    acciones = {(e[1], e[2]) for e in spec["EVENTS"]}
    assert ("ruta", "ar") in acciones and ("show", "sq-m3") in acciones


@pytest.fixture(scope="module", params=["cuaderno", "pizarra"])
def video_diagramas(request, tmp_path_factory):
    """El .html del video de prueba de los diagramas, con voz falsa, en cada estilo."""
    from pathlib import Path

    import reproductor
    if not Path(CFG["gsap"]).exists():
        if EXIGIR:
            pytest.fail(f"falta {CFG['gsap']}: el job web del CI lo baja antes de los tests")
        pytest.skip("gsap no está instalado (s2s.py instalar)")
    g = json.loads(FIXTURE.read_text(encoding="utf-8"))
    spec, rep = compilar(g, {**LEX, **g["lexico"]})
    assert rep.errores == []
    d = tmp_path_factory.mktemp(request.param) / "t01"
    escribir_salidas(d, spec)
    generar(d)
    subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d), request.param], check=True,
                   capture_output=True, env={**os.environ, "S2S_DATOS": str(d.parent / "datos")})
    estado = json.loads(re.search(r"<script>const S = (\{.*?\});</script>", (d / "index.html").read_text(encoding="utf-8"))[1])
    tema = json.loads((SKILL / "scripts" / "temas" / f"{request.param}.json").read_text(encoding="utf-8"))
    return reproductor.construir(d, d.parent / "t01.html", "Diagramas"), estado["EV"], tema


def test_el_motor_dibuja_los_diagramas_con_los_colores_del_tema(video_diagramas):
    html, _, tema = video_diagramas
    texto = html.read_text(encoding="utf-8")
    assert 'class="card diag secuencia" id="sq"' in texto and 'class="card diag arbol" id="ar"' in texto
    for i in range(3):
        assert f'id="sq-p{i}"' in texto
    for k in range(7):
        assert f'id="sq-m{k}"' in texto
    assert 'id="ar-e-n-www"' in texto and 'id="ar-e-n-raiz"' not in texto
    assert 'class="dcorte"' in texto                                         # el mensaje perdido tiene su X
    for clave in ("dVida", "dParte", "dArista", "dCorte"):
        assert tema["py"][clave] in texto
    assert tema["c"]["ruta"] in texto


@pytest.fixture(scope="module")
def navegador():
    if EXIGIR:
        import playwright.sync_api as pw
    else:
        pw = pytest.importorskip("playwright.sync_api")
    try:
        with pw.sync_playwright() as p:
            nav = p.chromium.launch()
            yield nav
            nav.close()
    except Exception as e:
        if EXIGIR:
            raise
        pytest.skip(f"Chromium de Playwright no disponible: {e}")


@pytest.fixture
def pagina(navegador, video_diagramas):
    html, ev, tema = video_diagramas
    p = navegador.new_page(viewport={"width": 390, "height": 693})
    errores_js = []
    p.on("pageerror", lambda e: errores_js.append(str(e)))
    p.goto(html.as_uri())
    p.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=30000)
    yield p, ev, tema
    assert errores_js == []
    p.close()


def momento(ev, accion, id_):
    return next(e["t"] for e in ev if e["a"] == accion and e["id"] == id_)


ESTADO_MSG = """id => { const m = document.getElementById(id), lin = m.querySelector(".dlin"), lab = m.querySelector(".dlab");
  return { grupo: +getComputedStyle(m).opacity, linea: +getComputedStyle(lin).opacity,
           resto: parseFloat(getComputedStyle(lin).strokeDashoffset), texto: +getComputedStyle(lab).opacity }; }"""


def test_show_de_un_mensaje_dibuja_la_flecha_y_despues_el_texto(pagina):
    p, ev, _ = pagina
    t = momento(ev, "show", "sq-m1")
    p.evaluate("t => __s2s.pintar(t)", t - 0.3)
    antes = p.evaluate(ESTADO_MSG, "sq-m1")
    assert antes["grupo"] == 0 and antes["texto"] == 0
    p.evaluate("t => __s2s.pintar(t)", t + 0.2)                  # la flecha a mitad de camino, sin texto
    medio = p.evaluate(ESTADO_MSG, "sq-m1")
    assert medio["grupo"] == 1 and medio["resto"] > 1 and medio["texto"] == 0
    p.evaluate("t => __s2s.pintar(t)", t + 1.0)
    despues = p.evaluate(ESTADO_MSG, "sq-m1")
    assert despues == {"grupo": 1, "linea": 1, "resto": 0, "texto": 1}
    # el que sigue todavía no está, y el {show sq} del principio mostró las partes pero no los mensajes
    assert p.evaluate(ESTADO_MSG, "sq-m2")["grupo"] == 0
    p.evaluate("t => __s2s.pintar(t)", momento(ev, "show", "sq") + 1.0)
    assert p.evaluate("[0,1,2].map(i => +getComputedStyle(document.getElementById('sq-p' + i)).opacity)") == [1, 1, 1]
    assert p.evaluate(ESTADO_MSG, "sq-m0")["grupo"] == 0


def test_el_mensaje_perdido_se_corta_con_una_x(pagina):
    p, ev, _ = pagina
    p.evaluate("t => __s2s.pintar(t)", momento(ev, "show", "sq-m3") + 1.0)
    r = p.evaluate("""() => { const m = document.getElementById("sq-m3");
      return { x: +getComputedStyle(m.querySelector(".dcorte")).opacity, cabeza: m.querySelector(".dcab") === null }; }""")
    assert r == {"x": 1, "cabeza": True}


RUTA = """() => [...document.querySelectorAll("#ar .dnodo")].map(n => [n.id, n.querySelector(".dfondo").getAttribute("fill")])
  .concat([...document.querySelectorAll("#ar .darista")].map(a => [a.id, +getComputedStyle(a.querySelector(".druta")).opacity]))"""


def test_ruta_resalta_exactamente_el_camino_pedido(pagina):
    p, ev, tema = pagina
    t = momento(ev, "ruta", "ar")
    p.evaluate("t => __s2s.pintar(t)", t - 0.05)
    antes = dict(p.evaluate(RUTA))
    p.evaluate("t => __s2s.pintar(t)", t + 1.5)
    despues = dict(p.evaluate(RUTA))
    verde = tema["c"]["good"]                                    # {ruta ar hasta=n-www kind=good}
    camino = ["n-raiz", "n-com", "n-ej", "n-www"]
    for nodo, color in despues.items():
        if nodo.startswith("ar-e-"):
            assert color == (1 if nodo[5:] in camino else 0), nodo
        elif nodo in camino:
            assert color.lower() == verde.lower() and antes[nodo].lower() != verde.lower(), nodo
        else:
            assert color == antes[nodo], nodo
    # de a uno: a mitad de la ruta, la raíz ya está y la hoja todavía no
    p.evaluate("t => __s2s.pintar(t)", t + 0.35)
    medio = dict(p.evaluate(RUTA))
    assert medio["n-raiz"].lower() == verde.lower() and medio["n-www"].lower() != verde.lower()


def test_una_ruta_hace_aparecer_los_nodos_que_faltaban(pagina):
    p, ev, _ = pagina
    t = momento(ev, "ruta", "ar2")                               # el 6 no tiene {show}: lo trae la ruta
    opac = "() => +getComputedStyle(document.getElementById('b6')).opacity"
    p.evaluate("t => __s2s.pintar(t)", t - 0.1)
    assert p.evaluate(opac) == 0
    p.evaluate("t => __s2s.pintar(t)", t + 1.2)
    assert p.evaluate(opac) == 1
