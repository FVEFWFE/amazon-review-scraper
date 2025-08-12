"""
Base class for review source adapters.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncGenerator, Optional

from amazon_review_scraper.models import Review


class SourceType(str, Enum):
    """Available source types."""
    
    FREE = "free"
    OXYLABS = "oxylabs"


class ReviewSource(ABC):
    """Abstract base class for review sources."""
    
    @abstractmethod
    async def fetch_reviews(
        self,
        asin: str,
        domain: str = "com",
        max_pages: Optional[int] = None,
        start_page: int = 1,
    ) -> AsyncGenerator[Review, None]:
        """
        Fetch reviews from the source.
        
        Args:
            asin: Amazon Standard Identification Number
            domain: Amazon marketplace domain
            max_pages: Maximum number of pages to fetch
            start_page: Starting page number
            
        Yields:
            Review objects
        """
        pass
    
    @abstractmethod
    async def get_review_count(self, asin: str, domain: str = "com") -> Optional[int]:
        """
        Get the total number of reviews for a product.
        
        Args:
            asin: Amazon Standard Identification Number
            domain: Amazon marketplace domain
            
        Returns:
            Total review count or None if unavailable
        """
        pass