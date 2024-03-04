
if ! [ -x "$(command -v brew)" ]; then
  echo 'Error: brew is not installed.'
  exit 1
fi

function check_or_install {
  if ! [ -x "$(command -v $1)" ]
  then
    echo "Error: $1 is not installed."
    brew install "$1"
  fi
}

check_or_install git
check_or_install yarn
check_or_install node
check_or_install python3

GIT_DIR=$(pwd)
git submodule update --init --recursive
rm -R -f ~/crynux_app
mkdir ~/crynux_app
cd ~/crynux_app

cp -R "$GIT_DIR/src/webui" ~/crynux_app/
cd ~/crynux_app/webui
cp src/config.example.json  src/config.json
yarn && yarn build
cd ~/crynux_app

### Server ###
python3 -m venv server-venv
export PATH="~/crynux_app/venv/bin:${PATH}"
mkdir ~/crynux_app/crynux-node
cd ~/crynux_app/crynux-node
cp -R $GIT_DIR/src src
cp $GIT_DIR/pyproject.toml pyproject.toml
cp $GIT_DIR/setup.py setup.py
cp $GIT_DIR/requirements.txt requirements.txt
cp $GIT_DIR/MANIFEST.in MANIFEST.in
cp $GIT_DIR/go.mod go.mod
cp $GIT_DIR/go.sum go.sum
pip install -r requirements.txt && pip install .


### worker ###
python3 -m venv worker-venv
cp -R $GIT_DIR/stable-diffusion-task stable-diffusion-task
cd stable-diffusion-task
pip install -r requirements_macos.txt
pip install .
cd ~/crynux_app

cp -R $GIT_DIR/gpt-task gpt-task
cd gpt-task
pip install -r requirements_macos.txt
pip install .
cd ~/crynux_app

mkdir ~/crynux_app/worker
cp $GIT_DIR/src/prefetch.py worker/prefetch.py
cp $GIT_DIR/src/inference.py worker/inference.py

mkdir data
mkdir data/external
mkdir data/huggingface
mkdir data/results
mkdir data/inference-logs
mkdir config

cp $GIT_DIR/config/config.yml.example config/config.yml
cp $GIT_DIR/start.sh start.sh
export CRYNUX_SERVER_CONFIG="$(pwd)/config/config.yml"
python3 -m crynux_server.main run

