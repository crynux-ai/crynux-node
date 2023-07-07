from .celery_app import celery_app
from lora_runner.config import config
import os


@celery_app.task(bind=True, name="sd_lora_inference", track_started=True)
def sd_lora_inference(self, model_id, pretrained_model_name, prompts, negative_prompts, pose, task_config):

    log_file = os.path.join(config["inference_logs_dir"], self.request.id + ".log")
    merged_prompts = prompts + " --n " + negative_prompts

    pretrained_model = os.path.join(
        config["pretrained_models_dir"],
        pretrained_model_name,
        pretrained_model_name + ".ckpt"
    )

    model_file = os.path.join(
        config["data_dir"],
        "model",
        model_id,
        "character.safetensors"
    )

    image_output_dir = os.path.join(
        config["data_dir"],
        "image",
        self.request.id
    )

    if not os.path.exists(image_output_dir):
        os.mkdir(image_output_dir)

    env_vars = {
        "PRETRAINED_MODEL": pretrained_model,
        "OUTPUT_DIR": image_output_dir,
        "PROMPT": merged_prompts,
        "STEPS": task_config["steps"],
        "MODEL_FILE": model_file,
        "MODEL_WEIGHT": task_config["weight"],
    }

    cmd = "export"

    for var in env_vars.keys():

        if isinstance(env_vars[var], int):
            value = str(env_vars[var])
        else:
            value = '"' + env_vars[var] + '"'

        cmd = cmd + " " + var + '=' + value

    cmd = cmd + " && cd /app/lora-scripts && . ./venv/bin/activate && ./inference.sh"
    cmd = cmd + ' >> "' + log_file + '" 2>&1'

    status = os.system(cmd)

    if os.WIFEXITED(status):
        if os.WEXITSTATUS(status) != 0:
            raise Exception("inference process exited with error")
    else:
        raise Exception("inference process did not exit normally")
