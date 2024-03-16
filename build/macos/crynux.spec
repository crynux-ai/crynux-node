# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['crynux-node/src/app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/*', 'config/'),
    ] + collect_data_files('crynux_server.contracts.abi'),
    hiddenimports=['aiosqlite', "crynux_server.contracts.abi"],
    collect_submodules=["crynux_server.contracts.abi"],
    collect_data=["crynux_server.contracts.abi"],
    module_collection_mode={
        'crynux_server': 'py',
        'crynux_worker': 'py',
    },
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='crynux',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['res/icon.icns'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='crynux',
)
app = BUNDLE(
    coll,
    name='crynux.app',
    icon='res/icon.icns',
    bundle_identifier=None,
    info_plist={
        'CFBundleShortVersionString': '0.0.1',
    },
)