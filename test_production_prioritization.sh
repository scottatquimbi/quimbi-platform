#!/bin/bash
# Test production deployment of ticket prioritization

echo "=================================="
echo "TESTING PRODUCTION DEPLOYMENT"
echo "=================================="

WEBHOOK_URL="https://ecommerce-backend-staging-a14c.up.railway.app/api/gorgias/webhook/test"
WEBHOOK_SECRET="${GORGIAS_WEBHOOK_SECRET:-test_secret}"

echo ""
echo "[TEST 1] LCC Member with Cancel Request (Should be URGENT)"
echo "-----------------------------------------------------------"
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_SECRET" \
  -d '{
    "id": "99901",
    "customer": {
      "id": "123456",
      "name": "Sarah Johnson",
      "email": "sarah@example.com",
      "integrations": {
        "shopify_123": {
          "__integration_type__": "shopify",
          "customer": {
            "id": "789012",
            "total_spent": "1245.00",
            "orders_count": 8,
            "tags": "LCC_Member, VIP, Newsletter"
          }
        }
      }
    },
    "messages": [
      {
        "body_text": "I need to cancel my order immediately!",
        "from_agent": false
      }
    ],
    "channel": "email",
    "via": "email"
  }' | python3 -m json.tool | grep -E "(status|priority|urgency|is_lcc_member|reason)" | head -10

echo ""
echo "[TEST 2] Standard Customer with Wrong Address (Should be URGENT)"
echo "----------------------------------------------------------------"
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_SECRET" \
  -d '{
    "id": "99902",
    "customer": {
      "id": "234567",
      "name": "Mike Smith",
      "email": "mike@example.com",
      "integrations": {
        "shopify_456": {
          "__integration_type__": "shopify",
          "customer": {
            "id": "890123",
            "total_spent": "85.00",
            "orders_count": 1,
            "tags": ""
          }
        }
      }
    },
    "messages": [
      {
        "body_text": "The package shipped to the wrong address!",
        "from_agent": false
      }
    ],
    "channel": "email",
    "via": "email"
  }' | python3 -m json.tool | grep -E "(status|priority|urgency|is_lcc_member|reason)" | head -10

echo ""
echo "[TEST 3] LCC Member with General Question (Should be HIGH)"
echo "----------------------------------------------------------"
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_SECRET" \
  -d '{
    "id": "99903",
    "customer": {
      "id": "345678",
      "name": "Jennifer Davis",
      "email": "jennifer@example.com",
      "integrations": {
        "shopify_789": {
          "__integration_type__": "shopify",
          "customer": {
            "id": "901234",
            "total_spent": "450.00",
            "orders_count": 3,
            "tags": "LCC_Member"
          }
        }
      }
    },
    "messages": [
      {
        "body_text": "What fabric is this quilt made from?",
        "from_agent": false
      }
    ],
    "channel": "email",
    "via": "email"
  }' | python3 -m json.tool | grep -E "(status|priority|urgency|is_lcc_member|reason)" | head -10

echo ""
echo "[TEST 4] Standard Customer with Damaged Item (Should be HIGH)"
echo "-------------------------------------------------------------"
curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_SECRET" \
  -d '{
    "id": "99904",
    "customer": {
      "id": "456789",
      "name": "Lisa Brown",
      "email": "lisa@example.com",
      "integrations": {
        "shopify_012": {
          "__integration_type__": "shopify",
          "customer": {
            "id": "012345",
            "total_spent": "200.00",
            "orders_count": 2,
            "tags": ""
          }
        }
      }
    },
    "messages": [
      {
        "body_text": "My quilt arrived damaged",
        "from_agent": false
      }
    ],
    "channel": "email",
    "via": "email"
  }' | python3 -m json.tool | grep -E "(status|priority|urgency|is_lcc_member|reason)" | head -10

echo ""
echo "=================================="
echo "DEPLOYMENT TESTS COMPLETE"
echo "=================================="
