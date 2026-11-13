"""La app del teléfono (web/, armada con tools/sitio.py) en Chromium, con Playwright.

Se sirve _site/ con http.server en localhost (los service workers piden un origen seguro), se importa un
paquete de prueba y se reproduce. Los videos son páginas de juguete que hablan con la app igual que los
reales (postMessage "listo", "inicio", "fin"), pero terminan a los 0,3 s: no hace falta gsap, Piper ni audio.

Si Playwright o Chromium no están instalados, se saltean; con S2S_EXIGIR_NAVEGADOR=1 (el job "web" del CI)
fallan en vez de saltearse."""
import functools
import json
import os
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
import sys  # noqa: E402
sys.path.insert(0, str(RAIZ / "tools"))
import sitio  # noqa: E402

EXIGIR = os.environ.get("S2S_EXIGIR_NAVEGADOR") == "1"
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    if EXIGIR:
        raise
    pytest.skip("playwright no está instalado", allow_module_level=True)

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
VIDEO = """<!doctype html><html><head><title>{id}</title></head>
<body style="margin:0;height:100vh;background:#123;color:#fff">{id}<script>
const avisar = tipo => parent.postMessage({{ s2s: {{ tipo, video: "{id}" }} }}, "*");
window.VIDEO_ID = "{id}"; window.recibidos = [];
addEventListener("message", e => {{
  recibidos.push(e.data);
  // retomado tras una recarga ("desde"): se queda sonando, así el test lo puede mirar
  if (e.data && e.data.s2s === "play") {{ avisar("inicio"); if (!e.data.desde) setTimeout(() => avisar("fin"), 300); }}
}});
avisar("listo");
</script></body></html>"""


def paquete(titulo="Redes", ids=("t01", "t02"), sufijo=""):
    return {"v": 1, "titulo": titulo, "idioma": "es", "generado": "2026-11-13T10:00:00+00:00",
            "videos": [{"id": i, "titulo": f"Tema {i}{sufijo}", "pregunta": f"¿Pregunta {i}?", "duracion": 42,
                        "html": VIDEO.format(id=i)} for i in ids]}


def archivo(d, nombre="Redes.s2s.json"):
    return {"name": nombre, "mimeType": "application/json", "buffer": json.dumps(d).encode("utf-8")}


class _Callado(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def sitio_url(tmp_path_factory):
    d = sitio.armar(tmp_path_factory.mktemp("web") / "_site")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Callado, directory=str(d)))
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


@pytest.fixture(scope="module")
def navegador():
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch()
            yield nav
            nav.close()
    except Exception as e:                     # Chromium no instalado (`playwright install chromium`)
        if EXIGIR:
            raise
        pytest.skip(f"Chromium no disponible: {e}")


@pytest.fixture
def contexto(navegador):
    ctxs = []

    def nuevo(**kw):
        kw.setdefault("locale", "es-UY")
        kw.setdefault("viewport", {"width": 390, "height": 844})
        c = navegador.new_context(**kw)
        ctxs.append(c)
        return c
    yield nuevo
    for c in ctxs:
        c.close()


def abrir(ctx, url):
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    return page


def frame_del_video(page, vid):
    page.wait_for_function("document.getElementById('v').src.startsWith('blob:')")
    for _ in range(50):
        for f in page.frames:
            if f.url.startswith("blob:"):
                try:
                    if f.evaluate("window.VIDEO_ID") == vid:
                        return f
                except Exception:
                    pass
        page.wait_for_timeout(100)
    raise AssertionError(f"no apareció el video {vid}")


def importar(page, d, **kw):
    page.set_input_files("#archivo", archivo(d, **kw))


def texto(page, sel):
    return page.text_content(sel).strip()


def test_importar_reproducir_y_el_progreso_sigue_al_recargar(contexto, sitio_url):
    page = abrir(contexto(), sitio_url)
    assert page.is_visible("#vacio") and page.is_visible("#importar") and not page.is_visible("#instalar")
    assert texto(page, "#importar") == "Importar videos"
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    assert "2 videos guardados" in texto(page, "#aviso")
    assert texto(page, "#titulo") == "Redes" and texto(page, "#tToca") == "Tema t01"
    page.wait_for_function("document.getElementById('espacio').textContent.includes('MB')")

    # el video corre aislado: sandbox sin allow-same-origin, no ve el almacenamiento de la app
    f = frame_del_video(page, "t01")
    assert f.evaluate("(() => { try { return localStorage.length; } catch (e) { return 'bloqueado'; } })()") == "bloqueado"
    assert f.evaluate("(() => { try { return parent.document.title; } catch (e) { return 'bloqueado'; } })()") == "bloqueado"
    url_t01 = page.eval_on_selector("#v", "v => v.src")

    page.click("#toca")                                     # play -> inicio -> fin (0,3 s)
    page.wait_for_function("document.getElementById('nVistos').textContent === '1 / 2'")
    frame_del_video(page, "t02")                            # pasa solo al siguiente
    assert texto(page, "#nRacha") == "1" and texto(page, "#tToca") == "Tema t02"
    # la URL del video anterior se liberó
    assert page.evaluate("u => fetch(u).then(() => 'viva', () => 'liberada')", url_t01) == "liberada"
    guardado = json.loads(page.evaluate("localStorage.getItem('s2s:Redes')"))
    assert list(guardado["dias"].values()) == [["t01"]] and guardado["cur"] == "t02"

    page.reload()
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    assert texto(page, "#nVistos") == "1 / 2" and texto(page, "#nRacha") == "1"
    assert texto(page, "#tToca") == "Tema t02"
    frame_del_video(page, "t02")
    assert page.is_visible("li.visto") and texto(page, "li.visto .num") == "✓"


def test_un_archivo_que_no_es_paquete_da_un_error_claro_y_no_guarda_nada(contexto, sitio_url):
    page = abrir(contexto(), sitio_url)
    page.set_input_files("#archivo", {"name": "foto.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xe0"})
    page.wait_for_selector("#error:not([hidden])")
    assert "no es un paquete de scroll to study" in texto(page, "#error")
    malo = paquete()
    del malo["videos"][1]["duracion"]
    importar(page, malo)
    page.wait_for_function("document.getElementById('error').textContent.includes('videos[1].duracion')")
    assert page.is_visible("#vacio") and not page.is_visible("#reproductor")
    assert page.evaluate("""new Promise(ok => { const r = indexedDB.open('s2s-app');
        r.onsuccess = () => { const q = r.result.transaction('paquetes').objectStore('paquetes').count();
                              q.onsuccess = () => ok(q.result); }; })""") == 0


def test_varios_paquetes_reimportar_conserva_el_progreso_y_borrar(contexto, sitio_url):
    page = abrir(contexto(), sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    page.click("#toca")
    page.wait_for_function("document.getElementById('nVistos').textContent === '1 / 2'")

    importar(page, paquete("Bases de datos", ("b1",)), nombre="Bases.s2s.json")
    page.wait_for_function("document.getElementById('titulo').textContent === 'Bases de datos'")
    assert page.is_visible("#paquetes")
    assert page.eval_on_selector_all("#paquetes option", "os => os.map(o => o.value)") == ["Bases de datos", "Redes"]
    assert texto(page, "#nVistos") == "0 / 1"

    page.select_option("#paquetes", "Redes")
    page.wait_for_function("document.getElementById('titulo').textContent === 'Redes'")
    assert texto(page, "#nVistos") == "1 / 2"

    # reimportar el mismo título: reemplaza los videos (t02 sale, t03 entra) y el progreso queda
    importar(page, paquete("Redes", ("t01", "t03"), sufijo=" (nuevo)"))
    page.wait_for_function("document.getElementById('aviso').textContent.includes('Se actualizó')")
    assert texto(page, "#nVistos") == "1 / 2"
    assert page.eval_on_selector_all("#lista .t b", "bs => bs.map(b => b.textContent)") == ["Tema t01 (nuevo)", "Tema t03 (nuevo)"]
    claves = page.evaluate("""new Promise(ok => { const r = indexedDB.open('s2s-app');
        r.onsuccess = () => { const q = r.result.transaction('videos').objectStore('videos').getAllKeys();
                              q.onsuccess = () => ok(q.result); }; })""")
    assert sorted(claves) == sorted(['["Bases de datos","b1"]', '["Redes","t01"]', '["Redes","t03"]'])

    # borrar pide confirmación: con "no" no pasa nada
    page.once("dialog", lambda d: d.dismiss())
    page.click("#borrarPaq")
    assert texto(page, "#titulo") == "Redes"
    page.once("dialog", lambda d: d.accept())
    page.click("#borrarPaq")
    page.wait_for_function("document.getElementById('titulo').textContent === 'Bases de datos'")
    assert not page.is_visible("#paquetes")
    assert page.evaluate("localStorage.getItem('s2s:Redes')") is not None     # si lo reimporta, el progreso sigue


def test_abre_sin_conexion_desde_el_service_worker(contexto, sitio_url):
    ctx = contexto()
    page = abrir(ctx, sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
    page.wait_for_function("""caches.keys().then(ks => ks.some(k => k.startsWith('s2s-app-')))""")

    ctx.set_offline(True)
    page.reload()
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    assert texto(page, "#titulo") == "Redes"
    frame_del_video(page, "t01")
    page.click("#toca")
    page.wait_for_function("document.getElementById('nVistos').textContent === '1 / 2'")
    # una pestaña nueva, también sin red
    otra = abrir(ctx, sitio_url)
    assert texto(otra, "#titulo") == "Redes"


def test_iphone_sin_instalar_explica_como_instalarla(contexto, sitio_url):
    page = abrir(contexto(user_agent=IPHONE, locale="en-US", is_mobile=True, has_touch=True), sitio_url)
    assert page.is_visible("#instalar") and not page.is_visible("#importar") and not page.is_visible("#vacio")
    assert texto(page, "#iTitulo") == "First, install the app"
    assert "Add to Home Screen" in texto(page, "#iPaso2")
    assert "separate from Safari" in texto(page, "#iSeparado")
    page.click("#importarIgual")
    assert page.is_visible("#importar") and not page.is_visible("#instalar")
    assert texto(page, "#importar") == "Import videos"


def test_iphone_con_la_app_instalada_muestra_importar(contexto, sitio_url):
    ctx = contexto(user_agent=IPHONE, is_mobile=True, has_touch=True)
    ctx.add_init_script("Object.defineProperty(navigator, 'standalone', { get: () => true })")
    page = abrir(ctx, sitio_url)
    assert page.is_visible("#importar") and not page.is_visible("#instalar")


# --- preguntas después del video (paquete v2) ------------------------------------------------------

HOY = datetime(2026, 11, 12, 12, 0)
PREGUNTAS = [
    {"id": "q1", "texto": "¿A qué tabla apunta la FK de multa?", "opciones": ["A socio", "A prestamo", "A ejemplar"],
     "correcta": 1, "explicacion": "Apunta a prestamo con id_prestamo.", "general": False},
    {"id": "q2", "texto": "¿Cómo se ubica una FK?", "opciones": ["Por el nombre", "Por la dependencia", "Al azar"],
     "correcta": 1, "explicacion": "Método general, no está en tu material: por la dependencia.", "general": True},
]


def paquete_v2():
    """t01 trae preguntas; t02 no."""
    d = paquete()
    d["v"] = 2
    for x in d["videos"]:
        x["preguntas"] = PREGUNTAS if x["id"] == "t01" else []
    return d


def abrir_el_dia(ctx, url, fecha=HOY):
    page = ctx.new_page()
    page.clock.set_fixed_time(fecha)
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    return page


def test_preguntas_despues_del_video_y_el_tema_vuelve_manana(contexto, sitio_url):
    page = abrir_el_dia(contexto(), sitio_url)
    importar(page, paquete_v2())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    assert texto(page, "#nHoy") == "2" and texto(page, "#lHoy") == "para hoy"
    page.click("#toca")                                     # play -> fin (0,3 s) -> preguntas
    page.wait_for_selector(".caja .s2s-quiz")
    assert texto(page, ".s2s-quiz .q-num") == "Pregunta 1 de 2"
    assert texto(page, ".s2s-quiz h2") == "¿A qué tabla apunta la FK de multa?"

    page.click(".s2s-quiz .q-op >> text=A prestamo")        # bien
    assert texto(page, ".s2s-quiz .q-exp b") == "¡Bien!"
    page.click(".s2s-quiz .q-sig")
    assert texto(page, ".s2s-quiz .q-gen") == "método general · no está en tu material"
    page.click(".s2s-quiz .q-op >> text=Por el nombre")     # mal
    assert page.eval_on_selector_all(".s2s-quiz .q-op", "bs => bs.map(b => b.className)") == [
        "q-op mal", "q-op bien", "q-op"]
    assert texto(page, ".s2s-quiz .q-exp b") == "No era esa."
    assert "por la dependencia" in texto(page, ".s2s-quiz .q-exp")
    page.click(".s2s-quiz .q-sig")
    assert texto(page, ".s2s-quiz .q-res") == "1 de 2 correctas"
    assert texto(page, ".s2s-quiz .q-vuelve") == "Este tema vuelve mañana."
    assert texto(page, ".s2s-quiz .q-seguir") == "Seguir: Tema t02"
    g = json.loads(page.evaluate("localStorage.getItem('s2s:Redes')"))
    assert g["repaso"] == {"t01": {"nivel": 0, "proxima": "2026-11-13",
                                   "historial": [{"fecha": "2026-11-12", "aciertos": 1, "total": 2}]}}
    assert g["dias"] == {"2026-11-12": ["t01"]}

    page.reload()
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    frame_del_video(page, "t02")                            # hoy toca t02 (nuevo); t01 vuelve mañana
    assert page.query_selector(".s2s-quiz") is None
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Al día · vuelve mañana"
    assert texto(page, "#lista li:nth-child(2) .s2s-rep") == "Nuevo"
    assert texto(page, "#nHoy") == "1" and texto(page, "#tToca") == "Tema t02"


def test_saltear_preguntas_en_la_app(contexto, sitio_url):
    page = abrir_el_dia(contexto(), sitio_url)
    importar(page, paquete_v2())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    page.click("#toca")
    page.wait_for_selector(".caja .s2s-quiz")
    page.click(".s2s-quiz >> text=Saltear preguntas")
    frame_del_video(page, "t02")                            # sigue con lo que toca hoy (y lo reproduce)
    page.wait_for_function("document.getElementById('nVistos').textContent === '2 / 2'")
    assert page.query_selector(".s2s-quiz") is None         # t02 no tiene preguntas
    g = json.loads(page.evaluate("localStorage.getItem('s2s:Redes')"))
    assert g["repaso"] == {} and g["dias"] == {"2026-11-12": ["t01", "t02"]}
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Al día"
    assert texto(page, "#tToca") == "Nada pendiente hoy" and texto(page, "#nHoy") == "0"


def test_si_el_video_se_recarga_solo_la_app_lo_retoma_y_anota_el_corte(contexto, sitio_url):
    ctx = contexto()
    ctx.add_init_script("Object.defineProperty(navigator, 'clipboard', "
                        "{ value: { writeText: async t => { window.copiado = t; } } });")
    page = abrir_el_dia(ctx, sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    f = frame_del_video(page, "t01")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, video: 't01' } }, '*')")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 7.25, video: 't01' } }, '*')")
    # un iframe sandbox no puede recargar su propia URL blob: se recarga desde afuera, sin pasar por abrir()
    # (para la app es lo mismo que cuando iOS lo recarga solo)
    page.evaluate("(v => { v.src = v.src; })(document.getElementById('v'))")
    f = frame_del_video(page, "t01")
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'play' && m.desde === 7.25)")
    cortes = json.loads(page.evaluate("localStorage.getItem('s2s-cortes:Redes')"))
    assert [(c["video"], c["t"]) for c in cortes] == [("t01", 7.25)] and cortes[0]["fecha"].startswith("2026-11-12")
    assert json.loads(page.evaluate("localStorage.getItem('s2s:Redes')"))["dias"] == {}
    page.click("#exp")
    page.wait_for_function("window.copiado !== undefined")
    assert json.loads(page.evaluate("window.copiado"))["cortes"] == cortes


def test_la_app_no_cuenta_un_video_que_casi_no_sono(contexto, sitio_url):
    page = abrir_el_dia(contexto(), sitio_url)
    importar(page, paquete_v2())
    page.wait_for_selector("#reproductor:not([hidden])")
    f = frame_del_video(page, "t01")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 42, duracion: 42, reproducidos: 12, video: 't01' } }, '*')")
    page.wait_for_timeout(300)
    assert page.query_selector(".s2s-quiz") is None and texto(page, "#nVistos") == "0 / 2"
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 42, duracion: 42, reproducidos: 30, video: 't01' } }, '*')")
    page.wait_for_selector(".caja .s2s-quiz")
    assert texto(page, "#nVistos") == "1 / 2"
