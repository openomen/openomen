# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the GUI binary:  pyinstaller openomen-gui.spec
# Needs PySide6 installed in the build environment (pip install PySide6).


a = Analysis(
    ['openomen-gui'],
    pathex=['src'],
    binaries=[],
    # Bundled typefaces (Chakra Petch, Barlow; SIL OFL) next to the gui package.
    datas=[('src/openomen/gui/fonts', 'openomen/gui/fonts')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Only QtCore/QtGui/QtWidgets are used; keep the rest of Qt out of the binary.
    excludes=['tkinter', 'PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick',
              'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtMultimedia',
              'PySide6.Qt3DCore', 'PySide6.QtPdf', 'PySide6.QtCharts', 'PySide6.QtDataVisualization'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='openomen-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
