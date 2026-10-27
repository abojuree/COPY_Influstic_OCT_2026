from ..base import BaseSocialScraper

class TikTokApifyScraper(BaseSocialScraper):
    def fetch_profile(self, username: str) -> dict:
        platform_name = "تيك توك"
        
        import os
        from apify_client import ApifyClient
        import logging
        from datetime import datetime

        logger = logging.getLogger(__name__)
        
        try:
            client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
            
            run_input = {
                "profiles": [username],
                "maxFollowersPerProfile": 0,
                "maxFollowingPerProfile": 0,
                "commentsPerPost": 0,
                "topLevelCommentsPerPost": 0,
                "maxRepliesPerComment": 0,
            }
            
            run = client.actor("clockworks/tiktok-profile-scraper").call(run_input=run_input)
            
            dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else run.default_dataset_id
            items = list(client.dataset(dataset_id).iterate_items())
            
            if not items or items[0].get("error") or items[0].get("noResults"):
                error_msg = items[0].get('error') if items else 'No items returned'
                return {
                    "username": username,
                    "platform_name": platform_name,
                    "error": f"TikTok Scraping failed or user not found: {error_msg}"
                }
                
            first_item = items[0]
            author_meta = first_item.get("authorMeta", {})
            
            followers = author_meta.get("fans", 0)
            total_posts = author_meta.get("video", 0)
            total_likes = author_meta.get("heart", 0)
            bio_text = author_meta.get("signature", "")
            full_name = author_meta.get("nickName") or author_meta.get("name", username)
            profile_pic = author_meta.get("avatar") or author_meta.get("originalAvatarUrl", "")
            
            print(f"DEBUG [TikTok Clockworks Parsed]: Username={username}, Followers={followers}, Likes={total_likes}, Posts={len(items)}")
            
            recent_posts = []
            for item in items:
                if not item.get("id"):
                    continue
                
                timestamp = item.get("createTimeISO")
                posted_at = None
                if timestamp:
                    try:
                        posted_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except ValueError:
                        posted_at = None

                post = {
                    "platform_post_id": str(item.get("id")),
                    "posted_at": posted_at,
                    "plays": item.get("playCount", 0),
                    "likes": item.get("diggCount", 0),
                    "comments": item.get("commentCount", 0),
                    "shares": item.get("shareCount", 0),
                    "saves": item.get("collectCount", 0), # collectCount = Bookmarks/Saves
                    "caption": item.get("text", ""),
                    "raw_data": item
                }
                recent_posts.append(post)

            return {
                "username": username,
                "platform_name": platform_name,
                "full_name": full_name,
                "followers_count": followers,
                "total_likes": total_likes,
                "total_posts": total_posts,
                "is_verified": author_meta.get("verified", False),
                "bio_text": bio_text,
                "profile_pic_url": profile_pic,
                "external_url": f"https://www.tiktok.com/@{username}",
                "recent_posts": recent_posts
            }
            
        except Exception as e:
            return self.handle_http_error(platform_name, username, e)
