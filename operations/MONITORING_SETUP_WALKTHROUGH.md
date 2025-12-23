# Monitoring Setup Walkthrough

**Total Time:** ~2 hours (including testing)
**Difficulty:** Beginner-friendly
**Requirements:** Railway project, Slack workspace, email access

---

## Overview

This guide sets up a **3-tier monitoring system**:

1. **Tier 1: UptimeRobot** - External health monitoring
2. **Tier 2: Railway Alerts** - Infrastructure alerts
3. **Tier 3: Slack Webhooks** - Real-time error notifications

By the end, you'll have:
- ✅ Email/SMS alerts when your API goes down
- ✅ Notifications for deployment failures
- ✅ Real-time Slack messages for errors
- ✅ Public status page for customers
- ✅ <10 minute detection time for issues

---

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Railway account with deployed project
- [ ] Slack workspace (free tier works)
- [ ] Email address for alerts
- [ ] (Optional) Phone number for SMS alerts
- [ ] ~2 hours of time

---

## Tier 1: UptimeRobot Setup (30 minutes)

### Step 1: Create Account (5 minutes)

1. Go to https://uptimerobot.com
2. Click **"Sign Up Free"**
3. Fill in:
   - Email
   - Password
   - Name
4. Click **"Create Account"**
5. Verify email (check inbox)
6. Log in to dashboard

**✅ Checkpoint:** You should see the UptimeRobot dashboard

---

### Step 2: Add Health Check Monitor (10 minutes)

1. Click **"+ Add New Monitor"** (big blue button)

2. **Monitor Configuration:**
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** `Customer Intelligence API - Health`
   - **URL (or IP):** `https://ecommerce-backend-staging-a14c.up.railway.app/health`
   - **Monitoring Interval:** 5 minutes
   - **Monitor Timeout:** 30 seconds

3. **Alert Settings:**
   - Click **"Advanced Settings"**
   - **Keyword Monitoring:** Select "Alert if keyword exists"
   - **Keyword:** `healthy`
   - **Keyword Type:** Exists
   - This ensures the API returns `{"status":"healthy",...}`, not just any 200 response

4. **Alert Contacts:**
   - Your email should be pre-filled
   - To add SMS: Click "Add Alert Contact" → Mobile Phone → Enter number
   - Select notification method: **Email** (or Email + SMS)

5. Click **"Create Monitor"** (green button)

**✅ Checkpoint:** Monitor status should show "Up" with green checkmark

---

### Step 3: Add Performance Monitor (10 minutes)

1. Click **"+ Add New Monitor"** again

2. **Monitor Configuration:**
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** `Customer Intelligence API - Performance`
   - **URL:** `https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/random`
   - **Monitoring Interval:** 5 minutes
   - **Monitor Timeout:** 30 seconds

3. **Authentication Header:**
   - Click **"Advanced Settings"**
   - Scroll to **"Custom HTTP Headers"**
   - Click **"Add Header"**
   - **Name:** `X-API-Key`
   - **Value:** Get your ADMIN_KEY from Railway:

```bash
# In terminal:
railway variables | grep ADMIN_KEY

# Copy the value after ADMIN_KEY=
```

4. **Response Time Alert:**
   - In Advanced Settings, find **"Response Time Alert"**
   - Check **"Alert if response time is greater than"**
   - Enter: `2000` (milliseconds = 2 seconds)

5. **Alert Contacts:**
   - Select your email

6. Click **"Create Monitor"**

**✅ Checkpoint:** Both monitors showing "Up" status

---

### Step 4: Create Public Status Page (5 minutes)

1. In left sidebar, click **"Status Pages"**
2. Click **"+ Add Status Page"**

3. **Configuration:**
   - **Status Page Name:** `Customer Intelligence Platform Status`
   - **URL:** Choose subdomain (e.g., `yourcompany-status` → `yourcompany-status.uptimerobot.com`)
   - **Select Monitors:** Check BOTH monitors you created
   - **Custom Domain:** (Optional - requires DNS setup)

4. **Appearance:**
   - **Show Uptime:** Yes (shows % uptime)
   - **Show Response Times:** Yes (shows performance chart)
   - **Auto-Refresh:** 60 seconds

5. Click **"Create Status Page"**

6. **Copy the status page URL** - it looks like:
   ```
   https://yourcompany-status.uptimerobot.com
   ```

7. **Share with customers** (optional):
   - Add link to your docs: "Check system status: [link]"
   - Include in support emails

**✅ Checkpoint:** Status page loads and shows both monitors

---

### Test UptimeRobot (Optional - 5 minutes)

**Test downtime detection:**

1. In Railway, temporarily stop your service:
   ```bash
   railway down  # Stop service
   ```

2. Wait 5-10 minutes

3. Check email - you should receive:
   ```
   Subject: [UptimeRobot] Customer Intelligence API - Health is DOWN

   Your monitor is DOWN:
   Friendly Name: Customer Intelligence API - Health
   URL: https://...railway.app/health
   Reason: HTTP 503 - Service Unavailable
   ```

4. Restart service:
   ```bash
   railway up
   ```

5. Within 5 minutes, receive "UP" email

**⚠️ Skip this test if you have live customers**

---

## Tier 2: Railway Alerts (15 minutes)

### Step 1: Navigate to Railway Project (2 minutes)

1. Go to https://railway.app
2. Log in
3. Select project: **"ecommerce-backend-staging-a14c"** (or your project name)
4. Click on your service (the FastAPI backend)

---

### Step 2: Enable Deployment Alerts (5 minutes)

1. Click **"Settings"** tab (gear icon)
2. Scroll to **"Notifications"** section

3. **Enable these notifications:**
   - ✅ Deployment Started
   - ✅ Deployment Succeeded
   - ✅ **Deployment Failed** ← Critical
   - ✅ Deployment Crashed ← Critical
   - ✅ **Build Failed** ← Critical

4. **Email Recipients:**
   - Your email should be auto-filled
   - To add team members: Click "+ Add Email" → Enter email → Save

5. **Slack Integration** (Optional - for deployment notifications):
   - Click "Add Slack Integration"
   - Select Slack channel (e.g., `#deployments`)
   - Authorize Railway

6. Click **"Save Changes"**

**✅ Checkpoint:** Deployment notifications enabled

---

### Step 3: Configure Resource Alerts (5 minutes)

1. In your service, click **"Metrics"** tab

2. Click **"Alerts"** button (top right)

3. **Create Memory Alert:**
   - Click **"+ Add Alert"**
   - **Alert Name:** `High Memory Usage`
   - **Metric:** Memory Usage (%)
   - **Condition:** Greater than
   - **Threshold:** `80` (percent)
   - **Duration:** 5 minutes (sustained usage)
   - **Notification Method:** Email
   - Click **"Create Alert"**

4. **Create CPU Alert:**
   - Click **"+ Add Alert"** again
   - **Alert Name:** `High CPU Usage`
   - **Metric:** CPU Usage (%)
   - **Condition:** Greater than
   - **Threshold:** `90` (percent)
   - **Duration:** 5 minutes
   - **Notification Method:** Email
   - Click **"Create Alert"**

5. **Create Crash Alert** (if not already enabled):
   - Click **"+ Add Alert"**
   - **Alert Name:** `Service Crashed`
   - **Metric:** Service Status
   - **Condition:** Equals
   - **Value:** Crashed
   - **Notification Method:** Email + Slack (if configured)
   - Click **"Create Alert"**

**✅ Checkpoint:** 3 resource alerts configured

---

### Step 4: Test Deployment Alert (Optional - 3 minutes)

Trigger a test deployment:

```bash
# In your terminal:
git commit --allow-empty -m "Test deployment alert"
git push

# Railway auto-deploys on push
```

**Expected results:**
1. Email: "Deployment Started"
2. Wait 2-3 minutes
3. Email: "Deployment Succeeded" (or "Failed" if issues)

**✅ Checkpoint:** Deployment notification received

---

## Tier 3: Slack Webhooks (15 minutes)

### Step 1: Create Slack Webhook (5 minutes)

1. Go to https://api.slack.com/apps
2. Click **"Create New App"**
3. Select **"From scratch"**

4. **App Configuration:**
   - **App Name:** `Customer Intelligence Alerts`
   - **Pick a workspace:** Select your Slack workspace
   - Click **"Create App"**

5. **Activate Incoming Webhooks:**
   - In left sidebar, click **"Incoming Webhooks"**
   - Toggle **"Activate Incoming Webhooks"** to **ON** (should turn green)

6. **Add Webhook to Workspace:**
   - Scroll down to **"Webhook URLs for Your Workspace"**
   - Click **"Add New Webhook to Workspace"**
   - **Select a channel:** Choose where alerts go (e.g., `#alerts`, `#engineering`, `#monitoring`)
   - Click **"Allow"**

7. **Copy Webhook URL:**
   - You'll see a webhook URL like:
     ```
     https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
     ```
   - Click **"Copy"** button
   - Save this URL - you'll need it next

**✅ Checkpoint:** Webhook URL copied to clipboard

---

### Step 2: Add Webhook to Railway Environment (5 minutes)

**Option A: Using Railway CLI** (Recommended)

```bash
# In your terminal:
railway variables --set "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Verify it was added:
railway variables | grep SLACK_WEBHOOK_URL

# Redeploy for changes to take effect:
railway up
```

**Option B: Using Railway Dashboard**

1. Go to Railway dashboard
2. Click your service
3. Click **"Variables"** tab
4. Click **"+ New Variable"**
5. **Variable:**
   - **Name:** `SLACK_WEBHOOK_URL`
   - **Value:** (paste webhook URL)
6. Click **"Add"**
7. Service will automatically redeploy

**✅ Checkpoint:** Environment variable set, service redeployed

---

### Step 3: Test Slack Alerts (5 minutes)

Run the test script:

```bash
# In your terminal (in project directory):
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

python scripts/test_slack_alerts.py
```

**Expected output:**
```
🚀 Starting Slack Alert Tests

Testing Slack Alert Integration
============================================================
✅ Webhook URL configured: https://hooks.slack.com/services/T...

Test 1: Basic Info Alert
  ✅ Sent
  Check your Slack channel!

Test 2: Error Alert
  ✅ Sent (check Slack)

Test 3: Performance Alert
  ✅ Sent (check Slack)

Test 4: Deployment Success Alert
  ✅ Sent (check Slack)

Test 5: Health Degraded Alert
  ✅ Sent (check Slack)

Test 6: Warning Alert
  ✅ Sent (check Slack)

============================================================
✅ All 6 test alerts sent successfully!

Check your Slack channel - you should see 6 messages:
  1. Blue (info) - Basic test alert
  2. Red (error) - Test error
  3. Orange (warning) - Slow endpoint
  4. Green (success) - Deployment completed
  5. Orange (warning) - Database degraded
  6. Orange (warning) - Warning alert
============================================================
```

**In Slack, you should see 6 messages with colors:**
- 🔵 Blue (info)
- 🔴 Red (error)
- 🟠 Orange (warning) × 3
- 🟢 Green (success)

**✅ Checkpoint:** All 6 test alerts appear in Slack

---

### Step 4: Configure Alert Thresholds (Optional - 5 minutes)

Fine-tune when Slack alerts fire:

**Edit `backend/middleware/slack_alerts.py`:**

```python
# Customize alert thresholds:

# Performance threshold (default: 2 seconds)
SLOW_RESPONSE_THRESHOLD = 2.0  # seconds

# Error rate threshold (default: 5 errors in 5 minutes)
ERROR_RATE_THRESHOLD = 5
ERROR_RATE_WINDOW = 300  # seconds

# Memory threshold (default: 80%)
MEMORY_ALERT_THRESHOLD = 0.80

# CPU threshold (default: 90%)
CPU_ALERT_THRESHOLD = 0.90
```

**✅ Checkpoint:** Thresholds customized (optional)

---

## Verification Checklist

After completing all 3 tiers, verify your monitoring setup:

### UptimeRobot ✅
- [ ] Health check monitor shows "Up" (green)
- [ ] Performance monitor shows "Up" (green)
- [ ] Response time <2 seconds
- [ ] Email alert configured
- [ ] Status page accessible publicly
- [ ] Status page shows both monitors

### Railway Alerts ✅
- [ ] Deployment notifications enabled
- [ ] Memory alert configured (>80%)
- [ ] CPU alert configured (>90%)
- [ ] Crash alert configured
- [ ] Email recipients added
- [ ] Test deployment triggered email

### Slack Webhooks ✅
- [ ] Webhook URL created
- [ ] Environment variable set in Railway
- [ ] Service redeployed with new variable
- [ ] Test script ran successfully
- [ ] 6 test messages appeared in Slack
- [ ] Alerts have correct colors/formatting

---

## Alert Response Times

Expected detection times after setup:

| Alert Type | Detection Time | Notification Time | Total MTTD |
|------------|----------------|-------------------|------------|
| **API Down** | 5 min (UptimeRobot) | <1 min | **~6 min** |
| **Deployment Failed** | Immediate | <1 min | **<2 min** |
| **Error 500** | Immediate | <10 sec | **<1 min** |
| **High Memory** | 5 min sustained | <1 min | **~6 min** |
| **Slow Response** | 5 min (UptimeRobot) | <1 min | **~6 min** |

**Target: MTTD <10 minutes for all critical issues** ✅

---

## What Happens When Things Break

### Scenario 1: API Goes Down

**Timeline:**
1. **T+0:** API crashes
2. **T+5 min:** UptimeRobot detects failure (next check)
3. **T+6 min:** You receive email: "API is DOWN"
4. **T+7 min:** You receive SMS (if configured)
5. **T+8 min:** You check Railway logs via `railway logs`
6. **T+10 min:** Issue identified (see [INCIDENT_RUNBOOK.md](INCIDENT_RUNBOOK.md))
7. **T+15 min:** Fix deployed, API restored

**Notifications you'll receive:**
- ✉️ Email: "Customer Intelligence API - Health is DOWN"
- 📱 SMS: "Monitor DOWN: Customer Intelligence API"
- ✉️ Railway: "Service Crashed"
- 💬 Slack: Red alert with error details

---

### Scenario 2: Slow Database Queries

**Timeline:**
1. **T+0:** Database query takes 3 seconds (threshold: 2s)
2. **T+1 sec:** Slack alert: "Slow API Response" (orange)
3. **T+5 min:** UptimeRobot detects if sustained >2s
4. **T+6 min:** Email: "Response time exceeded 2000ms"

**Notifications you'll receive:**
- 💬 Slack: Orange warning "Slow API Response"
- ✉️ Email: "Performance monitor alert" (if sustained)

---

### Scenario 3: Deployment Failure

**Timeline:**
1. **T+0:** Git push triggers deployment
2. **T+30 sec:** Build starts
3. **T+2 min:** Build fails (missing dependency)
4. **T+2 min 10 sec:** You receive email: "Build Failed"
5. **T+2 min 30 sec:** Slack notification (if configured)

**Notifications you'll receive:**
- ✉️ Railway: "Build Failed: [error message]"
- 💬 Slack: "Deployment Failed" (if webhook configured)

---

## Troubleshooting

### UptimeRobot Issues

**Problem:** Monitor shows "Down" but API works in browser

**Solution:**
```bash
# Test your health endpoint:
curl https://ecommerce-backend-staging-a14c.up.railway.app/health

# Should return:
{"status":"healthy","timestamp":"2025-..."}

# If it works, check UptimeRobot keyword settings:
# Keyword: "healthy" should be set to "Alert if keyword NOT exists"
```

---

**Problem:** Not receiving email alerts

**Solution:**
1. Check spam folder
2. Verify email in UptimeRobot → Settings → Alert Contacts
3. Click "Send Test Notification"
4. If still no email, add alternative email address

---

### Railway Alert Issues

**Problem:** No deployment notifications

**Solution:**
```bash
# Verify notifications enabled in Railway:
# Dashboard → Service → Settings → Notifications

# Trigger test deployment:
git commit --allow-empty -m "Test alert"
git push
```

---

**Problem:** Memory alert not triggering

**Solution:**
```bash
# Check current memory usage:
railway run cat /sys/fs/cgroup/memory/memory.usage_in_bytes

# If <80%, alert won't trigger (working as expected)
# To test, temporarily lower threshold to 50%
```

---

### Slack Webhook Issues

**Problem:** Test script says "slack_webhook_not_configured"

**Solution:**
```bash
# Verify environment variable is set:
railway variables | grep SLACK_WEBHOOK_URL

# If missing, add it:
railway variables --set "SLACK_WEBHOOK_URL=https://hooks.slack.com/..."

# Redeploy:
railway up
```

---

**Problem:** Webhook URL returns 404

**Solution:**
1. Webhook URL expired or deleted
2. Go to https://api.slack.com/apps
3. Click your app → Incoming Webhooks
4. Deactivate and reactivate webhooks
5. Create new webhook URL
6. Update Railway environment variable

---

**Problem:** Messages not appearing in Slack

**Solution:**
```bash
# Test webhook manually:
curl -X POST 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL' \
  -H 'Content-Type: application/json' \
  -d '{"text": "Test message from curl"}'

# Should return "ok"
# If "invalid_payload", check URL is correct
# If "channel_not_found", recreate webhook
```

---

## Next Steps

After monitoring is configured:

### Week 1: Monitor Closely
- [ ] Check status page daily
- [ ] Review Slack alerts for patterns
- [ ] Tune alert thresholds if too noisy
- [ ] Document any false positives

### Week 2: Optimize
- [ ] Review average response times
- [ ] Identify slow endpoints
- [ ] Optimize queries causing >2s responses
- [ ] Reduce alert noise

### Week 3: Expand
- [ ] Add more monitors (specific endpoints)
- [ ] Set up PagerDuty (for on-call rotation)
- [ ] Create Grafana dashboard (if using Prometheus)
- [ ] Add customer-specific health checks

---

## Cost Summary

| Service | Tier | Cost | What You Get |
|---------|------|------|--------------|
| **UptimeRobot** | Free | $0/mo | 50 monitors, 5-min checks |
| **UptimeRobot** | Pro | $7/mo | 1-min checks, SMS, more monitors |
| **Railway** | Hobby | $5/mo | Email alerts included |
| **Railway** | Pro | $20/mo | Slack integration |
| **Slack** | Free | $0/mo | Webhooks included |
| **Slack** | Pro | $7.25/user/mo | Better history |

**Recommended Setup Cost:** $0-12/month (Free tier + optional Railway Pro)

---

## Summary

You now have a **production-grade 3-tier monitoring system**:

✅ **External monitoring** (UptimeRobot) catches outages even if Railway is down
✅ **Infrastructure alerts** (Railway) notify about deployments and resource issues
✅ **Real-time errors** (Slack) give instant visibility into production problems

**Mean Time To Detect (MTTD):** <10 minutes
**Mean Time To Notify (MTTN):** <2 minutes
**Total Setup Time:** ~2 hours
**Maintenance:** <1 hour/month

---

## Resources

- **UptimeRobot Docs:** https://uptimerobot.com/help/
- **Railway Alerts:** https://docs.railway.app/reference/notifications
- **Slack Webhooks:** https://api.slack.com/messaging/webhooks
- **Incident Runbook:** [INCIDENT_RUNBOOK.md](INCIDENT_RUNBOOK.md)
- **Alerting Setup:** [ALERTING_SETUP.md](ALERTING_SETUP.md)

---

## Support

If you encounter issues during setup:

1. **Check this troubleshooting section** ↑
2. **Review logs:** `railway logs --tail 100`
3. **Test manually:** Use curl commands provided
4. **Slack webhook issues:** Delete and recreate webhook
5. **Email issues:** Check spam, verify email address

**Still stuck?** Create an issue with:
- Which step you're on
- Error message (if any)
- What you've tried

---

**Setup completed? Great! You're now production-ready.** 🎉

Go to [Production Readiness Plan](PRODUCTION_READINESS_PLAN.md) for next steps.
