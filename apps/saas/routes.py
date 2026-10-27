from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from apps import db
from apps.saas.models import Agency, Plan, Subscription, Shortlist
from apps.authentication.models import Users
from datetime import datetime, timedelta
from apps.profiles.models import Influencer
from apps.saas.util import require_subscription_limit
from apps.authentication.util import permission_required

blueprint = Blueprint('saas_blueprint', __name__, url_prefix='/saas')

@blueprint.route('/agency')
@login_required
def agency():
    """
    Agency dashboard showing details, assigned users, and active subscription.
    """
    agency_id = current_user.agency_id
    if not agency_id:
        flash('أنت لست معيناً في أي وكالة.', 'danger')
        return redirect(url_for('authentication_blueprint.login'))

    # Get agency
    agency = Agency.query.get_or_404(agency_id)
    
    # Get users
    users = Users.query.filter_by(agency_id=agency_id).all()
    
    # Get active subscription
    subscription = Subscription.query.filter_by(agency_id=agency_id, status='active').first()
    
    return render_template('saas/agency.html', agency=agency, users=users, subscription=subscription)

@blueprint.route('/plans')
@login_required
def plans():
    """
    Displays available tiers from the Plan table.
    """
    agency_id = current_user.agency_id
    if not agency_id:
        flash('أنت لست معيناً في أي وكالة.', 'danger')
        return redirect(url_for('authentication_blueprint.login'))
        
    plans_list = Plan.query.filter_by(is_active=True).order_by(Plan.price.asc()).all()
    current_subscription = Subscription.query.filter_by(agency_id=agency_id, status='active').first()
    
    return render_template('saas/plans.html', plans=plans_list, current_subscription=current_subscription)

@blueprint.route('/select-plan/<int:plan_id>', methods=['POST'])
@login_required
def select_plan(plan_id):
    """
    Updates or creates the Subscription for the user's Agency.
    """
    agency_id = current_user.agency_id
    if not agency_id:
        flash('أنت لست معيناً في أي وكالة.', 'danger')
        return redirect(url_for('authentication_blueprint.login'))
        
    plan = Plan.query.get_or_404(plan_id)
    
    # Check for existing subscription
    existing_sub = Subscription.query.filter_by(agency_id=agency_id).first()
    
    if existing_sub:
        existing_sub.plan_id = plan.id
        existing_sub.status = 'active'
        existing_sub.current_period_end = datetime.utcnow() + timedelta(days=30)
        flash(f'تم تحديث الباقة بنجاح إلى {plan.name}', 'success')
    else:
        new_sub = Subscription(
            agency_id=agency_id,
            plan_id=plan.id,
            status='active',
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(new_sub)
        flash(f'تم الاشتراك في باقة {plan.name} بنجاح', 'success')
        
    db.session.commit()
    
    return redirect(url_for('saas_blueprint.agency'))

from apps.saas.models import Campaign, Shortlist
from apps.home.util import generate_recommendations
from flask import jsonify

@blueprint.route('/campaigns')
@login_required
@permission_required('campaigns', 'read')
def list_campaigns():
    """ Dashboard displaying all agency campaigns. """
    agency_id = current_user.agency_id
    if not agency_id:
        return redirect(url_for('authentication_blueprint.login'))
    campaigns = Campaign.query.filter_by(agency_id=agency_id).order_by(Campaign.created_at.desc()).all()
    return render_template('saas/campaigns.html', campaigns=campaigns)


@blueprint.route('/campaigns/new', methods=['GET', 'POST'])
@login_required
@permission_required('campaigns', 'write')
def new_campaign():
    """ Wizard to create a new campaign and capture Campaign DNA. """
    if request.method == 'POST':
        # Enforce Campaign Limits based on Subscription Plan
        agency = current_user.agency
        active_sub = agency.subscriptions.filter_by(status='active').first()
        campaign_limit = active_sub.plan.campaign_limit if active_sub and active_sub.plan else 1
        
        current_campaigns_count = Campaign.query.filter_by(agency_id=agency.id).count()
        if current_campaigns_count >= campaign_limit:
            flash(f"لقد تجاوزت الحد الأقصى المسموح به للحملات ({campaign_limit}). يرجى ترقية اشتراكك.", "danger")
            return redirect(url_for('saas_blueprint.campaigns'))

        name = request.form.get('name')
        target_platform = request.form.get('target_platform')
        objective = request.form.get('objective')
        keywords = request.form.get('keywords')
        
        campaign = Campaign(
            agency_id=current_user.agency_id,
            name=name,
            target_platform=target_platform,
            objective=objective,
            keywords=keywords,
            status='Active'
        )
        db.session.add(campaign)
        db.session.commit()
        
        # Create a default shortlist for the campaign
        default_shortlist = Shortlist(
            campaign_id=campaign.id,
            created_by=current_user.id,
            name="Default Shortlist"
        )
        db.session.add(default_shortlist)
        db.session.commit()
        
        flash("Campaign created successfully!", "success")
        return redirect(url_for('saas_blueprint.campaign_workspace', campaign_id=campaign.id))
        
    return render_template('saas/campaign_new.html')

@blueprint.route('/campaigns/<int:campaign_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('campaigns', 'write')
def edit_campaign(campaign_id):
    """ Edit an existing campaign. """
    campaign = Campaign.query.filter_by(id=campaign_id, agency_id=current_user.agency_id).first_or_404()
    
    if request.method == 'POST':
        campaign.name = request.form.get('name')
        campaign.target_platform = request.form.get('target_platform')
        campaign.objective = request.form.get('objective')
        campaign.keywords = request.form.get('keywords')
        campaign.status = request.form.get('status', 'Active')
        
        db.session.commit()
        flash("Campaign updated successfully!", "success")
        return redirect(url_for('saas_blueprint.list_campaigns'))
        
    return render_template('saas/campaign_edit.html', campaign=campaign)


@blueprint.route('/campaigns/<int:campaign_id>/workspace')
@login_required
@permission_required('campaigns', 'read')
def campaign_workspace(campaign_id):
    """ The persistent workspace for a specific campaign. """
    campaign = Campaign.query.filter_by(id=campaign_id, agency_id=current_user.agency_id).first_or_404()
    
    # Load shortlists directly tied to this campaign
    campaign_shortlists = Shortlist.query.filter_by(campaign_id=campaign.id).all()
    
    from apps.home.util import get_unified_table_data
    from apps.social.models import SocialAccount
    
    chosen_influencer_ids = []
    if campaign_shortlists and campaign_shortlists[0].influencers:
        chosen_influencer_ids = [inf.id for inf in campaign_shortlists[0].influencers]
        
    if chosen_influencer_ids:
        accounts_with_metrics = get_unified_table_data(SocialAccount.influencer_id.in_(chosen_influencer_ids))
    else:
        accounts_with_metrics = []
    
    # We also need global accounts for Smart Discovery
    all_accounts_with_metrics = get_unified_table_data()
    
    return render_template(
        'saas/campaign_workspace.html', 
        campaign=campaign, 
        shortlists=campaign_shortlists,
        accounts_with_metrics=accounts_with_metrics,
        all_accounts_with_metrics=all_accounts_with_metrics
    )


@blueprint.route('/campaigns/<int:campaign_id>/recommendations')
@login_required
@permission_required('campaigns', 'read')
def campaign_recommendations(campaign_id):
    """ 
    API Endpoint called via AJAX from the Workspace Smart Discovery Tab.
    Executes the math engine and returns the sanitized JSON payload.
    """
    try:
        campaign = Campaign.query.filter_by(id=campaign_id, agency_id=current_user.agency_id).first_or_404()
        
        recommendations = generate_recommendations(campaign.id) 
        
        return jsonify({
            "status": "success",
            "data": recommendations
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"حدث خطأ أثناء تحليل الترشيحات: {str(e)}",
            "data": []
        }), 500

@blueprint.route('/campaigns/<int:campaign_id>/action', methods=['POST'])
@login_required
@permission_required('campaigns', 'write')
def campaign_action(campaign_id):
    """ Endpoint to handle Start/End/Pause state changes. """
    campaign = Campaign.query.filter_by(id=campaign_id, agency_id=current_user.agency_id).first_or_404()
    
    action = request.form.get('action')
    if action in ['Draft', 'Active', 'Completed']:
        campaign.status = action
        db.session.commit()
        flash(f"Campaign marked as {action}", "success")
        
    return redirect(url_for('saas_blueprint.campaign_workspace', campaign_id=campaign.id))

@blueprint.route('/campaigns/<int:campaign_id>/shortlist/add/<int:influencer_id>', methods=['POST'])
@login_required
@permission_required('campaigns', 'write')
@require_subscription_limit
def add_to_shortlist(campaign_id, influencer_id):
    """ Add an influencer to the campaign's default shortlist. """
    campaign = Campaign.query.filter_by(id=campaign_id, agency_id=current_user.agency_id).first_or_404()
    shortlist = Shortlist.query.filter_by(campaign_id=campaign.id).first()
    
    influencer = Influencer.query.get_or_404(influencer_id)
    if influencer not in shortlist.influencers:
        shortlist.influencers.append(influencer)
        db.session.commit()
        
    return jsonify({"status": "success"})
