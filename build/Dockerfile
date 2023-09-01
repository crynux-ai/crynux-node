FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as builder

RUN apt update
RUN apt install python3.10 python3.10-venv ffmpeg libsm6 libxext6 curl -y

RUN python3 -m venv /venv
ENV PATH="/venv/bin:${PATH}"

RUN curl -O -L "https://golang.org/dl/go1.21.0.linux-amd64.tar.gz" && tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
ENV PATH="${PATH}:/usr/local/go/bin"

WORKDIR /app

COPY remote-lora-scripts lora-scripts

WORKDIR /app/lora-scripts/sd-scripts
RUN pip install torch==2.0.0+cu118 torchvision==0.15.1+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
RUN pip install -r requirements.txt
RUN pip install lion-pytorch lycoris-lora dadaptation fastapi uvicorn wandb network==0.1 xformers==0.0.19 tensorrt==8.6.1

WORKDIR /app/lora-scripts

ENV LD_LIBRARY_PATH="/venv/lib/python3.10/site-packages/tensorrt_libs:${LD_LIBRARY_PATH}"
ENV LD_LIBRARY_PATH="/venv/lib/python3.10/site-packages/torch/lib:${LD_LIBRARY_PATH}"
RUN ln -s /venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer.so.8 /venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer.so.7 && \ 
    ln -s /venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer_plugin.so.8 /venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer_plugin.so.7 && \
    ln -s /venv/lib/python3.10/site-packages/torch/lib/libnvrtc-672ee683.so.11.2 /venv/lib/python3.10/site-packages/torch/lib/libnvrtc.so

WORKDIR /app/lora-runner

COPY src src
COPY pyproject.toml pyproject.toml
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt && pip install .


FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

RUN apt update
RUN apt install python3.10 ffmpeg libsm6 libxext6 -y

WORKDIR /app

COPY remote-lora-scripts lora-scripts

COPY prefetch.py prefetch.py

COPY --from=builder /venv /venv
ENV PATH="/venv/bin:${PATH}"

ENV HF_HOME="/app/lora-scripts/huggingface"
RUN python3 prefetch.py

ENV H_SERVER_CONFIG=/app/data/config.yml

ENTRYPOINT ["python3", "-m", "h_server.main"]
