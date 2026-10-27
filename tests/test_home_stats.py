#!/usr/bin/env python
"""
Script to test the home page statistics.
"""
import os
from dotenv import load_dotenv

# Configure icecream before importing any modules that use it
from ic_config import configure_icecream
configure_icecream()

from apps.config import config_dict
from apps import create_app, db
from apps.social.models import SocialAccount, Platform
from apps.home.util import get_summerized_report

def test_home_stats():
    """
    Test the home page statistics.
    """
    # Determine the environment and load the appropriate .env file
    basedir = os.path.dirname(__file__)
    if os.getenv("FLASK_ENV") == "development":
        dotenv_path = os.path.join(basedir, ".env.dev")
    else:
        dotenv_path = os.path.join(basedir, ".env.prod")
    load_dotenv(dotenv_path)
    
    # Determine the environment
    DEBUG = os.getenv("DEBUG_MODE", "False") == "True"
    get_config_mode = 'Debug' if DEBUG else 'Production'
    print(f"Environment: {get_config_mode}")
    
    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]
    
    # Create the Flask application
    app = create_app(app_config)
    
    # Test the home page statistics within the application context
    with app.app_context():
        # Get the total number of accounts directly from the database
        total_accounts = SocialAccount.query.count()
        print(f"Direct database query - Total social accounts: {total_accounts}")
        
        # Count by platform
        platforms = Platform.query.all()
        for platform in platforms:
            count = SocialAccount.query.filter_by(platform_id=platform.id).count()
            print(f"  - {platform.name}: {count} accounts")
        
        # Get the statistics from the get_summerized_report function
        stats = get_summerized_report()
        print(f"\nget_summerized_report() - Total social accounts: {stats['total_accounts']}")
        
        # Check if the counts match
        if total_accounts == stats['total_accounts']:
            print("\nSUCCESS: The counts match!")
        else:
            print(f"\nERROR: The counts do not match! Direct query: {total_accounts}, get_summerized_report(): {stats['total_accounts']}")

if __name__ == "__main__":
    test_home_stats()
