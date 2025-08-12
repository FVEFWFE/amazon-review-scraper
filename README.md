# Amazon Review Scraper Service

A production-ready FastAPI microservice for scraping and serving Amazon product reviews. Built for the ArbVault marketplace to provide external review summaries on Product Detail Pages (PDPs).

## 🚀 Features

- **FastAPI REST API** with automatic OpenAPI documentation
- **Dual scraping sources**: Free mode (rate-limited) and Oxylabs API (production)
- **Background job processing** with Celery and Redis
- **SQLite database** with SQLAlchemy ORM for review storage
- **Redis caching** with 15-minute TTL for improved performance
- **Cursor-based pagination** for efficient data retrieval
- **Prometheus metrics** for monitoring
- **Docker support** with multi-stage builds
- **Comprehensive test suite** with pytest
- **Rate limiting** and retry logic with exponential backoff
- **CORS support** for frontend integration

## 📋 Prerequisites

- Python 3.11+
- Poetry (for dependency management) OR pip
- Docker and Docker Compose (for containerized deployment)
- Redis (for caching and job queue)
- Oxylabs API credentials (for production use)

## 🛠️ Installation

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/FVEFWFE/amazon-review-scraper.git
cd amazon-review-scraper
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Install dependencies:

**Option A: Using Poetry (recommended for development)**
```bash
pip install poetry
poetry install
```

**Option B: Using pip**
```bash
pip install -r requirements.txt
```

4. Initialize the project:
```bash
mkdir -p data logs
```

### Docker Deployment

1. Build and start services:
```bash
make up
```

2. View logs:
```bash
make logs
```

3. Stop services:
```bash
make down
```

## 🔧 Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OXYSCRAPER_AUTH_USER` | Oxylabs API username | - |
| `OXYSCRAPER_AUTH_PASS` | Oxylabs API password | - |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `REVIEWS_DB_URL` | Database connection URL | `sqlite:///./data/reviews.db` |
| `RATE_LIMIT_RPS` | Requests per second (free mode) | `1.0` |
| `MAX_PAGES_FREE` | Max pages to scrape (free mode) | `2` |
| `MAX_PAGES_OXYLABS` | Max pages to scrape (Oxylabs) | `10` |
| `CACHE_TTL_SECONDS` | Cache TTL in seconds | `900` |

## 📡 API Endpoints

### Health Check
```http
GET /health
```
Returns service health status.

### Initiate Scraping
```http
POST /scrape
Content-Type: application/json

{
  "asin": "B08N5WRWNW",
  "domain": "com",
  "source": "free"
}
```
Queues a scraping job. Sources: `free` or `oxylabs`.

### Get Job Status
```http
GET /jobs/{job_id}
```
Returns the status of a scraping job.

### Get Reviews
```http
GET /reviews?asin=B08N5WRWNW&domain=com&limit=20&cursor=R1234567890
```
Returns paginated reviews for a product.

### Get Statistics
```http
GET /stats?asin=B08N5WRWNW&domain=com
```
Returns aggregated review statistics.

### Prometheus Metrics
```http
GET /metrics
```
Returns Prometheus-formatted metrics.

## 🧪 Testing

Run the test suite:

**With Poetry:**
```bash
poetry run pytest tests/
```

**With pip:**
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

## 🐳 Docker Architecture

The service uses a multi-container architecture:

- **api**: FastAPI application server
- **worker**: Celery worker for background jobs
- **beat**: Celery beat for scheduled tasks
- **redis**: Redis for caching and job queue
- **flower**: Celery monitoring UI (development only)

## 📊 Data Models

### Review
```python
{
  "id": "R1234567890",
  "asin": "B08N5WRWNW",
  "domain": "com",
  "author": "John Doe",
  "title": "Great product!",
  "content": "This product exceeded my expectations...",
  "rating": 5,
  "is_verified": true,
  "product_attributes": "Color: Black, Size: Large",
  "timestamp_text": "Reviewed on January 1, 2024",
  "fetched_at": "2024-01-15T10:30:00Z"
}
```

### ReviewStats
```python
{
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
```

## 🔐 Security Considerations

- **Rate Limiting**: Free mode is limited to 1 RPS with max 2 pages
- **Authentication**: Oxylabs API requires credentials
- **CORS**: Configured for specific origins
- **Input Validation**: Pydantic models validate all inputs
- **SQL Injection**: Protected via SQLAlchemy ORM
- **XSS Prevention**: All content is escaped in frontend

## 📈 Performance

- **Caching**: Redis caches results for 15 minutes
- **Pagination**: Cursor-based pagination for efficient data retrieval
- **Background Processing**: Celery handles long-running scraping tasks
- **Database Indexing**: Optimized indexes on ASIN and domain
- **Connection Pooling**: SQLAlchemy manages database connections

## 🚦 Monitoring

- **Health Endpoint**: `/health` for service monitoring
- **Prometheus Metrics**: `/metrics` for detailed metrics
- **Flower UI**: Available at `http://localhost:5555` in dev mode
- **Structured Logging**: JSON-formatted logs for easy parsing

## 📝 Development Workflow

1. **Format code**:
```bash
make format
```

2. **Run linting**:
```bash
make lint
```

3. **Type checking**:
```bash
make type-check
```

4. **Run all checks**:
```bash
make check
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

This project is proprietary software for ArbVault marketplace.

## 🆘 Support

For issues or questions, please open an issue on GitHub or contact the development team.

## 🔄 CI/CD

The project includes GitHub Actions workflows for:
- Running tests on pull requests
- Building and pushing Docker images
- Deploying to staging/production

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Oxylabs API Documentation](https://developers.oxylabs.io/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [SQLAlchemy Documentation](https://www.sqlalchemy.org/)

---

Built with ❤️ for ArbVault marketplace
