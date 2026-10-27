from apps import db

from flask import  render_template, redirect, request, session, url_for, flash
from flask_login import login_required

from apps.home.models import Log
from apps.home.util import search_user_profile
from apps.social import blueprint
from apps.social.forms import  SocialAccountForm
from apps.social.models import  SocialAccount, Platform
from apps.profiles.models import Influencer
from apps.content_types.models import Content

from icecream import ic
from sqlalchemy.exc import IntegrityError


@blueprint.route("/socialaccounts/<int:influencer_id>")
@login_required
def socialaccounts(influencer_id):
    """
    Retrieves a paginated list of social accounts associated with a specific influencer.

    Parameters:
        influencer_id (int): The ID of the influencer.

    Returns:
        flask.Response: The rendered template with the social accounts and influencer information.

    Raises:
        None
    """
    # Clear any lingering session data
    session.pop("profile_data", None)
    session.pop("search_flow", None)
    session.pop("current_influencer_id", None)

    page = request.args.get("page", 1, type=int)
    influencer = Influencer.query.get(influencer_id)
    if not influencer:
        flash("الملف غير موجود", "danger")
        return redirect(url_for("profiles_blueprint.influencers"))

    socialaccounts = (
        SocialAccount.query.filter_by(influencer_id=influencer_id)
        .order_by(SocialAccount.id.desc())
        .paginate(page=page, per_page=10)
    )
    return render_template(
        "social/socialaccounts.html",
        socialaccounts=socialaccounts,
        influencer=influencer,
    )


@blueprint.route("/socialaccount_add/<int:influencer_id>", methods=["GET", "POST"])
@login_required
@Log.add_log("إضافة حساب")
def socialaccount_add(influencer_id):
    """
    A view function to add a social account for a specific influencer. 
    Handles form submission, data validation, and database operations. 
    Returns the rendered template with the form, influencer, and profile data.
    """
    influencer = Influencer.query.get(influencer_id)
    if not influencer:
        flash("الملف غير موجود", "danger")
        return redirect(url_for("profiles_blueprint.influencers"))

    # Store the current influencer_id if not already stored
    if not session.get("current_influencer_id"):
        session["current_influencer_id"] = influencer_id
        return redirect(url_for("home_blueprint.search", from_add=True))

    # Only clear profile data if we're starting a new search for a different influencer
    stored_influencer_id = session.get("current_influencer_id")
    if stored_influencer_id and stored_influencer_id != influencer_id:
        session.pop("profile_data", None)
        session["current_influencer_id"] = influencer_id
        return redirect(url_for("home_blueprint.search", from_add=True))

    profile_data = session.get("profile_data", {})
    
    form = SocialAccountForm()  # Create an instance of the form
    form.platform.choices = [(str(p.id), p.name) for p in Platform.query.all()]
    
    # Pre-fill form data from profile_data if available
    if profile_data:
        form.platform.data = str(profile_data.get("platform_id", "1"))
        form.username.data = profile_data.get("username", "")
        form.bio_text.data = profile_data.get("bio_text", "No Bio")
        form.profile_picture.data = profile_data.get("profile_picture", "")
        form.external_url.data = profile_data.get("external_url", "")
        form.public_profile_name.data = profile_data.get("public_profile_name", "")

    # Get available content types for the form
    content_choices = [(c.id, c.name) for c in Content.query.all()]
    form.contents.choices = content_choices

    if form.validate_on_submit():
        try:
            new_socialaccount = SocialAccount(
                influencer_id=influencer_id,
                platform_id=int(form.platform.data),
                username=form.username.data,
                bio_text=form.bio_text.data,
                profile_picture=form.profile_picture.data,
                external_url=form.external_url.data,
                public_profile_name=form.public_profile_name.data
            )
            
            # Add selected content types
            if form.contents.data:
                new_socialaccount.contents = Content.query.filter(Content.id.in_(form.contents.data)).all()
            
            db.session.add(new_socialaccount)
            db.session.commit()

            # Clear session data after successful addition
            session.pop("profile_data", None)
            session.pop("current_influencer_id", None)
            session.pop("search_flow", None)

            flash("تم إضافة الحساب بنجاح", "success")
            return redirect(
                url_for(
                    "social_blueprint.socialaccounts",
                    influencer_id=influencer_id,
                )
            )
        except IntegrityError:
            db.session.rollback()
            flash("اسم المستخدم موجود مسبقاً", "danger")
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")

    return render_template(
        "social/socialaccount_add.html",
        form=form,
        influencer=influencer,
        profile_data=profile_data,
    )


@blueprint.route("/socialaccount_delete/<int:influencer_id>/<int:socialaccount_id>", methods=["POST"])
@login_required
@Log.add_log("حذف حساب")
def socialaccount_delete(influencer_id, socialaccount_id):
    """
    A view function to delete a social account for a specific influencer. 
    Handles the POST request to delete a social account. 

    Args:
        influencer_id (int): The ID of the influencer.
        socialaccount_id (int): The ID of the social account to be deleted.

    Returns:
        redirect: Redirects to the social accounts page of the influencer after deleting the social account.
    """
    socialaccount = SocialAccount.query.get(socialaccount_id)
    if not socialaccount:
        flash("الحساب غير موجود", "danger")
        return redirect(url_for("social_blueprint.socialaccounts", influencer_id=influencer_id))
    db.session.delete(socialaccount)
    db.session.commit()
    flash("تم حذف الحساب", "success")
    return redirect(url_for("social_blueprint.socialaccounts", influencer_id=influencer_id))


@blueprint.route("/socialaccount_edit/<int:socialaccount_id>",methods=["GET", "POST"])
@login_required
@Log.add_log("تعديل حساب")
def socialaccount_edit(socialaccount_id):
    """
    A view function to edit a social account for a specific influencer. 
    Handles the GET and POST requests to edit a social account. 

    Args:
        socialaccount_id (int): The ID of the social account to be edited.

    Returns:
        redirect or render_template: If the form is valid, redirects to the social accounts page of the influencer after editing the social account. 
        Otherwise, renders the socialaccount_edit.html template with the form and relevant data.
    """
    socialaccount = SocialAccount.query.get(socialaccount_id)
    if not socialaccount:
        flash("الحساب غير موجود", "danger")
        return redirect(url_for("profiles_blueprint.influencers"))

    # Do search
    profile_data = {}
    try:
        profile_data = search_user_profile(socialaccount.username, socialaccount.platform_id)
        if not profile_data:
            flash("لا يمكن العثور على الحساب", "danger")
        elif profile_data.get("error") is not None:
            flash(profile_data["error"], "danger")
    except Exception as e:
        ic("Error in <SocialAccount_Edit>: ", e)
        flash(f"Error: {str(e)}")  # Handle backend errors gracefully

    form = SocialAccountForm()  # Create an instance of the form and populate it with existing data
    
    # Get all platforms from the database
    form.platform.choices = [(str(p.id), p.name) for p in Platform.query.all()]
    form.platform.data = str(socialaccount.platform_id)
    form.username.data = socialaccount.username
    
    # Set content choices and selected values
    form.contents.choices = [(c.id, c.name) for c in Content.query.all()]
    if not form.is_submitted():
        form.contents.data = [content.id for content in socialaccount.contents]
    
    # Set other form fields
    form.bio_text.data = socialaccount.bio_text or profile_data.get("bio_text", "No Bio")
    form.external_url.data = socialaccount.external_url or profile_data.get("external_url", "")
    form.public_profile_name.data = socialaccount.public_profile_name or profile_data.get("public_profile_name", "")
    form.profile_picture.data = socialaccount.profile_picture or profile_data.get("profile_picture")
        
    if form.validate_on_submit():
        try:
            socialaccount.platform_id = int(form.platform.data)
            socialaccount.username = form.username.data
            
            # Get selected content IDs from the form
            selected_content_ids = request.form.getlist("contents")
            ic("Selected content IDs:", selected_content_ids)
            
            # Convert to integers and query Content objects
            content_ids = [int(id) for id in selected_content_ids]
            socialaccount.contents = Content.query.filter(Content.id.in_(content_ids)).all()
            
            socialaccount.bio_text = form.bio_text.data
            socialaccount.external_url = form.external_url.data
            socialaccount.public_profile_name = form.public_profile_name.data
            socialaccount.profile_picture = form.profile_picture.data

            db.session.commit()
            flash("تم تعديل الحساب", "success")
            return redirect(url_for("social_blueprint.socialaccounts", influencer_id=socialaccount.influencer_id))
        except Exception as e:
            ic("Error saving social account:", e)
            db.session.rollback()
            flash(f"حدث خطأ أثناء حفظ البيانات: {str(e)}", "danger")
    else:
        errors = form.errors
        ic("SocialAccount_Edit Form Errors=>", errors)

    return render_template(
        "social/socialaccount_edit.html",
        form=form,
        socialaccount=socialaccount,
        influencer=socialaccount.influencer,
        profile_data=profile_data
    )
