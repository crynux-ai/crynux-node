FROM server_base:dev

WORKDIR /app
COPY . .

EXPOSE 5025

ENTRYPOINT gunicorn -c build/data/gunicorn.conf.py 'lora_runner:app'
