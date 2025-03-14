# Start crynux node from docker
#   bash start.sh run

echo $(pwd)

# Do not override the config file if it already exists
if [ ! -f config/config.yml ]; then
    mkdir -p config
    cp config.yml.example config/config.yml
fi

# Start the node
python3 -m crynux_server.main $1
