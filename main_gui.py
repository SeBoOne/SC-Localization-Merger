#!/usr/bin/env python3
"""
SC Localization Merger — PySide6 GUI.

Zwei-Klick-Workflow:
  1. Kanal + Build auswaehlen (automatische Erkennung oder eigener Pfad).
  2. Mod-Dateien aus dem ini/-Unterordner an-/abwaehlen.
  3. „Extrahieren & Mergen" → Output/global.ini.

Lauft auf Linux und Windows. Headless-faehig (QT_QPA_PLATFORM=offscreen).
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# PySide6 als Modul + QApplication (QtWidgets nötig für Basisklasse QMainWindow)
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# QApplication: nur beim eigentlichen Start instantiiert (import ohne exec)
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
# Importe der Nachbarmodule (defensiv, version_detection fehlt evtl.)
# ---------------------------------------------------------------------------

import extract_global
import merge

try:
    import version_detection
except ImportError:
    version_detection = None

# ---------------------------------------------------------------------------
# QSS — dunkles Theme + Drake-Rot #C8102E Akzent
# ---------------------------------------------------------------------------

_QSS = """
QMainWindow {
    background-color: #1e1e1e;
}
QStatusBar {
    background-color: #1e1e1e;
    color: #cccccc;
    border-top: 1px solid #333333;
}

/* --------------------------------------------------------------- Kombobox
   (Version-Auswahl) */
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

/* --------------------------------------------------------------- Zeilen-
   edit (Build-Nummer) */
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

/* --------------------------------------------------------------- List Widget
   (Mod-Dateien) */
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

/* Checkboxes im QListWidget — Standard-QCheckBox in QListWidgetItem */
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

/* --------------------------------------------------------------- Button */
QPushButton {
    background-color: #C8102E;
    color: #ffffff;
    border: none;
    border-radius: 4px;
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

/* --------------------------------------------------------------- Labels */
QLabel {
    color: #e0e0e0;
}
QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}
QLabel#section {
    font-size: 12px;
    font-weight: bold;
    color: #C8102E;
    padding-top: 6px;
}
QLabel#status {
    color: #aaaaaa;
    font-size: 11px;
}
"""


class MainWindow(QtWidgets.QMainWindow):
    """Hauptfenster des SC Localization Merger."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SC Localization Merger")
        self.resize(620, 560)
        self.setMinimumSize(480, 400)

        self.apply_qss()

        # Projektordner
        self._proj_dir = str(Path(__file__).resolve().parent)

        # ini/-Verzeichnis anlegen, falls nicht vorhanden
        self._ini_dir = os.path.join(self._proj_dir, "ini")
        os.makedirs(self._ini_dir, exist_ok=True)

        # Version-Erkennung (kann None sein)
        self._versions: list = []
        if version_detection is not None:
            try:
                self._versions = version_detection.detect_versions()
            except Exception:
                self._versions = []

        # Widgets bauen
        self._combo_box = self._build_combo()
        self._build_layout_wrapper = self._build_build_line()
        self._list = self._build_list()
        self._merge_btn = self._build_merge_button()
        self._status_label = self._build_status()

        # Hauptlayout
        main_layout = self._build_layout()
        central = self._widget_from_layout(main_layout)
        self.setCentralWidget(central)

        # Status
        self._update_status("Bereit — Kanal wählen")

        # Build-Feld mit dem anfangs gewählten Kanal vorbelegen,
        # aber nur wenn tatsächlich eine (auto-erkannte) Version gewählt ist.
        if self._versions:
            self._on_combo_changed(self._combo_box.currentIndex())

    # --------------------------------------------------------------- QSS

    def apply_qss(self):
        """QSS-Stylesheet auf das gesamte Fenster anwenden."""
        self.setStyleSheet(_QSS)

    # --------------------------------------------------------------- Builder

    def _build_combo(self):
        """QComboBox für die Versionsauswahl."""
        from PySide6.QtWidgets import QComboBox, QLabel, QHBoxLayout

        combobox = QComboBox()
        combobox.setMinimumHeight(32)

        # Items: Label → SCVersion-Map
        self._version_map: dict[str, object] = {}
        items = []

        for v in self._versions:
            base = os.path.basename(os.path.dirname(v.data_p4k))
            label = f"{v.channel} — {base}"
            items.append(label)
            self._version_map[label] = v

        # Marker für eigenen Pfad
        items.append("Eigener Pfad...")

        combobox.addItems(items)
        # Standard: erster Eintrag; falls leer → letzter (Eigen)
        if items:
            combobox.setCurrentIndex(0 if items else len(items) - 1)

        combobox.currentIndexChanged.connect(self._on_combo_changed)

        # Layout mit Label
        label = QLabel("Kanal:")
        row = QHBoxLayout()
        row.addWidget(label, 0)
        row.addWidget(combobox, 1)
        row.setContentsMargins(0, 0, 0, 0)

        wrapper = self._widget_from_layout(row)
        self._combo_wrapper = wrapper
        return combobox

    def _build_build_line(self):
        """QLineEdit für die Build-Nummer."""
        from PySide6.QtWidgets import QLineEdit, QLabel, QHBoxLayout

        edit = QLineEdit()
        edit.setMinimumHeight(32)
        edit.setPlaceholderText("Build-Nummer wird automatisch gesetzt")
        self._build_edit = edit

        label = QLabel("Build-Nummer:")
        row = QHBoxLayout()
        row.addWidget(label, 0)
        row.addWidget(edit, 1)
        row.setContentsMargins(0, 0, 0, 0)

        wrapper = self._widget_from_layout(row)
        return wrapper

    def _build_list(self):
        """QListWidget mit CheckBoxes für Mod-Dateien."""
        from PySide6.QtWidgets import QListWidget
        from PySide6.QtCore import Qt

        widget = QListWidget()
        widget.setMinimumHeight(200)

        mod_files = merge.list_mod_inis(self._ini_dir)

        if not mod_files:
            item = self._list_item("Keine .ini-Dateien in ini/ — lege eine ab")
            item.setCheckState(Qt.CheckState.Unchecked)
            widget.addItem(item)
        else:
            for fname in mod_files:
                item = self._list_item(fname)
                item.setCheckState(Qt.CheckState.Checked)  # Alle angehakt
                widget.addItem(item)

        return widget

    def _list_item(self, text: str):
        """QListWidgetItem mit Checkbox zurückgeben."""
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt

        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        return item

    def _build_merge_button(self):
        """QPushButton „Extrahieren & Mergen"."""
        from PySide6.QtWidgets import QPushButton

        btn = QPushButton("Extrahieren & Mergen")
        btn.setMinimumHeight(40)
        btn.setMinimumWidth(200)
        return btn

    def _build_status(self):
        """QSatusbar für Fortschritt/Status."""
        from PySide6.QtWidgets import QLabel

        label = QLabel("")
        label.setProperty("status", True)
        label.setText("Status")
        return label

    # --------------------------------------------------------------- Layout

    def _build_layout(self):
        """Hauptlayout zusammenbauen."""
        from PySide6.QtWidgets import (
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
        )

        # Titel
        title = QLabel("Star Citizen — global.ini Merger")
        title.setProperty("title", True)

        # Sektionen
        section1 = QLabel("1. Kanal auswählen")
        section1.setProperty("section", True)

        section2 = QLabel("2. Build-Nummer (optional editierbar)")
        section2.setProperty("section", True)

        section3 = QLabel("3. Mod-Dateien auswählen")
        section3.setProperty("section", True)

        # Button + Status
        btn_status = QHBoxLayout()
        btn_status.addStretch()
        btn_status.addWidget(self._merge_btn)
        btn_status.addWidget(self._status_label, 1)
        btn_status.setContentsMargins(40, 10, 40, 0)

        main = QVBoxLayout()
        main.addWidget(title)
        main.addSpacing(10)
        main.addWidget(section1)
        main.addWidget(self._combo_wrapper)
        main.addSpacing(4)
        main.addWidget(section2)
        main.addWidget(self._build_layout_wrapper)
        main.addSpacing(8)
        main.addWidget(section3)
        main.addWidget(self._list)
        main.addSpacing(16)
        main.addLayout(btn_status)
        main.addStretch()
        main.setContentsMargins(24, 16, 24, 16)

        return main

    def _widget_from_layout(self, layout):
        """Layout in ein QWidget einbetten."""
        from PySide6.QtWidgets import QWidget

        w = QWidget()
        w.setLayout(layout)
        return w

    # --------------------------------------------------------------- Signale

    def _on_combo_changed(self, index: int):
        """Reagiert auf Kanalwechsel — Build-Feld aktualisieren."""
        from PySide6.QtWidgets import QFileDialog

        items = self._combo_box.itemText(index)

        if items == "Eigener Pfad...":
            self._build_edit.setText("")
            # Ordner auswählen
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
                return

            # data_p4k = <folder>/Data.p4k
            data_p4k = os.path.join(folder, "Data.p4k")
            if version_detection is not None:
                build_number = version_detection.find_build_number(folder)
            else:
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
                self._update_status(
                    f"{v.channel} — Build {v.build_number}"
                )
            else:
                self._update_status("Unbekannter Kanal-Eintrag")

    def _on_merge_clicked(self):
        """Hauptaktion: Extrahieren + Mergen."""
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import Qt

        self._merge_btn.setEnabled(False)
        self._status_label.setText("Arbeite...")
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
                self._status_label.setText("Fehler: Data.p4k fehlt")
                self._merge_btn.setEnabled(True)
                return

            # 2. Extrahieren
            self._status_label.setText("Extrahiere global.ini...")
            _ensure_qapp().processEvents()
            tmp_base = os.path.join(self._proj_dir, "tmp_global_base.ini")
            rc = extract_global.extract_to(data_p4k, tmp_base)
            if rc != 0:
                raise RuntimeError(
                    f"Extraktion fehlgeschlagen (Rückgabe {rc})"
                )

            # 3. Ausgewählte Mod-Dateien ermitteln
            self._status_label.setText("Lade Mod-Einstellungen...")
            _ensure_qapp().processEvents()

            selected_inis = []
            for i in range(self._list.count()):
                item = self._list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    selected_inis.append(item.text())

            replacements = merge.load_selected_replacements(
                self._ini_dir, selected_inis
            )

            # 4. Mergen
            self._status_label.setText("Merge läuft...")
            _ensure_qapp().processEvents()
            out_path = os.path.join(self._proj_dir, "Output", "global.ini")
            replaced, total = merge.merge(tmp_base, replacements, out_path)

            # 5. tmp bereinigen
            if os.path.isfile(tmp_base):
                os.remove(tmp_base)

            # 6. Erfolg
            self._status_label.setText(f"Fertig — {replaced} Werte ersetzt")
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

    def _handle_error(self, msg: str, detail: bool = False):
        """Fehlermeldung anzeigen + Stack-Trace in Konsole."""
        from PySide6.QtWidgets import QMessageBox

        self._status_label.setText("Fehler!")
        if detail:
            full_msg = f"{msg}\n\n{traceback.format_exc()}"
        else:
            full_msg = msg
        QMessageBox.critical(self, "Fehler", full_msg)
        self._merge_btn.setEnabled(True)

    def _update_status(self, text: str):
        """Statusleiste aktualisieren."""
        self._status_label.setText(text)


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
    # Merge-Button Signal verbinden
    win._merge_btn.clicked.connect(win._on_merge_clicked)
    return win


if __name__ == "__main__":
    win = create_app()
    sys.exit(_ensure_qapp().exec())
