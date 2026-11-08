import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "scroll-to-study"
sys.path.insert(0, str(SKILL / "scripts"))
