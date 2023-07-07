from flask import Flask
from flask_cors import CORS
from .sd_lora_training.routes import sd_lora_training_routes
from .sd_lora_inference.routes import sd_lora_inference_routes
from .node_info.routes import node_info_routes
from .pretrained_models.routes import pretrained_models_routes
from .response import handle_default_400


def create_server():
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(sd_lora_training_routes, url_prefix="/v1/sd_lora_training")
    app.register_blueprint(sd_lora_inference_routes, url_prefix="/v1/sd_lora_inference")
    app.register_blueprint(node_info_routes, url_prefix="/v1/node")
    app.register_blueprint(pretrained_models_routes, url_prefix="/v1/pretrained_models")
    app.register_error_handler(400, handle_default_400)

    return app
