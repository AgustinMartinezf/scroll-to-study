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
window.VIDEO_ID = "{id}";
addEventListener("message", e => {{
  if (e.data && e.data.s2s === "play") {{ avisar("inicio"); setTimeout(() => avisar("fin"), 300); }}
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
