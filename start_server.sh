#!/bin/bash

gunicorn -c build/data/gunicorn.conf.py 'lora_runner:app' --worker-tmp-dir /tmp

