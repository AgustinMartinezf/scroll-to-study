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
  computer or phone, offline. The playlist is at `scroll-to-study/videos/index.html`. It remembers, in
  that browser only, which days you watched each video, opens the one that is up today and shows your
  streak; "Export progress" copies that history as JSON so you can share it. On a touch screen, swipe
  up or down on a playing video for the next or previous one.
- After each video come 2 or 3 multiple-choice questions on its topic, checked against the same
  statements as the script. Your answers decide when the topic comes back (see [Review](#review)).
- With an exercise sheet and no theory, it does not solve your exercises: it teaches how to recognize
  each type of exercise and the general method and traps, labeled as "general method".

## Review

When a video ends, its questions show up over the player, one at a time. After you pick an answer,
the right one turns green, yours turns red if it was wrong, and the explanation appears. Questions
built on a general method (not from your material) are labeled as such.

The answers set when the topic comes back, with three levels:

- any wrong answer: back to level 0, the topic is due **tomorrow**;
- all right: up one level, due in **3 days** (level 1) or **7 days** (level 2, the top).

"Up today" opens overdue topics first (the most overdue first) and then the ones you have never
watched, in order. When nothing is left it says "Nothing left for today", and you can still watch any
video. Each topic in the list says whether it is due today, up to date or new, and the header shows how
many are due. "Skip questions" leaves the topic as watched without counting as an answer. Topics without
questions are simply watched or not. All of this stays in that browser (or in the phone app), and
"Export progress" includes it.

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
`claude plugin install scroll-to-study@scroll-to-study`.)

### Update

What changed in each version is in [CHANGELOG.md](CHANGELOG.md).

**In Claude Code:**

```
/plugin marketplace update scroll-to-study
/plugin update scroll-to-study@scroll-to-study
/reload-plugins
```

The first command fetches the list of versions, the second installs the new one and the third loads
it without restarting. Automatic updates are off by default for third-party marketplaces like this
one, so the plugin does not update by itself until you run these commands (or turn auto-update on for
this marketplace in `/plugin`).

**In the Claude app:** Plugins → Scroll to study → Update.

The first time you use it, Claude installs the Python dependencies (`numpy`, `soundfile`, `piper-tts`,
`onnx`, `pypdf`, `python-pptx`, `python-docx`) and downloads the voice for your language (~65 MB),
gsap and KaTeX to `~/.scroll-to-study` (`S2S_DATOS` changes the folder). That folder stays when the plugin updates.

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
  t01/ … t20/         guion.json, preguntas.json (practice questions, asked after each video)
                      + what the compiler and the voice generate
  videos/index.html   the playlist
  registro.jsonl      when and how many times each stage ran
```

## On your phone

The `.html` videos do not play from the Files app on an iPhone (its preview does not run JavaScript).
The way to watch them on your phone, offline, is the **scroll to study app**: a page you install on
your home screen, at <https://agustinmartinezf.github.io/scroll-to-study/>. It is only the empty
player; your videos never go there. You import them from a file and they stay stored on your phone.

1. On your computer, ask Claude for the phone package (or run `s2s.py paquete -t scroll-to-study`). It
   writes `scroll-to-study/<title>.s2s.json`, with every video in one file.
2. On your phone, open the link above in Safari (iPhone) or Chrome (Android).
3. Add it to your home screen: on iPhone, Share → Add to Home Screen; on Android, the menu → Install app
   (or Add to Home screen). Open it from there from now on: on iPhone the installed app has its own
   storage, separate from Safari, so videos imported in Safari do not show up in the app.
4. Send yourself the `.s2s.json` (WhatsApp, AirDrop, Drive) and save it to your phone's files.
5. In the app, tap "Import videos" and pick the file. That is all: it opens with airplane mode on,
   asks the questions after each video, keeps your progress (today's topics, review, streak, watched)
   on the phone and can hold one package per course. Packages made by 0.2.0 still import, without
   questions. Importing a package with the same title again replaces its videos and keeps your progress.

The app asks the browser to keep its storage (so the phone does not clear it when it runs low on
space) and shows how much it uses.

**Alternative: MP4.** If you prefer plain video files, ask Claude to export them to MP4 (or run
`s2s.py mp4 -t scroll-to-study`): each video becomes `scroll-to-study/mp4/t01.mp4`, …, which you can
send to your phone and watch offline in Photos or WhatsApp, without progress tracking. It is optional
and needs `playwright` (`pip install playwright`, then `playwright install chromium`) and
[ffmpeg](https://ffmpeg.org); if they are missing, the command tells you how to install them.
`s2s.py diagnostico` lists what is installed and what is missing.

## Known limits

- The English voice (`hfc_male`) was trained on a CC BY-NC-SA dataset: fine for studying, not for
  commercial use. The Spanish voice (`davefx`) has its own terms (see [THIRD_PARTY.md](THIRD_PARTY.md)).
- Formulas are quoted by the text around them: PDF text extraction usually breaks formulas, so the
  formula itself cannot be checked letter by letter against the material.
- The material can be PDFs with text, slides (`.pptx`), Word documents (`.docx`) and text or code
  files. Old `.ppt`/`.doc` files and Google Slides/Docs links are not read: export them first.
- Scanned PDFs have no text to quote. `corpus` warns when more than half of a PDF's pages are empty;
  run it through OCR (for example `ocrmypdf`) or use the digital version. There is no built-in OCR.
- Diagrams that are only images in slides or documents cannot be quoted, so they do not make it into
  the videos. Text inside charts and SmartArt in `.pptx`, and headers, footers and footnotes in
  `.docx`, are not read either.
- "The script only sees its statements" is an instruction to Claude, who has already read the whole
  material; the validator backs it up by flagging names and numbers that are not in the sources.
- Code checks that the quote is in the material and that the statement's names and numbers appear in
  it; that the quote actually *supports* the statement is Claude's own review, not a mechanical check.
  A wrong call there is possible, so in a project you confirm the doubtful ones and in a course they
  are dropped.
- Tested in Chromium. Safari on iPhone (including the phone app) needs more testing.

## Development

```
python -m pip install numpy soundfile pypdf python-pptx python-docx pytest
python -m pytest -q tests
```

`tools/mp4.py VIDEO.html OUT.mp4` exports a single video to MP4 (needs `playwright` and `ffmpeg`; it
calls the same code as `s2s.py mp4`).
`tools/revisar.py VIDEO.html` opens a video in Chromium and checks what the style guide asks for: that
the animation follows the audio, that nothing important falls outside the TikTok/Reels/Shorts safe
zones, and that the picture never stays still for more than a second (needs `playwright`).

The phone app is in `web/`. `tools/sitio.py` builds the published site into `_site/` (it adds
`progreso.js` and `cuestionario.js`, which only live in `skills/scroll-to-study/scripts/`, and versions
the service worker's cache); serve it with `python -m http.server -d _site 8000` to try it. `.github/workflows/pages.yml`
publishes it to GitHub Pages on every push to `main` that touches it. Its tests
(`tests/test_app_web.py`, and `tests/test_lista_navegador.py` for the playlist) need `playwright` with
Chromium and are skipped without them.

The tests use an invented project (`tests/fixtures/biblioteca`) and a silent voice, so they need
neither Piper nor network. The code is in `skills/scroll-to-study/scripts/` (names are in Spanish):

| File | What it does |
|---|---|
| `s2s.py` | The command line Claude uses: instalar, corpus, verificar, respaldo, temas, pedido, guion, preguntas, video, videos, estado, mp4, paquete, diagnostico |
| `fuentes.py` | Numbers the material and checks each statement against its quote |
| `etapas.py` | Modes, languages and formats; builds the request for each script and its questions, and checks the questions |
| `compile.py` | Validates the script and computes what the model does not decide (layout, pauses, pronunciation) |
| `voice.py` | Voice with Piper and per-word timings |
| `engine.py` + `engine.js` | Builds the animation (GSAP); looks come from `temas/` |
| `reproductor.py` + `sonido.py` | Mixes the audio and outputs a `.html` that plays by itself |
| `mp4.py` | Optional: exports a video `.html` to `.mp4` with Playwright and ffmpeg |
| `paquete.py` | Puts every video in one `.s2s.json` for the phone app |
| `progreso.js` + `cuestionario.js` | Progress and review (pure functions) and the questions after each video; shared by the playlist and the phone app |
| `diagnostico.py` | Checks Python, the packages, the voices, gsap and KaTeX, and says how to fix what is missing |

## License

[AGPL-3.0](LICENSE). If you offer a modified version as a service, you must publish its code.
Third-party components and their licenses are in [THIRD_PARTY.md](THIRD_PARTY.md).
