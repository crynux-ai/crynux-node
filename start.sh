# Start crynux node
#   bash start.sh run ~/crynux_data
#
# If you load from MacOS package, run this to unpack:
#   WORKDIR=~/crynux_app && mkdir $WORKDIR && tar -xvzf crynux.tar.gz -C $WORKDIR && cd $WORKDIR

DATA_DIR=$2
echo $(pwd)
echo $DATA_DIR


if [ -d data ]; then
    echo "$(pwd)/data exist, delete if you'd like to overwrite."
else
  # In case the data has been stored elsewhere
  if [[ -z "$DATA_DIR" ]]; then
    mkdir data
    mkdir data/external
    mkdir data/huggingface
    mkdir data/results
    mkdir data/inference-logs  
  else
    cp -R $DATA_DIR data
  fi
fi


if [ ! -f config/config.yml ]; then
    mkdir -p config
    cp config.yml.example config/config.yml
fi
export CRYNUX_SERVER_CONFIG="$(pwd)/config/config.yml"
source venv/bin/activate
python3 -m crynux_server.main $1