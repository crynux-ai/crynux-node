from .celery_app import celery_app
from .task_common import env_vars_to_cmd_str
from lora_runner.config import config
import os


@celery_app.task(bind=True, name="sd_lora_inference", track_started=True)
def sd_lora_inference(
        self,
        model_id,
        pretrained_model_name,
        prompts,
        negative_prompts,
        pose,
        task_config):

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
        "PROMPTS": merged_prompts,
        "STEPS": task_config["steps"],
        "MODEL_FILE": model_file,
        "MODEL_WEIGHT": task_config["weight"],
        "IMAGE_WIDTH": task_config["image_width"],
        "IMAGE_HEIGHT": task_config["image_height"],
        "NUM_IMAGES": task_config["num_images"],
        "POSE_WEIGHT": task_config["pose_weight"]
    }

    if pose["use_pose"]:
        openpose_model_file = os.path.join(
            config["controlnet_models_dir"],
            "control_v11p_sd15_openpose.pth"
        )

        pose_image_file = ""

        for file in os.listdir(image_output_dir):
            if file.startswith("pose"):
                pose_image_file = os.path.join(image_output_dir, file)

        if os.path.isfile(openpose_model_file) and pose_image_file != "":
            env_vars['POSE_IMAGE'] = pose_image_file
            env_vars['POSE_PREPROCESS'] = 1 if pose['preprocess'] else 0
            env_vars['CONTROLNET_MODEL'] = openpose_model_file

    cmd = env_vars_to_cmd_str(env_vars)
    cmd = cmd + " && cd /app/lora-scripts && . ./venv/bin/activate && ./inference.sh"
    cmd = cmd + ' >> "' + log_file + '" 2>&1'

    status = os.system(cmd)

    if os.WIFEXITED(status):
        if os.WEXITSTATUS(status) != 0:
            raise Exception("inference process exited with error")
    else:
        raise Exception("inference process did not exit normally")
