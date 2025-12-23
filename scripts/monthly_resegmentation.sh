#!/bin/bash
#
# Monthly Customer Re-Segmentation Job
#
# This script runs the complete segmentation pipeline:
# 1. Run efficient segmentation on all customers
# 2. Load results to Railway database
# 3. Generate segment names using Claude (optional)
# 4. Generate validation report
#
# Designed to run monthly via cron to keep segments fresh.
#
# Usage:
#   ./scripts/monthly_resegmentation.sh
#
# Cron schedule (1st of each month at 2 AM):
#   0 2 1 * * /path/to/unified-segmentation-ecommerce/scripts/monthly_resegmentation.sh >> /var/log/segmentation-cron.log 2>&1

set -e  # Exit on error

# Configuration
PROJECT_DIR="/Users/scottallen/unified-segmentation-ecommerce"
CSV_PATH="$PROJECT_DIR/product_sales_order.csv"
SAMPLE_SIZE=5000
BATCH_SIZE=10000
LOG_DIR="$PROJECT_DIR/logs/segmentation"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/resegmentation_${TIMESTAMP}.log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "MONTHLY CUSTOMER RE-SEGMENTATION STARTING"
log "=========================================="
log "Timestamp: $TIMESTAMP"
log "CSV Path: $CSV_PATH"
log "Sample Size: $SAMPLE_SIZE"
log "Batch Size: $BATCH_SIZE"
log ""

# Change to project directory
cd "$PROJECT_DIR"

# Check required environment variables
if [ -z "$DATABASE_URL" ]; then
    log "ERROR: DATABASE_URL environment variable not set"
    log "Please set it before running this script:"
    log "  export DATABASE_URL='postgresql://user:password@host:port/database'"
    exit 1
fi

if [ ! -f "$CSV_PATH" ]; then
    log "ERROR: CSV file not found at $CSV_PATH"
    log "Please ensure product_sales_order.csv is in the project root"
    exit 1
fi

log "✅ Environment checks passed"
log ""

# Step 1: Run efficient segmentation
log "=========================================="
log "STEP 1: Running efficient segmentation"
log "=========================================="

python3 scripts/load_efficient_segments_to_db.py \
    --csv-path "$CSV_PATH" \
    --sample-size "$SAMPLE_SIZE" \
    --batch-size "$BATCH_SIZE" \
    2>&1 | tee -a "$LOG_FILE"

if [ $? -ne 0 ]; then
    log "ERROR: Segmentation failed"
    exit 1
fi

log "✅ Segmentation completed successfully"
log ""

# Step 2: Generate validation report
log "=========================================="
log "STEP 2: Generating validation report"
log "=========================================="

python3 scripts/validate_segments.py \
    2>&1 | tee -a "$LOG_FILE"

if [ $? -ne 0 ]; then
    log "WARNING: Validation report generation failed (non-critical)"
else
    log "✅ Validation report generated"

    # Move validation report to logs directory
    LATEST_VALIDATION=$(ls -t segment_validation_*.txt 2>/dev/null | head -1)
    if [ -n "$LATEST_VALIDATION" ]; then
        mv "$LATEST_VALIDATION" "$LOG_DIR/"
        log "   Report saved to: $LOG_DIR/$LATEST_VALIDATION"
    fi
fi

log ""

# Step 3: Generate segment names (optional - requires ANTHROPIC_API_KEY)
if [ -n "$ANTHROPIC_API_KEY" ]; then
    log "=========================================="
    log "STEP 3: Generating segment names with Claude"
    log "=========================================="

    python3 scripts/generate_segment_names.py \
        2>&1 | tee -a "$LOG_FILE"

    if [ $? -ne 0 ]; then
        log "WARNING: Segment naming failed (non-critical)"
    else
        log "✅ Segment names generated"

        # Move segment names file to logs directory
        if [ -f "segment_names.json" ]; then
            cp segment_names.json "$LOG_DIR/segment_names_${TIMESTAMP}.json"
            log "   Names saved to: $LOG_DIR/segment_names_${TIMESTAMP}.json"
        fi
    fi
else
    log "⚠️  STEP 3: Skipping segment naming (ANTHROPIC_API_KEY not set)"
fi

log ""

# Summary
log "=========================================="
log "MONTHLY RE-SEGMENTATION COMPLETE"
log "=========================================="
log "Total runtime: $SECONDS seconds"
log "Log file: $LOG_FILE"
log ""

# Query database for final stats
log "Final segment statistics:"
log ""

python3 -c "
import os
import asyncio
import asyncpg

async def get_stats():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))

    # Get overall stats
    result = await conn.fetchrow('''
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN segment_memberships <> '{}' THEN 1 END) as with_segments
        FROM customer_profiles
    ''')

    print(f'  Total customers: {result[\"total\"]:,}')
    print(f'  Customers with segments: {result[\"with_segments\"]:,}')
    print(f'  Segmentation rate: {result[\"with_segments\"]/result[\"total\"]*100:.1f}%')

    # Get axes count
    result = await conn.fetch('''
        SELECT DISTINCT jsonb_object_keys(segment_memberships) as axis
        FROM customer_profiles
        WHERE segment_memberships <> '{}'
    ''')

    print(f'  Axes: {len(result)}')

    await conn.close()

asyncio.run(get_stats())
" 2>&1 | tee -a "$LOG_FILE"

log ""
log "=========================================="
log "✅ ALL STEPS COMPLETED SUCCESSFULLY"
log "=========================================="

exit 0
