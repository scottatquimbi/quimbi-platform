# 🚨 Incident Response Runbook

**Platform:** Customer Intelligence API
**Last Updated:** 2025-10-29
**Version:** 1.0

---

## 📞 Emergency Contacts

### On-Call Engineer
- **Primary:** Your Name
- **Phone:** +1-XXX-XXX-XXXX
- **Email:** oncall@yourdomain.com
- **Slack:** @oncall

### Escalation Path
1. **On-Call Engineer** (immediate response)
2. **Technical Lead** (if unresolved in 30 min)
3. **CTO** (if customer-impacting >1 hour)

### Service Providers
- **Railway Support:** support@railway.app
  - Priority Support: <1 hour response
  - Dashboard: https://railway.app/dashboard
- **Anthropic Claude API:** support@anthropic.com
- **Azure SQL Support:** Azure Portal → Support

---

## 🎯 Incident Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| **P0** | Complete outage | 15 minutes | API returns 503 for all requests |
| **P1** | Degraded performance | 1 hour | Response times >2s, high error rate |
| **P2** | Minor issue | 4 hours | Single feature broken, workaround exists |
| **P3** | Cosmetic/planned | 24 hours | Documentation outdated, minor UI bug |

---

## 🔥 P0: Complete System Outage

**Symptoms:**
- Health check fails: `curl https://ecommerce-backend-staging-a14c.up.railway.app/health` → 503
- All API endpoints return errors
- UptimeRobot alert: "API Health Check DOWN"
- Customer reports: "Website is down"

### Diagnosis Steps (5 minutes)

**1. Check Railway Service Status**
```bash
# SSH into Railway
railway login
railway link
railway status

# Expected: "Status: Running"
# If crashed: "Status: Crashed" or "Status: Deploying"
```

**2. Check Recent Logs**
```bash
railway logs --tail 100

# Look for:
# - "error", "exception", "crash", "killed"
# - "Database connection failed"
# - "Out of memory"
# - "Permission denied"
```

**3. Check Health Endpoint (if accessible)**
```bash
curl https://ecommerce-backend-staging-a14c.up.railway.app/health

# If returns JSON with error, service is running but unhealthy
```

### Common Root Causes & Fixes

#### Cause A: Database Connection Failed
**Symptoms in logs:**
```
Error: could not connect to server
FATAL: remaining connection slots reserved
```

**Fix:**
```bash
# 1. Check database status
railway run -- pg_isready -h switchyard.proxy.rlwy.net -p 47164

# 2. If database is down, check Railway dashboard
# Dashboard → Database → Status

# 3. If connection pool exhausted, restart service
railway restart

# 4. Verify recovery
curl https://ecommerce-backend-staging-a14c.up.railway.app/health
```

**Recovery Time:** 2-5 minutes

---

#### Cause B: Out of Memory (OOM)
**Symptoms in logs:**
```
Killed
MemoryError
Container exceeded memory limit
```

**Fix:**
```bash
# 1. Check memory usage in Railway dashboard
# Dashboard → Metrics → Memory

# 2. If consistently >90%, increase memory limit
# Dashboard → Settings → Resources → Memory Limit
# Increase from 512MB → 1GB (or higher)

# 3. Restart service
railway restart

# 4. Monitor memory usage
railway logs | grep -i memory
```

**Prevention:**
- Implement pagination for large queries (Phase 3)
- Monitor memory usage trends
- Set up memory alerts

**Recovery Time:** 5-10 minutes

---

#### Cause C: Environment Variable Missing
**Symptoms in logs:**
```
ADMIN_KEY not set - authentication disabled
DATABASE_URL is required
ANTHROPIC_API_KEY not found
```

**Fix:**
```bash
# 1. Check all required environment variables
railway variables

# Required variables:
# - DATABASE_URL
# - ANTHROPIC_API_KEY
# - ADMIN_KEY
# - ALLOWED_ORIGINS

# 2. Set missing variable
railway variables set VARIABLE_NAME="value"

# 3. Restart service (automatic after variable change)
# Wait 30 seconds for deployment

# 4. Verify
curl https://ecommerce-backend-staging-a14c.up.railway.app/health
```

**Recovery Time:** 2-3 minutes

---

#### Cause D: Failed Deployment
**Symptoms:**
- Recent deployment in Railway dashboard
- Logs show build/startup errors

**Fix:**
```bash
# 1. Check recent deployments
# Railway Dashboard → Deployments → View logs

# 2. Rollback to last working deployment
# Dashboard → Deployments → [Previous deployment] → "Redeploy"

# 3. Verify rollback successful
curl https://ecommerce-backend-staging-a14c.up.railway.app/health

# 4. Investigate failed deployment
railway logs --deployment <deployment-id>
```

**Recovery Time:** 3-5 minutes

---

#### Cause E: Azure SQL Sync Process Hung
**Symptoms in logs:**
```
Sync started...
(no "Sync completed" message for >10 minutes)
```

**Fix:**
```bash
# 1. Check if sync process is running
railway run -- ps aux | grep sync_combined_sales

# 2. Kill hung process
railway run -- pkill -f sync_combined_sales

# 3. Restart service
railway restart

# 4. Verify recovery
curl https://ecommerce-backend-staging-a14c.up.railway.app/health
```

**Prevention:**
- Sync timeout is set to 10 minutes (backend/main.py)
- File locking prevents concurrent syncs

**Recovery Time:** 5-10 minutes

---

### Communication Template (P0)

**Slack/Email:**
```
🚨 P0 INCIDENT: API Outage

Status: INVESTIGATING / IDENTIFIED / RESOLVED
Started: [TIME] UTC
Impact: All API requests failing
ETA: [TIME] or UNKNOWN

Root Cause: [If identified]
Current Action: [What we're doing]

Next Update: [TIME] or "When resolved"

Status Page: https://status.yourdomain.com
```

**Frequency:** Update every 15 minutes until resolved

---

## 🐌 P1: Degraded Performance

**Symptoms:**
- API responds but slowly (>2 seconds)
- Intermittent timeouts
- High error rate (>5% requests fail)
- UptimeRobot alert: "Response time > 2000ms"

### Diagnosis Steps (10 minutes)

**1. Check Response Times**
```bash
# Test endpoint response time
time curl https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/random \
  -H "X-API-Key: $ADMIN_KEY"

# Repeat 5 times to see consistency
# Normal: <500ms
# Degraded: >2000ms
```

**2. Check Prometheus Metrics (if enabled)**
```bash
curl https://ecommerce-backend-staging-a14c.up.railway.app/metrics \
  | grep http_request_duration

# Look for p95/p99 latencies
```

**3. Check Database Connection Pool**
```bash
curl https://ecommerce-backend-staging-a14c.up.railway.app/admin/db/pool \
  -H "X-Admin-Key: $ADMIN_KEY"

# Check if pool is exhausted:
# "checked_out": 30 (if pool_size is 30, this is bad)
```

**4. Check Redis Cache Status**
```bash
curl https://ecommerce-backend-staging-a14c.up.railway.app/admin/cache/stats \
  -H "X-Admin-Key: $ADMIN_KEY"

# Check cache hit rate:
# "hit_rate": 0.75 = GOOD (75%)
# "hit_rate": 0.1 = BAD (10%)
```

### Common Root Causes & Fixes

#### Cause A: Redis Cache Down
**Symptoms:**
- Cache hit rate suddenly drops to 0%
- All queries hit database directly
- Slow but functional

**Fix:**
```bash
# 1. Check Redis connection
railway run redis-cli ping
# Expected: PONG

# 2. If Redis is down, restart it
railway restart redis

# 3. Verify cache working
# Call same endpoint twice, second should be faster
time curl https://.../api/mcp/customer/random -H "X-API-Key: $ADMIN_KEY"
time curl https://.../api/mcp/customer/random -H "X-API-Key: $ADMIN_KEY"
```

**Note:** System works without Redis (graceful degradation), just slower.

**Recovery Time:** 2-5 minutes

---

#### Cause B: Database Connection Pool Exhausted
**Symptoms:**
- Timeouts on database queries
- Logs show "QueuePool limit exceeded"

**Fix:**
```bash
# 1. Check current pool settings
grep "DB_POOL_SIZE" backend/core/database.py
# Current: DB_POOL_SIZE = 30, DB_MAX_OVERFLOW = 20

# 2. Increase pool size via environment variable
railway variables set DB_POOL_SIZE=50
railway variables set DB_MAX_OVERFLOW=30

# 3. Restart service (automatic)
# Wait 30 seconds

# 4. Monitor pool usage
curl https://.../admin/db/pool -H "X-Admin-Key: $ADMIN_KEY"
```

**Recovery Time:** 3-5 minutes

---

#### Cause C: Slow Queries (Missing Indexes)
**Symptoms:**
- Logs show query_duration_ms > 1000
- Specific endpoints consistently slow

**Fix:**
```bash
# 1. Identify slow queries in logs
railway logs | grep "query_duration_ms" | grep -E "[0-9]{4,}" | tail -20

# 2. Check if indexes exist
railway run -- psql $DATABASE_URL -c "\d+ fact_customer_current"
# Look for indexes on commonly queried columns

# 3. If missing, apply indexes
railway run -- psql $DATABASE_URL << 'SQL'
CREATE INDEX CONCURRENTLY idx_customer_ltv
ON fact_customer_current(lifetime_value DESC);
SQL

# 4. Verify improvement
time curl https://.../api/mcp/search -H "X-API-Key: $ADMIN_KEY" \
  -d '{"filters":{"ltv_min":1000}}'
```

**Recovery Time:** 5-10 minutes (index creation can take time)

---

#### Cause D: High Traffic / Rate Limiting
**Symptoms:**
- Many 429 errors
- Logs show "rate_limit_exceeded"

**Fix:**
```bash
# 1. Check which IPs are hitting rate limits
railway logs | grep "rate_limit_exceeded" | tail -50

# 2. If legitimate traffic, increase rate limits
# Edit: backend/main.py rate limit decorators

# 3. If abuse, block IP in Railway
# Dashboard → Networking → IP Allowlist

# 4. Deploy changes
git add backend/main.py
git commit -m "Increase rate limits for legitimate traffic"
railway up
```

**Recovery Time:** 5-10 minutes

---

### Communication Template (P1)

**Slack/Email:**
```
⚠️ P1 INCIDENT: Degraded Performance

Status: INVESTIGATING / IDENTIFIED / MONITORING
Started: [TIME] UTC
Impact: API responses slower than normal (>2s)
Customer Impact: MINOR / MODERATE

Root Cause: [If identified]
Current Action: [What we're doing]

Workaround: System is functional, just slower
Next Update: [TIME]
```

**Frequency:** Update every 30 minutes

---

## ❌ P2: Customer Data Issues

**Symptoms:**
- Customer reports: "My data looks wrong"
- Churn prediction doesn't match reality
- LTV is outdated
- Orders not showing up

### Diagnosis Steps (15 minutes)

**1. Check Data Freshness**
```bash
curl https://ecommerce-backend-staging-a14c.up.railway.app/health | jq '.data_status'

# Check:
# - "last_sync_at": timestamp
# - "customers_loaded": count
# - If last_sync_at > 24 hours ago, data is stale
```

**2. Check Sync Logs**
```bash
railway logs | grep "sync" | tail -50

# Look for:
# - "✅ Sync completed" (success)
# - "❌ Sync failed" (failure)
# - Errors connecting to Azure SQL
```

**3. Verify Customer Data**
```bash
# Look up specific customer
curl https://.../api/mcp/customer/{customer_id} \
  -H "X-API-Key: $ADMIN_KEY"

# Check:
# - lifetime_value matches expected
# - total_orders matches expected
# - days_since_last_purchase reasonable
```

### Fix: Manual Data Sync

```bash
# 1. Trigger manual sync
curl -X POST https://.../admin/sync-sales \
  -H "X-Admin-Key: $ADMIN_KEY"

# Response:
# {"status": "sync_started", "message": "..."}

# 2. Monitor sync progress (takes 2-10 minutes)
railway logs --tail

# Look for:
# "sync_started"
# "Processing batch..."
# "sync_completed" or "sync_failed"

# 3. Verify data updated
curl https://.../health | jq '.data_status.last_sync_at'

# 4. Check customer data again
curl https://.../api/mcp/customer/{customer_id} \
  -H "X-API-Key: $ADMIN_KEY"
```

**Recovery Time:** 10-15 minutes

---

### Fix: Azure SQL Connection Issues

**Symptoms in logs:**
```
Error connecting to Azure SQL
Login failed for user
Network path not found
```

**Fix:**
```bash
# 1. Test Azure SQL connection
railway run -- python3 -c "
import pymssql
import os
conn = pymssql.connect(
    server=os.getenv('AZURE_SQL_SERVER'),
    user=os.getenv('AZURE_SQL_USERNAME'),
    password=os.getenv('AZURE_SQL_PASSWORD'),
    database=os.getenv('AZURE_SQL_DATABASE')
)
print('✅ Azure SQL connection OK')
conn.close()
"

# 2. If fails, check environment variables
railway variables | grep AZURE_SQL

# 3. Check Azure SQL firewall rules
# Azure Portal → SQL Database → Networking → Firewall
# Ensure Railway IP ranges are allowed

# 4. If credentials wrong, update
railway variables set AZURE_SQL_PASSWORD="correct_password"
```

**Recovery Time:** 10-20 minutes

---

## 🔐 P2: Authentication Issues

**Symptoms:**
- Customer reports: "API key doesn't work"
- 401 errors in logs
- "Invalid or inactive API key"

### Diagnosis Steps

**1. Verify API Key Exists**
```bash
# Customer provides their API key (first 10 chars only for security)
# Check logs for validation attempts
railway logs | grep "invalid_api_key_attempted" | tail -20
```

**2. Test API Key**
```bash
# Test with customer's API key
curl https://.../api/mcp/customer/random \
  -H "X-API-Key: sk_customer_provided_key"

# Expected: 200 OK with customer data
# If 401: API key invalid
# If 403: API key valid but unauthorized
```

### Fix: Verify/Reset API Key

```bash
# Current implementation uses ADMIN_KEY for all customers
# Check current ADMIN_KEY
railway variables | grep ADMIN_KEY

# If customer is using old/wrong key, provide correct one:
echo $ADMIN_KEY

# Send to customer via secure channel (NOT email/Slack)
```

**Note:** For production multi-tenant, implement database-backed API keys (Phase 2)

**Recovery Time:** 5-10 minutes

---

## 📊 Post-Incident Review

**Complete within 48 hours of incident resolution:**

### 1. Document Incident

Create file: `incidents/YYYY-MM-DD-incident-name.md`

```markdown
# Incident: [Name]

**Date:** YYYY-MM-DD
**Severity:** P0 / P1 / P2
**Duration:** [START] - [END] ([DURATION])
**Status:** RESOLVED

## Timeline

- HH:MM - Incident detected (how?)
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix applied
- HH:MM - Service recovered
- HH:MM - Incident closed

## Impact

- **Users Affected:** [NUMBER or "All"]
- **Services Affected:** [List]
- **Data Loss:** Yes / No
- **Financial Impact:** $[AMOUNT] or N/A

## Root Cause

[Detailed explanation of what went wrong]

## Resolution

[What we did to fix it]

## Prevention

[Action items to prevent recurrence]

- [ ] Action item 1 (Owner: Name, Due: Date)
- [ ] Action item 2 (Owner: Name, Due: Date)
```

### 2. Update Runbook

If incident revealed gaps in runbook:
- Add new scenario
- Update diagnosis steps
- Add prevention measures

### 3. Blameless Postmortem

Schedule 30-minute meeting with team:
- What happened?
- What went well?
- What could be improved?
- Action items (with owners and dates)

---

## 🎯 Service Level Objectives (SLOs)

### Availability
- **Target:** 99.5% uptime per month
- **Measurement:** HTTP 200/201 responses to /health
- **Downtime Budget:** 43 minutes per month
- **Current Status:** Check https://status.yourdomain.com

### Response Time
- **Target (P95):** <500ms for standard endpoints
- **Target (P99):** <2000ms for standard endpoints
- **Target (NL Queries):** <3000ms for AI-powered queries

### Error Rate
- **Target:** <1% of requests return 5xx errors
- **Measurement:** Count(5xx) / Count(all requests)

### Data Freshness
- **Target:** Customer data synced within 24 hours
- **Measurement:** Time since last successful sync

---

## 🛠️ Useful Commands Reference

### Railway CLI
```bash
# Login
railway login

# Link to project
railway link

# View logs
railway logs --tail 100
railway logs --follow

# Check status
railway status

# Restart service
railway restart

# Run command in Railway environment
railway run -- [command]

# View environment variables
railway variables

# Set environment variable
railway variables set KEY="value"

# Deploy
railway up
```

### Database Queries
```bash
# Connect to database
railway run -- psql $DATABASE_URL

# Check table sizes
railway run -- psql $DATABASE_URL -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Check active connections
railway run -- psql $DATABASE_URL -c "
SELECT count(*), state
FROM pg_stat_activity
GROUP BY state;
"
```

### Health Checks
```bash
# Basic health check
curl https://ecommerce-backend-staging-a14c.up.railway.app/health

# Database connection
railway run -- pg_isready -h switchyard.proxy.rlwy.net -p 47164

# Redis connection
railway run redis-cli ping

# Check cache stats
curl https://.../admin/cache/stats -H "X-Admin-Key: $ADMIN_KEY"

# Check DB pool
curl https://.../admin/db/pool -H "X-Admin-Key: $ADMIN_KEY"
```

---

## 📚 Related Documentation

- **Troubleshooting Guide:** [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Daily Operations SOP:** [docs/SOP_DAILY_OPERATIONS.md](docs/SOP_DAILY_OPERATIONS.md)
- **API Documentation:** [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Deployment Guide:** [.ai-docs/api/DEPLOYMENT_GUIDE.md](.ai-docs/api/DEPLOYMENT_GUIDE.md)

---

## 🔄 Runbook Maintenance

**Review Schedule:** Monthly
**Owner:** On-Call Engineer
**Last Review:** 2025-10-29

**Update Triggers:**
- After each P0/P1 incident
- When new services added
- When infrastructure changes
- When contact information changes

---

**Version History:**

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-10-29 | Initial runbook | Claude |
