# Monitoring Strategy

**Date:** October 28, 2025
**Status:** Implemented (Optional Prometheus + Railway Built-in)

---

## Overview

The platform uses a **hybrid monitoring approach**:

1. **Railway Built-in Monitoring** (Always Active) - Infrastructure metrics
2. **Prometheus Metrics** (Optional) - Application-level observability

---

## Railway Built-in Monitoring ✅

**What Railway Provides:**
- CPU usage
- Memory usage
- Network I/O
- Disk usage
- Deployment logs
- Container restarts
- HTTP response codes (basic)

**Access:** Railway Dashboard → Your Service → Metrics tab

**Best For:**
- MVP and initial deployments
- Infrastructure health monitoring
- Cost-effective for small scale
- Zero configuration needed

**Limitations:**
- No application-specific metrics (endpoint performance, database query times)
- No custom business metrics (churn predictions, LTV percentiles)
- No integration tracking (Slack/Gorgias call durations)
- Limited alerting capabilities

---

## Prometheus Metrics (Optional) 🔧

**Enable with:**
```bash
railway variables set ENABLE_PROMETHEUS_METRICS=true
railway up
```

### What You Get

**Application Metrics:**
- Request duration by endpoint
- Request count by status code
- Requests currently in progress
- Error rates by endpoint

**Database Metrics:**
- Query duration by type
- Active connections
- Query errors by type

**Cache Metrics:**
- Hit/miss rates by cache type
- Cache performance

**AI/Integration Metrics:**
- Claude API call duration
- Token usage tracking
- Slack/Gorgias call performance
- Integration error rates

**Business Metrics:**
- Customers loaded count
- Archetypes loaded count
- High-risk churn customers
- Customer LTV percentiles

**MCP Tool Metrics:**
- Tool call counts by name
- Tool execution duration
- Success vs error rates

### Accessing Metrics

**1. Direct Access**
```bash
# View raw Prometheus metrics
curl https://your-app.railway.app/metrics
```

**2. Grafana Cloud (Optional)**

Free tier: 10K series, 14-day retention
```bash
# Add to Grafana Cloud data sources:
URL: https://your-app.railway.app/metrics
```

**3. Self-Hosted Prometheus**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'ecommerce-api'
    static_configs:
      - targets: ['your-app.railway.app']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

---

## Recommended Approach by Stage

### Stage 1: MVP / Testing (Recommended: Railway Only)
**Use:** Railway built-in monitoring
**Cost:** $0 (included)
**Setup:** None needed
**Rationale:** Infrastructure metrics sufficient for small scale

### Stage 2: Pilot Customers (Recommended: Railway + Basic Prometheus)
**Use:** Railway + Prometheus endpoint (no external scraper)
**Cost:** $0 (metrics endpoint only)
**Setup:** `ENABLE_PROMETHEUS_METRICS=true`
**Rationale:** Application metrics available on-demand via `/metrics` endpoint

### Stage 3: Production (Recommended: Railway + Prometheus + Grafana)
**Use:** Full observability stack
**Cost:** ~$0-29/month (Grafana Cloud free tier or self-hosted)
**Setup:** Prometheus + Grafana + alerting
**Rationale:** Enterprise-grade observability with alerts

---

## Cost Comparison

| Solution | Monthly Cost | Features |
|----------|--------------|----------|
| **Railway Only** | $0 (included) | Infrastructure metrics |
| **Railway + Prometheus Endpoint** | $0 | + Application metrics (manual check) |
| **Railway + Grafana Cloud Free** | $0 | + Dashboards, 10K series, 14d retention |
| **Railway + Grafana Cloud Paid** | $29+ | + Alerting, longer retention, more series |
| **Railway + Self-Hosted** | $5-20 | + Full control (VPS cost) |

---

## Key Metrics to Monitor

### For Support/Operations

**Critical:**
- `http_requests_total{status_code="500"}` - Server errors
- `http_request_duration_seconds{quantile="0.95"}` - P95 latency
- `db_connections_total` - Database connection pool usage

**Important:**
- `integration_errors_total` - Slack/Gorgias failures
- `ai_query_errors_total` - Claude API issues

### For Product/Business

**Critical:**
- `customers_loaded_total` - Data freshness
- `churn_predictions_high_risk` - Customers at risk

**Important:**
- `mcp_tool_calls_total` - Feature usage
- `cache_hit_rate` - Performance optimization

### For Development

**Critical:**
- `http_request_duration_seconds` - Endpoint performance
- `db_query_duration_seconds` - Query optimization needs

**Important:**
- `ai_tokens_used_total` - Cost tracking
- `cache_misses_total` - Caching effectiveness

---

## Sample Grafana Dashboard Queries

### Request Rate (requests/second)
```promql
rate(http_requests_total[5m])
```

### Error Rate (%)
```promql
rate(http_requests_total{status_code=~"5.."}[5m]) /
rate(http_requests_total[5m]) * 100
```

### P95 Request Duration
```promql
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket[5m])
)
```

### Cache Hit Rate
```promql
cache_hit_rate{cache_type="customer_profiles"}
```

### AI Token Cost Estimate
```promql
sum(rate(ai_tokens_used_total[1h])) * 0.000001  # Assuming $1/1M tokens
```

---

## Alerting Rules (If Using Prometheus + Alertmanager)

### Critical Alerts

**High Error Rate**
```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "Error rate above 5% for 5 minutes"
```

**Database Connection Pool Exhausted**
```yaml
- alert: DatabasePoolExhausted
  expr: db_connections_total > 18  # Max pool size is 20
  for: 2m
  annotations:
    summary: "Database connection pool near capacity"
```

**High Churn Risk Count**
```yaml
- alert: HighChurnRiskCustomers
  expr: churn_predictions_high_risk > 100
  for: 1h
  annotations:
    summary: "Over 100 customers at high churn risk"
```

---

## Performance Optimization with Metrics

### Identify Slow Endpoints
```promql
topk(5,
  histogram_quantile(0.95,
    rate(http_request_duration_seconds_bucket[1h])
  )
) by (endpoint)
```

### Find Cache Opportunities
```promql
topk(5,
  sum(rate(db_query_duration_seconds_count[1h])) by (query_type)
)
```

### Track AI Cost
```promql
sum(ai_tokens_used_total) by (model, type)
```

---

## Implementation Status

### ✅ Completed
- Prometheus metrics module created
- All metric types defined (HTTP, DB, Cache, AI, Integration, MCP, Business)
- Middleware for automatic request tracking
- Helper functions for manual tracking
- Optional via `ENABLE_PROMETHEUS_METRICS` environment variable
- No-op when disabled (zero performance impact)

### 🟡 To-Do (Optional)
- Integrate metrics calls into existing endpoints
- Add Grafana dashboard JSON
- Configure alerting rules
- Set up Prometheus scraper (if using external monitoring)

---

## Recommendation

**For Your Use Case:**

**Now (MVP):** Use Railway only
- Set `ENABLE_PROMETHEUS_METRICS=false` (default)
- Monitor via Railway dashboard
- Cost: $0, Setup: 0 minutes

**Later (Production):** Enable Prometheus
- Set `ENABLE_PROMETHEUS_METRICS=true`
- Add Grafana Cloud free tier
- Cost: $0, Setup: 15 minutes

**Future (Scale):** Full observability
- Keep Prometheus enabled
- Upgrade to Grafana Cloud paid or self-host
- Add alerting rules
- Cost: $0-29/month, Setup: 2-4 hours

---

## Files Created

- `/backend/middleware/metrics.py` - Prometheus metrics definitions and helpers
- `/MONITORING_STRATEGY.md` - This document

---

## Next Steps

1. **Test metrics module:** Verify it compiles without errors
2. **Integrate into main.py:** Add middleware and metric tracking calls
3. **Deploy with metrics disabled:** Default Railway monitoring
4. **Enable when needed:** `ENABLE_PROMETHEUS_METRICS=true` for production

---

**Decision:** Start with Railway's built-in monitoring (sufficient for MVP), enable Prometheus later when you need application-level insights for optimization and debugging.
