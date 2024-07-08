# Prepare the project for pyinstaller packaging
# Generate a directory that to be packaged by pyinstaller
# Example call: ./build/windows/prepare.ps1 build/crynux_node

param(
    [string]$RELEASE_DIR
)

if (-not $RELEASE_DIR) {
    Write-Error "Please set the output dir"
    exit 1
}

$ErrorActionPreference = "Stop"

$WORK_DIR = Get-Location
$RELEASE_DIR = Join-Path -Path $WORK_DIR -ChildPath $RELEASE_DIR

Write-Output $WORK_DIR
Write-Output $RELEASE_DIR

# 0. Clear the release dir if exists

if (Test-Path -Path $RELEASE_DIR) {
    Write-Output "Deleting the old release folder"
    Remove-Item -Recurse -Force $RELEASE_DIR
}

New-Item -ItemType Directory -Path $RELEASE_DIR

# 1. Build the WebUI
Set-Location "$WORK_DIR/src/webui"
Copy-Item src/config.example.json src/config.json

if (Test-Path -Path "dist") {
    Remove-Item -Recurse "dist"
}

New-Item -ItemType Directory -Path "dist"

yarn
yarn build

## Copy the dist WebUI package to the release folder
New-Item -ItemType Directory -Path "$RELEASE_DIR/webui"
Copy-Item -Recurse "$WORK_DIR/src/webui/dist" "$RELEASE_DIR/webui/dist"


# 2. Build the server
Set-Location $RELEASE_DIR
python -m venv venv
./venv/Scripts/Activate.ps1
New-Item -ItemType Directory -Path "$RELEASE_DIR/crynux-node"
Set-Location "$RELEASE_DIR/crynux-node"

Copy-Item -Recurse $WORK_DIR/src src
Copy-Item -Recurse $WORK_DIR/res ../res
Copy-Item $WORK_DIR/pyproject.toml pyproject.toml
Copy-Item $WORK_DIR/setup.py setup.py
Copy-Item $WORK_DIR/requirements_desktop.txt requirements.txt
Copy-Item $WORK_DIR/MANIFEST.in MANIFEST.in
Copy-Item $WORK_DIR/go.mod go.mod
Copy-Item $WORK_DIR/go.sum go.sum
pip install -r requirements.txt
pip install .[app]

# 3. Build the worker

### Update git submodule
Set-Location $WORK_DIR
git submodule update --init --recursive

Set-Location $RELEASE_DIR
New-Item -ItemType Directory -Path "$RELEASE_DIR/worker"
Copy-Item $WORK_DIR/crynux-worker/crynux_worker_process.py worker/

Set-Location $RELEASE_DIR/worker
python -m venv venv
./venv/Scripts/Activate.ps1
pip install pyinstaller==6.5.0

Copy-Item -Recurse $WORK_DIR/stable-diffusion-task $RELEASE_DIR/stable-diffusion-task
Set-Location $RELEASE_DIR/stable-diffusion-task
pip install -r requirements_cuda.txt
pip install .

Copy-Item -Recurse $WORK_DIR/gpt-task $RELEASE_DIR/gpt-task
Set-Location $RELEASE_DIR/gpt-task
pip install -r requirements_cuda.txt
pip install .

Copy-Item -Recurse $WORK_DIR/crynux-worker $RELEASE_DIR/crynux-worker
Set-Location $RELEASE_DIR/crynux-worker
pip install -r requirements.txt
pip install .

Set-Location $RELEASE_DIR
New-Item -ItemType Directory -Path config
Copy-Item $WORK_DIR/config/config.yml.package_example config/config.yml
Copy-Item $WORK_DIR/start.sh start.sh
Copy-Item $WORK_DIR/build/windows/* .

Set-Location $WORK_DIR
