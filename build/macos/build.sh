# Build package from source
# Example call: bash build/macos/build.sh ~/crynux_app 
WORK_DIR=$1
echo $WORK_DIR


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

GIT_DIR=$(pwd)
mkdir $WORK_DIR
cd $WORK_DIR

cp -R "$GIT_DIR/src/webui" $WORK_DIR
cd "$WORK_DIR/webui"
cp src/config.example.json  src/config.json
yarn && yarn build
cd $WORK_DIR

### Server ###
python3.10 -m venv venv
export PATH="$WORK_DIR/venv/bin:${PATH}"
mkdir "$WORK_DIR/crynux-node"
cd "$WORK_DIR/crynux-node"
cp -R $GIT_DIR/src src
cp -R $GIT_DIR/res ../res
cp $GIT_DIR/pyproject.toml pyproject.toml
cp $GIT_DIR/setup.py setup.py
cp $GIT_DIR/requirements.txt requirements.txt
cp $GIT_DIR/MANIFEST.in MANIFEST.in
cp $GIT_DIR/go.mod go.mod
cp $GIT_DIR/go.sum go.sum
pip install -r requirements.txt && pip install .


### worker ###
cd $GIT_DIR
git submodule update --init --recursive
cd $WORK_DIR
mkdir "$WORK_DIR/worker"
cp $GIT_DIR/src/prefetch.py worker/prefetch.py
cp $GIT_DIR/src/inference.py worker/inference.py


python3.10 -m venv worker/venv
source "$WORK_DIR/worker/venv/bin/activate"

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

PYBIN = $(realpath $(which python3.10))
rm "$WORK_DIR/worker/venv/pyvenv.cfg"
cp -f $PYBIN "$WORK_DIR/worker/venv/bin/python3.10"
echo "include-system-site-packages = false" > "$WORK_DIR/worker/venv/pyvenv.cfg"

mkdir config
cp $GIT_DIR/config/config.yml.shell_example config/config.yml
cp $GIT_DIR/start.sh start.sh
cp $GIT_DIR/build/macos/app.sh app.sh
cp $GIT_DIR/build/macos/crynux.spec crynux.spec

# bash build/macos/build.sh ~/crynux_app ~/crynux.tar.gz
# OUTPUT_FILE=$2
# echo $OUTPUT_FILE
# tar czf $OUTPUT_FILE .
