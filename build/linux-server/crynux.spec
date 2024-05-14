# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['crynux-node/src/crynux_server/run.py'],
    pathex=[],
    binaries=[
        ('dist/crynux_worker_process', '.'),
    ],
    datas=[
        ('config/*', 'config/'),
        ('data', 'data'),
        ('res', 'res'),
        ('webui', 'webui'),
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
    name='crynux_node',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='crynux_node',
)
