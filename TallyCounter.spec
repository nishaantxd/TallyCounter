# -*- mode: python ; coding: utf-8 -*-

import os

src_dir = os.path.join(os.getcwd(), 'src')
icon_path = os.path.join(src_dir, 'icon.ico')

a = Analysis(
    [os.path.join(src_dir, 'main.py')],
    pathex=[src_dir],
    binaries=[],
    datas=[
        (icon_path, '.') if os.path.exists(icon_path) else None,
    ],
    hiddenimports=[
        'win32gui',
        'win32process',
        'win32con',
        'psutil',
        'pystray',
        'PIL',
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# Remove None entries from datas (in case icon doesn't exist)
a.datas = [d for d in a.datas if d is not None]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TallyCounter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # No console window (system tray app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None,
)
