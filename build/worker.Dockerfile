FROM worker_runner_base:dev

COPY . /app/lora-runner

WORKDIR /app/lora-runner
CMD . ./venv/bin/activate && celery -A lora_runner.tasks worker -l INFO
