# Package the app using pyinstaller
# Generate a directory that contains the releasing app
# Example call: .\build\windows\package.ps1

./venv/Scripts/Activate.ps1
pyinstaller crynux.spec


./worker/venv/Scripts/Activate.ps1

# # change in controlnet_aux/zoe/zoedepth/models/layers/attractor.py
$TAR_FILE = "worker/venv/Lib/site-packages/controlnet_aux/zoe/zoedepth/models/layers/attractor.py"

if(Test-Path $TAR_FILE -PathType Leaf) {
    (Get-Content $TAR_FILE) | ForEach-Object {$_ -replace "@torch.jit.script", "#@torch.jit.script"} | Set-Content -Path $TAR_FILE
}

pyinstaller crynux_worker_process.spec

Move-Item -Path "dist/crynux_worker_process" "dist/Crynux Node/crynux_worker_process"

Copy-Item -Recurse "data" "dist/Crynux Node/data"

New-Item -ItemType Directory -Path "dist/Crynux Node/webui"
Copy-Item -Recurse "webui/dist" "dist/Crynux Node/webui/dist"

Copy-Item -Recurse "res" "dist/Crynux Node/res"

# Create the archive file
$VERSION = "3.0.0"
$RELEASE_NAME = "crynux-node-helium-v${VERSION}-windows-x64"

Move-Item -Path "dist/Crynux Node" "dist/$RELEASE_NAME"

Compress-Archive -Path "dist/$RELEASE_NAME" -DestinationPath "dist/$RELEASE_NAME.zip"
