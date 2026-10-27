#!/usr/bin/env python
"""
Script to seed default Platforms and a base Subscription Plan.
"""
import os
import sys
from dotenv import load_dotenv

# Configure icecream before importing any modules that use it
from ic_config import configure_icecream
configure_icecream()

from apps.config import config_dict
from apps import create_app, db
from apps.social.models import Platform
from apps.saas.models import Plan

def seed_defaults():
    print("Starting default seeding process...")

    basedir = os.path.dirname(__file__)
    if os.getenv("FLASK_ENV") == "production":
        dotenv_path = os.path.join(basedir, ".env.prod")
    else:
        dotenv_path = os.path.join(basedir, ".env.dev")
    load_dotenv(dotenv_path)

    DEBUG = os.getenv("DEBUG_MODE", "False") == "True"
    get_config_mode = 'Debug' if DEBUG else 'Production'

    try:
        app_config = config_dict[get_config_mode.capitalize()]
    except KeyError:
        error_msg = 'Error: Invalid <config_mode>. Expected values [Debug, Production]'
        print(error_msg)
        sys.exit(error_msg)

    app = create_app(app_config)

    with app.app_context():
        # Seed Platforms
        platforms = [
            {"name": "انستقرام", "name_english": "Instagram"},
            {"name": "تيك توك", "name_english": "TikTok"},
            {"name": "سناب شات", "name_english": "Snapchat"},
            {"name": "يوتيوب", "name_english": "YouTube"},
            {"name": "اكس (تويتر)", "name_english": "X (Twitter)"},
            {"name": "فيسبوك", "name_english": "Facebook"}
        ]

        for p_data in platforms:
            existing = Platform.query.filter_by(name_english=p_data["name_english"]).first()
            if not existing:
                new_platform = Platform(name=p_data["name"], name_english=p_data["name_english"])
                db.session.add(new_platform)
                print(f"Added platform: {p_data['name_english']}")
            else:
                print(f"Platform already exists: {p_data['name_english']}")

        # Seed Base Plan
        free_plan = Plan.query.filter_by(name="Free").first()
        if not free_plan:
            free_plan = Plan(name="Free", tracking_limit=5, price=0.0, is_active=True)
            db.session.add(free_plan)
            print("Added default 'Free' plan.")
        else:
            print("'Free' plan already exists.")

        db.session.commit()
        print("Database seeding completed.")

if __name__ == "__main__":
    seed_defaults()
