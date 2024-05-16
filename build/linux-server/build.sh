#!/bin/bash

PROJECT_ROOT=${pwd}
./build/linux-server/prepare.sh -w build/crynux_node

cd build/crynux_node
./package.sh

cd $PROJECT_ROOT
