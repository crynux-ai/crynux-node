#!/bin/bash

source ~/.virutalenv/lora-runner/bin/activate
gunicorn -c data/gunicorn.conf.py 'lora_runner:app'

