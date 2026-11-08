# Componentes de terceros

## Incluidos en este repositorio

| Componente | Dónde | Licencia |
|---|---|---|
| [Phosphor Icons](https://phosphoricons.com) (21 íconos, peso bold) | `skills/scroll-to-study/scripts/iconos/` | MIT, Copyright (c) 2023 Phosphor Icons |
| [Inter](https://rsms.me/inter/) (subconjunto latino, variable) | `skills/scroll-to-study/scripts/fuentes/` | SIL Open Font License 1.1 (`LICENSE-Inter.txt`) |
| [JetBrains Mono](https://www.jetbrains.com/lp/mono/) (subconjunto latino, variable) | `skills/scroll-to-study/scripts/fuentes/` | SIL Open Font License 1.1 (`LICENSE-JetBrainsMono.txt`) |

Los efectos de sonido (`scripts/sfx/`) y la música de fondo (`scripts/sonido.py`) se sintetizan con
código propio (`scripts/sfx/generar.sh`) y tienen la misma licencia que el proyecto.

## Que se descargan al instalar (no están en el repositorio)

| Componente | Licencia | Notas |
|---|---|---|
| [GSAP](https://gsap.com) 3.12.5 | [Standard "No Charge" License](https://gsap.com/standard-license) | Se inserta en cada video generado. |
| [piper-tts](https://github.com/OHF-Voice/piper1-gpl) | GPL-3.0-or-later | Se instala con pip y se ejecuta como proceso aparte. |
| Voz `es_ES-davefx-medium` (Piper), empaquetada por [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models) | Dataset CC0 según su MODEL_CARD | Es un ajuste fino de la voz en inglés `lessac`. Revisá las condiciones de esa voz base antes de un uso comercial. |
| numpy, soundfile, pypdf | BSD / BSD / BSD | Dependencias de Python. |
