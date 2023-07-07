FROM python:3.10

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

EXPOSE 5025

ENTRYPOINT gunicorn -c data/gunicorn.conf.py 'lora_runner:app'
