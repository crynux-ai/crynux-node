#!/bin/bash

./build/macos/prepare.sh ./build/crynux_node

cd ./build/crynux_node
./package.sh
