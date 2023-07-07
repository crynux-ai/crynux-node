FROM worker_runner_base:dev

COPY . /app/lora-runner
COPY ./lora-scripts/train.sh /app/lora-scripts/train.sh
COPY ./lora-scripts/inference.sh /app/lora-scripts/inference.sh

WORKDIR /app/lora-runner
CMD . ./venv/bin/activate && celery -A lora_runner.tasks worker -l INFO
