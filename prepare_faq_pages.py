"""Zwei gezielt ausgewählte, öffentliche Markdown-Artikel für MkDocs bereitstellen.

Die Quelldateien in beiden Repositories bleiben unverändert. Diese Kopien
existieren nur während des CI-Builds und werden nicht ins Git übernommen.
Relative Verweise aus den Originaldateien führen zu den Quellen auf GitHub.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
FAQ_DIR = ROOT / "docs" / "FAQ"

# Repository, Original-Pfad, lokale Quelle, temporäres MkDocs-Ziel.
SOURCES = (
    (
        "FoxAir_Control",
        "docs/firmware_overview.md",
        ROOT / "docs" / "firmware_overview.md",
        FAQ_DIR / "firmware-uebersicht.md",
    ),
    (
        "FoxAir_updater",
        "docs/HowTo/PHNIX_UPDATER_ENDANWENDER.md",
        ROOT / ".external" / "FoxAir_updater" / "docs" / "HowTo"
        / "PHNIX_UPDATER_ENDANWENDER.md",
        FAQ_DIR / "foxair-updater-anleitung.md",
    ),
)

MARKDOWN_LINK = re.compile(
    r"(?P<prefix>!?\[[^\]\n]*\]\()(?P<target>[^)\n]+)(?P<suffix>\))"
)
GITHUB_ALERT = re.compile(r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", re.I)
ALERT_LABELS = {
    "NOTE": ("note", "Hinweis"),
    "TIP": ("tip", "Tipp"),
    "IMPORTANT": ("important", "Wichtig"),
    "WARNING": ("warning", "Warnung"),
    "CAUTION": ("danger", "Achtung"),
}


def rewrite_links(markdown: str, repo: str, source_path: str) -> str:
    """Links und Bilder unabhängig vom neuen FAQ-Dateipfad gültig halten."""

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        if (
            not target
            or target.startswith(("#", "/", "//"))
            or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target)
        ):
            return match.group(0)

        path, sep, fragment = target.partition("#")
        if not path:
            return match.group(0)
        resolved = posixpath.normpath(
            posixpath.join(posixpath.dirname(source_path), path)
        )
        if resolved == ".." or resolved.startswith("../"):
            raise ValueError(f"Ungültiger relativer Link in {source_path}: {target}")

        is_image = match.group("prefix").startswith("!")
        base = (
            f"https://raw.githubusercontent.com/dosordie/{repo}/main/"
            if is_image
            else f"https://github.com/dosordie/{repo}/blob/main/"
        )
        url = base + quote(resolved, safe="/%")
        if sep:
            url += "#" + fragment
        return match.group("prefix") + url + match.group("suffix")

    return MARKDOWN_LINK.sub(replace, markdown)


def material_alerts(markdown: str) -> str:
    """GitHub-Alerts als Material-Admonitions anzeigen, ohne Quellen zu ändern."""
    lines = markdown.splitlines()
    output: list[str] = []
    i = 0

    while i < len(lines):
        match = GITHUB_ALERT.match(lines[i])
        if not match:
            output.append(lines[i])
            i += 1
            continue

        kind, label = ALERT_LABELS[match.group(1).upper()]
        output.append(f'!!! {kind} "{label}"')
        i += 1
        while i < len(lines) and lines[i].startswith(">"):
            output.append("    " + re.sub(r"^>\s?", "", lines[i]))
            i += 1
        output.append("")

    result = "\n".join(output)
    return result + ("\n" if markdown.endswith("\n") else "")


def main() -> None:
    for repo, source_path, source, destination in SOURCES:
        if not source.is_file():
            raise FileNotFoundError(
                f"Quelle fehlt: {source} – vor dem Build Repository auschecken"
            )

        markdown = source.read_text(encoding="utf-8")
        markdown = rewrite_links(markdown, repo, source_path)
        markdown = material_alerts(markdown)

        source_url = (
            f"https://github.com/dosordie/{repo}/blob/main/"
            + quote(source_path, safe="/")
        )
        markdown = markdown.rstrip() + (
            "\n\n---\n\n"
            f"*Originaldatei: [Quelle auf GitHub]({source_url}). "
            "Diese FAQ-Seite wird beim Website-Build automatisch übernommen.*\n"
        )

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(markdown, encoding="utf-8")
        print(f"FAQ-Import: {source_path} → {destination.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
