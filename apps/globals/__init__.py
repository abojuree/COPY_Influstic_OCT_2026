from flask import Blueprint

blueprint = Blueprint(
    'globals_blueprint',
    __name__,
    url_prefix=''
)
