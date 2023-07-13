FROM python:3.10

WORKDIR /app/lora-runner
COPY . .

RUN pip install -r requirements.txt
