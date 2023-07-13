FROM server_base:dev

WORKDIR /app/lora-runner
COPY . .

EXPOSE 5025

ENTRYPOINT gunicorn -c /app/lora-runner/data/gunicorn.conf.py 'lora_runner:app'
