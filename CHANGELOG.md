# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.0] - 2026-11-14

### Added

- `capas`, for layers and levels (the OSI and TCP/IP models, the layers of an operating system, the
  architecture of a project): 2 to 7 stacked bars of the same width, top down, with the name on the
  left and an optional detail on the right ("HTTP, DNS"). `{show id}` shows the frame and the layers
  without a `{show}` of their own; the others appear one by one. `hl`, `good`, `bad` and `strike` work
  on layers.
  - The `atravesar` action moves a token from one layer to another during the sentence, lighting the
    layers in between one by one: encapsulation going down, decapsulation going up.
- `codigo`, for code (Java, Python, C, SQL, JS, Bash or plain text): up to 12 lines of up to 34
  characters, with line numbers and its own syntax highlighting (keywords, strings, comments and
  numbers, in the theme's colors, no external libraries). A line with its own `{show}` appears alone,
  to build the block step by step; `hl` puts a band behind a line, and `good`, `bad` and `strike` work
  on lines too.
  - Code must be copied from the material: `s2s.py guion` checks every non-empty line against
    `corpus.txt` (normalized like the quotes, without indentation) and fails on a line that is not
    there, unless the block is marked `"ejemplo": true`, which the video labels "example".
- Both have seeded entrances: layers cascade top down or bottom up; code appears line by line or is
  typed.

### Changed

- `prompts/guion.md` sends layers and levels to `capas` (with `atravesar`) and code to `codigo`, shown
  line by line with `hl` on the key line, and says that code must be copied from the material or marked
  as an example. The question example situates TCP in the transport layer and the myth example shows the
  `fork()` call as an example snippet.

## [0.7.0] - 2026-11-14

### Changed

- Videos no longer all look the same. The engine decides the animation by itself (the script format and
  the prompts do not change), from a stable seed made of the topic id and the playlist title (FNV-1a and
  mulberry32, never `Math.random`): the same topic gives the same video, byte for byte.
  - Each element type has 3 to 5 entrances: the old pop, slide in from a side or from below, a wipe
    with `clip-path: inset()`, typed letter by letter (chip, big and toast) and a cascade of its parts
    (table rows, list items, the chips of a row, chart bars, flow boxes, tree nodes). Within a video a
    type always enters the same way. Entrances start on the word of their `{show}` and end in the same
    frame as before.
  - Scene transitions: the old trip with a drawn path, a quick cut, a side pan or a fast zoom into the
    next scene; one per video.
  - Each format has its own staging: question scenes in a column with the countdown scene closer; myth
    with the wrong idea on the left and the right one on its right, with a side pan between them; A
    versus B as a split screen (side A on the left, side B on the right) for each type with an even
    number of elements in a block, without shrinking text below 28 px; steps in a column with a fixed
    progress line that advances on every step; story as 2x2 panels visited in order. Scenes in a column
    are far enough apart that the next one stays out of frame.
  - Everything is still animated only with opacity, 2D scale, position, 2D rotation, `strokeDashoffset`
    and `clip-path: inset()`, with no 3D layers (for iOS).

### Added

- `s2s.py variedad -t T` shows, per video, the format, the entrance of each element type, the transition
  and the layout, and how many different combinations the playlist has; it is recorded in
  `registro.jsonl`, and so is the animation of each video that `s2s.py video` makes.
- `s2s.py video` and `videos` keep the playlist title of `T/videos/index.html` when `--titulo` is not
  given (it is part of the seed).

## [0.6.0] - 2026-11-14

### Added

- Two diagrams for content that a table or a flow drew badly (a DNSSEC video showed its key pairs and
  chain of trust as a table):
  - `secuencia`, a sequence diagram for protocols and exchanges between 2 to 4 parties: one column
    and a dotted lifeline per part, and up to 7 messages that appear one by one, each arrow drawn from
    sender to receiver and then its text. A message can be colored (good, bad, warn), go to itself
    (a loop) or get lost (`perdido`: the arrow stops with an X before the target).
  - `arbol`, a tree for hierarchies and chains (up to 10 nodes, 4 levels and 4 children per node),
    laid out top-down with every parent centered over its children and no crossings. A node appears by
    drawing the edge that reaches it first.
  - The `ruta` action walks a tree from the root to a node, lighting each edge and node in turn on
    that word (a chain of trust, a DNS resolution, a search in a binary tree).
  - `hl`, `good`, `bad` and `strike` work on the parts and messages of a sequence and the nodes of a
    tree. Both are SVG inside a card, animated only with opacity, 2D scale, position and
    `strokeDashoffset` (no 3D layers, for iOS), with their colors in the `cuaderno` and `pizarra`
    themes.
  - The compiler checks the limits, parts and parents that do not exist, cycles, repeated ids and
    whether everything fits at a readable size (it computes the columns, rows, positions and font
    size), and warns when a message is shown before the previous one or a node before its parent.

### Changed

- `prompts/guion.md` sends exchanges between parties to `secuencia` (better than a flow with `send`
  when there are round trips or more than 2 messages) and hierarchies and chains to `arbol` with
  `ruta`; `flow` is left for one-direction processes. The question example (TCP handshake) uses a
  sequence diagram and the myth example (`fork()`) a tree of parent and child processes.

## [0.5.0] - 2026-11-14

### Changed

- Videos of any subject no longer look like a database course. A table without an icon used to get the
  database icon (a DNSSEC video showed its KSK/ZSK key pairs as a database table); now a table, list,
  chart or Venn diagram without an icon shows its title alone. A console's default title is "terminal"
  instead of "mysql>".
- There is one example script per format, each from a different subject: a question about a network
  protocol, a myth about operating systems, a math comparison with formulas, programming steps with a
  console and a list, and the library project as a story. `s2s.py pedido` names the example for the
  topic's format and says to copy its shape, not its elements. The examples moved to
  `prompts/ejemplos/<format>.<language>.json`.
- `prompts/guion.md` suggests scenes by the shape of the content (an exchange, a hierarchy, a
  comparison, steps, a number, a formula, a mistake, a definition) and leaves the table for data that
  really has rows and columns. `prompts/preguntas.md` has a second example, from networks.

### Added

- Videos in a playlist vary. `s2s.py pedido` lists the format and element types of the earlier videos
  with a validated script, and `s2s.py guion` warns when a script opens with the same element as the
  previous video or repeats the exact combination of another one. Each validated script's element
  types are recorded in `registro.jsonl`.
- `s2s.py guion` warns when a script uses the database or table icon in a topic whose statements do not
  mention databases; the skill treats that warning as an error.

## [0.4.2] - 2026-11-14

### Fixed

- The phone app now updates without deleting it from the home screen. It looks for a new version when
  it opens and every time it comes back to the foreground, and shows "There is a new version of the
  app" with an "Update" button. It never reloads by itself while a video plays.
- A new version of the app could keep old files for up to 10 minutes after a deploy (GitHub Pages lets
  browsers cache them): the app's offline copy is now always downloaded fresh.
- A package made by a newer plugin than the app said to make the package again; it now says to open the
  app with internet to update it, and starts looking for the update. Packages now say which version of
  scroll-to-study made them ("hecho_con"), and that version shows in both version errors.
- Closing the app, or the playlist on the computer, halfway through a video now offers "Resume from
  m:ss" when it is opened again (within 12 hours). It is no longer recorded as a cut: only an
  unannounced close (iOS out of memory) is.

### Added

- The app shows its version, small, at the bottom.

## [0.4.1] - 2026-11-14

### Fixed

- On iPhone, the installed app closed and reloaded itself 10 to 20 seconds into a video. The
  animations created a GPU layer for every element that moved, on top of the large scaled scene, until
  iOS ran out of memory; videos now use only 2D transforms.
- On iPhone, the videos' sound only played with silent mode off. The app and the playlist now ask iOS
  for the "playback" audio session themselves (asking only from inside the video was not enough) and,
  on the first tap, start a silent audio loop so the sound plays in silent mode on older iOS versions too.
- When the whole app reloads mid-video, the cut is now recorded in "cortes" (it stayed empty, because
  only reloads of the video's page were detected), and the app opens that video paused where it was,
  with "Resume from m:ss". It does not play on its own.
- Videos made by an earlier version keep their old player: remake them with
  `s2s.py videos --todo -t scroll-to-study` (and the phone package with `s2s.py paquete`) to get these
  fixes.

## [0.4.0] - 2026-11-13

### Added

- Seeking inside the video, in the playlist and in the phone app: drag the progress bar (it looks thin
  but is easy to grab, and shows the frame under your finger while you drag), double tap the left or
  right third of the video for -5 s / +5 s, or use the left and right arrow keys and space on a
  computer. A single tap still pauses. Seeking before the first tap plays from there.
- "Full screen" opens a feed: the video fills the screen, swipe up for the next one and down for the
  previous one, and the X (or a swipe down from the top edge) goes back to the list. On a computer,
  the up and down arrows or the mouse wheel change video and Esc leaves. The questions show there too.
- "Export progress" includes "cortes": a log, kept only in that browser, of the times a video's page
  reloaded by itself mid-video (date, video, second and browser), to diagnose it.

### Changed

- The playlist no longer changes video when you swipe on the player: the page scrolls normally to the
  list, and swiping between videos is in the full screen feed.
- A video counts as watched, and its questions show, only if at least 70 % of it actually played. If
  not, it stays at the end with "Watch again".
- Videos made by an earlier version keep their old player: remake them with
  `s2s.py videos --todo -t scroll-to-study` (and the phone package with `s2s.py paquete`) to get the new
  controls and the fix below.

### Fixed

- On iPhone, videos stopped halfway and started again from the beginning. The likely cause is the
  blur animated on every camera move between scenes, which makes iOS reserve huge layers and drop the
  video's page; videos no longer animate any blur (the camera move fades instead), and if the page
  still reloads, the video resumes where it was instead of at 0.

## [0.3.0] - 2026-11-13

### Added

- The practice questions are shown after each video, in the playlist and in the phone app: one at a
  time, with the right answer in green, a wrong one in red and the explanation. Questions built on a
  general method are labeled. Only questions validated without errors, and not edited since, are
  shown; `s2s.py videos` and `s2s.py paquete` warn about the topics that go without them.
- Spaced review: a wrong answer brings the topic back tomorrow, all right moves it up a level (back in
  3 days, then 7). "Up today" opens overdue topics first and then new ones, and says "Nothing left for
  today" when there is nothing due. Each topic in the list shows whether it is due today, up to date or
  new, and the header shows how many are due. "Skip questions" leaves the topic as watched.
- "Export progress" includes the review history.

### Changed

- Phone packages are now version 2 (they carry the questions). The app still imports version 1
  packages, without questions.
- Saved progress moves to version 3 (adds the review). Progress from 0.2.0 is migrated on load.
- When every topic is watched and none is due, "Up today" no longer reopens the one watched longest
  ago: it says there is nothing left for today.

## [0.2.0] - 2026-11-13

### Added

- `s2s.py respaldo`: Claude reviews, quote by quote, that each quote actually backs its statement.
  Statements it does not back move to "comprobar" with the reason, and the verdicts are kept when
  `verificar` runs again (#2).
- Study material can now be slides (`.pptx`, cited slide by slide, speaker notes included) and Word
  documents (`.docx`, numbered by paragraph, tables included) (#4).
- `s2s.py corpus` warns when more than half of a PDF's pages have no text, as in a scanned PDF (#4).
- `s2s.py mp4` exports the videos to MP4 to watch them offline in Photos or WhatsApp; it needs
  Playwright and ffmpeg and says how to install them when they are missing (#5).
- `s2s.py diagnostico` lists Python, each package, the voices, gsap and KaTeX, Playwright and ffmpeg,
  and gives the command that fixes whatever is missing (#5).
- `s2s.py preguntas`: practice questions for each topic, checked against that topic's verified
  statements. `s2s.py estado` shows which topics have them. They are not shown in the videos yet (#6).
- The playlist tracks progress per day: it opens the topic that is up today, shows the streak,
  exports the history as JSON and, on touch screens, changes video with a vertical swipe (#7).
- `s2s.py paquete` puts every video in one `.s2s.json` file (#8).
- An installable offline phone app, at <https://agustinmartinezf.github.io/scroll-to-study/>, that
  plays imported `.s2s.json` packages and keeps progress on the phone (#8).

### Changed

- The playlist's "Start the day over" is replaced by "Clear progress". Progress saved by 0.1.0 is
  migrated on load (#7).
- Exporting to MP4 (`tools/mp4.py`, now a wrapper around `s2s.py mp4`) is about 6 times faster (#5).

### Fixed

- Videos played without sound on iPhone when the phone was in silent mode (#3).

## [0.1.0] - 2026-11-10

### Added

- First public version: a Claude Code plugin that turns study material into 30–60 second vertical
  videos with voice, in English or Spanish, for understanding a project or studying a course.
- Statements with a verbatim quote and its source, checked by code against the material.
- Topics, scripts per topic with a validator, local voice with Piper, and one self-contained `.html`
  per video plus a playlist.

[Unreleased]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/AgustinMartinezf/scroll-to-study/releases/tag/v0.1.0
