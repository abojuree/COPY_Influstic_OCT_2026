import json
from datetime import datetime, timedelta
from sqlalchemy import func
from apps import db
from apps.reports.models import ScanResults, ScanLog
from apps.saas.models import Agency, Subscription, Plan, Shortlist, shortlist_influencer
from apps.profiles.models import Influencer
from apps.social.models import SocialAccount
from apps.authentication.models import Users

def get_start_date(time_range):
    today = datetime.now().date()
    start_date = today
    if time_range == '7days':
        start_date = today - timedelta(days=7)
    elif time_range == '30days':
        start_date = today - timedelta(days=30)
    elif time_range == 'all':
        start_date = datetime(2000, 1, 1).date()
    return start_date, today

def get_home_kpis(time_range='today'):
    """
    Calculate KPIs and chart data for the Admin Home (API & Infrastructure) page.
    """
    start_date, today = get_start_date(time_range)
    
    # Success and failure counts for range from ScanLog
    logs_query = ScanLog.query
    if time_range != 'all':
        logs_query = logs_query.filter(func.date(ScanLog.creation_date) >= start_date)
    logs_in_range = logs_query.all()
    
    successful_scans_today = 0
    failed_scans_today = 0
    
    for log in logs_in_range:
        if log.success_count:
            successful_scans_today += sum(log.success_count.values())
        if log.failure_count:
            failed_scans_today += sum(log.failure_count.values())

    total_api_calls = successful_scans_today + failed_scans_today
    success_rate = (successful_scans_today / total_api_calls * 100) if total_api_calls > 0 else 0.0
    
    total_scans_today = successful_scans_today  # Use this instead of ScanResults.count() to avoid cascade delete drops

    # 7-Day Scan Trend (always 7 days for the chart to make sense, regardless of time_range)
    labels = []
    dataset_1 = [] # Success
    dataset_2 = [] # Failed

    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        labels.append(target_date.strftime("%b %d"))
        
        logs = ScanLog.query.filter(
            func.date(ScanLog.creation_date) == target_date
        ).all()
        
        day_success = 0
        day_failure = 0
        for log in logs:
            if log.success_count:
                day_success += sum(log.success_count.values())
            if log.failure_count:
                day_failure += sum(log.failure_count.values())
                
        dataset_1.append(day_success)
        dataset_2.append(day_failure)

    # Fetch last 20 failed scans from recent logs
    recent_logs = ScanLog.query.order_by(ScanLog.creation_date.desc(), ScanLog.creation_time.desc()).limit(10).all()
    recent_failures = []
    for log in recent_logs:
        if log.failures:
            for f in log.failures:
                recent_failures.append({
                    "timestamp": f"{log.creation_date} {log.creation_time}",
                    "handle": f.get("handle", "Unknown"),
                    "error_message": f.get("error", "Unknown error")
                })
                if len(recent_failures) >= 20:
                    break
        if len(recent_failures) >= 20:
            break

    return {
        "total_scans_today": total_scans_today,
        "successful_scans_today": successful_scans_today,
        "failed_scans_today": failed_scans_today,
        "success_rate": f"{success_rate:.1f}",
        "chart_labels": json.dumps(labels),
        "chart_success": json.dumps(dataset_1),
        "chart_failed": json.dumps(dataset_2),
        "recent_failures": recent_failures
    }

def get_clients_kpis(time_range='today'):
    """
    Calculate KPIs and chart data for the Admin Clients page.
    """
    total_agencies = Agency.query.count()
    active_subscriptions = Subscription.query.filter_by(status='active').count()

    # Plan Distribution Doughnut Chart
    plans = Plan.query.all()
    plan_counts = {plan.name: 0 for plan in plans}
    if "Free" not in plan_counts:
        plan_counts["Free"] = 0
        
    agencies = Agency.query.all()
    for agency in agencies:
        active_sub = Subscription.query.filter_by(agency_id=agency.id, status='active').first()
        plan_name = active_sub.plan.name if active_sub and active_sub.plan else "Free"
        if plan_name in plan_counts:
            plan_counts[plan_name] += 1
        else:
            plan_counts[plan_name] = 1

    labels = []
    data = []
    for p_name, count in plan_counts.items():
        if count > 0:
            labels.append(p_name)
            data.append(count)

    # Master table data
    agencies = Agency.query.all()
    agencies_data = []
    for agency in agencies:
        active_sub = Subscription.query.filter_by(agency_id=agency.id, status='active').first()
        plan_name = active_sub.plan.name if active_sub and active_sub.plan else "Free"
        plan_limit = active_sub.plan.tracking_limit if active_sub and active_sub.plan else 50
        campaign_limit = active_sub.plan.campaign_limit if active_sub and active_sub.plan else 1
        user_count = Users.query.filter_by(agency_id=agency.id).count()
        
        # Calculate distinct influencers across all shortlists
        from apps.saas.models import Campaign
        shortlists = Shortlist.query.join(Campaign).filter(Campaign.agency_id == agency.id).all()
        influencer_ids = set()
        for sl in shortlists:
            for inf in sl.influencers:
                influencer_ids.add(inf.id)
                
        quota_used = len(influencer_ids)
        
        campaigns_count = Campaign.query.filter_by(agency_id=agency.id).count()
        
        agencies_data.append({
            "name": agency.name,
            "plan_name": plan_name,
            "user_count": user_count,
            "quota_used": quota_used,
            "quota_limit": plan_limit,
            "campaign_used": campaigns_count,
            "campaign_limit": campaign_limit
        })

    return {
        "total_agencies": total_agencies,
        "active_subscriptions": active_subscriptions,
        "chart_labels": json.dumps(labels),
        "chart_data": json.dumps(data),
        "agencies_data": agencies_data
    }

def get_influencers_kpis(time_range='today'):
    """
    Calculate KPIs and chart data for the Admin Influencers page.
    """
    total_influencers = Influencer.query.count()
    total_accounts = SocialAccount.query.count()

    # Top 5 most tracked influencers
    most_tracked = db.session.query(
        shortlist_influencer.c.influencer_id,
        func.count(shortlist_influencer.c.influencer_id).label('total')
    ).group_by(shortlist_influencer.c.influencer_id).order_by(func.count(shortlist_influencer.c.influencer_id).desc()).limit(5).all()
    
    most_tracked_names = []
    for mt in most_tracked:
        inf = Influencer.query.get(mt.influencer_id)
        if inf:
            account = SocialAccount.query.filter_by(influencer_id=inf.id).first()
            if account and account.public_profile_name:
                most_tracked_names.append(account.public_profile_name)
            elif account and getattr(account, 'username', None):
                most_tracked_names.append(account.username)
            else:
                most_tracked_names.append(inf.full_name or f"ID: {inf.id}")

    if not most_tracked_names:
        most_tracked_names = ["لا يوجد"]

    # Platform breakdown bar chart
    from apps.social.models import Platform
    platforms = db.session.query(
        Platform.name,
        func.count(SocialAccount.id)
    ).join(SocialAccount, SocialAccount.platform_id == Platform.id).group_by(Platform.name).all()

    labels = [p[0] for p in platforms if p[0]]
    data = [p[1] for p in platforms if p[0]]

    # All global influencers table
    from apps.home.util import get_unified_table_data
    accounts_with_metrics = get_unified_table_data()

    return {
        "total_influencers": total_influencers,
        "total_accounts": total_accounts,
        "most_tracked_influencer": " | ".join(most_tracked_names),
        "chart_labels": json.dumps(labels),
        "chart_data": json.dumps(data),
        "accounts_with_metrics": accounts_with_metrics
    }

def get_system_kpis(time_range='today'):
    """
    Calculate KPIs and chart data for the Admin System page.
    """
    total_users = Users.query.count()
    
    total_influencers = Influencer.query.count()
    total_accounts = SocialAccount.query.count()
    total_scans = ScanResults.query.count()
    total_db_records = total_influencers + total_accounts + total_scans

    # User Management table
    users = Users.query.filter(Users.role != 'client').all()
    users_data = []
    for u in users:
        agency_name = u.agency.name if u.agency else "لا يوجد"
        
        if u.role == "admin":
            role_ar = "مدير النظام"
        elif u.role == "custom":
            role_ar = "دور خاص"
        elif u.role_model:
            role_ar = u.role_model.name
        else:
            role_ar = "مستخدم"
        status_ar = "نشط" if getattr(u, 'is_active', True) else "غير نشط"
        
        users_data.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "agency": agency_name,
            "role": role_ar,
            "status": status_ar
        })

    return {
        "total_users": total_users,
        "total_db_records": total_db_records,
        "users_data": users_data
    }
