#!/usr/bin/env python
"""
Cron job script for scanning social profiles.
Executed by the system crontab (see deploy/crontab).
"""
import os
import sys
import datetime
import traceback

# Configure icecream before importing any modules that use it
from ic_config import configure_icecream
configure_icecream()

from dotenv import load_dotenv
from apps.config import config_dict
from apps import create_app, db
from tasks import scan_database, cleanup_old_scanlogs
from email_utils import send_cron_job_failure_notification, send_high_failure_rate_notification

def main():
    """
    Main function to run the social profile scan.
    """
    start_time = datetime.datetime.now()
    print(f"[{start_time}] Starting social profile scan cron job")

    try:
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
        print(f"[{datetime.datetime.now()}] Environment: {get_config_mode}")

        try:
            # Load the configuration using the default values
            app_config = config_dict[get_config_mode.capitalize()]
        except KeyError:
            error_msg = 'Error: Invalid <config_mode>. Expected values [Debug, Production]'
            print(f"[{datetime.datetime.now()}] {error_msg}")
            sys.exit(error_msg)

        # Create the Flask application
        app = create_app(app_config)

        # Run the scan_database function within the application context
        with app.app_context():
            try:
                # Initialize the database if needed
                db.create_all()

                # Run the scan
                print(f"[{datetime.datetime.now()}] Starting database scan")
                scan_database(app, db.session)
                print(f"[{datetime.datetime.now()}] Database scan completed successfully")

                # Check for high failure rates in platforms
                from tasks import scan_log

                # Process platform statistics and check failure rates
                for platform, failure_count in scan_log.get("failure_count", {}).items():
                    success_count = scan_log.get("success_count", {}).get(platform, 0)
                    total = failure_count + success_count

                    if total > 0:
                        failure_rate = (failure_count / total) * 100
                        print(f"[{datetime.datetime.now()}] Platform {platform}: Success={success_count}, Failure={failure_count}, Rate={failure_rate:.2f}%")

                        # If failure rate exceeds 50%, send notification
                        if failure_rate > 50:
                            print(f"[{datetime.datetime.now()}] High failure rate detected for {platform}: {failure_rate:.2f}%")

                            # Prepare details for the notification
                            details = {
                                "total": total,
                                "failed": failure_count,
                                "succeeded": success_count,
                                "failures": scan_log.get("failures", {}).get(platform, {})
                            }

                            # Send notification
                            send_high_failure_rate_notification(platform, failure_rate, details)

                # Clean up old scan logs, keeping only the last 3
                print(f"[{datetime.datetime.now()}] Cleaning up old scan logs")
                cleanup_old_scanlogs(db.session, keep_count=3)
                print(f"[{datetime.datetime.now()}] Cleanup completed")
            except Exception as e:
                error_message = f"ERROR in database scan: {str(e)}"
                print(f"[{datetime.datetime.now()}] {error_message}")
                error_traceback = traceback.format_exc()
                print(error_traceback)

                # Send email notification about the failure
                send_cron_job_failure_notification(f"{error_message}\n\n{error_traceback}")

                sys.exit(1)

    except Exception as e:
        error_message = f"ERROR in cron job: {str(e)}"
        print(f"[{datetime.datetime.now()}] {error_message}")
        error_traceback = traceback.format_exc()
        print(error_traceback)

        # Send email notification about the failure
        send_cron_job_failure_notification(f"{error_message}\n\n{error_traceback}")

        sys.exit(1)

    end_time = datetime.datetime.now()
    duration = end_time - start_time
    print(f"[{end_time}] Cron job completed in {duration}")

if __name__ == "__main__":
    main()
