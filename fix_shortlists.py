import os

def replace_in_file(filepath, old, new):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Replaced in {filepath}')
    else:
        print(f'Not found in {filepath}')

base_dir = 'e:/Freelancing/Influencers Analytics Platform/Influencers-Analytics-Platform'

# 1. apps/admin/util.py
admin_util = os.path.join(base_dir, 'apps/admin/util.py')
old_admin_kpis = """    # Total ScanResults created in range
    total_scans_query = ScanResults.query
    if time_range != 'all':
        total_scans_query = total_scans_query.filter(func.date(ScanResults.creation_date) >= start_date)
    total_scans_today = total_scans_query.count()

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
    success_rate = (successful_scans_today / total_api_calls * 100) if total_api_calls > 0 else 0.0"""
    
new_admin_kpis = """    # Success and failure counts for range from ScanLog
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
    
    total_scans_today = successful_scans_today  # Use this instead of ScanResults.count() to avoid cascade delete drops"""

replace_in_file(admin_util, old_admin_kpis, new_admin_kpis)

# 2. apps/admin/util.py - get_clients_kpis
old_clients = """        # Calculate distinct influencers across all shortlists
        shortlists = Shortlist.query.filter_by(agency_id=agency.id).all()"""
new_clients = """        # Calculate distinct influencers across all shortlists
        from apps.saas.models import Campaign
        shortlists = Shortlist.query.join(Campaign).filter(Campaign.agency_id == agency.id).all()"""
replace_in_file(admin_util, old_clients, new_clients)

# 3. apps/profiles/routes.py
profiles_routes = os.path.join(base_dir, 'apps/profiles/routes.py')
old_profiles = """    # Get the user's shortlists to pass to the template for the "Add to Shortlist" modal/dropdown
    from apps.saas.models import Shortlist
    user_shortlists = Shortlist.query.filter_by(agency_id=current_user.agency_id).all() if current_user.agency_id else []"""
new_profiles = """    # Get the user's shortlists to pass to the template for the "Add to Shortlist" modal/dropdown
    from apps.saas.models import Shortlist, Campaign
    user_shortlists = Shortlist.query.join(Campaign).filter(Campaign.agency_id == current_user.agency_id).all() if current_user.agency_id else []"""
replace_in_file(profiles_routes, old_profiles, new_profiles)

# 4. apps/home/routes.py (we have two instances here)
home_routes = os.path.join(base_dir, 'apps/home/routes.py')
old_home_1 = """        shortlist = Shortlist.query.filter_by(id=shortlist_id, agency_id=current_user.agency_id).first()"""
new_home_1 = """        from apps.saas.models import Campaign
        shortlist = Shortlist.query.join(Campaign).filter(Shortlist.id == shortlist_id, Campaign.agency_id == current_user.agency_id).first()"""
replace_in_file(home_routes, old_home_1, new_home_1)

old_home_2 = """    shortlists = Shortlist.query.filter_by(agency_id=current_user.agency_id).all()"""
new_home_2 = """    from apps.saas.models import Campaign
    shortlists = Shortlist.query.join(Campaign).filter(Campaign.agency_id == current_user.agency_id).all()"""
replace_in_file(home_routes, old_home_2, new_home_2)
