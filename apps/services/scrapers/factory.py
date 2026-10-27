from .base import BaseSocialScraper
from .implementations.instagram_apify import InstagramApifyScraper
from .implementations.tiktok_apify import TikTokApifyScraper
from .implementations.snapchat_scraper import SnapchatScraper

class ScraperFactory:
    """
    Factory for retrieving the appropriate social media scraper instance.
    """
    
    @staticmethod
    def get_scraper(platform: str, provider: str = 'default') -> BaseSocialScraper:
        platform = platform.lower()
        provider = provider.lower()
        
        if platform == 'instagram' and provider == 'apify':
            return InstagramApifyScraper()
            
        elif platform == 'tiktok' and provider == 'apify':
            return TikTokApifyScraper()
            
        elif platform == 'snapchat':
            return SnapchatScraper()
            
        # Fallbacks for testing
        elif platform == 'instagram':
            return InstagramApifyScraper()
        elif platform == 'tiktok':
            return TikTokApifyScraper()
            
        raise ValueError(f"No scraper implementation found for platform '{platform}' with provider '{provider}'")
