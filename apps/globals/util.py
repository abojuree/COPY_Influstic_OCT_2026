import datetime
from os import path
from icecream import ic
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from apps import db
import pandas as pd
from flask import current_app, flash

from apps.content_types.models import Content
from apps.home.models import Log
from apps.profiles.models import Influencer
from apps.reports.models import ScanResults, ScanLog
from apps.social.models import SocialAccount, SocialAccount_Content
from apps.authentication.models import Users


def download_excel(model_name) -> str:
    """
    Downloads data from a given model and saves it to an Excel file. 

    Args:
        model_name (str): The name of the model to download data from.

    Returns:
        str: The full path of the saved Excel file.
    """
    model = globals().get(model_name)
    if not model:
        ic("Model not found")
        return ""

    items = model.query.all()
    if not items:
        ic("No data to export")
        return ""

    data = {}
    for column in model.__table__.columns:
        column_name: str = column.name
        if column_name.endswith("_id"):
            column_name_2 = column_name.replace("_id", "")
            data[column_name_2] = [getattr(item, column_name_2) for item in items]
        data[column.name] = [getattr(item, column_name) for item in items]

    df = pd.DataFrame(data)

    excel_file_path = (
        f"{model_name}-{datetime.datetime.now().date()}-{datetime.datetime.now().time()}.xlsx"
    )
    excel_file_path = secure_filename(excel_file_path)

    # Create an ExcelWriter object

    # excel_writer = pd.ExcelWriter(os.path.join('/home/ziada/YourSpace/app', excel_file_path), engine='xlsxwriter')
    excel_writer = pd.ExcelWriter(excel_file_path, engine="xlsxwriter")
    # Write the DataFrame to Excel
    df.to_excel(excel_writer, sheet_name=f"YourSpace-{model_name}", index=False)
    # Close the ExcelWriter object using close() method
    excel_writer.close()

    # Get the full path of the excel file
    full_path = path.abspath(excel_file_path)
    return full_path


def import_content_from_excel(file: FileStorage, selected_option: str) -> bool:
    try:
        file_extension = path.splitext(file.filename)[1]
        file_path = path.join(current_app.root_path, "import" + file_extension)
        with open(file_path, "wb") as f:
            f.write(file.read())
    except Exception as e:
        ic("Error while copying the file in <import_content_from_excel>: ", e)
        flash(f"خطأ أثناء نسخ الملف: {e}", "danger")
        return False

    if selected_option == "contents":
        # Define the column names
        column_names = [
            "name",
            "description",
        ]  # Add other column names here as necessary
        # Read the CSV file

        if file_extension in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, names=column_names, header=None)
        else:
            df = pd.read_csv(file_path, names=column_names, header=None, encoding="utf-8")
        # Iterate over the rows of the DataFrame
        for index, row in df.iterrows():
            # Create a new Content object
            content = Content.query.filter_by(name=row["name"].strip()).first()
            if content:
                continue
            content = Content(
                name=row["name"].strip(),
                description=str(row.get("description", "")).strip(),
            )
            # Add the new Content object to the session
            db.session.add(content)

    elif selected_option == "accounts":
        # Define the column names
        column_names = ["username", "platform_id", "influencer", "content"]
        # Read the CSV file
        if file_extension in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, names=column_names, header=None)
        else:
            df = pd.read_csv(file_path, names=column_names, header=None, encoding="utf-8")
        # Iterate over the rows of the DataFrame
        for index, row in df.iterrows():
            # Create a new SocialAccount object
            # Check if there is a SocialAccount with the same username
            existing_social_account = SocialAccount.query.filter_by(
                username=row["username"].strip()
            ).first()
            if existing_social_account:
                continue

            influencer = Influencer.query.filter_by(
                full_name=row["influencer"].strip()
            ).first()
            if influencer:
                influencer_id = influencer.id
            else:
                # flash(f"Influencer with full name {row['influencer']} not found", "danger")
                continue

            social_account = SocialAccount(
                username=row["username"].strip(),
                platform_id=row.get("platform_id"),
                influencer_id=influencer_id,
            )
            # Add the new SocialAccount object to the session
            db.session.add(social_account)

            content = Content.query.filter_by(name=row["content"].strip()).first()
            if content:
                content_id = content.id
            else:
                # Handle the case when the content does not exist
                continue

            # Create a new record in the socialaccount_contents table
            socialaccount_content = SocialAccount_Content(
                socialaccount_id=social_account.id, content_id=content_id
            )
            # Add the new record to the session
            db.session.add(socialaccount_content)

    elif selected_option == "profiles":
        # Define the column names
        column_names = [
            "full_name",
            "gender",
            "country",
            "city",
            "phone",
            "email",
            "profile_picture",
        ]
        # Read the CSV file
        if file_extension in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, names=column_names, header=None)
        else:
            df = pd.read_csv(file_path, names=column_names, header=None, encoding="utf-8")
        # Iterate over the rows of the DataFrame
        for index, row in df.iterrows():
            # Create a new Influencer object
            # Check if there is an influencer with the same full_name
            existing_influencer = Influencer.query.filter_by(
                full_name=row["full_name"].strip()
            ).first()
            if existing_influencer:
                continue

            influencer = Influencer(
                full_name=str(row["full_name"]).strip(),
                gender=str(row.get("gender", "")).strip(),
                country=str(row.get("country", "")).strip(),
                city=str(row.get("city", "")).strip(),
                phone=str(row.get("phone", "")).strip(),
                email=str(row.get("email", "")).strip(),
                profile_picture=str(row.get("profile_picture", "")).strip(),
            )
            # Add the new Influencer object to the session
            db.session.add(influencer)

    else:
        flash("الخيار المحدد غير مدعوم", "danger")
        return False

    # Commit the session to save the new Content objects to the database
    try:
        db.session.commit()
        return True
    except Exception as e:
        ic("Error while importing the data in <import_content_from_excel>: ", e)
        db.session.rollback()
        flash(f"خطأ أثناء إستيراد البيانات: {e}", "danger")
        return False
