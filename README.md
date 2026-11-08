# scroll to study

Convierte el material de tu proyecto (código, informe, letra del obligatorio) en videos verticales
de 45–60 segundos para preparar la defensa oral. Uno por día, cada uno prepara una pregunta que el
tribunal te puede hacer. Funciona como plugin de **Claude Code**: lo usás con tu propio Claude y todo
queda en tu computadora.

La diferencia con otras herramientas de "estudiar scrolleando": **cada dato del video se verifica
contra tu material**. Claude propone afirmaciones con una cita textual y la fuente (archivo y línea);
un script comprueba que la cita esté ahí y que los nombres y números de la afirmación también. Lo que
no se puede verificar no llega al video sin que vos lo apruebes.

## Cómo funciona

```
tu repo + informe ──► inventario de afirmaciones ──► verificación por código (cita textual, fuente)
                                                          │
            vos elegís los temas ◄── temas (8 a 15) ◄─────┘
                    │
                    ▼
   guion por tema ──► validador ──► voz (Piper) + animación ──► video .html (se reproduce solo)
   (solo ve las afirmaciones        (Claude corrige
    verificadas de su tema)          lo que marca)
```

- Claude escribe el inventario, los temas y los guiones. Los scripts calculan todo lo demás:
  tamaños de letra, pausas, pronunciación, sincronización de la animación con la voz.
- La voz es [Piper](https://github.com/OHF-Voice/piper1-gpl) (voz `davefx`, español) y corre local.
- Cada video es un único `.html` de ~1 MB, sin dependencias: se abre en el navegador de la compu o
  del celular, sin internet. La lista de reproducción queda en `scroll-to-study/videos/index.html`.

## Ejemplo

`ejemplo/la-fk-de-multa.html` es un video generado con la herramienta sobre un proyecto inventado (una biblioteca, en `tests/fixtures/biblioteca`). Bajalo y abrilo en el navegador.

## Instalar

Necesitás [Claude Code](https://code.claude.com) y Python 3.10 o más nuevo.

```
/plugin marketplace add AgustinMartinezf/scroll-to-study
/plugin install scroll-to-study@scroll-to-study
```

La primera vez, Claude instala las dependencias de Python (`numpy`, `soundfile`, `piper-tts`,
`pypdf`) y baja la voz (~65 MB) y gsap a una carpeta de datos (`~/.scroll-to-study`, o la del
plugin si Claude Code la define; `S2S_DATOS` la cambia).

## Usar

Abrí Claude Code en la carpeta de tu proyecto y pedile algo como:

> Preparame la defensa del obligatorio con scroll to study. El informe está en docs/informe.pdf.

Claude va a frenar dos veces para que decidas: qué afirmaciones dudosas son ciertas, y qué temas
entran. El resto lo hace solo.

## Qué queda en tu carpeta

```
scroll-to-study/
  corpus.txt          tu material numerado por línea (lo que lee Claude)
  inventario.json     afirmaciones con fuente, cita y estado (ok / comprobar)
  temas.json          los temas que elegiste
  t01/ … t15/         guion.json + lo que genera el compilador y la voz
  videos/index.html   la lista de reproducción
  registro.jsonl      cuándo y cuántas veces se corrió cada etapa
```

## Límites conocidos

- Pensado para la defensa de un proyecto propio, en español. Para exámenes falta un caso aparte:
  quien estudia no puede validar si un dato es cierto.
- Los tiempos de cada palabra se reparten por sílabas, no se alinean con el audio.
- El aislamiento "el guion solo ve sus afirmaciones" es una instrucción a Claude, que ya leyó todo el
  material; lo refuerza el validador, que marca nombres y números que no están en las fuentes.
- Probado en Chromium. Falta probar más en Safari de iPhone.

## Desarrollo

```
python -m pip install numpy soundfile pypdf pytest
python -m pytest -q tests
```

Los tests usan un proyecto inventado (`tests/fixtures/biblioteca`) y una voz en silencio, así que no
necesitan Piper ni red. El código está en `skills/scroll-to-study/scripts/`:

| Archivo                        | Qué hace                                                                                    |
| ------------------------------ | ------------------------------------------------------------------------------------------- |
| `s2s.py`                       | La línea de comandos que usa Claude: corpus, verificar, temas, pedido, guion, video, videos |
| `fuentes.py`                   | Numera el material y verifica cada afirmación contra su cita                                |
| `compile.py`                   | Valida el guion y calcula lo que el modelo no decide (layout, pausas, pronunciación)        |
| `voice.py`                     | Voz con Piper y tiempos por palabra                                                         |
| `engine.py` + `engine.js`      | Arma la animación (GSAP)                                                                    |
| `reproductor.py` + `sonido.py` | Mezcla el audio y deja un `.html` que se reproduce solo                                     |

## Licencia

[AGPL-3.0](LICENSE). Si ofrecés una versión modificada como servicio, tenés que publicar su código.
Los componentes de terceros y sus licencias están en [THIRD_PARTY.md](THIRD_PARTY.md).
