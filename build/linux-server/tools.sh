#! /bin/bash

INSTALL=$1

if [[ -z $INSTALL ]]; then
  echo "Please specify the installation path"
  exit 1
fi

# Golang
GOPATH="$INSTALL/golib"
export GOPATH
export PATH=$PATH:$INSTALL/go/bin:$GOPATH/bin

if [ ! -d "$GOPATH" ]; then
    mkdir "$GOPATH"
fi

if ! command -v go version &> /dev/null
then
    echo "Installing Golang..."
    wget https://go.dev/dl/go1.21.10.linux-amd64.tar.gz
    tar -C "$INSTALL" -xzf go1.21.10.linux-amd64.tar.gz
fi

# Nodejs
chmod +x ~/.bashrc
~/.bashrc

if ! command -v fnm --version &> /dev/null
then
    echo "Installing fnm..."
    # installs fnm (Fast Node Manager)
    curl -fsSL https://fnm.vercel.app/install | bash
    ~/.bashrc
fi

if ! command -v node --version &> /dev/null
then
    echo "Installing Nodejs..."
    fnm use --install-if-missing 22
fi

# Yarn
if ! command -v yarn --version &> /dev/null
then
    echo "Installing Yarn..."
    npm install -g yarn
fi
