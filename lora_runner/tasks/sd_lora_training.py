from .celery_app import celery_app
from lora_runner.config import config
import os


@celery_app.task(bind=True, name="sd_lora_training", track_started=True)
def sd_lora_training(self, client_id, dataset_id, pretrained_model_name, task_config):

    # dataset folder
    dataset_folder = os.path.join(
        config["data_dir"],
        "dataset",
        client_id,
        dataset_id
    )

    # model output folder
    model_folder = os.path.join(
        config["data_dir"],
        "model",
        self.request.id
    )

    if not os.path.exists(model_folder):
        os.mkdir(model_folder)

    log_file = os.path.join(config["training_logs_dir"], self.request.id + ".log")

    epoch = task_config["epoch"]

    # start lora-script
    cmd = 'export PRETRAINED_MODEL="'\
          + os.path.join(
                config["pretrained_models_dir"],
                pretrained_model_name,
                pretrained_model_name + ".ckpt"
            ) + '"'
    cmd = cmd + ' DATASET_DIR="' + dataset_folder + '"'
    cmd = cmd + ' OUTPUT_DIR="' + model_folder + '"'
    cmd = cmd + ' EPOCH=' + str(epoch)
    cmd = cmd + " && cd /app/lora-scripts && . ./venv/bin/activate && ./train.sh"
    cmd = cmd + ' >> "' + log_file + '" 2>&1'

    status = os.system(cmd)

    if os.WIFEXITED(status):
        if os.WEXITSTATUS(status) != 0:
            raise Exception("training process exited with error")
    else:
        raise Exception("training process did not exit normally")

