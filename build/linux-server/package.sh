#!/bin/bash
# Example call: ./package.sh

## Package the worker
source worker/venv/bin/activate
# change in controlnet_aux/zoe/zoedepth/models/layers/attractor.py
TAR_FILE=worker/venv/lib/python3.10/site-packages/controlnet_aux/zoe/zoedepth/models/layers/attractor.py
sed -i.bak "s/@torch.jit.script/#@torch.jit.script/g" $TAR_FILE

pyinstaller crynux_worker_process.spec

## Package the node
## The worker, webui, res, data will be collected into the node package
## as described in the crynux.spec file

source venv/bin/activate
pyinstaller crynux.spec
