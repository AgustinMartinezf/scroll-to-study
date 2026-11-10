#!/usr/bin/env python3
"""Exports a video .html to .mp4 (for the README, or to post it somewhere).

    python3 tools/mp4.py VIDEO.html SALIDA.mp4 [--fps 30] [--alto 1280]

Opens the video in Chromium, paints every frame with the player's own clock (__s2s.pintar) and pipes
the screenshots to ffmpeg together with the MP3 embedded in the .html. Needs playwright and ffmpeg.
"""
import argparse
import base64
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--alto", type=int, default=1280, help="alto del mp4 (el ancho sale de 9:16)")
    a = ap.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("falta ffmpeg")
    html = a.video.read_text(encoding="utf-8")
    mp3 = base64.b64decode(re.search(r'id="s2s-mp3">([^<]+)<', html)[1])
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "audio.mp3"
        audio.write_bytes(mp3)
        ancho = a.alto * 9 // 16 // 2 * 2
        ff = subprocess.Popen([ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps),
                               "-c:v", "mjpeg", "-i", "-", "-i", str(audio),
                               "-vf", f"scale={ancho}:{a.alto}:flags=lanczos", "-c:v", "libx264", "-preset", "slow",
                               "-crf", "26", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                               "-shortest", "-movflags", "+faststart", str(a.salida)], stdin=subprocess.PIPE)
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            p = nav.new_page(viewport={"width": 1080, "height": 1920})
            p.goto(a.video.resolve().as_uri())
            p.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=20000)
            p.evaluate("document.getElementById('s2s-tapa').hidden = true;"
                       "document.getElementById('s2s-barra').style.display = 'none'")
            dur = p.evaluate("__s2s.D")
            n = int(dur * a.fps)
            for i in range(n):
                p.evaluate("t => __s2s.pintar(t)", i / a.fps)
                ff.stdin.write(p.screenshot(type="jpeg", quality=92))
            nav.close()
        ff.stdin.close()
        if ff.wait() != 0:
            sys.exit("ffmpeg falló")
    print(f"{a.salida} ({n} cuadros, {a.salida.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
