# Start crynux node from docker
#   bash start.sh run

echo $(pwd)

if [ ! -f config/config.yml ]; then
    mkdir -p config
    cp config.yml.example config/config.yml
fi
python3 -m crynux_server.main $1