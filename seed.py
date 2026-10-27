import os
from dotenv import load_dotenv
from apps import create_app, db
from apps.social.models import Platform
from apps.config import config_dict

# Load correct environment variables
env_file = ".env.prod" if os.getenv("FLASK_ENV") == "production" else ".env.dev"
load_dotenv(env_file)

# Select the correct configuration
config_mode = "Production" if os.getenv("FLASK_ENV") == "production" else "Debug"
app = create_app(config_dict[config_mode])

def seed_platforms():
    with app.app_context():
        # Hardcoded IDs to perfectly match the Excel legacy data expectations
        platforms = [
            Platform(id=1, name='Youtube', name_english='youtube'),
            Platform(id=2, name='Tiktok', name_english='tiktok'),
            Platform(id=3, name='Instagram', name_english='instagram'),
            Platform(id=4, name='Snapchat', name_english='snapchat')
        ]
        
        # Idempotent insertion: only add if the ID doesn't already exist
        for p in platforms:
            if not Platform.query.get(p.id):
                db.session.add(p)
                print(f"Added platform: {p.name} (ID: {p.id})")
        
        db.session.commit()
        print("Final Platform List:", [f"{p.id}={p.name}" for p in Platform.query.all()])

if __name__ == "__main__":
    seed_platforms()
