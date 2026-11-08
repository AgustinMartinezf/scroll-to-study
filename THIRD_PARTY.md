# Third-party components

## Included in this repository

| Component | Where | License |
|---|---|---|
| [Phosphor Icons](https://phosphoricons.com) (22 icons, bold weight) | `skills/scroll-to-study/scripts/iconos/` | MIT, Copyright (c) 2023 Phosphor Icons |
| [Inter](https://rsms.me/inter/) (Latin subset, variable) | `skills/scroll-to-study/scripts/fuentes/` | SIL Open Font License 1.1 (`LICENSE-Inter.txt`) |
| [JetBrains Mono](https://www.jetbrains.com/lp/mono/) (Latin subset, variable) | `skills/scroll-to-study/scripts/fuentes/` | SIL Open Font License 1.1 (`LICENSE-JetBrainsMono.txt`) |

The sound effects (`scripts/sfx/`) and the background music (`scripts/sonido.py`) are synthesized by
this project's own code (`scripts/sfx/generar.sh`) and share the project's license.

## Downloaded at install time (not in the repository)

| Component | License | Notes |
|---|---|---|
| [KaTeX](https://katex.org) 0.16.11 | MIT | Draws formulas; embedded (with its fonts) only in videos that have formulas. |
| [GSAP](https://gsap.com) 3.12.5 | [Standard "No Charge" License](https://gsap.com/standard-license) | Embedded in every generated video. |
| [piper-tts](https://github.com/OHF-Voice/piper1-gpl) | GPL-3.0-or-later | Installed with pip and run as a separate process. |
| Voice `es_ES-davefx-medium` (Piper, Spanish), packaged by [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models) | Dataset CC0 according to its MODEL_CARD | Fine-tuned from the English `lessac` voice. Check the terms of that base voice before any commercial use. |
| Voice `en_US-hfc_male-medium` (Piper, English), packaged by [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models) | Dataset [Hi-Fi-CAPTAIN](https://ast-astrec.nict.go.jp/en/release/hi-fi-captain/), CC BY-NC-SA 4.0 | **Non-commercial.** Videos made with this voice are for personal study, not for selling. |
| numpy, soundfile, pypdf | BSD / BSD / BSD | Python dependencies. |
