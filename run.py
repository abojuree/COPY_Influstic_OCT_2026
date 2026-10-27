import os

from flask_migrate import Migrate
# from flask_minify  import Minify
from sys import exit

from apps.config import config_dict

# Configure icecream before importing any modules that use it
from ic_config import configure_icecream
configure_icecream()

from apps import create_app, db

from icecream import ic
from dotenv import load_dotenv


# dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
# load_dotenv(dotenv_path)

# Determine the environment and load the appropriate .env file
basedir = os.path.dirname(__file__)
if os.getenv("FLASK_ENV") == "production":
    dotenv_path = os.path.join(basedir, ".env.prod")
else:
    dotenv_path = os.path.join(basedir, ".env.dev")
load_dotenv(dotenv_path)

# WARNING: Don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG_MODE", "False") == "True"

# The configuration
get_config_mode = 'Debug' if DEBUG else 'Production'

ic(get_config_mode)

try:
    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]
except KeyError as e:
    msg = f"Error: Invalid <config_mode>. Expected values [Debug, Production], {e} "
    ic(msg)
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production] ')

app = create_app(app_config)
Migrate(app, db)

# if not DEBUG:
#     Minify(app=app, html=True, js=False, cssless=False)
if DEBUG:
    app.logger.info('DEBUG            = ' + str(DEBUG)             )
    app.logger.info('Page Compression = ' + 'FALSE' if DEBUG else 'TRUE' )
    app.logger.info('DBMS             = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT      = ' + app_config.ASSETS_ROOT )

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, use_reloader=DEBUG, debug=DEBUG)
