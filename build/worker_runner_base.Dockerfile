FROM worker_base:dev

COPY . /app/lora-runner
WORKDIR /app/lora-runner

RUN /usr/bin/python3.10 -m venv venv
RUN . ./venv/bin/activate && pip install -r requirements.txt
