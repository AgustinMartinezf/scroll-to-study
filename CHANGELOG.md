# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/AgustinMartinezf/scroll-to-study/releases/tag/v0.1.0
