from .celery_app import celery_app
from lora_runner.config import config
from .task_common import env_vars_to_cmd_str, print_cuda_info
import os


@celery_app.task(bind=True, name="sd_lora_training", track_started=True)
def sd_lora_training(self, client_id, dataset_id, pretrained_model_name, task_config):

    # pretrained model
    pretrained_model = os.path.join(
                config["pretrained_models_dir"],
                pretrained_model_name,
                pretrained_model_name + ".ckpt"
            )

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

    print_cuda_info(log_file)

    env_vars = {
        "PRETRAINED_MODEL": pretrained_model,
        "DATASET_DIR": dataset_folder,
        "OUTPUT_DIR": model_folder,
        "EPOCH": task_config["epoch"],
        "IMAGE_WIDTH": task_config["image_width"],
        "IMAGE_HEIGHT": task_config["image_height"],
        "BATCH_SIZE": task_config["batch_size"],
        "NETWORK_DIMENSION": task_config["network_dimension"],
        "LEARNING_RATE": task_config["learning_rate"],
        "OPTIMIZER": task_config["optimizer"],
    }

    # start lora-script
    cmd = env_vars_to_cmd_str(env_vars)
    cmd = cmd + " && cd /app/lora-scripts && ./train.sh"
    cmd = cmd + ' >> "' + log_file + '" 2>&1'

    status = os.system(cmd)

    if os.WIFEXITED(status):
        if os.WEXITSTATUS(status) != 0:
            raise Exception("training process exited with error")
    else:
        raise Exception("training process did not exit normally")
