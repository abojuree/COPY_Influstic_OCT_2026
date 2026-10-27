from apps import create_app, db
from apps.config import config_dict
from apps.home.util import tiktok
import json

def main():
    app = create_app(config_dict['Debug'])
    with app.app_context():
        # Test with multiple usernames
        test_usernames = [
            # Valid usernames
            "sheryelfakih",  # Known valid username
            "khaby.lame",    # Very popular TikTok user

            # Invalid usernames
            "thisisanonexistentusername123456789",  # Completely made up
            "this_user_does_not_exist_12345",       # Another made up username
        ]

        for username in test_usernames:
            test_username(username)

def test_username(username):
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
    else:
        print(f"\nUsername '{username}' successfully retrieved:")
        print(f"Name: {result['public_profile_name']}")
        print(f"Followers: {result['followers']}")
        print(f"Likes: {result['likes']}")
        print(f"Posts: {result['posts']}")
        print(f"Bio: {result['bio_text']}")
        print(f"Profile Picture URL available: {'Yes' if result['profile_picture'] else 'No'}")
        print(f"External URL: {result['external_url']}")

if __name__ == "__main__":
    main()
