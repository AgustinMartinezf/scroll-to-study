"""Las preguntas de práctica de cada tema: S2S preguntas pide (sin preguntas.json) y valida (con él)."""
import copy
import json
import os
import re
import time

import pytest
import s2s
from datos import FIX, INVENTARIO, TEMAS

# Lo que Claude escribiría para t01 (afirmaciones A1–A4 de la biblioteca inventada)
BUENAS = {"preguntas": [
    {"id": "q1", "texto": "¿A qué tabla apunta la FK de multa?",
     "opciones": ["A socio", "A prestamo", "A ejemplar"], "correcta": 1,
     "explicacion": "Apunta a prestamo con id_prestamo: solo se multa a quien se llevó un ejemplar.",
     "fuentes": ["A1", "A2"]},
    {"id": "q2", "texto": "¿Por qué no hay una FK directa de multa a socio?",
     "opciones": ["Porque abriría un segundo camino que podría contradecirla",
                  "Porque una tabla no puede tener dos FK", "Porque socio no tiene clave primaria"],
     "correcta": 0, "explicacion": "Al socio ya se llega por prestamo; un segundo camino podría contradecirlo.",
     "fuentes": ["A3"]},
    {"id": "q3", "texto": "¿Qué controla que un ejemplar ya esté prestado?",
     "opciones": ["Una FK", "Un índice", "Un trigger", "Nada"], "correcta": 2,
     "explicacion": "Lo controla un trigger: una FK no puede verlo.", "fuentes": ["A4"]},
]}


@pytest.fixture
def t(tmp_path):
    t = tmp_path / "trabajo"
    assert s2s.main(["corpus", "-t", str(t), "--repo", str(FIX)]) == 0
    (t / "inventario.json").write_text(json.dumps(INVENTARIO), encoding="utf-8")
    assert s2s.main(["verificar", "-t", str(t)]) == 0
    (t / "temas.json").write_text(json.dumps(TEMAS), encoding="utf-8")
    assert s2s.main(["temas", "-t", str(t)]) == 0
    return t


def _escribir(t, datos, tema="t01"):
    d = t / tema
    d.mkdir(exist_ok=True)
    texto = datos if isinstance(datos, str) else json.dumps(datos, ensure_ascii=False)
    (d / "preguntas.json").write_text(texto, encoding="utf-8")


def _validar(t, capsys, datos, tema="t01"):
    _escribir(t, datos, tema)
    capsys.readouterr()
    codigo = s2s.main(["preguntas", "-t", str(t), "--tema", tema])
    return codigo, capsys.readouterr().out


def _buenas():
    return copy.deepcopy(BUENAS)


def test_sin_preguntas_imprime_el_pedido(t, capsys):
    capsys.readouterr()
    assert s2s.main(["preguntas", "-t", str(t), "--tema", "t01"]) == 0
    out = capsys.readouterr().out
    assert "Tema: La FK de multa" in out and "prompts/preguntas.md" in out
    assert str(t / "t01" / "preguntas.json") in out
    assert "- A4: Que un ejemplar ya esté prestado" in out and "A5" not in out   # solo lo verificado
    assert not (t / "t01" / "preguntas.json").exists()


def test_pedido_marca_los_metodos_generales(tmp_path, capsys):
    t = _con_general(tmp_path)
    capsys.readouterr()
    s2s.main(["preguntas", "-t", str(t), "--tema", "t01"])
    assert "G1 (método general, NO está en el material)" in capsys.readouterr().out


def test_preguntas_validas_pasan_y_se_registran(t, capsys):
    codigo, out = _validar(t, capsys, BUENAS)
    assert codigo == 0, out
    assert "ARREGLAR" not in out and "AVISO" not in out and "ok en el intento 1" in out
    rep = json.loads((t / "t01" / "preguntas_reporte.json").read_text(encoding="utf-8"))
    assert rep["errores"] == [] and rep["avisos"] == [] and rep["intentos"] == 1
    registro = [json.loads(l) for l in (t / "registro.jsonl").read_text(encoding="utf-8").splitlines()]
    assert registro[-1]["cmd"] == "preguntas" and registro[-1]["fase"] == "validar" and registro[-1]["ok"] is True


def _cambiar(**cambios):
    def f(p):
        p["preguntas"][0].update(cambios)
        return p
    return f


@pytest.mark.parametrize("arruinar, esperado", [
    (_cambiar(fuentes=["A99"]), "«A99» no está en el inventario"),
    (_cambiar(fuentes=["A7"]), "«A7» es de otro tema"),             # en el inventario, pero no en t01
    (_cambiar(fuentes=[]), "sin fuentes"),
    (_cambiar(correcta=3), "«correcta» tiene que ser la posición"),
    (_cambiar(correcta=-1), "«correcta» tiene que ser la posición"),
    (_cambiar(correcta="1"), "«correcta» tiene que ser la posición"),
    (_cambiar(opciones=["A socio", "A prestamo"], correcta=1), "tiene 2 opciones"),
    (_cambiar(opciones=["A socio", "A prestamo", "A ejemplar", "A libro", "A reserva"]), "tiene 5 opciones"),
    (_cambiar(opciones=["A socio", "A prestamo", "a  socio"]), "opciones repetidas: a socio"),
    (lambda p: {"preguntas": p["preguntas"][:1]}, "hay 1 preguntas"),
    (lambda p: {"preguntas": p["preguntas"] + [dict(p["preguntas"][0], id="q4")]}, "hay 4 preguntas"),
    (lambda p: {"preguntas": p["preguntas"][:2] + [dict(p["preguntas"][2], id="q1")]}, "ids de pregunta repetidos"),
    (_cambiar(explicacion=""), "falta «explicacion»"),
    (lambda p: p["preguntas"], 'tiene que ser {"preguntas"'),
])
def test_cada_error_se_detecta(t, capsys, arruinar, esperado):
    codigo, out = _validar(t, capsys, arruinar(_buenas()))
    assert codigo == 1
    assert any(esperado in l for l in out.splitlines() if l.startswith("ARREGLAR")), out


def test_fuente_de_otro_tema_aunque_este_verificada(t, capsys):
    """t02 solo tiene A4: A1 está verificada, pero es de t01."""
    p = {"preguntas": [dict(BUENAS["preguntas"][0]), dict(BUENAS["preguntas"][2])]}
    codigo, out = _validar(t, capsys, p, tema="t02")
    assert codigo == 1 and "«A1» es de otro tema" in out and "«A4»" not in out


def test_json_roto(t, capsys):
    codigo, out = _validar(t, capsys, '{"preguntas": [')
    assert codigo == 1 and "ARREGLAR   el JSON no se pudo leer" in out


def test_numero_inventado_en_la_opcion_correcta_da_aviso(t, capsys):
    p = _buenas()
    p["preguntas"][0]["opciones"][1] = "A prestamo, a los 30 días"
    codigo, out = _validar(t, capsys, p)
    assert "AVISO      pregunta q1: no aparecen en sus fuentes (¿inventados?): 30" in out
    rep = json.loads((t / "t01" / "preguntas_reporte.json").read_text(encoding="utf-8"))
    assert rep["avisos"] and codigo == 0      # como en el guion: el aviso no frena, el skill lo trata como error


def test_identificador_inventado_en_la_explicacion_da_aviso(t, capsys):
    p = _buenas()
    p["preguntas"][2]["explicacion"] = "Lo controla el trigger trg_prestamo_unico."
    _, out = _validar(t, capsys, p)
    assert "pregunta q3: no aparecen en sus fuentes (¿inventados?): trg_prestamo_unico" in out


def test_los_distractores_no_dan_aviso(t, capsys):
    p = _buenas()
    p["preguntas"][0]["opciones"][0] = "A socio, con fk_multa_socio"        # incorrecta: no se revisa
    _, out = _validar(t, capsys, p)
    assert "AVISO" not in out


def test_aviso_al_tercer_intento(t, capsys):
    malo = _cambiar(correcta=9)(_buenas())
    for _ in range(3):
        _, out = _validar(t, capsys, malo)
    assert "no sigas corrigiendo estas preguntas" in out


def test_estado_muestra_las_preguntas(t, capsys):
    def estado():
        capsys.readouterr()
        s2s.main(["estado", "-t", str(t)])
        return {l.split()[0]: l for l in capsys.readouterr().out.splitlines()}
    assert estado()["t01"].endswith("sin preguntas")
    _escribir(t, BUENAS)
    assert estado()["t01"].endswith("preguntas sin validar")
    _validar(t, capsys, BUENAS)
    lineas = estado()
    assert lineas["t01"].endswith("preguntas validadas") and lineas["t02"].endswith("sin preguntas")
    _validar(t, capsys, _cambiar(correcta=9)(_buenas()))
    assert estado()["t01"].endswith("preguntas con 1 errores")
    p = _buenas(); p["preguntas"][0]["opciones"][1] = "A prestamo, a los 30 días"
    _validar(t, capsys, p)
    assert estado()["t01"].endswith("preguntas validadas (1 avisos)")
    _escribir(t, BUENAS)                                         # cambió después de validar
    assert estado()["t01"].endswith("preguntas sin validar")


def test_tema_inexistente(t, capsys):
    assert s2s.main(["preguntas", "-t", str(t), "--tema", "t09"]) == 1
    assert "no existe el tema «t09»" in capsys.readouterr().out


# Modo materia: una pregunta sobre un método general lo dice en la explicación
def _con_general(tmp_path):
    t = tmp_path / "materia"
    s2s.main(["corpus", "-t", str(t), "--modo", "materia", "--repo", str(FIX)])
    inv = copy.deepcopy(INVENTARIO)
    inv["afirmaciones"][0]["tipo"] = "ejercicio"
    inv["afirmaciones"].append({"id": "G1", "origen": "general", "tipo": "metodo", "para": ["A1"],
                                "texto": "Para ubicar una FK, buscá qué tabla depende de cuál."})
    (t / "inventario.json").write_text(json.dumps(inv), encoding="utf-8")
    s2s.main(["verificar", "-t", str(t)])
    (t / "temas.json").write_text(json.dumps({"temas": [
        {"id": "t01", "titulo": "La FK de multa", "pregunta": "¿?", "afirmaciones": ["A1", "A2", "A3", "G1"]}]}),
        encoding="utf-8")
    s2s.main(["temas", "-t", str(t)])
    return t


def test_metodo_general_lo_dice_la_explicacion(tmp_path, capsys):
    t = _con_general(tmp_path)
    p = {"preguntas": copy.deepcopy(BUENAS["preguntas"][:2])}
    p["preguntas"][1]["fuentes"] = ["A3", "G1"]
    codigo, out = _validar(t, capsys, p)
    assert codigo == 1 and "usa un método general y la explicación no lo dice" in out
    p["preguntas"][1]["explicacion"] = "Método general, no está en tu material: " + p["preguntas"][1]["explicacion"]
    codigo, out = _validar(t, capsys, p)
    assert codigo == 0, out


def test_fuente_para_comprobar_va_a_la_persona(t, capsys):
    """Si después de armar los temas una afirmación del tema pasa a «comprobar», no la arregla el modelo."""
    p = t / "inventario.json"
    inv = json.loads(p.read_text(encoding="utf-8"))
    a3 = next(a for a in inv["afirmaciones"] if a["id"] == "A3")
    a3["estado"], a3["motivos"] = "comprobar", ["la cita no respalda la afirmación"]
    p.write_text(json.dumps(inv), encoding="utf-8")
    codigo, out = _validar(t, capsys, BUENAS)
    assert codigo == 1 and "PREGUNTAR  pregunta q2: A3 está para comprobar" in out


# Después de validarlas, las preguntas salen en la lista (s2s.py videos) y en el paquete (s2s.py paquete)
def _videos_en_la_lista(t):
    html = (t / "videos" / "index.html").read_text(encoding="utf-8")
    return json.loads(re.search(r"const VIDEOS = (\[.*?\]), TX = ", html)[1])


def _con_video(t, tema="t01"):
    """Un video ya hecho, más nuevo que su spec.json: s2s.py videos no lo rehace (no hace falta Piper)."""
    d = t / tema
    d.mkdir(exist_ok=True)
    (d / "spec.json").write_text("{}", encoding="utf-8")
    (d / "timing.json").write_text(json.dumps({"duration": 40.0}), encoding="utf-8")
    (t / "videos").mkdir(exist_ok=True)
    html = t / "videos" / f"{tema}.html"
    html.write_text("<!doctype html><html><body>video</body></html>", encoding="utf-8")
    futuro = time.time() + 60
    os.utime(html, (futuro, futuro))


def test_las_preguntas_validadas_llegan_a_la_lista_y_al_paquete_con_la_marca_general(tmp_path, capsys):
    t = _con_general(tmp_path)
    p = {"preguntas": copy.deepcopy(BUENAS["preguntas"][:2])}
    p["preguntas"][1]["fuentes"] = ["A3", "G1"]
    p["preguntas"][1]["explicacion"] = "Método general, no está en tu material: " + p["preguntas"][1]["explicacion"]
    codigo, out = _validar(t, capsys, p)
    assert codigo == 0, out
    _con_video(t)
    assert s2s.main(["videos", "-t", str(t), "--titulo", "Bases"]) == 0
    assert "AVISO" not in capsys.readouterr().out
    [v] = _videos_en_la_lista(t)
    assert [(q["id"], q["correcta"], q["general"]) for q in v["preguntas"]] == [("q1", 1, False), ("q2", 0, True)]
    assert v["preguntas"][0]["opciones"] == BUENAS["preguntas"][0]["opciones"] and "fuentes" not in v["preguntas"][0]

    assert s2s.main(["paquete", "-t", str(t)]) == 0
    paq = json.loads((t / "Bases.s2s.json").read_text(encoding="utf-8"))
    assert paq["v"] == 2 and paq["videos"][0]["preguntas"] == v["preguntas"]


def test_preguntas_editadas_despues_de_validar_no_salen_en_la_lista(t, capsys):
    _validar(t, capsys, BUENAS)
    _con_video(t)
    s2s.main(["videos", "-t", str(t)])
    assert len(_videos_en_la_lista(t)[0]["preguntas"]) == 3
    p = _buenas()
    p["preguntas"][0]["opciones"][1] = "A prestamo, a los 30 días"     # cambia después de validar
    _escribir(t, p)
    capsys.readouterr()
    assert s2s.main(["videos", "-t", str(t)]) == 0
    out = capsys.readouterr().out
    assert _videos_en_la_lista(t)[0]["preguntas"] == []
    assert f"AVISO  t01: preguntas.json no se validó o cambió después de validarlo; va sin preguntas " \
           f"(corré s2s.py preguntas -t {t} --tema t01)" in out
    # los .html de los videos no cambian: las preguntas solo van en la lista
    assert (t / "videos" / "t01.html").read_text(encoding="utf-8") == "<!doctype html><html><body>video</body></html>"
