FROM node:18-buster-slim as web-builder

WORKDIR /app

COPY src/webui /app/
RUN mv src/config.example.json src/config.json

RUN yarn && yarn build

FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as base

RUN apt update
RUN apt install python3.10 python3.10-venv ffmpeg libsm6 libxext6 -y

FROM base as builder1

RUN apt install curl -y

RUN curl -O -L "https://golang.org/dl/go1.21.0.linux-amd64.tar.gz" && tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
ENV PATH="${PATH}:/usr/local/go/bin"

WORKDIR /app

RUN python3 -m venv venv
ENV PATH="/app/venv/bin:${PATH}"

WORKDIR /app/h-node

COPY src src
COPY pyproject.toml pyproject.toml
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt && pip install .

FROM base as builder2

WORKDIR /app

COPY remote-lora-scripts lora-scripts

WORKDIR /app/lora-scripts

RUN python3 -m venv venv
ENV PATH="/app/lora-scripts/venv/bin:${PATH}"

WORKDIR /app/lora-scripts/sd-scripts
RUN pip install torch==2.0.0+cu118 torchvision==0.15.1+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
RUN pip install -r requirements.txt
RUN pip install lion-pytorch lycoris-lora dadaptation fastapi uvicorn wandb network==0.1 xformers==0.0.19 tensorrt==8.6.1

FROM base as final

COPY --from=builder1 /app/venv /app/venv
COPY --from=builder2 /app/lora-scripts /app/lora-scripts

ENV PATH="/app/venv/bin:${PATH}"

ENV LD_LIBRARY_PATH="/app/lora-scripts/venv/lib/python3.10/site-packages/tensorrt_libs:${LD_LIBRARY_PATH}"
ENV LD_LIBRARY_PATH="/app/lora-scripts/venv/lib/python3.10/site-packages/torch/lib:${LD_LIBRARY_PATH}"

WORKDIR /app/lora-scripts
RUN ln -s venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer.so.8 venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer.so.7 && \ 
    ln -s venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer_plugin.so.8 venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer_plugin.so.7 && \
    ln -s venv/lib/python3.10/site-packages/torch/lib/libnvrtc-672ee683.so.11.2 venv/lib/python3.10/site-packages/torch/lib/libnvrtc.so

WORKDIR /app

COPY build/data/ data/
RUN mv data/config.yml.example config.yml
COPY --from=web-builder /app/dist/ dist/

ENV H_SERVER_CONFIG="/app/config.yml"

ENTRYPOINT ["python3", "-m", "h_server.main"]
