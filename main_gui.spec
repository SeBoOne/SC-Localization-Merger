# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-Spec für SC Localization Merger.
Einzel-EXE, fensterlos (GUI), Windows/Linux-kompatibel.
"""

import sys
from pathlib import Path

block_cipher = None

# --- PySide6-Automatik: Hooks werden automatisch geladen ---

# Versteckte Imports für Module der App
hiddenimports = [
    'merge',
    'p4k_reader',
    'extract_global',
    'version_detection',
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Cipher.AES',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
]

# --- Binärdateien: keine externen Binaries nötig ---
binaries = []

# --- Daten-Dateien: keine zusätzlichen Daten ---
datas = []

# --- Eingabe: Hauptskript ---
a = Analysis(
    ['main_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'setuptools',
        'distutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SC-Localization-Merger',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # fensterlos (GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
)
