if [ ! -f config/config.yml ]; then
    cp config.yml.example config/config.yml
fi
python3 -m h_server.main