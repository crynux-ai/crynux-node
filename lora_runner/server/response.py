from jsonschema import ValidationError


def handle_default_400(error):
    if isinstance(error.description, ValidationError):
        original_error = error.description
        return response_validation_error("", original_error.message)

    return error


def response_data(data):
    return data, 200


def response_validation_error(field, message):
    return {
        "field": field,
        "message": message
    }, 400


def response_internal_error():
    return {
        "message": "internal_server_error"
    }, 500


def response_not_found():
    return "404 not found", 404
