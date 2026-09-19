#!/usr/bin/env python3
"""
SC Localization Merger — CustomTkinter-GUI.

Zwei-Klick-Workflow:
  1. Kanal + Build auswählen (automatische Erkennung oder eigener Pfad).
  2. Mod-Dateien aus dem App-INI-Ordner an-/abwählen (Drag & Drop / Datei-Dialog).
  3. „Extract & Merge“ → Output/global.ini im App-Datenordner.

Läuft auf Linux, Windows und macOS. Design: dunkles Theme + Drake-Rot
#C8102E als Akzent. CustomTkinter rendert plattformidentisch.

Testbarkeit:
  - MainWindow konstruiert KEIN mainloop automatisch.
  - create_app() ist die Factory für App-Start / Tests.
  - confirm_drop_conflict(name) -> bool ist mock-patchbar.
  - 'import main_gui' erzwingt KEIN Tk-Init (kein Display nötig).
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image  # Reload-Icon rendern

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Backend-Module (unverändert genutzte APIs)
# ---------------------------------------------------------------------------
import app_dirs
import extract_global
import merge
import settings
import version_detection

# ---------------------------------------------------------------------------
# Farben & Design-Konstanten (dunkles Theme, Drake-Rot Akzent)
# ---------------------------------------------------------------------------
ACCENT = "#C8102E"            # Drake-Rot: Überschriften, Buttons, aktive Elemente
ACCENT_HOVER = "#E0243F"      # Helleres Rot für Hover-Zustände
BG_WINDOW = "#17171A"         # Fensterhintergrund (beinahe schwarz)
BG_CARD = "#222226"           # Karten / Listen-Hintergrund (dunkelgrau)
BG_INPUT = "#2C2C31"          # Eingabefelder (Combo, Entry, Checkbox-Hintergrund)
BG_NEUTRAL = "#333338"        # Sekundäre Buttons
BG_NEUTRAL_HOVER = "#3D3D44"
TEXT_MAIN = "#EAEAEA"         # Haupttext
TEXT_DIM = "#9A9A9A"          # Sekundärtext (Hinweise, Output-Pfad)
ERROR_RED = "#FF5C5C"         # Fehler in der Statusleiste
SUCCESS_GREEN = "#2ECC71"     # Erfolg-Haken im Ergebnis-Overlay

CUSTOM_PATH_LABEL = "Eigener Pfad..."  # Label im Versions-Dropdown für eigenen Pfad


def _asset_path(name: str) -> str:
    """Pfad zu einer mitgelieferten Asset-Datei (frozen-sicher).

    Im PyInstaller-Bundle liegen Assets im _MEIPASS-Verzeichnis; im Source-Lauf
    relativ zum Skript unter assets/.
    """
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", name)


# ---------------------------------------------------------------------------
# Hilfsfunktionen (OS-agnostisch)
# ---------------------------------------------------------------------------
def open_in_file_manager(path: str) -> bool:
    """Öffnet einen Ordner im nativen Dateimanager (Win/Linux/macOS).

    Gibt True zurück, falls ein Öffnungs-Befehl gestartet werden konnte.
    Auf Linux wird zuerst der systemweite Dateimanager über das Desktop-Portal
    (gio open) versucht, dann xdg-open, dann ein bekannter Dateimanager.
    """
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # Windows: nativer Explorer
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
            return True

        # Linux: mehrere Strategien, damit es auch auf Wayland/Hyprland öffnet.
        strategies = [
            ["gio", "open", path],
            ["xdg-open", path],
            ["nautilus", path],
            ["dolphin", path],
            ["thunar", path],
        ]
        for cmd in strategies:
            try:
                p = subprocess.Popen(cmd, start_new_session=True)
                # kurz warten, ob der Prozess sofort scheitert (exit != 0)
                try:
                    rc = p.wait(timeout=0.6)
                    if rc != 0:
                        continue  # dieser Öffner schlug fehl → nächster
                except subprocess.TimeoutExpired:
                    return True  # läuft → Erfolg
                return True
            except Exception:
                continue
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Hauptfenster
# ---------------------------------------------------------------------------
class MainWindow(ctk.CTk):
    """Hauptfenster des SC Localization Merger (CustomTkinter).

    Konstruiert das komplette UI. Startet KEIN mainloop — das macht
    create_app() bzw. der __main__-Block. Dadurch ist die Klasse in
    Tests (Xvfb / DISPLAY) direkt instanzierbar.
    """

    def __init__(self, *args, **kwargs):
        # Fensterhintergrund als Default setzen, falls nicht übergeben
        kwargs.setdefault("fg_color", BG_WINDOW)
        super().__init__(*args, **kwargs)

        # Dunkles Theme (muss nach dem Tk-Root gesetzt werden)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Fenstereigenschaften
        self.title("SC Localization Merger")
        self.geometry("660x780")
        self.minsize(520, 520)

        # Schriften (Titel deutlich größer als Normtext)
        self._font_title = ctk.CTkFont(size=30, weight="bold")
        self._font_subtitle = ctk.CTkFont(size=13)
        self._font_section = ctk.CTkFont(size=16, weight="bold")
        self._font_body = ctk.CTkFont(size=14)
        self._font_small = ctk.CTkFont(size=12)
        self._font_button = ctk.CTkFont(size=14, weight="bold")
        # Eigene, groessere Font fuer das Reload-Symbol — sonst wirkt das ⟳-
        # Glyph mit der Button-Font (14) sehr schmal/duenn.
        self._font_reload = ctk.CTkFont(size=22, weight="bold")

        # ---------------------------------------------------------- App-Pfade
        self._ini_dir = str(app_dirs.get_ini_dir())
        self._output_dir = str(app_dirs.get_output_dir())
        self._data_p4k: str | None = None      # aktuell gewähltes Data.p4k
        self._custom_folder: str | None = None  # eigener Channel-Pfad (falls gewählt)

        # Einmalige Migration der Projekt-INIs in den App-Ordner.
        # ACHTUNG: nur aufrufen, wenn der Projekt-ini-Ordner wirklich existiert —
        # im PyInstaller-Frozen-Bundle zeigt __file__ auf /tmp/_MEI... und die
        # Migration würde mit FileNotFoundError crashen.
        proj_ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ini")
        if os.path.isdir(proj_ini):
            app_dirs.migrate_project_inis(proj_ini)

        # ---------------------------------------------------------- Versionen
        self._versions: list = []
        try:
            self._versions = version_detection.detect_versions()
        except Exception:
            self._versions = []  # Erkennung fehlgeschlagen → nur "Eigener Pfad"

        # Label → SCVersion-Karte für das Dropdown
        self._version_map: dict[str, object] = {}
        for v in self._versions:
            # Label-Format: '{channel} — {basisname_des_channel_ordners}'
            base = os.path.basename(os.path.dirname(v.data_p4k))
            self._version_map[f"{v.channel} — {base}"] = v

        # ---------------------------------------------------------- UI bauen
        self._build_title()
        self._build_section_version()
        self._build_section_mods()
        self._build_section_output()
        self._build_status_bar()

        # ---------------------------------------------------------- Settings
        self._settings_path = str(app_dirs.get_settings_path())
        self._settings = settings.load_settings(self._settings_path)
        self._restore_settings()

    # =============================================================== Titel
    def _build_title(self):
        """Große Überschrift + Fan-Kennzeichnung."""
        title = ctk.CTkLabel(
            self, text="SC Localization Merger",
            font=self._font_title, text_color="#FFFFFF",
        )
        title.pack(padx=24, pady=(18, 0), anchor="w")

        subtitle = ctk.CTkLabel(
            self, text="Unofficial fan project",
            font=self._font_subtitle, text_color=TEXT_DIM,
        )
        subtitle.pack(padx=26, pady=(0, 6), anchor="w")

    # =============================================================== Sektion 1
    def _build_section_version(self):
        """Sektion '1. Star Citizen Version': Dropdown + Build-Feld."""
        header = ctk.CTkLabel(
            self, text="1. Star Citizen Version",
            font=self._font_section, text_color=ACCENT, anchor="w",
        )
        header.pack(fill="x", padx=24, pady=(14, 6))

        # Dropdown-Zeile: 'Kanal:' + OptionMenu
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row, text="Kanal:", font=self._font_body, text_color=TEXT_MAIN,
        ).grid(row=0, column=0, padx=(0, 10), pady=8, sticky="w")

        # Werte: erkannte Versionen + 'Eigener Pfad...'
        values = list(self._version_map.keys()) + [CUSTOM_PATH_LABEL]
        self._version_menu = ctk.CTkOptionMenu(
            row, values=values,
            command=self._on_version_changed,
            font=self._font_body,
            fg_color=BG_INPUT, button_color=ACCENT,
            button_hover_color=ACCENT_HOVER, text_color=TEXT_MAIN,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_MAIN,
            dropdown_hover_color=ACCENT,
            height=36, anchor="w",
        )
        self._version_menu.grid(row=0, column=1, sticky="ew", pady=8)
        # Default-Auswahl: erste erkannte Version, sonst 'Eigener Pfad...'
        self._version_menu.set(values[0])

        # Build-Nummer-Zeile: Label + editierbares Entry
        build_row = ctk.CTkFrame(self, fg_color="transparent")
        build_row.pack(fill="x", padx=24, pady=(0, 0))
        build_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            build_row, text="Build:", font=self._font_body,
            text_color=TEXT_MAIN,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")

        self._build_entry = ctk.CTkEntry(
            build_row, font=self._font_body,
            fg_color=BG_INPUT, border_color="#444449", text_color=TEXT_MAIN,
            placeholder_text="Build-Nummer wird automatisch gesetzt",
            height=34,
        )
        self._build_entry.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        self._build_entry.bind("<KeyRelease>", lambda _e: self._save_settings())

    def _on_version_changed(self, value: str):
        """Dropdown-Änderung: Build auslesen, _data_p4k setzen, speichern."""
        if value == CUSTOM_PATH_LABEL:
            # Ordner-Dialog (abgespalten, damit Tests mocken können)
            folder = self.ask_channel_folder()
            if not folder:
                # Abgebrochen → vorherige Auswahl wiederherstellen
                self._revert_version_menu()
                self._set_status("Ordnerauswahl abgebrochen")
                return
            self._custom_folder = folder
            self._data_p4k = os.path.join(folder, "Data.p4k")
            build = ""
            try:
                build = version_detection.find_build_number(folder)
            except Exception:
                build = ""
            self._build_entry.delete(0, "end")
            self._build_entry.insert(0, build)
            self._set_status(f"Ordner: {os.path.basename(folder)}")
        else:
            v = self._version_map.get(value)
            if v:
                self._custom_folder = None
                self._data_p4k = v.data_p4k
                self._build_entry.delete(0, "end")
                self._build_entry.insert(0, v.build_number)
                self._set_status(f"{v.channel} — Build {v.build_number}")
            else:
                self._set_status("Unbekannter Kanal-Eintrag")
        self._save_settings()

    def ask_channel_folder(self) -> str:
        """Öffnet den Ordner-Dialog für einen Channel-Ordner.

        Gibt den gewählten Pfad zurück oder '' bei Abbruch.
        (Abgespaltene Methode — in Tests mocken.)
        """
        return filedialog.askdirectory(
            parent=self, title="Channel-Ordner auswählen"
        ) or ""

    def _revert_version_menu(self):
        """Dropdown auf die zuletzt gültige Auswahl zurücksetzen."""
        prev = self._settings.get("version", "") or ""
        values = list(self._version_map.keys()) + [CUSTOM_PATH_LABEL]
        self._version_menu.set(prev if prev in values else values[0])

    # =============================================================== Sektion 2
    def _build_section_mods(self):
        """Sektion '2. Mod-Auswahl': Header + Reload-Button + Mod-Liste."""
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", padx=24, pady=(16, 6))
        header_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_row, text="2. Mod-Auswahl",
            font=self._font_section, text_color=ACCENT, anchor="w",
        ).grid(row=0, column=0, sticky="w")

        # Kleiner Reload-Button rechts (Bild-Icon) — liest den ini/-Ordner neu ein,
        # ohne den Checkstand der vorhandenen Einträge zu verlieren.
        # Bild statt Unicode-Glyph: ⟳/↻ wird je nach Systemfont duenn gerendert;
        # ein PNG rendert identisch und deutlich sichtbar.
        _reload_path = _asset_path("reload_icon.png")
        with open(_reload_path, "rb") as _f:
            _reload_img = Image.open(_f).copy()
        reload_icon = ctk.CTkImage(
            light_image=_reload_img,
            dark_image=_reload_img,
            size=(24, 24),
        )
        self._reload_btn = ctk.CTkButton(
            header_row, text="", image=reload_icon, width=44, height=34,
            fg_color=BG_CARD, hover_color=BG_NEUTRAL_HOVER,
            command=self.reload_mod_list,
        )
        self._reload_btn.grid(row=0, column=1, sticky="e")

        # Scrollbare Liste der Mod-Dateien (eine Checkbox je .ini)
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=BG_CARD, corner_radius=8,
        )
        self._list_frame.pack(fill="x", padx=24)

        # Checkbox-Variablen je Datei (Name → BooleanVar)
        self._checkboxes: dict[str, ctk.BooleanVar] = {}

        # Dateiopfer-Einladung: 'INI-Datei hinzufügen...' (auch für Drag-Geste)
        self._add_ini_btn = ctk.CTkButton(
            self, text="➕  INI-Datei hinzufügen...",
            font=self._font_body, fg_color=BG_CARD,
            hover_color=BG_NEUTRAL_HOVER, text_color=TEXT_MAIN,
            height=32, command=self.choose_ini_file,
        )
        self._add_ini_btn.pack(fill="x", padx=24, pady=(6, 0))

        # Drag & Drop per Maus-Geste:
        # ButtonPress/B1-Motion/ButtonRelease auf der Listenfläche —
        # eine Drag-Bewegung ruft am Ende den Datei-Dialog auf (Dateiopfer).
        self._drag_start: tuple[int, int] | None = None
        self._drag_active = False
        self._list_frame.bind("<ButtonPress-1>", self._on_drag_press)
        self._list_frame.bind("<B1-Motion>", self._on_drag_motion)
        self._list_frame.bind("<ButtonRelease-1>", self._on_drag_release)

    def _on_drag_press(self, event):
        """Drag-Anfang merken (Maus-Position)."""
        self._drag_start = (event.x, event.y)
        self._drag_active = False

    def _on_drag_motion(self, event):
        """Drag-Erkennung: Bewegung über 8 Pixel zählt als Drag."""
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        if (dx * dx + dy * dy) ** 0.5 > 8:
            self._drag_active = True

    def _on_drag_release(self, _event):
        """Drag-Ende: Datei-Dialog öffnen (Dateiopfer für .ini-Dateien)."""
        active, self._drag_active = self._drag_active, False
        self._drag_start = None
        if active:
            self.choose_ini_file()

    # ---------------------------------------------------------- Mod-Liste
    def _build_mod_list(self, checked_names: set[str] | None = None):
        """Liste aller .ini-Dateien aus dem App-INI-Ordner aufbauen.

        checked_names=None  → alle angehakt (Standard beim Erststart).
        checked_names=set   → gespeicherter Checkstand wiederherstellen.
        """
        # Alte Einträge entfernen
        for child in self._list_frame.winfo_children():
            child.destroy()
        self._checkboxes.clear()

        files = merge.list_mod_inis(self._ini_dir)

        if not files:
            # Hinweis bei leerem Ordner
            ctk.CTkLabel(
                self._list_frame,
                text="Keine .ini-Dateien — ziehe eine hierher oder nutze "
                     "'INI-Datei hinzufügen...'",
                font=self._font_small, text_color=TEXT_DIM,
            ).pack(padx=12, pady=14)
            return

        for fname in files:
            row = ctk.CTkFrame(self._list_frame, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=2)

            # Standard: angehakt, außer gespeichertes Set existiert
            default_checked = (
                fname in checked_names if checked_names is not None else True
            )
            var = ctk.BooleanVar(value=default_checked)
            self._checkboxes[fname] = var

            ctk.CTkCheckBox(
                row, text=fname, variable=var,
                command=lambda name=fname: self._on_checkbox_changed(name),
                checkbox_width=20, checkbox_height=20,
                border_width=2,
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                checkmark_color="#FFFFFF",
                text_color=TEXT_MAIN, font=self._font_body,
            ).pack(side="left", fill="x", expand=True, padx=(6, 4))

            # Löschen-Button: löscht GENAU diese (markierte) Datei
            ctk.CTkButton(
                row, text="🗑", width=32, height=28,
                fg_color=BG_INPUT, hover_color=BG_NEUTRAL_HOVER,
                text_color=TEXT_DIM,
                command=lambda name=fname: self.delete_mod_row(name),
            ).pack(side="right", padx=(0, 4))

            # Kontextmenü (Rechtsklick): 'Löschen' für genau diese Zeile
            menu = tk.Menu(row, tearoff=0)
            menu.add_command(
                label="Löschen",
                command=lambda name=fname: self.delete_mod_row(name),
            )
            row.bind(
                "<Button-3>",
                lambda e, menu=menu: menu.tk_popup(e.x_root, e.y_root),
            )

    def reload_mod_list(self):
        """ini/-Ordner neu einlesen — Checkstand bestehender Einträge bleibt erhalten."""
        checked = {name for name, var in self._checkboxes.items() if var.get()}
        self._build_mod_list(checked_names=checked)
        self._save_settings()
        self._set_status("Mod-Liste neu geladen")

    def _on_checkbox_changed(self, _name: str):
        """Checkbox geändert → Auswahl persistieren."""
        self._save_settings()

    def delete_mod_row(self, filename: str) -> bool:
        """Löscht genau die markierte (selektierte) Datei per merge.delete_mod_ini.

        Ohne Markierung tut nichts (Rückgabe False).
        """
        if not filename:
            self._set_status("Keine Datei markiert — erst anklicken/auswählen")
            return False
        ok = merge.delete_mod_ini(self._ini_dir, filename)
        if not ok:
            self._set_status(f"'{filename}' konnte nicht gelöscht werden", error=True)
            return False
        self.reload_mod_list()
        self._set_status(f"'{filename}' gelöscht")
        return True

    # ---------------------------------------------------------- Drag & Drop / Datei-Dialog
    def choose_ini_file(self):
        """Datei-Dialog: .ini-Datei wählen und in den App-INI-Ordner übernehmen."""
        source = filedialog.askopenfilename(
            parent=self,
            title=".ini-Datei auswählen",
            filetypes=[("INI-Dateien", "*.ini"), ("Alle Dateien", "*.*")],
        )
        if source:
            self.handle_ini_drop(source)

    def handle_ini_drop(self, source_path: str) -> bool:
        """Übernimmt eine .ini-Datei in den App-INI-Ordner (via app_dirs.drop_ini_into).

        Existiert die Datei bereits, wird per confirm_drop_conflict() gefragt;
        bei 'Nein' wird NICHT kopiert.
        """
        if not source_path.lower().endswith(".ini"):
            self._set_status("Nur .ini-Dateien werden übernommen", error=True)
            return False

        name = os.path.basename(source_path)
        target = os.path.join(self._ini_dir, name)

        # Konflikt-Entscheidung (testbare Methode — via mock patchbar)
        if os.path.exists(target):
            if not self.confirm_drop_conflict(name):
                self._set_status("Drop abgebrochen (Datei existiert)")
                return False

        try:
            app_dirs.drop_ini_into(self._ini_dir, source_path)
        except Exception as exc:
            self._set_status(f"Kopieren fehlgeschlagen: {exc}", error=True)
            return False

        self.reload_mod_list()
        self._set_status(f"Datei '{name}' hinzugefügt")
        return True

    def confirm_drop_conflict(self, name: str) -> bool:
        """Fragt nach, ob eine existierende Datei überschrieben werden soll.

        Rückgabe: True = Fortfahren (überschreiben), False = Abbrechen.
        (Testbar: in Tests per mock.patch patchen.)
        """
        return messagebox.askyesno(
            "Datei existiert",
            f"'{name}' existiert bereits im INI-Ordner.\nÜberschreiben?",
            parent=self,
        )

    # =============================================================== Sektion 3
    def _build_section_output(self):
        """Sektion '3. Output & Aktion': Output-Pfad + Aktions-Buttons."""
        header = ctk.CTkLabel(
            self, text="3. Output & Aktion",
            font=self._font_section, text_color=ACCENT, anchor="w",
        )
        header.pack(fill="x", padx=24, pady=(16, 6))

        # Output-Pfad inline anzeigen
        self._output_label = ctk.CTkLabel(
            self, text=f"Output: {self._output_dir}",
            font=self._font_small, text_color=TEXT_DIM,
            anchor="w", justify="left", wraplength=600,
        )
        self._output_label.pack(fill="x", padx=24)

        # Button-Zeile: 'Output-Ordner öffnen' + 'Extract & Merge'
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(8, 0))
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_row, text="Output-Ordner öffnen",
            font=self._font_body, fg_color=BG_CARD,
            hover_color=BG_NEUTRAL_HOVER, text_color=TEXT_MAIN,
            height=40, command=self._on_open_output,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._merge_btn = ctk.CTkButton(
            btn_row, text="Extract & Merge",
            font=self._font_button, fg_color=ACCENT,
            hover_color=ACCENT_HOVER, text_color="#FFFFFF",
            height=40, command=self._on_merge_clicked,
        )
        self._merge_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _on_open_output(self):
        """Öffnet den Output-Ordner im nativen Dateimanager."""
        out_dir = self._output_dir
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        if open_in_file_manager(out_dir):
            self._set_status("Output-Ordner geöffnet")
        else:
            self._set_status(f"Konnte '{out_dir}' nicht öffnen", error=True)

    # =============================================================== Statusleiste
    def _build_status_bar(self):
        """Statusleiste am Boden (Bereit / Arbeitsstatus / Fehler in Rot)."""
        self._status_label = ctk.CTkLabel(
            self, text="Bereit — Kanal wählen",
            font=self._font_small, text_color=TEXT_DIM, anchor="w",
        )
        self._status_label.pack(side="bottom", fill="x", padx=24, pady=(8, 10))

    def _set_status(self, text: str, error: bool = False):
        """Status-Nachricht setzen (rot bei Fehler)."""
        self._status_label.configure(text=text, text_color=ERROR_RED if error else TEXT_DIM)

    # =============================================================== Settings
    def _restore_settings(self):
        """Gespeicherte UI-Zustände wiederherstellen (ohne Dialoge)."""
        version = self._settings.get("version", "")
        path = self._settings.get("path", "")
        selected = self._settings.get("selected", [])

        # Version / Kanal wiederherstellen (set() triggert keinen Command)
        values = list(self._version_map.keys()) + [CUSTOM_PATH_LABEL]
        if version in values:
            self._version_menu.set(version)
        else:
            self._version_menu.set(values[0])
            version = values[0]

        # _data_p4k + Build anhand der wiederhergestellten Auswahl setzen.
        # Fällt zurück auf den zuerst automatisch erkannten Kanal, wenn der
        # gespeicherte "Eigener Pfad" nicht (mehr) existiert — z.B. nach einem
        # Wechsel Windows→Linux, wo ein Windows-Pfad auf Linux tot ist.
        if version == CUSTOM_PATH_LABEL and path and os.path.isdir(path) \
                and os.path.isfile(os.path.join(path, "Data.p4k")):
            self._custom_folder = path
            self._data_p4k = os.path.join(path, "Data.p4k")
            try:
                build = version_detection.find_build_number(path)
            except Exception:
                build = ""
            self._build_entry.insert(0, build)
        else:
            v = self._version_map.get(version)
            if v:
                self._custom_folder = None
                self._data_p4k = v.data_p4k
                self._build_entry.insert(0, v.build_number)
            elif self._version_map:
                # Gespeicherter Verweis ist ungueltig/tot → erste erkannte Version
                fallback = next(iter(self._version_map.values()))
                if version != CUSTOM_PATH_LABEL:
                    self._version_menu.set(
                        f"{fallback.channel} — {fallback.build_number}"
                    )
                self._custom_folder = None
                self._data_p4k = fallback.data_p4k
                self._build_entry.insert(0, fallback.build_number)

        # Gespeicherte Auswahl NUR anwenden, wenn sie nicht leer ist
        # (sonst Standard beim Erststart: ALLE angehakt)
        checked = set(selected) if selected else None
        self._build_mod_list(checked_names=checked)

    def _save_settings(self):
        """Aktuellen UI-Zustand persistieren (selected / version / path)."""
        checked = [name for name, var in self._checkboxes.items() if var.get()]
        data = {
            "selected": checked,
            "version": self._version_menu.get(),
            "path": self._custom_folder or "",
        }
        try:
            settings.save_settings(self._settings_path, data)
        except Exception:
            # Persistenz-Fehler dürfen die GUI nicht crashen lassen
            pass

    # =============================================================== Merge
    def _on_merge_clicked(self):
        """Hauptaktion: global.ini extrahieren + angehakten Mods mergen.

        Der Merge läuft in einem Hintergrund-Thread; ein modales Overlay mit
        Lade-Spinner wird gezeigt und blockiert alle anderen Steuerelemente.
        Am Ende wird der Spinner grün (Haken) bzw. rot (Kreuz); das Overlay
        schließt sich nach 3 Sekunden automatisch.
        """
        # --- (1) Schnelle Vorprüfung synchron, OHNE Overlay/Thread ---
        data_p4k = getattr(self, "_data_p4k", None)
        if not data_p4k or not os.path.isfile(data_p4k):
            messagebox.showwarning(
                "Data.p4k fehlt",
                "Keine Data.p4k gefunden.\nBitte wähle einen gültigen "
                "Kanal im Dropdown oder einen eigenen Channel-Ordner "
                "über 'Eigener Pfad...'.",
                parent=self,
            )
            self._set_status("Fehler: Data.p4k fehlt", error=True)
            return

        # --- (2) Falls schon ein Overlay aktiv ist, nicht neu starten ---
        if getattr(self, "_overlay_open", False):
            return

        self._merge_btn.configure(state="disabled")
        self._work_queue = queue.Queue()
        self._show_overlay(phase="Arbeite...")

        worker = threading.Thread(
            target=self._merge_worker,
            args=(data_p4k,),
            daemon=True,
        )
        worker.start()
        self._poll_merge_worker()

    def _merge_worker(self, data_p4k: str):
        """Führt Extraktion + Merge aus (im Hintergrund-Thread).

        Schiebt Phasen-Statusmeldungen und das Endergebnis in die Queue.
        Greift NICHT direkt auf Widgets zu (CustomTkinter ist nicht
        thread-safe) — der Poller im Main-Thread übernimmt alle UI-Updates.
        """
        q = self._work_queue
        try:
            q.put(("phase", "Extrahiere global.ini..."))
            tmp_base = os.path.join(
                str(app_dirs.get_data_dir()), "tmp_global_base.ini"
            )
            rc = extract_global.extract_to(data_p4k, tmp_base)
            if rc != 0:
                raise RuntimeError(f"Extraktion fehlgeschlagen (Rückgabe {rc})")

            q.put(("phase", "Lade Mod-Einstellungen..."))
            selected_inis = [
                name for name, var in self._checkboxes.items() if var.get()
            ]
            replacements = merge.load_selected_replacements(
                self._ini_dir, selected_inis
            )

            q.put(("phase", "Merge läuft..."))
            out_path = os.path.join(self._output_dir, "global.ini")
            replaced, total = merge.merge(tmp_base, replacements, out_path)

            if os.path.isfile(tmp_base):
                os.remove(tmp_base)

            q.put((
                "result", "ok",
                f"Ersetzte Werte: {replaced}\n"
                f"Zeilen gesamt: {total}\n"
                f"Mod-Dateien: {len(selected_inis)}\n"
                f"Output: {out_path}",
            ))
        except FileNotFoundError as exc:
            q.put(("result", "err", f"Datei nicht gefunden:\n{exc}"))
        except Exception as exc:
            q.put(("result", "err", f"{exc}\n{traceback.format_exc()}"))

    def _poll_merge_worker(self):
        """Main-Thread: liest Queue, aktualisiert Overlay, triggert sich erneut."""
        try:
            while True:
                kind, *rest = self._work_queue.get_nowait()
                if kind == "phase":
                    self._set_overlay_phase(rest[0])
                elif kind == "result":
                    status, text = rest[0], rest[1]
                    self._finish_merge(status, text)
                    return  # fertig, kein Weiter-Pollen
        except queue.Empty:
            pass
        self.after(120, self._poll_merge_worker)

    # ------------------------------------------------------------------
    # Modales Ergebnis-Overlay (im App-Stil)
    # ------------------------------------------------------------------
    def _show_overlay(self, phase: str):
        """Zeigt ein modales Overlay-Fenster mit Lade-Spinner über der App."""
        self._overlay_open = True
        top = ctk.CTkToplevel(self)
        top.title("")
        top.geometry("360x200")
        top.resizable(False, False)
        top.configure(fg_color=BG_CARD)
        try:
            top.transient(self)
            top.grab_set()  # blockiert alle anderen Steuerelemente
            top.attributes("-topmost", True)
        except Exception:
            pass

        # Spinner-Label (Animations-String wird per after() rotiert)
        self._overlay_spinner = ctk.CTkLabel(
            top, text="", font=("Segoe UI", 42),
            text_color=ACCENT, width=90, height=70,
        )
        self._overlay_spinner.pack(pady=(18, 4))
        self._overlay_phase = ctk.CTkLabel(
            top, text=phase, font=self._font_body,
            text_color=TEXT_MAIN, anchor="center",
        )
        self._overlay_phase.pack(pady=(0, 2))

        self._overlay_top = top
        self._overlay_spin_i = 0
        self._overlay_after = None
        self._spin_chars = ["⚙ ", "⟳", "◒", "… ", "●"]
        self._rotate_spinner()

    def _rotate_spinner(self):
        """Rotiert das Ladesymbol (nur solange das Overlay im Arbeitsmodus ist)."""
        if not getattr(self, "_overlay_open", False):
            return
        if getattr(self, "_overlay_done", False):
            return
        frames = ["⟳", "…", "⚙", "◒", "⋯"]
        self._overlay_spinner.configure(
            text=frames[self._overlay_spin_i % len(frames)]
        )
        self._overlay_spin_i += 1
        self._overlay_after = self.after(180, self._rotate_spinner)

    def _set_overlay_phase(self, text: str):
        """Aktualisiert den Phasen-Text des Overlays (Main-Thread)."""
        if not getattr(self, "_overlay_open", False):
            return
        self._overlay_phase.configure(text=text)

    def _finish_merge(self, status: str, text: str):
        """Abschluss: Spinner → Haken/Kreuz, Ergebnistext, nach 3s schließen."""
        if not getattr(self, "_overlay_open", False):
            return
        self._overlay_done = True
        if self._overlay_after:
            self.after_cancel(self._overlay_after)
            self._overlay_after = None

        ok = status == "ok"
        symbol = "✔" if ok else "✘"
        color = SUCCESS_GREEN if ok else ERROR_RED
        self._overlay_spinner.configure(text=symbol, text_color=color)
        self._overlay_phase.configure(
            text=text,
            text_color=TEXT_MAIN,
            justify="left",
            wraplength=320,
        )

        # Statusleiste setzen
        if ok:
            first = text.splitlines()[0] if text else ""
            self._set_status(f"Fertig — {first}")
        else:
            head = text.splitlines()[0] if text.splitlines() else text
            self._set_status(f"Fehler: {head}", error=True)
            self._write_error_log(text)

        self._merge_btn.configure(state="normal")
        self.after(3000, self._close_overlay)

    def _close_overlay(self):
        """Schließt das Overlay und hebt die Sperre auf."""
        if not getattr(self, "_overlay_open", False):
            return
        try:
            self._overlay_top.grab_release()
            self._overlay_top.destroy()
        except Exception:
            pass
        self._overlay_open = False
        self._overlay_done = False

    def _write_error_log(self, msg: str):
        """Schreibt den vollen Traceback in die Logdatei (Diagnose)."""
        try:
            logp = os.path.join(str(app_dirs.get_data_dir()), "error.log")
            with open(logp, "a", encoding="utf-8") as fh:
                fh.write("=" * 60 + "\n")
                fh.write(msg + "\n")
            print(f"[SC-Merger] {msg}", file=sys.stderr)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# App-Start / Factory
# ---------------------------------------------------------------------------
def create_app() -> MainWindow:
    """Factory: erzeugt das Hauptfenster (ohne mainloop).

    Rückgabe: MainWindow-Instanz. Der Aufrufer zeigt das Fenster an und
    führt das Event-Loop aus (siehe __main__-Block) — dadurch bleibt die
    Funktion in Tests (Xvfb/DISPLAY) gut handhabbar.
    """
    return MainWindow()


if __name__ == "__main__":
    app = create_app()
    app.mainloop()
