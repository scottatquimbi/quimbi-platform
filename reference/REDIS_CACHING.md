# Redis Caching Implementation Guide

**Status:** ✅ Implemented (Phase 2)
**Date:** October 28, 2025
**Feature:** Optional Redis caching layer for performance optimization

---

## Overview

Redis caching has been implemented to reduce database load and improve response times for frequently accessed data. The caching layer is **optional** and gracefully degrades if Redis is unavailable.

### Key Features

- ✅ **Optional** - Disabled by default, enable with `ENABLE_CACHE=true`
- ✅ **Graceful degradation** - System works normally if Redis unavailable
- ✅ **Automatic serialization** - JSON serialization/deserialization
- ✅ **Configurable TTL** - Different cache durations per data type
- ✅ **Cache invalidation** - Pattern-based key deletion
- ✅ **Metrics integration** - Tracks cache hit/miss rates (if Prometheus enabled)
- ✅ **Admin endpoint** - `/admin/cache/stats` for monitoring

---

## Configuration

### Environment Variables

```bash
# Enable/disable caching (default: true)
ENABLE_CACHE=true

# Redis connection URL (default: localhost)
REDIS_URL=redis://localhost:6379/0

# Default cache TTL in seconds (default: 3600 = 1 hour)
CACHE_TTL=3600
```

### Railway Setup

```bash
# Check if Railway provides Redis addon
railway addons list

# If Redis addon available:
railway addons create redis

# Or use external Redis (e.g., Upstash, Redis Labs):
railway variables set REDIS_URL="redis://user:pass@host:port/db"
railway variables set ENABLE_CACHE=true
```

---

## Architecture

### Cache Flow

```
User Request
    ↓
Check Redis Cache
    ├─ Hit → Return cached data (fast: <10ms)
    └─ Miss → Fetch from DB → Cache result → Return
```

### Cache Keys

Prefixes organize cache by data type:

- `customer:{id}` - Customer profiles (TTL: 1 hour)
- `churn:{id}` - Churn predictions (TTL: 30 minutes)
- `archetype:{id}` - Archetype data (TTL: 1 hour)
- `query:{hash}` - Query results (TTL: 10 minutes)
- `segment:{id}` - Segment data (TTL: 1 hour)

### Cache Durations

| Data Type | TTL | Reason |
|-----------|-----|--------|
| Customer profile | 1 hour | Rarely changes |
| Churn prediction | 30 min | Time-sensitive |
| Archetype data | 1 hour | Static reference |
| Query results | 10 min | May become stale |
| Segment data | 1 hour | Rarely changes |

---

## Cached Endpoints

### 1. Customer Profile
**Endpoint:** `GET /api/mcp/customer/{customer_id}`
**Cache Key:** `customer:{customer_id}`
**TTL:** 1 hour

**Behavior:**
- First request: Fetches from DB, caches result
- Subsequent requests: Returns from cache (instant)
- Cache automatically expires after 1 hour

### 2. Churn Risk Prediction
**Endpoint:** `GET /api/mcp/customer/{customer_id}/churn-risk`
**Cache Key:** `churn:{customer_id}`
**TTL:** 30 minutes

**Behavior:**
- Predictions cached for 30 minutes
- More frequent refresh than profiles (time-sensitive)

---

## Cache Statistics

### Admin Endpoint

```bash
GET /admin/cache/stats
```

**Response (Redis enabled):**
```json
{
  "enabled": true,
  "total_keys": 1547,
  "hits": 8932,
  "misses": 2341,
  "hit_rate": 79.23,
  "memory_used_mb": 12.45
}
```

**Response (Redis disabled):**
```json
{
  "enabled": false,
  "reason": "Cache disabled or not connected"
}
```

### Monitoring Cache Performance

```bash
# View cache statistics
curl http://localhost:8080/admin/cache/stats | jq

# Check cache hit rate in logs
tail -f logs/backend.log | grep cache_hit
tail -f logs/backend.log | grep cache_miss

# If Prometheus enabled:
curl http://localhost:8080/metrics | grep cache_hit_rate
```

---

## Cache Invalidation

### Manual Invalidation (via code)

```python
from backend.cache.redis_cache import invalidate_customer, invalidate_all_customers

# Invalidate single customer
await invalidate_customer("5971333382399")

# Invalidate all customers
await invalidate_all_customers()
```

### Pattern-Based Invalidation

```python
from backend.cache.redis_cache import cache

# Delete all customer caches
await cache.delete_pattern("customer:*")

# Delete all churn predictions
await cache.delete_pattern("churn:*")

# Clear entire cache (use with caution!)
await cache.clear_all()
```

### Automatic Invalidation

Cache keys automatically expire based on TTL:
- No manual invalidation needed for most cases
- System remains consistent through TTL expiration

---

## Performance Impact

### Without Caching
- Customer profile lookup: **50-100ms** (DB query)
- Churn prediction: **200-300ms** (DB + computation)

### With Caching
- Customer profile lookup (cached): **5-10ms** (Redis fetch)
- Churn prediction (cached): **5-10ms** (Redis fetch)

### Expected Improvement
- **10-20x faster** response times for cached data
- **50-80% reduction** in database load
- **Higher throughput** - more concurrent users

---

## Graceful Degradation

### If Redis Unavailable

1. **Startup:** System logs warning but continues running
2. **Runtime:** All cache operations become no-ops
3. **Endpoints:** Work normally by fetching from DB
4. **Performance:** No caching benefit, but no errors

**Log Example:**
```json
{
  "event": "cache_disabled",
  "reason": "ENABLE_CACHE=false",
  "level": "info"
}
```

---

## Development Testing

### Local Redis Setup

```bash
# Option 1: Docker
docker run -d -p 6379:6379 redis:7-alpine

# Option 2: Homebrew (macOS)
brew install redis
brew services start redis

# Option 3: Use cloud Redis (Upstash free tier)
# Sign up at: https://upstash.com/
# Get REDIS_URL from dashboard
```

### Test Caching

```bash
# Start backend with caching enabled
export REDIS_URL="redis://localhost:6379/0"
export ENABLE_CACHE=true
cd backend
uvicorn main:app --reload --port 8080

# Test customer profile (first request - cache miss)
time curl http://localhost:8080/api/mcp/customer/5971333382399

# Test again (second request - cache hit, should be faster)
time curl http://localhost:8080/api/mcp/customer/5971333382399

# Check cache stats
curl http://localhost:8080/admin/cache/stats | jq
```

### Verify Cache Hits

Check logs for cache activity:
```bash
# Look for cache hits
tail -f logs/backend.log | grep cache_hit

# Look for cache misses
tail -f logs/backend.log | grep cache_miss
```

---

## Production Deployment

### Railway Redis Setup

**Option 1: Railway Redis Plugin (if available)**
```bash
railway addons create redis
railway variables  # Note REDIS_URL auto-added
railway variables set ENABLE_CACHE=true
railway up
```

**Option 2: External Redis (Upstash)**
1. Sign up at https://upstash.com/
2. Create Redis database
3. Copy connection URL
4. Add to Railway:
```bash
railway variables set REDIS_URL="rediss://default:pass@host:port"
railway variables set ENABLE_CACHE=true
railway up
```

### Cost Estimates

**Upstash Free Tier:**
- 10K requests/day
- 256MB storage
- **Cost:** Free

**Upstash Pay-As-You-Go:**
- $0.20 per 100K requests
- $0.25 per GB storage/month
- **Estimated:** $2-5/month for typical usage

**Railway Redis (if available):**
- Check Railway pricing page

---

## Troubleshooting

### Issue: Cache not working

**Check:**
1. `ENABLE_CACHE=true` set?
2. `REDIS_URL` correct?
3. Redis server running?
4. Network connectivity?

**Debug:**
```bash
# Check cache status
curl http://localhost:8080/admin/cache/stats

# Check logs
railway logs | grep cache

# Test Redis connection
redis-cli -u $REDIS_URL ping
```

### Issue: High memory usage

**Solutions:**
1. Reduce TTL values (shorter cache duration)
2. Clear cache: `await cache.clear_all()`
3. Use Redis eviction policy: `maxmemory-policy allkeys-lru`
4. Upgrade Redis instance size

### Issue: Stale data

**Solutions:**
1. Reduce TTL for affected data type
2. Implement manual invalidation on data updates
3. Add versioning to cache keys

---

## API Reference

### Core Functions

```python
from backend.cache.redis_cache import (
    cache,
    cache_customer,
    get_cached_customer,
    invalidate_customer
)

# Cache customer data
await cache_customer("customer_id", data, ttl=3600)

# Retrieve cached customer
customer = await get_cached_customer("customer_id")

# Invalidate customer cache
await invalidate_customer("customer_id")

# Check if key exists
exists = await cache.exists("customer:5971333382399")
```

### Decorator Pattern

```python
from backend.cache.redis_cache import cached

@cached("customer", ttl=3600)
async def get_customer_profile(customer_id: str):
    # Function result automatically cached
    return fetch_from_db(customer_id)
```

---

## Next Steps

### Phase 2 Remaining Tasks

1. ✅ Redis caching - **COMPLETE**
2. ⏭️ Database connection pooling optimization
3. ⏭️ Slack reaction handlers completion
4. ⏭️ Gorgias ticketing methods completion

### Future Enhancements

- Implement cache warming on startup
- Add distributed caching (Redis Cluster)
- Implement cache versioning for breaking changes
- Add cache analytics dashboard
- Implement write-through caching pattern

---

## References

- **Redis Cache Module:** `backend/cache/redis_cache.py`
- **Redis Python Client:** https://redis-py.readthedocs.io/
- **Upstash Redis:** https://upstash.com/
- **Railway Redis:** https://docs.railway.app/databases/redis

---

**Last Updated:** October 28, 2025
**Status:** ✅ Production Ready
