"""Verweise aus docs/FAQ auf andere öffentliche Repo-Dokumente auflösen.

Diese Korrektur passiert nur beim MkDocs-Build. Die bestehenden FAQ-Markdown-
Dateien und ihre GitHub-Links bleiben vollständig unverändert.
"""

from __future__ import annotations

import posixpath
import re
from urllib.parse import quote

_GITHUB_BASE = "https://github.com/dosordie/FoxAir_Control/blob/main/"
_RAW_BASE = "https://raw.githubusercontent.com/dosordie/FoxAir_Control/main/"
_LINK = re.compile(r"(?P<prefix>!?\[[^\]]*\]\()(?P<target>\.\./[^)]+)(?P<suffix>\))")
_IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
_GITHUB_ONLY = re.compile(
    r"<!-- github-only:start -->.*?<!-- github-only:end -->\n*", re.DOTALL
)

# Beim Website-Build die GitHub-Quelldokumente intern verlinken.
_UPDATER_FAQ_LINKS = {
    "https://github.com/dosordie/FoxAir_updater/blob/main/docs/HowTo/firmware_backup_lte.md": "lte-modem-backup.md",
    "https://github.com/dosordie/FoxAir_updater/blob/main/docs/HowTo/firmware_update_windows.md": "firmwareupdate-windows.md",
    "https://github.com/dosordie/FoxAir_updater/blob/main/docs/HowTo/PHNIX_UPDATER_ENDANWENDER.md#linux--raspberry-pi": "firmwareupdate-linux.md",
}


def on_page_markdown(markdown: str, **kwargs) -> str:
    """Nur relative Links korrigieren, die aus dem FAQ-Ordner hinausführen."""

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        path, sep, anchor = target.partition("#")
        resolved = posixpath.normpath(posixpath.join("docs/FAQ", path))
        # Auf GitHub bleibt der Original-Link; auf Pages führt er zur FAQ-Seite.
        if resolved == "docs/firmware_overview.md":
            suffix = "#" + anchor if sep else ""
            return match.group("prefix") + "firmware-uebersicht.md" + suffix + match.group("suffix")
        if not resolved.startswith("docs/"):
            return match.group(0)
        base = _RAW_BASE if resolved.lower().endswith(_IMAGES) else _GITHUB_BASE
        url = base + quote(resolved, safe="/%")
        if sep:
            url += "#" + anchor
        return match.group("prefix") + url + match.group("suffix")

    # Hinweise, die nur in der GitHub-Markdownansicht erscheinen sollen,
    # beim Bau der öffentlichen FAQ entfernen (ohne die Quelldatei zu ändern).
    markdown = _GITHUB_ONLY.sub("", markdown)
    # Nur reguläre FAQ-Quelldateien umleiten; Quellenangaben von importierten
    # Artikeln müssen weiterhin auf die Originaldateien bei GitHub verweisen.
    page = kwargs.get("page")
    src_uri = getattr(getattr(page, "file", None), "src_uri", "")
    if src_uri in {"FAQ.md", "firmware.md"}:
        for github_url, faq_target in _UPDATER_FAQ_LINKS.items():
            markdown = markdown.replace(f"]({github_url})", f"]({faq_target})")
    return _LINK.sub(replace, markdown)
