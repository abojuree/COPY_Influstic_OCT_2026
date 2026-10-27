import unittest, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from apps import create_app, db
from apps.config import Config

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    DEBUG = True

from apps.authentication.models import Users
from apps.saas.models import Agency, Plan, Subscription, Shortlist
from apps.profiles.models import Influencer

class E2EFlowTestCase(unittest.TestCase):
    def setUp(self):
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['USE_SQLITE'] = 'True'
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            free_plan = Plan(name="Free", tracking_limit=2, price=0, is_active=True)
            db.session.add(free_plan)
            
            influencer = Influencer(full_name="test_influencer", email="test1@test.com")
            db.session.add(influencer)
            db.session.commit()

            self.test_username = 'test_agency_user'
            self.test_password = 'password123'
            self.test_email = 'test@agency.com'
    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_3_global_discovery_vs_isolated_shortlists(self):
        self.client.post('/register', data={'username': self.test_username, 'email': self.test_email, 'password': self.test_password, 'register': 'True'})
        self.client.post('/login', data={'username': self.test_username, 'password': self.test_password, 'login': 'True'})
        
        response = self.client.get('/influencers')
        if b'test_influencer' in response.data:
            with open('tools/failed_output.html', 'wb') as f:
                f.write(response.data)

if __name__ == '__main__':
    unittest.main()
