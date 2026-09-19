# settings.py — Persistenz-Modul für die Star Citizen Localization Merger GUI
# Speichert angehakte .ini-Dateinamen, SC-Version/Kanal und zuletzt genutzten Pfad.
# Einzige Abhängigkeiten: stdlib (json, os, pathlib, copy). Keine GUI-Importe.

import json
import os
import copy
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Standardwerte
# ---------------------------------------------------------------------------
# selected: Liste angehakter .ini-Dateinamen
# version:  SC-Version/Kanal (z. B. 'live', 'ptu', 'pugc', 'Eigener Pfad')
# path:     Letztgenutzter Pfad (Verzeichnis oder Datei)
DEFAULT_SETTINGS: dict[str, Any] = {
    'selected': [],
    'version': '',
    'path': '',
}


# ---------------------------------------------------------------------------
# load_settings
# ---------------------------------------------------------------------------
def load_settings(path: str | Path) -> dict[str, Any]:
    """Liest JSON von *path* und fuellt fehlende Keys aus DEFAULT_SETTINGS auf.

    - Wenn die Datei fehlt oder das JSON ungültig ist, wird eine Kopie von
      DEFAULT_SETTINGS zurueckgegeben.
    - Kein raise bei fehlendem File oder kaputtem JSON — stets tolerant.
    - 'selected' wird tief gemerged, damit alte Eintraege erhalten bleiben.
    """
    default: dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)

    p = Path(path)

    # Datei existiert nicht → Defaults
    if not p.exists():
        return default

    # Datei existiert, aber kein lesbares JSON → Defaults
    try:
        raw = p.read_text(encoding='utf-8')
        data: dict[str, Any] = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default

    # data ist kein Dict → Defaults
    if not isinstance(data, dict):
        return default

    # --- tiefes Merging ---
    # Starte mit Defaults als Basis
    result: dict[str, Any] = copy.deepcopy(default)

    # Fehleinde Keys aus der gespeicherten Daten ueberschreiben (flach)
    for key in ('selected', 'version', 'path'):
        if key in data:
            if key == 'selected' and isinstance(data[key], list):
                # Tiefes Merging: Reihenfolge erhalten — neue Eintraege nur anhaengen, wenn nicht bereits vorhanden
                existing = list(result.get('selected', []))
                for item in data['selected']:
                    if item not in existing:
                        existing.append(item)
                result['selected'] = existing
            else:
                result[key] = data[key]

    # Alle weiteren Keys, die vielleicht von zukuenftigen Versionen stammen,
    # unverandert uebernehmen (abwaertskompatibel)
    for key, value in data.items():
        if key not in result:
            result[key] = value

    return result


# ---------------------------------------------------------------------------
# save_settings
# ---------------------------------------------------------------------------
def save_settings(path: str | Path, settings: dict[str, Any]) -> None:
    """Schreibt *settings* als JSON nach *path*.

    - Elternordner wird ggf. erstellt (mkdir parents=True, exist_ok=True).
    - settings['path'] wird auf den letzten genutzten Kanal/Pfad gesetzt.
    - UTF-8, ensure_ascii=False, indent=2.
    """
    p = Path(path)

    # Sicherstellen, dass der Elternordner existiert
    p.parent.mkdir(parents=True, exist_ok=True)

    # settings['path'] aktuell halten — hier der zuletzt genutzte Kanal/Pfad
    # (wird vom Aufrufer bereits gesetzt, wird aber zur Sicherheit aktualisiert)
    data = copy.deepcopy(settings)

    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
