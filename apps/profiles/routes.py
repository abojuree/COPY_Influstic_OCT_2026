from apps import db

from flask import (
    jsonify,
    render_template,
    redirect,
    request,
    session,
    url_for,
    flash,
)
from flask_wtf.file import FileField
from flask_login import login_required, current_user

from sqlalchemy import desc
from icecream import ic
from sqlalchemy.exc import IntegrityError

from apps.home.models import Log
from apps.home.util import search_user_profile
from apps.profiles import blueprint
from apps.profiles.forms import InfluencerForm
from apps.profiles.models import Influencer

from apps.reports.models import ScanResults
from apps.social.models import SocialAccount


@blueprint.route("/influencers")
@login_required
def influencers():
    """
    Route decorator for the "/influencers" endpoint. This function is responsible for displaying a paginated list of influencers based on the search terms provided in the query string.

    Parameters:
        None

    Returns:
        A rendered HTML template "profiles/influencers.html" with the list of influencers.

    Raises:
        None
    """
    page = request.args.get("page", 1, type=int)
    per_page = 50  # Number of logs per page

    # Get search term from query string (optional)
    search_terms = request.args.get("q", "")

    from flask_login import current_user
    from apps.saas.models import Shortlist

    query = Influencer.query
    if current_user.username != 'admin' and current_user.agency_id:
        query = query.join(Influencer.shortlists).filter(Shortlist.agency_id == current_user.agency_id)

    # filter influencers
    influencers = (
        query.filter(
            (Influencer.full_name.ilike(f"%{search_terms}%"))
            | (
                Influencer.socialaccounts.any(
                    SocialAccount.username.ilike(f"%{search_terms}%")
                )
            )
        ).paginate(page=page, per_page=per_page, error_out=False)
        # .all()
    )
    return render_template("profiles/influencers.html", influencers=influencers, search_terms=search_terms)


@blueprint.route("/discover")
@login_required
def discover():
    """
    Global discovery route. Displays the full global registry of influencers
    without filtering by the user's shortlists.
    """
    page = request.args.get("page", 1, type=int)
    per_page = 50

    search_terms = request.args.get("q", "")

    query = Influencer.query
    
    # filter influencers globally
    influencers = (
        query.filter(
            (Influencer.full_name.ilike(f"%{search_terms}%"))
            | (
                Influencer.socialaccounts.any(
                    SocialAccount.username.ilike(f"%{search_terms}%")
                )
            )
        ).paginate(page=page, per_page=per_page, error_out=False)
    )
    
    # Get the user's shortlists to pass to the template for the "Add to Shortlist" modal/dropdown
    from apps.saas.models import Shortlist, Campaign
    user_shortlists = Shortlist.query.join(Campaign).filter(Campaign.agency_id == current_user.agency_id).all() if current_user.agency_id else []
    
    return render_template("profiles/discover.html", influencers=influencers, search_terms=search_terms, shortlists=user_shortlists)

@blueprint.route("/influencer_add", methods=["GET", "POST"])
@login_required
@Log.add_log("إضافة ملف")
def influencer_add():
    """
    Adds a new influencer to the database.

    This function is a route handler for the "/influencer_add" endpoint. It requires the user to be logged in.
    It also logs the action of adding a new influencer.

    Parameters:
    None

    Returns:
    If the form is valid and the new influencer is added successfully, it redirects to the "social_blueprint.socialaccount_add" endpoint with the newly created influencer's ID and profile data.
    If there is an IntegrityError (duplicate influencer name), it redirects to the "profiles_blueprint.influencer_edit" endpoint with the existing influencer's ID and profile data.
    If there is any other exception, it rolls back the database session and flashes an error message.
    If the form is not valid, it renders the "profiles/influencer_add.html" template with the form and profile data.
    """
    profile_data = {}
    if session.get("profile_data"):
        profile_data = session.pop("profile_data")  # Get and remove from session
        session.pop("search_flow", None)  # Clear search flow flag
        session.pop("current_influencer_id", None)  # Clear any stored influencer ID

    form = InfluencerForm()  # Create an instance of the form
    if form.validate_on_submit():
        try:
            new_influencer = Influencer(
                full_name=form.full_name.data,
                gender=form.gender.data,
                country=form.country.data,
                city=form.city.data,
                phone=form.phone.data,
                email=form.email.data,
                profile_picture=None,  # Set a default value initially
            )

            # Check if the profile picture is a URL/Local and save it
            set_as_default_profile_picture = form.set_as_default_profile_picture.data
            if set_as_default_profile_picture:
                new_influencer.profile_picture = profile_data["profile_picture"] if profile_data else None
            elif form.profile_picture.data:
                new_influencer.save_profile_picture(picture_file=form.profile_picture.data)

            db.session.add(new_influencer)
            db.session.commit()
            flash("تم إضافة الملف", "success")
            
            # Store profile data in session only if we have it
            if profile_data:
                session["profile_data"] = profile_data
                session["search_flow"] = True
            
            return redirect(url_for("social_blueprint.socialaccount_add", influencer_id=new_influencer.id))
        except IntegrityError as e:
            ic("IntegrityError in <influencer_add>: ", e)
            db.session.rollback()
            flash(
                "إسم الملف موجود بالفعل, تم تحويلك إلى صفحة تعديل الملف",
                "danger",
            )
            influencer_id = (
                Influencer.query.filter_by(full_name=form.full_name.data).first().id
            )
            return redirect(
                url_for(
                    "profiles_blueprint.influencer_edit",
                    influencer_id=influencer_id
                )
            )

        except Exception as e:
            ic("Error in <influencer_add>: ", e)
            db.session.rollback()
            flash(f"حدث خطأ أثناء إضافة الملف\n{e}", "danger")
    return render_template("profiles/influencer_add.html", form=form, profile_data=profile_data)


@blueprint.route("/influencer_delete/<int:influencer_id>", methods=["POST"])
@login_required
@Log.add_log("حذف ملف")
def influencer_delete(influencer_id):
    """
    Deletes an influencer from the database.

    Parameters:
        influencer_id (int): The ID of the influencer to be deleted.

    Returns:
        redirect: A redirect to the 'influencers' page if the influencer is successfully deleted.
                  Otherwise, a redirect to the 'influencers' page with a flash message indicating that the influencer does not exist.
    """
    influencer = Influencer.query.get(influencer_id)
    if not influencer:
        flash("الملف غير موجود", "danger")
        return redirect(url_for("profiles_blueprint.influencers"))
    db.session.delete(influencer)
    db.session.commit()
    flash("تم حذف الملف", "success")
    return redirect(url_for("profiles_blueprint.influencers"))


@blueprint.route("/influencer_edit/<int:influencer_id>", methods=["GET", "POST"])
@login_required
@Log.add_log("تعديل ملف")
def influencer_edit(influencer_id):
    """
    Edit an influencer's profile.

    Parameters:
        influencer_id (int): The ID of the influencer to be edited.

    Returns:
        redirect: A redirect to the 'influencers' page if the influencer does not exist.
                  Otherwise, a redirect to the 'influencers' page with a success message.
    """
    # profile_data = {}
    # if session.get("profile_data"):
    #     profile_data = session["profile_data"]
    #     # session.pop("profile_data")

    influencer = Influencer.query.get(influencer_id)
    if not influencer:
        flash("الملف غير موجود", "danger")
        return redirect(url_for("profiles_blueprint.influencers"))

    # Prepare the data for the template
    scanresults=[]
    socialaccounts = influencer.socialaccounts
    for socialaccount in socialaccounts:
        scan_result = (
            db.session.query(ScanResults)
            .filter_by(socialaccount_id=socialaccount.id)
            .order_by(desc(ScanResults.creation_date))
            .limit(5)
            .all()
        )
        scanresults.extend(scan_result)

    profile_data_list = []
    for socialaccount in socialaccounts:
        profile_data = search_user_profile(socialaccount.username, socialaccount.platform_id)
        profile_data_list.append(profile_data)

    form = InfluencerForm(obj=influencer)  # Create an instance of the form
    if form.validate_on_submit():
        influencer.full_name = form.full_name.data
        influencer.gender = form.gender.data
        influencer.country = form.country.data
        influencer.city = form.city.data
        influencer.phone = form.phone.data
        influencer.email = form.email.data
        # influencer.profile_picture=form.profile_picture.data
        
        # ic(form.profile_picture.data)
        if type(form.profile_picture) == FileField and form.profile_picture.data:
            influencer.save_profile_picture(picture_file=form.profile_picture.data)

        db.session.commit()
        flash("تم تعديل الملف", "success")
        return redirect(url_for("profiles_blueprint.influencers"))

    return render_template(
        "profiles/influencer_edit.html",
        form=form,
        influencer=influencer,
        scanresults=scanresults,
        profile_data_list=profile_data_list,
    )
    
    
@blueprint.route("/influencer/update_picture", methods=["POST"])
@login_required
@Log.add_log("تعديل صورة ملف")
def influencer_update_picture():
    """
    Updates the picture of an influencer.

    This function is a route handler for the "/influencer/update_picture" endpoint. It is responsible for updating the picture of an influencer when a POST request is made to this endpoint.

    Parameters:
        None

    Returns:
        A JSON response containing the redirect URL to the influencer edit page if the picture update is successful. Otherwise, a JSON response with an error message is returned.

    Raises:
        None
    """
    influencer_id = request.form.get('influencer_id')
    picture_url = request.form.get('picture_url')
    influencer = Influencer.query.get(influencer_id)
    
    if not influencer:
        flash("الملف غير موجود", "danger")
        return jsonify({"redirect_url": url_for("profiles_blueprint.influencers")})
    if not picture_url:
        flash("الرجاء تحديد صورة", "danger")
        return jsonify({"redirect_url": url_for("profiles_blueprint.influencer_edit", influencer_id=influencer_id)})
    
    influencer.profile_picture = picture_url
    ic(influencer.profile_picture, picture_url)
    # influencer.download_image(picture_url)
    flash("تم تعديل الصورة", "success")
    return jsonify({"redirect_url": url_for("profiles_blueprint.influencer_edit", influencer_id=influencer_id)})