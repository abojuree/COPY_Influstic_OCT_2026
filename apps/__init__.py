import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from importlib import import_module
from icecream import ic

db = SQLAlchemy()
login_manager = LoginManager()


def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)


def register_blueprints(app):
    for module_name in ('authentication', 'home', 'social', 'profiles', 'reports', 'globals', 'health', 'saas'):
        module = import_module('apps.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)


def configure_database(app):

    # Import all models so SQLAlchemy registers them before create_all()
    import apps.saas.models  # noqa: F401 — Agency, Subscription, Shortlist

    # @app.before_first_request
    def initialize_database():
        try:
            db.create_all()
        except Exception as e:

            ic('DBMS Exception: ',str(e) )

            # fallback to SQLite
            basedir = os.path.abspath(os.path.dirname(__file__))
            app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'db.sqlite3')

            ic('Fallback to SQLite ')
            db.create_all()

    # Removed teardown_request for db.session.remove() because Flask-SQLAlchemy 
    # handles this automatically on teardown_appcontext.


def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    register_extensions(app)
    register_blueprints(app)
    configure_database(app)
    return app
