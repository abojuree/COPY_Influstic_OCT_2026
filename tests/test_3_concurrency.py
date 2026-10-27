import pytest
import time
import concurrent.futures
from unittest.mock import patch
from apps.social.models import SocialAccount, Platform
from apps.profiles.models import Influencer
from tasks import process_username, scan_progress, scan_log

@pytest.fixture
def setup_social_accounts(db):
    platform = Platform(name="Instagram", name_english="instagram")
    db.session.add(platform)
    db.session.commit()
    
    accounts = []
    for i in range(10):
        inf = Influencer(full_name=f"Inf {i}")
        db.session.add(inf)
        db.session.commit()
        
        sa = SocialAccount(influencer_id=inf.id, platform_id=platform.id, username=f"user_{i}")
        db.session.add(sa)
        db.session.commit()
        accounts.append(sa)
        
    return platform, accounts

def test_3_1_isolated_session_verification(app, db, setup_social_accounts):
    """
    Test 3.1 - Isolated Session Verification:
    Submit 20 concurrent tasks. Verify no DetachedInstanceError or DB pool exhaustion.
    """
    platform, accounts = setup_social_accounts
    
    # Reset tracking
    scan_progress['success'] = 0
    scan_progress['failure'] = 0
    scan_log['success_count'] = {}
    scan_log['failure_count'] = {}

    def mock_search_user_profile(username, platform_id):
        # Simulate network delay to ensure threads overlap
        time.sleep(0.05)
        return {"followers": 1000, "likes": 500, "posts": 10, "bio_text": "bio", "profile_picture": "pic", "public_profile_name": "name", "time_taken": 1.5, "external_url": "url"}

    with patch('tasks.search_user_profile', side_effect=mock_search_user_profile):
        with patch('apps.db.session.commit'):
            with patch('apps.db.session.add'):
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = []
                    # Submit 5 accounts
                    for sa in accounts[:5]:
                        futures.append(executor.submit(process_username, app, platform.id, sa.username, sa.id))
                        
                    # Wait for all to complete
                    concurrent.futures.wait(futures)
                    
                    # Check for any exceptions in futures
                    for f in futures:
                        # This will raise if the thread raised an exception (like DetachedInstanceError)
                        exc = f.exception()
                        assert exc is None, f"Thread failed with exception: {exc}"

    # If we got here, no DB pool or session isolation errors occurred!
    assert scan_log['success_count'].get(platform.name, 0) == 5

def test_3_2_mutex_lock_global_tracking(app, db, setup_social_accounts):
    """
    Test 3.2 - Mutex Lock Global Tracking:
    Submit 50 successful and 10 failed scans concurrently.
    Verify global dictionaries match expected totals perfectly.
    """
    platform, accounts = setup_social_accounts
    
    # Reset tracking globally
    scan_progress['success'] = 0
    scan_progress['failure'] = 0
    scan_progress['processed'] = 0
    scan_log['success_count'] = {platform.name: 0}
    scan_log['failure_count'] = {platform.name: 0}

    # We will make the first 10 fail, and the next 50 succeed
    def mock_search_user_profile_mixed(username, platform_id):
        time.sleep(0.01) # Small sleep to overlap threads
        num = int(username.split('_')[1])
        if num < 10:
            # Simulate failure
            return {"error": "Profile not found"}
        return {"followers": 1000, "likes": 500, "posts": 10}

    with patch('tasks.search_user_profile', side_effect=mock_search_user_profile_mixed):
        with patch('apps.db.session.commit'):
            with patch('apps.db.session.add'):
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = []
                    # Submit all 10 accounts
                    for sa in accounts:
                        futures.append(executor.submit(process_username, app, platform.id, sa.username, sa.id))
                        
                    concurrent.futures.wait(futures)
                    # Check for any exceptions in futures
                    for f in futures:
                        exc = f.exception()
                        assert exc is None, f"Thread failed with exception: {exc}"

    # Global dictionaries should exactly reflect thread activity without race conditions
    assert scan_log['success_count'].get(platform.name, 0) == 0
    assert scan_log['failure_count'].get(platform.name, 0) == 10
    assert len(scan_log['failures'].get(platform.name, {})) == 10
