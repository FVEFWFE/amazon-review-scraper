"""
Oxylabs source adapter for scraping Amazon reviews via API.
"""

import logging
from typing import AsyncGenerator, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from amazon_review_scraper.config import settings
from amazon_review_scraper.models import Review
from amazon_review_scraper.sources.base import ReviewSource

logger = logging.getLogger(__name__)


class OxylabsSource(ReviewSource):
    """Oxylabs source adapter using their API for reliable scraping."""
    
    def __init__(self):
        if not settings.has_oxylabs_credentials:
            raise ValueError("Oxylabs credentials not configured")
        
        self.client = httpx.AsyncClient(
            timeout=60.0,
            auth=(settings.OXYSCRAPER_AUTH_USER, settings.OXYSCRAPER_AUTH_PASS),
        )
    
    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=1, max=10),
    )
    async def _fetch_page(self, asin: str, domain: str, page: int) -> dict:
        """Fetch a page of reviews from Oxylabs API."""
        url = settings.get_reviews_url(asin, domain, page)
        
        payload = {
            "source": "amazon",
            "url": url,
            "parse": True,
            "context": [
                {"key": "autoparse", "value": True},
            ],
        }
        
        response = await self.client.post(
            settings.OXYSCRAPER_BASE_URL,
            json=payload,
        )
        response.raise_for_status()
        
        return response.json()
    
    def _parse_review(self, review_data: dict, asin: str, domain: str) -> Optional[Review]:
        """Parse review data from Oxylabs response."""
        try:
            # Oxylabs returns parsed data in a structured format
            review_id = review_data.get("id", "")
            if not review_id:
                # Generate ID from other fields
                import hashlib
                content = f"{review_data.get('author', '')}{review_data.get('title', '')}"
                review_id = f"R{hashlib.md5(content.encode()).hexdigest()[:10].upper()}"
            
            return Review(
                id=review_id,
                asin=asin,
                domain=domain,
                author=review_data.get("author", "Anonymous"),
                title=review_data.get("title", ""),
                content=review_data.get("content", ""),
                rating=float(review_data.get("rating", 0)),
                is_verified=review_data.get("verified_purchase", False),
                product_attributes=review_data.get("product_variant"),
                timestamp_text=review_data.get("date", ""),
            )
        except Exception as e:
            logger.warning(f"Failed to parse Oxylabs review: {e}")
            return None
    
    async def fetch_reviews(
        self,
        asin: str,
        domain: str = "com",
        max_pages: Optional[int] = None,
        start_page: int = 1,
    ) -> AsyncGenerator[Review, None]:
        """Fetch reviews from Amazon using Oxylabs API."""
        max_pages = max_pages or settings.MAX_PAGES_OXYLABS
        
        for page_num in range(start_page, start_page + max_pages):
            try:
                logger.info(f"Fetching page {page_num} via Oxylabs for {asin}")
                
                response_data = await self._fetch_page(asin, domain, page_num)
                
                # Check if we have results
                results = response_data.get("results", [])
                if not results:
                    logger.info("No results from Oxylabs")
                    break
                
                # Extract reviews from the first result
                result = results[0]
                content = result.get("content", {})
                
                # Handle different response structures
                reviews_data = []
                if "reviews" in content:
                    reviews_data = content["reviews"]
                elif "customer_reviews" in content:
                    reviews_data = content["customer_reviews"]
                elif isinstance(content, list):
                    reviews_data = content
                
                if not reviews_data:
                    logger.info(f"No more reviews found on page {page_num}")
                    break
                
                for review_data in reviews_data:
                    review = self._parse_review(review_data, asin, domain)
                    if review:
                        yield review
                
                # Check if there are more pages
                pagination = content.get("pagination", {})
                if not pagination.get("has_next", False):
                    logger.info("No more pages available")
                    break
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info(f"Product not found: {asin}")
                    break
                logger.error(f"HTTP error fetching page {page_num}: {e}")
                break
            except Exception as e:
                logger.error(f"Error fetching page {page_num}: {e}")
                break
    
    async def get_review_count(self, asin: str, domain: str = "com") -> Optional[int]:
        """Get the total number of reviews for a product."""
        try:
            response_data = await self._fetch_page(asin, domain, 1)
            
            results = response_data.get("results", [])
            if results:
                result = results[0]
                content = result.get("content", {})
                
                # Look for review count in various places
                if "total_reviews" in content:
                    return content["total_reviews"]
                elif "review_count" in content:
                    return content["review_count"]
                elif "summary" in content:
                    summary = content["summary"]
                    if isinstance(summary, dict) and "total_reviews" in summary:
                        return summary["total_reviews"]
                
        except Exception as e:
            logger.error(f"Error getting review count from Oxylabs: {e}")
        
        return None
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()