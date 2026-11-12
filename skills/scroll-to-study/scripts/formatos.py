"""Diapositivas (.pptx) y documentos de Word (.docx) -> texto que fuentes.py puede numerar y citar.

  .pptx: una lista con el texto de cada diapositiva (título, cuadros de texto, tablas y notas del
         orador), que se cita como «clase.pptx:d4».
  .docx: una lista de líneas (un párrafo o una fila de tabla por línea, en el orden del documento),
         que se cita como «apunte.docx:12-18», igual que un archivo de texto.

Las imágenes no tienen texto que citar, así que no entran.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

NOTAS = "[notas del orador]"


def _fila(celdas: Iterable[Any]) -> str:
    """Las celdas combinadas se repiten en python-pptx/docx: cada texto va una vez por fila."""
    textos: list[str] = []
    for c in celdas:
        t = " ".join(c.text.split())
        if t and (not textos or textos[-1] != t):
            textos.append(t)
    return " | ".join(textos)


def _textos_forma(forma: Any) -> list[str]:
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    if forma.shape_type == MSO_SHAPE_TYPE.GROUP:
        return [t for f in forma.shapes for t in _textos_forma(f)]
    if getattr(forma, "has_table", False) and forma.has_table:
        return [f for f in (_fila(fila.cells) for fila in forma.table.rows) if f]
    if forma.has_text_frame:
        return [p.text for p in forma.text_frame.paragraphs if p.text.strip()]
    return []


def diapositivas_pptx(p: Path) -> list[str]:
    from pptx import Presentation
    salida = []
    for d in Presentation(str(p)).slides:
        titulo = d.shapes.title
        lineas = _textos_forma(titulo) if titulo is not None else []
        for forma in d.shapes:
            if titulo is None or forma.shape_id != titulo.shape_id:
                lineas += _textos_forma(forma)
        if d.has_notes_slide:
            notas = [l for l in d.notes_slide.notes_text_frame.text.splitlines() if l.strip()]
            if notas:
                lineas += [NOTAS, *notas]
        salida.append("\n".join(lineas))
    return salida


def lineas_docx(p: Path) -> list[str]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = Document(str(p))
    lineas: list[str] = []
    for el in doc.element.body.iterchildren():
        nombre = el.tag.rsplit("}", 1)[-1]
        if nombre == "p":
            lineas += [l for l in Paragraph(el, doc).text.splitlines() if l.strip()]
        elif nombre == "tbl":
            lineas += [f for f in (_fila(fila.cells) for fila in Table(el, doc).rows) if f]
    return lineas
