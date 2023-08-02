FROM python:3.10-alpine

WORKDIR /app/lora-runner
COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY lora_runner lora_runner

EXPOSE 5025
ENTRYPOINT gunicorn -c /app/lora-runner/data/gunicorn.conf.py 'lora_runner:app'