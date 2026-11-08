#!/usr/bin/env python3
"""Revisa un video generado como pide la guía de estilo, con un navegador de verdad.

    python tools/revisar.py scroll-to-study/videos/t01.html [--capturas carpeta]

Comprueba:
  - que la página cargue sin errores de JavaScript;
  - que al reproducir, la animación siga al audio (diferencia en ms);
  - zonas seguras de TikTok/Reels/Shorts: nada en los 220 px de arriba, los 420 de abajo ni a menos
    de 60 px de los costados (salvo durante los viajes de cámara, que son movimiento);
  - que nunca haya una imagen quieta más de 1 s (sin contar los subtítulos).
Herramienta de desarrollo: necesita `pip install playwright pillow numpy` y `playwright install chromium`.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright


def cuadro(page) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(page.screenshot())).convert("L"), dtype=np.int16)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--capturas", type=Path, help="guarda una captura cada 5 s para mirarlas")
    a = ap.parse_args()
    html = a.video.read_text(encoding="utf-8")
    viajes = [float(x) for x in re.findall(r'"\d+": ([\d.]+)', re.search(r'"travel": \{[^}]*\}', html)[0])]
    problemas: list[str] = []

    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        p = nav.new_page(viewport={"width": 1080, "height": 1920})
        errores: list[str] = []
        p.on("pageerror", lambda e: errores.append(str(e)))
        p.on("console", lambda m: m.type == "error" and errores.append(m.text))
        p.goto(a.video.resolve().as_uri())
        p.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=20000)
        dur = p.evaluate("__s2s.D")

        # 1) sincronía al reproducir
        p.click("#s2s-tapa")
        p.wait_for_timeout(2500)
        r = p.evaluate("({a: __s2s.ahora(), t: __timelines.main.time()})")
        desfase = abs(r["a"] - r["t"]) * 1000
        if r["a"] < 1.5:
            problemas.append(f"el audio no arrancó (a los 2,5 s va por {r['a']:.2f} s)")
        if desfase > 40:
            problemas.append(f"la animación va {desfase:.0f} ms desfasada del audio")
        p.click("#root")
        p.evaluate("document.getElementById('s2s-tapa').hidden = true; document.getElementById('s2s-barra').style.display = 'none'")

        # 2) zonas seguras y 3) imagen quieta
        fuera, quieto, previo, desde, racha = [], [], None, None, {}
        t = 0.2
        while t < dur:
            p.evaluate("t => __s2s.pintar(t)", t)
            # el fondo (papel, rejilla) se oculta para medir solo el contenido, sea cual sea el estilo
            p.evaluate("document.getElementById('bg').style.visibility = 'hidden'; document.body.style.setProperty('background', '#000', 'important');"
                       "document.querySelectorAll('#world > svg.abs').forEach(e => e.style.visibility = 'hidden')")   # caminos: decoración
            img = cuadro(p)
            p.evaluate("document.getElementById('bg').style.visibility = ''; document.querySelectorAll('#world > svg.abs').forEach(e => e.style.visibility = '')")
            viajando = t < 0.9 or any(-0.2 < t - v < 1.0 for v in viajes)
            if not viajando:
                m = img > 60
                for zona, z in (("arriba", m[:220]), ("abajo", m[1500:]), ("izquierda", m[220:1500, :60]),
                                ("derecha", m[220:1500, 1020:])):
                    if z.sum() > 50:
                        racha[zona] = racha.get(zona, 0) + 1
                        if racha[zona] == 2:          # un golpe o un pop de 0,25 s no cuenta; algo que se queda, sí
                            fuera.append(f"{t:.1f}s {zona}")
                    else:
                        racha[zona] = 0
            p.evaluate("document.getElementById('caps').style.visibility = 'hidden'")
            sin_subs = cuadro(p)
            p.evaluate("document.getElementById('caps').style.visibility = ''")
            if previo is not None:
                if (np.abs(sin_subs - previo) > 6).mean() < 0.0005:
                    desde = desde if desde is not None else t
                else:
                    if desde is not None and t - desde >= 1.0:
                        quieto.append(f"{desde:.1f}–{t:.1f}s")
                    desde = None
            previo = sin_subs
            if a.capturas and abs(t / 5 - round(t / 5)) < 0.01:
                a.capturas.mkdir(parents=True, exist_ok=True)
                Image.fromarray(img.astype(np.uint8)).save(a.capturas / f"{t:04.1f}.png")
            t = round(t + 0.25, 2)
        nav.close()

    if errores:
        problemas.append("errores en la página: " + "; ".join(errores[:3]))
    if fuera:
        problemas.append("contenido fuera de la zona segura: " + ", ".join(fuera[:8]))
    if quieto:
        problemas.append("imagen quieta: " + ", ".join(quieto))
    print(json.dumps({"video": str(a.video), "duracion": dur, "desfase_ms": round(desfase, 1),
                      "problemas": problemas}, ensure_ascii=False, indent=1))
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
