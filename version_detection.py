"""Schnittstelle zur automatischen Erkennung von Star-Citizen-Installationen und -Builds.

Entdeckt LIVE/PTU/EPTU/HOTFIX/TECH-PREVIEW-Kanäle und liest deren Build-Nummern
aus den logbackups-Logdateien aus.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


__all__: list[str] = ["SCVersion", "detect_versions", "find_build_number"]


KNOWN_CHANNELS: list[str] = [
    "LIVE",
    "PTU",
    "EPTU",
    "HOTFIX",
    "TECH-PREVIEW",
]


@dataclass
class SCVersion:
    """Metadaten eines Star-Citizen-Kanals."""

    channel: str
    root_dir: str
    data_p4k: str
    build_number: str


def detect_versions(base_dir: Optional[str] = None) -> List[SCVersion]:
    """Suche nach allen installierten Star-Citizen-Kanälen.

    Args:
        base_dir: Wenn None, werden die Standardpfade (Linux LUG, Windows) durchsucht.
                  Wenn gesetzt, wird <base_dir>/StarCitizen als Wurzel interpretiert,
                  die die Channel-Unterordner enthält.

    Returns:
        Liste aller SCVersion-Instanzen, sortiert nach Kanalname.
    """
    sc_roots: list[str] = []

    if base_dir is not None:
        sc_roots.append(os.path.join(base_dir, "StarCitizen"))
    else:
        sc_roots.extend(_resolve_default_roots())

    results: list[SCVersion] = []
    for sc_root in sc_roots:
        results.extend(_scan_star_citizen_root(sc_root))

    results.sort(key=lambda v: v.channel)
    return results


def _resolve_default_roots() -> list[str]:
    """Stelle die Standard-Star-Citizen-Wurzelordner für alle Plattformen zusammen."""
    home = Path.home()

    # Linux LUG-Pfad
    linux_paths: list[str] = [
        str(home / "Games" / "star-citizen" / "drive_c" / "Program Files" /
            "Roberts Space Industries" / "StarCitizen"),
    ]

    # Windows-Pfade (für spätere Windows-Nutzung, existieren hier nicht)
    for drive in ("C:", "D:", "E:", "F:"):
        linux_paths.extend([
            f"{drive}\\Program Files\\Roberts Space Industries\\StarCitizen",
            f"{drive}\\Program Files (x86)\\Roberts Space Industries\\StarCitizen",
            f"{drive}\\Games\\Roberts Space Industries\\StarCitizen",
            f"{drive}\\RSI\\StarCitizen",
            f"{drive}\\Roberts Space Industries\\StarCitizen",
        ])

    return linux_paths


def _scan_star_citizen_root(sc_root: str) -> list[SCVersion]:
    """Scanne einen einzelnen StarCitizen-Wurzelordner nach gültigen Kanälen.

    Ein Kanal gilt als gültig, wenn <root>/<channel>/Data.p4k existiert.
    """
    versions: list[SCVersion] = []
    if not os.path.isdir(sc_root):
        return versions

    for known in KNOWN_CHANNELS:
        # Case-insensitive Suche im Verzeichnis
        for entry in os.scandir(sc_root):
            if entry.is_dir(follow_symlinks=False) and entry.name.upper() == known:
                channel_path = entry.path
                data_p4k = os.path.join(channel_path, "Data.p4k")
                if os.path.isfile(data_p4k):
                    build_number = find_build_number(channel_path)
                    versions.append(SCVersion(
                        channel=entry.name,
                        root_dir=channel_path,
                        data_p4k=data_p4k,
                        build_number=build_number,
                    ))
                break

    return versions


def find_build_number(channel_root: str) -> str:
    """Ermittle die Build-Nummer aus den logbackups eines Kanals.

    Durchsucht <channel_root>/logbackups/ nach Dateien, deren Name mit
    ``Game Build`` beginnt und auf ``.log`` endet.  Die Build-Nummer wird
    aus dem Dateinamen per Regex extrahiert; die Datei mit der neuesten
    Modifikationszeit gewinnt.

    Args:
        channel_root: Pfad zum Kanal-Ordner (z. B. ``…/StarCitizen/LIVE``).

    Returns:
        Build-Nummer als String, z. B. ``\"42000\"``.  Leerer String, wenn
        keine passenden Dateien gefunden werden.
    """
    logbackups = os.path.join(channel_root, "logbackups")
    if not os.path.isdir(logbackups):
        return ""

    log_files: list[str] = [
        f for f in os.listdir(logbackups)
        if f.lower().endswith(".log") and f.lower().startswith("game build")
    ]
    if not log_files:
        return ""

    latest = max(log_files, key=lambda f: os.path.getmtime(os.path.join(logbackups, f)))

    # Regex auf den Dateinamen anwenden. Beide echten SC-Formate abdecken:
    #   "Game Build(12572603) 08 Sep 26..."  -> Zahl direkt in runden Klammern
    #   "Game Build 12572603 ..."            -> Zahl nach Leerzeichen
    match = re.search(r"Game Build\s*\(\s*(\d+(?:\.\d+)*)", latest)
    if match:
        return match.group(1)

    match = re.search(r"Game Build\s*(\d+(?:\.\d+)*)", latest)
    if match:
        return match.group(1)

    # Fallback: einfacheres Build-Muster
    match = re.search(r"Build\s*\(?\s*(\d+(?:\.\d+)*)", latest)
    if match:
        return match.group(1)

    return ""
