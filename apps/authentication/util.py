import os
import hashlib
import binascii
import secrets
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from flask import abort

# Master Permission Matrix Constants
PERMISSION_MODULES = [
    'user_management',
    'system_settings',
    'financials',
    'campaigns',
    'influencers',
    'reports'
]

PERMISSION_ACTIONS = ['read', 'write', 'delete', 'execute']

def permission_required(module, action='read'):
    """
    Decorator that strictly enforces route-level access control based on the master permission matrix.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('authentication_blueprint.login'))
                
            # Master admin & Agency Owner bypass
            if current_user.role in ['admin', 'client']:
                return func(*args, **kwargs)
            
            # Check individual custom permission overrides first
            perms = current_user.custom_permissions or {}
            
            # If no custom overrides, fallback to their assigned role
            if not perms and current_user.role_id:
                perms = current_user.role_model.permissions if current_user.role_model else {}
            
            # Extract truthy value for the requested module/action
            module_perms = perms.get(module, {})
            has_permission = module_perms.get(action) in [True, 'True', '1', 'on']
            
            if not has_permission:
                flash(f"غير مصرح لك بالوصول: مطلوب إذن '{action}' في وحدة '{module}'", "danger")
                abort(403) # Forbidden
                
            return func(*args, **kwargs)
        return wrapper
    return decorator
def hash_pass(password):
    """Hash a password for storing."""

    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'),
                                  salt, 100000)
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash)  # return bytes


def verify_pass(provided_password, stored_password):
    """Verify a stored password against one provided by user"""

    # Check if stored_password is None
    if stored_password is None:
        return False

    stored_password = stored_password.decode('ascii')
    salt = stored_password[:64]
    stored_password = stored_password[64:]
    pwdhash = hashlib.pbkdf2_hmac('sha512',
                                  provided_password.encode('utf-8'),
                                  salt.encode('ascii'),
                                  100000)
    pwdhash = binascii.hexlify(pwdhash).decode('ascii')
    return pwdhash == stored_password


# Admin-only decorator
def admin_required(f):
    """
    Decorator that restricts access to the system admin portal.
    Enforces that the user belongs to the master admin's agency (they are a System Employee).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('authentication_blueprint.login'))
            
        # Strict Agency Check for System Employees
        from apps.authentication.models import Users
        master_admin = Users.query.filter_by(username='admin').first()
        
        # If master_admin exists and the current user does not belong to the same agency, block them.
        if master_admin and current_user.agency_id != master_admin.agency_id:
            from flask import abort
            abort(403)
            
        return f(*args, **kwargs)
    return decorated_function


def roles_required(module_name, required_permission='read'):
    """
    Decorator that restricts access based on dynamic role permissions and custom overrides.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('authentication_blueprint.login'))
            
            # Admin and Agency Owner always have full access
            if current_user.role in ['admin', 'client']:
                return f(*args, **kwargs)
                
            # 1. Check Custom Permissions Overrides First
            if current_user.custom_permissions and module_name in current_user.custom_permissions:
                if current_user.custom_permissions[module_name].get(required_permission) in ['1', 'on', True]:
                    return f(*args, **kwargs)
                else:
                    from flask import abort
                    abort(403)
                    
            # 2. Check dynamic role permissions
            if current_user.role_model and current_user.role_model.is_active:
                perms = current_user.role_model.permissions
                if perms and module_name in perms:
                    if perms[module_name].get(required_permission) in ['1', 'on', True]:
                        return f(*args, **kwargs)
            
            from flask import abort
            abort(403)
        return decorated_function
    return decorator


# Create the default admin user (you can modify this data as needed)
def create_default_admin(Users,db):
    """
    Creates a default admin user if one does not already exist in the database.

    Args:
        Users (class): The Users model class representing the user table in the database.
        db (SQLAlchemy): The SQLAlchemy database object.

    Returns:
        None
    """
    username = "admin"
    password = "12345678"
    email = "admin@email.com"
    admin_user = Users.query.filter_by(username=username).first()
    if admin_user is None:
        try:
            print(f"Generated default admin password for runtime: {password}")
            # If the admin user doesn't exist, create it
            admin_user = Users(username=username, password=password, email=email, role='admin')
            db.session.add(admin_user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # If there was an error, try to fix the sequence and try again
            try:
                # Execute raw SQL to fix the sequence
                db.session.execute("CREATE SEQUENCE IF NOT EXISTS users_id_seq")
                db.session.execute("SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM \"Users\"), 1))")
                db.session.execute("ALTER TABLE \"Users\" ALTER COLUMN id SET DEFAULT nextval('users_id_seq')")
                db.session.commit()

                # Try creating the admin user again
                admin_user = Users(username=username, password=password, email=email, role='admin')
                db.session.add(admin_user)
                db.session.commit()
            except Exception as e2:
                db.session.rollback()
                print(f"Error creating admin user: {str(e2)}")