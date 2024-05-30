#!/bin/bash
# Build package from source
# Example call: bash build/macos/prepare.sh -w ~/crynux_app

while getopts ":w:d:" opt; do
  case $opt in
    w) WORK_DIR="$OPTARG"
    ;;
    d) DATA_DIR="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    exit 1
    ;;
  esac

  case $OPTARG in
    -*) echo "Option $opt needs a valid argument"
    exit 1
    ;;
  esac
done

if [[ -z $WORK_DIR ]]; then
  echo "Please specify the target directory"
  exit 1
fi

if [[ -d "$WORK_DIR" ]]; then
  echo "Deleting old package folder"
  rm -r $WORK_DIR
fi

echo "Creating package folder"
mkdir $WORK_DIR

WORK_DIR=$(realpath $WORK_DIR)
echo "Package folder: $WORK_DIR"

GIT_DIR=$(pwd)
GIT_DIR=$(realpath $GIT_DIR)
echo "Workspace folder: $GIT_DIR"


# 1. Prepare the WebUI dist
if !command -v fnm &> /dev/null
then
    # installs fnm (Fast Node Manager)
    curl -fsSL https://fnm.vercel.app/install | bash
fi

fnm use --install-if-missing 22

if ! command -v yarn &> /dev/null
then
    npm install -g yarn
fi


mkdir "$WORK_DIR/webui"

cd "$GIT_DIR/src/webui"
cp src/config.example.json  src/config.json

yarn && yarn build
cp -R "$GIT_DIR/src/webui/dist" "$WORK_DIR/webui/dist"


# 2. Prepare the server
cd $WORK_DIR
python3.10 -m venv venv
export PATH="$WORK_DIR/venv/bin:${PATH}"
mkdir "$WORK_DIR/crynux-node"
cd "$WORK_DIR/crynux-node"
cp -R $GIT_DIR/src src
cp -R $GIT_DIR/res ../res
cp $GIT_DIR/pyproject.toml pyproject.toml
cp $GIT_DIR/setup.py setup.py
cp $GIT_DIR/requirements_docker.txt requirements.txt
cp $GIT_DIR/MANIFEST.in MANIFEST.in
cp $GIT_DIR/go.mod go.mod
cp $GIT_DIR/go.sum go.sum
pip install -r requirements.txt && pip install .[app]


# 3. Prepare the worker
cd $GIT_DIR
git submodule update --init --recursive
cd $WORK_DIR
mkdir "$WORK_DIR/worker"
cp $GIT_DIR/src/crynux_worker_process.py worker/

python3.10 -m venv worker/venv
source "$WORK_DIR/worker/venv/bin/activate"
pip install pyinstaller==6.5.0

cp -R $GIT_DIR/stable-diffusion-task stable-diffusion-task
cd stable-diffusion-task
pip install -r requirements_cuda.txt
pip install .
cd $WORK_DIR

cp -R $GIT_DIR/gpt-task gpt-task
cd gpt-task
pip install -r requirements_cuda.txt
pip install .

cd $WORK_DIR

mkdir config
cp $GIT_DIR/config/config.yml.package_example config/config.yml
cp $GIT_DIR/start.sh start.sh
cp $GIT_DIR/build/linux-server/* .
chmod +x *.sh


## Prepare the data folder
if [ $DATA_DIR ] && [ -d $DATA_DIR ]; then
  # In case the data has been stored elsewhere
  echo "$DATA_DIR exist, copy it to dist"
  mkdir "data"
  cp -R $DATA_DIR/* "data/"
else
  cp -R $GIT_DIR/build/data .
fi
