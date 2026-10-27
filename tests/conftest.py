import pytest
import os

# Force development env so it doesn't try to connect to prod PostgreSQL
os.environ['FLASK_ENV'] = 'development'
os.environ['DB_ENGINE'] = ''
os.environ['DB_NAME'] = ''

from apps import create_app, db as _db
from apps.config import config_dict

@pytest.fixture(scope='session')
def app():
    app_config = config_dict['Debug']
    app = create_app(app_config)
    
    # Override configuration for testing
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db',
        'WTF_CSRF_ENABLED': False,
    })
    
    with app.app_context():
        yield app

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def db(app):
    with app.app_context():
        from apps.authentication.models import Users, Role
        from apps.profiles.models import Influencer
        from apps.social.models import Platform, SocialAccount, SocialPost
        from apps.reports.models import ScanResults, ScanLog
        from apps.saas.models import Agency, Plan, Subscription, Campaign, Shortlist
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()
        
        # Clear flask.g to prevent leaking state (like current_user) across requests
        # since the app_context is session-scoped in this test suite.
        from flask import g
        g.pop('_login_user', None)
