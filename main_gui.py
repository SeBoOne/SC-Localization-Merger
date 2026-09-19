#!/usr/bin/env python3
"""
SC Localization Merger — PySide6 GUI.

Zwei-Klick-Workflow:
  1. Kanal + Build auswählen (automatische Erkennung oder eigener Pfad).
  2. Mod-Dateien aus dem App-INI-Ordner an-/abwählen.
  3. „Extract & Merge" → Output/global.ini im App-Datenordner.

Läuft auf Linux und Windows. Headless-fähig (QT_QPA_PLATFORM=offscreen).
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QAction
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# QApplication: nur beim eigentlichen Start instantiiert (Import ohne exec)
# ---------------------------------------------------------------------------

_QApp = None


def _ensure_qapp() -> "QApplication":
    """Lazy QApplication-Erzeugung. Nur nötig beim Show/Exec."""
    global _QApp
    if _QApp is None:
        _QApp = QApplication.instance()
        if _QApp is None:
            _QApp = QApplication(sys.argv)
    return _QApp


# ---------------------------------------------------------------------------
# Importe der Nachbarmodule (defensiv, falls noch nicht installiert)
# ---------------------------------------------------------------------------

import extract_global
import merge

try:
    import app_dirs
except ImportError:
    app_dirs = None

try:
    import settings
except ImportError:
    settings = None

try:
    import version_detection
except ImportError:
    version_detection = None

# ---------------------------------------------------------------------------
# QSS — dunkles Theme + Drake-Rot #C8102E Akzent
# ---------------------------------------------------------------------------

_QSS = """
/* --------------------------------------------------------------- Hauptfenster */
QMainWindow {
    background-color: #1e1e1e;
}

/* --------------------------------------------------------------- Statusbar */
QStatusBar {
    background-color: #1e1e1e;
    color: #cccccc;
    border-top: 1px solid #333333;
}
QStatusBar QLabel {
    color: #aaaaaa;
    font-size: 11px;
}

/* --------------------------------------------------------------- QGroupBox */
QGroupBox {
    background-color: #252526;
    border: 1px solid #333333;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #C8102E;
    font-size: 12px;
    font-weight: bold;
}

/* --------------------------------------------------------------- QComboBox */
QComboBox {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 5px 10px;
    min-height: 28px;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #e0e0e0;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e0e0e0;
    selection-background-color: #C8102E;
    selection-color: #ffffff;
    border: 1px solid #444444;
    outline: none;
}

/* --------------------------------------------------------------- QLineEdit */
QLineEdit {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 5px 10px;
}
QLineEdit:focus {
    border: 1px solid #C8102E;
}

/* --------------------------------------------------------------- QListWidget */
QListWidget {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 4px;
}
QListWidget::item {
    padding: 4px 8px;
    border-radius: 2px;
}
QListWidget::item:selected {
    background-color: #C8102E;
    color: #ffffff;
}
QListWidget::item:hover:!selected {
    background-color: #3a3a3a;
}

/* Drop-Highlight: über Qt-Eigenschaft [draggable] gesteuert */
QListWidget[draggable="true"] {
    border: 2px solid #C8102E;
}

/* --------------------------------------------------------------- Checkbox */
QCheckBox {
    color: #e0e0e0;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #555555;
    border-radius: 3px;
    background-color: #2d2d2d;
}
QCheckBox::indicator:checked {
    background-color: #C8102E;
    border-color: #C8102E;
}
QCheckBox::indicator:hover {
    border-color: #ff6666;
}

/* --------------------------------------------------------------- QPushButton */
QPushButton {
    background-color: #C8102E;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #d93044;
}
QPushButton:pressed {
    background-color: #a80d24;
}
QPushButton:disabled {
    background-color: #555555;
    color: #888888;
}

/* Sekundär-/Neutral-Button (z.B. "Output-Ordner öffnen") */
QPushButton:not(#primary_btn):not(#reload_btn) {
    background-color: #333333;
    color: #e0e0e0;
    border: 1px solid #4a4a4a;
    font-weight: normal;
}
QPushButton:not(#primary_btn):not(#reload_btn):hover {
    background-color: #3d3d3d;
    border-color: #C8102E;
}
QPushButton:not(#primary_btn):not(#reload_btn):pressed {
    background-color: #2a2a2a;
}

/* Kleiner Reload-Button (runde Form) */
QPushButton#reload_btn {
    background-color: #333333;
    color: #C8102E;
    border: 1px solid #4a4a4a;
    border-radius: 13px;
    font-size: 15px;
    font-weight: bold;
    padding: 0;
}
QPushButton#reload_btn:hover {
    background-color: #3d3d3d;
    border-color: #C8102E;
}

/* --------------------------------------------------------------- QLabel */
QLabel {
    color: #e0e0e0;
}
QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
    letter-spacing: 0.5px;
}
QLabel#section {
    font-size: 13px;
    font-weight: bold;
    color: #C8102E;
    padding-top: 8px;
    border-bottom: 1px solid #333333;
    padding-bottom: 4px;
}
QLabel#output_path {
    color: #9a9a9a;
    font-family: monospace;
    font-size: 11px;
    background-color: #232323;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px 8px;
}
"""


class MainWindow(QMainWindow):
    """Hauptfenster des SC Localization Merger."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SC Localization Merger")
        self.resize(620, 560)
        self.setMinimumSize(480, 400)

        self.apply_qss()

        assert app_dirs is not None, "app_dirs-Modul ist nicht verfügbar"

        # App-Datenverzeichnisse statt Projektordner
        self._ini_dir = str(app_dirs.get_ini_dir())
        self._output_dir = str(app_dirs.get_output_dir())

        # Projekt-ini-Ordner für Migration (nur beim ersten Start).
        # Im PyInstaller-Frozen-Bundle existiert kein Projekt-ini — dann überspringen,
        # sonst crasht die Migration mit FileNotFoundError (__file__ zeigt auf /tmp/_MEI...).
        proj_ini = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "ini"
        )
        if app_dirs is not None and os.path.isdir(proj_ini):
            app_dirs.migrate_project_inis(proj_ini)

        # Prüfen, ob App-INI-Ordner leer ist → Projekt als Lese-Fallback
        # (nur sinnvoll im Source-Lauf, wo ein Projekt-ini existieren kann).
        self._fallback_dir = None
        if os.path.isdir(proj_ini) and not os.listdir(self._ini_dir):
            self._fallback_dir = proj_ini

        # Version-Erkennung
        self._versions: list = []
        if version_detection is not None:
            try:
                self._versions = version_detection.detect_versions()
            except Exception:
                self._versions = []

        # Widgets bauen
        self._combo_box = self._build_combo()
        self._build_edit = self._build_build_line()
        self._list = self._build_list()
        self._merge_btn = self._build_merge_button()
        self._open_output_btn = self._build_open_output_button()
        self._reload_btn = self._build_reload_button()
        self._output_path_label = QLabel("")
        self._output_path_label.setObjectName("output_path")
        self._output_path_label.setWordWrap(True)
        self._status_bar = self._build_status_bar()

        # Mod-Liste einmalig befüllen (sonst bleibt sie leer, bis DnD/Refresh greift)
        self._load_list()

        # Layout
        main_layout = self._build_layout()
        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Signale verbinden
        self._connect_signals()

        # Settings laden und UI vorbelegen
        if settings is not None:
            self._settings_path = str(app_dirs.get_settings_path())
            self._load_settings()
            self._restore_settings()

    # =============================================================== QSS

    def apply_qss(self):
        """QSS-Stylesheet auf das gesamte Fenster anwenden."""
        self.setStyleSheet(_QSS)

    # =============================================================== Builder

    def _build_combo(self):
        """QComboBox für die Versionsauswahl."""
        combobox = self._make_combobox()

        self._version_map: dict[str, object] = {}
        for v in self._versions:
            base = os.path.basename(os.path.dirname(v.data_p4k))
            label = f"{v.channel} — {base}"
            self._version_map[label] = v

        combobox.addItems(list(self._version_map.keys()) + ["Eigener Pfad..."])
        if self._versions:
            combobox.setCurrentIndex(0)

        return combobox

    def _build_build_line(self):
        """QLineEdit für die Build-Nummer."""
        edit = self._make_lineedit()
        edit.setPlaceholderText("Build-Nummer wird automatisch gesetzt")
        return edit

    def _build_list(self):
        """QListWidget mit CheckBoxes für Mod-Dateien."""
        widget = QListWidget()
        widget.setMinimumHeight(200)
        widget.setAcceptDrops(True)
        widget.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        widget.setProperty("draggable", False)

        self._delete_action = QAction("Löschen", self)
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        widget.addAction(self._delete_action)
        self._delete_action.triggered.connect(self._on_delete_selected)

        widget.dragEnterEvent = self._on_drag_enter
        widget.dragLeaveEvent = self._on_drag_leave
        widget.dropEvent = self._on_drop

        return widget

    def _build_merge_button(self):
        """QPushButton „Extract & Merge"."""
        btn = QPushButton("Extract & Merge")
        btn.setMinimumHeight(40)
        btn.setMinimumWidth(220)
        btn.setObjectName("primary_btn")
        return btn

    def _build_open_output_button(self):
        """QPushButton „Output-Ordner öffnen"."""
        btn = QPushButton("Output-Ordner öffnen")
        btn.setMinimumHeight(36)
        btn.setMinimumWidth(200)
        btn.setToolTip(
            "Öffnet den Ordner, in dem die gemergte global.ini "
            "abgelegt wird (App-Datenordner/Output)."
        )
        return btn

    def _build_reload_button(self):
        """Kleiner Reload-Button über der Mod-Liste (Neu einlesen des ini/-Ordners)."""
        btn = QPushButton("⟳")
        btn.setFixedSize(30, 26)
        btn.setToolTip(
            "Mod-Liste neu laden — prüft den ini/-Ordner auf neue/entfernte Dateien"
        )
        btn.setObjectName("reload_btn")
        return btn

    def _on_reload_clicked(self):
        """Mods neu aus dem ini/-Ordner einlesen (Checkstand bleibt erhalten)."""
        self._list.blockSignals(True)
        self._refresh_list()
        self._list.blockSignals(False)
        self._update_status("Mod-Liste neu geladen")

    def _on_open_output(self):
        """Öffnet den Output-Ordner im Dateimanager."""
        out_dir = self._output_dir
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        _ensure_qapp().processEvents()
        url = QUrl.fromLocalFile(out_dir)
        if not QDesktopServices.openUrl(url):
            self._update_status(f"Konnte '{out_dir}' nicht öffnen")
            return
        self._update_status("Output-Ordner geöffnet")

    def _build_status_bar(self):
        """QStatusBar mit Nachricht und Fortschritt."""
        bar = QStatusBar()
        self._status_msg = QLabel("")
        self._status_progress = QLabel("")
        bar.addWidget(self._status_msg)
        bar.addPermanentWidget(self._status_progress)
        self.setStatusBar(bar)
        self._update_status("Bereit — Kanal wählen")
        return bar

    # =============================================================== Layout

    def _build_layout(self):
        """Hauptlayout zusammenbauen."""
        # Titel
        title = QLabel("SC Localization Merger")
        title.setObjectName("title")

        # Fan-Kennzeichner (BEHALTEN)
        fan_label = QLabel("Unofficial fan project")
        fan_label.setObjectName("section")

        # Sektionen
        s1 = QLabel("1. Star Citizen Version")
        s1.setObjectName("section")
        s2 = QLabel("2. Mod-Auswahl")
        s2.setObjectName("section")
        s3 = QLabel("3. Output & Aktion")
        s3.setObjectName("section")

        # QGroupBox-Styling (zweiter Weg über Stylesheet)
        self.setStyleSheet(
            _QSS
            + """
QGroupBox {
    background-color: #252526;
    border: 1px solid #333333;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #C8102E;
    font-size: 12px;
    font-weight: bold;
}
"""
        )

        main = QVBoxLayout()
        main.setSpacing(12)
        main.addSpacing(4)
        main.addWidget(title)
        main.addWidget(fan_label)
        main.addSpacing(4)

        # 1. Star Citizen Version
        main.addWidget(s1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Kanal:"))
        row.addWidget(self._combo_box, 1)
        main.addLayout(row)
        main.addWidget(self._build_edit)
        main.addSpacing(8)

        # 2. Mod-Auswahl (+ Reload-Button rechts in derselben Zeile)
        mod_header = QHBoxLayout()
        mod_header.addWidget(s2)
        mod_header.addStretch()
        mod_header.addWidget(self._reload_btn)
        main.addLayout(mod_header)
        main.addWidget(self._list)
        main.addSpacing(8)

        # 3. Output & Aktion (Output-Pfad inline + Aktion beibehalten)
        main.addWidget(s3)
        main.addWidget(self._output_path_label)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self._open_output_btn)
        btn_row.addWidget(self._merge_btn)
        btn_row.addStretch()
        main.addLayout(btn_row)
        main.addStretch()
        main.setContentsMargins(24, 16, 24, 16)

        # Outputpfad nach Layout verfügbar machen
        self._output_path_label.setText(f"Output: {self._output_dir}")
        return main

    # =============================================================== Widgets

    def _make_combobox(self):
        """QComboBox erstellen."""
        from PySide6.QtWidgets import QComboBox

        return QComboBox()

    def _make_lineedit(self):
        """QLineEdit erstellen."""
        from PySide6.QtWidgets import QLineEdit

        return QLineEdit()

    # =============================================================== Signale

    def _connect_signals(self):
        """UI-Signale mit Speicherungs-Callback verbinden."""
        self._merge_btn.clicked.connect(self._on_merge_clicked)
        self._reload_btn.clicked.connect(self._on_reload_clicked)
        self._open_output_btn.clicked.connect(self._on_open_output)
        self._combo_box.currentIndexChanged.connect(self._on_combo_changed)
        self._build_edit.textChanged.connect(self._save_settings)
        self._list.itemChanged.connect(self._save_settings)

    def _on_combo_changed(self, index: int):
        """Reagiert auf Kanalwechsel — Build-Feld aktualisieren + _data_p4k setzen."""
        items = self._combo_box.itemText(index)

        if items == "Eigener Pfad...":
            # Ordner auswählen (Dateidialog nur auf Userverseite im Event)
            folder = QFileDialog.getExistingDirectory(
                self,
                "Channel-Ordner auswählen",
                "",
                QFileDialog.Option.ShowDirsOnly,
            )
            if not folder:
                # Abgebrochen — zurück zur vorherigen Auswahl
                self._combo_box.blockSignals(True)
                self._combo_box.setCurrentIndex(max(0, index - 1))
                self._combo_box.blockSignals(False)
                self._update_status("Ordnerauswahl abgebrochen")
                self._save_settings()
                return

            data_p4k = os.path.join(folder, "Data.p4k")
            build_number = ""
            if version_detection is not None:
                try:
                    build_number = version_detection.find_build_number(folder)
                except Exception:
                    build_number = ""
            self._build_edit.setText(build_number)
            self._custom_folder = folder
            self._data_p4k = data_p4k
            self._update_status(f"Ordner: {os.path.basename(folder)}")
        else:
            v = self._version_map.get(items)
            if v:
                self._custom_folder = None
                self._data_p4k = v.data_p4k
                self._build_edit.setText(v.build_number)
                self._update_status(f"{v.channel} — Build {v.build_number}")
            else:
                self._update_status("Unbekannter Kanal-Eintrag")

        # Version / Pfad in Settings speichern
        self._save_settings()

    def _load_settings(self):
        if settings is None:
            self._settings = {
                "selected": [],
                "version": "",
                "path": "",
            }
        else:
            self._settings = settings.load_settings(self._settings_path)

    def _restore_settings(self):
        """Gespeicherte UI-Zustände wiederherstellen."""
        # Signale temporär sperren, um kein versehentliches Speichern auszulösen
        self._combo_box.blockSignals(True)
        self._build_edit.blockSignals(True)
        self._list.blockSignals(True)

        version = self._settings.get("version", "")
        path = self._settings.get("path", "")
        selected = self._settings.get("selected", [])

        # Version / Kanal wiederherstellen
        for i in range(self._combo_box.count()):
            if self._combo_box.itemText(i) == version:
                self._combo_box.setCurrentIndex(i)
                break

        self._build_edit.setText(path)
        # Nur persistierte Auswahl anwenden, wenn sie gespeichert wurde;
        # sonst Stand lassen (Default = alle angehakt beim ersten Start).
        if selected:
            self._restore_checked_items(selected)

        self._combo_box.blockSignals(False)
        self._build_edit.blockSignals(False)
        self._list.blockSignals(False)

        # _data_p4k anhand der wiederhergestellten Version aktualisieren
        # (ohne Dateidialog — gleiche Logik wie _on_combo_changed, aber zeilenweise).
        cur = self._combo_box.currentText()
        v = self._version_map.get(cur)
        if cur == "Eigener Pfad..." and path:
            self._custom_folder = path
            self._data_p4k = os.path.join(path, "Data.p4k")
        elif v:
            self._custom_folder = None
            self._data_p4k = v.data_p4k

    def _save_settings(self):
        """Aktuellen UI-Zustand in Settings speichern."""
        if settings is None:
            return
        checked = [
            self._list.item(i).text()
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]
        data = {
            "selected": checked,
            "version": self._combo_box.currentText(),
            "path": self._build_edit.text(),
        }
        settings.save_settings(self._settings_path, data)

    def _restore_checked_items(self, selected_files: list[str]) -> None:
        """CheckBox-Status der angegebenen Dateien wiederherstellen."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is not None and item.text() in selected_files:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

    # =============================================================== Liste

    def _load_list(self):
        """Mod-Dateien aus INI-Ordner laden."""
        ini_dir = self._ini_dir  # immer App-INI als Quelle für die Liste

        files = merge.list_mod_inis(ini_dir)
        self._list.clear()

        if not files:
            item = QListWidgetItem("Keine .ini-Dateien — ziehe eine per Drag & Drop")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._list.addItem(item)
        else:
            for fname in files:
                self._add_to_list(fname)

    def _add_to_list(self, text: str):
        """Einzelnes QListWidgetItem mit Checkbox hinzufügen (Standard: angehakt)."""
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)  # Default: mod aktiviert
        self._list.addItem(item)

    def _refresh_list(self):
        """Liste aktualisieren und alten Check-Status wiederherstellen."""
        current_checked = [
            self._list.item(i).text()
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]
        self._load_list()
        self._restore_checked_items(current_checked)
        self._save_settings()

    def _remove_orphans(self):
        """Items für nicht mehr existierende INI-Dateien entfernen."""
        existing = set(merge.list_mod_inis(self._ini_dir))
        indices_to_remove = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is not None and item.text() not in existing:
                indices_to_remove.append(i)
        for i in reversed(indices_to_remove):
            self._list.takeItem(i)

    # =============================================================== Drag & Drop

    def _on_drag_enter(self, event: QDragEnterEvent):
        """Drag-Enter: .ini-URLs prüfen, visuelle Hervorhebung setzen."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(".ini"):
                    self._list.setProperty("draggable", True)
                    self._list.style().unpolish(self._list)
                    self._list.style().polish(self._list)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _on_drag_leave(self, event):
        """Drag-Leave: Hervorhebung entfernen."""
        self._list.setProperty("draggable", False)
        self._list.style().unpolish(self._list)
        self._list.style().polish(self._list)

    def _on_drop(self, event: QDropEvent):
        """Drop-Event: .ini-Datei in INI-Ordner kopieren."""
        urls = event.mimeData().urls()
        source = None
        for url in urls:
            local = url.toLocalFile()
            if local.lower().endswith(".ini"):
                source = local
                break

        if source is None:
            event.ignore()
            return

        name = os.path.basename(source)
        target_path = os.path.join(self._ini_dir, name)

        if os.path.exists(target_path):
            if not self.confirm_drop_conflict(name):
                self._update_status("Drop abgebrochen (Datei existiert)")
                event.ignore()
                return

        if app_dirs is not None:
            app_dirs.drop_ini_into(self._ini_dir, source)

        self._refresh_list()
        self._update_status(f"Datei '{name}' hinzugefügt")
        event.acceptProposedAction()

    def confirm_drop_conflict(self, name: str) -> bool:
        """Nachfrage, ob existierende Datei überschrieben werden soll.

        Rückgabe: True = Fortfahren, False = Abbrechen.
        """
        return (
            QMessageBox.question(
                self,
                "Datei existiert",
                f"Datei {name} wird überschrieben. Fortfahren?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    # =============================================================== Löschen

    def _on_delete_selected(self):
        """Aktuell markierte Datei aus Liste und INI-Ordner löschen.

        Löscht genau die in der Liste markierte (selektierte) Zeile —
        NICHT alle angehakten Mods.
        """
        # Die aktive/markierte Zeile auswerten (User-Entscheidung),
        # nicht den Checkbox-Status der Liste.
        items = self._list.selectedItems()
        if not items:
            # Fallback: ohne Markierung nichts löschen (verhindert Versehen)
            self._update_status("Keine Datei markiert — erst anklicken/auswählen")
            return
        fname = items[0].text()

        if not merge.delete_mod_ini(self._ini_dir, fname):
            self._update_status(f"'{fname}' konnte nicht gelöscht werden")
            return

        self._refresh_list()
        self._update_status(f"'{fname}' gelöscht")

    # =============================================================== Merge

    def _on_merge_clicked(self):
        """Hauptaktion: Extrahieren + Mergen."""
        self._merge_btn.setEnabled(False)
        self._status_progress.setText("")
        self._update_status("Arbeite...")
        _ensure_qapp().processEvents()

        try:
            # 1. data_p4k ermitteln
            data_p4k = getattr(self, "_data_p4k", None)
            if not data_p4k or not os.path.isfile(data_p4k):
                QMessageBox.warning(
                    self,
                    "Data.p4k fehlt",
                    "Keine Data.p4k gefunden.\nBitte wähle einen gültigen "
                    "Channel-Ordner über 'Eigener Pfad...'.",
                )
                self._update_status("Fehler: Data.p4k fehlt")
                self._merge_btn.setEnabled(True)
                return

            # 2. Extrahieren (temporär im App-Datenordner)
            tmp_base = os.path.join(
                str(app_dirs.get_data_dir()), "tmp_global_base.ini"
            )
            self._status_progress.setText("Extrahiere global.ini...")
            _ensure_qapp().processEvents()
            rc = extract_global.extract_to(data_p4k, tmp_base)
            if rc != 0:
                raise RuntimeError(
                    f"Extraktion fehlgeschlagen (Rückgabe {rc})"
                )

            # 3. Ausgewählte Mod-Dateien ermitteln
            #    (Lese-Fallback, falls App-INI-Ordner leer ist)
            read_dir = self._fallback_dir or self._ini_dir
            self._status_progress.setText("Lade Mod-Einstellungen...")
            _ensure_qapp().processEvents()

            selected_inis = []
            for i in range(self._list.count()):
                item = self._list.item(i)
                if item is not None and (
                    item.checkState() == Qt.CheckState.Checked
                ):
                    selected_inis.append(item.text())

            replacements = merge.load_selected_replacements(
                read_dir, selected_inis
            )

            # 4. Mergen → Output im App-Datenordner
            self._status_progress.setText("Merge läuft...")
            _ensure_qapp().processEvents()
            out_path = os.path.join(self._output_dir, "global.ini")
            replaced, total = merge.merge(tmp_base, replacements, out_path)

            # 5. tmp bereinigen
            if os.path.isfile(tmp_base):
                os.remove(tmp_base)

            # 6. Erfolg
            self._update_status(f"Fertig — {replaced} Werte ersetzt")
            self._status_progress.setText(f"Gesamt: {total} Zeilen")
            QMessageBox.information(
                self,
                "Fertig",
                f"Output/global.ini wurde erstellt.\n\n"
                f"Ersetzte Werte: {replaced}\n"
                f"Zeilen gesamt: {total}\n"
                f"Mod-Dateien: {len(selected_inis)}",
            )

        except FileNotFoundError as exc:
            self._handle_error(f"Datei nicht gefunden:\n{exc}")
        except Exception as exc:
            self._handle_error(
                f"Unerwarteter Fehler:\n{exc}",
                detail=True,
            )
        finally:
            self._merge_btn.setEnabled(True)

    # =============================================================== Fehler

    def _handle_error(self, msg: str, detail: bool = False):
        """Fehlermeldung anzeigen + Stack-Trace in Konsole."""
        self._update_status("Fehler!")
        self._status_progress.setText("")
        if detail:
            full_msg = f"{msg}\n\n{traceback.format_exc()}"
        else:
            full_msg = msg
        QMessageBox.critical(self, "Fehler", full_msg)
        self._merge_btn.setEnabled(True)

    # =============================================================== Status

    def _update_status(self, text: str):
        """Status-Nachricht setzen (rot bei Fehler)."""
        self._status_msg.setText(text)
        if "Fehler" in text:
            self._status_msg.setStyleSheet("color: #ff6666;")
        else:
            self._status_msg.setStyleSheet("")


# ---------------------------------------------------------------------------
# create_app() — für Headless-Tests oder externen Aufruf
# ---------------------------------------------------------------------------


def create_app():
    """
    Erzeugt QApplication + MainWindow und zeigt das Fenster.

    Kann direkt aufgerufen werden (z. B. von einem Test) oder via __main__.
    """
    _ensure_qapp()
    win = MainWindow()
    win.show()
    return win


if __name__ == "__main__":
    win = create_app()
    sys.exit(_ensure_qapp().exec())
