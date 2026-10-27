#!/usr/bin/env python
"""
Script to count the number of social accounts in the database.
"""
import os
from dotenv import load_dotenv

# Configure icecream before importing any modules that use it
from ic_config import configure_icecream
configure_icecream()

from apps.config import config_dict
from apps import create_app, db
from apps.social.models import SocialAccount, Platform

def count_accounts():
    """
    Count the number of social accounts in the database.
    """
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
    
    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]
    
    # Create the Flask application
    app = create_app(app_config)
    
    # Count accounts within the application context
    with app.app_context():
        total_accounts = SocialAccount.query.count()
        print(f"Total social accounts: {total_accounts}")
        
        # Count by platform
        platforms = Platform.query.all()
        for platform in platforms:
            count = SocialAccount.query.filter_by(platform_id=platform.id).count()
            print(f"  - {platform.name}: {count} accounts")

if __name__ == "__main__":
    count_accounts()
