from abc import ABC, abstractmethod
import requests
from requests.exceptions import Timeout, RequestException
import logging

logger = logging.getLogger(__name__)

class BaseSocialScraper(ABC):
    """
    Abstract Base Class for all social media scrapers.
    Forces implementation of fetch_profile.
    """
    
    @abstractmethod
    def fetch_profile(self, username: str) -> dict:
        """
        Fetches the profile for a given username and returns a standardized dict.
        """
        pass
        
    def handle_http_error(self, platform_name: str, username: str, exception: Exception) -> dict:
        """
        Standardized error handling for all HTTP/network related exceptions.
        """
        logger.error(f"[SCRAPER ERROR] {platform_name} scraper failed for '{username}': {str(exception)}")
        
        error_msg = "فشل في استرجاع البيانات من المنصة"
        if isinstance(exception, Timeout):
            error_msg = "انتهت مهلة الاتصال بالمنصة"
            
        return {
            "username": username,
            "platform_name": platform_name,
            "error": error_msg
        }
