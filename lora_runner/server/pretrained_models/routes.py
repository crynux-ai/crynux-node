from flask import Blueprint
from .controller import list_pretrained_models

pretrained_models_routes = Blueprint("pretrained_models", __name__)

pretrained_models_routes.route("/", methods=["GET"])(list_pretrained_models)
