"""Ausgewählte öffentliche Markdown-Artikel samt Bildern für MkDocs bereitstellen.

Die Quelldateien in beiden Repositories bleiben unverändert. Diese Kopien
existieren nur während des CI-Builds und werden nicht ins Git übernommen.
Relative Verweise aus den Originaldateien führen zu den Quellen auf GitHub.
"""

from __future__ import annotations

import posixpath
import re
import shutil
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
        "docs/HowTo/firmware_backup_lte.md",
        ROOT / ".external" / "FoxAir_updater" / "docs" / "HowTo"
        / "firmware_backup_lte.md",
        FAQ_DIR / "lte-modem-backup.md",
    ),
    (
        "FoxAir_updater",
        "docs/HowTo/firmware_update_windows.md",
        ROOT / ".external" / "FoxAir_updater" / "docs" / "HowTo"
        / "firmware_update_windows.md",
        FAQ_DIR / "firmwareupdate-windows.md",
    ),
    (
        "FoxAir_updater",
        "docs/HowTo/PHNIX_UPDATER_ENDANWENDER.md",
        ROOT / ".external" / "FoxAir_updater" / "docs" / "HowTo"
        / "PHNIX_UPDATER_ENDANWENDER.md",
        FAQ_DIR / "firmwareupdate-linux.md",
    ),
)

# Relative Links zwischen importierten Artikeln bleiben in unserer FAQ.
IMPORTED_PAGES = {
    (repo, source_path): destination.name
    for repo, source_path, _source, destination in SOURCES
}

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
        if not is_image and (repo, resolved) in IMPORTED_PAGES:
            # Beispiel: Windows-Update-Anleitung -> eingebundener LTE-Backup-Artikel.
            url = IMPORTED_PAGES[(repo, resolved)]
        elif is_image:
            # Screenshots werden lokal mit ins GitHub-Pages-Artefakt kopiert.
            # So bleiben sie direkt in der Anleitung sichtbar und müssen
            # beim Seitenaufruf nicht von raw.githubusercontent.com kommen.
            checkout_root = (
                ROOT if repo == "FoxAir_Control" else ROOT / ".external" / repo
            )
            original_image = checkout_root / resolved
            if not original_image.is_file():
                raise FileNotFoundError(
                    f"Screenshot fehlt: {repo}/{resolved} in {source_path}"
                )
            local_image = posixpath.join("assets", "imported", repo, resolved)
            target_image = FAQ_DIR / local_image
            target_image.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_image, target_image)
            url = quote(local_image, safe="/%")
        else:
            url = (
                f"https://github.com/dosordie/{repo}/blob/main/"
                + quote(resolved, safe="/%")
            )
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


def extract_linux_guide(markdown: str) -> str:
    """Nur den Linux-/Raspberry-Pi-Abschnitt aus der Updater-Originalanleitung.

    Scheitert bewusst, falls die Quellüberschrift geändert wird. Damit werden
    später nicht stillschweigend falsche oder leere FAQ-Seiten veröffentlicht.
    """
    match = re.search(
        r"(?ms)^## Linux / Raspberry Pi\s*\n(?P<body>.*?)(?=^## [^#]|\Z)",
        markdown,
    )
    if not match:
        raise ValueError(
            "Linux / Raspberry Pi nicht mehr eindeutig in "
            "PHNIX_UPDATER_ENDANWENDER.md gefunden"
        )
    body = match.group("body").strip()
    if not body or "### Raspberry Pi als Server für die Windows-GUI" not in body:
        raise ValueError("Linux-Abschnitt der Updater-Anleitung ist unvollständig")

    # Aus der ursprünglichen Unterüberschrift eine reguläre H2 der
    # neuen eigenständigen Seite machen (für das rechte Inhaltsverzeichnis).
    body = re.sub(r"(?m)^### (.+)$", r"## \1", body)
    return (
        "# Firmwareupdate unter Linux / Raspberry Pi\n\n"
        "Linux und Raspberry Pi ermöglichen Firmwareupdates auch ohne "
        "Windows-PC. Die folgenden Angaben werden automatisch aus der "
        "Originalanleitung des FoxAir Updaters übernommen.\n\n"
        + body
        + "\n"
    )


def main() -> None:
    for repo, source_path, source, destination in SOURCES:
        if not source.is_file():
            raise FileNotFoundError(
                f"Quelle fehlt: {source} – vor dem Build Repository auschecken"
            )

        markdown = source.read_text(encoding="utf-8")
        if destination.name == "firmwareupdate-linux.md":
            markdown = extract_linux_guide(markdown)
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
