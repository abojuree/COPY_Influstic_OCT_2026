from concurrent.futures import ThreadPoolExecutor
import datetime
from threading import Lock  # <-- Added for global tracking synchronization
from itertools import zip_longest, chain
from sqlalchemy import desc
from icecream import ic

from apps import db  # Ensure this points to your Flask-SQLAlchemy db instance
from apps.reports.models import ScanResults, ScanLog
from apps.home.util import search_user_profile
from apps.social.models import Platform, SocialAccount

# Create a threading lock to protect global dictionaries
state_lock = Lock()

# Global variable to track if scan should be stopped
scan_should_stop = False

# Global variable to track scan progress
scan_progress = {
    "total": 0,
    "processed": 0,
    "success": 0,
    "failure": 0,
    "status": "idle",
    "message": "No scan in progress"
}

scan_log = {
    "success_count": {},
    "failure_count": {},
    "failures": {},
}

def cleanup_old_scanlogs(db_session, keep_count=3):
    """
    Cleanup old scan logs, keeping only the most recent ones.
    """
    try:
        all_logs = db_session.query(ScanLog).order_by(
            desc(ScanLog.creation_date),
            desc(ScanLog.creation_time)
        ).all()

        if len(all_logs) > keep_count:
            logs_to_delete = all_logs[keep_count:]
            delete_ids = [log.id for log in logs_to_delete]

            delete_count = db_session.query(ScanLog).filter(
                ScanLog.id.in_(delete_ids)
            ).delete(synchronize_session=False)

            db_session.commit()
            ic(f"Cleaned up {delete_count} old scan logs, keeping the {keep_count} most recent")
            return delete_count
        else:
            ic(f"No cleanup needed. Only have {len(all_logs)} logs, keeping {keep_count}")
            return 0
    except Exception as e:
        ic(f"Error cleaning up old scan logs: {str(e)}")
        return 0

def process_username(app, platform_id, username, socialaccount_id):
    """
    Thread-isolated worker function. Creates its own DB context and safely mutates global tracking.
    """
    global scan_log

    # Force each worker thread into its own isolated Application Context
    with app.app_context():
        try:
            # Flask-SQLAlchemy's db.session is scoped to the current thread identifier
            platform_name = (
                db.session.query(Platform.name)
                .filter(Platform.id == platform_id)
                .scalar()
            ) or f"Platform_{platform_id}"

            print(f"[SCRAPER LOG] Starting scrape for @{username} on platform {platform_id}...")
            profile_data = search_user_profile(username, str(platform_id), socialaccount_id)

            if profile_data.get("error"):
                raise Exception(profile_data["error"])

            # Use new dict structure
            followers = profile_data.get('followers_count', profile_data.get('followers', 0))
            likes = profile_data.get('likes_count', profile_data.get('total_likes', profile_data.get('likes', 0)))
            posts = profile_data.get('posts_count', profile_data.get('total_posts', profile_data.get('posts', 0)))

            # Check if ScanResults already has a row with identical metrics
            existing_scanresult = (
                db.session.query(ScanResults)
                .filter(ScanResults.socialaccount_id == socialaccount_id)
                .filter(ScanResults.followers == followers)
                .filter(ScanResults.likes == likes)
                .filter(ScanResults.posts == posts)
                .first()
            )

            if not existing_scanresult:
                # Store only time-series numerical metrics
                new_scanresults = ScanResults(
                    socialaccount_id=socialaccount_id,
                    followers=followers,
                    likes=likes,
                    posts=posts,
                    time_taken=profile_data.get("time_taken", "0.0s"),
                )
                
                db.session.add(new_scanresults)
                db.session.commit()

            print(f"[SCRAPER LOG] Successfully saved metrics for @{username}.")

            # Safely log success metrics using the thread state lock
            with state_lock:
                scan_log["success_count"][platform_name] = scan_log["success_count"].get(platform_name, 0) + 1

        except Exception as e:
            db.session.rollback()
            msg = f"Error in process_username [{username}] on [{platform_id}]: {e}"
            ic(msg)
            
            # Safely log failure metrics using the thread state lock
            with state_lock:
                platform_name = locals().get('platform_name', f"Platform_{platform_id}")
                scan_log["failure_count"][platform_name] = scan_log["failure_count"].get(platform_name, 0) + 1

                if "failures" not in scan_log:
                    scan_log["failures"] = {}
                if platform_name not in scan_log["failures"]:
                    scan_log["failures"][platform_name] = {}
                scan_log["failures"][platform_name][username] = str(e)
        finally:
            # Critically important: remove the scoped session context when this thread terminates
            db.session.remove()

def scan_database(app, db_session):
    global scan_should_stop, scan_progress, scan_log

    # Reset scan variables
    scan_should_stop = False
    scan_log = {
        "success_count": {},
        "failure_count": {},
        "failures": {},
    }

    try:
        start_time = datetime.datetime.now()
        ic(f"Scanning database started at {start_time}")

        scan_progress["status"] = "running"
        scan_progress["message"] = "Initializing scan..."

        platform_ids = [row[0] for row in db_session.query(SocialAccount.platform_id).distinct()]
        platforms_accounts = {}

        for platform_id in platform_ids:
            platforms_accounts[platform_id] = db_session.query(SocialAccount).filter_by(platform_id=platform_id).all()

        social_account_lists = platforms_accounts.values()
        interleaved = zip_longest(*social_account_lists)
        all_social_accounts = [item for item in chain(*interleaved) if item is not None]

        scan_progress["total"] = len(all_social_accounts)
        scan_progress["processed"] = 0
        scan_progress["success"] = 0
        scan_progress["failure"] = 0
        scan_progress["message"] = f"Starting scan of {len(all_social_accounts)} accounts..."

        with ThreadPoolExecutor() as executor:
            futures = []

            for socialaccount in all_social_accounts:
                if scan_should_stop:
                    ic("Scan stopped by user")
                    scan_progress["status"] = "stopping"
                    scan_progress["message"] = "Stopping scan..."
                    break

                # Corrected: Removed db_session argument to align perfectly with process_username signature
                futures.append(
                    executor.submit(
                        process_username,
                        app,
                        socialaccount.platform_id,
                        socialaccount.username,
                        socialaccount.id,
                    )
                )

            for future in futures:
                if scan_should_stop:
                    scan_progress["status"] = "stopping"
                    scan_progress["message"] = "Stopping scan..."
                    executor.shutdown(wait=False)
                    break

                try:
                    future.result()
                except Exception as e:
                    ic(f"Error tracking background future execution thread: {e}")
                finally:
                    # Synchronize the progress dictionary counters securely
                    with state_lock:
                        scan_progress["processed"] += 1
                        success_count = sum(scan_log["success_count"].values()) if scan_log["success_count"] else 0
                        failure_count = sum(scan_log["failure_count"].values()) if scan_log["failure_count"] else 0

                        scan_progress["success"] = success_count
                        scan_progress["failure"] = failure_count

                        if scan_progress["total"] > 0:
                            percent = int((scan_progress["processed"] / scan_progress["total"]) * 100)
                            scan_progress["message"] = f"Processing: {scan_progress['processed']}/{scan_progress['total']} accounts ({percent}%)"

        if scan_should_stop:
            scan_log["stopped_by_user"] = True
            scan_progress["status"] = "stopped"
            scan_progress["message"] = "Scan stopped by user"

        end_time = datetime.datetime.now()
        time_taken = end_time - start_time
        minutes = round(time_taken.total_seconds() // 60)
        seconds = round(time_taken.total_seconds() % 60)
        scan_log["time_taken"] = f"{minutes} دقيقة {seconds} ثانية"

        if scan_progress["processed"] > 0:
            new_scanlog = ScanLog(
                success_count=scan_log["success_count"],
                failure_count=scan_log["failure_count"],
                failures=scan_log["failures"],
                time_taken=str(scan_log["time_taken"]),
            )
            db_session.add(new_scanlog)
            db_session.commit()

            cleanup_old_scanlogs(db_session, keep_count=3)

        if not scan_should_stop:
            scan_progress["status"] = "completed"
            scan_progress["message"] = f"Scan completed in {minutes}m {seconds}s"

        ic(f"Database scan finished execution state context trace. Duration: ({time_taken})")

    except Exception as e:
        scan_progress["status"] = "error"
        scan_progress["message"] = f"Error: {str(e)}"
        ic(f"Error in scan_database execution pipeline: {e}")
        import traceback
        ic(traceback.format_exc())