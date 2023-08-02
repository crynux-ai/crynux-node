from urllib.request import urlopen
from mimetypes import guess_extension, guess_type
from lora_runner.config import config
from flask_expects_json import expects_json
from flask import g, request
from lora_runner.server.response import *
from lora_runner.tasks import celery_app, sd_lora_inference
import os
import base64
import uuid


def get_model(model_id):
    model_file = os.path.join(
        config["data_dir"],
        "model",
        model_id,
        "character.safetensors"
    )

    if os.path.isfile(model_file):
        return response_data({
            'model_id': model_id,
            'cached': True
        })
    else:
        return response_validation_error("model_id", "model not found")


def upload_model():
    client_id = request.form.get("client_id")

    if client_id is None:
        return response_validation_error("client_id", "client_id is required")

    if "file" not in request.files:
        return response_validation_error("file", "no_file_uploaded")

    file = request.files["file"]

    if file is None or file.filename is None or file.filename == "":
        return response_validation_error("file", "no_file_uploaded")

    file_ext = file.filename.rsplit(".", 1)[1].lower()

    if file_ext not in ["safetensors"]:
        return response_validation_error("file", "invalid_file_type")

    model_id = str(uuid.uuid4())

    model_path = os.path.join(
        config["data_dir"],
        "model",
        model_id
    )

    if not os.path.isdir(model_path):
        os.mkdir(model_path)

    file.save(os.path.join(model_path, "character.safetensors"))

    return response_data({
        'model_id': model_id,
        'cached': True
    })


task_config_schema = {
    'type': 'object',
    'properties': {
        'model_id': {'type': 'string'},
        'pretrained_model_name': {'type': 'string'},
        'prompts': {'type': 'string'},
        'negative_prompts': {'type': 'string', 'default': ''},
        'pose': {
            'type': 'object',
            'properties': {
                'dataURL': {'type': 'string', 'default': ''},
                'preprocess': {'type': 'boolean', 'default': False}
            }
        },
        'config': {
            'type': 'object',
            'properties': {
                'steps': {'type': 'integer', 'default': 40},
                'weight': {'type': 'integer', 'default': 1},
                'image_width': {'type': 'integer', 'default': 768},
                'image_height': {'type': 'integer', 'default': 1024},
                'num_images': {'type': 'integer', 'default': 6},
                'pose_weight': {'type': 'number', 'default': 1},
                'seed': {'type': 'number', 'default': 0}
            }
        }
    },
    'required': ['model_id', 'pretrained_model_name', 'prompts', 'config', 'pose']
}


@expects_json(task_config_schema, fill_defaults=True)
def create_inference_task(model_id):
    prompts = g.data["prompts"]
    negative_prompts = g.data["negative_prompts"]
    pretrained_model_name = g.data["pretrained_model_name"]
    pose = g.data["pose"]
    task_config = g.data["config"]

    pretrained_model = os.path.join(config["pretrained_models_dir"], pretrained_model_name,
                                    pretrained_model_name + ".ckpt")

    if not os.path.isfile(pretrained_model):
        return response_validation_error("pretrained_model_name", "pretrained model not found")

    model_file = os.path.join(
        config["data_dir"],
        "model",
        model_id,
        "character.safetensors"
    )

    if not os.path.isfile(model_file):
        return response_validation_error("model_id", "model not found")

    task_id = str(uuid.uuid4())

    image_folder = os.path.join(
        config["data_dir"],
        "image",
        task_id
    )

    if not os.path.isdir(image_folder):
        os.mkdir(image_folder)

    use_pose = False
    if pose["dataURL"] != "":
        file_ext = guess_extension(guess_type(pose["dataURL"])[0])

        response = urlopen(pose["dataURL"])
        pose_file = os.path.join(image_folder, 'pose' + file_ext)
        with open(pose_file, 'wb') as fd:
            fd.write(response.file.read())
            fd.close()
            use_pose = True

    task = celery_app.send_task(
        "sd_lora_inference", (
            model_id,
            pretrained_model_name,
            prompts,
            negative_prompts,
            {
                'use_pose': use_pose,
                'preprocess': pose["preprocess"]
            },
            task_config),
        task_id=task_id
    )

    return response_data({
        "task_id": task.task_id
    })


def get_task_state(task_id):
    task = sd_lora_inference.AsyncResult(task_id)

    return response_data({
        "task_id": task_id,
        "status": task.status
    })


def get_task_image(task_id, image_num):
    image_folder = os.path.join(
        config["data_dir"],
        "image",
        task_id
    )

    current_num = 0
    image_num_int = int(image_num)

    for file in os.listdir(image_folder):
        if file.endswith('.png') and not file.startswith("pose"):

            if image_num_int != current_num:
                current_num += 1
                continue

            file_path = os.path.join(image_folder, file)
            binary_fc = open(file_path, 'rb').read()
            base64_utf8_str = base64.b64encode(binary_fc).decode('utf-8')
            dataurl = f'data:image/png;base64,{base64_utf8_str}'

            return response_data({
                'dataurl': dataurl
            })

    return response_not_found()


def get_task_log(task_id):
    start_line = 0

    if "start_line" in request.args and request.args["start_line"].isnumeric():
        start_line = int(request.args["start_line"])

    task_log_file = os.path.join(config["inference_logs_dir"], task_id + ".log")

    if not os.path.isfile(task_log_file):
        return ""

    with open(task_log_file, "r") as fp:
        lines = fp.readlines()

    return response_data(lines[start_line:])


def stop_task(task_id):
    task = sd_lora_inference.AsyncResult(task_id)

    if task:
        task.revoke(terminate=True)

    return response_data({})
