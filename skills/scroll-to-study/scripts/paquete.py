"""Paquete para la app del teléfono: todos los videos de un trabajo en un solo .s2s.json.

La app (web/, publicada en GitHub Pages) no trae material: cada persona importa este archivo y queda
guardado en su teléfono. El formato (v2):

    {"v": 2, "titulo", "idioma", "generado": "<ISO>",
     "videos": [{"id", "titulo", "pregunta", "duracion", "html",
                 "preguntas": [{"id", "texto", "opciones", "correcta", "explicacion", "general"}]}]}

en el orden de temas.json, solo con los temas que ya tienen video en T/videos/. "preguntas" son las de
T/tNN/preguntas.json solo si se validaron sin errores y no cambiaron después (etapas.preguntas_listas);
si no, va una lista vacía. v1 era igual sin "preguntas". web/paquete.js valida lo mismo del lado de la
app y acepta v1 y v2; si cambia el formato, cambian los dos (y sube "v").
"""
from __future__ import annotations

import html as html_mod
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etapas import preguntas_listas

VERSION = 2
SUFIJO = ".s2s.json"
TITULO_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
# lo que no puede ir en un nombre de archivo en Windows, macOS o Linux
PROHIBIDOS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def titulo_de_lista(t: Path) -> str | None:
    """El título con el que se armó T/videos/index.html (así la clave del progreso coincide)."""
    idx = t / "videos" / "index.html"
    if not idx.exists():
        return None
    m = TITULO_RE.search(idx.read_text(encoding="utf-8")[:4000])
    if not m:
        return None
    return html_mod.unescape(m[1]).strip() or None


def nombre_archivo(titulo: str) -> str:
    """'Redes 2026: parcial' -> 'Redes-2026-parcial.s2s.json' (sin espacios ni caracteres prohibidos)."""
    base = PROHIBIDOS_RE.sub("", re.sub(r"\s+", "-", titulo.strip()))
    base = re.sub(r"-{2,}", "-", base).strip(".-") or "videos"
    return base[:80] + SUFIJO


def _duracion(t: Path, tema_id: str) -> float | None:
    timing = t / tema_id / "timing.json"
    if not timing.exists():
        return None
    return round(float(json.loads(timing.read_text(encoding="utf-8"))["duration"]), 1)


def armar(t: Path, titulo: str, idioma: str, ahora: datetime | None = None, inv: dict[str, Any] | None = None
          ) -> tuple[dict[str, Any], list[str], list[str], dict[str, str]]:
    """Devuelve (paquete, temas sin video, temas sin duración conocida, {tema: motivo} de los que van sin
    preguntas). inv: el inventario, para marcar las preguntas que usan un método general."""
    temas = json.loads((t / "temas.json").read_text(encoding="utf-8"))["temas"]
    videos, sin_video, sin_duracion, sin_preguntas = [], [], [], {}
    for x in temas:
        archivo = t / "videos" / f"{x['id']}.html"
        if not archivo.exists():
            sin_video.append(x["id"])
            continue
        dur = _duracion(t, x["id"])
        if dur is None:
            sin_duracion.append(x["id"])
        preguntas, motivo = preguntas_listas(t / x["id"], inv)
        if motivo:
            sin_preguntas[x["id"]] = motivo
        videos.append({"id": x["id"], "titulo": x.get("titulo") or x["id"], "pregunta": x.get("pregunta", ""),
                       "duracion": dur or 0.0, "html": archivo.read_text(encoding="utf-8"), "preguntas": preguntas})
    ahora = ahora or datetime.now(timezone.utc)
    paquete = {"v": VERSION, "titulo": titulo, "idioma": idioma,
               "generado": ahora.isoformat(timespec="seconds"), "videos": videos}
    return paquete, sin_video, sin_duracion, sin_preguntas


def escribir(t: Path, paquete: dict[str, Any]) -> Path:
    destino = t / nombre_archivo(paquete["titulo"])
    # compacto: el html ya es grande y el archivo viaja por WhatsApp o AirDrop
    destino.write_text(json.dumps(paquete, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return destino


def tamano(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(1, round(n / 1024))} KB"
