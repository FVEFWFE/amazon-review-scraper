"""
FastAPI application for Amazon Review Scraper service.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

import redis
from fastapi import FastAPI, HTTPException, Query, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest
from sqlalchemy.orm import Session

from amazon_review_scraper.config import settings
from amazon_review_scraper.database import get_db, init_db, ReviewDB, JobDB, StatsCache
from amazon_review_scraper.models import (
    Review,
    ReviewStats,
    ScrapeJobRequest,
    ScrapeJobResponse,
    JobStatus,
    HealthResponse,
)
from amazon_review_scraper.tasks import scrape_reviews_task

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Amazon Review Scraper API",
    description="Microservice for scraping and serving Amazon product reviews",
    version=settings.SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Prometheus metrics
request_counter = Counter(
    "reviews_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)
request_duration = Histogram(
    "reviews_api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(ok=True, version=settings.SERVICE_VERSION)


@app.post("/scrape", response_model=ScrapeJobResponse)
async def initiate_scrape(
    request: ScrapeJobRequest,
    db: Session = Depends(get_db),
):
    """
    Initiate a scraping job for Amazon reviews.
    
    The job will be queued and processed asynchronously.
    """
    job_id = str(uuid.uuid4())
    
    # Check if we already have recent data
    cache_key = f"scrape:{request.asin}:{request.domain}"
    last_scrape = redis_client.get(cache_key)
    
    if last_scrape:
        # Check if last scrape was within the cache TTL
        last_scrape_time = datetime.fromisoformat(last_scrape)
        if datetime.utcnow() - last_scrape_time < timedelta(seconds=settings.CACHE_TTL_SECONDS):
            return ScrapeJobResponse(
                job_id="cached",
                status="cached",
                message="Recent data available, no new scrape needed",
            )
    
    # Queue the scraping task
    task = scrape_reviews_task.delay(
        asin=request.asin,
        domain=request.domain,
        source=request.source,
        job_id=job_id,
    )
    
    # Store task ID for tracking
    redis_client.setex(f"task:{job_id}", 3600, task.id)
    
    # Mark scrape as initiated
    redis_client.setex(cache_key, settings.CACHE_TTL_SECONDS, datetime.utcnow().isoformat())
    
    return ScrapeJobResponse(
        job_id=job_id,
        status="queued",
        message="Scrape job queued successfully",
    )


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Get the status of a scraping job."""
    
    # Special case for cached response
    if job_id == "cached":
        return JobStatus(
            job_id="cached",
            status="cached",
            asin="",
            domain="",
            source="",
            reviews_fetched=0,
            pages_processed=0,
        )
    
    # Look up job in database
    job = db.query(JobDB).filter(JobDB.job_id == job_id).first()
    
    if not job:
        # Check if task exists in Redis
        task_id = redis_client.get(f"task:{job_id}")
        if task_id:
            return JobStatus(
                job_id=job_id,
                status="queued",
                asin="",
                domain="",
                source="",
                reviews_fetched=0,
                pages_processed=0,
            )
        
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatus(
        job_id=job.job_id,
        status=job.status,
        asin=job.asin,
        domain=job.domain,
        source=job.source,
        reviews_fetched=job.reviews_fetched,
        pages_processed=job.pages_processed,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
    )


@app.get("/reviews", response_model=List[Review])
async def get_reviews(
    asin: str = Query(..., description="Amazon Standard Identification Number"),
    domain: str = Query("com", description="Amazon marketplace domain"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of reviews to return"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """
    Get reviews for a product with cursor-based pagination.
    
    Results are cached for 15 minutes.
    """
    
    # Check Redis cache
    cache_key = f"reviews:{asin}:{domain}:{limit}:{cursor or 'start'}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data:
        import json
        reviews_data = json.loads(cached_data)
        response.headers["X-Cache"] = "HIT"
        return [Review(**r) for r in reviews_data]
    
    # Query database
    query = db.query(ReviewDB).filter(
        ReviewDB.asin == asin,
        ReviewDB.domain == domain,
    )
    
    # Apply cursor if provided
    if cursor:
        query = query.filter(ReviewDB.id > cursor)
    
    # Order by ID for stable pagination
    query = query.order_by(ReviewDB.id)
    
    # Apply limit
    reviews_db = query.limit(limit).all()
    
    # Convert to Pydantic models
    reviews = [
        Review(
            id=r.id,
            asin=r.asin,
            domain=r.domain,
            author=r.author,
            title=r.title,
            content=r.content,
            rating=r.rating,
            is_verified=r.is_verified,
            product_attributes=r.product_attributes,
            timestamp_text=r.timestamp_text,
            fetched_at=r.fetched_at.isoformat(),
        )
        for r in reviews_db
    ]
    
    # Cache the results
    import json
    redis_client.setex(
        cache_key,
        settings.CACHE_TTL_SECONDS,
        json.dumps([r.dict() for r in reviews]),
    )
    
    response.headers["X-Cache"] = "MISS"
    
    # Add next cursor if there are more results
    if reviews:
        response.headers["X-Next-Cursor"] = reviews[-1].id
    
    return reviews


@app.get("/stats", response_model=ReviewStats)
async def get_stats(
    asin: str = Query(..., description="Amazon Standard Identification Number"),
    domain: str = Query("com", description="Amazon marketplace domain"),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """
    Get aggregated statistics for a product's reviews.
    
    Results are cached for 15 minutes.
    """
    
    # Check Redis cache
    cache_key = f"stats:{asin}:{domain}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data:
        import json
        stats_data = json.loads(cached_data)
        response.headers["X-Cache"] = "HIT"
        return ReviewStats(**stats_data)
    
    # Query stats cache
    stats_db = db.query(StatsCache).filter(
        StatsCache.asin == asin,
        StatsCache.domain == domain,
    ).first()
    
    if not stats_db:
        # Calculate stats from reviews if not cached
        reviews = db.query(ReviewDB).filter(
            ReviewDB.asin == asin,
            ReviewDB.domain == domain,
        ).all()
        
        if not reviews:
            # Return empty stats
            stats = ReviewStats(
                asin=asin,
                domain=domain,
                review_count=0,
                average_rating=0.0,
                rating_breakdown={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                last_reviewed_at_text=None,
                last_fetched_at=datetime.utcnow().isoformat(),
            )
        else:
            # Calculate stats
            review_count = len(reviews)
            total_rating = sum(r.rating for r in reviews)
            average_rating = total_rating / review_count if review_count > 0 else 0
            
            rating_breakdown = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for review in reviews:
                rating_int = int(review.rating)
                if rating_int in rating_breakdown:
                    rating_breakdown[rating_int] += 1
            
            most_recent = max(reviews, key=lambda r: r.fetched_at)
            
            stats = ReviewStats(
                asin=asin,
                domain=domain,
                review_count=review_count,
                average_rating=round(average_rating, 1),
                rating_breakdown=rating_breakdown,
                last_reviewed_at_text=most_recent.timestamp_text if most_recent else None,
                last_fetched_at=datetime.utcnow().isoformat(),
            )
    else:
        # Convert from database model
        stats = ReviewStats(
            asin=stats_db.asin,
            domain=stats_db.domain,
            review_count=stats_db.review_count,
            average_rating=round(stats_db.average_rating, 1),
            rating_breakdown={
                1: stats_db.rating_1_count,
                2: stats_db.rating_2_count,
                3: stats_db.rating_3_count,
                4: stats_db.rating_4_count,
                5: stats_db.rating_5_count,
            },
            last_reviewed_at_text=stats_db.last_reviewed_at_text,
            last_fetched_at=stats_db.last_fetched_at.isoformat(),
        )
    
    # Cache the results
    import json
    redis_client.setex(
        cache_key,
        settings.CACHE_TTL_SECONDS,
        json.dumps(stats.dict()),
    )
    
    response.headers["X-Cache"] = "MISS"
    
    return stats


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )