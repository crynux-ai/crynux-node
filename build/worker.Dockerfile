FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

RUN apt update
RUN apt install python3.10 python3.10-venv ffmpeg libsm6 libxext6 -y

RUN python3 -m venv /venv
ENV PATH="/venv/bin:${PATH}"

WORKDIR /app

COPY remote-lora-scripts lora-scripts

WORKDIR /app/lora-scripts/sd-scripts
RUN pip install torch==2.0.0+cu118 torchvision==0.15.1+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
RUN pip install -r requirements.txt
RUN pip install lion-pytorch lycoris-lora dadaptation fastapi uvicorn wandb network==0.1 xformers==0.0.19 tensorrt==8.6.1

WORKDIR /app/lora-scripts
COPY ./lora-scripts/* ./

ENV LD_LIBRARY_PATH="/venv/lib/python3.10/site-packages/tensorrt_libs:${LD_LIBRARY_PATH}"
RUN ln -s /venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer.so.8 /venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer.so.7 && \ 
    ln -s /venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer_plugin.so.8 /venv/lib/python3.10/site-packages/tensorrt_libs/libnvinfer_plugin.so.7
RUN chmod +x train.sh && chmod +x inference.sh && chmod +x prefetch.sh && ./prefetch.sh

WORKDIR /app/lora-runner
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY lora_runner lora_runner
CMD celery -A lora_runner.tasks worker -l INFO