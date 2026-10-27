from flask import Blueprint

blueprint = Blueprint(
    'health_blueprint',
    __name__,
    url_prefix=''
)
