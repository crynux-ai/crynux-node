FROM nvcr.io/nvidia/pytorch:23.05-py3

RUN apt update
RUN apt install ffmpeg libsm6 libxext6 -y

WORKDIR /app

COPY remote-lora-scripts lora-scripts

WORKDIR /app/lora-scripts

WORKDIR /app/lora-scripts/sd-scripts
RUN pip3 install -r requirements.txt
RUN pip3 install lion-pytorch lycoris-lora dadaptation fastapi uvicorn wandb network==0.1 xformers==0.0.19

WORKDIR /app/lora-scripts
COPY ./lora-scripts/* ./

ENV LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}"
RUN ln -s /usr/lib/x86_64-linux-gnu/libnvinfer.so.8 /usr/lib/x86_64-linux-gnu/libnvinfer.so.7
RUN ln -s /usr/lib/x86_64-linux-gnu/libnvinfer_plugin.so.8 /usr/lib/x86_64-linux-gnu/libnvinfer_plugin.so.7
RUN chmod +x train.sh && chmod +x inference.sh && chmod +x prefetch.sh && ./prefetch.sh

WORKDIR /app/lora-runner
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY lora_runner lora_runner
CMD celery -A lora_runner.tasks worker -l INFO