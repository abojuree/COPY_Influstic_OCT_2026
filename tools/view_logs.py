from apps import create_app, db
from apps.config import config_dict
from apps.reports.models import ScanLog
from apps.social.models import Platform, SocialAccount

def main():
    app = create_app(config_dict['Debug'])
    with app.app_context():
        # Get the most recent scan log
        log = ScanLog.query.order_by(ScanLog.creation_date.desc(), ScanLog.creation_time.desc()).first()
        
        if log:
            print("\n===== LAST SCAN LOG =====")
            print(f"Date: {log.creation_date}")
            print(f"Time: {log.creation_time}")
            print(f"Time Taken: {log.time_taken}")
            
            # Success counts
            print("\n----- SUCCESS COUNTS -----")
            total_success = 0
            for platform, count in log.success_count.items():
                print(f"{platform}: {count}")
                total_success += count
            print(f"Total Success: {total_success}")
            
            # Failure counts
            print("\n----- FAILURE COUNTS -----")
            total_failure = 0
            for platform, count in log.failure_count.items():
                print(f"{platform}: {count}")
                total_failure += count
            print(f"Total Failure: {total_failure}")
            
            # Calculate success rate
            total = total_success + total_failure
            if total > 0:
                success_rate = (total_success / total) * 100
                print(f"\nSuccess Rate: {success_rate:.2f}%")
            
            # Sample of failures
            print("\n----- SAMPLE FAILURES -----")
            for platform, users in log.failures.items():
                print(f"\nPlatform: {platform}")
                print(f"Total failures: {len(users)}")
                print("Sample errors:")
                count = 0
                for username, error in users.items():
                    count += 1
                    if count <= 5:  # Show only 5 examples per platform
                        print(f"  Username: {username}")
                        print(f"  Error: {error}")
                        print("  ---")
            
            # Get platform statistics
            print("\n===== PLATFORM STATISTICS =====")
            platforms = Platform.query.all()
            for platform in platforms:
                account_count = SocialAccount.query.filter_by(platform_id=platform.id).count()
                success_count = log.success_count.get(platform.name, 0)
                failure_count = log.failure_count.get(platform.name, 0)
                
                print(f"\nPlatform: {platform.name}")
                print(f"Total Accounts: {account_count}")
                print(f"Success: {success_count}")
                print(f"Failure: {failure_count}")
                
                if success_count + failure_count > 0:
                    platform_success_rate = (success_count / (success_count + failure_count)) * 100
                    print(f"Success Rate: {platform_success_rate:.2f}%")
        else:
            print("No scan logs found.")

if __name__ == "__main__":
    main()
