from flask import Blueprint

blueprint = Blueprint(
    'saas_blueprint',
    __name__,
    url_prefix='/saas'
)
