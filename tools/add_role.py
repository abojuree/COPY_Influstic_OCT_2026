import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.dev'))

from apps.config import config_dict
app_config = config_dict['Debug']

from apps import create_app, db
from sqlalchemy import text
app = create_app(app_config)

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE "Users" ADD COLUMN role VARCHAR(20) DEFAULT \'user\''))
        db.session.commit()
        print("Role column added.")
    except Exception as e:
        print("Error:", e)
        db.session.rollback()
