import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.dev'))

from apps.config import config_dict
app_config = config_dict['Debug']

from apps import create_app, db
from apps.authentication.models import Users
app = create_app(app_config)

with app.app_context():
    try:
        admin_user = Users.query.filter_by(username='admin').first()
        if admin_user:
            admin_user.role = 'admin'
            db.session.commit()
            print("Admin user role set to admin.")
    except Exception as e:
        print("Error:", e)
        db.session.rollback()
