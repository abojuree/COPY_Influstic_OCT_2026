from ..base import BaseSocialScraper

class SnapchatScraper(BaseSocialScraper):
    def fetch_profile(self, username: str) -> dict:
        platform_name = "سناب شات"
        
        import os
        from apify_client import ApifyClient
        import logging
        from datetime import datetime

        logger = logging.getLogger(__name__)

        try:
            client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
            # "tri_angle/snapchat-scraper" usually takes profilesInput
            # We will send just the username, as building full URLs seems to fail on the new Apify actor
            run_input = { "profilesInput": [username] }
            run = client.actor("tri_angle/snapchat-scraper").call(run_input=run_input)
            
            dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else run.default_dataset_id
            items = list(client.dataset(dataset_id).iterate_items())
            
            if not items:
                return {
                    "username": username,
                    "platform_name": platform_name,
                    "error": "لم يتم العثور على بيانات"
                }
                
            profile_data = items[0]
            print(f"DEBUG 1 [Snapchat Raw Payload]: {str(profile_data)[:200]}...")
            
            followers_count = profile_data.get("subscribers", 0)
            bio = profile_data.get("profileDescription", "")
            full_name = profile_data.get("username1", username)
            category = profile_data.get("category", "")
            
            print(f"DEBUG 2 [Snapchat Parsed]: Followers={followers_count}, Category={category}, Bio={bio}")
            
            stories = profile_data.get("stories", [])
            spotlights = profile_data.get("spotlights", [])
            
            all_media = stories + spotlights
                
            recent_posts = []
            
            for item in all_media:
                snaps = item.get("snaps", [])
                if not snaps:
                    continue
                
                # Taking the timestamp from the first snap in the story/spotlight
                timestamp = snaps[0].get("timestamp")
                posted_at = None
                if timestamp:
                    if isinstance(timestamp, str):
                        try:
                            posted_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except ValueError:
                            try:
                                posted_at = datetime.fromtimestamp(float(timestamp))
                            except ValueError:
                                posted_at = None
                    elif isinstance(timestamp, (int, float)):
                        posted_at = datetime.fromtimestamp(timestamp)
                
                caption = item.get("storyTitle") or item.get("videoDescription", "")
                
                post = {
                    "platform_post_id": item.get("id"),
                    "posted_at": posted_at,
                    "plays": item.get("views", 0),
                    "likes": None,
                    "comments": None,
                    "shares": None,
                    "saves": None,
                    "caption": caption,
                    "raw_data": item
                }
                recent_posts.append(post)

            return {
                "username": username,
                "platform_name": platform_name,
                "full_name": full_name,
                "followers_count": followers_count,
                "bio_text": bio,
                "category": category,
                "external_url": f"https://www.snapchat.com/@{username}",
                "recent_posts": recent_posts
            }
            
        except Exception as e:
            return self.handle_http_error(platform_name, username, e)
