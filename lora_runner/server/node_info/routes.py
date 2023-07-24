from flask import Blueprint
from .controller import get_node_info

node_info_routes = Blueprint("node_info", __name__)

node_info_routes.route("", methods=["GET"])(get_node_info)
