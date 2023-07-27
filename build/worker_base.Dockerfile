FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

RUN apt update
RUN apt install python3.10 python3.10-venv git ffmpeg libsm6 libxext6 -y

WORKDIR /app

RUN git clone --recurse-submodules --depth 1 --branch v1.1.0 https://github.com/Akegarasu/lora-scripts.git

WORKDIR /app/lora-scripts

RUN chmod +x ./install.bash
RUN ./install.bash

RUN . ./venv/bin/activate && pip install tensorrt==8.6.1 network==0.1

WORKDIR /app/lora-scripts/venv/lib/python3.10/site-packages/tensorrt_libs
RUN ln -s libnvinfer.so.8 libnvinfer.so.7
RUN ln -s libnvinfer_plugin.so.8 libnvinfer_plugin.so.7

WORKDIR /app/lora-scripts

COPY ./lora-scripts/* .

RUN chmod +x train.sh && chmod +x inference.sh && chmod +x prefetch.sh
RUN . ./venv/bin/activate && ./prefetch.sh
