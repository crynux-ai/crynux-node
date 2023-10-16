FROM node:18-buster-slim as web-builder

WORKDIR /app

COPY src/webui /app/
RUN mv src/config.example.json src/config.json

RUN yarn && yarn build

FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as base

RUN apt update
RUN apt install python3.10 python3.10-venv ffmpeg libsm6 libxext6 -y

FROM base as builder1

RUN apt install curl build-essential libssl-dev libffi-dev python3.10-dev -y

RUN curl -O -L "https://golang.org/dl/go1.21.0.linux-amd64.tar.gz" && tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
ENV PATH="${PATH}:/usr/local/go/bin"
ENV CGO_ENABLED="1"

WORKDIR /app

RUN python3 -m venv venv
ENV PATH="/app/venv/bin:${PATH}"

WORKDIR /app/h-node

COPY src src
COPY pyproject.toml pyproject.toml
COPY setup.py setup.py
COPY requirements.txt requirements.txt
COPY MANIFEST.in MANIFEST.in
COPY go.mod go.mod
COPY go.sum go.sum
RUN pip install -r requirements.txt && pip install .

FROM base as builder2

WORKDIR /app

COPY stable-diffusion-task stable-diffusion-task

WORKDIR /app/stable-diffusion-task

RUN python3 -m venv venv
ENV PATH="/app/stable-diffusion-task/venv/bin:${PATH}"

RUN pip install -r requirements.txt
RUN pip install .
RUN pip uinstall opencv-python opencv-contrib-python && pip install opencv-contrib-python

FROM base as final

COPY --from=builder1 /app/venv /app/venv
COPY --from=builder2 /app/stable-diffusion-task /app/stable-diffusion-task
COPY src/prefetch.py /app/stable-diffusion-task/prefetch.py
COPY src/inference.py /app/stable-diffusion-task/inference.py

ENV PATH="/app/venv/bin:${PATH}"

ENV LD_LIBRARY_PATH="/app/stable-diffusion-task/venv/lib/python3.10/site-packages/torch/lib:${LD_LIBRARY_PATH}"

RUN ln -s /app/stable-diffusion-task/venv/lib/python3.10/site-packages/torch/lib/libnvrtc-672ee683.so.11.2 /app/stable-diffusion-task/venv/lib/python3.10/site-packages/torch/lib/libnvrtc.so

WORKDIR /app

COPY build/data/ data/
COPY build/config.yml.example config.yml
COPY --from=web-builder /app/dist/ dist/

ENV H_SERVER_CONFIG="/app/config.yml"

ENTRYPOINT ["python3", "-m", "h_server.main"]
