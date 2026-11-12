#!/usr/bin/env python3
"""Exporta un video .html a .mp4, para verlo sin navegador (Fotos, WhatsApp) en el teléfono.

    python3 mp4.py VIDEO.html SALIDA.mp4 [--fps 30] [--alto 1280]

Abre el video en Chromium, pinta cada cuadro con el reloj del propio reproductor (__s2s.pintar) y le pasa
las capturas a ffmpeg junto con el MP3 que lleva adentro el .html. Captura directo al tamaño de salida (el
reproductor escala la escena a la ventana) y con varias pestañas a la vez, cada una con un cuadro distinto:
capturar es lo que más tarda. Playwright y ffmpeg son opcionales: el
resto del skill no los necesita, y `faltantes()` dice cómo instalar lo que falte.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import config  # noqa: E402,F401  (salida en UTF-8 en Windows)

PESTANAS = 4          # capturas en paralelo: 4 bajan el tiempo por cuadro a la mitad; más casi no suma


def _python() -> str:
    return f'"{sys.executable}"' if " " in sys.executable else sys.executable


def como_instalar_ffmpeg() -> str:
    if sys.platform == "win32":
        return "winget install --id Gyan.FFmpeg -e   (y abrí una terminal nueva para que aparezca en el PATH)"
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    return "sudo apt install ffmpeg   (o el gestor de paquetes de tu distribución: dnf, pacman, …)"


def hay_playwright() -> bool:
    return importlib.util.find_spec("playwright") is not None


def chromium_instalado() -> bool:
    """¿Está el Chromium de Playwright? Arranca el driver de Playwright (un segundo), no el navegador."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            return Path(pw.chromium.executable_path).exists()
    except Exception:
        return False


def ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def dependencias() -> list[tuple[str, str | None]]:
    """[(qué, None si está o el comando que la instala)] para playwright, su Chromium y ffmpeg."""
    pw = hay_playwright()
    return [
        ("playwright", None if pw else f"{_python()} -m pip install playwright"),
        ("chromium (playwright)", None if pw and chromium_instalado() else f"{_python()} -m playwright install chromium"),
        ("ffmpeg", None if ffmpeg() else como_instalar_ffmpeg()),
    ]


def faltantes() -> list[tuple[str, str]]:
    return [(n, arreglo) for n, arreglo in dependencias() if arreglo]


def exportar(video: Path, salida: Path, fps: int = 30, alto: int = 1280) -> int:
    """Escribe salida (.mp4) y devuelve cuántos cuadros tiene. Escribe a un archivo aparte y lo renombra al
    terminar: un .mp4 a medias nunca queda con el nombre final (ni cuenta como «al día»)."""
    exe = ffmpeg()
    if not exe:
        raise SystemExit("falta ffmpeg: " + como_instalar_ffmpeg())
    alto = alto // 2 * 2                          # libx264 con yuv420p pide lados pares
    ancho = alto * 9 // 16 // 2 * 2
    html = Path(video).read_text(encoding="utf-8")
    m = re.search(r'id="s2s-mp3">([^<]+)<', html)
    if not m:
        raise SystemExit(f"{video}: no tiene el audio de un video de scroll to study")
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    parcial = salida.with_name(salida.stem + ".parcial.mp4")
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "audio.mp3"
        audio.write_bytes(base64.b64decode(m[1]))
        ff = subprocess.Popen([exe, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
                               "-c:v", "mjpeg", "-i", "-", "-i", str(audio),
                               "-vf", f"scale={ancho}:{alto}:flags=lanczos", "-c:v", "libx264", "-preset", "medium",
                               "-crf", "26", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                               "-shortest", "-movflags", "+faststart", str(parcial)], stdin=subprocess.PIPE)
        try:
            n = asyncio.run(_capturar(Path(video), ancho, alto, fps, ff.stdin.write))
            ff.stdin.close()
            if ff.wait() != 0:
                raise SystemExit(f"ffmpeg falló al exportar {video}")
        except BaseException:
            if ff.poll() is None:
                ff.kill()
                ff.wait()
            parcial.unlink(missing_ok=True)
            raise
    parcial.replace(salida)
    return n


async def _capturar(video: Path, ancho: int, alto: int, fps: int, escribir) -> int:
    """Pinta y captura todos los cuadros, de a PESTANAS a la vez, y se los pasa a escribir en orden."""
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        nav = await pw.chromium.launch()
        try:
            pestanas = []
            for _ in range(PESTANAS):
                p = await nav.new_page(viewport={"width": ancho, "height": alto})
                await p.goto(video.resolve().as_uri())
                await p.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=20000)
                await p.evaluate("document.getElementById('s2s-tapa').hidden = true;"
                                 "document.getElementById('s2s-barra').style.display = 'none'")
                pestanas.append(p)
            n = int(await pestanas[0].evaluate("__s2s.D") * fps)

            async def cuadro(p, i: int) -> bytes:
                await p.evaluate("t => __s2s.pintar(t)", i / fps)
                return await p.screenshot(type="jpeg", quality=92)

            for inicio in range(0, n, PESTANAS):
                tanda = range(inicio, min(n, inicio + PESTANAS))
                for imagen in await asyncio.gather(*(cuadro(p, i) for p, i in zip(pestanas, tanda))):
                    escribir(imagen)
            return n
        finally:
            await nav.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--alto", type=int, default=1280, help="alto del mp4 (el ancho sale de 9:16)")
    a = ap.parse_args(argv)
    falta = faltantes()
    if falta:
        print("Para exportar a MP4 falta:")
        for nombre, arreglo in falta:
            print(f"  {nombre}: {arreglo}")
        return 1
    n = exportar(a.video, a.salida, a.fps, a.alto)
    print(f"{a.salida} ({n} cuadros, {a.salida.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
