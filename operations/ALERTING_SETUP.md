# 🚨 Alerting Setup Guide

**Platform:** Customer Intelligence API
**Last Updated:** 2025-10-29
**Status:** Ready for Configuration

---

## Overview

This guide sets up a 3-tier alerting system:

1. **Tier 1: UptimeRobot** (Free) - External health monitoring
2. **Tier 2: Railway Email Alerts** (Free) - Infrastructure alerts
3. **Tier 3: Slack Webhooks** (Optional) - Real-time error notifications

**Total Cost:** $0 (free tier) or $7/month (UptimeRobot Pro)

---

## 🎯 Alert Types & SLOs

| Alert | Threshold | Response Time | Channel |
|-------|-----------|---------------|---------|
| **API Down** | Health check fails | 15 min | Email + SMS |
| **High Latency** | P95 > 2s | 1 hour | Email |
| **High Error Rate** | 5xx > 5% | 1 hour | Email + Slack |
| **Database Down** | Connection fails | 15 min | Email + SMS |
| **Memory High** | Usage > 90% | 4 hours | Email |
| **Deployment Failed** | Build error | 30 min | Email |

---

## 1️⃣ Tier 1: UptimeRobot Setup (External Monitoring)

### Why UptimeRobot?
- ✅ Free tier: 50 monitors, 5-minute checks
- ✅ Email + SMS alerts
- ✅ Public status page
- ✅ Independent of Railway (detects full outages)

### Setup Steps (10 minutes)

**Step 1: Create Account**
```
1. Visit: https://uptimerobot.com/signUp
2. Sign up with work email
3. Verify email
```

**Step 2: Add Health Check Monitor**
```
Monitor Type: HTTP(s)
Friendly Name: Customer Intelligence API - Health
URL: https://ecommerce-backend-staging-a14c.up.railway.app/health
Monitoring Interval: 5 minutes (free tier)
Monitor Timeout: 30 seconds

Alert Contacts:
- Email: your-email@domain.com
- SMS: +1-XXX-XXX-XXXX (optional, pro tier)

Expected Response:
- HTTP Status: 200
- Keyword: "healthy" (monitors JSON response)
```

**Step 3: Add Response Time Monitor**
```
Monitor Type: HTTP(s)
Friendly Name: Customer Intelligence API - Response Time
URL: https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/random
Monitoring Interval: 10 minutes
Monitor Timeout: 30 seconds

Alert When:
- Response time > 2000ms (triggers alert)
- Response time > 5000ms (critical alert)

Note: This endpoint requires authentication
Add custom header:
- Header: X-API-Key
- Value: [Your ADMIN_KEY]
```

**Step 4: Configure Alert Timing**
```
Alert When Down For: 2 minutes
- Prevents false positives from transient errors
- Alerts after 2 consecutive failed checks (10 minutes total)

Alert When Up Again: Immediate
- Confirms recovery quickly
```

**Step 5: Create Status Page (Optional)**
```
Dashboard → Status Pages → Create
Name: Customer Intelligence API Status
URL: [your-subdomain].betteruptime.com (or custom domain)

Add Monitors:
- Health Check Monitor
- Response Time Monitor

Enable:
✅ Show uptime percentage
✅ Show response time graph
✅ Show incident history
✅ Allow email subscriptions
```

**Step 6: Test Alerts**
```
1. Click monitor → "Test Alert"
2. Verify you receive email
3. Check spam folder if not received
```

### Expected Alerts

**Scenario: API Down**
```
Subject: [Down] Customer Intelligence API - Health
Body:
Your monitor "Customer Intelligence API - Health" is DOWN.

URL: https://ecommerce-backend-staging-a14c.up.railway.app/health
Error: HTTP 503 Service Unavailable
Last checked: 2025-10-29 12:34:56 UTC

View details: [link]
```

**Scenario: High Latency**
```
Subject: [Slow] Customer Intelligence API - Response Time
Body:
Your monitor is responding slowly.

URL: https://.../api/mcp/customer/random
Response time: 3,245 ms (threshold: 2,000 ms)
Last checked: 2025-10-29 12:34:56 UTC
```

---

## 2️⃣ Tier 2: Railway Email Alerts (Infrastructure)

### Setup Steps (5 minutes)

**Step 1: Configure Railway Notifications**
```
1. Visit: https://railway.app/dashboard
2. Select project: unified-segmentation-ecommerce
3. Settings → Notifications

Enable alerts for:
✅ Deployment Failed
✅ Service Crashed
✅ High Memory Usage (>80%)
✅ High CPU Usage (>90%)
✅ Build Failed

Email: your-email@domain.com
```

**Step 2: Set Memory Threshold**
```
Settings → Resources
Memory Alert Threshold: 80%
Current Limit: 1GB (adjust based on usage)

Alert when memory usage exceeds 800MB for 5+ minutes
```

**Step 3: Configure Deployment Notifications**
```
Settings → Deployments
Notify on:
✅ Deployment started
✅ Deployment succeeded
✅ Deployment failed (CRITICAL)

Slack Integration (optional):
- Webhook URL: [Your Slack webhook]
- Channel: #deployments
```

### Expected Alerts

**Scenario: Service Crashed**
```
Subject: [Railway] Service Crashed - unified-segmentation-ecommerce
Body:
Your service "web" has crashed.

Project: unified-segmentation-ecommerce
Environment: production
Exit Code: 137 (OOM kill)
Timestamp: 2025-10-29 12:34:56 UTC

View logs: [link to Railway dashboard]
```

**Scenario: Deployment Failed**
```
Subject: [Railway] Deployment Failed - unified-segmentation-ecommerce
Body:
Your deployment has failed.

Reason: Build error
Exit Code: 1

Error: ModuleNotFoundError: No module named 'xyz'

View build logs: [link]
```

---

## 3️⃣ Tier 3: Slack Webhooks (Real-Time Errors)

### Why Slack Webhooks?
- ✅ Real-time error notifications
- ✅ Team visibility
- ✅ Rich formatting with context
- ✅ Free (no cost)

### Setup Steps (10 minutes)

**Step 1: Create Slack Incoming Webhook**
```
1. Visit: https://api.slack.com/messaging/webhooks
2. Click "Create your Slack app"
3. Choose workspace
4. App Name: "Customer Intelligence Alerts"
5. Click "Incoming Webhooks" → Enable
6. Click "Add New Webhook to Workspace"
7. Choose channel: #alerts (or create new)
8. Copy webhook URL: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX
```

**Step 2: Add Webhook to Railway**
```bash
railway variables set SLACK_ALERTS_WEBHOOK="https://hooks.slack.com/services/..."
```

**Step 3: Verify Webhook Exists in Code**

Check that webhook notification is implemented:
```bash
grep -r "SLACK_ALERTS_WEBHOOK" backend/
```

The system already has Slack notification infrastructure, just needs the webhook URL configured.

**Step 4: Test Slack Alerts**
```bash
# Test alert manually
curl -X POST "$SLACK_ALERTS_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "🧪 Test Alert from Customer Intelligence API",
    "attachments": [{
      "color": "warning",
      "title": "Test Alert",
      "text": "If you see this, Slack alerts are working!",
      "footer": "Customer Intelligence API",
      "ts": '$(date +%s)'
    }]
  }'
```

### Alert Examples

**Error Alert in Slack:**
```
🚨 ERROR: Unhandled Exception

Path: /api/mcp/customer/12345
Method: GET
Error: CustomerNotFoundError
Message: Customer 12345 not found

Correlation ID: req_abc123xyz
Timestamp: 2025-10-29 12:34:56 UTC

View logs: [Railway dashboard link]
```

**High Error Rate Alert:**
```
⚠️ WARNING: High Error Rate Detected

Error rate: 8.3% (threshold: 5%)
Time window: Last 5 minutes
Total requests: 1,234
Failed requests: 103

Top errors:
- 500 Internal Server Error (45)
- 503 Service Unavailable (38)
- 504 Gateway Timeout (20)

Action required: Check Railway logs
```

---

## 4️⃣ Optional: Enable Prometheus Metrics

### Why Prometheus?
- Advanced metrics (percentiles, histograms)
- Grafana dashboards
- Custom alert rules
- Historical data analysis

### Setup Steps (5 minutes)

**Step 1: Enable Metrics in Railway**
```bash
railway variables set ENABLE_PROMETHEUS_METRICS=true
railway restart
```

**Step 2: Verify Metrics Endpoint**
```bash
curl https://ecommerce-backend-staging-a14c.up.railway.app/metrics

# Expected output:
# TYPE http_requests_total counter
# http_requests_total{method="GET",endpoint="/health",status_code="200"} 1234
# ...
```

**Step 3: Add Grafana Cloud (Optional)**

**Free Tier Limits:**
- 10K series
- 14-day retention
- 50GB logs
- Free forever

**Setup:**
```
1. Visit: https://grafana.com/auth/sign-up/create-user
2. Create account
3. Click "Add data source" → Prometheus
4. URL: https://ecommerce-backend-staging-a14c.up.railway.app/metrics
5. Click "Save & Test"
```

**Pre-built Dashboard:**
```
1. Import dashboard: ID 1860 (FastAPI monitoring)
2. Or create custom dashboard:
   - Request rate
   - Error rate
   - Response time (P50, P95, P99)
   - Cache hit rate
   - Database connection pool
```

**Step 4: Configure Grafana Alerts (Optional - Paid tier)**
```
Alert: High Error Rate
Query: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.05
Threshold: 5% error rate
Notification: Email + Slack
Frequency: Check every 1 minute
```

---

## 🧪 Testing Your Alerts

### Test 1: API Down Alert
```bash
# Simulate outage by stopping Railway service
railway down

# Wait 5-10 minutes for UptimeRobot to detect
# Expected: Email alert "API Down"

# Restore service
railway up

# Expected: Email alert "API Up"
```

### Test 2: High Latency Alert
```bash
# Simulate slow response by adding artificial delay
# (requires code change - not recommended for production)

# Or: Trigger slow query
curl https://.../api/mcp/search \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{"filters":{"complex_query":true}}'

# Monitor response time in UptimeRobot
```

### Test 3: Memory Alert
```bash
# Check current memory usage
curl https://.../admin/system/metrics -H "X-Admin-Key: $ADMIN_KEY"

# Memory alerts trigger automatically when >80%
# Railway will send email
```

### Test 4: Slack Error Alert
```bash
# Trigger an error deliberately
curl https://.../api/mcp/customer/INVALID_ID \
  -H "X-API-Key: $ADMIN_KEY"

# Check Slack channel for error notification
# (requires Slack webhook configured)
```

---

## 📊 Alert Dashboard (Recommended)

Create a simple alert dashboard for visibility:

**Google Sheets / Notion Dashboard:**
```
| Alert Type | Last Triggered | Status | Response Time |
|------------|----------------|--------|---------------|
| API Down | Never | ✅ OK | N/A |
| High Latency | 2025-10-28 | ✅ OK | 15 min |
| High Error Rate | 2025-10-25 | ✅ OK | 30 min |
| Memory High | Never | ✅ OK | N/A |

Total Incidents (30 days): 2
Average MTTR: 22.5 minutes
Current Uptime: 99.87%
```

---

## 🔔 Alert Fatigue Prevention

### Best Practices

**1. Tune Thresholds**
```
Don't alert on:
- Single errors (wait for pattern)
- Transient spikes (<2 minutes)
- Known maintenance windows

Do alert on:
- Sustained issues (>5 minutes)
- Customer-impacting errors
- SLO breaches
```

**2. Use Alert Aggregation**
```
Instead of: 100 alerts for 100 errors
Send: "High error rate: 100 errors in 5 minutes"

Aggregate by:
- Time window (5 min, 15 min)
- Error type
- Severity level
```

**3. Maintenance Windows**
```
Before planned maintenance:
1. Announce in Slack: "#alerts: Maintenance 2-3pm UTC"
2. Pause UptimeRobot monitors (or increase threshold)
3. Resume after maintenance
```

**4. On-Call Rotation**
```
Week 1: Engineer A (primary) + Engineer B (backup)
Week 2: Engineer B (primary) + Engineer C (backup)

Document in:
- Slack channel topic: "#alerts - On-call: @engineerA"
- PagerDuty (if using)
```

---

## 📈 Monitoring What Matters

### Key Metrics to Monitor

**1. The Four Golden Signals** (Google SRE)
```
Latency:     How long requests take
Traffic:     How many requests
Errors:      Rate of failed requests
Saturation:  How "full" is your service (CPU, memory, disk)
```

**2. Application-Specific Metrics**
```
Data Freshness:   Time since last sync (<24 hours)
Cache Hit Rate:   % of requests served from cache (>50%)
Auth Failures:    Rate of invalid API keys (<1%)
AI Query Latency: Claude API response time (<3s)
```

**3. Business Metrics (Optional)**
```
Active API Keys:      Track customer usage
Queries per Day:      Understand load patterns
Top Error Types:      Prioritize fixes
Revenue at Risk:      High-value customer errors
```

---

## 🚀 Quick Start Checklist

**Complete these in order (30 minutes total):**

- [ ] **UptimeRobot Setup** (10 min)
  - [ ] Create account
  - [ ] Add health check monitor
  - [ ] Add response time monitor
  - [ ] Test alerts

- [ ] **Railway Alerts** (5 min)
  - [ ] Enable deployment notifications
  - [ ] Enable crash notifications
  - [ ] Set memory threshold (80%)

- [ ] **Slack Webhooks** (10 min)
  - [ ] Create incoming webhook
  - [ ] Add to Railway environment
  - [ ] Test with curl
  - [ ] Verify messages in Slack

- [ ] **Documentation** (5 min)
  - [ ] Update INCIDENT_RUNBOOK.md with contact info
  - [ ] Add alert URLs to README.md
  - [ ] Document on-call rotation

---

## 📞 Alert Contact Information

**Update these with real values:**

```bash
# Add to Railway environment variables
railway variables set ALERT_EMAIL="oncall@yourdomain.com"
railway variables set ALERT_PHONE="+1-XXX-XXX-XXXX"
railway variables set SLACK_ALERTS_WEBHOOK="https://hooks.slack.com/..."
```

**Document in team wiki:**
```
Primary On-Call: [Name] - [Phone] - [Email]
Backup On-Call: [Name] - [Phone] - [Email]
Escalation: CTO - [Phone] - [Email]

Alert Channels:
- Email: oncall@yourdomain.com
- Slack: #alerts
- SMS: +1-XXX-XXX-XXXX (UptimeRobot Pro)

Status Page: https://[your-subdomain].betteruptime.com
UptimeRobot Dashboard: https://uptimerobot.com/dashboard
Railway Dashboard: https://railway.app/project/[your-project-id]
```

---

## 🔄 Maintenance

**Monthly Review:**
- Check alert fatigue (too many false positives?)
- Review incident response times
- Update thresholds based on traffic patterns
- Test alert delivery

**Quarterly Review:**
- Evaluate alerting costs (consider paid tiers?)
- Review SLOs (too strict? too loose?)
- Update runbook with new scenarios
- Train team on incident response

---

## 📚 Related Documentation

- **Incident Runbook:** [INCIDENT_RUNBOOK.md](INCIDENT_RUNBOOK.md)
- **Monitoring Strategy:** [MONITORING_STRATEGY.md](MONITORING_STRATEGY.md)
- **SOP Daily Operations:** [docs/SOP_DAILY_OPERATIONS.md](docs/SOP_DAILY_OPERATIONS.md)

---

## ✅ Success Criteria

**Your alerting is working when:**

1. ✅ You receive email within 10 minutes of API downtime
2. ✅ UptimeRobot shows 99%+ uptime
3. ✅ Slack receives error notifications in real-time
4. ✅ Railway alerts on deployment failures
5. ✅ False positive rate <5% (no alert fatigue)
6. ✅ Mean time to detect (MTTD) <10 minutes
7. ✅ Mean time to respond (MTTR) <30 minutes

---

**Last Updated:** 2025-10-29
**Next Review:** 2025-11-29
**Owner:** On-Call Engineer
