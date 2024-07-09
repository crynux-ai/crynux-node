
if (Test-Path -Path "worker") {
    Write-Output "Deleting the old worker folder"
    Remove-Item -Recurse -Force "worker"
}

if (Test-Path -Path "venv") {
    Write-Output "Deleting the old venv folder"
    Remove-Item -Recurse -Force "venv"
}

$WORK_DIR = Get-Location

# 1. Build the WebUI
Set-Location "$WORK_DIR/src/webui"
Copy-Item src/config.example.json src/config.json

if (Test-Path -Path "dist") {
    Remove-Item -Recurse "dist"
}

New-Item -ItemType Directory -Path "dist"

yarn
yarn build

# 2. Prepare the server
Set-Location $WORK_DIR
python -m venv venv
./venv/Scripts/Activate.ps1

pip install -r requirements_desktop.txt
pip install .

# 3. Prepare the worker
Set-Location $WORK_DIR
New-Item -ItemType Directory -Path "worker"
Copy-Item crynux-worker/crynux_worker_process.py worker/
Set-Location "$WORK_DIR/worker"
python -m venv venv
./venv/Scripts/Activate.ps1

Set-Location "$WORK_DIR/stable-diffusion-task"
pip install -r requirements_cuda.txt
pip install .

Set-Location "$WORK_DIR/gpt-task"
pip install -r requirements_cuda.txt
pip install .

Set-Location "$WORK_DIR/crynux-worker"
pip install -r requirements.txt
pip install .

# go back to server venv
Set-Location $WORK_DIR
./venv/Scripts/Activate.ps1
