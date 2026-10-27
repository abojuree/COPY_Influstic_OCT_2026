from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from apps import db
from apps.saas.models import Agency, Subscription, Plan, Shortlist, shortlist_influencer
from apps.profiles.models import Influencer

def require_subscription_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        agency_id = getattr(current_user, 'agency_id', None)
        if not agency_id:
            flash('أنت لست معيناً في أي وكالة. يرجى الاشتراك في باقة لإضافة مؤثرين.', 'danger')
            return redirect(url_for('saas_blueprint.plans'))
            
        # Get active subscription
        subscription = Subscription.query.filter(
            Subscription.agency_id == agency_id,
            Subscription.status == 'active'
        ).first()
        
        if not subscription or not subscription.plan:
            flash('لا يوجد لديك اشتراك نشط أو الباقة محذوفة. يرجى الاشتراك في باقة صالحة.', 'danger')
            return redirect(url_for('saas_blueprint.plans'))
            
        plan_limit = subscription.plan.tracking_limit
        
        # Count unique tracked influencers for this agency
        from apps.saas.models import Campaign
        count_query = db.session.query(db.func.count(db.distinct(shortlist_influencer.c.influencer_id)))\
            .join(Shortlist, Shortlist.id == shortlist_influencer.c.shortlist_id)\
            .join(Campaign, Campaign.id == Shortlist.campaign_id)\
            .filter(Campaign.agency_id == agency_id)
            
        current_tracked = count_query.scalar() or 0
                
        if current_tracked >= plan_limit:
            flash(f'لقد وصلت للحد الأقصى لباقة الاشتراك الخاصة بك ({plan_limit} مؤثر). يرجى الترقية لإضافة المزيد.', 'danger')
            return redirect(url_for('saas_blueprint.plans'))
            
        return f(*args, **kwargs)
    return decorated_function
