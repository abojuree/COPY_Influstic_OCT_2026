from datetime import datetime
from genericpath import isfile
import os
from os import listdir, makedirs, path
import random
from bs4 import BeautifulSoup, NavigableString, Tag
from flask import current_app, url_for
from icecream import ic
import json
import requests
from werkzeug.utils import secure_filename

from apps.profiles.models import Influencer
from apps.reports.models import ScanLog
from apps.social.models import Platform, SocialAccount
from apps.authentication.models import Users

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class TransientHTTPError(Exception):
    pass

def get_unified_table_data(query_filter=None):
    from sqlalchemy import func
    from apps import db
    from apps.social.models import SocialPost
    
    query = db.session.query(
        SocialAccount,
        func.avg(SocialPost.plays).label('avg_views'),
        func.avg(SocialPost.likes).label('avg_likes'),
        func.avg(SocialPost.comments).label('avg_comments'),
        func.avg(SocialPost.shares).label('avg_shares'),
        func.avg(SocialPost.saves).label('avg_saves')
    ).outerjoin(SocialPost).group_by(SocialAccount.id)
    
    if query_filter is not None:
        query = query.filter(query_filter)
        
    results = query.all()
    
    data = []
    for row in results:
        account = row[0]
        data.append({
            'account': account,
            'influencer': account.influencer,
            'platform': account.platform,
            'avg_views': int(row.avg_views) if row.avg_views is not None else None,
            'avg_likes': int(row.avg_likes) if row.avg_likes is not None else None,
            'avg_comments': int(row.avg_comments) if row.avg_comments is not None else None,
            'avg_shares': int(row.avg_shares) if row.avg_shares is not None else None,
            'avg_saves': int(row.avg_saves) if row.avg_saves is not None else None,
        })
    return data

def return_error_dict(retry_state):
    return {"error": f"فشل بعد 3 محاولات: {str(retry_state.outcome.exception())}"}
# profile_data: dict = {
#     "username": '',
#     "platform": '',
#     "public_profile_name": '',
#     "followers": 0,
#     "likes": 0,
#     "posts": 0,
#     "profile_picture": '',
#     "bio_text": '',
#     "external_url": '',
#     "time_taken": 0,
#     "error": ''
#     "existing_record":""
# }


def search_user_profile(username:str, platform_id, socialaccount_id=None) -> dict:
    """
    Search for a user profile on a specific platform
    :param username: The username to search for
    :param platform: The platform to search on
    :return: A dictionary containing the user's profile data
    """
    from apps import db
    from apps.social.models import SocialAccount, SocialPost

    t1 = datetime.now()

    platform = Platform.query.get(platform_id)
    if platform:
        platform_name_english = platform.name_english.lower().strip()
        # Map platform names to functions
        platform_functions = {
            'tiktok': tiktok,
            'snapchat': snapchat,
            'instagram': instagram
        }

        if platform_name_english in platform_functions:
            profile_data = platform_functions[platform_name_english](username)
        else:
            raise ValueError(f"المنصة {platform.name} غير مدعومة حالياً")
    else:
        raise ValueError("المنصة غير موجودة في قاعدة البيانات")

    duration = datetime.now() - t1
    profile_data["time_taken"] = f"{duration.total_seconds():.1f} ثانية"
    profile_data["platform_id"] = platform_id
    profile_data["username"] = username
    profile_data["platform"] = platform.name
    profile_data["platform_name_english"] = platform.name_english

    # Direct Database Mapping
    if "error" not in profile_data:
        account = None
        if socialaccount_id:
            account = SocialAccount.query.get(socialaccount_id)
        if not account:
            account = SocialAccount.query.filter_by(username=username, platform_id=platform_id).first()
        
        if account:
            # Parse the JSON safely using .get() chains
            account.followers = profile_data.get('followers_count', profile_data.get('followers', 0))
            account.total_likes = profile_data.get('likes_count', profile_data.get('total_likes', profile_data.get('likes', 0)))
            account.total_posts = profile_data.get('posts_count', profile_data.get('total_posts', profile_data.get('posts', 0)))
            
            # Update other fields safely
            account.public_profile_name = profile_data.get('full_name', profile_data.get('public_profile_name', ''))
            account.bio_text = profile_data.get('bio_text', '')
            account.profile_picture = profile_data.get('profile_pic_url', profile_data.get('profile_picture', ''))
            account.external_url = profile_data.get('external_url', '')
            if 'recent_posts' in profile_data and profile_data['recent_posts']:
                # Clear existing posts
                SocialPost.query.filter_by(socialaccount_id=account.id).delete()
                
                # Upsert new posts
                posts_to_save = []
                for p in profile_data['recent_posts']:
                    new_post = SocialPost(
                        influencer_id=account.influencer_id,
                        socialaccount_id=account.id,
                        platform_post_id=str(p.get('platform_post_id')),
                        posted_at=p.get('posted_at'),
                        plays=p.get('plays', 0),
                        likes=p.get('likes', 0),
                        comments=p.get('comments', 0),
                        shares=p.get('shares', 0),
                        saves=p.get('saves', 0),
                        caption=p.get('caption', ''),
                        raw_data=p.get('raw_data', {})
                    )
                    posts_to_save.append(new_post)
                if posts_to_save:
                    db.session.bulk_save_objects(posts_to_save)

            db.session.commit()

    return profile_data

# ////////////////////////////////////////////////////////////////////////////////////////

def tiktok_old(username: str) -> dict:
    """
    Retrieves the profile data of a user from the TikTok platform.

    Args:
        username (str): The username of the user.

    Returns:
        dict: A dictionary containing the profile data of the user. The dictionary has the following keys:
            - "public_profile_name" (str): The public profile name of the user.
            - "followers" (int): The number of followers the user has.
            - "likes" (int): The number of likes the user has.
            - "posts" (int): The number of posts the user has.
            - "profile_picture" (str): The URL of the user's profile picture.
            - "bio_text" (str): The user's bio text.
            - "external_url" (str): The URL of the user's TikTok profile.

            If there is an error retrieving the profile data, the dictionary will also contain the following key:
            - "error" (str): A description of the error that occurred.

    Raises:
        KeyError: If the required data is not found in the JSON structure.

    Note:
        - The function uses the TikTok API to retrieve the profile data.
        - The function handles cases where the user's profile is not found on the TikTok platform.
        - The function uses the BeautifulSoup library to parse the HTML content of the TikTok profile page.
        - The function uses the requests library to send GET requests to the TikTok API and retrieve the profile data.

    Example:
        >>> tiktok("example_user")
        {
            "public_profile_name": "Example User",
            "followers": 1000,
            "likes": 5000,
            "posts": 0,
            "profile_picture": "https://example.com/profile_picture.jpg",
            "bio_text": "This is an example user.",
            "external_url": "https://www.tiktok.com/@example_user"
        }
    """
    profile_data = {}
    url = f"https://www.tiktok.com/@{username}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    # proxies = {
    #     "http": "http://10.10.1.10:3128",
    #     "https": "http://10.10.1.10:1080",
    # }

    # r = requests.get(url, headers=headers, proxies=proxies, timeout=5)
    r = requests.get(url, headers=headers, timeout=30)

    # Print the status code
    # ic(r.status_code)

    # ic(r.status_code)
    if r.status_code != 200:
        # ic("From TikTok: ", r.status_code)
        profile_data["username"] = username
        profile_data["platform"] = "تيك توك"
        profile_data["error"] = "إسم المستخدم غير موجود على هذه المنصة"
        return profile_data

    # Parse the HTML content
    soup = BeautifulSoup(r.text, "html.parser")
    # Save the soup to a file
    # with open("tiktok_soup.html", "w", encoding="utf-8") as file:
    #     file.write(str(soup))

    # Find the script element by ID
    script_element = soup.find("script", id="__UNIVERSAL_DATA_FOR_REHYDRATION__")
    # ic("script_element found" if script_element else "script_element not found")

    # Check if the script element exists
    if script_element is None:
        # ic("From TikTok: ", "Script Element is None")
        profile_data["username"] = username
        profile_data["platform"] = "تيك توك"
        profile_data["error"] = "خطأ أثناء قراءة البيانات من المنصة"
        return profile_data

    # Extract the text content of the script element
    json_text = script_element.text.strip()
    # Parse the JSON data
    json_data = json.loads(json_text)
    try:
        user_data = json_data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]["user"]
        stats_data = json_data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]["stats"]
        # ic(user_data, stats_data)
    except KeyError:
        # ic("From Tiktok: ",json_data)
        profile_data["username"] = username
        profile_data["platform"] = "تيك توك"
        profile_data["error"] = "Could not find the required data in the JSON structure."
        return profile_data

    profile_data: dict = {
        # "username": username,
        # "platform": "TikTok",
        # "platform_id": platform_id,
        "public_profile_name": user_data.get("nickname", ""),
        "followers": stats_data.get("followerCount", "0"),
        "likes": stats_data.get("heartCount", "0"),
        "posts": 0,
        "profile_picture": user_data.get("avatarLarger", ""),
        "bio_text": user_data.get("signature", ""),
        "external_url": url,
        # "time_taken": duration.total_seconds(),
    }
    return profile_data

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((TransientHTTPError, requests.exceptions.RequestException, TimeoutError)),
    retry_error_callback=return_error_dict
)
def tiktok(username: str) -> dict:
    """
    Retrieves the profile data of a user from the TikTok platform using the TikTok Scraper API.

    Args:
        username (str): The username of the user.

    Returns:
        dict: A dictionary containing the profile data of the user. The dictionary has the following keys:
            - "public_profile_name" (str): The public profile name of the user.
            - "followers" (int): The number of followers the user has.
            - "likes" (int): The number of likes the user has.
            - "posts" (int): The number of posts the user has.
            - "profile_picture" (str): The URL of the user's profile picture.
            - "bio_text" (str): The user's bio text.
            - "external_url" (str): The URL of the user's TikTok profile.

            If there is an error retrieving the profile data, the dictionary will also contain the following key:
            - "error" (str): A description of the error that occurred.

    Note:
        - The function uses the TikTok Scraper API from RapidAPI to retrieve the profile data.
        - The function handles cases where the user's profile is not found on the TikTok platform.
        - The function uses HTTP client to make requests to the TikTok Scraper API.

    Example:
        >>> tiktok("example_user")
        {
            "public_profile_name": "Example User",
            "followers": 1000,
            "likes": 5000,
            "posts": 159,
            "profile_picture": "https://example.com/profile_picture.jpg",
            "bio_text": "This is an example user.",
            "external_url": "https://www.tiktok.com/@example_user"
        }
    """
    user_data = {}
    profile_data = {
        "username": username,
        "platform": "تيك توك",
        "external_url": f"https://www.tiktok.com/@{username}",
        "success": True,
        "error": None
    }

    try:
        url = "https://tiktok-scraper2.p.rapidapi.com/user/info"
        querystring = {"user_name": username}

        rapidapi_key = os.getenv("RAPIDAPI_KEY")
        print(f"[DEBUG] tiktok - RAPIDAPI_KEY loaded: {rapidapi_key is not None}, Length: {len(rapidapi_key) if rapidapi_key else 0}")
        headers = {
            'x-rapidapi-key': rapidapi_key or "YOUR_RAPIDAPI_KEY_HERE",
            'x-rapidapi-host': "tiktok-scraper2.p.rapidapi.com"
        }

        print(f"[DEBUG] tiktok - Calling RapidAPI endpoint /user/info?user_name={username}")
        response = requests.get(url, headers=headers, params=querystring, timeout=30)

        # Check if the request was successful
        if response.status_code == 429:
            return {"success": False, "error": "Rate limit exceeded (HTTP 429). Please try again later."}
            
        if response.status_code != 200:
            print(f"[DEBUG] tiktok - RapidAPI request failed! Status: {response.status_code}")
            ic(f"From TikTok API: Status code {response.status_code}")
            if response.status_code in [500, 502, 503, 504]:
                raise TransientHTTPError(f"HTTP {response.status_code}")
            return {"success": False, "error": "فشل في استرجاع البيانات من المنصة"}

        json_data = response.json()

        # Check if the response contains user info
        if not json_data.get("userInfo"):
            ic("From TikTok API: No userInfo in response")
            return {"success": False, "error": "إسم المستخدم غير موجود على هذه المنصة"}

        # Extract user data and stats safely
        user_data = json_data.get("userInfo", {}).get("user", {})
        stats_data = json_data.get("userInfo", {}).get("stats", {})

        # Verify that the returned username matches the requested username
        returned_username = user_data.get("uniqueId", "").lower()
        if returned_username != username.lower():
            ic(f"From TikTok API: Username mismatch - requested: {username}, returned: {returned_username}")
            return {"success": False, "error": "إسم المستخدم غير موجود على هذه المنصة"}

        # Populate profile data
        profile_data.update({
            "public_profile_name": user_data.get("nickname", ""),
            "followers": stats_data.get("followerCount", 0),
            "likes": stats_data.get("heartCount", 0),
            "posts": stats_data.get("videoCount", 0),
            "profile_picture": user_data.get("avatarLarger", ""),
            "bio_text": user_data.get("signature", "") if "signature" in user_data else "",
        })

    except (TransientHTTPError, requests.exceptions.RequestException, TimeoutError) as e:
        print(f"[DEBUG] tiktok - TransientHTTPError: {e}")
        raise e
    except Exception as e:
        print(f"[DEBUG] tiktok - Exception: {e}")
        ic(f"Error in TikTok API: {str(e)}")
        return {"success": False, "error": f"خطأ أثناء قراءة البيانات من المنصة: {str(e)}"}

    return profile_data

# ////////////////////////////////////////////////////////////////////////////////////////

def snapchat_old(username: str) -> dict:
    """
    Retrieves Snapchat profile data for a given username.

    Args:
        username (str): The Snapchat username to retrieve profile data for.

    Returns:
        dict: A dictionary containing the retrieved profile data including the profile name, followers, likes, posts, profile picture, bio text, external URL.
    """
    profile_data = {}
    url = f"https://www.snapchat.com/add/{username}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    # proxies = {
    #     "http": "http://10.10.1.10:3128",
    #     "https": "http://10.10.1.10:1080",
    # }

    # r = requests.get(url, headers=headers, proxies=proxies)
    r = requests.get(url, headers=headers, timeout=30)

    if r.status_code != 200:
        # ic("From SnapChat: ", r.status_code)
        profile_data["username"] = username
        profile_data["platform"] = "سناب شات"
        profile_data["error"] = "إسم المستخدم غير موجود على هذه المنصة"
        return profile_data

    # Parse HTML content
    soup = BeautifulSoup(r.text, "html.parser")

    #for debugging only
    with open("debug_snapchat.html", "w", encoding="utf-8") as f:
            f.write(str(soup))


    profile_section = soup.find("div", class_=lambda x: x and "PublicProfileCard_userDetailsContainer" in x)

    if profile_section is None:
        # ic("From SnapChat: ", "Profile Section is None")
        profile_data["username"] = username
        profile_data["platform"] = "سناب شات"
        profile_data["error"] = "خطأ أثناء قراءة البيانات من المنصة"
        return profile_data

    # Extract profile details
    obj=profile_section.find("span", class_=lambda x: x and "PublicProfileDetailsCard_displayNameText" in x)
    profile_name = obj.text.strip() if obj else ""
    obj=profile_section.find("div", class_=lambda x: x and "SubscriberText" in x)
    follower_count = obj.text.strip() if obj else "0"
    obj=soup.find("div", class_=lambda x: x and "PublicProfileCard_" in x and "Title" in x)
    subtitle = obj.text.strip() if obj else ""
    obj = soup.find("a", class_=lambda x: x and "PublicProfileCard_" in x and "Detail" in x)
    subtitle_line2 = obj.text.strip() if obj else ""
    obj: Tag | NavigableString | None = soup.find("picture", class_=lambda x: x and "ProfilePictureBubble_webPImage" in x)
    profile_image = obj.find("img")["srcset"] if obj else ""

    profile_data: dict = {
        # "username": username,
        # "platform": "SnapChat",
        "public_profile_name": profile_name,
        "followers": format_numbers_snapchat(follower_count),
        "likes": 0,
        "posts": 0,
        "profile_picture": profile_image,
        "bio_text": subtitle+'\n'+subtitle_line2,
        # "address": address,
        "external_url": url,
        # "platform_id": platform_id,
        # "time_taken": duration.total_seconds(),
    }
    return profile_data


def snapchat_old2(username: str) -> dict:
    """
    Retrieves Snapchat profile data for a given username.

    Args:
        username (str): The Snapchat username to retrieve profile data for.

    Returns:
        dict: A dictionary containing the retrieved profile data including the profile name, followers, likes, posts, profile picture, bio text, external URL.
    """
    profile_data = {}
    url = f"https://www.snapchat.com/add/{username}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    # proxies = {
    #     "http": "http://10.10.1.10:3128",
    #     "https": "http://10.10.1.10:1080",
    # }

    # r = requests.get(url, headers=headers, proxies=proxies)
    r = requests.get(url, headers=headers, timeout=30)

    if r.status_code != 200:
        # ic("From SnapChat: ", r.status_code)
        profile_data["username"] = username
        profile_data["platform"] = "سناب شات"
        profile_data["error"] = "إسم المستخدم غير موجود على هذه المنصة"
        return profile_data

    # Parse HTML content
    soup = BeautifulSoup(r.text, "html.parser")

    # # for debugging only
    # with open("debug_snapchat.html", "w", encoding="utf-8") as f:
    #     f.write(str(soup))

    profile_section = soup.find("meta", property="og:title") and soup.find("meta", property="og:url")

    if not profile_section:
        # ic("From SnapChat: ", "Profile Section is None")
        profile_data["username"] = username
        profile_data["platform"] = "سناب شات"
        profile_data["error"] = "خطأ أثناء قراءة البيانات من المنصة"
        return profile_data

    # Extract profile details
    subtitle = (
        soup.find("meta", property="og:title")["content"]
        if soup.find("meta", property="og:title")
        else None
    )
    url = (
        soup.find("meta", property="og:url")["content"]
        if soup.find("meta", property="og:url")
        else None
    )
    # profile_image = (
    #     soup.find("meta", property="og:image")["content"]
    #     if soup.find("meta", property="og:image")
    #     else None
    # )
    # subtitle_line2 = (
    #     soup.find("meta", property="og:description")["content"]
    #     if soup.find("meta", property="og:description")
    #     else None
    # )
    description_meta = soup.find("meta", {"name": "description"})
    subtitle_line2 = description_meta["content"] if description_meta else None

    # Extract JSON-LD structured data if available
    json_ld_data = soup.find("script", type="application/ld+json")
    if json_ld_data:
        json_content = json.loads(json_ld_data.string)
        profile_name = json_content.get("mainEntity", {}).get("name")
        profile_image = json_content.get("mainEntity", {}).get("image", None)
        # profile_data["address"] = json_content.get("mainEntity", {}).get("address")
        # profile_data["identifier"] = (
        #     json_content.get("mainEntity", {}).get("identifier", {}).get("value")
        # )
        follower_count = (
            json_content.get("mainEntity", {})
            .get("interactionStatistic", [])[0]
            .get("userInteractionCount")
        )



    profile_data: dict = {
        # "username": username,
        # "platform": "SnapChat",
        "public_profile_name": profile_name,
        "followers": follower_count,
        "likes": 0,
        "posts": 0,
        "profile_picture": profile_image,
        "bio_text": subtitle + "\n" + subtitle_line2,
        # "address": address,
        "external_url": url,
        # "platform_id": platform_id,
        # "time_taken": duration.total_seconds(),
    }

    # ic("From SnapChat: ", profile_data)

    return profile_data


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((TransientHTTPError, requests.exceptions.RequestException, TimeoutError)),
    retry_error_callback=return_error_dict
)
def snapchat(username: str) -> dict:
    """
    Retrieves Snapchat profile data for a given username.

    Args:
        username (str): The Snapchat username to retrieve profile data for.

    Returns:
        dict: A dictionary containing the retrieved profile data including the profile name, followers, likes, posts, profile picture, bio text, external URL.
    """
    user_data = {}
    profile_data = {
        "username": username,
        "platform": "سناب شات",
        "external_url": f"https://www.snapchat.com/add/{username}",
        "success": True,
        "error": None
    }

    url = "https://snapchat-scraper2.p.rapidapi.com/api/v1/users/detail"
    querystring = {"username":username}
    headers = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY_HERE"),
        "X-RapidAPI-Host": "snapchat-scraper2.p.rapidapi.com",
    }

    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    print(f"[DEBUG] snapchat - RAPIDAPI_KEY loaded: {rapidapi_key is not None}, Length: {len(rapidapi_key) if rapidapi_key else 0}")
    print(f"[DEBUG] snapchat - Calling RapidAPI endpoint {url} with username={username}")

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
    except Exception as e:
        print(f"[DEBUG] snapchat - requests.get threw exception: {e}")
        return {"success": False, "error": f"خطأ أثناء قراءة البيانات من المنصة: {str(e)}"}
    
    if response.status_code == 429:
        return {"success": False, "error": "Rate limit exceeded (HTTP 429). Please try again later."}
        
    if response.status_code != 200:
        print(f"[DEBUG] snapchat - RapidAPI request failed! Status: {response.status_code}")
        ic("From Snapchat: ",response.status_code)
        if response.status_code in [500, 502, 503, 504]:
            raise TransientHTTPError(f"HTTP {response.status_code}")
        return {"success": False, "error": "فشل في استرجاع البيانات من المنصة"}

    json_data = response.json()

    user_profile = json_data.get("data", {}).get("props", {}).get("pageProps", {}).get("userProfile", {})
    if user_profile and user_profile.get("$case") == "publicProfileInfo" and "publicProfileInfo" in user_profile:
        user_data = user_profile.get("publicProfileInfo", {})
    else:
        ic("From Snapchat: ", "User's profile not found!")
        return {"success": False, "error": "ملف المستخدم غير موجود أو خاص"}

    if not user_data:
        return {"success": False, "error": "ملف المستخدم غير موجود أو خاص"}

    # ic(
    #     user_data.get("title", ""),
    #     user_data.get("subscriberCount", "0"),
    #     user_data.get("profilePictureUrl", ""),
    #     user_data.get("bio", ""),
    #     user_data.get("websiteUrl", ""),
    #     user_data.get("snapchatCanonicalUrl", ""),
    # )

    # Retrieve profile details
    profile_data.update({
        "public_profile_name": user_data.get("title", ""),
        "followers": int(user_data.get("subscriberCount", "0") or 0),
        "likes": 0,
        "posts": 0,
        "profile_picture": user_data.get("profilePictureUrl", ""),
        "bio_text": user_data.get("bio", "")
        + "\n"
        + user_data.get("websiteUrl", "")
    })

    return profile_data

#////////////////////////////////////////////////////////////////////////////////////////

def instagram_old(username: str) -> dict:
    """
    Retrieves Instagram profile data for a given user.

    Args:
        username (str): The username of the Instagram account to retrieve data for.

    Returns:
        dict: A dictionary containing the profile data of the Instagram account. The dictionary has the following keys:
            - "public_profile_name" (str): The full name of the Instagram account.
            - "followers" (int): The number of followers the Instagram account has.
            - "likes" (int): The number of likes the Instagram account has.
            - "posts" (int): The number of posts the Instagram account has.
            - "profile_picture" (str): The URL of the Instagram account's profile picture.
            - "bio_text" (str): The biography text of the Instagram account.
            - "external_url" (str): The external URL of the Instagram account.
            If the Instagram account does not exist or there is an error, the dictionary will contain the following key:
            - "error" (str): An error message indicating that the Instagram account does not exist or there was an error.
    """
    profile_data = {}

    # url = "https://instagram-scraper-2022.p.rapidapi.com/ig/info_username/"
    # querystring = {"user": username}
    # headers = {
    #     "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY_HERE"),
    #     "X-RapidAPI-Host": "instagram-scraper-2022.p.rapidapi.com",
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    # }

    url = "https://instagram-scraper-api2.p.rapidapi.com/v1/info"
    querystring = {"username_or_id_or_url":username,"include_about":"false","url_embed_safe":"true"}
    headers = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY_HERE"),
        "X-RapidAPI-Host": "instagram-scraper-api2.p.rapidapi.com",
        # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    response = requests.get(url, headers=headers, params=querystring, timeout=30)
    json_data = response.json()

    # if json_data.get("status","") != "ok" or json_data.get("answer","") == "bad" or response.status_code != 200:
    if response.status_code != 200:
        # ic("From Instagram: ",response.status_code)
        profile_data["username"] = username
        profile_data["platform"] = "إنستاجرام"
        profile_data["error"] = "إسم المستخدم غير موجود على هذه المنصة"
        # ic("From Instagram: ", json_data)
        return profile_data


    # user_data = json_data["user"]
    # ic(user_data)
    user_data = json_data["data"]

    # ic(
    #     user_data["username"],
    #     user_data["full_name"],
    #     user_data["biography"],
    #     user_data["follower_count"],
    #     user_data["hd_profile_pic_url_info"]["url"],
    #     user_data["hd_profile_pic_versions"][0]["url"],
    #     user_data["hd_profile_pic_versions"][1]["url"],
    #     user_data["profile_pic_url"],
    #     user_data["external_url"],
    #     user_data["contact_phone_number"],
    #     user_data["city_name"],
    #     user_data["page_name"],
    # )

    # Retrieve profile details
    profile_data: dict = {
        # "username": profile.username,
        # "platform": "Instagram",
        "public_profile_name": user_data.get("full_name", ""),
        "followers": user_data.get("follower_count", "0"),
        "likes": 0,
        "posts": user_data.get("media_count", "0"),
        "profile_picture": user_data.get("profile_pic_url", ""),
        # download_profile_image_instagram(user_data["profile_pic_url"]),
        "bio_text": user_data.get("biography", "")
        + "\n"
        + user_data.get("external_url", ""),
        "external_url": f"https://www.instagram.com/{username}/",
        # "time_taken": duration.total_seconds(),
        # "platform_id": platform_id,
    }

    return profile_data

def instagram_old2(username: str) -> dict:
    """
    Retrieves Instagram profile data for a given user.

    Args:
        username (str): The username of the Instagram account to retrieve data for.

    Returns:
        dict: A dictionary containing the profile data of the Instagram account. The dictionary has the following keys:
            - "public_profile_name" (str): The full name of the Instagram account.
            - "followers" (int): The number of followers the Instagram account has.
            - "likes" (int): The number of likes the Instagram account has.
            - "posts" (int): The number of posts the Instagram account has.
            - "profile_picture" (str): The URL of the Instagram account's profile picture.
            - "bio_text" (str): The biography text of the Instagram account.
            - "external_url" (str): The external URL of the Instagram account.
            If the Instagram account does not exist or there is an error, the dictionary will contain the following key:
            - "error" (str): An error message indicating that the Instagram account does not exist or there was an error.
    """
    profile_data = {}

    # url = "https://instagram-scraper-2022.p.rapidapi.com/ig/info_username/"
    # querystring = {"user": username}
    # headers = {
    #     "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY_HERE"),
    #     "X-RapidAPI-Host": "instagram-scraper-2022.p.rapidapi.com",
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    # }

    url = "https://mediafy-api.p.rapidapi.com/v1/info"
    querystring = {"username_or_id_or_url":username,"include_about":"false","url_embed_safe":"true"}
    headers = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY_HERE"),
        "X-RapidAPI-Host": "mediafy-api.p.rapidapi.com",
        # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    response = requests.get(url, headers=headers, params=querystring, timeout=30)
    json_data = response.json()

    # if json_data.get("status","") != "ok" or json_data.get("answer","") == "bad" or response.status_code != 200:
    if response.status_code != 200:
        # ic("From Instagram: ",response.status_code)
        profile_data["username"] = username
        profile_data["platform"] = "إنستاجرام"
        profile_data["error"] = "إسم المستخدم غير موجود على هذه المنصة"
        # ic("From Instagram: ", json_data)
        return profile_data


    # user_data = json_data["user"]
    # ic(user_data)
    user_data = json_data["data"]

    # ic(
    #     user_data["username"],
    #     user_data["full_name"],
    #     user_data["biography"],
    #     user_data["follower_count"],
    #     user_data["hd_profile_pic_url_info"]["url"],
    #     user_data["hd_profile_pic_versions"][0]["url"],
    #     user_data["hd_profile_pic_versions"][1]["url"],
    #     user_data["profile_pic_url"],
    #     user_data["external_url"],
    #     user_data["contact_phone_number"],
    #     user_data["city_name"],
    #     user_data["page_name"],
    # )

    # Retrieve profile details
    profile_data: dict = {
        # "username": profile.username,
        # "platform": "Instagram",
        "public_profile_name": user_data.get("full_name", ""),
        "followers": user_data.get("follower_count", "0"),
        "likes": 0,
        "posts": user_data.get("media_count", "0"),
        "profile_picture": user_data.get("profile_pic_url", ""),
        # download_profile_image_instagram(user_data["profile_pic_url"]),
        "bio_text": user_data.get("biography", "")
        + "\n"
        + user_data.get("external_url", ""),
        "external_url": f"https://www.instagram.com/{username}/",
        # "time_taken": duration.total_seconds(),
        # "platform_id": platform_id,
    }

    return profile_data

#def instagram(username: str) -> dict:
#    """
#    Retrieves Instagram profile data for a given user using the Instagram Looter API.
#
#    Args:
#        username (str): The username of the Instagram account to retrieve data for.
#
#    Returns:
#        dict: A dictionary containing the profile data of the Instagram account. The dictionary has the following keys:
#            - "public_profile_name" (str): The full name of the Instagram account.
#            - "followers" (int): The number of followers the Instagram account has.
#            - "likes" (int): The number of likes the Instagram account has.
#            - "posts" (int): The number of posts the Instagram account has.
#            - "profile_picture" (str): The URL of the Instagram account's profile picture.
#            - "bio_text" (str): The biography text of the Instagram account.
#            - "external_url" (str): The external URL of the Instagram account.
#            If the Instagram account does not exist or there is an error, the dictionary will contain the following key:
#            - "error" (str): An error message indicating that the Instagram account does not exist or there is an error.
#    """
#    profile_data = {
#        "username": username,
#        "platform": "إنستاجرام",
#        "external_url": f"https://www.instagram.com/{username}/"
#    }
#
#    try:
#        # Use http.client to connect to the RapidAPI endpoint
#        import http.client
#        import json
#
#        # Set up the connection
#        conn = http.client.HTTPSConnection("instagram-looter2.p.rapidapi.com")
#
#        # Define headers with API key
#        headers = {
#            'x-rapidapi-key': os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY_HERE"),
#            'x-rapidapi-host': "instagram-looter2.p.rapidapi.com"
#        }
#
#        # Make the request
#        conn.request("GET", f"/profile2?username={username}", headers=headers)
#
#        # Get the response
#        response = conn.getresponse()
#
#        # Check if the request was successful
#        if response.status != 200:
#            ic(f"From Instagram API: Status code {response.status}")
#            profile_data["error"] = "فشل في استرجاع البيانات من المنصة"
#            return profile_data
#
#        # Read and parse the response data
#        data = response.read()
#        json_data = json.loads(data.decode("utf-8"))
#
#        # Check if the response indicates success
#        if not json_data.get("status", False):
#            ic("From Instagram API: Status is False")
#            profile_data["error"] = "إسم المستخدم غير موجود على هذه المنصة"
#            return profile_data
#
#        # Verify that the returned username matches the requested username
#        returned_username = json_data.get("username", "").lower()
#        if returned_username != username.lower():
#            ic(f"From Instagram API: Username mismatch - requested: {username}, returned: {returned_username}")
#            profile_data["error"] = "إسم المستخدم غير موجود على هذه المنصة"
#            return profile_data
#
#        # Populate profile data
#        profile_data.update({
#            "public_profile_name": json_data.get("full_name", ""),
#            "followers": json_data.get("follower_count", 0),
#            "likes": 0,  # Instagram doesn't provide a total likes count
#            "posts": json_data.get("media_count", 0),
#            "profile_picture": json_data.get("profile_pic_url", ""),
#            "bio_text": json_data.get("biography", "") +
#                        ("\n" + json_data.get("external_url", "") if json_data.get("external_url") else "")
#        })
#
#        # Close the connection
#        conn.close()
#
#    except Exception as e:
#        ic(f"Error in Instagram API: {str(e)}")
#        profile_data["error"] = f"خطأ أثناء قراءة البيانات من المنصة: {str(e)}"
#
#    return profile_data

# ////////////////////////////////////////////////////////////////////////////////////////

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception_type((TransientHTTPError, requests.exceptions.RequestException, TimeoutError)),
    retry_error_callback=return_error_dict
)
def instagram(username: str) -> dict:
    """
    Retrieves Instagram profile data for a given user using the new Instagram Scraper AI API.

    Args:
        username (str): The username of the Instagram account to retrieve data for.

    Returns:
        dict: A dictionary containing the profile data of the Instagram account. The dictionary has the following keys:
            - "public_profile_name" (str): The full name of the Instagram account.
            - "followers" (int): The number of followers the Instagram account has.
            - "likes" (int): The number of likes the Instagram account has.
            - "posts" (int): The number of posts the Instagram account has.
            - "profile_picture" (str): The URL of the Instagram account's profile picture.
            - "bio_text" (str): The biography text of the Instagram account.
            - "external_url" (str): The external URL of the Instagram account.
            If the Instagram account does not exist or there is an error, the dictionary will contain the following key:
            - "error" (str): An error message indicating that the Instagram account does not exist or there is an error.
    """
    user_data = {}
    profile_data = {
        "username": username,
        "platform": "إنستاجرام",
        "external_url": f"https://www.instagram.com/{username}/",
        "success": True,
        "error": None
    }

    try:
        url = "https://instagram-statistics-api.p.rapidapi.com/community"
        profile_url = f"https://www.instagram.com/{username}/"
        payload = {"url": profile_url}
        
        rapidapi_key = os.getenv("RAPIDAPI_KEY")
        print(f"[DEBUG] instagram - RAPIDAPI_KEY loaded: {rapidapi_key is not None}, Length: {len(rapidapi_key) if rapidapi_key else 0}")
        
        headers = {
            "x-rapidapi-key": rapidapi_key or "YOUR_RAPIDAPI_KEY_HERE",
            "x-rapidapi-host": "instagram-statistics-api.p.rapidapi.com",
            "Content-Type": "application/json"
        }

        print(f"[DEBUG] instagram - Calling RapidAPI endpoint {url} with params={payload}")
        response = requests.get(url, params=payload, headers=headers)

        print(f"[DEBUG] instagram - RapidAPI Status Code: {response.status_code}")
        if response.status_code == 429:
            return {"success": False, "error": "Rate limit exceeded (HTTP 429). Please try again later."}

        if response.status_code != 200:
            print(f"[DEBUG] instagram - RapidAPI request failed! Status: {response.status_code}")
            ic(f"From Instagram API: Status code {response.status_code}")
            if response.status_code in [500, 502, 503, 504]:
                raise TransientHTTPError(f"HTTP {response.status_code}")
            return {"success": False, "error": "فشل في استرجاع البيانات من المنصة"}

        res_json = response.json()

        if 'data' not in res_json:
            print(f"[DEBUG] instagram - 'data' key missing in JSON: {res_json}")
            ic("From Instagram API: User not found")
            return {"success": False, "error": "إسم المستخدم غير موجود على هذه المنصة"}

        user_data = res_json.get('data', {})

        # Populate profile data
        profile_data.update({
            "public_profile_name": user_data.get("name", ""),
            "followers": user_data.get("usersCount", 0),
            "likes": 0,
            "posts": 0,
            "profile_picture": user_data.get("image", ""),
            "bio_text": "",
            "is_verified": user_data.get("verified", False)
        })

    except (TransientHTTPError, requests.exceptions.RequestException, TimeoutError) as e:
        print(f"[DEBUG] instagram - TransientHTTPError: {e}")
        raise e
    except Exception as e:
        print(f"[DEBUG] instagram - Exception: {e}")
        ic(f"Error in Instagram API: {str(e)}")
        return {"success": False, "error": f"خطأ أثناء قراءة البيانات من المنصة: {str(e)}"}

    return profile_data

# ////////////////////////////////////////////////////////////////////////////////////////

def format_numbers_snapchat(follower_count_str):
    """
    Format the follower count string for Snapchat.

    Parameters:
        follower_count_str (str): The follower count string from Snapchat.

    Returns:
        int: The formatted follower count.

    This function takes a follower count string from Snapchat and removes any unnecessary characters. It then converts the string to an integer based on the suffix ('m' for millions, 'k' for thousands) and returns the formatted follower count.

    Example:
        >>> format_numbers_snapchat("1.2m")
        1200000

        >>> format_numbers_snapchat("100k")
        100000

        >>> format_numbers_snapchat("12345")
        12345
    """
    try:
        # Remove ' Subscribers' from the string
        follower_count_str = follower_count_str.split(' ')[0]
        # Remove commas from the string
        if follower_count_str.endswith('m'):
            return int(float(follower_count_str[:-1]) * 1_000_000)
        elif follower_count_str.endswith('k'):
            return int(float(follower_count_str[:-1]) * 1_000)
        else:
            return int(follower_count_str)
    except:
        return 0


def download_profile_image_instagram(image_url):
    """
    Downloads the profile image from the provided image URL, saves it in the static folder, and returns the URL for the saved image.

    Args:
        image_url (str): The URL of the image to download.

    Returns:
        str: The URL for the saved profile picture.
    """
    response = requests.get(image_url)
    upload_folder = path.join(current_app.root_path, "static", "profile_pictures")
    if not path.exists(upload_folder):
        makedirs(upload_folder)
    new_filename = secure_filename(f"temp_insta_profile_image.jpg")
    filepath = path.join(upload_folder, new_filename)
    with open(filepath, "wb") as f:
        f.write(response.content)
    profile_picture_url=url_for("static", filename="profile_pictures/" + new_filename)
    return profile_picture_url  # Return the path to the downloaded image

# ////////////////////////////////////////////////////////////////////////////////////////

def get_summerized_report()->dict:
    """
    Generates a summary report of various statistics from the database.

    Returns:
        dict: A dictionary containing the following statistics:
            - total_users (int): The total number of users in the database.
            - total_profiles (int): The total number of profiles in the database.
            - total_accounts (int): The total number of accounts in the database.
            - total_scans (int): The total number of scans in the database.
            - last_scan_date (datetime.date or None): The date of the last scan in the database, or None if no scans exist.
            - last_scan_time (datetime.time or None): The time of the last scan in the database, or None if no scans exist.
            - platforms (list of tuples): A list of tuples containing the name of each platform and the count of scans for that platform.
            - random_pictures (list of str): A list of filenames of randomly selected pictures from the "profile_pictures" folder.
    """
    # Make sure we're using the latest data
    from flask import current_app

    # Get pictures for the profile showcase
    pictures_folder = path.join(current_app.root_path, "static", "profile_pictures")
    pictures = [f for f in listdir(pictures_folder) if isfile(path.join(pictures_folder, f))]

    # Get the latest scan log
    last_scan = ScanLog.query.order_by(ScanLog.creation_date.desc(), ScanLog.creation_time.desc()).first()

    # Get all platforms and count accounts for each
    platforms = Platform.query.all()

    # Use a direct count query for each platform to ensure accuracy
    platform_counts = []
    for platform in platforms:
        count = SocialAccount.query.filter_by(platform_id=platform.id).count()
        platform_counts.append((platform.name, count))

    # Get total counts with direct queries
    total_users = Users.query.count()
    total_profiles = Influencer.query.count()
    total_accounts = SocialAccount.query.count()
    total_scans = ScanLog.query.count()

    # Build the report dictionary
    report = {
        "total_users": total_users,
        "total_profiles": total_profiles,
        "total_accounts": total_accounts,
        "accounts_per_platform": platform_counts,
        "total_scans": total_scans,
        "last_scan_date": last_scan.creation_date if last_scan else None,
        "last_scan_time": last_scan.creation_time if last_scan else None,
        "last_scan_duration": last_scan.time_taken if last_scan else None,
        "platforms": platform_counts,
        "random_pictures": random.sample(pictures, min(10, len(pictures))) if pictures else [],
    }

    # Log the counts for debugging
    ic(f"Report generated - Total accounts: {total_accounts}")
    for platform_name, count in platform_counts:
        ic(f"  - {platform_name}: {count}")

    return report

# ////////////////////////////////////////////////////////////////////////////////////////


def generate_recommendations(campaign_id):
    """
    Generates tailored influencer recommendations based on the Campaign DNA.
    Returns a sanitized list containing only standard stats and a composite match_score (0-100%).
    Raw metrics (Virality, Jaccard, Community Fit) remain strictly in the backend.
    
    Optimized: Uses batch JOIN queries instead of N+1 per-influencer loops.
    """
    from apps import db
    from apps.saas.models import Campaign, shortlist_influencer
    from apps.profiles.models import Influencer
    from apps.social.models import SocialPost, SocialAccount, Platform
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload
    import json
    import datetime

    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return []

    # Parse Campaign DNA
    target_platform = (campaign.target_platform or 'all').lower()
    objective = (campaign.objective or '').lower()
    
    import re
    
    # Process Keywords
    C_words = set(re.findall(r'\w+', str(campaign.keywords).lower())) if campaign.keywords else set()
    
    # Get influencers already in the campaign's shortlist
    from apps.saas.models import Shortlist
    campaign_shortlist = Shortlist.query.filter_by(campaign_id=campaign_id).first()
    shortlisted_influencer_ids = set()
    if campaign_shortlist:
        shortlisted_influencer_ids = {inf.id for inf in campaign_shortlist.influencers}

    # --- BATCH QUERY 1: Load all influencers with their socialaccounts eagerly ---
    influencers = Influencer.query.options(
        joinedload(Influencer.socialaccounts).joinedload(SocialAccount.platform)
    ).all()
    
    # Filter out already shortlisted influencers
    influencers = [inf for inf in influencers if inf.id not in shortlisted_influencer_ids]
    
    if not influencers:
        return []
    
    # --- BATCH QUERY 2: Trending counts (all at once) ---
    trending_counts = db.session.query(
        shortlist_influencer.c.influencer_id,
        func.count(shortlist_influencer.c.shortlist_id).label('count')
    ).group_by(shortlist_influencer.c.influencer_id).all()
    trending_map = {row.influencer_id: row.count for row in trending_counts}

    # --- BATCH QUERY 3: Aggregate post metrics per socialaccount_id ---
    # This replaces the N+1 SocialPost.query.filter_by(influencer_id=...) inside the loop
    post_stats = db.session.query(
        SocialPost.socialaccount_id,
        func.sum(SocialPost.plays).label('total_plays'),
        func.sum(SocialPost.likes).label('total_likes'),
        func.sum(SocialPost.comments).label('total_comments'),
        func.sum(SocialPost.shares).label('total_shares'),
        func.sum(SocialPost.saves).label('total_saves'),
        func.count(SocialPost.id).label('post_count')
    ).group_by(SocialPost.socialaccount_id).all()
    
    post_stats_map = {}
    for row in post_stats:
        post_stats_map[row.socialaccount_id] = {
            'total_plays': row.total_plays or 0,
            'total_likes': row.total_likes or 0,
            'total_comments': row.total_comments or 0,
            'total_shares': row.total_shares or 0,
            'total_saves': row.total_saves or 0,
            'post_count': row.post_count or 0,
        }

    # --- BATCH QUERY 4: Captions for Jaccard text matching (batched) ---
    caption_rows = db.session.query(
        SocialPost.influencer_id,
        SocialPost.caption
    ).filter(SocialPost.caption.isnot(None)).all()
    
    caption_map = {}
    for row in caption_rows:
        caption_map.setdefault(row.influencer_id, []).append(row.caption.lower())
    
    # --- BATCH QUERY 5: Recent snap velocity (last 30 days) ---
    thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    snap_velocity_rows = db.session.query(
        SocialPost.socialaccount_id,
        func.count(SocialPost.id).label('recent_count')
    ).filter(
        SocialPost.posted_at >= thirty_days_ago
    ).group_by(SocialPost.socialaccount_id).all()
    
    snap_velocity_map = {row.socialaccount_id: row.recent_count for row in snap_velocity_rows}

    scored_influencers = []

    for inf in influencers:
        text_corpus = ""
        
        # 1. Filter by Target Platform
        valid_platform = True if target_platform == 'all' else False
        
        tiktok_account_ids = []
        ig_account_ids = []
        snap_account_ids = []
        
        for acc in inf.socialaccounts:
            platform_name = (acc.platform.name_english.lower().strip() if acc.platform else '').lower()
            
            if acc.bio_text:
                text_corpus += acc.bio_text.lower() + " "
            
            if platform_name == target_platform:
                valid_platform = True
            
            if platform_name == 'tiktok':
                tiktok_account_ids.append(acc.id)
            elif platform_name == 'instagram':
                ig_account_ids.append(acc.id)
            elif platform_name == 'snapchat':
                snap_account_ids.append(acc.id)
                
        if not valid_platform and target_platform != 'all':
            continue

        # Add captions to text corpus from pre-fetched map
        for caption in caption_map.get(inf.id, []):
            text_corpus += caption + " "
                
        import math
        
        # 1. Overlap Coefficient Niche Match
        I_words = set(re.findall(r'\w+', text_corpus.lower()))
        
        if not C_words:
            score_niche = 1.0  # Neutral multiplier if no keywords provided
        else:
            overlap = len(C_words.intersection(I_words))
            score_niche = max(overlap / min(len(C_words), len(I_words)) if I_words else 0.0, 0.10)

        # Pre-compute total followers for Scale Score
        total_followers = sum([acc.followers for acc in inf.socialaccounts if acc.followers])
        
        # 2. Platform-Aware Objective Scoring
        score_objective = 0.0
        
        for acc in inf.socialaccounts:
            platform_name = (acc.platform.name_english.lower().strip() if acc.platform else '').lower()
            stats = post_stats_map.get(acc.id, {})
            
            total_plays = stats.get('total_plays', 0) or 1
            total_likes = stats.get('total_likes', 0) or 0
            total_comments = stats.get('total_comments', 0) or 0
            total_shares = stats.get('total_shares', 0) or 0
            total_saves = stats.get('total_saves', 0) or 0
            
            acc_followers = acc.followers or 1
            post_count = stats.get('post_count', 0) or 1
            
            # Universal Engagement Rate
            rate_engagement = (total_likes + total_comments) / acc_followers
            community_fit = min(rate_engagement / 0.20, 1.0)
            
            acc_score_obj = 0.0
            
            if platform_name == 'tiktok':
                rate_virality = total_shares / total_plays if total_plays > 1 else 0
                virality_index = min(rate_virality / 0.05, 1.0)
                
                rate_intent = total_saves / total_plays if total_plays > 1 else 0
                purchase_intent = min(rate_intent / 0.05, 1.0)
                
                if objective == 'brand awareness':
                    acc_score_obj = (virality_index * 0.7) + (community_fit * 0.3)
                elif objective == 'direct conversions':
                    acc_score_obj = (purchase_intent * 0.7) + (community_fit * 0.3)
                elif objective == 'community engagement':
                    acc_score_obj = (community_fit * 0.8) + (virality_index * 0.2)
                else:
                    acc_score_obj = (virality_index * 0.33) + (community_fit * 0.33) + (purchase_intent * 0.33)
            else:
                # Instagram/Snapchat: Degrade gracefully to rely on Engagement & Views
                avg_views = total_plays / post_count
                views_fit = min(avg_views / 1000000.0, 1.0) # Caps at 1M average views
                
                if objective == 'brand awareness':
                    acc_score_obj = (views_fit * 0.6) + (community_fit * 0.4)
                elif objective == 'direct conversions':
                    acc_score_obj = community_fit
                elif objective == 'community engagement':
                    acc_score_obj = community_fit
                else:
                    acc_score_obj = (views_fit * 0.5) + (community_fit * 0.5)
            
            score_objective = max(score_objective, acc_score_obj)

        # 3. Final Multiplicative Score Assembly
        score_scale = min(math.log10(total_followers + 1) / 9.0, 1.0)
        
        w_obj = 0.7
        w_scale = 0.3
        
        # New Multiplicative Formula with hard niche multiplier
        composite_score = score_niche * ((w_obj * score_objective) + (w_scale * score_scale))
        final_match_score = composite_score * 100

        # Apply Trending Bonus (Up to 10 extra points)
        if trending_map.get(inf.id, 0) >= 2:
            final_match_score += 10
            
        # Cap Score at 99.9%
        final_match_score = min(99.9, final_match_score)

        # Step 3: Append unconditionally without hard drops
        primary_platform = inf.socialaccounts[0].platform.name.lower() if inf.socialaccounts and inf.socialaccounts[0].platform else 'unknown'
        username = inf.socialaccounts[0].username if inf.socialaccounts else inf.full_name
        
        scored_influencers.append({
                'id': inf.id,
                'full_name': inf.full_name,
                'username': username,
                'profile_picture': inf.profile_picture,
                'total_followers': total_followers,
                'match_score': round(final_match_score, 1),
                'primary_platform': primary_platform
            })

    # Sort by score descending and return Top 5
    scored_influencers.sort(key=lambda x: x['match_score'], reverse=True)
    return scored_influencers[:5]


