#! /bin/bash

# Golang
if ! command -v go version &> /dev/null
then
    echo "Installing Golang..."
    wget https://go.dev/dl/go1.21.10.linux-amd64.tar.gz
    tar -C /usr/local -xzf go1.21.10.linux-amd64.tar.gz
    mkdir /usr/local/golib
    GOPATH=/usr/local/golib
    export GOPATH
    export PATH=$PATH:/usr/local/go/bin:$GOPATH/bin
fi

# Nodejs
if ! command -v node --version &> /dev/null
then
    echo "Installing Nodejs..."
    # installs fnm (Fast Node Manager)
    curl -fsSL https://fnm.vercel.app/install | bash
    fnm use --install-if-missing 22
fi

# Yarn
if ! command -v yarn --version &> /dev/null
then
    echo "Installing Yarn..."
    npm install -g yarn
fi
