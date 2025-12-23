#!/bin/bash
# Clone staging database to production database

set -e  # Exit on error

echo "=========================================================================="
echo "CLONE STAGING DATA TO PRODUCTION DATABASE"
echo "=========================================================================="
echo ""

# Database credentials
STAGING_HOST="switchyard.proxy.rlwy.net"
STAGING_PORT="47164"
STAGING_USER="postgres"
STAGING_PASS="JSKjhRNwAbpJWgRysXyFKNUcopesLIfq"
STAGING_DB="railway"

PROD_HOST="tramway.proxy.rlwy.net"
PROD_PORT="53924"
PROD_USER="postgres"
PROD_PASS="ovgyrwRFpdkonlIuQJdPjnXQnrMeGNVK"
PROD_DB="railway"

DUMP_FILE="/tmp/staging_db_dump_$(date +%Y%m%d_%H%M%S).sql"

echo "Step 1: Testing database connections..."
echo "----------------------------------------"

echo "Testing STAGING connection..."
PGPASSWORD="$STAGING_PASS" psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" -c "SELECT COUNT(*) as customer_count FROM customer_profiles;" || {
    echo "❌ Failed to connect to staging database"
    exit 1
}

echo ""
echo "Testing PRODUCTION connection..."
PGPASSWORD="$PROD_PASS" psql -h "$PROD_HOST" -p "$PROD_PORT" -U "$PROD_USER" -d "$PROD_DB" -c "SELECT version();" || {
    echo "❌ Failed to connect to production database"
    exit 1
}

echo ""
echo "✅ Both database connections successful!"
echo ""

echo "Step 2: Dumping staging database..."
echo "----------------------------------------"
echo "This may take several minutes..."
echo ""

PGPASSWORD="$STAGING_PASS" pg_dump \
    -h "$STAGING_HOST" \
    -p "$STAGING_PORT" \
    -U "$STAGING_USER" \
    -d "$STAGING_DB" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    -f "$DUMP_FILE" || {
    echo "❌ Failed to dump staging database"
    exit 1
}

echo ""
echo "✅ Staging database dumped to: $DUMP_FILE"
echo "   File size: $(du -h "$DUMP_FILE" | cut -f1)"
echo ""

echo "Step 3: Restoring to production database..."
echo "----------------------------------------"
echo "This will REPLACE all data in production!"
echo ""

# Backup production first (optional but recommended)
PROD_BACKUP="/tmp/production_backup_$(date +%Y%m%d_%H%M%S).sql"
echo "Creating production backup first (safety)..."
PGPASSWORD="$PROD_PASS" pg_dump \
    -h "$PROD_HOST" \
    -p "$PROD_PORT" \
    -U "$PROD_USER" \
    -d "$PROD_DB" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    -f "$PROD_BACKUP" 2>/dev/null || echo "⚠️  No existing data to backup"

echo ""
echo "Restoring staging data to production..."
PGPASSWORD="$PROD_PASS" psql \
    -h "$PROD_HOST" \
    -p "$PROD_PORT" \
    -U "$PROD_USER" \
    -d "$PROD_DB" \
    -f "$DUMP_FILE" || {
    echo "❌ Failed to restore to production database"
    echo "Production backup saved at: $PROD_BACKUP"
    exit 1
}

echo ""
echo "✅ Data restored to production!"
echo ""

echo "Step 4: Verifying production database..."
echo "----------------------------------------"

echo "Checking customer_profiles table..."
PGPASSWORD="$PROD_PASS" psql -h "$PROD_HOST" -p "$PROD_PORT" -U "$PROD_USER" -d "$PROD_DB" -c "
SELECT
    COUNT(*) as total_customers,
    COUNT(CASE WHEN dominant_segments IS NOT NULL THEN 1 END) as with_segments,
    SUM(CASE WHEN (business_metrics->>'lifetime_value')::float > 0 THEN 1 ELSE 0 END) as with_ltv
FROM customer_profiles;
" || {
    echo "❌ Failed to verify production data"
    exit 1
}

echo ""
echo "Checking archetypes table..."
PGPASSWORD="$PROD_PASS" psql -h "$PROD_HOST" -p "$PROD_PORT" -U "$PROD_USER" -d "$PROD_DB" -c "
SELECT COUNT(*) as archetype_count FROM archetypes;
" 2>/dev/null || echo "No archetypes table (may be expected)"

echo ""
echo "Checking tickets table..."
PGPASSWORD="$PROD_PASS" psql -h "$PROD_HOST" -p "$PROD_PORT" -U "$PROD_USER" -d "$PROD_DB" -c "
SELECT COUNT(*) as ticket_count FROM tickets;
" 2>/dev/null || echo "No tickets table (may be expected)"

echo ""
echo "=========================================================================="
echo "CLONE COMPLETE!"
echo "=========================================================================="
echo ""
echo "Summary:"
echo "  ✅ Staging data dumped: $DUMP_FILE"
echo "  ✅ Production backup: $PROD_BACKUP (if existed)"
echo "  ✅ Data restored to production"
echo "  ✅ Production database verified"
echo ""
echo "Next steps:"
echo "  1. Update production DATABASE_URL to point to tramway database"
echo "  2. Restart production service"
echo "  3. Test production endpoints"
echo "  4. Set up daily batch updates for production"
echo ""
echo "Cleanup (optional):"
echo "  rm $DUMP_FILE"
echo "  rm $PROD_BACKUP"
echo ""
