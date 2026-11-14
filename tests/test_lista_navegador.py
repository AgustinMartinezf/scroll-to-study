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
parent.postMessage({ s2s: { tipo: "listo", t: 0, duracion: 40, reproducidos: 0 } }, "*");
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


def arrastrar(page, x, y0, y1, pasos=6):
    """Un arrastre de verdad con el dedo (eventos táctiles de Chromium, como en un teléfono)."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]})
    for k in range(1, pasos + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y0 + (y1 - y0) * k / pasos}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()


def centro(page, sel=".caja"):
    c = page.query_selector(sel).bounding_box()
    return c["x"] + c["width"] / 2, c["y"] + c["height"] / 2


def sonar(f):
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, duracion: 40, reproducidos: 0 } }, '*')")


def test_modo_normal_sin_gestos_la_pagina_scrollea_y_los_toques_llegan_al_video(navegador, lista):
    page = abrir(navegador, lista, tactil=True)
    f = video(page, "t01.html")
    assert texto(page, "#feed") == "Pantalla completa"
    sonar(f)
    page.wait_for_timeout(100)
    cx, cy = centro(page)
    page.touchscreen.tap(cx, cy)                                      # el toque llega al video, no a una capa
    f.wait_for_function("window.clics === 1")
    assert page.query_selector(".s2s-capa.activa") is None
    arriba = page.evaluate("scrollY")
    arrastrar(page, cx, cy + 150, cy - 150)                           # deslizar sobre el video hacia arriba
    page.wait_for_timeout(500)
    assert page.evaluate("document.getElementById('v').src").endswith("t01.html")     # no cambió de video
    assert page.evaluate("scrollY") > arriba                          # bajó la página, hacia la lista
    assert f.evaluate("window.recibidos.filter(m => m && m.s2s === 'play').length") == 0


def test_modo_feed_deslizar_cambia_de_video_y_la_x_vuelve_a_la_lista(navegador, lista):
    page = abrir(navegador, lista, tactil=True)
    f = video(page, "t01.html")
    page.click("#feed")
    caja = page.query_selector(".caja").bounding_box()
    assert (caja["x"], caja["y"], caja["width"], caja["height"]) == (0, 0, 390, 844)      # toda la pantalla
    assert page.evaluate("getComputedStyle(document.documentElement).overflow") == "hidden"
    # el video sabe del modo (postMessage llega después, no en el mismo click)
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'feed' && m.activo === true)")
    assert f.evaluate("window.recibidos").count({"s2s": "feed", "activo": True}) == 1
    sonar(f)
    page.wait_for_selector(".s2s-capa.activa")
    # la capa deja libre la franja de abajo, donde está la barra del video
    capa = page.query_selector(".s2s-capa").bounding_box()
    assert capa["y"] + capa["height"] <= 844 - 48
    page.touchscreen.tap(390 * 0.8, 400)                              # el toque pasa al video
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'toque' && m.x > 0.7 && m.x < 0.9)")
    arrastrar(page, 195, 600, 300)                                    # hacia arriba: el siguiente
    f2 = video(page, "t02.html")
    f2.wait_for_function("window.recibidos.some(m => m && m.s2s === 'play')")
    assert f2.evaluate("window.recibidos").count({"s2s": "feed", "activo": True}) == 1
    page.wait_for_timeout(450)                                       # termina la transición (mientras, no hay gestos)
    sonar(f2)
    page.wait_for_selector(".s2s-capa.activa")
    arrastrar(page, 195, 300, 600)                                    # hacia abajo: el anterior
    video(page, "t01.html")
    assert page.is_visible(".s2s-salir")
    page.click(".s2s-salir")                                          # la X vuelve a la lista
    assert not page.evaluate("document.querySelector('.caja').classList.contains('s2s-feed')")
    assert page.query_selector(".caja").bounding_box()["width"] < 390 and not page.is_visible(".s2s-salir")
    assert page.evaluate("getComputedStyle(document.documentElement).overflow") != "hidden"


def test_modo_feed_un_arrastre_corto_o_lento_no_cambia_de_video(navegador, lista):
    page = abrir(navegador, lista, tactil=True)
    f = video(page, "t01.html")
    page.click("#feed")
    sonar(f)
    page.wait_for_selector(".s2s-capa.activa")
    arrastrar(page, 195, 500, 440)                                    # 60 px: menos que el umbral
    cdp = page.context.new_cdp_session(page)                          # 200 px en más de 1 s: muy lento
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 195, "y": 600}]})
    for k in range(1, 6):
        page.wait_for_timeout(250)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 195, "y": 600 - 40 * k}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(500)
    assert page.evaluate("document.getElementById('v').src").endswith("t01.html")


def test_modo_feed_deslizar_hacia_abajo_desde_el_borde_de_arriba_sale(navegador, lista):
    page = abrir(navegador, lista, tactil=True)
    f = video(page, "t01.html")
    page.click("#feed")
    sonar(f)
    page.wait_for_selector(".s2s-capa.activa")
    arrastrar(page, 195, 20, 320)
    page.wait_for_function("!document.querySelector('.caja').classList.contains('s2s-feed')")
    assert page.evaluate("document.getElementById('v').src").endswith("t01.html")


def test_modo_feed_con_el_video_quieto_el_video_avisa_el_gesto(navegador, lista):
    """Sin sonar no hay capa (el toque que arranca el audio tiene que ser del video): el video avisa el gesto."""
    page = abrir(navegador, lista, tactil=True)
    f = video(page, "t01.html")
    page.click("#feed")
    assert page.query_selector(".s2s-capa.activa") is None
    f.evaluate("parent.postMessage({ s2s: { tipo: 'deslizar', dx: 4, dy: -240, ms: 120, y0: 500, duracion: 40 } }, '*')")
    video(page, "t02.html")


def test_modo_feed_en_la_compu_flechas_rueda_y_esc(navegador, lista):
    page = abrir(navegador, lista)
    f = video(page, "t01.html")
    page.click("#feed")
    page.keyboard.press("ArrowDown")
    f = video(page, "t02.html")
    page.wait_for_timeout(450)                                       # termina la transición
    page.keyboard.press("ArrowUp")
    f = video(page, "t01.html")
    page.wait_for_timeout(450)
    sonar(f)
    page.wait_for_selector(".s2s-capa.activa")
    page.mouse.move(195, 400)
    page.mouse.wheel(0, 120)                                          # la rueda: el siguiente
    f = video(page, "t02.html")
    page.wait_for_timeout(800)
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tecla', tecla: 'ArrowDown', duracion: 40 } }, '*')")   # con el foco en el video
    video(page, "t03.html")
    page.keyboard.press("Escape")
    page.wait_for_function("!document.querySelector('.caja').classList.contains('s2s-feed')")


def test_flechas_y_espacio_en_la_pagina_van_al_video(navegador, lista):
    page = abrir(navegador, lista)
    f = video(page, "t01.html")
    page.keyboard.press("ArrowRight")
    page.keyboard.press(" ")
    f.wait_for_function("window.recibidos.filter(m => m && m.s2s === 'tecla').map(m => m.tecla).join() === 'ArrowRight, '")
    page.keyboard.press("ArrowDown")                                  # fuera del modo feed no cambia de video
    page.wait_for_timeout(300)
    assert page.evaluate("document.getElementById('v').src").endswith("t01.html")


def test_las_preguntas_en_el_modo_feed_ocupan_la_pantalla(navegador, tmp_path):
    page = abrir(navegador, lista_con_preguntas(tmp_path), tactil=True)
    f = video(page, "t01.html")
    page.click("#feed")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 40, duracion: 40, reproducidos: 40 } }, '*')")
    page.wait_for_selector(".caja .s2s-quiz")
    q = page.query_selector(".s2s-quiz").bounding_box()
    assert (q["x"], q["y"], q["width"], q["height"]) == (0, 0, 390, 844)
    assert page.is_visible(".s2s-salir")                              # y se puede volver a la lista
    page.click(".s2s-quiz >> text=Saltear preguntas")
    video(page, "t02.html")
    assert page.evaluate("document.querySelector('.caja').classList.contains('s2s-feed')")


def test_si_el_video_se_recarga_solo_retoma_desde_el_ultimo_tiempo_y_anota_el_corte(navegador, lista):
    finge = "Object.defineProperty(navigator, 'clipboard', { value: { writeText: async t => { window.copiado = t; } } });"
    page = abrir(navegador, lista, init=finge)
    f = video(page, "t01.html")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0 } }, '*')")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 12.5 } }, '*')")
    f.evaluate("location.reload()")                                   # como cuando iOS mata el proceso del iframe
    f.wait_for_function("window.recibidos && window.recibidos.some(m => m && m.s2s === 'play' && m.desde === 12.5)")
    assert page.evaluate("document.getElementById('v').src").endswith("t01.html")
    cortes = json.loads(page.evaluate("localStorage.getItem('s2s-cortes:' + document.title)"))
    assert len(cortes) == 1
    c = cortes[0]
    assert c["video"] == "t01" and c["t"] == 12.5 and c["fecha"].startswith("2026-11-12") and "Mozilla" in c["ua"]
    assert guardado(page)["dias"] == {}                                # el registro va aparte del progreso
    # volver a abrirlo desde la lista no es un corte: arranca desde 0
    page.click("#lista li:nth-child(1) button")
    f = video(page, "t01.html")
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'play')")
    assert f.evaluate("window.recibidos.filter(m => m && m.s2s === 'play').map(m => m.desde)") == [None]
    assert len(json.loads(page.evaluate("localStorage.getItem('s2s-cortes:' + document.title)"))) == 1
    page.click("#exp")
    page.wait_for_function("window.copiado !== undefined")
    assert json.loads(page.evaluate("window.copiado"))["cortes"] == cortes


def test_exportar_copia_al_portapapeles(navegador, lista):
    finge = "Object.defineProperty(navigator, 'clipboard', { value: { writeText: async t => { window.copiado = t; } } });"
    page = abrir(navegador, lista, {"v": 2, "cur": "t01", "dias": {"2026-11-12": ["t01"], "2026-11-11": ["t02"]}}, init=finge)
    video(page, "t03.html")
    page.click("#exp")
    page.wait_for_function("window.copiado !== undefined")
    x = json.loads(page.evaluate("window.copiado"))
    assert x["titulo"] == "Piloto" and x["racha"] == 2 and x["generado"].startswith("2026-11-12")
    assert x["dias"] == {"2026-11-11": ["t02"], "2026-11-12": ["t01"]} and x["cortes"] == []
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


def test_solo_cuenta_como_visto_si_sono_al_menos_el_70_por_ciento(navegador, tmp_path):
    page = abrir(navegador, lista_con_preguntas(tmp_path))
    f = video(page, "t01.html")
    # sonó 20 de 40 s (se saltó al final): no queda visto, no hay preguntas, no pasa al siguiente
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 40, duracion: 40, reproducidos: 20 } }, '*')")
    page.wait_for_timeout(300)
    assert page.query_selector(".s2s-quiz") is None and texto(page, "#nVistos") == "0 / 3"
    assert guardado(page)["dias"] == {} and page.evaluate("document.getElementById('v').src").endswith("t01.html")
    # "Ver de nuevo" (en el video) y esta vez sonó 29 de 40: sí
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, duracion: 40, reproducidos: 0 } }, '*')")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 40, duracion: 40, reproducidos: 29 } }, '*')")
    page.wait_for_selector(".caja .s2s-quiz")
    assert guardado(page)["dias"] == {"2026-11-12": ["t01"]}


def test_lo_que_sono_antes_de_una_recarga_sigue_contando(navegador, lista):
    page = abrir(navegador, lista)
    f = video(page, "t01.html")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 20, duracion: 40, reproducidos: 20 } }, '*')")
    f.evaluate("location.reload()")
    f.wait_for_function("window.recibidos && window.recibidos.some(m => m && m.s2s === 'play' && m.desde === 20)")
    # el video recargado solo sabe de los últimos 10 s: con los 20 de antes son 30 de 40
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 40, duracion: 40, reproducidos: 10 } }, '*')")
    page.wait_for_function("document.getElementById('nVistos').textContent === '1 / 3'")


# --- el audio con el iPhone en modo silencio (reproduccion.js, prepararAudio) ------------------------------

# finge navigator.audioSession (iOS 17 o más) y anota los Audio() que se crean
AUDIO_SESSION = ("Object.defineProperty(navigator, 'audioSession', "
                 "{ configurable: true, value: { type: 'auto' } });")
ESPIA_AUDIO = """window.audios = []; const _Audio = window.Audio;
window.Audio = function (src) { const a = new _Audio(src); audios.push(a); return a; };"""


@pytest.mark.parametrize("ios", [False, True])
def test_la_lista_pide_playback_y_arranca_el_silencio_en_el_primer_toque(navegador, lista, ios):
    errores = []
    page = abrir(navegador, lista, init=(AUDIO_SESSION if ios else "") + ESPIA_AUDIO)
    page.on("pageerror", lambda e: errores.append(str(e)))
    page.reload()                                  # para escuchar los errores desde el arranque
    video(page, "t01.html")
    assert page.evaluate("!!navigator.audioSession") == ios
    if ios:
        assert page.evaluate("navigator.audioSession.type") == "playback"
    assert page.evaluate("audios.length") == 0      # nada antes de que la persona toque algo
    page.click("#sig")
    page.wait_for_function("audios.length === 1")
    assert page.evaluate("[audios[0].loop, audios[0].src.startsWith('data:audio/mpeg;base64,')]") == [True, True]
    page.click("#ant")
    page.wait_for_timeout(200)
    assert page.evaluate("audios.length") == 1      # uno solo, en bucle
    assert errores == []


# --- cortes de la página entera (la marca de "sonando", reproduccion.js) ------------------------------------

def marca(page):
    m = page.evaluate("localStorage.getItem('s2s-marca:' + document.title)")
    return None if m is None else json.loads(m)


def cortes(page):
    return json.loads(page.evaluate("localStorage.getItem('s2s-cortes:' + document.title)") or "[]")


HAY_MARCA = "localStorage.getItem('s2s-marca:' + document.title) !== null"
SIN_MARCA = "localStorage.getItem('s2s-marca:' + document.title) === null"


def test_mientras_suena_deja_una_marca_que_se_borra_al_pausar_terminar_o_cambiar(navegador, lista):
    page = abrir(navegador, lista)
    f = video(page, "t01.html")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0 } }, '*')")
    page.wait_for_timeout(100)
    assert marca(page) is None                                       # se guarda con cada "tiempo"
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 6 } }, '*')")
    page.wait_for_function(HAY_MARCA)
    m = marca(page)
    assert (m["video"], m["t"]) == ("t01", 6) and m["fecha"].startswith("2026-11-12")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'pausa', t: 7 } }, '*')")
    page.wait_for_function(SIN_MARCA)
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 9 } }, '*')")
    page.wait_for_function(HAY_MARCA)
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 40, duracion: 40, reproducidos: 10 } }, '*')")
    page.wait_for_function(SIN_MARCA)
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 3 } }, '*')")
    page.wait_for_function(HAY_MARCA)
    page.click("#sig")                                                # cambiar de video
    f = video(page, "t02.html")
    assert marca(page) is None
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 4 } }, '*')")
    page.wait_for_function(HAY_MARCA)
    page.reload()                                                     # cerrar o recargar la página no es un corte
    video(page, "t01.html")                                           # lo que toca hoy
    assert marca(page) is None and cortes(page) == []


def test_si_la_pagina_se_corto_sonando_anota_el_corte_y_ofrece_seguir_desde_ahi(navegador, lista):
    page = abrir(navegador, lista)
    video(page, "t01.html")
    # lo que queda cuando iOS recarga la página entera a mitad del video t02 (no avisa nada antes)
    page.evaluate("localStorage.setItem('s2s-marca:' + document.title, "
                  "JSON.stringify({ video: 't02', t: 25.4, fecha: '2026-11-12T11:58:00.000Z' }))")
    page.reload()
    f = video(page, "t02.html")
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'ir')")
    assert f.evaluate("window.recibidos") == [{"s2s": "ir", "t": 25.4}]   # quieto ahí: no reproduce solo
    c = cortes(page)
    assert [(x["video"], x["t"], x["fecha"]) for x in c] == [("t02", 25.4, "2026-11-12T11:58:00.000Z")]
    assert "Mozilla" in c[0]["ua"] and marca(page) is None
    assert texto(page, "#tAhora") == "Tema 2"
    page.reload()                                                     # el mismo corte no se anota dos veces
    video(page, "t01.html")                                           # ahora sí, lo que toca hoy
    assert len(cortes(page)) == 1


def test_una_marca_de_un_video_que_ya_no_esta_se_descarta(navegador, lista):
    page = abrir(navegador, lista)
    video(page, "t01.html")
    page.evaluate("localStorage.setItem('s2s-marca:' + document.title, "
                  "JSON.stringify({ video: 'otro', t: 5, fecha: 'x' }))")
    page.reload()
    f = video(page, "t01.html")
    page.wait_for_timeout(200)
    assert cortes(page) == [] and marca(page) is None
    assert not f.evaluate("window.recibidos.some(m => m && m.s2s === 'ir')")
