"""
Celery tasks for background scraping jobs.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from celery import Celery
from sqlalchemy.orm import Session

from amazon_review_scraper.config import settings
from amazon_review_scraper.database import SessionLocal, JobDB, ReviewDB, StatsCache
from amazon_review_scraper.models import Review
from amazon_review_scraper.sources import FreeSource, OxylabsSource, SourceType

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "amazon_review_scraper",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_time_limit=settings.TASK_TIME_LIMIT,
    task_soft_time_limit=settings.TASK_SOFT_TIME_LIMIT,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)


@celery_app.task(bind=True, name="scrape_reviews")
def scrape_reviews_task(
    self,
    asin: str,
    domain: str = "com",
    source: str = "free",
    job_id: Optional[str] = None,
) -> dict:
    """
    Background task to scrape reviews for a product.
    
    Args:
        asin: Amazon Standard Identification Number
        domain: Amazon marketplace domain
        source: Data source (free or oxylabs)
        job_id: Optional job ID (will be generated if not provided)
    
    Returns:
        Job result dictionary
    """
    import asyncio
    
    job_id = job_id or str(uuid.uuid4())
    db: Session = SessionLocal()
    
    try:
        # Create or update job record
        job = db.query(JobDB).filter(JobDB.job_id == job_id).first()
        if not job:
            job = JobDB(
                job_id=job_id,
                asin=asin,
                domain=domain,
                source=source,
                status="running",
                started_at=datetime.utcnow(),
            )
            db.add(job)
        else:
            job.status = "running"
            job.started_at = datetime.utcnow()
        
        db.commit()
        
        # Run the async scraping function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _scrape_reviews_async(db, job, asin, domain, source)
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error in scrape task: {e}")
        
        # Update job status
        if job:
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
        
        raise
    finally:
        db.close()


async def _scrape_reviews_async(
    db: Session,
    job: JobDB,
    asin: str,
    domain: str,
    source: str,
) -> dict:
    """Async function to scrape reviews."""
    
    # Initialize the appropriate source
    if source == SourceType.OXYLABS:
        if not settings.has_oxylabs_credentials:
            raise ValueError("Oxylabs credentials not configured")
        scraper = OxylabsSource()
    else:
        scraper = FreeSource()
    
    reviews_fetched = 0
    pages_processed = 0
    
    try:
        # Check for existing reviews to determine start page
        last_review = (
            db.query(ReviewDB)
            .filter(ReviewDB.asin == asin, ReviewDB.domain == domain)
            .order_by(ReviewDB.fetched_at.desc())
            .first()
        )
        
        start_page = 1
        existing_ids = set()
        
        if last_review:
            # Get all existing review IDs for deduplication
            existing_reviews = (
                db.query(ReviewDB.id)
                .filter(ReviewDB.asin == asin, ReviewDB.domain == domain)
                .all()
            )
            existing_ids = {r.id for r in existing_reviews}
        
        # Fetch reviews
        async for review in scraper.fetch_reviews(asin, domain, start_page=start_page):
            pages_processed = max(pages_processed, 1)
            
            # Skip if we already have this review
            if review.id in existing_ids:
                logger.info(f"Skipping duplicate review {review.id}")
                continue
            
            # Save review to database
            review_db = ReviewDB(
                id=review.id,
                asin=review.asin,
                domain=review.domain,
                author=review.author,
                title=review.title,
                content=review.content,
                rating=review.rating,
                is_verified=review.is_verified,
                product_attributes=review.product_attributes,
                timestamp_text=review.timestamp_text,
                fetched_at=datetime.utcnow(),
            )
            
            db.add(review_db)
            reviews_fetched += 1
            
            # Commit in batches
            if reviews_fetched % 10 == 0:
                db.commit()
                
                # Update job progress
                job.reviews_fetched = reviews_fetched
                job.pages_processed = pages_processed
                db.commit()
        
        # Final commit
        db.commit()
        
        # Update statistics cache
        await _update_stats_cache(db, asin, domain)
        
        # Mark job as completed
        job.status = "completed"
        job.reviews_fetched = reviews_fetched
        job.pages_processed = pages_processed
        job.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Scraping completed: {reviews_fetched} reviews from {pages_processed} pages")
        
        return {
            "job_id": job.job_id,
            "status": "completed",
            "reviews_fetched": reviews_fetched,
            "pages_processed": pages_processed,
        }
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        await scraper.close()


async def _update_stats_cache(db: Session, asin: str, domain: str):
    """Update the statistics cache for a product."""
    
    # Calculate statistics from reviews
    reviews = (
        db.query(ReviewDB)
        .filter(ReviewDB.asin == asin, ReviewDB.domain == domain)
        .all()
    )
    
    if not reviews:
        return
    
    review_count = len(reviews)
    total_rating = sum(r.rating for r in reviews)
    average_rating = total_rating / review_count if review_count > 0 else 0
    
    # Count ratings by star
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for review in reviews:
        rating_int = int(review.rating)
        if rating_int in rating_counts:
            rating_counts[rating_int] += 1
    
    # Get most recent review timestamp
    most_recent = max(reviews, key=lambda r: r.fetched_at)
    last_reviewed_text = most_recent.timestamp_text if most_recent else None
    
    # Update or create stats cache
    stats = (
        db.query(StatsCache)
        .filter(StatsCache.asin == asin, StatsCache.domain == domain)
        .first()
    )
    
    if stats:
        stats.review_count = review_count
        stats.average_rating = average_rating
        stats.rating_1_count = rating_counts[1]
        stats.rating_2_count = rating_counts[2]
        stats.rating_3_count = rating_counts[3]
        stats.rating_4_count = rating_counts[4]
        stats.rating_5_count = rating_counts[5]
        stats.last_reviewed_at_text = last_reviewed_text
        stats.last_fetched_at = datetime.utcnow()
    else:
        stats = StatsCache(
            asin=asin,
            domain=domain,
            review_count=review_count,
            average_rating=average_rating,
            rating_1_count=rating_counts[1],
            rating_2_count=rating_counts[2],
            rating_3_count=rating_counts[3],
            rating_4_count=rating_counts[4],
            rating_5_count=rating_counts[5],
            last_reviewed_at_text=last_reviewed_text,
            last_fetched_at=datetime.utcnow(),
        )
        db.add(stats)
    
    db.commit()