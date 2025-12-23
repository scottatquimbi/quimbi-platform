# How to Test/Query the Gorgias Bot

**Date:** 2025-11-09
**Purpose:** Test Quimbi's AI responses in Gorgias without waiting for real customer tickets

---

## Overview

The Gorgias bot automatically responds to new tickets by:
1. Extracting customer info from the webhook
2. Fetching analytics and order history from MCP API
3. Generating a personalized draft reply using Claude AI
4. Posting the draft as an **internal note** + **draft reply** in Gorgias

You can test this in 3 ways:

---

## Method 1: Create a Test Ticket in Gorgias (Recommended)

**Best for:** Quick testing with realistic workflow

### Steps:

1. **Go to Gorgias Dashboard**
   - URL: https://lindas.gorgias.com
   - Log in with your credentials

2. **Create New Ticket**
   - Click "+ New Ticket" button (top right)
   - Choose channel: Email

3. **Fill in Customer Info**
   - **Customer Email:** Use a real customer from the system
     - Example: `mauldenm@earthlink.net` (Marcia Maulden)
     - Example: `donna_caldwell@sbcglobal.net` (Donna Caldwell)
   - **Customer Name:** Will auto-fill if customer exists

4. **Add Customer Message**
   - Type a question to test order history:
     - "Did I buy any rose thread from you?"
     - "What did I order last time?"
     - "Can you check if I bought batting from you in the last 6 months?"

5. **Send Ticket**
   - Click "Send" or "Create"
   - Webhook fires automatically
   - Bot processes in ~5-10 seconds

6. **Check for Bot Response**
   - Look for **Internal Note** (private, visible only to agents):
     ```
     🤖 Quimbi Customer Intelligence

     📊 CUSTOMER ANALYTICS
     💰 Lifetime Value: $71 (Standard)
     ⚠️  Churn Risk: 23% (LOW - Healthy)
     📈 Historical: 2 orders, $36 avg order
     📅 Last Purchase: 401 days ago (At Risk)
     ```

   - Look for **Draft Reply** (suggested response):
     ```
     Hi Marcia,

     Yes! I found your rose thread purchase:

     📦 Order #87265 - August 29, 2024
     Products:
       • 478 Rose Signature Cotton Thread

     Total: $18.69

     Would you like to reorder this thread?

     Best regards,
     Linda's Customer Service
     ```

7. **Agent Actions**
   - **Approve:** Click "Send" to send the draft to customer
   - **Edit:** Modify the draft before sending
   - **Delete:** Ignore the draft and write your own

---

## Method 2: Reply to Existing Ticket

**Best for:** Testing updates/follow-ups

### Steps:

1. **Find an Existing Ticket**
   - Open any ticket in Gorgias
   - Look for one with a known customer (check Shopify integration)

2. **Add Customer Reply**
   - Scroll to bottom of ticket
   - Click "Add Message"
   - **Important:** Set sender to "Customer" (not Agent)
   - Type customer question

3. **Send**
   - Webhook fires on ticket update
   - Bot generates new draft based on conversation context

4. **Check for New Draft**
   - Look for updated internal note + new draft reply

---

## Method 3: Test via Webhook API (Advanced)

**Best for:** Automated testing, debugging, development

### Using the Test Script

I've created a test script that simulates a Gorgias webhook:

```bash
# Edit the script with your test data
nano test_gorgias_query.sh

# Make it executable
chmod +x test_gorgias_query.sh

# Run it
./test_gorgias_query.sh
```

### What the Script Does:

1. Creates a fake webhook payload with:
   - Real customer data (Marcia Maulden)
   - Test question about rose thread
   - Shopify integration data

2. Sends POST request to Railway webhook endpoint

3. Bot processes it and posts draft to Gorgias

### Customize the Test:

Edit these variables in `test_gorgias_query.sh`:

```bash
TICKET_ID="235766516"              # Real Gorgias ticket ID
CUSTOMER_EMAIL="mauldenm@earthlink.net"   # Real customer email
CUSTOMER_NAME="Marcia Maulden"     # Customer name
CUSTOMER_MESSAGE="Your test question here"
```

### Manual API Test:

```bash
curl -X POST \
  "https://ecommerce-backend-staging-a14c.up.railway.app/api/gorgias/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 235766516,
    "customer": {
      "email": "mauldenm@earthlink.net",
      "name": "Marcia Maulden",
      "integrations": {
        "82185": {
          "__integration_type__": "shopify",
          "customer": {
            "id": 7460267524351,
            "email": "mauldenm@earthlink.net"
          }
        }
      }
    },
    "messages": [
      {
        "from_agent": false,
        "body_text": "Did I buy any rose thread from you?",
        "created_datetime": "2025-11-09T10:00:00Z"
      }
    ]
  }'
```

---

## Test Customers Available

Here are real customers in the system you can test with:

| Customer | Email | Shopify ID | Orders | LTV | Good Test For |
|----------|-------|------------|--------|-----|---------------|
| Marcia Maulden | mauldenm@earthlink.net | 7460267524351 | 2 | $71.31 | Thread purchases, rose thread |
| Donna Caldwell | donna_caldwell@sbcglobal.net | 6846082875647 | 2 | $88.50 | General queries |
| Julie Atkinson | julesra77@gmail.com | 7045234393343 | Unknown | Unknown | New customer queries |

### Finding More Customers:

```bash
# Get a random customer
curl -s 'https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/random' \
  -H 'X-API-Key: e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31' \
  | python3 -m json.tool
```

---

## What to Test

### Basic Functionality

- [ ] Customer analytics appear in internal note
- [ ] Draft reply is generated
- [ ] Bot uses customer's name
- [ ] LTV and churn risk are shown

### Order History Integration (NEW!)

Test questions that require Shopify order history:

- [ ] **Product search:** "Did I buy any rose thread from you?"
  - Expected: Bot searches order history for "rose" + "thread"
  - Expected: Confirms with order number and date if found

- [ ] **Date filtering:** "What did I order in the last 6 months?"
  - Expected: Bot searches orders from last 6 months
  - Expected: Lists products with dates

- [ ] **Negative case:** "Did I buy a Tula Pink iron?"
  - Expected: Bot searches for "tula pink" + "iron"
  - Expected: Says "I checked your history and don't see..." if not found

- [ ] **General question:** "What did I order last time?"
  - Expected: Bot retrieves most recent order
  - Expected: Shows products and date

### Edge Cases

- [ ] New customer (no order history)
- [ ] Customer not in Shopify
- [ ] Customer with 20+ orders
- [ ] Very long customer message
- [ ] Message with special characters/emojis

---

## Expected Response Times

| Step | Time |
|------|------|
| Webhook received | Instant |
| Customer analytics lookup | ~1-2 seconds |
| Order history query | ~2-3 seconds |
| AI draft generation | ~3-5 seconds |
| Post to Gorgias | ~1 second |
| **Total** | **~7-11 seconds** |

---

## Monitoring Test Results

### In Gorgias:

1. **Internal Note** appears first (with analytics)
2. **Draft Reply** appears second (suggested response)
3. Check timestamp to confirm it's recent

### In Railway Logs:

```bash
# Watch logs in real-time
railway logs

# Look for these log messages:
# - "Received Gorgias webhook for ticket #XXX"
# - "Fetching order history for customer XXX"
# - "Retrieved X orders for customer XXX"
# - "Successfully posted draft reply to ticket #XXX"
```

### Check for Errors:

Common issues and solutions:

**Error:** "Shopify integration not configured"
- **Fix:** Add SHOPIFY_SHOP_NAME and SHOPIFY_ACCESS_TOKEN to Railway env

**Error:** "Customer not found in Shopify"
- **Fix:** Use a customer ID that exists in Shopify (check integrations data)

**Error:** "Failed to post draft reply"
- **Fix:** Check Gorgias API credentials in Railway env

---

## Example Test Flow

**Scenario:** Test "Did I buy rose thread?" query

1. **Create ticket in Gorgias:**
   - Customer: mauldenm@earthlink.net
   - Message: "Hi, I'm trying to remember if I bought some rose-colored thread from you a few months ago. Can you check?"

2. **Wait ~10 seconds**

3. **Check Gorgias ticket for:**

   **Internal Note:**
   ```
   🤖 Quimbi Customer Intelligence

   📊 CUSTOMER ANALYTICS
   💰 Lifetime Value: $71 (Standard)
   ⚠️  Churn Risk: 23% (LOW - Healthy)
   📈 Historical: 2 orders, $36 avg order
   📅 Last Purchase: 401 days ago (At Risk)
   ```

   **Draft Reply:**
   ```
   Hi Marcia,

   Yes! I found your rose thread purchase:

   📦 Order #87265 - August 29, 2024
   Product: 478 Rose Signature Cotton Thread
   Vendor: American & Efird Signature
   Total: $18.69

   Would you like to reorder this same thread?

   Best regards,
   Linda's Customer Service Team
   ```

4. **Verify accuracy:**
   - [ ] Customer name is correct (Marcia)
   - [ ] Order number matches (#87265)
   - [ ] Product name is accurate (478 Rose Signature Cotton Thread)
   - [ ] Date is correct (August 29, 2024)
   - [ ] Total is correct ($18.69)

5. **Agent action:**
   - Click "Send" to approve and send to customer
   - Or edit before sending

---

## Troubleshooting

### Bot doesn't respond

**Check:**
1. Webhook is configured in Gorgias (Settings → HTTP Integration)
2. Railway app is running (`railway status`)
3. ANTHROPIC_API_KEY is set in Railway
4. Check Railway logs for errors

### Wrong customer data

**Check:**
1. Customer email matches Shopify
2. Shopify integration data is present in webhook
3. Customer exists in MCP database

### Order history not found

**Check:**
1. SHOPIFY_SHOP_NAME and SHOPIFY_ACCESS_TOKEN are set
2. Customer ID is correct (numeric Shopify ID)
3. Customer has orders in Shopify
4. Search terms match product names

---

## Quick Reference Commands

```bash
# Test with real customer
./test_gorgias_query.sh

# Watch Railway logs
railway logs | grep -i "order history\|draft reply"

# Get random customer for testing
curl -s 'https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/random' \
  -H 'X-API-Key: e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31'

# Test order history endpoint directly
curl -s 'https://ecommerce-backend-staging-a14c.up.railway.app/api/mcp/customer/7460267524351/orders?search_terms=rose,thread' \
  -H 'X-API-Key: e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31' \
  | python3 -m json.tool
```

---

## Next Steps

After testing:

1. **Verify accuracy** of draft replies
2. **Tune the AI prompt** if responses need adjustment
3. **Add more test scenarios** for edge cases
4. **Monitor real tickets** for quality
5. **Train agents** on using/editing drafts

---

**Status:** Ready for testing
**Last Updated:** 2025-11-09
**Related Docs:**
- [SHOPIFY_ORDER_HISTORY_IMPLEMENTATION.md](SHOPIFY_ORDER_HISTORY_IMPLEMENTATION.md)
- [BETTY_BATES_PURCHASE_HISTORY_ANALYSIS.md](BETTY_BATES_PURCHASE_HISTORY_ANALYSIS.md)
