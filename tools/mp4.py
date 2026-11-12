#!/usr/bin/env python3
"""Exports a video .html to .mp4 (for the README, or to post it somewhere).

    python3 tools/mp4.py VIDEO.html SALIDA.mp4 [--fps 30] [--alto 1280]

Wrapper around skills/scroll-to-study/scripts/mp4.py, where the logic lives (the skill uses it for
`s2s.py mp4`). Needs playwright and ffmpeg; if they are missing it says how to install them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "scroll-to-study" / "scripts"))

import mp4  # noqa: E402

if __name__ == "__main__":
    sys.exit(mp4.main())
