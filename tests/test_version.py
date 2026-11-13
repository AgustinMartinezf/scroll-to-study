"""La versión de plugin.json (la que usa Claude Code para ver si hay actualización) coincide con el CHANGELOG."""
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_la_version_del_plugin_es_la_primera_del_changelog():
    plugin = json.loads((RAIZ / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    changelog = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    versiones = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    assert versiones, "CHANGELOG.md no tiene encabezados '## [X.Y.Z]'"
    assert plugin["version"] == versiones[0]


def test_marketplace_no_declara_version():
    # Si está en los dos, gana plugin.json sin avisar: la versión vive solo en plugin.json.
    marketplace = json.loads((RAIZ / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    for plugin in marketplace["plugins"]:
        assert "version" not in plugin, plugin["name"]
