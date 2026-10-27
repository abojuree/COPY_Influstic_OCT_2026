import sys
import os

# Append the current directory to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from run import app
from apps import db
from apps.saas.models import Plan

def seed_plans():
    with app.app_context():
        plans_data = [
            {"name": "Free", "tracking_limit": 50, "price": 0.0},
            {"name": "Plus", "tracking_limit": 200, "price": 99.0},
            {"name": "Super", "tracking_limit": 1000, "price": 299.0}
        ]

        for pdata in plans_data:
            plan = Plan.query.filter_by(name=pdata['name']).first()
            if not plan:
                plan = Plan(name=pdata['name'], tracking_limit=pdata['tracking_limit'], price=pdata['price'])
                db.session.add(plan)
            else:
                plan.tracking_limit = pdata['tracking_limit']
                plan.price = pdata['price']
        
        db.session.commit()
        print("Plans seeded successfully!")

if __name__ == "__main__":
    seed_plans()
