from lora_runner.tasks.celery_app import celery_app
from lora_runner.tasks.sd_lora_training import sd_lora_training
from flask import request, g, send_file
from lora_runner.config import config
from lora_runner.server import response
from flask_expects_json import expects_json
import os


def upload_dataset():
    client_id = request.form.get("client_id")
    dataset_id = request.form.get("dataset_id")

    if client_id is None:
        return response.response_validation_error("client_id", "client_id is required")

    if dataset_id is None:
        return response.response_validation_error("dataset_id", "dataset_id is required")

    if "file" not in request.files:
        return response.response_validation_error("file", "no_file_uploaded")

    file = request.files["file"]

    if file is None or file.filename is None or file.filename == "":
        return response.response_validation_error("file", "no_file_uploaded")

    file_ext = file.filename.rsplit(".", 1)[1].lower()

    if file_ext not in ["txt", "jpg", "png", "bmp", "jpeg"]:
        return response.response_validation_error("file", "invalid_file_type")

    dataset_images_folder = os.path.join(
        config["data_dir"],
        "dataset",
        client_id,
        dataset_id,
        "2_character"
    )
    if not os.path.isdir(dataset_images_folder):
        os.makedirs(dataset_images_folder)

    file.save(os.path.join(dataset_images_folder, file.filename))

    return response.response_data({})


task_config_schema = {
    'type': 'object',
    'properties': {
        'client_id': {'type': 'string'},
        'dataset_id': {'type': 'string'},
        'pretrained_model_name': {'type': 'string'},
        'config': {
            'type': 'object',
            'properties': {
                'image_width': {'type': 'integer', 'default': 768},
                'image_height': {'type': 'integer', 'default': 768},
                'epoch': {'type': 'integer', 'default': 10},
                'batch_size': {'type': 'integer', 'default': 5},
                'network_dimension': {'type': 'integer', 'default': 32},
                'learning_rate': {'type': 'string', 'default': "5e-5"},
                'optimizer': {'type': 'string', 'default': 'AdamW'}
            }
        }
    },
    'required': ['client_id', 'dataset_id', 'pretrained_model_name', 'config']
}


@expects_json(task_config_schema, fill_defaults=True)
def create_task():

    client_id = g.data["client_id"]
    dataset_id = g.data["dataset_id"]
    pretrained_model_name = g.data["pretrained_model_name"]
    task_config = g.data["config"]

    pretrained_model = os.path.join(config["pretrained_models_dir"], pretrained_model_name, pretrained_model_name + ".ckpt")

    if not os.path.isfile(pretrained_model):
        return response.response_validation_error("pretrained_model_name", "pretrained model not found")

    dataset_folder = os.path.join(
        config["data_dir"],
        "dataset",
        client_id,
        dataset_id
    )

    if not os.path.isdir(dataset_folder):
        return response.response_validation_error("dataset_id", "dataset not found")

    task = celery_app.send_task(
        "sd_lora_training", (client_id, dataset_id, pretrained_model_name, task_config)
    )

    return response.response_data({
        "task_id": task.task_id
    })


def stop_task(task_id):
    task = sd_lora_training.AsyncResult(task_id)

    if task:
        task.revoke(terminate=True)

    return response.response_data({})


def get_task_state(task_id):
    task = sd_lora_training.AsyncResult(task_id)

    return response.response_data({
        "task_id": task_id,
        "status": task.status
    })


def get_task_log(task_id):

    start_line = 0

    if "start_line" in request.args and request.args["start_line"].isnumeric():
        start_line = int(request.args["start_line"])

    task_log_file = os.path.join(config["training_logs_dir"], task_id + ".log")

    if not os.path.isfile(task_log_file):
        return ""

    with open(task_log_file, "r") as fp:
        lines = fp.readlines()

    return response.response_data(lines[start_line:])


def download_model(task_id):

    model_dir = os.path.join(
        config["data_dir"],
        "model",
        task_id
    )

    model_path = os.path.join(
        model_dir,
        "character.safetensors"
    )

    if os.path.isfile(model_path):
        return send_file(os.path.abspath(model_path), as_attachment=True)
    else:
        return response.response_not_found()
