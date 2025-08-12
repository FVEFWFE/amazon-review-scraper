"""
Free source adapter for scraping Amazon reviews using BeautifulSoup.
"""

import asyncio
import hashlib
import logging
import random
import re
from typing import AsyncGenerator, Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from amazon_review_scraper.config import settings
from amazon_review_scraper.models import Review
from amazon_review_scraper.sources.base import ReviewSource

logger = logging.getLogger(__name__)


class FreeSource(ReviewSource):
    """Free source adapter using direct HTTP requests with rate limiting."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=self._get_headers(),
        )
        self.rate_limiter = asyncio.Semaphore(1)  # Enforce sequential requests
        self.last_request_time = 0.0
        
    def _get_headers(self) -> dict:
        """Get randomized headers for requests."""
        user_agent = random.choice(settings.USER_AGENTS)
        return {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
    
    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        async with self.rate_limiter:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self.last_request_time
            min_interval = 1.0 / settings.RATE_LIMIT_RPS
            
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)
            
            self.last_request_time = asyncio.get_event_loop().time()
    
    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.RETRY_BACKOFF_SECONDS, min=2, max=30),
    )
    async def _fetch_page(self, url: str) -> str:
        """Fetch a page with retries and rate limiting."""
        await self._rate_limit()
        
        # Randomize headers for each request
        self.client.headers.update(self._get_headers())
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        # Add random delay to appear more human-like
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        return response.text
    
    def _parse_review(self, review_element, asin: str, domain: str) -> Optional[Review]:
        """Parse a single review element."""
        try:
            # Extract review ID
            review_id = review_element.get("id", "")
            if not review_id:
                # Try to find it in data attributes
                data_id = review_element.get("data-hook", "")
                if data_id:
                    review_id = data_id
                else:
                    # Generate a deterministic ID from content
                    content_hash = hashlib.md5(str(review_element).encode()).hexdigest()[:10]
                    review_id = f"R{content_hash.upper()}"
            
            # Extract author
            author_elem = review_element.find(class_="a-profile-name")
            author = author_elem.text.strip() if author_elem else "Anonymous"
            
            # Extract title
            title_elem = review_element.find("a", {"data-hook": "review-title"})
            if not title_elem:
                title_elem = review_element.find(class_="review-title-content")
                if title_elem:
                    title_elem = title_elem.find("span")
            title = title_elem.text.strip() if title_elem else ""
            
            # Extract content
            content_elem = review_element.find("span", {"data-hook": "review-body"})
            if not content_elem:
                content_elem = review_element.find(class_="review-text-content")
                if content_elem:
                    content_elem = content_elem.find("span")
            content = content_elem.text.strip() if content_elem else ""
            
            # Extract rating
            rating_elem = review_element.find("i", {"data-hook": "review-star-rating"})
            if not rating_elem:
                rating_elem = review_element.find(class_="review-rating")
            
            rating = 0.0
            if rating_elem:
                rating_text = rating_elem.get("class", [])
                if isinstance(rating_text, list):
                    for cls in rating_text:
                        if "a-star-" in cls:
                            rating_match = re.search(r"a-star-(\d)", cls)
                            if rating_match:
                                rating = float(rating_match.group(1))
                                break
                
                if rating == 0.0:
                    # Try alternative parsing
                    alt_text = rating_elem.text.strip()
                    rating_match = re.search(r"(\d+(?:\.\d+)?)\s*out of", alt_text)
                    if rating_match:
                        rating = float(rating_match.group(1))
            
            # Extract verified purchase
            verified_elem = review_element.find("span", {"data-hook": "avp-badge"})
            is_verified = bool(verified_elem and "Verified Purchase" in verified_elem.text)
            
            # Extract product attributes (size, color, etc.)
            attributes_elem = review_element.find("a", {"data-hook": "format-strip"})
            product_attributes = attributes_elem.text.strip() if attributes_elem else None
            
            # Extract timestamp
            date_elem = review_element.find("span", {"data-hook": "review-date"})
            timestamp_text = date_elem.text.strip() if date_elem else ""
            
            return Review(
                id=review_id,
                asin=asin,
                domain=domain,
                author=author,
                title=title,
                content=content,
                rating=rating,
                is_verified=is_verified,
                product_attributes=product_attributes,
                timestamp_text=timestamp_text,
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse review: {e}")
            return None
    
    async def fetch_reviews(
        self,
        asin: str,
        domain: str = "com",
        max_pages: Optional[int] = None,
        start_page: int = 1,
    ) -> AsyncGenerator[Review, None]:
        """Fetch reviews from Amazon using free scraping."""
        max_pages = max_pages or settings.MAX_PAGES_FREE
        
        for page_num in range(start_page, start_page + max_pages):
            try:
                url = settings.get_reviews_url(asin, domain, page_num)
                logger.info(f"Fetching page {page_num} from {url}")
                
                html = await self._fetch_page(url)
                soup = BeautifulSoup(html, "lxml")
                
                # Find review containers
                review_elements = soup.find_all("div", {"data-hook": "review"})
                if not review_elements:
                    # Try alternative selector
                    review_elements = soup.find_all("div", class_="review")
                
                if not review_elements:
                    logger.info(f"No more reviews found on page {page_num}")
                    break
                
                for review_elem in review_elements:
                    review = self._parse_review(review_elem, asin, domain)
                    if review:
                        yield review
                
                # Check if there's a next page
                next_button = soup.find("li", class_="a-last")
                if not next_button or "a-disabled" in next_button.get("class", []):
                    logger.info("No more pages available")
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching page {page_num}: {e}")
                break
    
    async def get_review_count(self, asin: str, domain: str = "com") -> Optional[int]:
        """Get the total number of reviews for a product."""
        try:
            url = settings.get_reviews_url(asin, domain, 1)
            html = await self._fetch_page(url)
            soup = BeautifulSoup(html, "lxml")
            
            # Look for review count in various places
            count_elem = soup.find("div", {"data-hook": "cr-filter-info-review-rating-count"})
            if count_elem:
                count_text = count_elem.text.strip()
                match = re.search(r"([\d,]+)\s*(?:global\s*)?(?:customer\s*)?reviews?", count_text, re.I)
                if match:
                    return int(match.group(1).replace(",", ""))
            
            # Alternative location
            count_elem = soup.find("span", {"data-hook": "total-review-count"})
            if count_elem:
                count_text = count_elem.text.strip()
                return int(count_text.replace(",", ""))
                
        except Exception as e:
            logger.error(f"Error getting review count: {e}")
        
        return None
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()