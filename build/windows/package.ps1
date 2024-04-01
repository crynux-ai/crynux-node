# Package the app using pyinstaller
# Generate a directory that contains the releasing app
# Example call: ./build/windows/package.ps1

./venv/Scripts/Activate.ps1
pyinstaller crynux.spec


./worker/venv/Scripts/Activate.ps1

# # change in controlnet_aux/zoe/zoedepth/models/layers/attractor.py
$TAR_FILE = "worker/venv/Lib/site-packages/controlnet_aux/zoe/zoedepth/models/layers/attractor.py"

if(Test-Path $TAR_FILE -PathType Leaf) {
    (Get-Content $TAR_FILE) | ForEach-Object {$_ -replace "@torch.jit.script", "#@torch.jit.script"} | Set-Content -Path $TAR_FILE
}

pyinstaller crynux_worker_process.spec

# New-Item -ItemType Directory -Path "dist/data"
# New-Item -ItemType Directory -Path "dist/data/external"
# New-Item -ItemType Directory -Path "dist/data/huggingface"
# New-Item -ItemType Directory -Path "dist/data/results"
# New-Item -ItemType Directory -Path "dist/data/inference-logs"
