from lora_runner.server.response import response_data
from lora_runner.config import config


def get_node_info():
    return response_data({
        "node_name": config["node"]["name"],
        "node_type": config["node"]["type"],
        "node_capabilities": config["node"]["capabilities"],
        "node_version": config["node"]["version"]
    })
