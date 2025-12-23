#!/bin/bash
#
# Test SMS ticket with phone number lookup
# This simulates a Klaviyo SMS message forwarded to Gorgias
#

set -e

# Get ADMIN_KEY from environment
if [ -z "$ADMIN_KEY" ]; then
    echo "Error: ADMIN_KEY environment variable not set"
    exit 1
fi

echo "🧪 Testing SMS ticket with phone number lookup..."
echo ""

# Test with a phone number (use a real one from your Shopify store)
# Format options to test normalization:
# - +15551234567 (E.164)
# - (555) 123-4567 (US format with parens)
# - 555-123-4567 (US format with dashes)

PHONE_NUMBER="+15551234567"  # Replace with actual test phone from Shopify

echo "📱 Testing phone: $PHONE_NUMBER"
echo ""

curl -X POST https://ecommerce-backend-staging-a14c.up.railway.app/api/gorgias/webhook/test \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"99999\",
    \"via\": \"sms\",
    \"channel\": \"sms\",
    \"subject\": \"SMS from customer\",
    \"customer\": {
      \"phone\": \"$PHONE_NUMBER\",
      \"email\": \"sms-test@example.com\",
      \"name\": \"SMS Test Customer\"
    },
    \"messages\": [
      {
        \"body_text\": \"Hey, where is my order? I ordered last week and haven't received tracking info yet.\",
        \"is_note\": false,
        \"from\": {
          \"phone\": \"$PHONE_NUMBER\"
        },
        \"created_datetime\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
      }
    ]
  }" | jq '.'

echo ""
echo "✅ Test complete - check logs for phone lookup results"
