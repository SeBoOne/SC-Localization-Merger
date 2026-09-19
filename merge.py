#!/usr/bin/env python3
"""
Merged die benutzerdefinierten .ini-Dateien in die Basis-global.ini.

Linux-Ersatz fuer merge.ps1 (PowerShell -> nur Windows).
Logik 1:1 uebernommen:
  - Alle Zeilen 'key=value' aus den Mod-Dateien in ein Dict laden (key getrimmt).
  - global.ini Zeile fuer Zeile: wenn der (getrimmte) Key im Dict ist,
    wird der Wert ersetzt, PREFIX (alles bis inkl. '=' inkl. Leerzeichen) bleibt.
  - Leerzeilen und Kommentare bleiben unangetastet.
Ausgabe: ./Output/global.ini

Mod-Dateien (Reihenfolge = Prioritaet, spaetere ueberschreiben):
  components.ini, modified_ships.ini, contracts.ini, ordnance.ini, mining.ini
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

MOD_FILES = [
    "components.ini",
    "modified_ships.ini",
    "contracts.ini",
    "ordnance.ini",
    "mining.ini",
]

# Unterordner der Mod-.ini-Dateien innerhalb des Projektordners.
MOD_INI_DIR = "ini"

KEYVALUE = re.compile(r"^(.*?)=(.*)$")
GLOBAL_LINE = re.compile(r"^(.*?)(=)(.*)$")


def load_replacements(mod_dir: str) -> dict:
    replacements: dict[str, str] = {}
    for fname in MOD_FILES:
        path = os.path.join(mod_dir, fname)
        if not os.path.isfile(path):
            print(f"  (uebersprungen, fehlt: {fname})")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\r\n")
                m = KEYVALUE.match(line)
                if m:
                    key = m.group(1).strip()
                    value = m.group(2)
                    replacements[key] = value
    return replacements


def merge(global_path: str, replacements: dict, out_path: str) -> tuple[int, int]:
    replaced = 0
    lines_out = []
    with open(global_path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            m = GLOBAL_LINE.match(line)
            if not m:
                lines_out.append(line)
                continue
            key = m.group(1).strip()
            if key in replacements:
                # PREFIX beibehalten (alles bis inkl. '='), nur Wert ersetzen
                eq = line.index("=")
                prefix = line[: eq + 1]
                lines_out.append(prefix + replacements[key])
                replaced += 1
            else:
                lines_out.append(line)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    # Ausgabeformat = Format der funktionierenden Star-Citizen-global.ini:
    # CRLF-Zeilenenden (\r\n) + UTF-8 mit BOM. Genau so legen die offiziellen
    # Extraktoren/CIG-Workflows die Datei ab; ein LF/w/o-BOM-Output wird von
    # SC nicht akzeptiert.
    with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("\r\n".join(lines_out) + "\r\n")
    return replaced, len(lines_out)


# ---------------------------------------------------------------------------
# NEU: Mod-ini-Unterordner-Unterstuetzung
# ---------------------------------------------------------------------------


def list_mod_inis(ini_dir: str) -> list[str]:
    """Gibt alle *.ini-Dateien in *ini_dir* zurueck, sortiert alphabetisch."""
    if not os.path.isdir(ini_dir):
        return []
    return sorted(
        fname for fname in os.listdir(ini_dir) if fname.endswith(".ini")
    )


def load_selected_replacements(
    ini_dir: str, selected_files: list[str]
) -> dict[str, str]:
    """
    Laedt Key=Value-Eintraege aus den angegebenen Dateien.
    Reihenfolge = Prioritaet; spaetere Dateien ueberschreiben fruehere.
    Fehlende Dateien werden mit einer print-Warnung uebersprungen.
    """
    replacements: dict[str, str] = {}
    for fname in selected_files:
        path = os.path.join(ini_dir, fname)
        if not os.path.isfile(path):
            print(f"  (Warnung, fehlt: {fname})")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\r\n")
                m = KEYVALUE.match(line)
                if m:
                    key = m.group(1).strip()
                    value = m.group(2)
                    replacements[key] = value
    return replacements


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "global.ini")
    out = os.path.join(HERE, "Output", "global.ini")

    # Wenn das Mod-Unterverzeichnis existiert, Mods von dort laden;
    # andernfalls Fallback auf die bisherigen Root-Mod-Dateien (abwaerts-kompatibel).
    ini_path = os.path.join(HERE, MOD_INI_DIR)
    if os.path.isdir(ini_path):
        all_inis = list_mod_inis(ini_path)
        if all_inis:
            replacements = load_selected_replacements(ini_path, all_inis)
            print(f"Mod-Eintraege geladen (ini/): {len(replacements)}")
        else:
            print("ini/ ist leer, Fallback auf Root-Mod-Dateien.")
            replacements = load_replacements(HERE)
            print(f"Mod-Eintraege geladen: {len(replacements)}")
    else:
        replacements = load_replacements(HERE)
        print(f"Mod-Eintraege geladen: {len(replacements)}")

    replaced, total = merge(base, replacements, out)
    print(f"Zeilen gesamt: {total}, ersetzt: {replaced}")
    print(f"=> geschrieben: {out}")
    return 0


def delete_mod_ini(ini_dir: str, filename: str) -> bool:
    """
    Entfernt eine einzelne Mod-*.ini*-Datei aus *ini_dir*.

    Gibt ``True`` zurueck, wenn die Datei erfolgreich geloescht wurde,
    ``False`` wenn sie nicht vorhanden ist oder nicht mit ``.ini`` endet.
    """
    if not filename.endswith(".ini"):
        return False
    path = os.path.join(ini_dir, filename)
    if not os.path.isfile(path):
        return False
    os.remove(path)
    return True


if __name__ == "__main__":
    raise SystemExit(main())
