import pytest
import datetime
from apps.saas.models import Agency, Plan, Subscription, Shortlist
from apps.authentication.models import Users
from apps.profiles.models import Influencer

def enforce_subscription_limit(db, agency_id, new_influencers_count=1):
    """
    Mock backend enforcement logic that will be used in the routes.
    Checks if adding `new_influencers_count` exceeds the agency's tracking limit.
    """
    from apps.saas.models import shortlist_influencer

    # 1. Query current authorized tracking limit by joining Subscription and Plan
    limit = db.session.query(Plan.tracking_limit)\
        .join(Subscription, Subscription.plan_id == Plan.id)\
        .filter(Subscription.agency_id == agency_id, Subscription.status == 'active')\
        .scalar()
        
    if limit is None:
        raise Exception("No active subscription found")

    # 2. Query current usage (number of distinct influencers in all agency shortlists)
    current_usage = db.session.query(db.func.count(db.distinct(shortlist_influencer.c.influencer_id)))\
        .join(Shortlist, Shortlist.id == shortlist_influencer.c.shortlist_id)\
        .filter(Shortlist.agency_id == agency_id)\
        .scalar()
        
    if (current_usage + new_influencers_count) > limit:
        raise Exception(f"Tracking limit reached. Usage: {current_usage}, Limit: {limit}")
        
    return True

@pytest.fixture
def setup_agency_plan(db):
    agency = Agency(name="Test Agency")
    plan = Plan(name="Starter", tracking_limit=50, price=99.0)
    db.session.add_all([agency, plan])
    db.session.commit()
    
    user = Users(username="test_user", email="test@test.com", agency_id=agency.id)
    sub = Subscription(
        agency_id=agency.id, 
        plan_id=plan.id, 
        status='active', 
        current_period_end=datetime.datetime.utcnow() + datetime.timedelta(days=30)
    )
    db.session.add_all([user, sub])
    db.session.commit()
    
    shortlist = Shortlist(name="My Shortlist", agency_id=agency.id, created_by=user.id)
    db.session.add(shortlist)
    db.session.commit()
    
    return agency, plan, user, shortlist

def test_2_1_under_limit_insertion(db, setup_agency_plan):
    """
    Test 2.1 - Under Limit Insertion:
    Add influencers below the tracking limit and verify success.
    """
    agency, plan, user, shortlist = setup_agency_plan
    
    # Create 10 influencers
    influencers = [Influencer(full_name=f"Influencer {i}") for i in range(10)]
    db.session.add_all(influencers)
    db.session.commit()
    
    # Check limit before inserting (we want to add 10)
    assert enforce_subscription_limit(db, agency.id, 10) == True
    
    # Insert them
    for inf in influencers:
        shortlist.influencers.append(inf)
    db.session.commit()
    
    assert len(shortlist.influencers) == 10

def test_2_2_hard_limit_rejection(db, setup_agency_plan):
    """
    Test 2.2 - Hard Limit Rejection:
    Attempt to exceed the limit and verify rejection.
    """
    agency, plan, user, shortlist = setup_agency_plan
    
    # Create 50 influencers to max out the limit
    influencers = [Influencer(full_name=f"Influencer {i}") for i in range(50)]
    db.session.add_all(influencers)
    db.session.commit()
    
    for inf in influencers:
        shortlist.influencers.append(inf)
    db.session.commit()
    
    # Try to add the 51st
    inf_51 = Influencer(full_name="Influencer 51")
    db.session.add(inf_51)
    db.session.commit()
    
    # Enforcement should fail
    with pytest.raises(Exception) as excinfo:
        enforce_subscription_limit(db, agency.id, 1)
        
    assert "Tracking limit reached" in str(excinfo.value)
    
    # Ensure it's not added (simulating the rollback that a route would do)
    # The route would catch this exception and return an error without appending

def test_2_3_dynamic_plan_propagation(db, setup_agency_plan):
    """
    Test 2.3 - Dynamic Plan Propagation:
    Update the base Plan table and verify the agency instantly inherits the new limit.
    """
    agency, plan, user, shortlist = setup_agency_plan
    
    # Fill up to the current limit of 50
    influencers = [Influencer(full_name=f"Influencer {i}") for i in range(50)]
    db.session.add_all(influencers)
    for inf in influencers:
        shortlist.influencers.append(inf)
    db.session.commit()
    
    # Adding one more should fail
    with pytest.raises(Exception):
        enforce_subscription_limit(db, agency.id, 1)
        
    # Update the Plan directly (e.g. business decision to increase limits)
    plan.tracking_limit = 100
    db.session.commit()
    
    # Adding one more should now succeed without touching the Subscription row
    assert enforce_subscription_limit(db, agency.id, 1) == True
