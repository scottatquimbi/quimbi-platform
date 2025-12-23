#!/bin/bash
# Update production DATABASE_URL to point to tramway database

echo "=========================================="
echo "UPDATE PRODUCTION DATABASE_URL"
echo "=========================================="
echo ""

echo "Current DATABASE_URL:"
railway variables --environment production 2>&1 | grep -A 3 "DATABASE_URL" | head -4
echo ""

echo "Should be (from DATABASE_PUBLIC_URL):"
railway variables --environment production 2>&1 | grep -A 3 "DATABASE_PUBLIC_URL" | head -4
echo ""

TRAMWAY_URL="postgresql://postgres:ovgyrwRFpdkonlIuQJdPjnXQnrMeGNVK@tramway.proxy.rlwy.net:53924/railway"

echo "=========================================="
echo "To fix this, run ONE of these commands:"
echo "=========================================="
echo ""

echo "Option 1: Via Railway CLI"
echo "-------------------"
echo "railway variables --environment production set DATABASE_URL=\"$TRAMWAY_URL\""
echo ""

echo "Option 2: Via Railway Dashboard"
echo "-------------------"
echo "1. Go to https://railway.app"
echo "2. Select project: patient-friendship"
echo "3. Select environment: production"
echo "4. Click 'Variables' tab"
echo "5. Find DATABASE_URL"
echo "6. Update value to:"
echo "   $TRAMWAY_URL"
echo "7. Click 'Save'"
echo "8. Click 'Restart' to apply changes"
echo ""

echo "After updating, verify with:"
echo "curl https://ecommerce-backend-production-b9cc.up.railway.app/api/mcp/customer/random -H 'X-API-Key: \$ADMIN_KEY'"
echo ""
