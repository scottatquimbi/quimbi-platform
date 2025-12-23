# Gorgias Production Webhook Setup

**Date:** 2025-11-12
**Production URL:** https://ecommerce-backend-production-b9cc.up.railway.app
**Webhook Endpoint:** https://ecommerce-backend-production-b9cc.up.railway.app/api/gorgias/webhook

---

## Quick Setup (5 minutes)

### Step 1: Access Gorgias HTTP Integration Settings

1. **Log in to Gorgias:**
   - Go to: https://lindas.gorgias.com
   - Log in with your credentials

2. **Navigate to Settings:**
   - Click your profile icon (bottom left)
   - Select **Settings**
   - Go to **Integrations** → **HTTP Integration**
   - OR direct link: https://lindas.gorgias.com/app/settings/http-integrations

---

### Step 2: Configure Webhook

#### **Webhook URL:**
```
https://ecommerce-backend-production-b9cc.up.railway.app/api/gorgias/webhook
```

#### **Trigger Event:**
- Select: **Ticket Message Created**
- This fires when ANY new message is added to a ticket (customer or agent)

#### **Authentication:**
Add custom header for security:
- **Header Name:** `X-Webhook-Token`
- **Header Value:** (Get from Railway - see below)

#### **Request Method:**
- Select: **POST**

#### **Content Type:**
- Select: **application/json**

---

### Step 3: Get Webhook Secret from Railway

The webhook requires authentication via `GORGIAS_WEBHOOK_SECRET` environment variable.

**Option A: Use existing secret (from staging)**
```bash
# Check current webhook secret
railway variables | grep GORGIAS_WEBHOOK_SECRET
```

Copy the value you see (should be 64 character hex string like: `08130fe49bd19885a555cb81885dfc44ec9b74d26a098a9a95f76ca55888f874`)

**Option B: Generate new secret**
```bash
# Generate new random secret
openssl rand -hex 32

# Set in Railway production environment
railway variables set GORGIAS_WEBHOOK_SECRET=<generated-value>
```

**Important:** Use the SAME secret value in both places:
1. Railway environment variable: `GORGIAS_WEBHOOK_SECRET`
2. Gorgias HTTP Integration header: `X-Webhook-Token`

---

### Step 4: Configure Gorgias HTTP Integration

Fill in the form:

```
┌─────────────────────────────────────────────────────────────┐
│ HTTP Integration Settings                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Integration Name:                                           │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Quimbi AI Assistant (Production)                        ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ URL:                                                        │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ https://ecommerce-backend-production-b9cc.up.railway... ││
│ │ .app/api/gorgias/webhook                                ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ Method: [POST ▼]                                           │
│                                                             │
│ Headers:                                                    │
│ ┌───────────────────┬─────────────────────────────────────┐│
│ │ X-Webhook-Token   │ 08130fe49bd19885a555cb81885dfc44... ││
│ └───────────────────┴─────────────────────────────────────┘│
│ [+ Add Header]                                              │
│                                                             │
│ Trigger: [Ticket Message Created ▼]                        │
│                                                             │
│ ☑ Active                                                    │
│                                                             │
│ [Test Connection] [Save]                                    │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 5: Test the Webhook

#### **A. Test Connection in Gorgias**

Click **"Test Connection"** button in the HTTP Integration settings.

**Expected Result:**
```json
{
  "status": "accepted",
  "ticket_id": "test",
  "message": "Webhook received and queued for processing"
}
```

#### **B. Create Test Ticket**

1. In Gorgias, click **"+ New Ticket"**
2. Select **Email** channel
3. **Customer Email:** Use a real customer from system
   - Example: `mauldenm@earthlink.net` (Marcia Maulden - has order history)
4. **Customer Message:**
   ```
   Hi, did I buy any rose thread from you recently?
   ```
5. Click **"Send"**

#### **C. Verify Bot Response (wait ~7-10 seconds)**

Check the ticket for:

1. **Internal Note** (visible only to agents):
   ```
   🤖 Quimbi Customer Intelligence

   📊 CUSTOMER ANALYTICS
   💰 Lifetime Value: $71 (Standard)
   ⚠️  Churn Risk: 23% (LOW - Healthy)
   📈 Historical: 2 orders, $36 avg order
   📅 Last Purchase: 401 days ago (At Risk)

   🎯 RETENTION STRATEGY
   • Risk Level: LOW
   • Action: Monitor engagement
   • Next Best Action: Gentle reminder email
   ```

2. **Draft Reply** (suggested response for agent):
   ```
   Hi Marcia,

   Yes! I found your rose thread purchase:

   📦 Order #87265 - August 29, 2024
   Products:
     • 478 Rose Signature Cotton Thread
     • Vendor: American & Efird Signature

   Total: $18.69

   Would you like to reorder this same thread?

   Best regards,
   Linda's Customer Service
   ```

---

## Environment Variables Checklist

Ensure these are set in **Railway Production Environment**:

### Required:
```bash
✓ ANTHROPIC_API_KEY          # Claude API key for AI responses
✓ GORGIAS_WEBHOOK_SECRET     # Matches X-Webhook-Token in Gorgias
✓ GORGIAS_DOMAIN=lindas      # Your Gorgias subdomain
✓ GORGIAS_USERNAME           # Gorgias API username/email
✓ GORGIAS_API_KEY            # Gorgias API key (base64 encoded)
✓ DATABASE_URL               # PostgreSQL connection
✓ ADMIN_KEY                  # For admin endpoints
```

### Shopify Integration (for order history):
```bash
✓ SHOPIFY_SHOP_NAME=lindas-electric-quilters
✓ SHOPIFY_ACCESS_TOKEN       # Shopify API token
✓ SHOPIFY_API_VERSION=2024-10
```

### Optional (Performance):
```bash
✓ REDIS_URL                  # Redis cache URL
✓ ENABLE_CACHE=true          # Enable caching
```

---

## Verify Environment Variables

```bash
# Check current environment
railway status

# Switch to production (if needed)
railway environment production

# List all variables
railway variables

# Verify critical ones
railway variables | grep -E "GORGIAS|ANTHROPIC|SHOPIFY"
```

---

## Monitoring & Logs

### Watch Webhook Processing in Real-Time

```bash
# Switch to production environment
railway environment production

# Follow logs
railway logs --follow

# Filter for webhook activity
railway logs | grep -i "gorgias\|webhook\|async"
```

### What to Look For

**Successful Processing:**
```
✓ Received Gorgias webhook for ticket #235766516
✓ [ASYNC] Starting background processing for ticket #235766516
✓ Fetching order history for customer 7460267524351
✓ Retrieved 2 orders for customer
✓ Successfully posted draft reply to ticket #235766516
✓ [ASYNC] Completed ticket #235766516: success
```

**Common Errors:**
```
❌ Invalid webhook token                → Check GORGIAS_WEBHOOK_SECRET matches
❌ Customer not found in Shopify        → Verify Shopify credentials
❌ Failed to post draft reply           → Check GORGIAS_API_KEY
❌ Anthropic API error                  → Check ANTHROPIC_API_KEY
```

---

## Test Scenarios

### Basic Test
- **Customer:** Any real customer email
- **Message:** "I have a question about my order"
- **Expected:** Analytics + generic draft reply

### Order History Test
- **Customer:** mauldenm@earthlink.net
- **Message:** "Did I buy any rose thread from you?"
- **Expected:** Analytics + specific order details with product names

### Churn Risk Test
- **Customer:** Customer with high churn risk (last purchase >90 days)
- **Message:** Any inquiry
- **Expected:** Critical churn warning + retention strategy in internal note

### New Customer Test
- **Customer:** Email not in system
- **Message:** "I'm interested in ordering"
- **Expected:** New customer note + welcoming draft reply

---

## Troubleshooting

### Webhook Not Firing

**Check:**
1. ✓ HTTP Integration is **Active** (checkbox enabled)
2. ✓ Trigger is set to **"Ticket Message Created"**
3. ✓ URL is correct (no typos)
4. ✓ Railway production service is running

**Test:**
```bash
# Check if service is healthy
curl https://ecommerce-backend-production-b9cc.up.railway.app/health

# Should return:
{"status":"healthy","timestamp":"2025-11-12T..."}
```

### Bot Not Responding

**Check Railway logs:**
```bash
railway logs | grep -i error

# Common issues:
# - Missing ANTHROPIC_API_KEY
# - Invalid GORGIAS_WEBHOOK_SECRET
# - Database connection failed
```

### Wrong Customer Data

**Check:**
1. ✓ Customer has Shopify integration data in webhook payload
2. ✓ SHOPIFY_* variables are set correctly
3. ✓ Customer ID matches Shopify database

### Draft Not Appearing

**Check:**
1. ✓ GORGIAS_API_KEY is valid
2. ✓ GORGIAS_USERNAME is correct
3. ✓ Gorgias API permissions allow posting notes/drafts

---

## Production vs Staging URLs

| Environment | URL |
|-------------|-----|
| **Production** | https://ecommerce-backend-production-b9cc.up.railway.app |
| **Staging** | https://ecommerce-backend-staging-a14c.up.railway.app |

**Important:** Make sure Gorgias webhook points to **Production**, not Staging!

---

## Security Notes

### Webhook Authentication

The webhook uses **custom header authentication** instead of URL signatures:
- **Header:** `X-Webhook-Token`
- **Value:** Shared secret between Gorgias and Railway
- **Purpose:** Prevents unauthorized webhook calls

### Why This Matters

Without proper authentication, anyone could send fake webhooks to your endpoint. The shared secret ensures only Gorgias can trigger the bot.

### Rotating Secrets

If you need to change the webhook secret:
```bash
# 1. Generate new secret
NEW_SECRET=$(openssl rand -hex 32)

# 2. Update Railway
railway variables set GORGIAS_WEBHOOK_SECRET=$NEW_SECRET

# 3. Update Gorgias HTTP Integration header
#    (Go to Gorgias settings and update X-Webhook-Token header)

# 4. Restart Railway service (automatic on variable change)
```

---

## Performance Expectations

| Metric | Target | Actual |
|--------|--------|--------|
| Webhook Response Time | <500ms | ~100ms |
| Background Processing | <15s | ~7-10s |
| Order History Query | <3s | ~2s |
| AI Draft Generation | <5s | ~3s |
| Post to Gorgias | <2s | ~1s |

**Total end-to-end:** ~7-10 seconds from ticket creation to draft appearing

---

## Rollback Plan

If production webhook has issues:

### Option A: Point back to staging
```
URL: https://ecommerce-backend-staging-a14c.up.railway.app/api/gorgias/webhook
```

### Option B: Disable webhook temporarily
- Uncheck **"Active"** in Gorgias HTTP Integration settings
- Fix the issue in production
- Re-enable when ready

---

## Next Steps After Setup

1. **Monitor First 10 Tickets:**
   - Check draft quality
   - Verify customer data accuracy
   - Ensure no errors in logs

2. **Train Support Team:**
   - How to use AI drafts
   - When to edit vs accept
   - Understanding internal notes

3. **Iterate on Prompts:**
   - Adjust AI response tone
   - Add/remove sections
   - Tune for your brand voice

4. **Scale Up:**
   - Add more test scenarios
   - Monitor performance metrics
   - Consider adding more channels (SMS, phone)

---

## Support Contacts

**Technical Issues:**
- Railway Logs: `railway logs`
- Railway Dashboard: https://railway.app
- Repository: https://github.com/Quimbi-ai/Ecommerce-backend

**Gorgias Setup:**
- Support: https://gorgias.com/help
- API Docs: https://developers.gorgias.com

**Quimbi Intelligence:**
- API Docs: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)
- Testing Guide: [HOW_TO_TEST_GORGIAS_BOT.md](HOW_TO_TEST_GORGIAS_BOT.md)

---

**Status:** Ready for production
**Last Updated:** 2025-11-12
**Deployment:** Production (b9cc)
