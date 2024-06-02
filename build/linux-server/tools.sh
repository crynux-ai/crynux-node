#! /bin/bash

# Golang
if ! command -v go version &> /dev/null
then
    echo "Installing Golang..."
    wget https://go.dev/dl/go1.21.10.linux-amd64.tar.gz
    tar -C ~/go -xzf go1.21.10.linux-amd64.tar.gz
    mkdir ~/golib
    GOPATH=~/golib
    export GOPATH
    export PATH=$PATH:~/go/bin:$GOPATH/bin
fi

# Nodejs
if ! command -v node --version &> /dev/null
then
    echo "Installing Nodejs..."
    # installs fnm (Fast Node Manager)
    curl -fsSL https://fnm.vercel.app/install | bash
    source ~/.bashrc
    fnm use --install-if-missing 22
fi

# Yarn
if ! command -v yarn --version &> /dev/null
then
    echo "Installing Yarn..."
    npm install -g yarn
fi
