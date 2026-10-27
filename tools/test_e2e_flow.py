import os
import sys
import unittest
import uuid

# Add the parent directory to the path so we can import apps
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
        # Configure app for testing
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['USE_SQLITE'] = 'True'
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            
            # Create a Free Plan for registration to use
            free_plan = Plan(name="Free", tracking_limit=2, price=0, is_active=True)
            db.session.add(free_plan)
            
            # Create a mock Influencer globally
            influencer = Influencer(full_name="test_influencer", email="test1@test.com")
            influencer2 = Influencer(full_name="test_influencer2", email="test2@test.com")
            influencer3 = Influencer(full_name="test_influencer3", email="test3@test.com")
            db.session.add_all([influencer, influencer2, influencer3])
            
            # Create an admin user to verify routes
            from apps.authentication.util import verify_pass
            admin_user = Users(username='admin', email='admin@test.com', password='password123')
            db.session.add(admin_user)
            db.session.commit()

            self.test_email = f"test_{uuid.uuid4().hex[:6]}@example.com"
            self.test_username = f"agency_{uuid.uuid4().hex[:6]}"
            self.test_password = "Password123!"

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_1_registration_and_subscription(self):
        # Registration & Default Subscription
        response = self.client.post('/register', data={
            'username': self.test_username,
            'email': self.test_email,
            'password': self.test_password,
            'register': 'True'
        }, follow_redirects=True)
        
        self.assertIn(b'\xd8\xaa\xd9\x85 \xd8\xa5\xd8\xb6\xd8\xa7\xd9\x81\xd8\xa9 \xd8\xa7\xd9\x84\xd8\xad\xd8\xb3\xd8\xa7\xd8\xa8', response.data) # "Account added" in Arabic

        with self.app.app_context():
            user = Users.query.filter_by(username=self.test_username).first()
            self.assertIsNotNone(user, "User should be created")
            self.assertIsNotNone(user.agency_id, "User should be assigned to an agency")
            
            agency = Agency.query.get(user.agency_id)
            self.assertIsNotNone(agency, "Agency should be created")
            
            subscription = Subscription.query.filter_by(agency_id=agency.id, status='active').first()
            self.assertIsNotNone(subscription, "Active subscription should be created")
            self.assertIsNotNone(subscription.current_period_end, "current_period_end should not be null")

    def test_2_security_route_lockdown(self):
        # Register and Login
        self.client.post('/register', data={'username': self.test_username, 'email': self.test_email, 'password': self.test_password, 'register': 'True'})
        self.client.post('/login', data={'username': self.test_username, 'password': self.test_password, 'login': 'True'})

        # Attempt to access admin routes
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302, "Should return 302 Redirect for /admin")

        response = self.client.get('/admin/agencies')
        self.assertEqual(response.status_code, 302, "Should return 302 Redirect for /admin/agencies")

        response = self.client.get('/backup_db')
        self.assertEqual(response.status_code, 302, "Should return 302 Redirect for /backup_db")

    def test_3_global_discovery_vs_isolated_shortlists(self):
        self.client.post('/register', data={'username': self.test_username, 'email': self.test_email, 'password': self.test_password, 'register': 'True'})
        self.client.post('/login', data={'username': self.test_username, 'password': self.test_password, 'login': 'True'})

        # Global Discovery
        response = self.client.get('/discover')
        self.assertEqual(response.status_code, 200, "/discover should return 200 OK")
        self.assertIn(b'test_influencer', response.data, "Should see global influencers in discovery")

        # Isolated Shortlists (My Influencers)
        response = self.client.get('/influencers')
        self.assertEqual(response.status_code, 200, "/influencers should return 200 OK")
        self.assertNotIn(b'test_influencer', response.data, "Should NOT see influencers before adding to shortlists")

    def test_4_shortlist_creation_and_limit_enforcement(self):
        self.client.post('/register', data={'username': self.test_username, 'email': self.test_email, 'password': self.test_password, 'register': 'True'})
        self.client.post('/login', data={'username': self.test_username, 'password': self.test_password, 'login': 'True'})

        # Create Shortlist
        response = self.client.post('/saas/shortlists/create', data={
            'name': 'Campaign A',
            'description': 'Test campaign'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            user = Users.query.filter_by(username=self.test_username).first()
            shortlist = Shortlist.query.filter_by(agency_id=user.agency_id).first()
            self.assertIsNotNone(shortlist, "Shortlist should be created")
            shortlist_id = shortlist.id
            
            influencer1_id = Influencer.query.filter_by(full_name="test_influencer").first().id
            influencer2_id = Influencer.query.filter_by(full_name="test_influencer2").first().id
            influencer3_id = Influencer.query.filter_by(full_name="test_influencer3").first().id

        # Add influencer 1
        response = self.client.post(f'/saas/shortlist_influencer/add/{influencer1_id}', data={'shortlist_id': shortlist_id}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Check Isolated View (/influencers)
        response = self.client.get('/influencers')
        self.assertIn(b'test_influencer', response.data, "Should see the added influencer in My Influencers")

        # Add influencer 2 (should work, limit is 2)
        response = self.client.post(f'/saas/shortlist_influencer/add/{influencer2_id}', data={'shortlist_id': shortlist_id}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Add influencer 3 (should fail due to limit)
        response = self.client.post(f'/saas/shortlist_influencer/add/{influencer3_id}', data={'shortlist_id': shortlist_id}, follow_redirects=True)
        # Verify block message
        self.assertIn('للحد الأقصى', response.data.decode('utf-8')) # "You have reached the maximum limit" in Arabic
        
        with self.app.app_context():
            user = Users.query.filter_by(username=self.test_username).first()
            shortlist = Shortlist.query.filter_by(agency_id=user.agency_id).first()
            self.assertEqual(len(shortlist.influencers), 2, "Should only have 2 influencers in shortlist")

    def test_5_navigation_and_template_rendering(self):
        self.client.post('/register', data={'username': self.test_username, 'email': self.test_email, 'password': self.test_password, 'register': 'True'})
        self.client.post('/login', data={'username': self.test_username, 'password': self.test_password, 'login': 'True'})

        # Render agency page
        response = self.client.get('/saas/agency')
        self.assertEqual(response.status_code, 200, "Agency page should render without errors")

if __name__ == '__main__':
    unittest.main()
