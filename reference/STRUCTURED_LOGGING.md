# Structured Logging Guide

**Date:** October 28, 2025
**Status:** ✅ Implemented & Active

---

## Overview

The platform uses **structlog** for structured, JSON-formatted logging with correlation IDs. This makes production debugging significantly easier.

---

## Key Features

### 1. Correlation IDs ✅

Every request gets a unique correlation ID that appears in all related logs.

**Example:**
```json
{
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2025-10-28T10:30:45.123456Z",
  "level": "info",
  "event": "request_completed",
  "method": "POST",
  "path": "/api/mcp/query/natural-language",
  "status_code": 200,
  "duration_seconds": 0.234
}
```

**Benefits:**
- Track a single request through all log entries
- Debug complex flows across multiple function calls
- Correlation IDs returned in response headers: `X-Correlation-ID`

### 2. Automatic vs Manual Format

**Production (Railway):** JSON format automatically enabled
```bash
# Railway sets RAILWAY_ENVIRONMENT automatically
# JSON logs are automatically enabled
```

**Local Development:** Console format for readability
```bash
# No RAILWAY_ENVIRONMENT set
# Console format used by default
2025-10-28 10:30:45 [info] request_completed correlation_id=a1b2... method=POST status_code=200
```

**Force JSON locally:**
```bash
export JSON_LOGS=true
python3 -m backend.main
```

### 3. Context Injection

Structured logging automatically includes:
- `correlation_id` - Unique request ID
- `method` - HTTP method (GET, POST, etc.)
- `path` - Endpoint path
- `client_ip` - Client IP address
- `timestamp` - ISO8601 timestamp (UTC)
- `level` - Log level (info, warning, error)

---

## Log Output Examples

### Production (JSON)

**Request Started:**
```json
{
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2025-10-28T10:30:45.000000Z",
  "level": "info",
  "event": "request_started",
  "method": "POST",
  "path": "/api/mcp/query/natural-language",
  "client_ip": "192.168.1.100",
  "query_params": {"query": "Show me top customers"},
  "user_agent": "Mozilla/5.0..."
}
```

**Request Completed:**
```json
{
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2025-10-28T10:30:45.234000Z",
  "level": "info",
  "event": "request_completed",
  "method": "POST",
  "path": "/api/mcp/query/natural-language",
  "client_ip": "192.168.1.100",
  "status_code": 200,
  "duration_seconds": 0.234
}
```

**Database Query:**
```json
{
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2025-10-28T10:30:45.100000Z",
  "level": "info",
  "event": "database_query_completed",
  "query_type": "get_customer",
  "duration_seconds": 0.043,
  "row_count": 1
}
```

**AI Query:**
```json
{
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2025-10-28T10:30:45.150000Z",
  "level": "info",
  "event": "ai_query_completed",
  "model": "claude-3-5-haiku",
  "tool": "query_customers",
  "duration_seconds": 1.234,
  "input_tokens": 500,
  "output_tokens": 300,
  "cost_usd": 0.000234
}
```

**Error:**
```json
{
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2025-10-28T10:30:45.200000Z",
  "level": "error",
  "event": "request_failed",
  "method": "POST",
  "path": "/api/mcp/query/natural-language",
  "client_ip": "192.168.1.100",
  "error": "Customer not found",
  "error_type": "ValueError",
  "duration_seconds": 0.123,
  "exc_info": "Traceback (most recent call last)..."
}
```

### Development (Console)

```
2025-10-28 10:30:45 [info] request_started correlation_id=a1b2c3d4... method=POST path=/api/mcp/query client_ip=192.168.1.100
2025-10-28 10:30:45 [info] database_query_completed correlation_id=a1b2c3d4... query_type=get_customer duration_seconds=0.043 row_count=1
2025-10-28 10:30:45 [info] ai_query_completed correlation_id=a1b2c3d4... model=claude-3-5-haiku tool=query_customers duration_seconds=1.234
2025-10-28 10:30:45 [info] request_completed correlation_id=a1b2c3d4... method=POST status_code=200 duration_seconds=0.234
```

---

## Using Structured Logging in Code

### Basic Logging

```python
from backend.middleware.logging_config import get_logger

logger = get_logger(__name__)

# Simple log
logger.info("customer_profile_requested")

# Log with context
logger.info("customer_profile_requested", customer_id="5971333382399", user_id=123)

# Error with context
logger.error("customer_not_found", customer_id="invalid_id", attempted_by="user_123")
```

### Adding Persistent Context

```python
from backend.middleware.logging_config import log_with_context

# Add context that persists for the entire request
log_with_context(user_id=123, customer_id="5971333382399")

# All subsequent logs will include user_id and customer_id
logger.info("churn_risk_calculated", risk_score=0.85)
# Output: {..., "user_id": 123, "customer_id": "5971333382399", "risk_score": 0.85}
```

### Database Query Logging

```python
from backend.middleware.logging_config import log_database_query
import time

start_time = time.time()
try:
    result = await db.execute(query)
    duration = time.time() - start_time
    log_database_query("get_customer", duration=duration, row_count=len(result))
except Exception as e:
    duration = time.time() - start_time
    log_database_query("get_customer", duration=duration, error=str(e))
```

### AI Query Logging

```python
from backend.middleware.logging_config import log_ai_query
import time

start_time = time.time()
try:
    response = await client.messages.create(...)
    duration = time.time() - start_time

    log_ai_query(
        model="claude-3-5-haiku",
        tool="query_customers",
        duration=duration,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost=calculate_cost(response.usage)
    )
except Exception as e:
    duration = time.time() - start_time
    log_ai_query(
        model="claude-3-5-haiku",
        tool="query_customers",
        duration=duration,
        error=str(e)
    )
```

### Integration Call Logging

```python
from backend.middleware.logging_config import log_integration_call
import time

start_time = time.time()
try:
    response = await slack_client.chat_postMessage(...)
    duration = time.time() - start_time
    log_integration_call("slack", "post_message", duration=duration, success=True)
except Exception as e:
    duration = time.time() - start_time
    log_integration_call("slack", "post_message", duration=duration, success=False, error=str(e))
```

### Business Event Logging

```python
from backend.middleware.logging_config import log_business_event

# Track important business events
log_business_event(
    "customer_at_churn_risk",
    customer_id="5971333382399",
    churn_risk=0.85,
    ltv=5000,
    last_purchase_days=120
)

log_business_event(
    "high_value_purchase",
    customer_id="5971333382399",
    order_value=2500,
    customer_ltv=15000
)
```

### Security Event Logging

```python
from backend.middleware.logging_config import log_security_event

# Track security events
log_security_event(
    "api_key_invalid",
    severity="warning",
    ip_address="1.2.3.4",
    attempted_key="sk-xxx...xxx"
)

log_security_event(
    "rate_limit_exceeded",
    severity="warning",
    ip_address="1.2.3.4",
    endpoint="/api/mcp/query",
    limit="50/hour"
)
```

---

## Searching Logs

### Railway Dashboard

**By Correlation ID:**
```
a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**By Event:**
```
event:request_failed
```

**By Error:**
```
level:error
```

**By Customer:**
```
customer_id:5971333382399
```

### Using jq (Local)

**Extract all errors:**
```bash
cat logs.json | jq 'select(.level == "error")'
```

**Find slow requests (>1s):**
```bash
cat logs.json | jq 'select(.event == "request_completed" and .duration_seconds > 1)'
```

**Track a specific correlation ID:**
```bash
cat logs.json | jq 'select(.correlation_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890")'
```

**Count errors by type:**
```bash
cat logs.json | jq 'select(.level == "error") | .error_type' | sort | uniq -c
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `JSON_LOGS` | `false` | Force JSON format (auto-detected in Railway) |
| `RAILWAY_ENVIRONMENT` | - | Automatically set by Railway (triggers JSON format) |

### Change Log Level

**Production (Railway):**
```bash
railway variables set LOG_LEVEL=DEBUG
railway up
```

**Local:**
```bash
export LOG_LEVEL=DEBUG
python3 -m backend.main
```

---

## Correlation ID Flow

### Client to Server

**1. Client sends request (optional header):**
```bash
curl -H "X-Correlation-ID: my-custom-id" https://api.example.com/query
```

**2. Server uses provided ID or generates new UUID:**
```python
correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
```

**3. Server includes ID in all logs:**
```json
{"correlation_id": "my-custom-id", "event": "request_started", ...}
{"correlation_id": "my-custom-id", "event": "database_query_completed", ...}
{"correlation_id": "my-custom-id", "event": "request_completed", ...}
```

**4. Server returns ID in response headers:**
```
X-Correlation-ID: my-custom-id
```

**5. Client can use ID to search logs**

---

## Integration with Monitoring

### Datadog / New Relic / CloudWatch

JSON logs are automatically parseable by log aggregation tools:

```json
{
  "correlation_id": "a1b2c3d4...",
  "event": "request_completed",
  "duration_seconds": 0.234,
  "status_code": 200
}
```

**Benefits:**
- Automatic field extraction
- Dashboard creation (duration_seconds, status_code)
- Alerting on specific events
- Correlation ID linking across services

### Grafana Loki

**Query Examples:**
```logql
{app="ecommerce-api"} | json | correlation_id="a1b2c3d4..."
{app="ecommerce-api"} | json | event="request_failed"
{app="ecommerce-api"} | json | duration_seconds > 1
```

---

## Best Practices

### 1. Use Event Names (not free-form text)

**Bad:**
```python
logger.info(f"Customer {customer_id} profile loaded successfully")
```

**Good:**
```python
logger.info("customer_profile_loaded", customer_id=customer_id, load_time=0.043)
```

### 2. Always Include Context

**Bad:**
```python
logger.error("Query failed")
```

**Good:**
```python
logger.error("query_failed", query_type="get_customer", customer_id=customer_id, error=str(e))
```

### 3. Use Consistent Field Names

**Bad (inconsistent):**
```python
logger.info("event1", custId="123")
logger.info("event2", customer_id="123")
logger.info("event3", cust="123")
```

**Good (consistent):**
```python
logger.info("event1", customer_id="123")
logger.info("event2", customer_id="123")
logger.info("event3", customer_id="123")
```

### 4. Log at Appropriate Levels

- **DEBUG:** Detailed diagnostic info (disabled in production)
- **INFO:** General informational messages (request completed, data loaded)
- **WARNING:** Something unexpected but not an error (missing optional config)
- **ERROR:** Errors that need attention (API call failed, database error)
- **CRITICAL:** System is unusable (database connection lost)

---

## Performance Impact

**Structured logging overhead:**
- JSON serialization: ~0.1-0.5ms per log entry
- Correlation ID generation: ~0.01ms (UUID4)
- Context injection: ~0.01ms

**Total impact:** <1ms per request (negligible)

**Benefits far outweigh costs:**
- Hours saved debugging production issues
- Easy log aggregation and analysis
- Professional-grade observability

---

## Files Created

- `/backend/middleware/logging_config.py` - Structured logging configuration
- `/backend/main.py` - Updated to use structured logging
- `/STRUCTURED_LOGGING_GUIDE.md` - This document

---

## Next Steps

### Optional Enhancements

1. **Add log sampling** - Log only 10% of successful requests in high-traffic scenarios
2. **Add sensitive data redaction** - Auto-redact credit cards, emails, etc.
3. **Add log rotation** - If writing to files locally
4. **Integrate with log aggregation** - Datadog, New Relic, CloudWatch, Loki

---

## Status

✅ **Implemented and Active**
- Correlation IDs working
- JSON format in production (Railway)
- Console format in development
- Helper functions available
- Updated key log statements in main.py

**Ready for:** Production deployment

**Recommendation:** Deploy and monitor logs in Railway dashboard. You'll immediately see the benefit when debugging issues.
