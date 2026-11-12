"""Diapositivas (.pptx), documentos de Word (.docx) y PDF escaneados en el corpus.

Los fixtures se generan acá con python-pptx y python-docx: el repositorio no guarda binarios.
"""
import json
from pathlib import Path

import formatos
import fuentes
import pytest
import s2s
from docx import Document
from pptx import Presentation
from pptx.util import Inches
from pypdf import PdfWriter


def _pptx(ruta: Path) -> Path:
    prs = Presentation()
    d1 = prs.slides.add_slide(prs.slide_layouts[1])                   # título y contenido
    d1.shapes.title.text = "Redes inalámbricas"
    d1.placeholders[1].text_frame.text = "WEP usa una clave compartida y fue quebrado hace años."

    d2 = prs.slides.add_slide(prs.slide_layouts[5])                   # solo título
    d2.shapes.title.text = "Cifrado en WPA2"
    caja = d2.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1))
    caja.text_frame.text = "WPA2 usa AES con claves de 128 bits."
    tabla = d2.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(6), Inches(1)).table
    for (f, c), texto in {(0, 0): "Protocolo", (0, 1): "Cifrado", (1, 0): "WPA2", (1, 1): "AES-CCMP"}.items():
        tabla.cell(f, c).text = texto
    d2.notes_slide.notes_text_frame.text = "Recalcar que TKIP quedó obsoleto."

    d3 = prs.slides.add_slide(prs.slide_layouts[6])                   # en blanco, con un grupo
    grupo = d3.shapes.add_group_shape()
    grupo.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame.text = "Texto dentro de un grupo"
    prs.save(str(ruta))
    return ruta


def _docx(ruta: Path) -> Path:
    doc = Document()
    doc.add_heading("Apunte de redes", level=1)
    doc.add_paragraph("El handshake de cuatro vías deriva la clave de sesión.")
    doc.add_paragraph("")                                             # los párrafos vacíos no ocupan línea
    t = doc.add_table(rows=2, cols=2)
    for (f, c), texto in {(0, 0): "Puerto", (0, 1): "Servicio", (1, 0): "443", (1, 1): "HTTPS"}.items():
        t.cell(f, c).text = texto
    doc.add_paragraph("Después de la tabla sigue el texto.")
    doc.save(str(ruta))
    return ruta


@pytest.fixture
def material(tmp_path):
    return _pptx(tmp_path / "clase.pptx"), _docx(tmp_path / "apunte.docx")


def test_pptx_por_diapositiva(material):
    d = formatos.diapositivas_pptx(material[0])
    assert len(d) == 3
    assert d[0].splitlines() == ["Redes inalámbricas", "WEP usa una clave compartida y fue quebrado hace años."]
    assert d[1].splitlines()[0] == "Cifrado en WPA2"                   # el título va primero
    assert "WPA2 usa AES con claves de 128 bits." in d[1]
    assert "Protocolo | Cifrado" in d[1] and "WPA2 | AES-CCMP" in d[1]
    assert d[1].endswith(f"{formatos.NOTAS}\nRecalcar que TKIP quedó obsoleto.")
    assert d[2] == "Texto dentro de un grupo"


def test_docx_por_parrafo_con_tablas_en_orden(material):
    assert formatos.lineas_docx(material[1]) == [
        "Apunte de redes",
        "El handshake de cuatro vías deriva la clave de sesión.",
        "Puerto | Servicio",
        "443 | HTTPS",
        "Después de la tabla sigue el texto.",
    ]


def test_corpus_marca_diapositivas_y_numera_docx(tmp_path, material, capsys):
    t = tmp_path / "trabajo"
    assert s2s.main(["corpus", "-t", str(t), "--modo", "materia", "--doc", str(material[0]),
                     "--doc", str(material[1])]) == 0
    assert "1 archivos, 0 páginas de PDF, 3 diapositivas" in capsys.readouterr().out
    corpus = (t / "corpus.txt").read_text(encoding="utf-8")
    assert "=== clase.pptx d2 ===\nCifrado en WPA2" in corpus
    assert "=== archivo: apunte.docx ===" in corpus and "4| 443 | HTTPS" in corpus


def test_cita_con_diapositiva_se_verifica(tmp_path, material):
    t = tmp_path / "trabajo"
    s2s.main(["corpus", "-t", str(t), "--modo", "materia", "--doc", str(material[0]), "--doc", str(material[1])])
    inv = {"afirmaciones": [
        {"id": "D1", "tipo": "dato", "texto": "WPA2 cifra con AES y claves de 128 bits.",
         "fuente": "clase.pptx:d2", "cita": "WPA2 usa AES con claves de 128 bits."},
        {"id": "D2", "tipo": "dato", "texto": "TKIP quedó obsoleto.",
         "fuente": "clase.pptx:d1-2", "cita": "TKIP quedó obsoleto"},             # notas del orador
        {"id": "D3", "tipo": "dato", "texto": "HTTPS usa el puerto 443.",
         "fuente": "apunte.docx:4", "cita": "443 | HTTPS"},
        # mal a propósito: la cita está en la diapositiva 1, no en la 3
        {"id": "D4", "tipo": "dato", "texto": "WEP fue quebrado.",
         "fuente": "clase.pptx:d3", "cita": "WEP usa una clave compartida"},
        {"id": "D5", "tipo": "dato", "texto": "WPA2 usa 256 bits.",                # número que no está
         "fuente": "clase.pptx:d2", "cita": "WPA2 usa AES"},
    ]}
    (t / "inventario.json").write_text(json.dumps(inv), encoding="utf-8")
    assert s2s.main(["verificar", "-t", str(t)]) == 0
    res = {a["id"]: a for a in json.loads((t / "inventario.json").read_text(encoding="utf-8"))["afirmaciones"]}
    assert [i for i, a in res.items() if a["estado"] == "ok"] == ["D1", "D2", "D3"]
    assert "aparece en clase.pptx:d1" in res["D4"]["motivos"][0]
    assert res["D5"]["motivos"] == ["no aparecen en la fuente: 256"]


def test_rango_de_diapositivas():
    c = fuentes.Corpus(diapositivas={"c.pptx": ["uno", "dos", "tres"]})
    assert c.fragmento("c.pptx:d2-3") == ("dos\ntres", None)
    assert "demasiado amplio (máximo 2)" in c.fragmento("c.pptx:d1-3")[1]
    assert "tiene 3 diapositivas" in c.fragmento("c.pptx:d4")[1]
    assert "no existe el archivo" in c.fragmento("otra.pptx:d1")[1]
    assert "usá c.pptx:dN" in c.fragmento("c.pptx:p1")[1]               # letra equivocada
    assert c.buscar("tres") == ["c.pptx:d3"]


def test_pdf_escaneado():
    c = fuentes.Corpus(paginas={"escaneado.pdf": ["", " \n", "algo"], "mitad.pdf": ["", "texto"],
                                "bien.pdf": ["a", "b"]})
    assert c.pdf_escaneados() == {"escaneado.pdf": (2, 3)}               # justo la mitad no avisa


def test_corpus_avisa_pdf_escaneado(tmp_path, capsys):
    w = PdfWriter()
    for _ in range(4):
        w.add_blank_page(width=200, height=200)
    pdf = tmp_path / "escaneado.pdf"
    with open(pdf, "wb") as f:
        w.write(f)
    assert s2s.main(["corpus", "-t", str(tmp_path / "t"), "--doc", str(pdf)]) == 0
    out = capsys.readouterr().out
    assert "AVISO  escaneado.pdf: 4 de 4 páginas no tienen texto" in out and "OCR" in out
