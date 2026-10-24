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


def on_page_markdown(markdown: str, **kwargs) -> str:
    """Nur relative Links korrigieren, die aus dem FAQ-Ordner hinausführen."""

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        path, sep, anchor = target.partition("#")
        resolved = posixpath.normpath(posixpath.join("docs/FAQ", path))
        if not resolved.startswith("docs/"):
            return match.group(0)
        base = _RAW_BASE if resolved.lower().endswith(_IMAGES) else _GITHUB_BASE
        url = base + quote(resolved, safe="/%")
        if sep:
            url += "#" + anchor
        return match.group("prefix") + url + match.group("suffix")

    return _LINK.sub(replace, markdown)
