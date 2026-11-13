# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/AgustinMartinezf/scroll-to-study/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/AgustinMartinezf/scroll-to-study/releases/tag/v0.1.0
