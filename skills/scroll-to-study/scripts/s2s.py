#!/usr/bin/env python3
"""scroll to study: del material de un proyecto a videos cortos para preparar la defensa.

Claude escribe los JSON (inventario, temas, guiones); este script comprueba todo lo que se puede
comprobar con código y fabrica los videos:

  python3 s2s.py instalar                       # una vez: voz (Piper) y gsap a la carpeta de datos
  python3 s2s.py corpus    -t T --repo RUTA|repo.zip [--doc informe.pdf ...]  -> T/corpus.txt
  python3 s2s.py verificar -t T                 # verifica T/inventario.json contra el material
  python3 s2s.py temas     -t T                 # filtra T/temas.json (solo afirmaciones verificadas)
  python3 s2s.py pedido    -t T --tema t01      # el pedido del guion: el tema y SOLO sus afirmaciones
  python3 s2s.py guion     -t T --tema t01      # valida T/t01/guion.json; si está ok escribe spec.json
  python3 s2s.py video     -t T --tema t01      # voz + animación -> T/videos/t01.html
  python3 s2s.py videos    -t T [--titulo ...]  # todos los guiones listos + T/videos/index.html
  python3 s2s.py estado    -t T

Cada llamada queda en T/registro.jsonl (cuántos intentos y cuánto tiempo lleva cada etapa).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import fuentes                                      # noqa: E402
from compile import compilar                        # noqa: E402
from config import CFG, DATOS                       # noqa: E402
from etapas import (escribir, escribir_salidas, filtrar_temas, leer, pedido_guion,  # noqa: E402
                    resumen_inventario, separar_errores)

ICONOS = AQUI / "iconos"          # solo los íconos permitidos (y que existen en el motor)
LEXICO = AQUI / "lexico.json"
MAX_INTENTOS = 3

DESCARGAS = {
    "gsap": {"url": "https://registry.npmjs.org/gsap/-/gsap-3.12.5.tgz",
             "sha256": "134ab4f04f6d98d5fd55f89b6f07726a3b9660c483d4ca31acc0efec62fd5236"},
    "davefx": {"url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
                      "vits-piper-es_ES-davefx-medium.tar.bz2",
               "sha256": "a3f6beb54a9cb893279f72978a22f807a4d9fc9c7848157b524d5cc7b7f58b22"},
}


def registrar(t: Path, cmd: str, **datos: Any) -> None:
    t.mkdir(parents=True, exist_ok=True)
    with open(t / "registro.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "cmd": cmd, **datos}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# instalar
# ---------------------------------------------------------------------------

def _bajar(nombre: str) -> bytes:
    d = DESCARGAS[nombre]
    print(f"  bajando {nombre} …", flush=True)
    with urllib.request.urlopen(d["url"], timeout=120) as r:
        datos = r.read()
    if hashlib.sha256(datos).hexdigest() != d["sha256"]:
        raise SystemExit(f"{nombre}: el archivo bajado no coincide con el esperado (sha256); no lo uso")
    return datos


def _extraer_seguro(tar: tarfile.TarFile, destino: Path) -> None:
    for m in tar.getmembers():
        if m.issym() or m.islnk() or Path(m.name).is_absolute() or ".." in Path(m.name).parts:
            raise SystemExit(f"el paquete tiene una ruta peligrosa: {m.name}")
    if hasattr(tarfile, "data_filter"):
        tar.extractall(destino, filter="data")
    else:
        tar.extractall(destino)


def cmd_instalar(a: argparse.Namespace) -> int:
    problemas = []
    for mod, pip in (("numpy", "numpy"), ("soundfile", "soundfile"), ("piper", "piper-tts")):
        try:
            __import__(mod)
        except ImportError:
            problemas.append(pip)
    if problemas:
        print(f"Faltan paquetes de Python: {' '.join(problemas)}\n"
              f"  {sys.executable} -m pip install -r {AQUI.parent / 'requirements.txt'}")
        return 1
    import soundfile as sf
    if "MP3" not in sf.available_formats():
        print(f"soundfile usa libsndfile {sf.__libsndfile_version__}, sin MP3: actualizá soundfile (>= 0.12)")
        return 1
    DATOS.mkdir(parents=True, exist_ok=True)
    gsap = Path(CFG["gsap"])
    if not gsap.exists():
        with tarfile.open(fileobj=io.BytesIO(_bajar("gsap")), mode="r:gz") as tar:
            gsap.write_bytes(tar.extractfile("package/dist/gsap.min.js").read())
    for voz, modelo in CFG["voces"].items():
        if not Path(modelo).exists() and voz in DESCARGAS:
            with tarfile.open(fileobj=io.BytesIO(_bajar(voz)), mode="r:bz2") as tar:
                _extraer_seguro(tar, DATOS / "voces")
    # prueba de punta a punta de la voz
    davefx = str(CFG["voces"]["davefx"])
    prueba = DATOS / "prueba.wav"
    r = subprocess.run([sys.executable, "-m", "piper", "-m", davefx, "-c", davefx + ".json", "-f", str(prueba)],
                       input="Hola, ya está todo listo.".encode("utf-8"), capture_output=True)
    if r.returncode != 0 or not prueba.exists():
        print("Piper no pudo generar la voz:\n" + r.stderr.decode("utf-8", "replace")[-800:])
        return 1
    print(f"listo: datos en {DATOS}")
    return 0


# ---------------------------------------------------------------------------
# del material a los guiones
# ---------------------------------------------------------------------------

def _extraer(p: Path, destino: Path) -> Path:
    """Un .zip se descomprime en destino; si adentro hay una sola carpeta, esa es la raíz."""
    if p.suffix.lower() != ".zip":
        return p
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in Path(n).parts:
                raise SystemExit(f"el zip tiene una ruta peligrosa: {n}")
        z.extractall(destino)
    hijos = [h for h in destino.iterdir() if not h.name.startswith(("__MACOSX", "."))]
    return hijos[0] if len(hijos) == 1 and hijos[0].is_dir() else destino


def cmd_corpus(a: argparse.Namespace) -> int:
    t = a.trabajo
    repo = _extraer(a.repo, t / "material" / "repo") if a.repo else None
    docs = [_extraer(d, t / "material" / d.stem) if d.suffix.lower() == ".zip" else d for d in a.doc]
    origen = {"repo": str(repo.resolve()) if repo else None, "docs": [str(Path(d).resolve()) for d in docs]}
    c = fuentes.cargar(repo, [Path(d) for d in docs])
    texto = c.texto_para_llm()
    escribir(t / "origen.json", origen)
    (t / "corpus.txt").write_text(texto, encoding="utf-8")
    print(f"{len(c.archivos)} archivos, {sum(len(p) for p in c.paginas.values())} páginas de PDF, "
          f"{len(texto)} caracteres → {t / 'corpus.txt'}")
    if c.omitidos:
        print("omitidos (binarios o > 200 KB):", ", ".join(c.omitidos[:20]))
    if len(texto) > 600_000:
        print("AVISO  material muy grande: pedí solo las carpetas relevantes para la defensa")
    registrar(t, "corpus", archivos=len(c.archivos), caracteres=len(texto))
    return 0


def cmd_verificar(a: argparse.Namespace) -> int:
    t = a.trabajo
    inv = leer(t / "inventario.json")
    o = leer(t / "origen.json")
    corpus = fuentes.cargar(Path(o["repo"]) if o.get("repo") else None, [Path(d) for d in o["docs"]])
    ids = [x.get("id") for x in inv.get("afirmaciones", [])]
    if len(ids) != len(set(ids)):
        print("ERROR  hay ids de afirmación repetidos"); return 1
    faltan = [x.get("id") for x in inv["afirmaciones"] if not all(k in x for k in ("id", "texto", "fuente", "cita", "tipo"))]
    if faltan:
        print(f"ERROR  afirmaciones sin id/texto/fuente/cita/tipo: {faltan}"); return 1
    inv = fuentes.verificar(inv, corpus)
    inv["origen"] = o
    escribir(t / "inventario.json", inv)
    resumen_inventario(inv)
    registrar(t, "verificar", total=len(inv["afirmaciones"]), ok=sum(x["estado"] == "ok" for x in inv["afirmaciones"]))
    return 0


def cmd_temas(a: argparse.Namespace) -> int:
    t = a.trabajo
    temas = filtrar_temas(leer(t / "temas.json"), leer(t / "inventario.json"))
    escribir(t / "temas.json", temas)
    for x in temas["temas"]:
        aviso = "  ← menos de 2 afirmaciones" if len(x["afirmaciones"]) < 2 else ""
        print(f"  {x['id']} {x['titulo']}  ({', '.join(x['afirmaciones'])}){aviso}")
    registrar(t, "temas", temas=len(temas["temas"]), sin_cubrir=len(temas["sin_cubrir"]))
    return 0


def cmd_pedido(a: argparse.Namespace) -> int:
    print(pedido_guion(leer(a.trabajo / "inventario.json"), leer(a.trabajo / "temas.json")["temas"], a.tema))
    return 0


def cmd_guion(a: argparse.Namespace) -> int:
    t, carpeta = a.trabajo, a.trabajo / a.tema
    previo = leer(carpeta / "reporte.json") if (carpeta / "reporte.json").exists() else {}
    intento = previo.get("intentos", 0) + 1
    try:
        guion = leer(carpeta / "guion.json")
        lex = {k.lower(): v for k, v in leer(LEXICO).items()}
        lex.update({k.lower(): v for k, v in guion.get("lexico", {}).items()})
        spec, rep = compilar(guion, lex, ICONOS, leer(t / "inventario.json"))
        errores, avisos = rep.errores, rep.avisos
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        spec, errores, avisos = {}, [f"el JSON no se pudo leer: {e}"], []
    arreglar, preguntar = separar_errores(errores)
    escribir(carpeta / "reporte.json", {"errores": errores, "avisos": avisos, "intentos": intento})
    for m in avisos: print("AVISO     ", m)
    for m in arreglar: print("ARREGLAR  ", m)
    for m in preguntar: print("PREGUNTAR ", m)
    if not errores:
        escribir_salidas(carpeta, spec)
        print(f"ok en el intento {intento}: {len(spec['PHRASES'])} frases, ~{spec['DURACION_ESTIMADA']}s")
    elif arreglar and intento >= MAX_INTENTOS:
        print(f"\nYa van {intento} intentos: no sigas corrigiendo este tema; contale a la persona y pasá al siguiente.")
    registrar(t, "guion", tema=a.tema, intento=intento, errores=len(arreglar), preguntar=len(preguntar), ok=not errores)
    return 0 if not errores else 1


# ---------------------------------------------------------------------------
# de los guiones a los videos
# ---------------------------------------------------------------------------

def _tema(t: Path, tema_id: str) -> dict[str, Any]:
    return next((x for x in leer(t / "temas.json")["temas"] if x["id"] == tema_id), {"id": tema_id, "titulo": tema_id})


def hacer_video(t: Path, tema_id: str, voz: str | None) -> Path:
    import reproductor
    carpeta = t / tema_id
    if not (carpeta / "spec.json").exists():
        raise SystemExit(f"{tema_id}: no hay spec.json; primero `s2s.py guion -t {t} --tema {tema_id}` sin errores")
    inicio = time.time()
    subprocess.run([sys.executable, str(AQUI / "voice.py"), str(carpeta)] + ([voz] if voz else []), check=True)
    subprocess.run([sys.executable, str(AQUI / "engine.py"), str(carpeta)], check=True, stdout=subprocess.DEVNULL)
    tema = _tema(t, tema_id)
    destino = reproductor.construir(carpeta, t / "videos" / f"{tema_id}.html", tema["titulo"])
    dur = leer(carpeta / "timing.json")["duration"]
    registrar(t, "video", tema=tema_id, duracion=dur, segundos=round(time.time() - inicio, 1))
    print(f"{destino} ({dur:.0f} s de video, {destino.stat().st_size // 1024} KB)")
    return destino


def cmd_video(a: argparse.Namespace) -> int:
    hacer_video(a.trabajo, a.tema, a.voz)
    return 0


def cmd_videos(a: argparse.Namespace) -> int:
    import reproductor
    t = a.trabajo
    lista = []
    for x in leer(t / "temas.json")["temas"]:
        c, html = t / x["id"], t / "videos" / f"{x['id']}.html"
        if not (c / "spec.json").exists():
            print(f"  {x['id']}: sin guion validado, lo salteo")
            continue
        if a.todo or not html.exists() or html.stat().st_mtime < (c / "spec.json").stat().st_mtime:
            hacer_video(t, x["id"], a.voz)
        lista.append({"archivo": html.name, "titulo": x["titulo"], "pregunta": x.get("pregunta", ""),
                      "duracion": leer(c / "timing.json")["duration"]})
    if not lista:
        print("no hay videos para armar"); return 1
    idx = reproductor.indice(t / "videos" / "index.html", a.titulo, lista)
    print(f"{len(lista)} videos → abrí {idx}")
    return 0


def cmd_estado(a: argparse.Namespace) -> int:
    t = a.trabajo
    for x in leer(t / "temas.json")["temas"]:
        r = t / x["id"] / "reporte.json"
        if not r.exists():
            print(f"  {x['id']} {x['titulo']:32} sin guion"); continue
        rep = leer(r)
        if (t / x["id"] / "spec.json").exists() and not rep["errores"]:
            est = "video listo" if (t / "videos" / f"{x['id']}.html").exists() else "guion listo"
        else:
            est = f"{len(rep['errores'])} errores"
        print(f"  {x['id']} {x['titulo']:32} {est}, {rep['intentos']} intento(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("etapa", choices=["instalar", "corpus", "verificar", "temas", "pedido", "guion",
                                      "video", "videos", "estado"])
    ap.add_argument("-t", "--trabajo", type=Path)
    ap.add_argument("--repo", type=Path)
    ap.add_argument("--doc", type=Path, action="append", default=[])
    ap.add_argument("--tema")
    ap.add_argument("--voz", help="voz de Piper (por defecto davefx)")
    ap.add_argument("--titulo", default="Preparación de la defensa")
    ap.add_argument("--todo", action="store_true", help="videos: rehacer aunque ya existan")
    a = ap.parse_args(argv)
    if a.etapa != "instalar" and not a.trabajo:
        ap.error("pasá -t CARPETA_DE_TRABAJO")
    if a.etapa == "corpus" and not a.repo and not a.doc:
        ap.error("pasá --repo y/o --doc")
    if a.etapa in ("pedido", "guion", "video") and not a.tema:
        ap.error("pasá --tema")
    return globals()[f"cmd_{a.etapa}"](a)


if __name__ == "__main__":
    sys.exit(main())
