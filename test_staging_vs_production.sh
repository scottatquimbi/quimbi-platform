#!/bin/bash
# Compare staging vs production to ensure no breaking changes

STAGING="https://ecommerce-backend-staging-a14c.up.railway.app"
PRODUCTION="https://ecommerce-backend-production-b9cc.up.railway.app"
ADMIN_KEY="${ADMIN_KEY:-e340256ddd65ab5d9643762f62eea44d7dfb95df32685e31}"

echo "======================================================================="
echo "STAGING vs PRODUCTION COMPARISON TEST"
echo "======================================================================="
echo "Staging:    $STAGING"
echo "Production: $PRODUCTION"
echo ""

# Function to test endpoint on both environments
test_endpoint() {
    local name="$1"
    local path="$2"
    local method="${3:-GET}"
    local headers="${4:-}"

    echo "-------------------------------------------------------------------"
    echo "TEST: $name"
    echo "-------------------------------------------------------------------"

    echo "📍 STAGING:"
    if [ "$method" = "GET" ]; then
        if [ -n "$headers" ]; then
            curl -s -w "\nHTTP Status: %{http_code}\n" "$STAGING$path" -H "$headers" 2>&1 | head -15
        else
            curl -s -w "\nHTTP Status: %{http_code}\n" "$STAGING$path" 2>&1 | head -15
        fi
    fi

    echo ""
    echo "🏭 PRODUCTION:"
    if [ "$method" = "GET" ]; then
        if [ -n "$headers" ]; then
            curl -s -w "\nHTTP Status: %{http_code}\n" "$PRODUCTION$path" -H "$headers" 2>&1 | head -15
        else
            curl -s -w "\nHTTP Status: %{http_code}\n" "$PRODUCTION$path" 2>&1 | head -15
        fi
    fi

    echo ""
}

# Test 1: Health Check
test_endpoint "Health Check" "/health"

# Test 2: Root endpoint
test_endpoint "Root Endpoint (Service Info)" "/"

# Test 3: MCP Tools List
test_endpoint "MCP Tools List" "/api/mcp/tools" "GET" "X-API-Key: $ADMIN_KEY"

# Test 4: Customer Lookup (random)
test_endpoint "Random Customer Lookup" "/api/mcp/customer/random" "GET" "X-API-Key: $ADMIN_KEY"

# Test 5: Top Archetypes
test_endpoint "Top Archetypes" "/api/mcp/archetypes/top?limit=3" "GET" "X-API-Key: $ADMIN_KEY"

echo "======================================================================="
echo "DETAILED COMPARISON: Key Endpoints"
echo "======================================================================="

# Test customer profile endpoint with specific customer
echo ""
echo "[CUSTOMER PROFILE TEST]"
echo "Testing with a known customer ID..."
echo ""

echo "📍 STAGING Response:"
STAGING_CUSTOMER=$(curl -s "$STAGING/api/mcp/customer/random" -H "X-API-Key: $ADMIN_KEY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('customer_id', 'none'))" 2>/dev/null)
if [ "$STAGING_CUSTOMER" != "none" ] && [ -n "$STAGING_CUSTOMER" ]; then
    echo "Found customer: $STAGING_CUSTOMER"
    curl -s "$STAGING/api/mcp/customer/$STAGING_CUSTOMER" -H "X-API-Key: $ADMIN_KEY" | python3 -m json.tool 2>/dev/null | head -30
else
    echo "Could not get random customer"
fi

echo ""
echo "🏭 PRODUCTION Response:"
PROD_CUSTOMER=$(curl -s "$PRODUCTION/api/mcp/customer/random" -H "X-API-Key: $ADMIN_KEY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('customer_id', 'none'))" 2>/dev/null)
if [ "$PROD_CUSTOMER" != "none" ] && [ -n "$PROD_CUSTOMER" ]; then
    echo "Found customer: $PROD_CUSTOMER"
    curl -s "$PRODUCTION/api/mcp/customer/$PROD_CUSTOMER" -H "X-API-Key: $ADMIN_KEY" | python3 -m json.tool 2>/dev/null | head -30
else
    echo "Could not get random customer"
fi

echo ""
echo "======================================================================="
echo "BREAKING CHANGE CHECK"
echo "======================================================================="

# Check if both environments have the same critical endpoints
echo ""
echo "[ENDPOINT AVAILABILITY CHECK]"
echo ""

STAGING_ROOT=$(curl -s "$STAGING/" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data.get('endpoints', {}), indent=2))" 2>/dev/null)
PROD_ROOT=$(curl -s "$PRODUCTION/" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data.get('endpoints', {}), indent=2))" 2>/dev/null)

echo "📍 STAGING Endpoints:"
echo "$STAGING_ROOT"

echo ""
echo "🏭 PRODUCTION Endpoints:"
echo "$PROD_ROOT"

echo ""
echo "======================================================================="
echo "NEW FEATURES IN STAGING (Not in Production)"
echo "======================================================================="

# Check staging for new prioritization features
echo ""
echo "[GORGIAS WEBHOOK ENDPOINT]"
echo "Checking if Gorgias webhook is available..."
echo ""

echo "📍 STAGING:"
curl -s -w "HTTP Status: %{http_code}\n" -X POST "$STAGING/api/gorgias/webhook/test" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: test" \
  -d '{"id":"test"}' 2>&1 | head -5

echo ""
echo "🏭 PRODUCTION:"
curl -s -w "HTTP Status: %{http_code}\n" -X POST "$PRODUCTION/api/gorgias/webhook/test" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: test" \
  -d '{"id":"test"}' 2>&1 | head -5

echo ""
echo "======================================================================="
echo "CORS CONFIGURATION CHECK"
echo "======================================================================="

echo ""
echo "Testing CORS headers..."
echo ""

echo "📍 STAGING CORS:"
curl -s -I -X OPTIONS "$STAGING/health" \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control"

echo ""
echo "🏭 PRODUCTION CORS:"
curl -s -I -X OPTIONS "$PRODUCTION/health" \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control"

echo ""
echo "======================================================================="
echo "SUMMARY"
echo "======================================================================="
echo ""
echo "✅ Tests completed!"
echo ""
echo "Review the output above to check:"
echo "  1. Both environments return HTTP 200 for critical endpoints"
echo "  2. Response structures are similar (no breaking changes)"
echo "  3. New features in staging (Gorgias prioritization) work correctly"
echo "  4. CORS headers are properly configured"
echo ""
echo "If all tests show similar responses (except new features), it's safe to deploy!"
echo ""
