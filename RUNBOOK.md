# ArbVault External Reviews Service - Runbook

## Quick Start Guide

This runbook provides step-by-step instructions for setting up and operating the Amazon Review Scraper service locally and integrating it with the ArbVault frontend.

## 📦 Phase 1: Backend Service Setup

### 1.1 Initial Setup

```bash
# Clone the repository
git clone https://github.com/FVEFWFE/amazon-review-scraper.git
cd amazon-review-scraper

# Initialize the project
make init

# This will:
# - Install Poetry dependencies
# - Create .env file from template
# - Create data and logs directories
```

### 1.2 Configure Environment

Edit the `.env` file with your configuration:

```bash
# For local testing (free mode only)
RATE_LIMIT_RPS=1.0
MAX_PAGES_FREE=2

# For production (add Oxylabs credentials)
OXYSCRAPER_AUTH_USER=your_username
OXYSCRAPER_AUTH_PASS=your_password
```

### 1.3 Start the Service

Using Docker (recommended):
```bash
# Build and start all services
make up

# Or with development tools (Flower monitoring)
make dev-full
```

Using local Python:
```bash
# Start Redis first (required)
redis-server

# In a new terminal, start the API
make dev

# In another terminal, start the Celery worker
poetry run celery -A amazon_review_scraper.tasks worker --loglevel=info
```

### 1.4 Verify Service Health

```bash
# Check health endpoint
curl http://localhost:8080/health

# Expected response:
# {"ok": true, "timestamp": "2024-01-15T10:30:00Z", "version": "0.2.0"}

# Check API documentation
open http://localhost:8080/docs
```

## 📱 Phase 2: Frontend Integration

### 2.1 Setup Frontend Environment

```bash
# Navigate to frontend repository
cd ../arbvault-frontend-main

# Add environment variable
echo "NEXT_PUBLIC_EXTERNAL_REVIEWS_BASE_URL=http://localhost:8080" >> .env.local
```

### 2.2 Install Frontend Dependencies

```bash
# Create the external reviews library
mkdir -p lib/external-reviews
```

### 2.3 Create Zod Schemas

Create `lib/external-reviews/schema.ts`:

```typescript
import { z } from 'zod';

export const Review = z.object({
  id: z.string(),
  asin: z.string(),
  domain: z.string(),
  author: z.string().default("Anonymous"),
  title: z.string().default(""),
  content: z.string().default(""),
  rating: z.number().min(1).max(5),
  isVerified: z.boolean().optional(),
  productAttributes: z.string().nullable().optional(),
  timestampText: z.string().default(""),
  fetchedAt: z.string(),
});

export const ReviewStats = z.object({
  asin: z.string(),
  domain: z.string(),
  reviewCount: z.number().int().nonnegative(),
  averageRating: z.number().min(0).max(5),
  ratingBreakdown: z.object({
    1: z.number(),
    2: z.number(),
    3: z.number(),
    4: z.number(),
    5: z.number(),
  }),
  lastReviewedAtText: z.string().nullable(),
  lastFetchedAt: z.string(),
});

export const ReviewsResponse = z.object({
  stats: ReviewStats,
  reviews: z.array(Review),
});

export type Review = z.infer<typeof Review>;
export type ReviewStats = z.infer<typeof ReviewStats>;
export type ReviewsResponse = z.infer<typeof ReviewsResponse>;
```

### 2.4 Create API Client

Create `lib/external-reviews/client.ts`:

```typescript
import { ReviewsResponse } from './schema';

const BASE_URL = process.env.NEXT_PUBLIC_EXTERNAL_REVIEWS_BASE_URL || 'http://localhost:8080';

export async function fetchExternalReviews(
  asin: string,
  domain: string = 'com',
  limit: number = 5
): Promise<ReviewsResponse | null> {
  try {
    const response = await fetch(
      `/api/external-reviews/${asin}?domain=${domain}&limit=${limit}`,
      { cache: 'force-cache' }
    );
    
    if (!response.ok) {
      console.error('Failed to fetch external reviews:', response.status);
      return null;
    }
    
    const data = await response.json();
    return ReviewsResponse.parse(data);
  } catch (error) {
    console.error('Error fetching external reviews:', error);
    return null;
  }
}
```

### 2.5 Create API Proxy Route

Create `app/api/external-reviews/[asin]/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';

export const revalidate = 900; // 15 minutes

export async function GET(
  request: NextRequest,
  { params }: { params: { asin: string } }
) {
  const searchParams = request.nextUrl.searchParams;
  const domain = searchParams.get('domain') ?? 'com';
  const limit = Number(searchParams.get('limit') ?? '5');
  
  const baseUrl = process.env.NEXT_PUBLIC_EXTERNAL_REVIEWS_BASE_URL || 'http://localhost:8080';
  
  try {
    const [statsRes, reviewsRes] = await Promise.all([
      fetch(`${baseUrl}/stats?asin=${params.asin}&domain=${domain}`, {
        cache: 'no-store',
      }),
      fetch(`${baseUrl}/reviews?asin=${params.asin}&domain=${domain}&limit=${limit}`, {
        cache: 'no-store',
      }),
    ]);
    
    if (!statsRes.ok || !reviewsRes.ok) {
      return NextResponse.json({ stats: null, reviews: [] });
    }
    
    const stats = await statsRes.json();
    const reviews = await reviewsRes.json();
    
    return NextResponse.json({ stats, reviews });
  } catch (error) {
    console.error('Error fetching external reviews:', error);
    return NextResponse.json({ stats: null, reviews: [] });
  }
}
```

### 2.6 Create External Reviews Component

Create `components/product/reviews/external-reviews.tsx`:

```tsx
import { fetchExternalReviews } from '@/lib/external-reviews/client';
import { Star } from 'lucide-react';

interface ExternalReviewsProps {
  asin: string;
  domain?: string;
}

export async function ExternalReviews({ asin, domain = 'com' }: ExternalReviewsProps) {
  const data = await fetchExternalReviews(asin, domain);
  
  if (!data || !data.reviews.length) {
    return null;
  }
  
  const { stats, reviews } = data;
  
  return (
    <div className="mt-8 border-t pt-8">
      <h2 className="text-2xl font-bold mb-4">External Reviews (Amazon)</h2>
      
      {stats && (
        <div className="mb-6 flex items-center gap-4">
          <div className="flex items-center">
            {[...Array(5)].map((_, i) => (
              <Star
                key={i}
                className={`w-5 h-5 ${
                  i < Math.floor(stats.averageRating)
                    ? 'fill-yellow-400 text-yellow-400'
                    : 'text-gray-300'
                }`}
              />
            ))}
          </div>
          <span className="text-lg font-semibold">
            {stats.averageRating.toFixed(1)} out of 5
          </span>
          <span className="text-gray-600">
            ({stats.reviewCount} reviews)
          </span>
        </div>
      )}
      
      <div className="space-y-4">
        {reviews.map((review) => (
          <div key={review.id} className="border-b pb-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="flex">
                {[...Array(5)].map((_, i) => (
                  <Star
                    key={i}
                    className={`w-4 h-4 ${
                      i < review.rating
                        ? 'fill-yellow-400 text-yellow-400'
                        : 'text-gray-300'
                    }`}
                  />
                ))}
              </div>
              <span className="font-semibold">{review.title}</span>
              {review.isVerified && (
                <span className="text-xs bg-orange-100 text-orange-800 px-2 py-1 rounded">
                  Verified Purchase
                </span>
              )}
            </div>
            <p className="text-sm text-gray-600 mb-1">
              By {review.author} on {review.timestampText}
            </p>
            <p className="text-gray-800 line-clamp-3">{review.content}</p>
          </div>
        ))}
      </div>
      
      <a
        href={`https://www.amazon.${domain}/product-reviews/${asin}`}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-4 inline-block text-blue-600 hover:underline"
      >
        View more on Amazon →
      </a>
    </div>
  );
}
```

### 2.7 Integrate into Product Page

Update your product page to include external reviews:

```tsx
// In your product page component
import { ExternalReviews } from '@/components/product/reviews/external-reviews';

export default async function ProductPage({ params }: { params: { id: string } }) {
  const product = await getProduct(params.id);
  
  return (
    <div>
      {/* ... existing product content ... */}
      
      {/* Internal reviews */}
      <ProductReviews productId={params.id} />
      
      {/* External reviews - only show if ASIN exists */}
      {product.metadata?.asin && (
        <ExternalReviews 
          asin={product.metadata.asin}
          domain={product.metadata.amazonDomain || 'com'}
        />
      )}
    </div>
  );
}
```

## 🛠️ Phase 3: Admin Scripts

### 3.1 Create ASIN Metadata Script

Create `scripts/set-product-asin.ts`:

```typescript
import { z } from 'zod';
import fetch from 'node-fetch';

const schema = z.object({
  productId: z.string(),
  asin: z.string(),
  domain: z.string().default('com'),
});

async function setProductAsin(productId: string, asin: string, domain: string = 'com') {
  const MEDUSA_BACKEND_URL = process.env.MEDUSA_BACKEND_URL || 'http://localhost:9000';
  const ADMIN_TOKEN = process.env.MEDUSA_ADMIN_TOKEN;
  
  if (!ADMIN_TOKEN) {
    throw new Error('MEDUSA_ADMIN_TOKEN is required');
  }
  
  const response = await fetch(`${MEDUSA_BACKEND_URL}/admin/products/${productId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${ADMIN_TOKEN}`,
    },
    body: JSON.stringify({
      metadata: {
        asin,
        amazonDomain: domain,
      },
    }),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to update product: ${response.statusText}`);
  }
  
  console.log(`✅ Product ${productId} updated with ASIN ${asin}`);
}

// CLI usage
const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('Usage: ts-node set-product-asin.ts <productId> <asin> [domain]');
  process.exit(1);
}

const [productId, asin, domain = 'com'] = args;

setProductAsin(productId, asin, domain)
  .catch(console.error);
```

### 3.2 Run the Script

```bash
# Set ASIN for a product
cd arbvault-frontend-main
npx ts-node scripts/set-product-asin.ts prod_01234567 B08N5WRWNW com
```

## 🧪 Testing the Integration

### Step 1: Trigger a Scrape

```bash
# Initiate scraping for a product
curl -X POST http://localhost:8080/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "asin": "B08N5WRWNW",
    "domain": "com",
    "source": "free"
  }'

# Response:
# {"job_id": "550e8400-e29b-41d4-a716-446655440000", "status": "queued", "message": "Scrape job queued successfully"}
```

### Step 2: Check Job Status

```bash
# Check job status
curl http://localhost:8080/jobs/550e8400-e29b-41d4-a716-446655440000

# Response shows progress
```

### Step 3: Fetch Reviews

```bash
# Get reviews
curl "http://localhost:8080/reviews?asin=B08N5WRWNW&domain=com&limit=5"

# Get statistics
curl "http://localhost:8080/stats?asin=B08N5WRWNW&domain=com"
```

### Step 4: View in Frontend

1. Set ASIN metadata on a product using the admin script
2. Navigate to the product page
3. Scroll down to see the "External Reviews (Amazon)" section

## 🔍 Monitoring & Debugging

### Check Service Logs

```bash
# View all logs
make logs

# View specific service logs
docker-compose logs -f api
docker-compose logs -f worker
```

### Monitor Celery Tasks

```bash
# Open Flower UI (if running in dev mode)
open http://localhost:5555
```

### Database Inspection

```bash
# Connect to SQLite database
sqlite3 data/reviews.db

# Show tables
.tables

# Count reviews
SELECT COUNT(*) FROM reviews;

# View recent reviews
SELECT * FROM reviews ORDER BY fetched_at DESC LIMIT 5;
```

### Redis Monitoring

```bash
# Connect to Redis
redis-cli

# Check keys
KEYS *

# Monitor commands in real-time
MONITOR
```

## 🚨 Troubleshooting

### Issue: Service won't start

```bash
# Check if ports are in use
lsof -i :8080
lsof -i :6379

# Stop conflicting services
docker-compose down
killall redis-server
```

### Issue: No reviews fetched

```bash
# Check worker logs
docker-compose logs worker

# Verify ASIN is valid
curl "https://www.amazon.com/dp/B08N5WRWNW"

# Test with known working ASIN
curl -X POST http://localhost:8080/scrape \
  -H "Content-Type: application/json" \
  -d '{"asin": "B08N5WRWNW", "domain": "com", "source": "free"}'
```

### Issue: Frontend not showing reviews

```bash
# Check browser console for errors
# Verify environment variable
echo $NEXT_PUBLIC_EXTERNAL_REVIEWS_BASE_URL

# Test API proxy directly
curl http://localhost:3000/api/external-reviews/B08N5WRWNW
```

## 📊 Performance Tuning

### Adjust Rate Limiting

Edit `.env`:
```bash
RATE_LIMIT_RPS=0.5  # Slower for safety
MAX_PAGES_FREE=1    # Fewer pages
```

### Increase Cache TTL

```bash
CACHE_TTL_SECONDS=1800  # 30 minutes
```

### Scale Workers

```bash
# Edit docker-compose.yml
command: celery -A amazon_review_scraper.tasks worker --loglevel=info --concurrency=4
```

## 🔄 Daily Operations

### Morning Checklist

1. Check service health: `curl http://localhost:8080/health`
2. Review error logs: `docker-compose logs --since 24h | grep ERROR`
3. Check disk space: `df -h data/`
4. Monitor Redis memory: `redis-cli INFO memory`

### Maintenance Tasks

```bash
# Clean old data (reviews older than 30 days)
sqlite3 data/reviews.db "DELETE FROM reviews WHERE fetched_at < datetime('now', '-30 days');"

# Vacuum database
sqlite3 data/reviews.db "VACUUM;"

# Clear Redis cache
redis-cli FLUSHDB
```

## 🚀 Production Deployment

### Prerequisites

1. Obtain Oxylabs API credentials
2. Set up monitoring (Prometheus/Grafana)
3. Configure proper domain and SSL

### Deployment Steps

```bash
# Update production environment
cp .env.production .env

# Build and deploy
make deploy

# Run health checks
./scripts/health-check.sh
```

## 📞 Support Contacts

- Backend Issues: Check logs and GitHub issues
- Frontend Integration: Review Next.js documentation
- API Questions: See FastAPI docs at `/docs`

---

Last Updated: January 2024
Version: 1.0.0