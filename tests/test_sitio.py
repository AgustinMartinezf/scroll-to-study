"""tools/sitio.py: arma el sitio de la app (web/ + progreso.js) igual que el workflow de Pages."""
import json
import re
import struct
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))

import sitio  # noqa: E402


def test_progreso_y_cuestionario_tienen_una_sola_fuente_y_se_copian_al_armar(tmp_path):
    for js in sitio.COMPARTIDOS:
        assert not (RAIZ / "web" / js.name).exists(), js.name
    d = sitio.armar(tmp_path / "_site")
    assert (d / "progreso.js").read_bytes() == sitio.PROGRESO.read_bytes()
    assert (d / "cuestionario.js").read_bytes() == sitio.CUESTIONARIO.read_bytes()
    assert (d / "reproduccion.js").read_bytes() == sitio.REPRODUCCION.read_bytes()
    for nombre in ("index.html", "app.js", "paquete.js", "sw.js", "manifest.webmanifest",
                   "iconos/icono-192.png", "iconos/icono-512.png", "iconos/apple-touch-icon.png"):
        assert (d / nombre).is_file(), nombre


def test_el_service_worker_cachea_todo_con_una_version_por_contenido(tmp_path, monkeypatch):
    d = sitio.armar(tmp_path / "a")
    sw = (d / "sw.js").read_text(encoding="utf-8")
    assert '"__VERSION__"' not in sw and "/*__ARCHIVOS__*/" not in sw
    version = re.search(r'const VERSION = "([0-9a-f]{12})";', sw)[1]
    lista = json.loads(re.search(r"const ARCHIVOS = (\[.*?\]);", sw)[1])
    esperados = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file() and p.name != "sw.js")
    assert lista == ["./"] + esperados and "progreso.js" in lista and "cuestionario.js" in lista and "reproduccion.js" in lista
    assert "index.html" in lista
    # armar dos veces lo mismo da la misma versión; cambiar un archivo da otra (y otra caché)
    assert sitio.armar(tmp_path / "b").joinpath("sw.js").read_text(encoding="utf-8") == sw
    web = tmp_path / "web"
    import shutil
    shutil.copytree(sitio.WEB, web)
    (web / "app.js").write_text((web / "app.js").read_text(encoding="utf-8") + "\n// cambio\n", encoding="utf-8")
    monkeypatch.setattr(sitio, "WEB", web)
    otra = re.search(r'const VERSION = "(\w+)"', sitio.armar(tmp_path / "c").joinpath("sw.js").read_text(encoding="utf-8"))[1]
    assert otra != version


def test_el_service_worker_borra_las_caches_viejas_y_responde_desde_cache():
    sw = (RAIZ / "web" / "sw.js").read_text(encoding="utf-8")
    assert "caches.delete" in sw and "k !== CACHE" in sw
    assert sw.index("c.match(req") < sw.index("fetch(req)")      # caché primero


def test_manifest_instalable_bajo_un_subcamino():
    m = json.loads((RAIZ / "web" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["display"] == "standalone"
    # vive en /scroll-to-study/: nada absoluto
    assert m["start_url"] == "./" and m["scope"] == "./"
    tamanos = set()
    for i in m["icons"]:
        assert not i["src"].startswith("/")
        png = (RAIZ / "web" / i["src"]).read_bytes()
        ancho, alto = struct.unpack(">II", png[16:24])
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and i["sizes"] == f"{ancho}x{alto}"
        tamanos.add(ancho)
    assert {192, 512} <= tamanos
    png = (RAIZ / "web" / "iconos" / "apple-touch-icon.png").read_bytes()
    assert struct.unpack(">II", png[16:24]) == (180, 180)


def test_la_pagina_no_usa_nada_de_afuera():
    html = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")
    assert not re.findall(r'(?:src|href)="(?:https?:)?//', html)
    assert 'sandbox="allow-scripts"' in html and "allow-same-origin" not in html
    # el selector de iOS deshabilita extensiones que no conoce: sin filtro accept
    assert re.search(r'<input id="archivo" type="file"[^>]*>', html) and "accept=" not in html
    for js in [RAIZ / "web" / x for x in ("app.js", "paquete.js", "sw.js")] + list(sitio.COMPARTIDOS):
        assert not re.search(r"https?://", js.read_text(encoding="utf-8")), js.name
