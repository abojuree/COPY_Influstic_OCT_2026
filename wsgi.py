"""
WSGI entry point for the application.
This file is used by Render.com to start the application.
"""
import os
import datetime

# Configure icecream before importing any modules that use it
from ic_config import configure_icecream
configure_icecream()

from flask_migrate import Migrate
from apps.config import config_dict
from apps import create_app, db
from flask_apscheduler import APScheduler
from tasks import scan_database, cleanup_old_scanlogs
# Import icecream for logging if needed
try:
    from icecream import ic
except ImportError:
    def ic(*args):
        return args[0] if args else None
from dotenv import load_dotenv

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
ic(f"Environment: {get_config_mode}")

try:
    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]
except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production]')

# Create the Flask application
app = create_app(app_config)
Migrate(app, db)

# Initialize the database if needed
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database initialization error: {str(e)}")

# Initialize scheduler instance
sched = APScheduler()

def scheduled_job():
    """
    This function is called by the scheduler at the configured time.
    It runs the scan_database function within the application context.
    """
    try:
        print(f"[{datetime.datetime.now()}] Starting scheduled job: scan_database")
        with app.app_context():
            scan_database(app, db.session)

            # Clean up old scan logs, keeping only the last 3
            print(f"[{datetime.datetime.now()}] Cleaning up old scan logs")
            cleanup_old_scanlogs(db.session, keep_count=3)
            print(f"[{datetime.datetime.now()}] Cleanup completed")
        print(f"[{datetime.datetime.now()}] Scheduled job completed successfully")
    except Exception as e:
        print(f"[{datetime.datetime.now()}] ERROR in scheduled job: {str(e)}")
        # Log the full traceback for better debugging
        import traceback
        print(traceback.format_exc())

# Configuring the scheduler
SCHEDULER_API_ENABLED = os.getenv("SCHEDULER_API_ENABLED", "True") == "True"
SCHEDULER_TRIGGER_HOUR = int(os.getenv("SCHEDULER_TRIGGER_HOUR", 0))
SCHEDULER_TRIGGER_MINUTE = int(os.getenv("SCHEDULER_TRIGGER_MINUTE", 0))
print(f"[{datetime.datetime.now()}] Scheduler settings: API Enabled={SCHEDULER_API_ENABLED}, Hour={SCHEDULER_TRIGGER_HOUR}, Minute={SCHEDULER_TRIGGER_MINUTE}")

if SCHEDULER_API_ENABLED:
    try:
        # Configure the scheduler
        app.config["SCHEDULER_API_ENABLED"] = SCHEDULER_API_ENABLED
        app.config["JOBS"] = [
            {
                "id": "job1",
                "func": scheduled_job,
                "args": [],
                "trigger": "cron",
                "hour": SCHEDULER_TRIGGER_HOUR,
                "minute": SCHEDULER_TRIGGER_MINUTE,
            }
        ]

        # Initialize and start the scheduler
        sched.init_app(app)
        sched.start()
        print(f"[{datetime.datetime.now()}] Scheduler started successfully with job scheduled at {SCHEDULER_TRIGGER_HOUR}:{SCHEDULER_TRIGGER_MINUTE}")

        # List all jobs for verification
        jobs = sched.get_jobs()
        for job in jobs:
            print(f"[{datetime.datetime.now()}] Registered job: {job.id}, Next run time: {job.next_run_time}")
    except Exception as e:
        print(f"[{datetime.datetime.now()}] ERROR starting scheduler: {str(e)}")
        import traceback
        print(traceback.format_exc())
else:
    print(f"[{datetime.datetime.now()}] Scheduler is disabled based on environment configuration")

if __name__ == "__main__":
    app.run()
