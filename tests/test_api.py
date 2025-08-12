"""
Tests for FastAPI endpoints.
"""

import json
from datetime import datetime

import pytest
from fastapi import status

from amazon_review_scraper.database import ReviewDB, StatsCache


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ok"] is True
    assert "version" in data
    assert "timestamp" in data


def test_scrape_endpoint(client):
    """Test scrape initiation endpoint."""
    payload = {
        "asin": "B08N5WRWNW",
        "domain": "com",
        "source": "free",
    }
    
    response = client.post("/scrape", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ["queued", "cached"]
    assert "message" in data


def test_scrape_invalid_source(client):
    """Test scrape with invalid source."""
    payload = {
        "asin": "B08N5WRWNW",
        "domain": "com",
        "source": "invalid",
    }
    
    response = client.post("/scrape", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_job_status_not_found(client):
    """Test job status for non-existent job."""
    response = client.get("/jobs/nonexistent-job-id")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_reviews_empty(client):
    """Test getting reviews when none exist."""
    response = client.get("/reviews?asin=B08N5WRWNW&domain=com")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == []


def test_get_reviews_with_data(client, test_db, sample_review):
    """Test getting reviews with existing data."""
    # Add a review to the database
    review_db = ReviewDB(
        id=sample_review["id"],
        asin=sample_review["asin"],
        domain=sample_review["domain"],
        author=sample_review["author"],
        title=sample_review["title"],
        content=sample_review["content"],
        rating=sample_review["rating"],
        is_verified=sample_review["is_verified"],
        product_attributes=sample_review["product_attributes"],
        timestamp_text=sample_review["timestamp_text"],
        fetched_at=datetime.utcnow(),
    )
    test_db.add(review_db)
    test_db.commit()
    
    # Get reviews
    response = client.get(f"/reviews?asin={sample_review['asin']}&domain={sample_review['domain']}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == sample_review["id"]
    assert data[0]["author"] == sample_review["author"]


def test_get_reviews_pagination(client, test_db):
    """Test review pagination."""
    # Add multiple reviews
    for i in range(25):
        review = ReviewDB(
            id=f"R{i:010d}",
            asin="B08N5WRWNW",
            domain="com",
            author=f"User {i}",
            title=f"Review {i}",
            content=f"Content {i}",
            rating=4.0,
            is_verified=True,
            timestamp_text=f"Reviewed on day {i}",
            fetched_at=datetime.utcnow(),
        )
        test_db.add(review)
    test_db.commit()
    
    # Get first page
    response = client.get("/reviews?asin=B08N5WRWNW&domain=com&limit=10")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 10
    
    # Check for cursor header
    assert "X-Next-Cursor" in response.headers
    cursor = response.headers["X-Next-Cursor"]
    
    # Get next page
    response = client.get(f"/reviews?asin=B08N5WRWNW&domain=com&limit=10&cursor={cursor}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 10


def test_get_stats_empty(client):
    """Test getting stats when no reviews exist."""
    response = client.get("/stats?asin=B08N5WRWNW&domain=com")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["review_count"] == 0
    assert data["average_rating"] == 0.0


def test_get_stats_with_cache(client, test_db, sample_stats):
    """Test getting stats from cache."""
    # Add stats to cache
    stats_cache = StatsCache(
        asin=sample_stats["asin"],
        domain=sample_stats["domain"],
        review_count=sample_stats["review_count"],
        average_rating=sample_stats["average_rating"],
        rating_1_count=sample_stats["rating_breakdown"]["1"],
        rating_2_count=sample_stats["rating_breakdown"]["2"],
        rating_3_count=sample_stats["rating_breakdown"]["3"],
        rating_4_count=sample_stats["rating_breakdown"]["4"],
        rating_5_count=sample_stats["rating_breakdown"]["5"],
        last_reviewed_at_text=sample_stats["last_reviewed_at_text"],
        last_fetched_at=datetime.utcnow(),
    )
    test_db.add(stats_cache)
    test_db.commit()
    
    # Get stats
    response = client.get(f"/stats?asin={sample_stats['asin']}&domain={sample_stats['domain']}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["review_count"] == sample_stats["review_count"]
    assert data["average_rating"] == sample_stats["average_rating"]


def test_metrics_endpoint(client):
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert "reviews_api_requests_total" in response.text