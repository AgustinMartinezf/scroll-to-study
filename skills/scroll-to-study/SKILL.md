---
name: scroll-to-study
description: Convierte el material de un proyecto universitario (repo, informe, letra del obligatorio) en videos cortos verticales para repasar la defensa oral, con cada dato verificado contra el material. Usar cuando la persona quiera preparar la defensa de su proyecto con videos, o pida inventario, temas o guiones de scroll to study.
---

# Scroll to study: del material a los videos de la defensa

Vas a producir, junto con la persona (autora del proyecto), entre 8 y 15 videos de 45–60 s que
preparan la defensa oral. Cada video es un `.html` que se reproduce solo en el navegador, con voz.

La regla central: **nada en un video puede afirmar algo que no esté en el material.** Cada dato pasa
por código que lo verifica: vos escribís los JSON y `s2s.py` los comprueba. Nunca des por buena una
etapa sin correr su comprobación, y nunca edites a mano lo que el script calcula.

Abreviaturas: `S2S` = `python3 ${CLAUDE_SKILL_DIR}/scripts/s2s.py` (en Windows puede ser `python`
en vez de `python3`). `T` = la carpeta de trabajo: `scroll-to-study/` dentro de la carpeta actual,
salvo que la persona pida otra. Los prompts están en `${CLAUDE_SKILL_DIR}/prompts/`. Donde un prompt
diga "respondé solo con el JSON", escribí ese JSON en el archivo indicado.

## 0. Preparar (una vez por computadora)

    python3 -m pip install -r ${CLAUDE_SKILL_DIR}/requirements.txt
    S2S instalar

`instalar` baja la voz (Piper, unos 65 MB) y gsap a una carpeta de datos y prueba que la voz ande.
Si falla, mostrá el error a la persona; no sigas a las etapas de video sin esto (las de guion sí
funcionan sin la voz).

## 1. Material

Preguntá dónde está el código del proyecto (carpeta o .zip), el informe y, si existe, la letra o
rúbrica del obligatorio. Después:

    S2S corpus -t T --repo RUTA_DEL_REPO --doc informe.pdf --doc letra.pdf

Si avisa que el material es muy grande, preguntá qué carpetas importan para la defensa.

## 2. Inventario de afirmaciones

Seguí `prompts/inventario.md` leyendo `T/corpus.txt` completo (por partes si es largo). Escribí
`T/inventario.json` con la forma `{"afirmaciones": [{"id","texto","fuente","cita","tipo"}, …]}` y corré

    S2S verificar -t T

Para cada afirmación en "comprobar", mirá el motivo: si dice dónde aparece la cita, corregí la
fuente; si la cita no está en el material, buscá la cita textual real o sacá la afirmación. Una sola
pasada de correcciones y volvé a verificar. Lo que siga en "comprobar" mostráselo a la persona en una
lista corta: si confirma que es correcto, poné `"aprobado": true` en esa afirmación; si no, sacala.
Nunca pongas `aprobado` sin que la persona lo diga.

## 3. Temas (decide la persona)

Seguí `prompts/temas.md` con el inventario verificado, escribí `T/temas.json`
(`{"temas": [{"id","titulo","pregunta","afirmaciones"}]}`) y corré `S2S temas -t T`.
Mostrale la lista (título y pregunta del tribunal) y preguntale qué sacar, agregar o reordenar, y si
falta algo que el tribunal seguro pregunta. Si falta, puede que no haya afirmaciones que lo
respalden: decíselo en vez de inventarlo. Aplicá sus cambios y volvé a correr `S2S temas`.

## 4. Guiones, uno por tema

Para cada tema, en orden:

1. `S2S pedido -t T --tema t01`. **Esa salida es lo único que podés usar como contenido**: aunque
   hayas leído todo el material, no agregues nombres, números, motivos ni ejemplos que no estén ahí.
2. Escribí el guion siguiendo `prompts/guion.md` en `T/t01/guion.json`. Si una palabra del proyecto
   se pronuncia mal (snake_case, siglas, palabras sin tilde en el código), agregala en `"lexico"`.
3. `S2S guion -t T --tema t01`. Corregí todo lo marcado `ARREGLAR` y volvé a correr. Tratá también
   como error los `AVISO` de identificadores o números que no están en las fuentes.
   `PREGUNTAR` no lo arreglás vos: anotalo para la persona.
   Si el script dice que no sigas, pasá al tema siguiente y contáselo al final.

Si son muchos temas, hacé de a 3 o 4 y preguntá si seguir. Al terminar, juntá todos los
`PREGUNTAR` y `[COMPROBAR]` y resolvelos con la persona: ella sabe si el dato es cierto. Con su
respuesta corregí el guion (o las fuentes) y volvé a validar.

## 5. Videos

    S2S videos -t T --titulo "<nombre del proyecto>"

Genera la voz y la animación de cada guion listo (unos segundos por video) y una lista de
reproducción en `T/videos/index.html`. Cada video es un único `.html` de ~1 MB que funciona sin
internet: se puede abrir en la compu o pasar al celular. Para rehacer uno después de cambiar su
guion: `S2S video -t T --tema t01`. `S2S estado -t T` muestra qué falta.

Al terminar, decí en dos o tres líneas cuántos videos quedaron, cuáles no y por qué, y dónde abrir
la lista. Sugerí ver uno por día, en orden.

## Lo que no hacés
- No escribas spec.json, script.json, gaps.json ni timing.json a mano: los generan los scripts.
- No cambies tamaños, pausas ni pronunciación en el guion fuera de `"lexico"`: lo calcula el compilador.
- No uses íconos fuera de la lista de `prompts/guion.md` (el validador los rechaza).
- No subas el material ni los videos a ningún lado: todo queda en la computadora de la persona.
