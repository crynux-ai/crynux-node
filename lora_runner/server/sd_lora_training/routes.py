from flask import Blueprint
from .controller import *

sd_lora_training_routes = Blueprint("sd_lora_training", __name__)

sd_lora_training_routes.route("", methods=["POST"])(create_task)
sd_lora_training_routes.route("/<task_id>", methods=["GET"])(get_task_state)
sd_lora_training_routes.route("/<task_id>", methods=["DELETE"])(stop_task)
sd_lora_training_routes.route("/<task_id>/logs", methods=["GET"])(get_task_log)
sd_lora_training_routes.route("/dataset", methods=["POST"])(upload_dataset)
sd_lora_training_routes.route("/<task_id>/model", methods=["GET"])(download_model)
