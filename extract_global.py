#!/usr/bin/env python3
"""
Extrahiert die englische global.ini aus einer Star-Citizen Data.p4k unter Linux.

Ersatz für SC_GlobalIni_Extractor.exe (Windows-only). Nutzt p4k_reader.py,
einen minimalen pure-Python-Reader für CIGs non-standard ZIP64-P4K-Format.
Nur Standardbibliothek + zstandard noetig.

Aufruf:
    extract_global.py [pfad/zu/Data.p4k] [ausgabe.ini]

Standard-P4K: durchsucht bekannte Installationspfade.
Standard-Ausgabe: ./global.ini  (wie von der Windows-EXE an den Projektordner)
"""
import sys

import p4k_reader

DEFAULT_OUT = "global.ini"

KNOWN_PATHS = [
    "drive_c/Program Files/Roberts Space Industries/StarCitizen/LIVE/Data.p4k",
    "drive_c/Program Files/Roberts Space Industries/StarCitizen/PTU/Data.p4k",
    "drive_c/Program Files/Roberts Space Industries/StarCitizen/EPTU/Data.p4k",
    "StarCitizen/LIVE/Data.p4k",
    "StarCitizen/PTU/Data.p4k",
]

LOCALIZATION_ENTRY = "Data/Localization/english/global.ini"


def find_p4k(candidates: list[str]) -> str:
    """Suche die erste vorhandene Data.p4k in bekannten Pfaden."""
    from pathlib import Path
    home = Path.home()
    searched = []
    for cand in candidates:
        for base in (home, Path.cwd(), Path(__file__).resolve().parent):
            p = base / cand
            searched.append(str(p))
            if p.is_file():
                return str(p)
    # Live-Pfad des Wine-Prefixes gesondert versuchen (case-sensitive)
    live = home / "Games/star-citizen/drive_c/Program Files/Roberts Space Industries/StarCitizen"
    if live.is_dir():
        subs = sorted(
            (d for d in live.iterdir() if d.is_dir()),
            key=lambda d: d.name.lower(),
        )
        for sub in subs:
            candidates.append(str(sub / "Data.p4k"))
    for cand in candidates:
        p = Path(cand)
        if p.is_file():
            return str(p)
    raise FileNotFoundError(
        "Keine Data.p4k gefunden. Gib den Pfad als Argument an:\n"
        "  extract_global.py /pfad/zu/Data.p4k"
    )


# ---------------------------------------------------------------------------
# NEU: Direkt aufrufbare Extraktionsfunktion
# ---------------------------------------------------------------------------


def extract_to(p4k_path: str, out_path: str) -> int:
    """
    Extrahiert global.ini aus der angegebenen Data.p4k nach out_path.

    Args:
        p4k_path: Pfad zur Data.p4k-Datei.
        out_path: Pfad der Ausgabedatei (.ini, UTF-8).

    Returns:
        0 bei Erfolg, 1 bei Fehler (Ausnahme wird nicht geworfen).
    """
    try:
        archive = p4k_reader.P4KFile(p4k_path)
        entry = archive.find(LOCALIZATION_ENTRY)
        if entry is None:
            print(f"[FEHLER] {LOCALIZATION_ENTRY} nicht in {p4k_path} gefunden")
            return 1
        data = archive.read(entry)
        with open(out_path, "wb") as fh:
            fh.write(data)
        print(f"[OK] {len(data)} Bytes nach {out_path}")
        return 0
    except FileNotFoundError:
        print(f"[FEHLER] Data.p4k nicht gefunden: {p4k_path}")
        return 1
    except Exception as exc:
        print(f"[FEHLER] Extraktion fehlgeschlagen: {exc}")
        return 1


def main() -> int:
    args = sys.argv[1:]
    p4k = args[0] if args else find_p4k(KNOWN_PATHS)
    out = args[1] if len(args) > 1 else DEFAULT_OUT

    print(f"[1/2] Parse {p4k}")
    archive = p4k_reader.P4KFile(p4k)
    print(f"      {len(archive.entries)} Eintraege geladen")

    print(f"[2/2] Lese {LOCALIZATION_ENTRY}")
    entry = archive.find(LOCALIZATION_ENTRY)
    if entry is None:
        raise FileNotFoundError(
            f"{LOCALIZATION_ENTRY} nicht in {p4k} gefunden"
        )
    data = archive.read(entry)
    print(f"      {len(data)} Bytes")

    with open(out, "wb") as fh:
        fh.write(data)
    print(f"=> geschrieben: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
