"""
Plattform-agnostische Pfad-Logik für die SC Localization Merger App.

Alle Pfade basieren auf os.environ / Path.home / pathlib. Damit funktioniert
das Modul sowohl im Entwicklungsbetrieb als auch nach dem Packen mit PyInstaller.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List


APP_NAME = "SC Localization Merger"


def get_data_dir() -> Path:
    """
    Gibt das Datenverzeichnis der App zurück und erzeugt es bei Bedarf.

    Windows:    %USERPROFILE%/Documents/SC Localization Merger
    Linux/mac:  ~/Documents/SC Localization Merger  (falls vorhanden)
                ~/.SCLocalizationMerger               (Fallback, kein Leerzeichen)

    Das Verzeichnis wird bei jedem Aufruf created (mkdir parents exist_ok),
    sodass Aufrufer garantiert auf einen bestehenden Pfad zugreifen können.
    """
    home = Path.home()
    documents = home / "Documents"

    if documents.is_dir():
        data_dir = documents / APP_NAME
    else:
        # Fallback: kein ~/Documents → versteckter Ordner im Home (kein Leerzeichen,
        # besser für Tools wie PyInstaller/Flatpak/Snap, die ~/Documents nicht sehen)
        data_dir = home / ".SCLocalizationMerger"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_ini_dir() -> Path:
    """
    Gibt das INI-Verzeichnis zurück: <data_dir>/ini, erzeugt es bei Bedarf.
    """
    ini_dir = get_data_dir() / "ini"
    ini_dir.mkdir(parents=True, exist_ok=True)
    return ini_dir


def get_output_dir() -> Path:
    """
    Gibt das Output-Verzeichnis zurück: <data_dir>/Output, erzeugt es bei Bedarf.
    """
    output_dir = get_data_dir() / "Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_settings_path() -> Path:
    """
    Gibt den Pfad zur settings.json zurück: <data_dir>/settings.json.
    """
    return get_data_dir() / "settings.json"


def drop_ini_into(ini_dir: str | Path, source_path: str) -> Path:
    """
    Kopiert eine einzelne .ini-Datei in das INI-Zielverzeichnis.

    Parameter
    ---------
    ini_dir : str | Path
        Zielverzeichnis, in das die Datei kopiert wird.
        Wird bei Bedarf erstellt.
    source_path : str
        Pfad zur Quelldatei. Muss auf ``.ini`` enden (case-insensitiv).

    Gibt
    ----
    Path
        Der absolute Pfad der kopierten Datei im Zielverzeichnis.

    Raises
    ------
    ValueError
        Wenn source_path nicht auf ``.ini`` endet.
    """
    source = Path(source_path)
    target_dir = Path(ini_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if not source.suffix.lower() == ".ini":
        raise ValueError(
            f"Quelldatei '{source_path}' hat keine .ini-Endung"
        )

    target = target_dir / source.name
    shutil.copy2(source, target)
    return target


def migrate_project_inis(
    proj_ini_dir: str | Path,
    ini_dir: str | Path | None = None,
) -> list[str]:
    """
    Kopiert alle *.ini-Dateien aus dem Projektordner in das INI-Zielverzeichnis.

    Bereits existierende Dateien im Ziel werden _nicht_ überschrieben.

    Parameter
    ---------
    proj_ini_dir : str | Path
        Quellverzeichnis mit den Projekt-INI-Dateien.
    ini_dir : str | Path | None, optional
        Zielverzeichnis. Wenn None, wird ``get_ini_dir()`` verwendet.

    Gibt
    ----
    list[str]
        Liste der _neu_ kopierten Dateinamen (Basisnamen der Dateien).
    """
    if ini_dir is None:
        ini_dir = get_ini_dir()

    source_dir = Path(proj_ini_dir)
    target_dir = Path(ini_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    migrated: list[str] = []

    for ini_file in sorted(source_dir.iterdir()):
        if ini_file.is_file() and ini_file.suffix.lower() == ".ini":
            target = target_dir / ini_file.name
            if not target.exists():
                shutil.copy2(ini_file, target)
                migrated.append(ini_file.name)

    return migrated
