"""
SaaS Multi-Tenancy Models
=========================
These models add the multi-tenant commercial SaaS layer to the platform.
They enable agency-based user isolation, subscription billing tiers,
plan management, and influencer shortlisting/campaign management.
"""

from datetime import datetime
from apps import db


class Agency(db.Model):
    """
    Represents a paying tenant (company/agency) in the SaaS model.
    All users, subscriptions, and shortlists belong to an Agency.
    """
    __tablename__ = 'agencies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    users = db.relationship(
        'Users', backref='agency',
        cascade="all, delete-orphan", lazy='dynamic'
    )
    subscriptions = db.relationship(
        'Subscription', backref='agency',
        cascade="all, delete-orphan", lazy='dynamic'
    )

    campaigns = db.relationship(
        'Campaign', backref='agency',
        cascade="all, delete-orphan", lazy='dynamic'
    )

    def __repr__(self):
        return f"Agency(id={self.id}, name='{self.name}')"


class Campaign(db.Model):
    """
    Campaign-Centric model for influencer personalization.
    Replaces global agency preferences to allow multiple isolated campaigns.
    """
    __tablename__ = 'campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'), nullable=False, index=True)
    
    name = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Draft') # 'Draft', 'Active', 'Completed'
    
    # Campaign DNA
    target_platform = db.Column(db.String(50), nullable=False, default='All') # 'TikTok', 'Instagram', 'Snapchat', 'All'
    objective = db.Column(db.String(100), nullable=False) # 'Brand Awareness', 'Direct Conversions', 'Community Engagement'
    keywords = db.Column(db.Text, nullable=True) # Comma-separated list
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Shortlists are now scoped to the campaign
    shortlists = db.relationship(
        'Shortlist', backref='campaign',
        cascade="all, delete-orphan", lazy='dynamic'
    )
    
    def __repr__(self):
        return f"Campaign(id={self.id}, name='{self.name}', status='{self.status}')"


class Plan(db.Model):
    """
    Represents a subscription plan tier (e.g., Starter, Pro, Enterprise).
    Centralizes plan definition, pricing, and tracking limits so updating
    a plan instantly updates rules for all subscribed agencies.
    """
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # e.g., 'Starter', 'Pro'
    tracking_limit = db.Column(db.Integer, nullable=False, default=0)
    campaign_limit = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    subscriptions = db.relationship('Subscription', backref='plan', lazy='dynamic')

    def __repr__(self):
        return f"Plan(id={self.id}, name='{self.name}', limit={self.tracking_limit}, price={self.price})"


class Subscription(db.Model):
    """
    Tracks billing status and expiration dates for an Agency.
    Links to a Plan via plan_id Foreign Key to dynamically determine rules and limits.
    """
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(
        db.Integer, db.ForeignKey('agencies.id'),
        nullable=False, index=True
    )
    plan_id = db.Column(
        db.Integer, db.ForeignKey('plans.id'),
        nullable=False, index=True
    )

    status = db.Column(db.String(20), nullable=False, default='active')  # 'active', 'past_due', 'canceled'

    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    current_period_end = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f"Subscription(id={self.id}, agency_id={self.agency_id}, plan_id={self.plan_id}, status='{self.status}')"


# ---------------------------------------------------------
# Shortlist & Campaign Management
# ---------------------------------------------------------

# Association table for the Many-to-Many relationship
# between Shortlists and Influencers
shortlist_influencer = db.Table(
    'shortlist_influencer',
    db.Column(
        'shortlist_id', db.Integer,
        db.ForeignKey('shortlists.id', ondelete="CASCADE"),
        primary_key=True
    ),
    db.Column(
        'influencer_id', db.Integer,
        db.ForeignKey('influencers.id', ondelete="CASCADE"),
        primary_key=True
    )
)


class Shortlist(db.Model):
    """
    Represents a saved list of influencers created by an agency user
    for campaign planning and influencer selection.
    """
    __tablename__ = 'shortlists'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.Integer, db.ForeignKey('campaigns.id'),
        nullable=False, index=True
    )
    created_by = db.Column(
        db.Integer, db.ForeignKey('Users.id'),
        nullable=False
    )

    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # M2M relationship to Influencers via the junction table
    influencers = db.relationship(
        'Influencer',
        secondary=shortlist_influencer,
        lazy='subquery',
        backref=db.backref('shortlists', lazy=True)
    )

    def __repr__(self):
        return f"Shortlist(id={self.id}, name='{self.name}', campaign_id={self.campaign_id})"

class Favourite(db.Model):
    """
    Represents a globally saved influencer by an agency, independent of campaigns.
    """
    __tablename__ = 'favourites'

    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(
        db.Integer, db.ForeignKey('agencies.id'),
        nullable=False, index=True
    )
    influencer_id = db.Column(
        db.Integer, db.ForeignKey('influencers.id'),
        nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    influencer = db.relationship('Influencer', backref='favourites')

