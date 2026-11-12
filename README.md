# scroll to study

Turns your study material into 30–60 second vertical videos with voice, to review one topic a day.
It works to **understand a project** (code, report, assignment brief) and to **study a course** for an
exam (notes, slides, exercises): tables, chats, charts, formulas and protocols that
animate right when the voice names them. Videos in English or Spanish. It is a **Claude Code** plugin:
you use it with your own Claude, and everything stays on your computer.

The difference from other "study by scrolling" tools: **every quote is checked by code, and Claude
reviews that the quote supports the statement**. Claude proposes statements with a verbatim quote and
its source (file and line, or PDF page); a script checks that the quote is there and that the names
and numbers in the statement are too, and then Claude reviews, quote by quote, that it actually backs
the statement. Whatever does not pass does not reach the video: in your own project you can approve it
yourself; in a course, it is left out.

## How it works

```
your material ──► inventory of statements ──► checked by code (verbatim quote, source)
                                                   │
          you pick the topics ◄── topics (8–20) ◄──┘
                  │
                  ▼
 script per topic ──► validator ──► voice (Piper) + animation ──► video .html (plays by itself)
 (only sees the checked           (Claude fixes
  statements of its topic)         what it flags)
```

- Claude writes the inventory, the topics and the scripts. The scripts compute everything else:
  font sizes, pauses, pronunciation, and syncing the animation with the voice.
- Each video gets a format that fits its topic: question and answer (with a countdown so you try to
  recall first), myth vs fact, A versus B, step by step, or the story of a decision. You can force one.
- The voice is [Piper](https://github.com/OHF-Voice/piper1-gpl) and runs locally. The time of each
  word comes from the voice model itself, so the animation lands on the word that names it.
- Each video is a single `.html` of about 1 MB with no dependencies: it opens in the browser on your
  computer or phone, offline. The playlist is at `scroll-to-study/videos/index.html`.
- With an exercise sheet and no theory, it does not solve your exercises: it teaches how to recognize
  each type of exercise and the general method and traps, labeled as "general method".

## Guide

A 50-second video made with the tool itself, from this README and the skill's instructions (turn the
sound on):

https://github.com/user-attachments/assets/6f098172-30c9-4070-916c-8e1dbf69b226

The real videos are `.html` files, not `.mp4`: `tools/mp4.py` exported this one so it can be shown
here. What Claude wrote to make it (the statements with their quotes, the topic and the script) is in
[`media/guia/`](media/guia/).

## Install

You need [Claude Code](https://code.claude.com) and Python 3.10 or newer. In Claude Code:

```
/plugin marketplace add AgustinMartinezf/scroll-to-study
/plugin install scroll-to-study@scroll-to-study
```

(From a terminal it is `claude plugin marketplace add AgustinMartinezf/scroll-to-study` and
`claude plugin install scroll-to-study@scroll-to-study`.) To get a newer version later:
`/plugin marketplace update scroll-to-study`.

The first time you use it, Claude installs the Python dependencies (`numpy`, `soundfile`, `piper-tts`,
`onnx`, `pypdf`) and downloads the voice for your language (~65 MB), gsap and KaTeX to
`~/.scroll-to-study` (`S2S_DATOS` changes the folder). That folder stays when the plugin updates.

## Use

Open Claude Code in the folder of your project or your notes and ask something like:

> I want to really understand this project with scroll to study. The report is in docs/report.pdf.

> I have a Networks midterm: make me scroll to study videos from theory.pdf and exercises.pdf.

Claude stops so you decide which topics go in (and, in a project, which doubtful facts are true).
It does the rest by itself.

## What ends up in your folder

```
scroll-to-study/
  corpus.txt          your material, numbered by line (what Claude reads)
  inventario.json     statements with source, quote and state (ok / comprobar / general)
  temas.json          the topics you picked
  t01/ … t20/         guion.json + what the compiler and the voice generate
  videos/index.html   the playlist
  registro.jsonl      when and how many times each stage ran
```

## Known limits

- The English voice (`hfc_male`) was trained on a CC BY-NC-SA dataset: fine for studying, not for
  commercial use. The Spanish voice (`davefx`) has its own terms (see [THIRD_PARTY.md](THIRD_PARTY.md)).
- Formulas are quoted by the text around them: PDF text extraction usually breaks formulas, so the
  formula itself cannot be checked letter by letter against the material.
- Diagrams that are only images in slides cannot be quoted, so they do not make it into the videos.
- "The script only sees its statements" is an instruction to Claude, who has already read the whole
  material; the validator backs it up by flagging names and numbers that are not in the sources.
- Code checks that the quote is in the material and that the statement's names and numbers appear in
  it; that the quote actually *supports* the statement is Claude's own review, not a mechanical check.
  A wrong call there is possible, so in a project you confirm the doubtful ones and in a course they
  are dropped.
- Tested in Chromium. Safari on iPhone needs more testing.

## Development

```
python -m pip install numpy soundfile pypdf pytest
python -m pytest -q tests
```

`tools/mp4.py VIDEO.html OUT.mp4` exports a video to MP4 (needs `playwright` and `ffmpeg`).
`tools/revisar.py VIDEO.html` opens a video in Chromium and checks what the style guide asks for: that
the animation follows the audio, that nothing important falls outside the TikTok/Reels/Shorts safe
zones, and that the picture never stays still for more than a second (needs `playwright`).

The tests use an invented project (`tests/fixtures/biblioteca`) and a silent voice, so they need
neither Piper nor network. The code is in `skills/scroll-to-study/scripts/` (names are in Spanish):

| File | What it does |
|---|---|
| `s2s.py` | The command line Claude uses: instalar, corpus, verificar, temas, pedido, guion, video, videos, estado |
| `fuentes.py` | Numbers the material and checks each statement against its quote |
| `etapas.py` | Modes, languages and formats; builds the request for each script |
| `compile.py` | Validates the script and computes what the model does not decide (layout, pauses, pronunciation) |
| `voice.py` | Voice with Piper and per-word timings |
| `engine.py` + `engine.js` | Builds the animation (GSAP); looks come from `temas/` |
| `reproductor.py` + `sonido.py` | Mixes the audio and outputs a `.html` that plays by itself |

## License

[AGPL-3.0](LICENSE). If you offer a modified version as a service, you must publish its code.
Third-party components and their licenses are in [THIRD_PARTY.md](THIRD_PARTY.md).
