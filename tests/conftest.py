"""
Pytest configuration and fixtures.
"""

import asyncio
import os
import tempfile
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from amazon_review_scraper.api import app
from amazon_review_scraper.database import Base, get_db


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def test_db():
    """Create a test database."""
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    # Create engine and tables
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    yield TestingSessionLocal()
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope="function")
def client(test_db):
    """Create a test client with test database."""
    
    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_review():
    """Sample review data for testing."""
    return {
        "id": "R1234567890",
        "asin": "B08N5WRWNW",
        "domain": "com",
        "author": "Test User",
        "title": "Great product!",
        "content": "This product exceeded my expectations. Would recommend!",
        "rating": 5,
        "is_verified": True,
        "product_attributes": "Color: Black",
        "timestamp_text": "Reviewed on January 1, 2024",
        "fetched_at": "2024-01-15T10:30:00Z",
    }


@pytest.fixture
def sample_stats():
    """Sample statistics data for testing."""
    return {
        "asin": "B08N5WRWNW",
        "domain": "com",
        "review_count": 100,
        "average_rating": 4.5,
        "rating_breakdown": {
            "1": 5,
            "2": 5,
            "3": 10,
            "4": 30,
            "5": 50,
        },
        "last_reviewed_at_text": "Reviewed on January 15, 2024",
        "last_fetched_at": "2024-01-15T10:30:00Z",
    }