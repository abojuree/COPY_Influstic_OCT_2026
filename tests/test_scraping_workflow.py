import pytest
import json
from unittest.mock import patch, MagicMock
from apps.profiles.models import Influencer
from apps.social.models import SocialAccount, Platform
from apps.authentication.models import Users, Role
from apps import db

def setup_admin_and_platform(client):
    # Setup admin
    role = Role.query.filter_by(name="admin").first()
    if not role:
        role = Role(name="admin", permissions={"admin_portal": {"read": "1"}, "influencers": {"read": "1", "edit": "1"}})
        db.session.add(role)
        db.session.commit()

    admin = Users.query.filter_by(username="admin_test").first()
    if not admin:
        admin = Users(username="admin_test", password="password", email="admin_test@email.com", role="admin", role_id=role.id)
        db.session.add(admin)
        db.session.commit()
        
    # Setup platform
    platform = Platform.query.filter_by(name="Instagram").first()
    if not platform:
        platform = Platform(name="Instagram", name_english="Instagram")
        db.session.add(platform)
        db.session.commit()
        
    p_id = platform.id

    # The login route requires 'email', 'password', and the 'login' button value in request.form
    client.post('/login', data={'email': 'admin_test@email.com', 'password': 'password', 'login': 'True'})
    return p_id

def test_scrape_interception(client, db):
    platform_id = setup_admin_and_platform(client)

    # Mock the scraper factory to prevent actual API calls
    with patch('apps.services.scrapers.factory.ScraperFactory.get_scraper') as mock_get_scraper:
        mock_scraper = MagicMock()
        mock_scraper.fetch_profile.return_value = {
            "username": "test_influencer",
            "full_name": "Test Influencer",
            "followers_count": 10000,
            "total_likes": 5000,
            "total_posts": 100,
            "profile_pic_url": "http://example.com/pic.jpg"
        }
        mock_get_scraper.return_value = mock_scraper

        data = {
            'platform': platform_id,
            'username': 'test_influencer'
        }
        response = client.post('/admin_scrape_influencer', data=data)

        assert response.status_code == 200
        assert b'test_influencer' in response.data
        
    assert Influencer.query.filter_by(full_name="Test Influencer").count() == 0

def test_payload_merge_and_save(client, db):
    platform_id = setup_admin_and_platform(client)

    valid_profile_data = {
        "username": "save_test",
        "public_profile_name": "Save Test Influencer",
        "followers": 50000,
        "likes": 20000,
        "total_posts": 150,
        "platform_id": platform_id,
        "platform_name_english": "instagram"
    }

    data = {
        'scraped_data_json': json.dumps(valid_profile_data),
        'email': 'test@example.com',
        'phone': '1234567890',
        'country': 'USA',
        'city': 'New York',
        'category': 'Tech'
    }

    response = client.post('/admin_scrape_save', data=data, follow_redirects=True)
    assert response.status_code == 200
    
    influencer = Influencer.query.filter_by(full_name="Save Test Influencer").first()
    assert influencer is not None
    assert influencer.email == 'test@example.com'
    assert influencer.phone == '1234567890'
    assert influencer.country == 'USA'
    assert influencer.category == 'Tech'

    social_account = SocialAccount.query.filter_by(influencer_id=influencer.id).first()
    assert social_account is not None
    assert social_account.followers == 50000
    assert social_account.username == 'save_test'

def test_nullable_contact_fields(client, db):
    platform_id = setup_admin_and_platform(client)

    valid_profile_data = {
        "username": "null_test",
        "public_profile_name": "Null Test Influencer",
        "followers": 1000,
        "likes": 500,
        "total_posts": 10,
        "platform_id": platform_id,
        "platform_name_english": "instagram"
    }

    data = {
        'scraped_data_json': json.dumps(valid_profile_data),
        'email': '',
        'phone': '',
        'country': '',
        'city': '',
        'category': ''
    }

    response = client.post('/admin_scrape_save', data=data, follow_redirects=True)
    assert response.status_code == 200
    
    influencer = Influencer.query.filter_by(full_name="Null Test Influencer").first()
    assert influencer is not None
    assert influencer.email is None
    assert influencer.phone is None
    assert influencer.category is None

def test_corrupted_json_payload(client, db):
    setup_admin_and_platform(client)
        
    data = {
        'scraped_data_json': '{bad_json: missing_quotes}',
        'email': 'test@example.com'
    }

    response = client.post('/admin_scrape_save', data=data, follow_redirects=False)
    assert response.status_code == 302
    
    with client.session_transaction() as session:
        flashes = dict(session.get('_flashes', []))
        assert "خطأ في قراءة البيانات" in flashes.values()
    
    assert Influencer.query.filter_by(email="test@example.com").count() == 0

def test_edit_influencer_contact(client, db):
    setup_admin_and_platform(client)
    
    influencer = Influencer(
        full_name="Edit Me",
        email="old@email.com",
        country="Old Country"
    )
    db.session.add(influencer)
    db.session.commit()
    influencer_id = influencer.id
        
    data = {
        'email': 'new@email.com',
        'phone': '9998887776',
        'country': 'New Country',
        'city': 'New City',
        'category': 'Gaming'
    }

    response = client.post(f'/edit_influencer_info/{influencer_id}', data=data, follow_redirects=True)
    assert response.status_code == 200

    updated_influencer = Influencer.query.get(influencer_id)
    assert updated_influencer.email == 'new@email.com'
    assert updated_influencer.phone == '9998887776'
    assert updated_influencer.country == 'New Country'
    assert updated_influencer.category == 'Gaming'
