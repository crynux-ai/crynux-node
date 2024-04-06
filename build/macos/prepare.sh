# Build package from source
# Example call: bash build/macos/build.sh ~/crynux_app 

if [[ -z $1 ]]; then
  exit 1
fi

if [[ -d "$1" ]]; then
  echo "Deleting old package folder"
  rm -r $1
fi

echo "Creating package folder"
mkdir $1

WORK_DIR=$(realpath $1)
echo "Package folder: $WORK_DIR"

GIT_DIR=$(pwd)
GIT_DIR=$(realpath $GIT_DIR)
echo "Workspace folder: $GIT_DIR"


if ! [ -x "$(command -v brew)" ]; then
  echo 'Error: brew is not installed.'
  exit 1
fi

function check_or_install {
  if ! [ -x "$(command -v $1)" ]
  then
    echo "Error: $1 is not installed."
    brew install "$2"
  fi
}

check_or_install git git
check_or_install yarn yarn
check_or_install node node
check_or_install go go
check_or_install python3.10 python@3.10
check_or_install create-dmg create-dmg


# 1. Prepare the WebUI dist

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
cp $GIT_DIR/requirements_macos.txt requirements.txt
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
pip install -r requirements_macos.txt
pip install .
cd $WORK_DIR

cp -R $GIT_DIR/gpt-task gpt-task
cd gpt-task
pip install -r requirements_macos.txt
pip install .
cd $WORK_DIR

mkdir config
cp $GIT_DIR/config/config.yml.package_example config/config.yml
cp $GIT_DIR/start.sh start.sh
cp $GIT_DIR/build/macos/* .

# bash build/macos/build.sh ~/crynux_app ~/crynux.tar.gz
# OUTPUT_FILE=$2
# echo $OUTPUT_FILE
# tar czf $OUTPUT_FILE .
