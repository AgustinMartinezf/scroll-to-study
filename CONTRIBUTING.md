# Contributing

Issues and pull requests are welcome. Only the maintainer merges into `main`; every change goes
through a pull request and has to pass the tests on Linux, Windows and macOS.

## Before you open a pull request

```
python -m pip install numpy soundfile pypdf python-pptx python-docx pytest
python -X warn_default_encoding -W error::EncodingWarning -m pytest -q tests
```

The tests need neither Piper nor network. If you change how videos look or sound, also run
`tools/revisar.py` on a generated video and attach a screenshot to the pull request.

## What to keep in mind

- The central rule: nothing in a video may state something that is not in the material. Changes that
  weaken the checks in `fuentes.py` or `compile.py` will not be merged.
- Everything runs on the user's computer. No uploads, accounts or telemetry.
- Code, commands and JSON keys are in Spanish; docs and prompts are in English. Keep each file in
  the language it already uses.
- One change per pull request, with a short description of what it fixes and how you checked it.

## Releasing

Claude Code and the Claude app decide whether there is an update from the `version` field in
`.claude-plugin/plugin.json`. A change that is merged without raising it does not reach anyone who
already has the plugin installed. The version lives only in `plugin.json`: do not add it to
`marketplace.json` (when it is in both, `plugin.json` wins without a warning).

Versions follow [Semantic Versioning](https://semver.org): raise the **patch** (0.2.0 → 0.2.1) for
fixes and the **minor** (0.2.0 → 0.3.0) for new features.

1. In one pull request, set the new `version` in `.claude-plugin/plugin.json` and add its section to
   [CHANGELOG.md](CHANGELOG.md), moving what was under `[Unreleased]` and updating the links at the
   bottom. `tests/test_version.py` fails if the two do not match.
2. Merge it into `main`.
3. Tag the merge commit on `main` and push the tag:

   ```
   git switch main
   git pull
   git tag -a vX.Y.Z -m "scroll-to-study X.Y.Z"
   git push origin vX.Y.Z
   ```

## Reporting a bug

Open an issue with what you ran, what you expected and what happened. Do not attach your study
material if it is private: a small invented example that shows the problem is enough.
