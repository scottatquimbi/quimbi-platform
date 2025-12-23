#!/bin/bash
# Get 5 diverse real customers for testing

API_URL="https://ecommerce-backend-staging-a14c.up.railway.app"
ADMIN_KEY="e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31"

echo "Fetching 5 random real customers..."
echo ""

for i in {1..5}; do
    echo "=== Customer $i ==="

    # Get random customer
    CUSTOMER=$(curl -s "$API_URL/api/mcp/customer/random" -H "X-API-Key: $ADMIN_KEY")
    CUSTOMER_ID=$(echo "$CUSTOMER" | python3 -c "import sys, json; print(json.load(sys.stdin).get('customer_id', 'unknown'))")

    echo "Customer ID: $CUSTOMER_ID"

    # Get churn risk
    CHURN=$(curl -s "$API_URL/api/mcp/customer/$CUSTOMER_ID/churn-risk" -H "X-API-Key: $ADMIN_KEY")

    echo "Profile:"
    echo "$CUSTOMER" | python3 -c "
import sys, json
data = json.load(sys.stdin)
metrics = data.get('business_metrics', {})
print(f\"  LTV: \${metrics.get('lifetime_value', 0):.2f}\")
print(f\"  Total Orders: {metrics.get('total_orders', 0)}\")
print(f\"  Avg Order Value: \${metrics.get('avg_order_value', 0):.2f}\")
print(f\"  Days Since Last Purchase: {metrics.get('days_since_last_purchase', 'N/A')}\")
"

    echo "Churn Risk:"
    echo "$CHURN" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"  Probability: {data.get('churn_probability', 0)*100:.1f}%\")
    print(f\"  Risk Level: {data.get('risk_level', 'unknown')}\")
except:
    print('  N/A')
"

    echo ""

    # Save full data
    echo "$CUSTOMER" > "customer_${i}_profile.json"
    echo "$CHURN" > "customer_${i}_churn.json"

    sleep 1
done

echo "✅ Data saved to customer_*_profile.json and customer_*_churn.json"
