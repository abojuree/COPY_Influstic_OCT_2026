from apps import create_app, db
from apps.config import config_dict
from apps.home.util import tiktok, instagram, snapchat
import json

def main():
    app = create_app(config_dict['Debug'])
    with app.app_context():
        # Initialize test results tracking
        test_results = {
            'tiktok': {'passed': 0, 'failed': 0},
            'instagram': {'passed': 0, 'failed': 0},
            'snapchat': {'passed': 0, 'failed': 0}
        }
        
        print("\n" + "="*70)
        print("TESTING TIKTOK API".center(70))
        print("="*70)
        
        tiktok_usernames = [
            "sheryelfakih",  # Valid
            "khaby.lame",    # Valid
            "this_user_does_not_exist_12345"  # Invalid
        ]
        
        for username in tiktok_usernames:
            result = test_tiktok(username)
            if result:
                test_results['tiktok']['passed'] += 1
            else:
                test_results['tiktok']['failed'] += 1
        
        print("\n" + "="*70)
        print("TESTING INSTAGRAM API".center(70))
        print("="*70)
        
        # Test Instagram with valid and invalid usernames
        instagram_usernames = [
            "engziada",   # Valid
            "cristiano",  # Valid
            "this_user_does_not_exist_12345"  # Invalid
        ]
        
        for username in instagram_usernames:
            result = test_instagram(username)
            if result:
                test_results['instagram']['passed'] += 1
            else:
                test_results['instagram']['failed'] += 1
                
        print("\n" + "="*70)
        print("TESTING SNAPCHAT API".center(70))
        print("="*70)
        
        # Test Snapchat with valid and invalid usernames
        snapchat_usernames = [
            "official",  # Valid
            "snapchat",  # Valid
            "this_user_does_not_exist_12345"  # Invalid
        ]
        
        for username in snapchat_usernames:
            result = test_snapchat(username)
            if result:
                test_results['snapchat']['passed'] += 1
            else:
                test_results['snapchat']['failed'] += 1
        
        # Print test summary report
        print_test_report(test_results)

def test_tiktok(username):
    print(f"\n{'='*50}")
    print(f"Testing TikTok function with username: {username}")
    print(f"{'='*50}")
    
    # Call the function
    result = tiktok(username)
    
    # Print the result in a formatted way
    print("\nResult:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Check if there was an error
    if "error" in result:
        print(f"\nUsername '{username}' returned an error:")
        print(f"Error message: {result['error']}")
        return False
    else:
        print(f"\nUsername '{username}' successfully retrieved:")
        print(f"Name: {result['public_profile_name']}")
        print(f"Followers: {result['followers']}")
        print(f"Likes: {result['likes']}")
        print(f"Posts: {result['posts']}")
        print(f"Bio: {result['bio_text']}")
        print(f"Profile Picture URL available: {'Yes' if result['profile_picture'] else 'No'}")
        print(f"External URL: {result['external_url']}")
        return True

def test_instagram(username):
    print(f"\n{'='*50}")
    print(f"Testing Instagram function with username: {username}")
    print(f"{'='*50}")
    
    # Call the function
    result = instagram(username)
    
    # Print the result in a formatted way
    print("\nResult:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Check if there was an error
    if "error" in result:
        print(f"\nUsername '{username}' returned an error:")
        print(f"Error message: {result['error']}")
        return False
    else:
        print(f"\nUsername '{username}' successfully retrieved:")
        print(f"Name: {result['public_profile_name']}")
        print(f"Followers: {result['followers']}")
        print(f"Posts: {result['posts']}")
        print(f"Bio: {result['bio_text']}")
        print(f"Profile Picture URL available: {'Yes' if result['profile_picture'] else 'No'}")
        print(f"External URL: {result['external_url']}")
        return True
        
def test_snapchat(username):
    print(f"\n{'='*50}")
    print(f"Testing Snapchat function with username: {username}")
    print(f"{'='*50}")
    
    # Call the function
    result = snapchat(username)
    
    # Print the result in a formatted way
    print("\nResult:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Check if there was an error
    if "error" in result:
        print(f"\nUsername '{username}' returned an error:")
        print(f"Error message: {result['error']}")
        return False
    else:
        print(f"\nUsername '{username}' successfully retrieved:")
        print(f"Name: {result['public_profile_name']}")
        print(f"Followers: {result['followers']}")
        print(f"Bio: {result['bio_text']}")
        print(f"Profile Picture URL available: {'Yes' if result['profile_picture'] else 'No'}")
        print(f"External URL: {result['external_url']}")
        return True

def print_test_report(test_results):
    """
    Print a summary report of all tests performed
    """
    print("\n" + "="*70)
    print("TEST SUMMARY REPORT".center(70))
    print("="*70)
    
    total_passed = 0
    total_failed = 0
    
    for platform, results in test_results.items():
        passed = results['passed']
        failed = results['failed']
        total = passed + failed
        total_passed += passed
        total_failed += failed
        
        if total > 0:
            success_rate = (passed / total) * 100
        else:
            success_rate = 0
            
        print(f"\n{platform.upper()} API Tests:")
        print(f"  Total Tests: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Success Rate: {success_rate:.1f}%")
    
    total_tests = total_passed + total_failed
    if total_tests > 0:
        overall_success_rate = (total_passed / total_tests) * 100
    else:
        overall_success_rate = 0
        
    print(f"\n{'-'*70}")
    print("OVERALL SUMMARY:".center(70))
    print(f"  Total Tests: {total_tests}")
    print(f"  Total Passed: {total_passed}")
    print(f"  Total Failed: {total_failed}")
    print(f"  Overall Success Rate: {overall_success_rate:.1f}%")
    print("="*70)

if __name__ == "__main__":
    main()
