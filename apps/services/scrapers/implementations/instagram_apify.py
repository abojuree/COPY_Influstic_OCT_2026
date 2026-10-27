from ..base import BaseSocialScraper

class InstagramApifyScraper(BaseSocialScraper):
    def fetch_profile(self, username: str) -> dict:
        platform_name = "انستغرام"
        
        import os
        from apify_client import ApifyClient
        import logging
        from datetime import datetime

        logger = logging.getLogger(__name__)

        try:
            client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
            run_input = { "usernames": [username] }
            run = client.actor("coderx/instagram-profile-scraper-api").call(run_input=run_input)
            
            dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else run.default_dataset_id
            items = list(client.dataset(dataset_id).iterate_items())
            
            if not items:
                return {
                    "username": username,
                    "platform_name": platform_name,
                    "error": "لم يتم العثور على بيانات"
                }
                
            profile_data = items[0]
            import json
            print(f"DEBUG 1 [Instagram Raw Payload]:\n{json.dumps(profile_data, indent=2, default=str)}")
            
            followers_count = (
                profile_data.get('followersCount') or 
                profile_data.get('follower_count') or 
                profile_data.get('edge_followed_by', {}).get('count') or 
                0
            )
            posts_count = (
                profile_data.get('postsCount') or 
                profile_data.get('mediaCount') or 
                profile_data.get('posts_count') or 
                profile_data.get('edge_owner_to_timeline_media', {}).get('count') or 
                0
            )
            bio = profile_data.get("biography", "")
            full_name = profile_data.get("fullName") or profile_data.get("full_name") or username
            profile_pic = profile_data.get("hdProfilePicUrl") or profile_data.get("profilePicUrl") or profile_data.get("profile_pic_url_hd") or profile_data.get("profile_pic_url")
            
            print(f"DEBUG 2 [Instagram Parsed]: Followers={followers_count}, Posts={posts_count}, Bio={bio}")
            
            posts_array = (
                profile_data.get('latestPosts') or 
                profile_data.get('posts') or 
                profile_data.get('items') or 
                profile_data.get('edge_owner_to_timeline_media', {}).get('edges', []) or 
                []
            )
            
            recent_posts = []
            
            for item in posts_array:
                post = item.get('node', item) if isinstance(item, dict) else item
                
                timestamp = post.get("timestamp") or post.get("taken_at_timestamp")
                posted_at = None
                if timestamp:
                    if isinstance(timestamp, str):
                        try:
                            # Handling ISO 8601 strings like "2026-02-19T19:08:14"
                            posted_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except ValueError:
                            try:
                                posted_at = datetime.fromtimestamp(float(timestamp))
                            except ValueError:
                                posted_at = None
                    elif isinstance(timestamp, (int, float)):
                        posted_at = datetime.fromtimestamp(timestamp)
                
                post_id = str(post.get('id') or post.get('shortcode') or post.get('code') or '')
                likes = post.get('likesCount') or post.get('like_count') or post.get('edge_liked_by', {}).get('count') or 0
                comments = post.get('commentsCount') or post.get('comment_count') or post.get('edge_media_to_comment', {}).get('count') or 0
                views = post.get('videoViewCount') or post.get('playCount') or post.get('view_count') or post.get('video_view_count') or 0
                caption = post.get('caption') or post.get('text') or ''
                
                if not caption and post.get('edge_media_to_caption', {}).get('edges'):
                    edges = post.get('edge_media_to_caption').get('edges')
                    if edges and len(edges) > 0:
                        caption = edges[0].get('node', {}).get('text', '')
                
                recent_posts.append({
                    "platform_post_id": post_id,
                    "posted_at": posted_at,
                    "plays": views,
                    "likes": likes,
                    "comments": comments,
                    "shares": None,
                    "saves": None,
                    "caption": caption,
                    "raw_data": post
                })

            if not posts_count or posts_count == 0:
                posts_count = len(recent_posts)

            profile_total_likes = profile_data.get('heartCount') or profile_data.get('likesCount') or 0
            if profile_total_likes == 0 and len(recent_posts) > 0:
                profile_total_likes = sum(post.get('likes', 0) for post in recent_posts)

            return {
                "username": username,
                "platform_name": platform_name,
                "full_name": full_name,
                "followers_count": followers_count,
                "total_posts": posts_count,
                "total_likes": profile_total_likes,
                "bio_text": bio,
                "profile_pic_url": profile_pic,
                "external_url": f"https://www.instagram.com/{username}/",
                "recent_posts": recent_posts
            }
            
        except Exception as e:
            return self.handle_http_error(platform_name, username, e)
