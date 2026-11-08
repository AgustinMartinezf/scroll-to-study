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
    assert spec["GAPS"] == {3: 0.4, 6: 0.4, 8: 0.4, 11: 0.4}


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


def test_prompt_de_guion_trae_el_ejemplo_actual():
    p = (SKILL / "prompts" / "guion.md").read_text(encoding="utf-8")
    assert json.loads(p[p.index("{", p.index("# Ejemplo completo")):]) == EJEMPLO
    assert "{boom trg" in p
