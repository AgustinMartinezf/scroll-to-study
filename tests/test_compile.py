import copy
import json

import pytest
from compile import compilar
from conftest import SKILL
from datos import EJEMPLO

LEX = json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8"))


def errores(mod):
    g = copy.deepcopy(EJEMPLO); mod(g)
    return " | ".join(compilar(g, LEX)[1].errores)


def test_ejemplo_compila_sin_errores():
    spec, rep = compilar(copy.deepcopy(EJEMPLO), LEX, SKILL / "scripts" / "iconos")
    assert rep.errores == []
    assert spec["GAPS"] == {3: 1.0, 6: 1.0, 8: 1.0, 11: 1.0}     # todos terminan mostrando algo


@pytest.mark.parametrize("mod, esperado", [
    (lambda g: g["bloques"][0]["frases"].__setitem__(0, "Hola {show nada}mundo."), "«nada» no existe"),
    (lambda g: g["bloques"][1]["frases"].__setitem__(0, "Y el préstamo {show m}apunta."), "es de otro bloque"),
    (lambda g: g["bloques"][1].__setitem__("frases", ["Sin ninguna animación."]), "ninguna frase anima"),
    (lambda g: g["bloques"][0]["frases"].__setitem__(1, "Apunta al {show fkp}"), "sin palabra después"),
    (lambda g: g["bloques"][0]["frases"].__setitem__(1, "Usa {show fkp}ON-DELETE acá."), "no se puede anclar"),
    (lambda g: g["bloques"][0]["frases"].__setitem__(1, "La efe~ka {show fkp}apunta."), "va en el léxico"),
    (lambda g: g["bloques"][0]["frases"].__setitem__(1, "Apunta {volar fkp}acá."), "acción desconocida"),
    (lambda g: g["bloques"][0]["frases"].__setitem__(1, "Apunta {strike e1}acá."), "strike sobre «e1»"),
    (lambda g: g["bloques"][0].__setitem__("comprobar", ["¿la FK es compuesta?"]), "[COMPROBAR] sin resolver"),
    (lambda g: g["bloques"][0]["elementos"][0]["rows"].append(["1", "2"]), "tiene 2 celdas"),
    (lambda g: g["bloques"][0]["elementos"].append({"type": "chip", "id": "m", "text": "x"}), "id repetido"),
    (lambda g: g["bloques"][0]["elementos"].append({"type": "chip", "id": "z", "text": "x" * 80}), "no entra"),
    (lambda g: g["final"]["frases"].__setitem__(1, "Mañana: la PK."), "falta {show fnext}"),
    (lambda g: g["final"]["lineas"].append("tercera línea"), "fl3 nunca aparece"),
])
def test_errores(mod, esperado):
    assert esperado in errores(mod)


def test_resaltado_por_aparicion():
    spec, _ = compilar(copy.deepcopy(EJEMPLO), LEX)
    assert [0, 14, "b"] in spec["KEYS"]               # el segundo "no" de la frase 0
    assert not any(k[0] == 7 for k in spec["KEYS"])   # "¿Y por qué no...?" no va en rojo


def test_ancla_segunda_aparicion():
    spec, _ = compilar(copy.deepcopy(EJEMPLO), LEX)
    assert ["0:no#2", "bad", "m-r1"] in spec["EVENTS"]


def test_el_prompt_apunta_a_los_dos_ejemplos_y_ambos_compilan():
    p = (SKILL / "prompts" / "guion.md").read_text(encoding="utf-8")
    assert "prompts/ejemplo_guion.json" in p and "prompts/example_script_en.json" in p
    en = json.loads((SKILL / "prompts" / "example_script_en.json").read_text(encoding="utf-8"))
    lex_en = json.loads((SKILL / "scripts" / "lexico_en.json").read_text(encoding="utf-8"))
    for g, lex in ((EJEMPLO, LEX), (en, lex_en)):
        spec, rep = compilar(copy.deepcopy(g), lex, SKILL / "scripts" / "iconos")
        assert rep.errores == [] and any(e[1] == "boom" for e in spec["EVENTS"])


@pytest.mark.parametrize("elemento, esperado", [
    ({"type": "counter", "id": "n", "value": "muchos"}, "tiene que ser un número"),
    ({"type": "counter", "id": "n", "value": "12345678901"}, "tiene que ser un número"),
    ({"type": "chart", "id": "g", "bars": [["solo una", 3]]}, "entre 2 y 5 barras"),
    ({"type": "chart", "id": "g", "bars": [["a", 1], ["b", "dos"]]}, "número >= 0"),
    ({"type": "chart", "id": "g", "bars": [["una etiqueta demasiado larga", 1], ["b", 2]]}, "pasa de 18"),
    ({"type": "chat", "id": "c", "msgs": [["c", "hola"]]}, '"a"|"b"'),
    ({"type": "chat", "id": "c", "msgs": [["a", "x" * 80]]}, "pasa de 70"),
])
def test_elementos_nuevos_se_validan(elemento, esperado):
    def mod(g):
        g["bloques"][0]["elementos"].append(elemento)
        g["bloques"][0]["frases"][0] = "{show " + elemento["id"] + "}" + g["bloques"][0]["frases"][0]
    assert esperado in errores(mod)


def test_ids_de_barras_y_mensajes_existen_para_las_acciones():
    g = json.loads((SKILL.parents[1] / "tests" / "fixtures" / "guion_elementos.json").read_text(encoding="utf-8"))
    spec, rep = compilar(g, LEX, SKILL / "scripts" / "iconos")
    assert rep.errores == []
    assert ["1:caminos", "bad", "g-b0"] in spec["EVENTS"] and ["0:explico", "show", "ch-m1"] in spec["EVENTS"]


def test_pausa_corta_si_lo_ultimo_aparece_temprano():
    g = copy.deepcopy(EJEMPLO)
    g["bloques"][0]["frases"][3] = "Si ese préstamo {show e1}no existe, la multa no entra."
    spec, _ = compilar(g, LEX)
    assert spec["GAPS"][3] == 0.4


@pytest.mark.parametrize("cambio, esperado", [
    ("{send hs de=cli a=cli}", "dos cajas distintas"),
    ("{send hs de=cli a=nadie}", "dos cajas distintas"),
    ("{send hs texto=MUY-LARGO-PARA-UN-PAQUETE}", "más de 12"),
    ("{send f}", "solo flujos"),
])
def test_send_se_valida(cambio, esperado):
    g = json.loads((SKILL.parents[1] / "tests" / "fixtures" / "guion_materia.json").read_text(encoding="utf-8"))
    g["bloques"][0]["frases"][0] = "¿Cómo {show hs}arranca? Con tres " + cambio + "mensajes."
    g["bloques"][0]["elementos"].append({"type": "formula", "id": "f", "tex": "x"})
    assert esperado in " | ".join(compilar(g, LEX)[1].errores)


@pytest.mark.parametrize("tex, esperado", [
    ("", "tex vacío"), ("\\frac{1}{2", "desbalanceadas"), ("\\href{http://x}{y}", "no se permite"),
])
def test_formula_se_valida(tex, esperado):
    def mod(g):
        g["bloques"][0]["elementos"].append({"type": "formula", "id": "fx", "tex": tex})
        g["bloques"][0]["frases"][0] = "{show fx}" + g["bloques"][0]["frases"][0]
    assert esperado in errores(mod)


def test_guion_de_materia_compila_con_titulo_propio():
    g = json.loads((SKILL.parents[1] / "tests" / "fixtures" / "guion_materia.json").read_text(encoding="utf-8"))
    spec, rep = compilar(g, LEX, SKILL / "scripts" / "iconos")
    assert rep.errores == [] and spec["FINAL"]["title"] == "PARA EL EXAMEN"
    assert ["0:mensajes", "send", "hs", {"de": "cli", "a": "srv", "texto": "SYN"}] in spec["EVENTS"]


@pytest.mark.parametrize("elemento, esperado", [
    ({"type": "venn", "id": "v", "sets": ["A"]}, "2 o 3 nombres"),
    ({"type": "venn", "id": "v", "sets": ["A", "B"], "labels": {"123": "x"}}, "no existe"),
    ({"type": "venn", "id": "v", "sets": ["A", "B", "C"], "labels": {"1": "demasiado"}}, "pasa de 6"),
])
def test_venn_se_valida(elemento, esperado):
    def mod(g):
        g["bloques"][0]["elementos"].append(elemento)
        g["bloques"][0]["frases"][0] = "{show v}" + g["bloques"][0]["frases"][0]
    assert esperado in errores(mod)


def test_regiones_del_venn_se_pueden_animar():
    g = copy.deepcopy(EJEMPLO)
    g["bloques"][0]["elementos"].append({"type": "venn", "id": "v", "sets": ["H", "B", "C"]})
    g["bloques"][0]["frases"][0] = "{show v}Primero {show v-123}adentro, {hl v-12}después " + g["bloques"][0]["frases"][0]
    assert compilar(g, LEX)[1].errores == []


def test_cuenta_regresiva_deja_el_silencio_para_pensar():
    g = copy.deepcopy(EJEMPLO)
    g["bloques"][0]["elementos"].append({"type": "countdown", "id": "cd", "seconds": 4})
    g["bloques"][0]["frases"][3] = "¿Y si ese préstamo no existe, la multa {show e1}entra? Pensalo {show cd}vos."
    spec, rep = compilar(g, LEX)
    assert rep.errores == [] and spec["GAPS"][3] == 4.4


def test_cuenta_regresiva_solo_al_final_del_bloque():
    g = copy.deepcopy(EJEMPLO)
    g["bloques"][0]["elementos"].append({"type": "countdown", "id": "cd"})
    g["bloques"][0]["frases"][0] = "{show cd}" + g["bloques"][0]["frases"][0]
    assert "va en la última frase" in " | ".join(compilar(g, LEX)[1].errores)
