import pytest
from apps.saas.models import Agency, Shortlist
from apps.authentication.models import Users

def test_1_1_strict_read_isolation(db):
    """
    Test 1.1 - Strict Read Isolation:
    Create two Agencies. Create a Shortlist for Agency A.
    Querying shortlists for a user in Agency B should not return Agency A's data.
    """
    # Create Agencies
    agency_a = Agency(name="Agency A")
    agency_b = Agency(name="Agency B")
    db.session.add_all([agency_a, agency_b])
    db.session.commit()

    # Create Users
    user_a = Users(username="user_a", email="a@test.com", agency_id=agency_a.id)
    user_b = Users(username="user_b", email="b@test.com", agency_id=agency_b.id)
    db.session.add_all([user_a, user_b])
    db.session.commit()

    # Create Shortlist for Agency A
    shortlist_a = Shortlist(name="Shortlist A", agency_id=agency_a.id, created_by=user_a.id)
    db.session.add(shortlist_a)
    db.session.commit()

    # Simulate reading shortlists as user_b
    user_b_shortlists = Shortlist.query.filter_by(agency_id=user_b.agency_id).all()
    
    assert len(user_b_shortlists) == 0
    
    # Simulate reading shortlists as user_a
    user_a_shortlists = Shortlist.query.filter_by(agency_id=user_a.agency_id).all()
    assert len(user_a_shortlists) == 1
    assert user_a_shortlists[0].name == "Shortlist A"


def test_1_2_strict_write_isolation(db):
    """
    Test 1.2 - Strict Write Isolation:
    Attempt to update or delete a Shortlist belonging to another Agency.
    """
    agency_a = Agency(name="Agency A")
    agency_b = Agency(name="Agency B")
    db.session.add_all([agency_a, agency_b])
    db.session.commit()

    user_a = Users(username="user_a", email="a@test.com", agency_id=agency_a.id)
    user_b = Users(username="user_b", email="b@test.com", agency_id=agency_b.id)
    db.session.add_all([user_a, user_b])
    db.session.commit()

    shortlist_a = Shortlist(name="Shortlist A", agency_id=agency_a.id, created_by=user_a.id)
    db.session.add(shortlist_a)
    db.session.commit()

    # Simulate user_b trying to update shortlist_a
    # The application logic should always scope updates to the user's agency_id
    updated_rows = Shortlist.query.filter_by(id=shortlist_a.id, agency_id=user_b.agency_id).update({"name": "Hacked"})
    db.session.commit()
    
    assert updated_rows == 0
    
    # Verify the original record remains unchanged
    db.session.refresh(shortlist_a)
    assert shortlist_a.name == "Shortlist A"

    # Simulate user_b trying to delete shortlist_a
    deleted_rows = Shortlist.query.filter_by(id=shortlist_a.id, agency_id=user_b.agency_id).delete()
    db.session.commit()
    
    assert deleted_rows == 0
    assert Shortlist.query.get(shortlist_a.id) is not None


def test_1_3_orphan_user_handling(db, client):
    """
    Test 1.3 - Orphan User Handling:
    Create a User with agency_id = None.
    Verify they can still be created and accessed without crashing.
    """
    # Create legacy admin user (no agency)
    admin_user = Users(username="admin", email="admin@test.com", agency_id=None)
    db.session.add(admin_user)
    db.session.commit()

    # Verify user exists and agency_id is None
    fetched_user = Users.query.filter_by(username="admin").first()
    assert fetched_user is not None
    assert fetched_user.agency_id is None
    
    # Ensure querying agency relationship doesn't crash (returns None)
    assert fetched_user.agency is None
