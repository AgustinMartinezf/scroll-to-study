"""El flujo del skill: Claude escribe los JSON (acá, los de datos.py) y s2s.py los comprueba."""
import json
import zipfile
from pathlib import Path

import fuentes
import pytest
import s2s
from datos import FIX, INVENTARIO, TEMAS, guion_bueno


def _zip_fixture(destino: Path) -> Path:
    z = destino / "obligatorio.zip"
    with zipfile.ZipFile(z, "w") as f:
        for p in FIX.rglob("*"):
            if p.is_file():
                f.write(p, ("biblioteca" / p.relative_to(FIX)).as_posix())
    return z


@pytest.fixture
def t(tmp_path):
    t = tmp_path / "trabajo"
    assert s2s.main(["corpus", "-t", str(t), "--repo", str(_zip_fixture(tmp_path))]) == 0
    (t / "inventario.json").write_text(json.dumps(INVENTARIO))
    assert s2s.main(["verificar", "-t", str(t)]) == 0
    (t / "temas.json").write_text(json.dumps(TEMAS))
    assert s2s.main(["temas", "-t", str(t)]) == 0
    return t


def _inv(t):
    return {a["id"]: a for a in json.loads((t / "inventario.json").read_text())["afirmaciones"]}


def test_zip_como_repo_y_corpus_numerado(t):
    assert "25|   CONSTRAINT fk_multa_prestamo" in (t / "corpus.txt").read_text(encoding="utf-8")


def test_verificacion_mecanica(t):
    inv = _inv(t)
    assert [i for i, a in inv.items() if a["estado"] == "ok"] == ["A1", "A2", "A3", "A4"]
    assert "aparece en sql/schema.sql:33" in inv["A5"]["motivos"][0]       # sugiere el lugar correcto
    assert "no aparece en el material" in inv["A6"]["motivos"][0]          # cita inventada
    assert "idx_multa_monto" in inv["A6"]["motivos"][1]
    assert inv["A7"]["motivos"] == ["no aparecen en la fuente: id_prestamo"]  # cita real, dato agregado
    assert "no existe el archivo" in inv["A8"]["motivos"][0]


def test_aprobado_a_mano_deja_el_motivo_a_la_vista(t):
    p = t / "inventario.json"; inv = json.loads(p.read_text())
    inv["afirmaciones"][6]["aprobado"] = True                               # A7
    p.write_text(json.dumps(inv))
    s2s.main(["verificar", "-t", str(t)])
    a7 = _inv(t)["A7"]
    assert a7["estado"] == "ok" and a7["motivos"]


def test_temas_sacan_afirmaciones_sin_verificar(t):
    temas = json.loads((t / "temas.json").read_text())
    assert temas["temas"][0]["afirmaciones"] == ["A1", "A2", "A3", "A4"] and temas["sin_cubrir"] == []


def test_pedido_solo_con_afirmaciones_verificadas(t, capsys):
    s2s.main(["pedido", "-t", str(t), "--tema", "t01"])
    out = capsys.readouterr().out
    assert "A4:" in out and "A5" not in out and "Tema de mañana: El trigger de préstamo" in out


def test_guion_cuenta_intentos_y_separa_errores(t, capsys):
    d = t / "t01"; d.mkdir()
    malo = guion_bueno(); malo["bloques"][0]["frases"][0] = "Hola {volar m}mundo."
    malo["bloques"][3]["fuentes"] = ["A5"]
    (d / "guion.json").write_text(json.dumps(malo))
    assert s2s.main(["guion", "-t", str(t), "--tema", "t01"]) == 1
    out = capsys.readouterr().out
    assert "ARREGLAR   " in out and "acción desconocida" in out
    assert "PREGUNTAR " in out and "A5 está para comprobar" in out
    (d / "guion.json").write_text(json.dumps(guion_bueno()))
    assert s2s.main(["guion", "-t", str(t), "--tema", "t01"]) == 0
    assert json.loads((d / "reporte.json").read_text())["intentos"] == 2
    assert all((d / f).exists() for f in ("spec.json", "script.json", "gaps.json"))


def test_avisa_datos_que_no_estan_en_las_fuentes(t):
    d = t / "t01"; d.mkdir(); (d / "guion.json").write_text(json.dumps(guion_bueno()))
    s2s.main(["guion", "-t", str(t), "--tema", "t01"])
    avisos = json.loads((d / "reporte.json").read_text())["avisos"]
    assert any("1452" in a for a in avisos)          # el código de error no sale del material


def test_icono_fuera_de_la_lista(t):
    d = t / "t01"; d.mkdir(); g = guion_bueno()
    g["bloques"][0]["elementos"].append({"type": "chip", "id": "zz", "text": "x", "icon": "rocket"})
    g["bloques"][0]["frases"][0] = "{show zz}" + g["bloques"][0]["frases"][0]
    (d / "guion.json").write_text(json.dumps(g))
    assert s2s.main(["guion", "-t", str(t), "--tema", "t01"]) == 1
    assert any("rocket" in e for e in json.loads((d / "reporte.json").read_text())["errores"])


def test_aviso_al_tercer_intento(t, capsys):
    d = t / "t01"; d.mkdir(); g = guion_bueno(); g["bloques"][0]["frases"][0] = "Hola {volar m}mundo."
    (d / "guion.json").write_text(json.dumps(g))
    for _ in range(3):
        s2s.main(["guion", "-t", str(t), "--tema", "t01"])
    assert "no sigas corrigiendo" in capsys.readouterr().out


def test_registro(t):
    cmds = [json.loads(l)["cmd"] for l in (t / "registro.jsonl").read_text().splitlines()]
    assert cmds == ["corpus", "verificar", "temas"]


def test_zip_con_ruta_peligrosa(tmp_path):
    z = tmp_path / "malo.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../fuera.txt", "x")
    with pytest.raises(SystemExit):
        s2s.main(["corpus", "-t", str(tmp_path / "t"), "--repo", str(z)])


def test_rango_amplio_y_pdf():
    c = fuentes.Corpus(archivos={"a.sql": [f"l{i}" for i in range(100)]}, paginas={"inf.pdf": ["uno", "dos FK"]})
    assert "demasiado amplio" in c.fragmento("a.sql:1-80")[1]
    assert c.fragmento("inf.pdf:p2") == ("dos FK", None)
    assert "tiene 2 páginas" in c.fragmento("inf.pdf:p5")[1]
