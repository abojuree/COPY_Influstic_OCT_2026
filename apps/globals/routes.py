from datetime import datetime
from os import path
import os
import random
from flask import current_app, redirect, render_template, flash, request, send_file, send_from_directory, url_for
from flask_login import login_required
from werkzeug.datastructures import FileStorage
from apps.authentication.util import admin_required
import pgdumplib
from db_backup import create_backup

from apps.globals import blueprint

from apps.globals.util import download_excel, import_content_from_excel
from apps.home.models import Log
from apps.home.util import get_summerized_report

from icecream import ic


@blueprint.route("/export_to_excel/<model_name>")
@login_required
@admin_required
@Log.add_log("تصدير بيانات لملف إكسل")
def export_to_excel(model_name):
    """
    Export data from a specified model to an Excel file and send it as a download.

    Parameters:
        model_name (str): The name of the model to export data from.

    Returns:
        flask.Response: The response object containing the Excel file as a download.

    Raises:
        None
    """
    file_path: str = download_excel(model_name)#.replace("app/", "")
    # ic(file_path)
    if not file_path:
        flash("No data to export", "danger")
        return render_template("home/index.html", segment="index", stats=get_summerized_report())
    return send_file(
        path_or_file=file_path,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@blueprint.route("/photo/<filename>")
def get_photo(filename):
    upload_folder = path.join(current_app.root_path, "static", "profile_pictures")
    try:
        ic(filename)
        return send_from_directory(upload_folder, filename)
    except:
        filenames = [f"donotdelete{x}.jpeg" for x in range(10)]
        filename = random.choice(filenames)
        return send_from_directory(upload_folder, filename)


@blueprint.route("/upload_excel", methods=["GET", "POST"])
@login_required
@admin_required
@Log.add_log("إستيراد بيانات من ملف إكسل")
def upload_excel():
    if request.method == "POST":
        # Get the selected option
        selected_option = request.form.get("option")

        # check if the post request has the file part
        if "excel_file" not in request.files:
            flash("لم يتم إختيار ملف", "danger")
            return redirect(request.url)
        file: FileStorage = request.files["excel_file"]
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == "":
            flash("لم يتم إختيار ملف", "danger")
            return redirect(request.url)
        if file:
            imported = import_content_from_excel(file, selected_option)
            if imported:
                flash("تم إستيراد البيانات بنجاح", "success")
            else:
                flash("خطأ أثناء حفظ البيانات", "danger")
        return redirect(url_for("globals_blueprint.upload_excel"))
    return render_template("globals/upload_excel.html")


@blueprint.route("/backup_db")
@login_required
@admin_required
@Log.add_log("تنزيل نسخة إحتياطية من قاعدة البيانات")
def backup_db():
    backup_path = create_backup()
    if backup_path and os.path.exists(backup_path):
        return send_file(backup_path, as_attachment=True)
    flash("فشل في إنشاء النسخة الإحتياطية", "danger")
    return redirect(url_for("home_blueprint.index"))