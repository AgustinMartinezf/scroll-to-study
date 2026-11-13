#!/usr/bin/env python3
"""Builds the phone app's site (what GitHub Pages publishes) into a folder, to test it locally.

    python3 tools/sitio.py [_site]          # web/ + progreso.js -> _site/
    python3 -m http.server -d _site 8000    # then open http://localhost:8000/
    python3 tools/sitio.py --iconos         # regenerate web/iconos/ from .claude-plugin/icon.png (needs Pillow)

progreso.js has a single source (skills/scroll-to-study/scripts/progreso.js) and is copied here, not
kept in web/. The service worker gets a version (a hash of every file of the site) and the list of
files to cache, so every published change uses a new cache. .github/workflows/pages.yml runs this same
script.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
WEB = RAIZ / "web"
PROGRESO = RAIZ / "skills" / "scroll-to-study" / "scripts" / "progreso.js"
ICONO = RAIZ / ".claude-plugin" / "icon.png"
ICONOS = {"icono-192.png": 192, "icono-512.png": 512, "apple-touch-icon.png": 180}


def armar(destino: Path) -> Path:
    if (WEB / "progreso.js").exists():
        raise SystemExit("web/progreso.js must not exist: the only source is skills/scroll-to-study/scripts/progreso.js")
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(WEB, destino)
    shutil.copy2(PROGRESO, destino / "progreso.js")
    archivos = sorted(p.relative_to(destino).as_posix() for p in destino.rglob("*") if p.is_file() and p.name != "sw.js")
    huella = hashlib.sha256()
    for nombre in archivos + ["sw.js"]:
        huella.update(nombre.encode() + b"\0" + (destino / nombre).read_bytes())
    sw = (destino / "sw.js").read_text(encoding="utf-8")
    for marca in ('"__VERSION__"', "/*__ARCHIVOS__*/"):
        if marca not in sw:
            raise SystemExit(f"web/sw.js lost its {marca} placeholder")
    sw = sw.replace('"__VERSION__"', json.dumps(huella.hexdigest()[:12]))
    sw = sw.replace("/*__ARCHIVOS__*/", ", ".join(json.dumps(a) for a in archivos))
    (destino / "sw.js").write_text(sw, encoding="utf-8")
    return destino


def iconos() -> None:
    from PIL import Image
    im = Image.open(ICONO).convert("RGB")      # opaque: iOS paints a transparent touch icon black
    (WEB / "iconos").mkdir(exist_ok=True)
    for nombre, lado in ICONOS.items():
        im.resize((lado, lado), Image.LANCZOS).save(WEB / "iconos" / nombre, optimize=True)


def main(argv: list[str]) -> int:
    if argv[:1] == ["--iconos"]:
        iconos()
        print(f"icons -> {WEB / 'iconos'}")
        return 0
    destino = armar(Path(argv[0]) if argv else RAIZ / "_site")
    print(f"site -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
