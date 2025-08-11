"""
Pydantic models for Amazon Review scraper service.
"""

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class Review(BaseModel):
    """Amazon review data model."""
    
    id: str = Field(..., description="Unique review identifier")
    asin: str = Field(..., description="Amazon Standard Identification Number")
    domain: str = Field(default="com", description="Amazon marketplace domain (e.g., com, nl, de)")
    author: str = Field(..., description="Review author name")
    title: str = Field(..., description="Review title")
    content: str = Field(..., description="Review content text")
    rating: float = Field(..., ge=1, le=5, description="Review rating (1-5)")
    is_verified: bool = Field(default=False, description="Whether purchase is verified")
    product_attributes: Optional[str] = Field(None, description="Product variant attributes")
    timestamp_text: str = Field(..., description="Raw timestamp text from Amazon")
    fetched_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp when review was fetched"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "R1234567890",
                "asin": "B08N5WRWNW",
                "domain": "com",
                "author": "John Doe",
                "title": "Great product!",
                "content": "This product exceeded my expectations...",
                "rating": 5,
                "is_verified": True,
                "product_attributes": "Color: Black, Size: Large",
                "timestamp_text": "Reviewed in the United States on January 1, 2024",
                "fetched_at": "2024-01-15T10:30:00Z"
            }
        }


class ReviewStats(BaseModel):
    """Aggregated review statistics for a product."""
    
    asin: str = Field(..., description="Amazon Standard Identification Number")
    domain: str = Field(default="com", description="Amazon marketplace domain")
    review_count: int = Field(default=0, ge=0, description="Total number of reviews")
    average_rating: float = Field(default=0.0, ge=0, le=5, description="Average rating")
    rating_breakdown: Dict[int, int] = Field(
        default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        description="Count of reviews per rating"
    )
    last_reviewed_at_text: Optional[str] = Field(
        None, 
        description="Timestamp text of most recent review"
    )
    last_fetched_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp of last fetch"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "asin": "B08N5WRWNW",
                "domain": "com",
                "review_count": 1523,
                "average_rating": 4.3,
                "rating_breakdown": {
                    "1": 45,
                    "2": 67,
                    "3": 189,
                    "4": 456,
                    "5": 766
                },
                "last_reviewed_at_text": "Reviewed on January 15, 2024",
                "last_fetched_at": "2024-01-15T10:30:00Z"
            }
        }


class ScrapeJobRequest(BaseModel):
    """Request model for initiating a scrape job."""
    
    asin: str = Field(..., description="Amazon Standard Identification Number")
    domain: str = Field(default="com", description="Amazon marketplace domain")
    source: str = Field(default="free", pattern="^(free|oxylabs)$", description="Data source")

    class Config:
        json_schema_extra = {
            "example": {
                "asin": "B08N5WRWNW",
                "domain": "com",
                "source": "free"
            }
        }


class ScrapeJobResponse(BaseModel):
    """Response model for scrape job initiation."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "message": "Scrape job queued successfully"
            }
        }


class JobStatus(BaseModel):
    """Job status information."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    asin: str = Field(..., description="Product ASIN")
    domain: str = Field(..., description="Amazon marketplace domain")
    source: str = Field(..., description="Data source used")
    reviews_fetched: int = Field(default=0, description="Number of reviews fetched")
    pages_processed: int = Field(default=0, description="Number of pages processed")
    started_at: Optional[str] = Field(None, description="Job start timestamp")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "asin": "B08N5WRWNW",
                "domain": "com",
                "source": "free",
                "reviews_fetched": 40,
                "pages_processed": 2,
                "started_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T10:31:30Z",
                "error": None
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""
    
    ok: bool = Field(..., description="Service health status")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Current timestamp"
    )
    version: str = Field(default="0.2.0", description="Service version")

    class Config:
        json_schema_extra = {
            "example": {
                "ok": True,
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "0.2.0"
            }
        }
