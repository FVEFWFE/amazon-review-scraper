"""
Database models and session management for review storage.
"""

from datetime import datetime
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from amazon_review_scraper.config import settings

Base = declarative_base()


class ReviewDB(Base):
    """Database model for storing Amazon reviews."""
    
    __tablename__ = "reviews"
    
    id = Column(String(50), primary_key=True)
    asin = Column(String(20), nullable=False, index=True)
    domain = Column(String(10), nullable=False, index=True)
    author = Column(String(200), nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    rating = Column(Float, nullable=False)
    is_verified = Column(Boolean, default=False)
    product_attributes = Column(Text, nullable=True)
    timestamp_text = Column(String(200), nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('id', 'asin', 'domain', name='_review_unique'),
        Index('idx_asin_domain', 'asin', 'domain'),
        Index('idx_fetched_at', 'fetched_at'),
    )


class JobDB(Base):
    """Database model for tracking scrape jobs."""
    
    __tablename__ = "jobs"
    
    job_id = Column(String(50), primary_key=True)
    asin = Column(String(20), nullable=False)
    domain = Column(String(10), nullable=False)
    source = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    reviews_fetched = Column(Integer, default=0)
    pages_processed = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_job_status', 'status'),
        Index('idx_job_asin_domain', 'asin', 'domain'),
    )


class StatsCache(Base):
    """Database model for caching review statistics."""
    
    __tablename__ = "stats_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    asin = Column(String(20), nullable=False)
    domain = Column(String(10), nullable=False)
    review_count = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    rating_1_count = Column(Integer, default=0)
    rating_2_count = Column(Integer, default=0)
    rating_3_count = Column(Integer, default=0)
    rating_4_count = Column(Integer, default=0)
    rating_5_count = Column(Integer, default=0)
    last_reviewed_at_text = Column(String(200), nullable=True)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('asin', 'domain', name='_stats_unique'),
        Index('idx_stats_asin_domain', 'asin', 'domain'),
    )


# Create engine and session factory
engine = create_engine(
    settings.REVIEWS_DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.REVIEWS_DB_URL else {},
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)