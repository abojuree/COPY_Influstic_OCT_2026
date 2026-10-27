#!/usr/bin/env python
"""
Script to fix the sequence for the Users table.
This can be run manually if the migration doesn't work.
"""
import os
from dotenv import load_dotenv
from apps import create_app, db
from apps.config import config_dict

# Load environment variables
load_dotenv()

# Get the configuration
config_mode = os.getenv('FLASK_ENV', 'development')
app_config = config_dict[config_mode.capitalize()]

# Create the app
app = create_app(app_config)

def fix_users_sequence():
    """Fix the sequence for the Users table."""
    with app.app_context():
        try:
            # Create the sequence if it doesn't exist
            db.session.execute("CREATE SEQUENCE IF NOT EXISTS users_id_seq")
            
            # Set the sequence value to the maximum ID in the Users table
            db.session.execute("SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM \"Users\"), 1))")
            
            # Set the default value for the id column to use the sequence
            db.session.execute("ALTER TABLE \"Users\" ALTER COLUMN id SET DEFAULT nextval('users_id_seq')")
            
            # Commit the changes
            db.session.commit()
            
            print("Successfully fixed the sequence for the Users table.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error fixing the sequence: {str(e)}")

if __name__ == "__main__":
    fix_users_sequence()
