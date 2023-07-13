from flask import Blueprint
from .controller import *

sd_lora_inference_routes = Blueprint("sd_lora_inference", __name__)

sd_lora_inference_routes.route("/models/<model_id>", methods=["GET"])(get_model)
sd_lora_inference_routes.route("/models", methods=["POST"])(upload_model)
sd_lora_inference_routes.route("/models/<model_id>/inference_tasks", methods=["POST"])(create_inference_task)
sd_lora_inference_routes.route("/models/inference_tasks/<task_id>", methods=["GET"])(get_task_state)
sd_lora_inference_routes.route("/models/inference_tasks/<task_id>", methods=["DELETE"])(stop_task)
sd_lora_inference_routes.route("/models/inference_tasks/<task_id>/images/<image_num>", methods=["GET"])(get_task_image)
sd_lora_inference_routes.route("/models/inference_tasks/<task_id>/logs", methods=["GET"])(get_task_log)
