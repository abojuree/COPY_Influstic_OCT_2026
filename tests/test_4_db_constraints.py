import pytest
from sqlalchemy.exc import IntegrityError
from apps.saas.models import Agency, Plan, Subscription, Shortlist
from apps.authentication.models import Users
from apps.profiles.models import Influencer
from apps.social.models import SocialAccount, Platform
from apps.reports.models import ScanResults

def test_4_1_influencer_cascade(db):
    """
    Test 4.1 - Influencer Cascade:
    Delete an Influencer and verify SocialAccount and ScanResults are purged.
    """
    inf = Influencer(full_name="To Be Deleted")
    platform = Platform(name="TBD Platform", name_english="tbd_platform")
    db.session.add_all([inf, platform])
    db.session.commit()

    sa = SocialAccount(influencer_id=inf.id, platform_id=platform.id, username="tbd_user")
    db.session.add(sa)
    db.session.commit()

    sr = ScanResults(socialaccount_id=sa.id, followers=100)
    db.session.add(sr)
    db.session.commit()

    inf_id = inf.id
    sa_id = sa.id
    sr_id = sr.id

    # Delete influencer
    db.session.delete(inf)
    db.session.commit()

    # Assert cascade deletion worked
    assert Influencer.query.get(inf_id) is None
    assert SocialAccount.query.get(sa_id) is None
    assert ScanResults.query.get(sr_id) is None

def test_4_2_agency_purge_cascade(db):
    """
    Test 4.2 - Agency Purge Cascade:
    Delete an Agency and verify related rows are purged, but Influencers remain untouched.
    """
    agency = Agency(name="Purge Agency")
    plan = Plan(name="Purge Plan")
    db.session.add_all([agency, plan])
    db.session.commit()

    sub = Subscription(agency_id=agency.id, plan_id=plan.id, current_period_end=db.func.current_date())
    user = Users(username="purge_user", email="purge@test.com", agency_id=agency.id)
    db.session.add_all([sub, user])
    db.session.commit()

    shortlist = Shortlist(name="Purge Shortlist", agency_id=agency.id, created_by=user.id)
    inf = Influencer(full_name="Permanent Influencer")
    db.session.add_all([shortlist, inf])
    db.session.commit()

    shortlist.influencers.append(inf)
    db.session.commit()

    # Store IDs
    agency_id = agency.id
    sub_id = sub.id
    user_id = user.id
    shortlist_id = shortlist.id
    inf_id = inf.id

    # Delete agency
    db.session.delete(agency)
    db.session.commit()

    # Verify cascades
    assert Agency.query.get(agency_id) is None
    assert Subscription.query.get(sub_id) is None
    assert Users.query.get(user_id) is None
    assert Shortlist.query.get(shortlist_id) is None
    
    # Verify Influencer survived
    assert Influencer.query.get(inf_id) is not None

def test_4_3_unique_constraints(db):
    """
    Test 4.3 - Unique Constraints:
    Attempt to insert two SocialAccount rows with exact same username and platform_id.
    """
    inf = Influencer(full_name="Constraint Inf")
    platform = Platform(name="Constraint Plat", name_english="constraint_plat")
    db.session.add_all([inf, platform])
    db.session.commit()

    sa1 = SocialAccount(influencer_id=inf.id, platform_id=platform.id, username="same_username")
    db.session.add(sa1)
    db.session.commit()

    sa2 = SocialAccount(influencer_id=inf.id, platform_id=platform.id, username="same_username")
    db.session.add(sa2)

    with pytest.raises(IntegrityError):
        db.session.commit()
    
    db.session.rollback()
