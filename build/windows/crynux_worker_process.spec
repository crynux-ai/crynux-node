# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_data_files
scipy_hiddenimports = collect_submodules('scipy')

scipy_datas = collect_data_files('scipy')

a = Analysis(
    ['worker/crynux_worker_process.py'],
    pathex=[],
    binaries=[],
    datas=scipy_datas,
    hiddenimports=[
        "diffusers.pipelines.stable_diffusion_xl.pipeline_output",
        "pkg_resources.extern",
    ] + scipy_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    module_collection_mode={
        'diffusers': 'py',
        'transformers': 'py',
        'torch': 'py',
        'sd_task': 'py',
        'gpt_task': 'py',
        'crynux_worker': 'py',
    },
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='crynux_worker_process',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=['res/icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='crynux_worker_process',
)
