from flask import abort, flash, render_template, redirect, request, session, url_for, send_file, send_from_directory, jsonify, current_app
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user
)

from apps import db, login_manager
from apps.authentication import blueprint

from apps.authentication.forms import LoginForm, CreateAccountForm
from apps.authentication.models import Users, Role

from apps.authentication.util import verify_pass, create_default_admin, admin_required, permission_required

from apps.home.models import Log
from icecream import ic

from datetime import datetime, timedelta
import threading
import os
import tempfile

from apps.reports.models import ScanLog
from apps.social.models import SocialAccount
from tasks import scan_database, scan_should_stop, scan_progress as task_scan_progress, cleanup_old_scanlogs
from apps.admin.db_utils import create_db_backup, export_db_to_excel
from apps.admin.util import get_home_kpis, get_clients_kpis, get_influencers_kpis, get_system_kpis

# Global variables for scan control
scan_thread = None
scan_running = False
scan_progress = {
    "total": 0,
    "processed": 0,
    "success": 0,
    "failure": 0,
    "status": "idle",
    "message": ""
}

@blueprint.route('/')
def route_default():
    """
    Redirects to the appropriate home page based on user role and agency.
    """
    if current_user.is_authenticated:
        from apps.authentication.models import Users
        master_admin = Users.query.filter_by(username='admin').first()
        
        # If user belongs to the same agency as the master admin, they are a system employee
        if master_admin and current_user.agency_id == master_admin.agency_id:
            return redirect(url_for('authentication_blueprint.admin_dashboard'))
        else:
            # Normal users (agencies created via signup) go to the campaigns portal
            return redirect(url_for('saas_blueprint.list_campaigns'))
    
    return redirect(url_for('authentication_blueprint.login'))


# Login & Registration

@blueprint.route('/login', methods=['GET', 'POST'])
@Log.add_log("تسجيل دخول")  # Pass the message as an argument
def login():
    """
    A route function that handles the login process. It checks if the admin user exists and creates it if not. It then reads the form data, locates the user, and checks the password. If the user and password are valid, the user is logged in and redirected to the default route. If the user or password is incorrect, it renders the login template with an error message. If the user is not authenticated, it renders the login template.
    """
    login_form = LoginForm(request.form)
    if 'login' in request.form:

        # Check if admin user exists, if not create it
        create_default_admin(Users=Users,db=db)

        # read form data
        email = request.form['email']
        password = request.form['password']

        # Locate user
        user = Users.query.filter_by(email=email).first()

        # Check the password
        if user and verify_pass(password, user.password):

            login_user(user)
            return redirect(url_for('authentication_blueprint.route_default'))

        # Something (user or pass) is not ok
        return render_template('accounts/login.html',
                               msg=' بيانات الحساب خطأ, من فضلك تأكد من البريد الإلكتروني و كلمة المرور',
                               form=login_form,
                               current_year=datetime.now().year)

    if not current_user.is_authenticated:
        return render_template('accounts/login.html',
                             form=login_form,
                             current_year=datetime.now().year)
    return redirect(url_for('authentication_blueprint.route_default'))


@blueprint.route('/register', methods=['GET', 'POST'])
@Log.add_log("إضافة مستخدم")
def register():
    """
    A route function that handles the user registration process. It creates an account form and checks if the username and email provided already exist in the database. If the username or email already exist, it renders the registration page with an error message. If the username and email are unique, it creates a new user, adds it to the database, and renders the registration success page.
    """
    create_account_form = CreateAccountForm(request.form)
    if 'register' in request.form:

        username = request.form['username']
        email = request.form['email']

        # Check usename exists
        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='إسم المستخدم موجود بالفعل',
                                   success=False,
                                   form=create_account_form)

        # Check email exists
        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='البريد الإلكتروني موجود بالفعل',
                                   success=False,
                                   form=create_account_form)

        # Create new Agency for the user
        from apps.saas.models import Agency, Subscription, Plan
        agency_name = f"وكالة {username}"
        new_agency = Agency(name=agency_name)
        db.session.add(new_agency)
        db.session.flush() # To get new_agency.id

        # Assign Free plan to the new agency
        free_plan = Plan.query.filter_by(name="Free").first()
        if free_plan:
            new_sub = Subscription(
                agency_id=new_agency.id,
                plan_id=free_plan.id,
                status='active',
                current_period_end=datetime.utcnow() + timedelta(days=365)
            )
            db.session.add(new_sub)

        # Create the user and link to agency
        user = Users(
            username=request.form.get('username'),
            email=request.form.get('email'),
            password=request.form.get('password'),
            agency_id=new_agency.id,
            role='client'
        )
        db.session.add(user)
        db.session.commit()
        
        flash('تم إنشاء الحساب بنجاح، يرجى تسجيل الدخول', 'success')
        return redirect(url_for('authentication_blueprint.login'))

    else:
        return render_template('accounts/register.html', form=create_account_form)

@blueprint.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Mock forgot password endpoint.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        user = Users.query.filter_by(email=email).first()
        if user:
            flash('تم إرسال رابط إعادة تعيين كلمة المرور إلى بريدك الإلكتروني (تجريبي).', 'success')
        else:
            flash('البريد الإلكتروني غير موجود.', 'danger')
        return redirect(url_for('authentication_blueprint.login'))
    return render_template('accounts/forgot_password.html')


@blueprint.route('/logout')
@Log.add_log_early("تسجيل خروج")
def logout():
    """
    Logs out the current user and redirects them to the login page.

    This function is a route handler for the '/logout' endpoint. It is responsible for logging out the current user and redirecting them to the login page.

    Returns:
        flask.Response: A redirect response to the login page.
    """
    logout_user()
    return redirect(url_for('authentication_blueprint.login'))


@blueprint.route('/users', methods=['GET'])
@Log.add_log("عرض جميع المستخدمين")
@login_required
@permission_required('user_management', 'read')
def users():
    return redirect(url_for('authentication_blueprint.admin_system'))


@blueprint.route('/users/create', methods=['GET', 'POST'])
@Log.add_log("إضافة مستخدم جديد")
@login_required
@permission_required('user_management', 'write')
def user_create():
    import json
    roles = Role.query.all()
    roles_data = {role.id: role.permissions for role in roles}
    
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        role_id_str = (request.form.get('role_id') or '').strip()
        password = (request.form.get('password') or '').strip()
        
        if not username or not email or not password or not role_id_str:
            flash('اسم الموظف والبريد الإلكتروني وكلمة المرور والدور الوظيفي مطلوبة ولا يمكن تركها فارغة.', 'danger')
            return render_template('accounts/create_employee.html', roles=roles, roles_data=json.dumps(roles_data))
        
        # Check if username exists
        if Users.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود بالفعل', 'danger')
            return render_template('accounts/create_employee.html', roles=roles, roles_data=json.dumps(roles_data))

        # Check if email exists
        if Users.query.filter_by(email=email).first():
            flash('البريد الإلكتروني موجود بالفعل', 'danger')
            return render_template('accounts/create_employee.html', roles=roles, roles_data=json.dumps(roles_data))
            
        role_id = None
        role_val = 'employee'
        default_permissions = {}
        
        if role_id_str == 'admin':
            role_val = 'admin'
        elif role_id_str == 'custom':
            role_val = 'custom'
        elif role_id_str and role_id_str.isdigit():
            role_id = int(role_id_str)
            role_val = 'employee'
            # Fetch default permissions for comparison
            selected_role = Role.query.get(role_id)
            if selected_role:
                default_permissions = selected_role.permissions or {}
            
        # Parse submitted permissions matrix
        submitted_permissions = {}
        for key in request.form:
            if key.startswith('permissions['):
                # format: permissions[users][read]
                parts = key.replace(']', '').split('[')
                if len(parts) == 3:
                    module = parts[1]
                    perm = parts[2]
                    if module not in submitted_permissions:
                        submitted_permissions[module] = {}
                    submitted_permissions[module][perm] = request.form.get(key)
        
        # Compare submitted matrix to default matrix
        custom_permissions = None
        if submitted_permissions != default_permissions:
            custom_permissions = submitted_permissions
            
        from apps.authentication.util import hash_pass
        user = Users(
            username=username,
            email=email,
            phone=phone,
            password=password, # hash_pass is handled in Users.__init__
            role=role_val,
            role_id=role_id,
            custom_permissions=custom_permissions,
            agency_id=current_user.agency_id
        )
        db.session.add(user)
        db.session.commit()
        flash('تم إضافة الموظف بنجاح', 'success')
        return redirect(url_for('authentication_blueprint.users'))
        
    return render_template('accounts/create_employee.html', roles=roles, roles_data=json.dumps(roles_data))

@blueprint.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@Log.add_log("تعديل بيانات المستخدم")
@login_required
@permission_required('user_management', 'write')
def user_edit(user_id):
    user = Users.query.get_or_404(user_id)
    roles = Role.query.all()
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        
        # Check if username exists for OTHER users
        if Users.query.filter(Users.username == new_username, Users.id != user_id).first():
            flash('اسم المستخدم موجود بالفعل', 'danger')
            return redirect(url_for('authentication_blueprint.user_edit', user_id=user_id))
            
        # Check if email exists for OTHER users
        if Users.query.filter(Users.email == new_email, Users.id != user_id).first():
            flash('البريد الإلكتروني موجود بالفعل', 'danger')
            return redirect(url_for('authentication_blueprint.user_edit', user_id=user_id))
            
        default_permissions = {}
        user.username = new_username
        user.email = new_email
        user.phone = request.form.get('phone')
        role_id_str = request.form.get('role_id')
        password = request.form.get('password')
        
        if role_id_str == 'admin':
            user.role = 'admin'
            user.role_id = None
        elif role_id_str == 'custom':
            user.role = 'custom'
            user.role_id = None
        elif role_id_str and role_id_str.isdigit():
            user.role = 'employee'
            user.role_id = int(role_id_str)
            selected_role = Role.query.get(user.role_id)
            if selected_role:
                default_permissions = selected_role.permissions or {}
        else:
            user.role = 'employee'
            user.role_id = None
            
        # Parse submitted permissions matrix
        submitted_permissions = {}
        for key in request.form:
            if key.startswith('permissions['):
                parts = key.replace(']', '').split('[')
                if len(parts) == 3:
                    module = parts[1]
                    perm = parts[2]
                    if module not in submitted_permissions:
                        submitted_permissions[module] = {}
                    submitted_permissions[module][perm] = request.form.get(key)
        
        # Compare submitted matrix to default matrix
        custom_permissions = None
        if submitted_permissions != default_permissions:
            custom_permissions = submitted_permissions
            
        user.custom_permissions = custom_permissions
            
        if password:
            from apps.authentication.util import hash_pass
            user.password = hash_pass(password)
            
        db.session.commit()
        flash('تم تعديل بيانات الموظف بنجاح', 'success')
        return redirect(url_for('authentication_blueprint.users'))
        
    import json
    roles_data = {role.id: role.permissions for role in roles}
    return render_template('accounts/user_edit.html', edit_mode=True, user=user, roles=roles, roles_data=json.dumps(roles_data))

@blueprint.route('/roles', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('user_management', 'read')
def roles():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        is_active = request.form.get('status') == 'on'
        
        if not name or not description:
            flash('اسم الدور والوصف مطلوبان ولا يمكن تركهما فارغين.', 'danger')
            roles = Role.query.all()
            return render_template('accounts/roles.html', roles=roles)
        
        # Parse matrix
        permissions = {}
        for key in request.form:
            if key.startswith('permissions['):
                # format: permissions[users][read]
                parts = key.replace(']', '').split('[')
                if len(parts) == 3:
                    module = parts[1]
                    perm = parts[2]
                    if module not in permissions:
                        permissions[module] = {}
                    permissions[module][perm] = request.form.get(key)
        
        role = Role(name=name, description=description, is_active=is_active, permissions=permissions)
        db.session.add(role)
        db.session.commit()
        flash('تم حفظ الدور بنجاح', 'success')
        return redirect(url_for('authentication_blueprint.roles'))
        
    roles = Role.query.all()
    return render_template('accounts/roles.html', roles=roles)

@blueprint.route('/roles/edit/<int:role_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('user_management', 'write')
def role_edit(role_id):
    role = Role.query.get_or_404(role_id)
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        role.is_active = request.form.get('status') == 'on'
        
        # Parse matrix
        permissions = {}
        for key in request.form:
            if key.startswith('permissions['):
                parts = key.replace(']', '').split('[')
                if len(parts) == 3:
                    module = parts[1]
                    perm = parts[2]
                    if module not in permissions:
                        permissions[module] = {}
                    permissions[module][perm] = request.form.get(key)
        
        role.permissions = permissions
        db.session.commit()
        flash('تم تعديل الدور بنجاح', 'success')
        return redirect(url_for('authentication_blueprint.roles'))
        
    return render_template('accounts/role_edit.html', role=role)

@blueprint.route('/roles/delete/<int:role_id>', methods=['POST'])
@login_required
@admin_required
@permission_required('user_management', 'delete')
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    
    # Find all users with this role and strip their permissions
    users_with_role = Users.query.filter_by(role_id=role.id).all()
    for user in users_with_role:
        user.role_id = None
        user.custom_permissions = None
        user.role = 'client'
        
    db.session.delete(role)
    db.session.commit()
    flash('تم حذف الدور بنجاح', 'success')
    return redirect(url_for('authentication_blueprint.roles'))

@blueprint.route('/delete_user/<int:user_id>', methods=['POST'])
@Log.add_log("حذف المستخدم")
@login_required
@permission_required('user_management', 'delete')
def delete_user(user_id):
    user = Users.query.get(user_id)
    if not user:
        flash('المستخدم غير موجود', 'danger')
        return redirect(url_for("authentication_blueprint.users"))
    db.session.delete(user)
    db.session.commit()
    flash('تم حذف المستخدم', 'success')
    return redirect(url_for("authentication_blueprint.users"))


@blueprint.route('/admin/add_by_email', methods=['POST'])
@login_required
@admin_required
def add_admin_by_email():
    import secrets
    email = request.form.get('email')
    
    if not email:
        flash('البريد الإلكتروني مطلوب', 'danger')
        return redirect(url_for("authentication_blueprint.users"))
        
    user = Users.query.filter_by(email=email).first()
    
    if user:
        if user.role == 'admin':
            flash('هذا الحساب مدير بالفعل', 'info')
        else:
            user.role = 'admin'
            db.session.commit()
            flash(f'تم تحديث صلاحيات الحساب {email} ليصبح مديراً بنجاح', 'success')
    else:
        # Create a new admin user
        username = email.split('@')[0]
        # Ensure username uniqueness
        base_username = username
        counter = 1
        while Users.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1
            
        password = secrets.token_urlsafe(12)
        new_admin = Users(username=username, email=email, password=password, role='admin')
        db.session.add(new_admin)
        db.session.commit()
        
        flash(f'تم إنشاء حساب المدير الجديد بنجاح. كلمة المرور المؤقتة هي: {password}', 'success')
        
    return redirect(url_for("authentication_blueprint.users"))


@blueprint.route('/admin', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_dashboard():
    global scan_running, scan_progress
    from flask import request
    
    time_range = request.args.get('range', 'today')
    kpis = get_home_kpis(time_range)
    
    return render_template(
        'admin/home.html',
        scan_running=scan_running,
        scan_progress=scan_progress,
        hide_header=True,
        current_range=time_range,
        **kpis
    )


@blueprint.route('/admin/clients', methods=['GET'])
@login_required
@admin_required
def admin_clients():
    from flask import request
    
    time_range = request.args.get('range', 'today')
    kpis = get_clients_kpis(time_range)
    
    return render_template(
        'admin/clients.html',
        hide_header=True,
        current_range=time_range,
        **kpis
    )

@blueprint.route('/admin/influencers/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_influencer(id):
    from apps.profiles.models import Influencer
    from apps import db
    influencer = Influencer.query.get_or_404(id)
    try:
        db.session.delete(influencer)
        db.session.commit()
        flash(f'تم حذف المؤثر {influencer.full_name} بنجاح.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء الحذف: {str(e)}', 'danger')
    return redirect(url_for('authentication_blueprint.admin_influencers'))


@blueprint.route('/admin/influencers', methods=['GET'])
@login_required
@admin_required
@permission_required('influencers', 'read')
def admin_influencers():
    from flask import request
    from apps.home.forms import SearchForm
    from apps.social.models import Platform
    
    time_range = request.args.get('range', 'today')
    kpis = get_influencers_kpis(time_range)
    
    form = SearchForm()
    form.platform.choices = [(str(p.id), p.name) for p in Platform.query.all()]
    
    return render_template(
        'admin/influencers.html',
        hide_header=True,
        current_range=time_range,
        form=form,
        **kpis
    )


@blueprint.route('/admin/influencer/<int:id>', methods=['GET'])
@login_required
@admin_required
def admin_influencer_detail(id):
    from apps.profiles.models import Influencer
    from apps.social.models import SocialAccount
    
    influencer = Influencer.query.get_or_404(id)
    accounts = SocialAccount.query.filter_by(influencer_id=id).all()
    
    return render_template(
        'admin/influencer_detail.html',
        hide_header=True,
        influencer=influencer,
        accounts=accounts
    )


@blueprint.route('/admin/system', methods=['GET'])
@login_required
@admin_required
@permission_required('system_settings', 'read')
def admin_system():
    from flask import request
    
    time_range = request.args.get('range', 'today')
    kpis = get_system_kpis(time_range)
    from apps.authentication.models import Role
    roles = Role.query.all()
    
    return render_template(
        'admin/system.html',
        hide_header=True,
        current_range=time_range,
        roles=roles,
        **kpis
    )


@blueprint.route('/admin/generate-cert', methods=['POST'])
@login_required
@admin_required
@Log.add_log("إنشاء شهادة")
def admin_generate_cert():
    try:
        ic("Generating certificate")
        # Call your certificate generation function
        cert_path = generate_certificate()
        # ic(cert_path)

        # Send the file for download
        return send_file(
            cert_path,
            as_attachment=True,
            download_name='database_certificate.crt',
            mimetype='application/x-x509-ca-cert'
        )
    except Exception as e:
        flash(f'Error generating certificate: {str(e)}', 'danger')
        return redirect(url_for('authentication_blueprint.admin_dashboard'))


@blueprint.route('/admin/backup-database', methods=['POST'])
@login_required
@admin_required
@Log.add_log("نسخ قاعدة البيانات")
def backup_database():
    """
    Create a backup of the database and send it as a downloadable file.
    """
    try:
        # Log the start of the backup process
        ic("Starting database backup process")

        # Create the database backup
        success, result = create_db_backup()

        if success:
            # If successful, result is the file path
            backup_path = result
            filename = os.path.basename(backup_path)

            # Check which method was used
            method_file = f"{backup_path}.method"
            backup_method = "unknown"
            if os.path.exists(method_file):
                try:
                    with open(method_file, 'r', encoding='utf-8') as f:
                        backup_method = f.read().strip()
                except Exception as e:
                    ic(f"Error reading method file: {str(e)}")
                    backup_method = "unknown"

            # Translate method name to Arabic
            method_ar_dict = {
                'pg_dump': 'PostgreSQL pg_dump (أسرع)',
                'sqlalchemy': 'SQLAlchemy (أبطأ ولكن أكثر توافقًا)',
                'unknown': 'غير معروف'
            }
            method_ar = method_ar_dict.get(backup_method, backup_method)

            ic(f"Backup successful using {backup_method} method, file saved at: {backup_path}")

            # Keep the original backup metadata for status endpoints and diagnostics.
            session['last_backup_method'] = backup_method
            session['last_backup_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session['last_backup_size'] = os.path.getsize(backup_path)
            session['last_backup_filename'] = filename

            ic(f"Backup successful, file saved at: {backup_path}")

            # Send the generated backup directly to the browser as a local download.
            return send_file(
                backup_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/octet-stream'
            )
        else:
            # If failed, result is the error message
            error_msg = f'Error creating database backup: {result}'
            ic(error_msg)
            flash(error_msg, 'danger')
            return redirect(url_for('authentication_blueprint.admin_dashboard'))
    except Exception as e:
        error_msg = f'Exception in backup_database: {str(e)}'
        ic(error_msg)
        import traceback
        ic(traceback.format_exc())
        flash(error_msg, 'danger')
        return redirect(url_for('authentication_blueprint.admin_dashboard'))


@blueprint.route('/admin/backup-method')
@login_required
@admin_required
def get_backup_method():
    """
    Return information about the last backup method used.
    """
    method = session.get('last_backup_method', 'unknown')
    time = session.get('last_backup_time', 'N/A')
    size = session.get('last_backup_size', 0)

    # Format size in human-readable format
    if size > 1024 * 1024:
        size_str = f"{size / (1024 * 1024):.2f} MB"
    elif size > 1024:
        size_str = f"{size / 1024:.2f} KB"
    else:
        size_str = f"{size} bytes"

    # Translate method name to Arabic
    method_ar = {
        'pg_dump': 'PostgreSQL pg_dump (أسرع)',
        'sqlalchemy': 'SQLAlchemy (أبطأ ولكن أكثر توافقًا)',
        'unknown': 'غير معروف'
    }.get(method, method)

    return jsonify({
        'method': method,
        'method_ar': method_ar,
        'time': time,
        'size': size_str
    })


@blueprint.route('/admin/check-file-status')
@login_required
@admin_required
def check_file_status():
    """
    Check if a backup or export file is ready for download.
    Returns status information about the last backup or export operation.
    """
    file_type = request.args.get('type', 'backup')  # 'backup' or 'export'

    if file_type == 'backup':
        filename = session.get('last_backup_filename')
        time = session.get('last_backup_time', 'N/A')
        size = session.get('last_backup_size', 0)
        method = session.get('last_backup_method', 'unknown')

        # Translate method name to Arabic
        method_ar = {
            'pg_dump': 'PostgreSQL pg_dump (أسرع)',
            'sqlalchemy': 'SQLAlchemy (أبطأ ولكن أكثر توافقًا)',
            'unknown': 'غير معروف'
        }.get(method, method)

        details = f"تم استخدام: {method_ar}"
    else:  # export
        filename = session.get('last_export_filename')
        time = session.get('last_export_time', 'N/A')
        size = session.get('last_export_size', 0)
        details = "تصدير قاعدة البيانات إلى ملفات CSV مضغوطة"

    # Check if file exists
    if not filename:
        return jsonify({
            'ready': False,
            'message': 'لم يتم إنشاء الملف بعد',
            'details': '',
            'download_url': '',
            'time': '',
            'size': ''
        })

    # Format size in human-readable format
    if size > 1024 * 1024:
        size_str = f"{size / (1024 * 1024):.2f} MB"
    elif size > 1024:
        size_str = f"{size / 1024:.2f} KB"
    else:
        size_str = f"{size} bytes"

    # Check if file exists on disk
    if file_type == 'backup':
        file_dir = os.path.join(current_app.root_path, 'static', 'backups')
        download_url = url_for('authentication_blueprint.download_backup', filename=filename)
    else:
        file_dir = os.path.join(current_app.root_path, 'static', 'exports')
        download_url = url_for('authentication_blueprint.download_export', filename=filename)

    file_path = os.path.join(file_dir, filename)
    file_exists = os.path.exists(file_path)

    # Get detailed information about the file
    if file_exists:
        # Get file creation time
        file_ctime = datetime.fromtimestamp(os.path.getctime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
        # Get file size
        file_size = os.path.getsize(file_path)
        if file_size > 1024 * 1024:
            file_size_str = f"{file_size / (1024 * 1024):.2f} MB"
        elif file_size > 1024:
            file_size_str = f"{file_size / 1024:.2f} KB"
        else:
            file_size_str = f"{file_size} bytes"

        details += f" - الحجم: {file_size_str} - الوقت: {file_ctime}"

    return jsonify({
        'ready': file_exists,
        'message': 'الملف جاهز للتنزيل' if file_exists else 'جاري إنشاء الملف...',
        'details': details,
        'download_url': download_url if file_exists else '',
        'time': time,
        'size': size_str
    })


@blueprint.route('/admin/download-backup/<path:filename>')
@login_required
@admin_required
def download_backup(filename):
    """
    Download a backup file directly from the static folder.
    """
    try:
        ic(f"Attempting to download backup file: {filename}")
        backup_dir = os.path.join(current_app.root_path, 'static', 'backups')
        return send_from_directory(directory=backup_dir, path=filename, as_attachment=True)
    except Exception as e:
        ic(f"Error downloading backup: {str(e)}")
        flash(f'Error downloading backup: {str(e)}', 'danger')
        return redirect(url_for('authentication_blueprint.admin_dashboard'))


@blueprint.route('/admin/download-export/<path:filename>')
@login_required
@admin_required
def download_export(filename):
    """
    Download an export file directly from the static folder.
    """
    try:
        ic(f"Attempting to download export file: {filename}")
        export_dir = os.path.join(current_app.root_path, 'static', 'exports')
        return send_from_directory(directory=export_dir, path=filename, as_attachment=True)
    except Exception as e:
        ic(f"Error downloading export: {str(e)}")
        flash(f'Error downloading export: {str(e)}', 'danger')
        return redirect(url_for('authentication_blueprint.admin_dashboard'))


@blueprint.route('/admin/export-excel', methods=['POST'])
@login_required
@admin_required
@Log.add_log("تصدير قاعدة البيانات إلى إكسل")
def export_database_excel():
    """
    Export the database to an Excel workbook with each table as a separate sheet.
    """
    try:
        # Log the start of the export process
        ic("Starting database export to Excel")

        # Export the database to Excel
        success, result = export_db_to_excel(db)

        if success:
            # If successful, result is the full file path
            excel_path = result
            filename = os.path.basename(excel_path)

            ic(f"Export successful, file saved at: {excel_path}")

            # Verify the file exists
            if not os.path.exists(excel_path):
                error_msg = f'Export file not found at path: {excel_path}'
                ic(error_msg)
                flash(error_msg, 'danger')
                return redirect(url_for('authentication_blueprint.admin_dashboard'))

            # Preserve export metadata for status endpoints and diagnostics.
            session['last_export_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session['last_export_size'] = os.path.getsize(excel_path)
            session['last_export_filename'] = filename

            ic(f"Export successful, file saved at: {excel_path}")

            # Send the generated Excel file directly to the browser as a local download.
            return send_file(
                excel_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            # If failed, result is the error message
            error_msg = f'Error exporting database to CSV: {result}'
            ic(error_msg)
            flash(error_msg, 'danger')
            return redirect(url_for('authentication_blueprint.admin_dashboard'))
    except Exception as e:
        error_msg = f'Exception in export_database_excel: {str(e)}'
        ic(error_msg)
        import traceback
        ic(traceback.format_exc())
        flash(error_msg, 'danger')
        return redirect(url_for('authentication_blueprint.admin_dashboard'))


# Scan log route merged into admin_dashboard




@blueprint.route('/admin/roles/create', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('user_management', 'write')
@Log.add_log("إنشاء دور جديد")
def create_role():
    if request.method == 'GET':
        roles = Role.query.all()
        return render_template('accounts/create_role.html', segment='roles', roles=roles)
        
    if request.method == 'POST':
        # 1. Extract Role Info
        role_name = request.form.get('role_name')
        role_desc = request.form.get('role_description')
        is_active = request.form.get('is_active') == 'on'
        
        # 2. Build the Permissions Matrix JSON
        permissions = {}
        for key in request.form:
            if key.startswith('permissions['):
                parts = key.replace(']', '').split('[')
                if len(parts) == 3:
                    module = parts[1]
                    perm = parts[2]
                    if module not in permissions:
                        permissions[module] = {}
                    permissions[module][perm] = request.form.get(key)
        
        # 3. Save to Database
        new_role = Role(
            name=role_name,
            description=role_desc,
            is_active=is_active,
            permissions=permissions
        )
        db.session.add(new_role)
        db.session.commit()
        
        flash('تم إنشاء الدور بنجاح', 'success')
        return redirect(url_for('authentication_blueprint.users'))

# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    """
    A route function that handles unauthorized access attempts.

    This function is a route handler for the '/' endpoint. It is responsible for handling unauthorized access attempts by returning a rendered template for the 'home/page-403.html' page and a status code of 403.

    Returns:
        A tuple containing the rendered template and the status code.
    """
    session['original_url'] = request.url
    # return redirect(url_for('authentication_blueprint.login'))
    return render_template("home/page-403.html"), 403


@blueprint.errorhandler(403)
def access_forbidden(error):
    """
    A route function that handles access forbidden errors.

    This function is a route handler for the '/' endpoint. It is responsible for handling access forbidden errors by returning a rendered template for the 'home/page-403.html' page and a status code of 403.

    Parameters:
        error (Exception): The access forbidden error that occurred.

    Returns:
        A tuple containing the rendered template and the status code.
    """
    session['original_url'] = request.url
    # return redirect(url_for("authentication_blueprint.login"))
    return render_template('home/page-403.html'), 403

@blueprint.errorhandler(404)
def not_found_error(error):
    """
    A route function that handles 404 errors.

    This function is a route handler for the '/' endpoint. It is responsible for handling 404 errors by returning a rendered template for the 'home/page-404.html' page and a status code of 404.

    Parameters:
        error (Exception): The 404 error that occurred.

    Returns:
        A tuple containing the rendered template and the status code.
    """
    return render_template('home/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    """
    A route function that handles internal server errors.

    This function is a route handler for the '/' endpoint. It is responsible for handling internal server errors by returning a rendered template for the 'home/page-500.html' page and a status code of 500.

    Parameters:
        error (Exception): The internal server error that occurred.

    Returns:
        A tuple containing the rendered template and the status code.
    """
    return render_template('home/page-500.html'), 500
