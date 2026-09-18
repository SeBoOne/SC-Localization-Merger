# SC GlobalIni Merger

Ein Python/PySide6-GUI-Tool zum Extrahieren der *Star Citizen* `global.ini` aus einer
`Data.p4k` und zum Einmergen eigener Mod-Ini-Dateien zu einer gemeinsamen
`Output/global.ini`.

![Screenshot](screenshot.png) — Screenshot folgt

## Funktionsweise

- **Mod-Ini-Dateien**: Der Ordner `ini/` enthält die `.ini`-Dateien der einzelnen Mods.
  Jede Datei kann in der GUI einzeln an- oder abgewählt werden.
- **Kanal-Auswahl**: Wähle den Installationskanal (LIVE/PTU/EPTU/… ), aus dem die
  `Data.p4k` extrahiert werden soll. Wird automatisch erkannt; "Eigener Pfad" erlaubt
  eine manuelle Auswahl des Kanal-Ordners.
- **Build-Nummer**: Die Build-Nummer wird automatisch aus dem neuesten
  `Game Build(N).log` im `logbackups/`-Ordner erkannt und kann manuell bearbeitet werden.
- **Output**: Die zusammengeführte Datei wird als `Output/global.ini` geschrieben.

## Systemvoraussetzungen

- **Python 3.11+**
- **PySide6** (GUI-Framework)
- **zstandard** (Kompression)
- **pycryptodome** (AES-Verschlüsselung für p4k-Pakete)
- Windows 10/11 (für die vorkompilierte EXE)

## Unter Linux starten

```bash
# Repository klonen oder Ordner vorbereiten
cd "Star Citizen Localization Merger"

# Virtuelle Umgebung anlegen
python3 -m venv .venv
source .venv/bin/activate

# Abhängigkeiten installieren
pip install PySide6 zstandard pycryptodome

# GUI starten
python main_gui.py
```

## Unter Windows starten

1. Lade die neueste Version aus dem [Releases-Bereich](https://github.com/SeBoOne/sc-globalini-merger/releases) herunter.
2. Entpacke die ZIP-Datei.
3. Führe `SC_GlobalIni_Merger.exe` aus.

Keine Installation von Python nötig — alles ist in der EXE enthalten.

## Lokale Entwicklung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # falls vorhanden
python main_gui.py
```

## Lizenz

Dieses Projekt ist öffentlich zugänglich.
