from flask import Blueprint

"""This is the authentication blueprint module."""
blueprint = Blueprint(
    'authentication_blueprint',
    __name__,
    url_prefix=''
)
