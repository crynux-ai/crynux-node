#!/bin/bash

# https://github.com/AnyLifeZLB/FaceVerificationSDK/blob/main/install_newest_mediapipe_on_macos.md
export SYSTEM_VERSION_COMPAT=0

# Must use arm64 version of Python
# CONDA_SUBDIR=osx-arm64 conda create -n crynux python=3.10
# python > 3.10.2 is required
arch=$(python3.10 -c "import platform;print(platform.uname())")
if [[ $arch == *"x86_64"* ]]; then
  echo "Please use the python in arm64 arch"
  exit 1
fi

# remove old env
if [ -d "venv" ]; then
  rm -rf venv
fi

if [ -d "worker" ]; then
  rm -rf worker
fi

# prepare the Web UI
cd src/webui

if [ -d "dist" ]; then
  rm -rf dist
fi

yarn
yarn build

cd ../../

# prepare the server
python3.10 -m venv venv
source ./venv/bin/activate
pip install -r requirements_desktop.txt
pip install .

# prepare the worker
mkdir worker
cp crynux-worker/crynux_worker_process.py worker/
cd worker
python3.10 -m venv venv
source ./venv/bin/activate

cd ../stable-diffusion-task
pip install -r requirements_macos.txt
pip install .

cd ../gpt-task
pip install -r requirements_macos.txt
pip install .

cd ../crynux-worker
pip install -r requirements.txt
pip install .

cd ../
