import os
from apps import create_app, db
from apps.social.models import SocialAccount, SocialPost
from apps.config import config_dict
from dotenv import load_dotenv

basedir = os.path.dirname(__file__)
dotenv_path = os.path.join(basedir, ".env.dev")
load_dotenv(dotenv_path)

DEBUG = os.getenv("DEBUG_MODE", "False") == "True"
get_config_mode = 'Debug' if DEBUG else 'Production'
app_config = config_dict[get_config_mode.capitalize()]

app = create_app(app_config)

with app.app_context():
    account = SocialAccount.query.filter_by(username='cristiano').first()
    
    if not account:
        print("[-] SocialAccount with username 'cristiano' not found in database.")
    else:
        print(f"\n====================================")
        print(f"PROFILE: {account.username} (Platform ID: {account.platform_id})")
        print(f"====================================")
        print(f"Followers:   {account.followers}")
        print(f"Total Posts: {account.total_posts}")
        print(f"Total Likes: {account.total_likes}")
        print(f"Category:    {account.category}")
        print(f"Bio:         {account.bio_text}")
        
        posts = SocialPost.query.filter_by(socialaccount_id=account.id).order_by(SocialPost.posted_at.desc()).all()
        print(f"\n[*] Found {len(posts)} total stored posts.")
        
        print("\n--- Top 3 Most Recent Posts ---")
        for i, post in enumerate(posts[:3], 1):
            caption_preview = post.caption[:50] + "..." if post.caption and len(post.caption) > 50 else (post.caption or "")
            caption_preview = caption_preview.encode('ascii', 'ignore').decode('ascii')
            
            print(f"\nPost #{i} (ID: {post.platform_post_id})")
            print(f"  Posted At: {post.posted_at}")
            print(f"  Plays:     {post.plays}")
            print(f"  Likes:     {post.likes}")
            print(f"  Comments:  {post.comments}")
            print(f"  Shares:    {post.shares}")
            print(f"  Saves:     {post.saves}")
            print(f"  Caption:   {caption_preview}")
        print("\n====================================\n")
