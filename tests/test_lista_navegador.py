"""La lista de reproducción completa (index.html de reproductor.indice) en Chromium, con Playwright.

Los videos son páginas de juguete que hablan con la lista igual que los reales (postMessage "listo",
"inicio", "pausa", "fin"), así no hace falta gsap, Piper ni audio. El reloj se fija en 2026-11-12.
Si Playwright o Chromium no están instalados, se saltea; con S2S_EXIGIR_NAVEGADOR=1 (el job "web" del CI)
falla en vez de saltearse."""
import json
import os
from datetime import datetime

import pytest

import reproductor

EXIGIR = os.environ.get("S2S_EXIGIR_NAVEGADOR") == "1"
if EXIGIR:
    import playwright.sync_api as pw
else:
    pw = pytest.importorskip("playwright.sync_api")

HOY = datetime(2026, 11, 12, 12, 0)
VIDEO_FALSO = """<!doctype html><html><body style="margin:0;height:100vh;background:#123"><script>
window.recibidos = []; window.clics = 0;
addEventListener("message", e => {
  recibidos.push(e.data);
  if (e.data && e.data.s2s === "play") parent.postMessage({ s2s: { tipo: "inicio" } }, "*");
  if (e.data && e.data.s2s === "pausa") parent.postMessage({ s2s: { tipo: "pausa" } }, "*");
});
document.addEventListener("click", () => { clics++; });
parent.postMessage({ s2s: { tipo: "listo" } }, "*");
</script></body></html>"""


@pytest.fixture(scope="module")
def navegador():
    try:
        with pw.sync_playwright() as p:
            nav = p.chromium.launch()
            yield nav
            nav.close()
    except Exception as e:                     # Chromium no instalado (`playwright install chromium`)
        if EXIGIR:
            raise
        pytest.skip(f"Chromium no disponible: {e}")


@pytest.fixture
def lista(tmp_path):
    for i in (1, 2, 3):
        (tmp_path / f"t0{i}.html").write_text(VIDEO_FALSO, encoding="utf-8")
    videos = [{"id": f"t0{i}", "archivo": f"t0{i}.html", "titulo": f"Tema {i}", "pregunta": "", "duracion": 40}
              for i in (1, 2, 3)]
    return reproductor.indice(tmp_path / "index.html", "Piloto", videos).as_uri()


def abrir(navegador, url, estado=None, tactil=False, init=""):
    ctx = navegador.new_context(has_touch=tactil, is_mobile=tactil, viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.clock.set_fixed_time(HOY)
    if init:
        page.add_init_script(init)
    page.goto(url)
    if estado is not None:
        page.evaluate("e => localStorage.setItem('s2s:' + document.title, JSON.stringify(e))", estado)
        page.reload()
    return page


def video(page, archivo):
    page.wait_for_function(f"document.getElementById('v').src.endsWith('{archivo}')")
    f = page.query_selector("#v").content_frame()
    f.wait_for_load_state()
    f.wait_for_function("window.recibidos !== undefined")
    return f


def texto(page, sel):
    return page.text_content(sel).strip()


def test_migra_el_formato_viejo_y_abre_lo_que_toca_hoy(navegador, lista):
    page = abrir(navegador, lista, {"dia": "2026-11-12", "vistos": [0], "cur": 0})
    video(page, "t02.html")                                          # se abre lo que toca, no cur
    assert texto(page, "#lToca") == "Hoy toca" and texto(page, "#tToca") == "Tema 2"
    assert texto(page, "#nRacha") == "1" and texto(page, "#lRacha") == "día seguido"
    assert texto(page, "#nVistos") == "1 / 3"
    guardado = json.loads(page.evaluate("localStorage.getItem('s2s:' + document.title)"))
    assert guardado == {"v": 3, "cur": "t02", "dias": {"2026-11-12": ["t01"]}, "repaso": {}}


def test_al_terminar_marca_el_dia_y_pasa_al_siguiente(navegador, lista):
    estado = {"v": 2, "cur": "t01", "dias": {"2026-11-09": ["t01"], "2026-11-10": ["t01"], "2026-11-11": ["t02"]}}
    page = abrir(navegador, lista, estado)
    f = video(page, "t03.html")                                      # t03 nunca se vio
    assert texto(page, "#nRacha") == "3" and texto(page, "#lRacha") == "días seguidos"
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin' } }, '*')")
    page.wait_for_function("document.getElementById('nVistos').textContent === '3 / 3'")
    assert texto(page, "#nRacha") == "4"
    # todos vistos y sin preguntas: no queda nada para hoy, pero cualquier video se puede ver igual
    assert texto(page, "#tToca") == "Nada pendiente hoy" and page.is_disabled("#toca")
    assert texto(page, "#nHoy") == "0" and texto(page, "#lHoy") == "para hoy"
    page.click("#lista li:nth-child(1) button")
    video(page, "t01.html")
    guardado = json.loads(page.evaluate("localStorage.getItem('s2s:' + document.title)"))
    assert guardado["dias"]["2026-11-12"] == ["t03"]


def test_borrar_progreso_con_confirmacion(navegador, lista):
    page = abrir(navegador, lista, {"v": 2, "cur": "t02", "dias": {"2026-11-12": ["t01"]}})
    video(page, "t02.html")
    page.click("#cero")
    page.click("#conf button.prim")
    page.wait_for_function("document.getElementById('nVistos').textContent === '0 / 3'")
    assert texto(page, "#nRacha") == "0" and texto(page, "#tToca") == "Tema 1"


def test_deslizar_cambia_de_video_y_el_toque_llega_al_video(navegador, lista):
    page = abrir(navegador, lista, tactil=True)
    f = video(page, "t01.html")
    caja = page.query_selector(".caja").bounding_box()
    cx, cy = caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2
    # con la tapa del video a la vista la capa no está: el toque llega al video ("Tocar para ver")
    assert page.evaluate("getComputedStyle(document.getElementById('capa')).display") == "none"
    page.touchscreen.tap(cx, cy)
    f.wait_for_function("window.clics === 1")
    # mientras suena, la capa toma los gestos
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio' } }, '*')")
    page.wait_for_function("document.getElementById('capa').classList.contains('activa')")
    deslizar = """([x, y, dy]) => {
      const c = document.getElementById('capa'), o = { pointerId: 1, pointerType: 'touch', bubbles: true };
      c.dispatchEvent(new PointerEvent('pointerdown', { ...o, clientX: x, clientY: y }));
      c.dispatchEvent(new PointerEvent('pointerup', { ...o, clientX: x + 5, clientY: y + dy }));
    }"""
    page.evaluate(deslizar, [cx, cy, 0])                              # tocar = pausa
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'pausa')")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'sigue' } }, '*')")
    page.wait_for_function("document.getElementById('capa').classList.contains('activa')")
    page.evaluate(deslizar, [cx, cy, -200])                           # hacia arriba = siguiente
    f2 = video(page, "t02.html")
    f2.wait_for_function("window.recibidos.some(m => m && m.s2s === 'play')")
    f2.evaluate("parent.postMessage({ s2s: { tipo: 'inicio' } }, '*')")
    page.wait_for_function("document.getElementById('capa').classList.contains('activa')")
    page.evaluate(deslizar, [cx, cy, 200])                            # hacia abajo = anterior
    video(page, "t01.html")


def test_en_escritorio_no_hay_capa(navegador, lista):
    page = abrir(navegador, lista)
    f = video(page, "t01.html")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio' } }, '*')")
    page.wait_for_timeout(100)
    assert not page.evaluate("document.getElementById('capa').classList.contains('activa')")


def test_exportar_copia_al_portapapeles(navegador, lista):
    finge = "Object.defineProperty(navigator, 'clipboard', { value: { writeText: async t => { window.copiado = t; } } });"
    page = abrir(navegador, lista, {"v": 2, "cur": "t01", "dias": {"2026-11-12": ["t01"], "2026-11-11": ["t02"]}}, init=finge)
    video(page, "t03.html")
    page.click("#exp")
    page.wait_for_function("window.copiado !== undefined")
    x = json.loads(page.evaluate("window.copiado"))
    assert x["titulo"] == "Piloto" and x["racha"] == 2 and x["generado"].startswith("2026-11-12")
    assert x["dias"] == {"2026-11-11": ["t02"], "2026-11-12": ["t01"]}
    assert texto(page, "#aviso") == "Copiado al portapapeles"
    assert page.query_selector("#expTxt") is None


def test_exportar_sin_portapapeles_muestra_el_json(navegador, lista):
    sin = "Object.defineProperty(navigator, 'clipboard', { value: undefined });"
    page = abrir(navegador, lista, {"v": 2, "cur": "t01", "dias": {"2026-11-12": ["t01"]}}, init=sin)
    video(page, "t02.html")
    page.click("#exp")
    page.wait_for_selector("#expTxt")
    x = json.loads(page.input_value("#expTxt"))
    assert x["dias"] == {"2026-11-12": ["t01"]} and x["racha"] == 1
    assert page.evaluate("document.activeElement.id") == "expTxt"
    assert page.evaluate("(t => t.selectionEnd - t.selectionStart)(document.getElementById('expTxt'))") == len(
        page.input_value("#expTxt"))


# --- preguntas después del video y repaso ----------------------------------------------------------

PREGUNTAS = [
    {"id": "q1", "texto": "¿A qué tabla apunta la FK de multa?", "opciones": ["A socio", "A prestamo", "A ejemplar"],
     "correcta": 1, "explicacion": "Apunta a prestamo con id_prestamo.", "general": False},
    {"id": "q2", "texto": "¿Cómo se ubica una FK?", "opciones": ["Por el nombre", "Por la dependencia", "Al azar"],
     "correcta": 1, "explicacion": "Método general, no está en tu material: por la dependencia.", "general": True},
]


def lista_con_preguntas(tmp_path, idioma="es"):
    """t01 y t03 tienen preguntas; t02 no."""
    for i in (1, 2, 3):
        (tmp_path / f"t0{i}.html").write_text(VIDEO_FALSO, encoding="utf-8")
    videos = [{"id": f"t0{i}", "archivo": f"t0{i}.html", "titulo": f"Tema {i}", "pregunta": "", "duracion": 40,
               "preguntas": PREGUNTAS if i != 2 else []} for i in (1, 2, 3)]
    return reproductor.indice(tmp_path / "index.html", "Piloto", videos, idioma).as_uri()


def terminar(page, archivo):
    video(page, archivo).evaluate("parent.postMessage({ s2s: { tipo: 'fin' } }, '*')")
    page.wait_for_selector(".caja .s2s-quiz")


def guardado(page):
    return json.loads(page.evaluate("localStorage.getItem('s2s:' + document.title)"))


def test_preguntas_una_bien_una_mal_y_el_tema_vuelve_manana(navegador, tmp_path):
    page = abrir(navegador, lista_con_preguntas(tmp_path))
    assert texto(page, "#nHoy") == "3" and texto(page, "#lHoy") == "para hoy"
    assert page.eval_on_selector_all("#lista .s2s-rep", "es => es.map(e => e.textContent)") == ["Nuevo"] * 3
    terminar(page, "t01.html")
    assert texto(page, ".s2s-quiz .q-num") == "Pregunta 1 de 2"
    assert texto(page, ".s2s-quiz h2") == "¿A qué tabla apunta la FK de multa?"
    assert page.query_selector(".s2s-quiz .q-gen") is None             # q1 no viene de un método general
    assert page.evaluate("document.activeElement.tagName") == "H2"     # el foco va a la pregunta
    assert guardado(page)["dias"] == {"2026-11-12": ["t01"]}           # ya quedó visto

    page.click(".s2s-quiz .q-op >> text=A prestamo")                   # bien
    assert page.eval_on_selector_all(".s2s-quiz .q-op", "bs => bs.map(b => b.className)") == ["q-op", "q-op bien", "q-op"]
    assert texto(page, ".s2s-quiz .q-exp") == "¡Bien!Apunta a prestamo con id_prestamo."
    assert page.is_disabled(".s2s-quiz .q-op >> nth=0")
    page.click(".s2s-quiz .q-sig")

    assert texto(page, ".s2s-quiz .q-num") == "Pregunta 2 de 2"
    assert texto(page, ".s2s-quiz .q-gen") == "método general · no está en tu material"
    page.click(".s2s-quiz .q-op >> text=Al azar")                      # mal
    clases = page.eval_on_selector_all(".s2s-quiz .q-op", "bs => bs.map(b => b.className)")
    assert clases == ["q-op", "q-op bien", "q-op mal"]                 # la correcta en verde, la elegida en rojo
    assert texto(page, ".s2s-quiz .q-exp b") == "No era esa."
    assert "por la dependencia" in texto(page, ".s2s-quiz .q-exp")
    assert texto(page, ".s2s-quiz .q-sig") == "Ver resultado"
    page.click(".s2s-quiz .q-sig")

    assert texto(page, ".s2s-quiz .q-res") == "1 de 2 correctas"
    assert texto(page, ".s2s-quiz .q-vuelve") == "Este tema vuelve mañana."
    assert texto(page, ".s2s-quiz .q-seguir") == "Seguir: Tema 2"
    assert guardado(page)["repaso"] == {"t01": {"nivel": 0, "proxima": "2026-11-13",
                                                "historial": [{"fecha": "2026-11-12", "aciertos": 1, "total": 2}]}}

    page.reload()
    video(page, "t02.html")                                            # abre lo que toca hoy: t02, nuevo
    assert page.query_selector(".s2s-quiz") is None
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Al día · vuelve mañana"
    assert page.get_attribute("#lista li:nth-child(1)", "data-rep") == "aldia"
    assert texto(page, "#nHoy") == "2" and texto(page, "#tToca") == "Tema 2"

    # mañana le toca a t01 antes que a los nuevos
    page.clock.set_fixed_time(datetime(2026, 11, 13, 9, 0))
    page.reload()
    video(page, "t01.html")
    assert texto(page, "#tToca") == "Tema 1" and texto(page, "#nHoy") == "3"
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Pendiente hoy"


def test_seguir_lleva_a_lo_que_toca_hoy(navegador, tmp_path):
    page = abrir(navegador, lista_con_preguntas(tmp_path))
    terminar(page, "t01.html")
    for _ in PREGUNTAS:
        page.click(".s2s-quiz .q-op >> nth=1")
        page.click(".s2s-quiz .q-sig")
    assert texto(page, ".s2s-quiz .q-vuelve") == "Este tema vuelve en 3 días."
    page.click(".s2s-quiz .q-seguir")
    f = video(page, "t02.html")
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'play')")
    assert page.query_selector(".s2s-quiz") is None
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Al día · vuelve en 3 días"


def test_saltear_preguntas_no_cuenta_y_el_tema_queda_visto(navegador, tmp_path):
    page = abrir(navegador, lista_con_preguntas(tmp_path))
    terminar(page, "t01.html")
    page.click(".s2s-quiz >> text=Saltear preguntas")
    video(page, "t02.html")                                            # sigue con lo que toca hoy
    assert page.query_selector(".s2s-quiz") is None
    g = guardado(page)
    assert g["repaso"] == {} and g["dias"] == {"2026-11-12": ["t01"]}
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Al día"
    assert texto(page, "#nHoy") == "2"


def test_preguntas_con_teclado_y_en_ingles(navegador, tmp_path):
    page = abrir(navegador, lista_con_preguntas(tmp_path, "en"))
    assert texto(page, "#lHoy") == "due today"
    terminar(page, "t01.html")
    assert texto(page, ".s2s-quiz .q-num") == "Question 1 of 2"
    assert texto(page, ".s2s-quiz .q-pie button") == "Skip questions"
    page.keyboard.press("Tab")                                         # de la pregunta a la primera opción
    assert page.evaluate("document.activeElement.textContent") == "A socio"
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")                                       # elige "A prestamo"
    assert texto(page, ".s2s-quiz .q-exp b") == "Right!"
    assert page.evaluate("document.activeElement.className") == "prim q-sig"
    page.keyboard.press("Enter")                                       # Next
    assert texto(page, ".s2s-quiz .q-gen") == "general method · not in your material"
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")                                       # "Por el nombre": mal
    assert texto(page, ".s2s-quiz .q-exp b") == "Not that one."
    page.keyboard.press("Enter")                                       # See result
    assert texto(page, ".s2s-quiz .q-res") == "1 of 2 correct"
    assert texto(page, ".s2s-quiz .q-vuelve") == "This topic comes back tomorrow."
    assert page.evaluate("document.activeElement.className") == "q-res"
    page.keyboard.press("Tab")
    assert texto(page, ".s2s-quiz .q-seguir") == "Next up: Tema 2"
    page.keyboard.press("Enter")
    video(page, "t02.html")
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Up to date · back tomorrow"


def test_cambiar_de_video_cierra_las_preguntas(navegador, tmp_path):
    page = abrir(navegador, lista_con_preguntas(tmp_path))
    terminar(page, "t01.html")
    page.click("#lista li:nth-child(3) button")
    video(page, "t03.html")
    assert page.query_selector(".s2s-quiz") is None and guardado(page)["repaso"] == {}
