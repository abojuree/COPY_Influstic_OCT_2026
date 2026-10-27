#!/usr/bin/env python
"""
Script to reset the admin user password in the database.
This will update the existing admin user's password to a newly generated strong random password.
"""
import os
import sys
import secrets
from dotenv import load_dotenv

# Configure icecream before importing any modules that use it
from ic_config import configure_icecream
configure_icecream()

from apps.config import config_dict
from apps import create_app, db
from apps.authentication.models import Users
from apps.authentication.util import hash_pass

def reset_admin():
    """
    Reset the admin user's password to the default.
    """
    print("Starting admin user password reset process...")

    # Determine the environment and load the appropriate .env file
    basedir = os.path.dirname(__file__)
    if os.getenv("FLASK_ENV") == "production":
        dotenv_path = os.path.join(basedir, ".env.prod")
    else:
        dotenv_path = os.path.join(basedir, ".env.dev")
    load_dotenv(dotenv_path)

    # Determine the environment
    DEBUG = os.getenv("DEBUG_MODE", "False") == "True"
    get_config_mode = 'Debug' if DEBUG else 'Production'
    print(f"Environment: {get_config_mode}")

    try:
        # Load the configuration using the default values
        app_config = config_dict[get_config_mode.capitalize()]
    except KeyError:
        error_msg = 'Error: Invalid <config_mode>. Expected values [Debug, Production]'
        print(error_msg)
        sys.exit(error_msg)

    # Create the Flask application
    app = create_app(app_config)

    # Run the reset within the application context
    with app.app_context():
        try:
            # Find the admin user
            admin_user = Users.query.filter_by(username="admin").first()

            if admin_user:
                print(f"Found admin user with ID: {admin_user.id}")
                default_password = "12345678"
                print(f"Generated admin password for runtime: {default_password}")
                admin_user.password = hash_pass(default_password)
                db.session.commit()
                print(f"Admin user password reset successfully.")
                print(f"You can now log in with username: admin, password: {default_password}")
            else:
                print("Admin user not found. Creating default admin user...")
                # Create the default admin user
                username = "admin"
                password = "12345678"
                email = "admin@email.com"
                print(f"Generated default admin password for runtime: {password}")
                admin_user = Users(username=username, password=password, email=email, role='admin')
                db.session.add(admin_user)
                db.session.commit()
                print(f"Default admin user created with username: {username}, password: {password}")

        except Exception as e:
            print(f"Error resetting admin user: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    reset_admin()
