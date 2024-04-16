# -*- mode: python ; coding: utf-8 -*-
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--identity", action="store")
options = parser.parse_args()

a = Analysis(
    ['worker/crynux_worker_process.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "diffusers.pipelines.stable_diffusion_xl.pipeline_output",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    module_collection_mode={
        'diffusers': 'py',
        'transformers': 'py',
        'torch': 'py',
        'sd_task': 'py',
        'gpt_task': 'py',
    },
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='crynux_worker_process',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=options.identity,
    entitlements_file='entitlements.plist',
)
