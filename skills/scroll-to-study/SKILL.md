---
name: scroll-to-study
description: Turns study material into short vertical videos with voice, to review one topic a day, with every fact checked against the material. Works to understand your own project (repo, report, assignment brief) or to study a course for an exam (notes, slides, exercises). Use it when the person wants to study or review with videos, or asks for a scroll to study inventory, topics or scripts.
---

# Scroll to study: from material to study videos

Together with the person, you will produce 8 to 20 videos of 30–60 s, to review one topic a day.
Each video is a single `.html` file that plays by itself in the browser, with voice.

There are two modes, and the first step is to know which one applies:
- **proyecto** (project): something the person made (an assignment, a work project). They know the
  material and can confirm doubtful facts.
- **materia** (course): they study for an exam with notes, slides or a book. They cannot tell whether
  a fact is true, so whatever cannot be checked against the material does not go into any video.

And two languages for the videos: **es** (Spanish, the default) and **en** (English). Ask which one
they want if it is not obvious from how they talk to you. The material can be in either language.

The central rule: **nothing in a video can state something that is not in the material.** Every fact
goes through code that checks it: you write the JSON files and `s2s.py` checks them. Never accept a
stage without running its check, and never hand-edit what the script computes.

Abbreviations: `S2S` = `python3 ${CLAUDE_SKILL_DIR}/scripts/s2s.py` (on Windows it may be `python`
instead of `python3`). `T` = the working folder: `scroll-to-study/` inside the current folder, unless
the person asks for another one. The prompts are in `${CLAUDE_SKILL_DIR}/prompts/`. Where a prompt
says "write ONLY the JSON", write that JSON to the file given.

Talk to the person in their language. The commands and JSON keys are in Spanish; that is expected.

## 0. Set up (once per computer)

    python3 -m pip install -r ${CLAUDE_SKILL_DIR}/requirements.txt
    S2S instalar --idioma es        # or --idioma en

`instalar` downloads the voice for that language (Piper, about 65 MB), gsap and KaTeX to a data
folder and checks that the voice works. Run it again with the other language if they want videos in
both. If it fails, run `S2S diagnostico`: it prints one line per requirement (Python version, each
package, the voice of each language, gsap, KaTeX), either "ok" or the command that fixes it. Show the
lines that are not "ok" to the person and run the fixes they agree to; do not go on to the video stage
until the required ones are ok (the script stages work without the voice). Playwright and ffmpeg show
up as optional: they are only needed for step 7.

## 1. Material

Ask what they are going to study and where the material is. In project mode: the code (folder or
.zip), the report and the assignment brief or rubric if there is one. In course mode: notes, slides,
worked exercises and, if they exist, the course syllabus or past exams. Then:

    S2S corpus -t T --modo proyecto --idioma en --repo PATH_TO_REPO --doc report.pdf --doc brief.pdf
    S2S corpus -t T --modo materia --idioma es --doc theory.pdf --doc exercises.pdf

Optional: `--estilo cuaderno` (notebook paper, the default) or `--estilo pizarra` (dark board) sets
how every video looks.

If it warns that the material is too large, ask which folders or chapters matter.

## 2. Inventory of statements

Follow `prompts/<modo>/inventario.md` reading all of `T/corpus.txt` (in parts if it is long). Write
`T/inventario.json` as `{"afirmaciones": [{"id","texto","fuente","cita","tipo"}, …]}` and run

    S2S verificar -t T

For each statement in "comprobar", look at the reason: if it says where the quote appears, fix the
source; if the quote is not in the material, find the real verbatim quote or remove the statement.
One round of fixes, then verify again. In project mode, show what is still in "comprobar" to the
person in a short list: if they confirm it is correct, set `"aprobado": true`; if not, remove it.
Never set `aprobado` unless the person says so. In course mode nothing is approved by hand: whatever
cannot be verified is removed (and tell the person how many statements were left out).

If in course mode the material is an exercise sheet without theory, do not solve specific exercises
(the person solves and checks them on their own). Record each type of exercise as a statement from
the material and add the general methods and traps to approach it, as `prompts/materia/inventario.md`
explains. Tell the person those methods do not come from their material and that the videos label
them as "general method".

If the material contradicts itself (for example, a slide's text says the opposite of its figure), do
not pick a version: leave that statement out and tell the person what you saw and where, so they can
check it with their teacher.

## 3. Does the quote back the statement?

The check in step 2 is mechanical: it confirms the quote is in the source and that the names and
numbers of the statement appear in it, but not that the statement actually follows from the quote. A
real quote can back a false statement ("WPA2 usa AES" does not prove "WPA2 usa 3 rondas de AES"). So:

    S2S respaldo -t T

With no `T/respaldo.json` yet, it writes `T/respaldo_pedido.txt` with the statements still in "ok" and
their quotes. Read ONLY that file — do not look at the material again — and for each one decide whether
the quote supports exactly what the statement claims. Write `T/respaldo.json` as
`{"<id>": {"respalda": true|false, "motivo": "<short reason>"}}`, one entry per id and no others. Set
`respalda` to false when the statement adds, contradicts or does not follow from the quote, and give
the `motivo` in those cases. Then run `S2S respaldo -t T` again to apply it: the statements with
`respalda` false move to "comprobar" with that reason.

The verdict is stored in each statement (key `respaldo`, do not edit it) and `respaldo.json` is renamed
to `respaldo_aplicado.json`. Running `verificar` again keeps the verdicts; if you add statements or
change a statement's text or quote, `verificar` says how many are pending and `S2S respaldo -t T` asks
only for those.

Then handle them like the rest of "comprobar". In project mode, show them to the person and only keep
the ones they confirm (`"aprobado": true` leaves a statement in "ok" and is respected here too). In
course mode nothing is approved by hand, so a statement whose quote does not back it does not reach any
video.

## 4. Topics (the person decides)

Follow `prompts/<modo>/temas.md` with the verified inventory, write `T/temas.json`
(`{"temas": [{"id","titulo","pregunta","afirmaciones"}]}`) and run `S2S temas -t T`.
Show them the list (title and question) and ask what to remove, add or reorder, and whether something
they will surely be asked is missing. If it is missing, there may be no statements that back it: say
so instead of making it up. Apply their changes and run `S2S temas` again.

Each video gets a format picked from its statements (pregunta: question and answer with a countdown;
mito: myth vs fact; avsb: A versus B; pasos: step by step; historia: problem → decision). If the
person wants a specific format for a topic, add `"formato": "<name>"` to that topic.

## 5. Scripts, one per topic

For each topic, in order:

1. `S2S pedido -t T --tema t01`. **That output is the only thing you may use as content**: even if
   you read the whole material, do not add names, numbers, reasons or examples that are not there.
   It also says the video language, the format and the closing line.
2. Write the script following `prompts/guion.md` to `T/t01/guion.json`, in the video language. If a
   word will be mispronounced (snake_case, acronyms, words without accents in code), add it to
   `"lexico"`.
3. `S2S guion -t T --tema t01`. Fix everything marked `ARREGLAR` and run it again. Also treat as
   errors the `AVISO` lines about identifiers or numbers that are not in the sources.
   You do not fix `PREGUNTAR`: note it for the person.
   If the script says not to continue, move on to the next topic and tell them at the end.

If there are many topics, do 3 or 4 at a time and ask whether to continue. When done, gather all
`PREGUNTAR` and `[COMPROBAR]` notes and resolve them with the person: they know whether the fact is
true. With their answer, fix the script (or the sources) and validate again.

## 6. Videos

    S2S videos -t T --titulo "<name of the project or course>"

It generates the voice and the animation of every finished script (a few seconds per video) and a
playlist at `T/videos/index.html`. Each video is a single `.html` of about 1 MB that works offline:
it can be opened on the computer or copied to a phone. To redo one after changing its script:
`S2S video -t T --tema t01`. `S2S estado -t T` shows what is missing.
If `video` warns that something appears right before the camera changes scene, move that `{show}`
earlier in the script or add a short sentence after it, validate again and redo that video.

When done, say in two or three lines how many videos were made, which were not and why, and where to
open the playlist. Suggest watching one a day, in order.

## 7. On the phone (optional)

The `.html` videos do not play from the Files app on an iPhone (its preview does not run JavaScript).
If the person wants to watch them on their phone, offer to export them to MP4:

    S2S mp4 -t T                    # every video in T/videos/ -> T/mp4/t01.mp4, …
    S2S mp4 -t T --tema t01         # just one; --alto 1280 (the default) sets the height

It skips the MP4s that are newer than their video, so after redoing a video run it again. It needs
Playwright with its Chromium and ffmpeg; if they are missing it prints how to install them and stops
without touching anything: show those commands to the person and run them only if they agree. The
MP4s go to the phone like any file (cable, AirDrop, or sending them to themselves on WhatsApp) and
play offline in Photos or WhatsApp. It takes about as long as the video lasts, or longer, per video.

## What you do not do
- Do not write spec.json, script.json, gaps.json or timing.json by hand: the scripts generate them.
- Do not change sizes, pauses or pronunciation in the script outside `"lexico"`: the compiler computes them.
- Do not use icons outside the list in `prompts/guion.md` (the validator rejects them).
- Do not upload the material or the videos anywhere: everything stays on the person's computer.
