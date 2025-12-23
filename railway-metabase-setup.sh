#!/bin/bash
# Railway Metabase Setup Script
# Run this to deploy Metabase to Railway

echo "🚀 Setting up Metabase on Railway..."

# Create new service
railway service create metabase

# Set environment variables
railway variables set \
  MB_DB_TYPE=postgres \
  MB_DB_DBNAME=railway \
  MB_DB_PORT=47164 \
  MB_DB_USER=postgres \
  MB_DB_PASS=JSKjhRNwAbpJWgRysXyFKNUcopesLIfq \
  MB_DB_HOST=switchyard.proxy.rlwy.net \
  MB_SITE_NAME="Customer Segmentation Dashboard"

# Deploy Metabase
railway up --service metabase --image metabase/metabase:latest

# Expose port
railway domain

echo "✅ Metabase deployed! Access it at the domain shown above"
echo ""
echo "📋 Next steps:"
echo "1. Open the Metabase URL"
echo "2. Complete the initial setup wizard"
echo "3. Your PostgreSQL connection should already be configured"
echo "4. Start building dashboards!"
