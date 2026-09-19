# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-Spec für SC Localization Merger (CustomTkinter-GUI).
Einzel-EXE, fensterlos (GUI), Windows/Linux-kompatibel.
"""

block_cipher = None

from pathlib import Path
import sys as _sys

# --- CustomTkinter-Automatik: PyInstaller-Hooks laden tkinter & CustomTkinter ---
# customtkinter hier explizit aufführen, damit alle Submodule (z.B. windows.widgets)
# sicher gebündelt werden.

# Versteckte Imports für Module der App
hiddenimports = [
    'customtkinter',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL._tkinter_finder',
    'merge',
    'p4k_reader',
    'extract_global',
    'version_detection',
    'app_dirs',
    'settings',
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Cipher.AES',
]

# --- Binärdateien: keine externen Binaries nötig (außer tkinter-Systemlibs) ---
binaries = []

# Auf Linux liegen die tkinter-Systemlibs (libtcl9.0/libtcl9tk9.0) im Python-Ordner
# ($base_prefix/lib). PyInstaller findet sie NICHT automatisch und das frozen Bundle
# crasht sonst beim Start mit 'ImportError: libtcl9.0.so'. Deshalb explizit mitpacken.
if _sys.platform != "win32":
    _libdir = Path(_sys.base_prefix) / "lib"
    for _name in ("libtcl9.0.so", "libtcl9tk9.0.so"):
        _src = _libdir / _name
        if _src.exists():
            binaries.append((str(_src), "."))

# --- Daten-Dateien: mitgelieferte Asset-Dateien (Reload-Icon) ---
datas = [("assets/reload_icon.png", "assets")]

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
