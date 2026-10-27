import datetime
from flask import  redirect, render_template, request, flash, session, url_for
from apps.home import blueprint
from flask_login import login_required, current_user
from jinja2 import TemplateNotFound

from apps.home.models import Log
from apps.home.forms import SearchForm
from apps.home.util import search_user_profile, get_summerized_report

from apps.social.models import Platform, SocialAccount

from icecream import ic
from apps.authentication.util import admin_required, permission_required


@blueprint.route('/index')
@login_required
def index():
    """
    Client Dashboard. Redirects to the appropriate default dashboard.
    """
    return redirect(url_for('authentication_blueprint.route_default'))

@blueprint.route('/profile', methods=['GET'])
@login_required
def profile():
    from apps.saas.models import Subscription, Plan
    subscription = Subscription.query.filter_by(agency_id=current_user.agency_id, status='active').first()
    plans = Plan.query.order_by(Plan.price.asc()).all()
    return render_template('home/profile.html', segment='profile', subscription=subscription, plans=plans)

@blueprint.route('/subscribe/<int:plan_id>', methods=['POST'])
@login_required
def subscribe(plan_id):
    from apps import db
    from apps.saas.models import Subscription, Plan
    from datetime import datetime, timedelta
    
    plan = Plan.query.get_or_404(plan_id)
    subscription = Subscription.query.filter_by(agency_id=current_user.agency_id, status='active').first()
    
    if subscription:
        subscription.plan_id = plan.id
    else:
        subscription = Subscription(
            agency_id=current_user.agency_id,
            plan_id=plan.id,
            status='active',
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(subscription)
        
    db.session.commit()
    flash(f'تم الاشتراك في باقة {plan.name} بنجاح', 'success')
    return redirect(url_for('home_blueprint.profile'))

@blueprint.route('/influencer/<int:id>')
@login_required
@permission_required('influencers', 'read')
def influencer_detail(id):
    from apps.profiles.models import Influencer
    from apps.saas.models import Shortlist, Campaign
    from apps.social.models import SocialPost
    influencer = Influencer.query.get_or_404(id)
    shortlists = Shortlist.query.join(Campaign).filter(Campaign.agency_id == current_user.agency_id).all()
    
    account_metrics = []
    for acc in influencer.socialaccounts:
        posts = SocialPost.query.filter_by(socialaccount_id=acc.id).all()
        post_count = len(posts)
        
        followers = acc.followers or 0
        
        valid_views = [p.plays for p in posts if p.plays is not None]
        avg_views = sum(valid_views) // len(valid_views) if valid_views else 0
        
        valid_likes = [p.likes for p in posts if p.likes is not None]
        avg_likes = sum(valid_likes) // len(valid_likes) if valid_likes else 0
        
        valid_comments = [p.comments for p in posts if p.comments is not None]
        avg_comments = sum(valid_comments) // len(valid_comments) if valid_comments else 0
        valid_shares = [p.shares for p in posts if p.shares is not None]
        avg_shares = sum(valid_shares) // len(valid_shares) if valid_shares else 0

        valid_saves = [p.saves for p in posts if p.saves is not None]
        avg_saves = sum(valid_saves) // len(valid_saves) if valid_saves else 0
        
        account_metrics.append({
            'account': acc,
            'followers': followers,
            'avg_views': avg_views,
            'avg_likes': avg_likes,
            'avg_comments': avg_comments,
            'avg_shares': avg_shares,
            'avg_saves': avg_saves
        })
        
    return render_template('home/influencer_detail.html', segment='discover', influencer=influencer, account_metrics=account_metrics, shortlists=shortlists)

@blueprint.route('/edit_influencer_info/<int:id>', methods=['POST'])
@login_required
@Log.add_log("تعديل بيانات مؤثر")
def edit_influencer_info(id):
    from apps.profiles.models import Influencer
    from apps import db
    influencer = Influencer.query.get_or_404(id)
    
    # Check if admin (optional, depending on your strict permissions)
    if current_user.role != 'admin':
        flash("غير مصرح لك بتعديل هذه البيانات", "danger")
        return redirect(request.referrer or url_for('home_blueprint.influencer_detail', id=id))
        
    influencer.email = request.form.get('email', '').strip() or None
    influencer.phone = request.form.get('phone', '').strip() or None
    influencer.country = request.form.get('country', '').strip() or None
    influencer.city = request.form.get('city', '').strip() or None
    influencer.category = request.form.get('category', '').strip() or None
    influencer.gender = request.form.get('gender', '').strip() or None
    
    try:
        db.session.commit()
        flash("تم تحديث بيانات المؤثر بنجاح", "success")
    except Exception as e:
        db.session.rollback()
        flash("حدث خطأ أثناء التحديث", "danger")
        
    return redirect(request.referrer or url_for('home_blueprint.influencer_detail', id=id))


    target_niches = []
    if preference and preference.target_niches:
        try:
            target_niches = json.loads(preference.target_niches) if isinstance(preference.target_niches, str) else preference.target_niches
        except:
            pass

    return render_template('home/profile.html', segment='profile', preference=preference, target_niches=target_niches)


@blueprint.route('/discover')
@login_required
@permission_required('influencers', 'read')
def discover():
    from apps.profiles.models import Influencer
    from apps.saas.models import Campaign
    influencers = Influencer.query.all()
    from apps.home.util import get_unified_table_data
    accounts_with_metrics = get_unified_table_data()
    
    # Pass campaigns instead of shortlists for the Add to Campaign modal
    campaigns = Campaign.query.filter_by(agency_id=current_user.agency_id).all()
    
    return render_template('home/discover.html', segment='discover', influencers=influencers, accounts_with_metrics=accounts_with_metrics, campaigns=campaigns)

@blueprint.route('/shortlists', methods=['GET', 'POST'])
@login_required
@permission_required('campaigns', 'read')
def shortlists():
    from apps import db
    from apps.saas.models import Shortlist

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        if name:
            # new_list = Shortlist(
            #     name=name,
            #     description=description,
            #     created_by=current_user.id
            #     # Note: creating a shortlist here without a campaign_id will fail DB constraint.
            #     # In a campaign-centric model, shortlists are created inside a campaign view.
            # )
            # db.session.add(new_list)
            # db.session.commit()
            flash('تم إنشاء القائمة بنجاح', 'success')
        return redirect(url_for('home_blueprint.shortlists'))

    from apps.saas.models import Campaign
    lists = Shortlist.query.join(Campaign).filter(Campaign.agency_id == current_user.agency_id).all()
    return render_template('home/shortlists.html', segment='shortlists', shortlists=lists)

@blueprint.route('/shortlists/<int:id>', methods=['GET'])
@login_required
@permission_required('campaigns', 'read')
def shortlist_detail(id):
    from apps.saas.models import Campaign
    shortlist = Shortlist.query.join(Campaign).filter(Shortlist.id == id, Campaign.agency_id == current_user.agency_id).first_or_404()
    return render_template('home/shortlist_detail.html', segment='shortlists', shortlist=shortlist)

@blueprint.route('/shortlists/add', methods=['POST'])
@login_required
def shortlist_add():
    from apps import db
    from apps.saas.models import Shortlist
    from apps.profiles.models import Influencer

    influencer_id = request.form.get('influencer_id')
    campaign_id = request.form.get('campaign_id')

    if influencer_id and campaign_id:
        from apps.saas.models import Campaign
        # Find the campaign and its default shortlist
        campaign = Campaign.query.filter_by(id=campaign_id, agency_id=current_user.agency_id).first()
        shortlist = Shortlist.query.filter_by(campaign_id=campaign_id).first()
        influencer = Influencer.query.get(influencer_id)

        if shortlist and influencer:
            if influencer not in shortlist.influencers:
                # We need to enforce tracking limit here as well, since this is a different endpoint
                from apps.saas.models import Subscription, shortlist_influencer
                subscription = Subscription.query.filter_by(agency_id=current_user.agency_id, status='active').first()
                if subscription and subscription.plan:
                    plan_limit = subscription.plan.tracking_limit
                    count_query = db.session.query(db.func.count(db.distinct(shortlist_influencer.c.influencer_id)))\
                        .join(Shortlist, Shortlist.id == shortlist_influencer.c.shortlist_id)\
                        .join(Campaign, Campaign.id == Shortlist.campaign_id)\
                        .filter(Campaign.agency_id == current_user.agency_id)
                    current_tracked = count_query.scalar() or 0
                    
                    if current_tracked >= plan_limit:
                        flash(f'لقد وصلت للحد الأقصى لباقة الاشتراك الخاصة بك ({plan_limit} مؤثر). يرجى الترقية لإضافة المزيد.', 'danger')
                        return redirect(request.referrer or url_for('home_blueprint.discover'))

                shortlist.influencers.append(influencer)
                db.session.commit()
                flash('تم الإضافة بنجاح', 'success')
            else:
                flash('المؤثر موجود بالفعل في هذه الحملة', 'info')
        else:
            flash('حدث خطأ في الإضافة', 'danger')
    return redirect(request.referrer or url_for('home_blueprint.discover'))



@blueprint.route('/<template>')
@login_required
def route_template(template):
    """
    A route function that handles dynamic routing for HTML templates.

    This function is responsible for serving HTML templates based on the provided template name. It takes a template parameter, which is a string representing the name of the template file. The function appends the '.html' extension to the template name if it doesn't already end with '.html'.

    The function first detects the current page by calling the get_segment() function with the request object. The get_segment() function extracts the last segment from the request path and returns it. If the segment is an empty string, it is set to 'index'.

    The function then attempts to render the template by calling the render_template() function with the template name and the segment variable. If the template is found, it is rendered with the segment variable and returned as the response.

    If a TemplateNotFound exception is raised, indicating that the template file does not exist, the function renders the 'home/page-404.html' template and returns it with a 404 status code.

    If any other exception is raised, the function renders the 'home/page-500.html' template and returns it with a 500 status code.

    Parameters:
        template (str): The name of the template file.

    Returns:
        The rendered HTML template if it exists, or the 'home/page-404.html' or 'home/page-500.html' template with the corresponding status code.
    """
    try:
        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):
    """
    Get the segment from the request path and return it.

    Parameters:
        request (object): The request object containing the path.

    Returns:
        str: The segment extracted from the request path. If the segment is an empty string, it is set to 'index'.
        None: If an exception occurs while extracting the segment.
    """
    try:
        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except:
        return None


#////////////////////////////////////////////////////////////////////////////////////////


@blueprint.route("/log", methods=["GET", "POST"])
@login_required
@permission_required('reports', 'read')
def log():
    """
    Renders the log page with logs based on the specified date range.

    Parameters:
        None

    Returns:
        str: The rendered log page template with logs, from_date, and to_date.
    """
    page = request.args.get("page", 1, type=int)
    per_page = 50  # Number of logs per page

    from_date = request.args.get("from_date", datetime.date.min)
    to_date = request.args.get("to_date", datetime.date.max)
    from_date=from_date if from_date else datetime.date.min
    to_date=to_date if to_date else datetime.date.max

    logs = (
        Log.query.filter(Log.creation_date >= from_date, Log.creation_date <= to_date)
        .order_by(Log.creation_date.desc())
        .order_by(Log.creation_time.desc())
        .paginate(page=page, per_page=per_page)
    )

    return render_template("home/log.html", logs=logs, from_date=from_date, to_date=to_date)

#////////////////////////////////////////////////////////////////////////////////////////

# profile_data: dict = {
#     "username": '',
#     "platform": '',
#     "public_profile_name": '',
#     "followers": 0,
#     "likes": 0,
#     "posts": 0,
#     "profile_picture": '',
#     "bio_text": '',
#     "external_url": '',
#     "time_taken": 0,
#     "error": ''
#     "existing_record":""
# }



@blueprint.route("/search", methods=["GET", "POST"])
@login_required
@permission_required('influencers', 'read')
@Log.add_log("عملية بحث")
def search():
    """
    Local database search for influencers by social account username.
    """
    if request.method == "GET" and not request.args.get("from_add"):
        session.pop("profile_data", None)
        session.pop("current_influencer_id", None)
        session.pop("search_flow", None)

    form = SearchForm()
    form.platform.choices = [(str(p.id), p.name) for p in Platform.query.all()]

    influencer = None

    if form.validate_on_submit():
        platform = form.platform.data
        username = form.username.data

        existingRecord = SocialAccount.query.filter_by(username=username, platform_id=platform).first()
        if existingRecord:
            influencer = existingRecord.influencer
        else:
            flash("إسم المستخدم غير موجود بقاعدة البيانات", "info")

    shortlists = []
    if hasattr(current_user, 'agency_id') and current_user.agency_id:
        from apps.saas.models import Shortlist
        shortlists = Shortlist.query.filter_by(agency_id=current_user.agency_id).all()

    return render_template("home/search.html", form=form, influencer=influencer, shortlists=shortlists)

@blueprint.route('/favourites/add', methods=['POST'])
@login_required
@permission_required('influencers', 'write')
def favourite_add():
    from apps import db
    from apps.saas.models import Favourite
    from apps.profiles.models import Influencer

    influencer_id = request.form.get('influencer_id')

    if influencer_id:
        influencer = Influencer.query.get(influencer_id)
        if influencer:
            existing = Favourite.query.filter_by(
                agency_id=current_user.agency_id,
                influencer_id=influencer.id
            ).first()
            if not existing:
                new_fav = Favourite(
                    agency_id=current_user.agency_id,
                    influencer_id=influencer.id
                )
                db.session.add(new_fav)
                db.session.commit()
                flash('تم إضافة المؤثر إلى المفضلة بنجاح', 'success')
            else:
                flash('المؤثر موجود بالفعل في المفضلة', 'info')
        else:
            flash('حدث خطأ. المؤثر غير موجود.', 'danger')
    return redirect(request.referrer or url_for('home_blueprint.discover'))

@blueprint.route('/favourites', methods=['GET'])
@login_required
@permission_required('influencers', 'read')
def favourites():
    from apps.saas.models import Favourite
    favorites_list = Favourite.query.filter_by(agency_id=current_user.agency_id).all()
    return render_template('home/favourites.html', segment='discover', favourites=favorites_list)

@blueprint.route('/favourites/remove', methods=['POST'])
@login_required
@permission_required('influencers', 'write')
def favourite_remove():
    from apps import db
    from apps.saas.models import Favourite
    
    favourite_id = request.form.get('favourite_id')
    if favourite_id:
        favourite = Favourite.query.filter_by(id=favourite_id, agency_id=current_user.agency_id).first()
        if favourite:
            db.session.delete(favourite)
            db.session.commit()
            flash('تم إزالة المؤثر من المفضلة بنجاح', 'success')
        else:
            flash('لم يتم العثور على المؤثر في المفضلة', 'danger')
    return redirect(request.referrer or url_for('home_blueprint.favourites'))

@blueprint.route('/scrape_start', methods=['POST'])
@login_required
def scrape_start():
    """
    Receives the scrape form, saves data to session, and renders the loading page immediately.
    The loading page then auto-submits to the real admin_scrape_influencer endpoint.
    """
    from apps.authentication.util import admin_required as _admin_required
    from apps.social.models import Platform
    from apps.home.forms import SearchForm

    form = SearchForm()
    form.platform.choices = [(str(p.id), p.name) for p in Platform.query.all()]

    platform = request.form.get('platform', '')
    username = request.form.get('username', '').strip().lstrip('@')
    csrf_token = request.form.get('csrf_token', '')

    # Store in session so the real endpoint can re-read if needed
    session['scrape_pending_platform'] = platform
    session['scrape_pending_username'] = username

    return render_template(
        'home/scrape_loading.html',
        platform=platform,
        username=username,
        csrf_token=csrf_token,
        scrape_url=url_for('home_blueprint.admin_scrape_influencer')
    )


@blueprint.route('/admin_scrape_influencer', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('influencers', 'write')
@Log.add_log("جلب بيانات مؤثر")
def admin_scrape_influencer():
    """
    Admin-only route to scrape influencer data from external API and add to DB.
    """
    from apps import db
    from apps.social.models import Platform, SocialAccount, SocialPost
    from apps.profiles.models import Influencer
    from apps.reports.models import ScanResults, ScanLog
    
    if request.method == "GET" and not request.args.get("from_add"):
        session.pop("profile_data", None)
        session.pop("current_influencer_id", None)
        session.pop("search_flow", None)

    session["search_flow"] = True

    form = SearchForm()
    form.platform.choices = [(str(p.id), p.name) for p in Platform.query.all()]

    profile_data = None

    if form.validate_on_submit():
        platform = form.platform.data
        username = form.username.data

        try:
            session.pop("profile_data", None)
            
            # Clean username and extract from URL if necessary
            original_username = username
            username = username.strip().lstrip('@')
            
            if "snapchat.com/" in username:
                username = username.split("snapchat.com/")[-1].lstrip('@').replace("add/", "")
            elif "instagram.com/" in username:
                username = username.split("instagram.com/")[-1].strip('/').split('/')[0]
            elif "tiktok.com/" in username:
                username = username.split("tiktok.com/")[-1].lstrip('@').strip('/').split('/')[0]
            print(f"[DEBUG] Original username: '{original_username}', Cleaned username: '{username}'")
            
            print(f"[DEBUG] Querying DB for existingRecord with username: '{username}', platform_id: '{platform}'")
            existingRecord = SocialAccount.query.filter_by(username=username, platform_id=platform).first()
            
            print(f"[DEBUG] Calling ScraperFactory for username: '{username}', platform_id: '{platform}'")
            platform_obj = Platform.query.get(platform)
            platform_name_english = platform_obj.name_english.lower().strip() if platform_obj else 'instagram'
            
            # Determine provider dynamically or default to rapidapi
            provider = 'rapidapi' if platform_name_english == 'instagram' else 'apify'
            
            from apps.services.scrapers.factory import ScraperFactory
            scraper = ScraperFactory.get_scraper(platform_name_english, provider=provider)
            profile_data = scraper.fetch_profile(username)
            
            # Check for error early (User Request #2)
            if profile_data.get("error"):
                from apps.reports.models import ScanLog
                error_msg = profile_data.get("error", "فشل في الجلب")
                new_scan_log = ScanLog(
                    success_count={},
                    failure_count={platform_name_english: 1},
                    failures=[{"handle": username, "error": error_msg}],
                    time_taken="0.0s"
                )
                db.session.add(new_scan_log)
                db.session.commit()
                flash(error_msg, "danger")
                return redirect(url_for('authentication_blueprint.route_default'))
                
            # Formatting to standard dictionary for DB insertion
            followers_count = profile_data.get("followers_count", 0)
            total_likes = profile_data.get("total_likes", 0)
            total_posts = profile_data.get("total_posts", 0)
            full_name = profile_data.get("full_name", username)
            
            profile_data["followers"] = followers_count
            profile_data["likes"] = total_likes
            profile_data["public_profile_name"] = full_name
            profile_data["profile_picture"] = profile_data.get("profile_pic_url", "")
            
            profile_data["platform_id"] = platform
            profile_data["platform"] = platform_obj.name if platform_obj else platform_name_english
            profile_data["platform_name_english"] = platform_name_english
            
            if existingRecord:
                existingRecord.followers = followers_count
                existingRecord.total_likes = total_likes
                existingRecord.total_posts = total_posts
                existingRecord.public_profile_name = full_name
                existingRecord.profile_picture = profile_data.get("profile_pic_url", "")
                existingRecord.bio_text = profile_data.get("bio_text", "")
                existingRecord.external_url = profile_data.get("external_url", "")
                if 'recent_posts' in profile_data and profile_data['recent_posts']:
                    SocialPost.query.filter_by(socialaccount_id=existingRecord.id).delete()
                    posts_to_save = []
                    for p in profile_data['recent_posts']:
                        new_post = SocialPost(
                            influencer_id=existingRecord.influencer_id,
                            socialaccount_id=existingRecord.id,
                            platform_post_id=str(p.get('platform_post_id')),
                            posted_at=p.get('posted_at'),
                            plays=p.get('plays', 0),
                            likes=p.get('likes', 0),
                            comments=p.get('comments', 0),
                            shares=p.get('shares', 0),
                            saves=p.get('saves', 0),
                            caption=p.get('caption', ''),
                            raw_data=p.get('raw_data', {})
                        )
                        posts_to_save.append(new_post)
                    if posts_to_save:
                        db.session.bulk_save_objects(posts_to_save)
                
                db.session.commit()

                flash("تم تحديث بيانات الحساب الموجود بالفعل بنجاح", "success")
                return redirect(url_for('authentication_blueprint.admin_influencers'))
            else:
                import json
                scraped_data_json = json.dumps(profile_data, default=str)
                return render_template('home/scrape_review.html', scraped_data=profile_data, scraped_data_json=scraped_data_json)

        except Exception as e:
            platform_obj = Platform.query.get(platform) if platform else None
            platform_name = platform_obj.name_english if platform_obj else "Unknown"
            
            new_scan_log = ScanLog(
                success_count={},
                failure_count={platform_name: 1},
                failures=[{"handle": username, "error": str(e)}],
                time_taken="0.0s"
            )
            db.session.add(new_scan_log)
            db.session.commit()
            
            flash("فشل في الجلب", "danger")

    return redirect(url_for('authentication_blueprint.admin_influencers'))


@blueprint.route('/admin_scrape_save', methods=['POST'])
@login_required
@admin_required
@Log.add_log("حفظ بيانات مؤثر بعد المراجعة")
def admin_scrape_save():
    """
    Saves the reviewed scraped influencer data to the database.
    """
    from apps import db
    from apps.social.models import Platform, SocialAccount, SocialPost
    from apps.profiles.models import Influencer
    from apps.reports.models import ScanResults, ScanLog
    import json
    
    scraped_data_json = request.form.get('scraped_data_json')
    if not scraped_data_json:
        flash("بيانات مفقودة", "danger")
        return redirect(url_for('authentication_blueprint.admin_influencers'))
        
    try:
        profile_data = json.loads(scraped_data_json)
    except json.JSONDecodeError:
        flash("خطأ في قراءة البيانات", "danger")
        return redirect(url_for('authentication_blueprint.admin_influencers'))
        
    # Manual inputs from review page
    manual_email = request.form.get('email', '').strip()
    manual_phone = request.form.get('phone', '').strip()
    manual_country = request.form.get('country', '').strip()
    manual_city = request.form.get('city', '').strip()
    manual_category = request.form.get('category', '').strip()
    manual_gender = request.form.get('gender', '').strip()
    
    platform = profile_data.get("platform_id")
    platform_name_english = profile_data.get("platform_name_english", "Unknown")
    username = profile_data.get("username")
    full_name = profile_data.get("public_profile_name", username)
    followers_count = profile_data.get("followers", 0)
    total_likes = profile_data.get("total_likes", profile_data.get("likes", profile_data.get("likes_count", 0)))
    total_posts = profile_data.get("total_posts", profile_data.get("posts", 0))

    try:
        import logging
        logger = logging.getLogger(__name__)

        # Handle unique Influencer name constraint
        existing_influencer = Influencer.query.filter_by(full_name=full_name).first()
        if existing_influencer:
            new_influencer_id = existing_influencer.id
            # Update existing influencer with manual data if empty
            if manual_email and not existing_influencer.email: existing_influencer.email = manual_email
            if manual_phone and not existing_influencer.phone: existing_influencer.phone = manual_phone
            if manual_country and not existing_influencer.country: existing_influencer.country = manual_country
            if manual_city and not existing_influencer.city: existing_influencer.city = manual_city
            if manual_category and not existing_influencer.category: existing_influencer.category = manual_category
            if manual_gender and not existing_influencer.gender: existing_influencer.gender = manual_gender
        else:
            new_influencer = Influencer(
                full_name=full_name,
                profile_picture=profile_data.get("profile_pic_url"),
                email=manual_email or None,
                phone=manual_phone or None,
                country=manual_country or None,
                city=manual_city or None,
                category=manual_category or None,
                gender=manual_gender or None
            )
            db.session.add(new_influencer)
            db.session.flush()
            new_influencer_id = new_influencer.id

        new_social_account = SocialAccount(
            influencer_id=new_influencer_id,
            platform_id=platform,
            username=username,
            public_profile_name=full_name,
            followers=followers_count,
            total_likes=total_likes,
            total_posts=total_posts,
            profile_picture=profile_data.get("profile_pic_url"),
            bio_text=profile_data.get("bio_text"),
            external_url=profile_data.get("external_url")
        )
        db.session.add(new_social_account)
        db.session.flush()
        
        if 'recent_posts' in profile_data and profile_data['recent_posts']:
            for p in profile_data['recent_posts']:
                new_post = SocialPost(
                    influencer_id=new_influencer_id,
                    socialaccount_id=new_social_account.id,
                    platform_post_id=str(p.get('platform_post_id')),
                    posted_at=p.get('posted_at'),
                    plays=p.get('plays', 0),
                    likes=p.get('likes', 0),
                    comments=p.get('comments', 0),
                    shares=p.get('shares', 0),
                    saves=p.get('saves', 0),
                    caption=p.get('caption', ''),
                    raw_data=p.get('raw_data', {})
                )
                db.session.add(new_post)
        
        new_scan_result = ScanResults(
            socialaccount_id=new_social_account.id,
            followers=followers_count,
            likes=total_likes,
            posts=total_posts,
            time_taken="0.0s"
        )
        db.session.add(new_scan_result)
        
        new_scan_log = ScanLog(
            success_count={platform_name_english: 1},
            failure_count={},
            failures=[],
            time_taken="0.0s"
        )
        db.session.add(new_scan_log)
        
        db.session.commit()
        flash("تم حفظ بيانات المؤثر بنجاح", "success")
    except Exception as db_e:
        db.session.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[DB ERROR] Failed to save scraped profile: {db_e}")
        
        new_scan_log = ScanLog(
            success_count={},
            failure_count={platform_name_english: 1},
            failures=[{"handle": username, "error": str(db_e)}],
            time_taken="0.0s"
        )
        db.session.add(new_scan_log)
        db.session.commit()
        
        flash("فشل في الحفظ", "danger")

    return redirect(url_for('authentication_blueprint.admin_influencers'))


# ////////////////////////////////////////////////////////////////////////////////////////

# ////////////////////////////////////////////////////////////////////////////////////////


# @blueprint.route("/start_scan", methods=["GET", "POST"])
# @login_required
# @Log.add_log("عملية مسح")
# def start_scan():
#     current_app.sched.run_job("job1")
#     flash("تم بدء عملية المسح", "success")
#     return redirect(url_for("home_blueprint.index"))
