# Automated Monthly Segmentation Setup Guide

This guide explains how to set up automated monthly customer re-segmentation using cron jobs.

## Overview

The segmentation system can be automated to run monthly, ensuring customer segments stay fresh as purchasing behavior evolves. The automation includes:

1. **Efficient segmentation** - Discover patterns from sample, assign all customers
2. **Database loading** - Update customer_profiles table with new segments
3. **Validation** - Generate quality reports to monitor segment health
4. **Naming** (optional) - Generate human-readable segment names using Claude AI

## Quick Setup

### 1. Environment Variables

The cron job requires these environment variables:

```bash
# Required
export DATABASE_URL="postgresql://user:password@host:port/database"

# Optional (for segment naming)
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Important:** Cron jobs don't inherit your shell environment by default. You must either:

- **Option A**: Add exports to the cron script itself
- **Option B**: Source a .env file in the cron script
- **Option C**: Set variables in crontab using special syntax

### 2. Test the Script Manually

Before setting up cron, test the script manually:

```bash
# Set environment variables
export DATABASE_URL="postgresql://..."
export ANTHROPIC_API_KEY="sk-ant-..."  # Optional

# Run the script
cd /Users/scottallen/unified-segmentation-ecommerce
./scripts/monthly_resegmentation.sh
```

Check the log output:
```bash
ls -lh logs/segmentation/
tail -100 logs/segmentation/resegmentation_*.log
```

### 3. Set Up Cron Job

Edit your crontab:
```bash
crontab -e
```

Add one of these cron schedules:

#### Monthly (1st of month at 2 AM)
```cron
0 2 1 * * DATABASE_URL="postgresql://..." /Users/scottallen/unified-segmentation-ecommerce/scripts/monthly_resegmentation.sh >> /var/log/segmentation-cron.log 2>&1
```

#### Weekly (Sunday at 3 AM)
```cron
0 3 * * 0 DATABASE_URL="postgresql://..." /Users/scottallen/unified-segmentation-ecommerce/scripts/monthly_resegmentation.sh >> /var/log/segmentation-cron.log 2>&1
```

#### Daily (for testing)
```cron
0 4 * * * DATABASE_URL="postgresql://..." /Users/scottallen/unified-segmentation-ecommerce/scripts/monthly_resegmentation.sh >> /var/log/segmentation-cron.log 2>&1
```

### 4. Verify Cron Setup

List your cron jobs:
```bash
crontab -l
```

Check cron logs (macOS):
```bash
log show --predicate 'eventMessage contains "cron"' --last 1h
```

Check cron logs (Linux):
```bash
grep CRON /var/log/syslog
```

## Cron Schedule Format

```
* * * * * command
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, Sunday = 0 or 7)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

## Advanced Configuration

### Using Environment File

Create a `.env` file:

```bash
# /Users/scottallen/unified-segmentation-ecommerce/.env
DATABASE_URL="postgresql://user:password@host:port/database"
ANTHROPIC_API_KEY="sk-ant-..."
```

Modify the cron script to source it:

```bash
#!/bin/bash
# At top of monthly_resegmentation.sh

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
fi
```

Then your crontab becomes simpler:

```cron
0 2 1 * * /Users/scottallen/unified-segmentation-ecommerce/scripts/monthly_resegmentation.sh >> /var/log/segmentation-cron.log 2>&1
```

### Custom Configuration

You can customize segmentation parameters by editing the script:

```bash
# In monthly_resegmentation.sh
SAMPLE_SIZE=5000      # Customers for pattern discovery
BATCH_SIZE=10000      # Batch size for assignment
```

### Railway Deployment

For production deployment on Railway, use Railway's cron jobs feature:

1. **Railway Cron**: Add a service in your `railway.toml`:

```toml
[deploy]
  cronJobs = ["0 2 1 * * /app/scripts/monthly_resegmentation.sh"]

[env]
  DATABASE_URL = "${{ Railway.DATABASE_URL }}"
  ANTHROPIC_API_KEY = "${{ Railway.ANTHROPIC_API_KEY }}"
```

2. **Or use Railway CLI**:

```bash
railway run scripts/monthly_resegmentation.sh
```

3. **Or GitHub Actions** (recommended for visibility):

Create `.github/workflows/monthly-segmentation.yml`:

```yaml
name: Monthly Customer Segmentation

on:
  schedule:
    # Run on 1st of month at 2 AM UTC
    - cron: '0 2 1 * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  segment:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run segmentation
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          chmod +x scripts/monthly_resegmentation.sh
          ./scripts/monthly_resegmentation.sh

      - name: Upload logs
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: segmentation-logs
          path: logs/segmentation/
```

## Monitoring

### Check Last Run

```bash
# View latest log
ls -t logs/segmentation/resegmentation_*.log | head -1 | xargs tail -100
```

### Check Database Stats

```python
import asyncio
import asyncpg
import os

async def check_segments():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))

    # Overall stats
    result = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN segment_memberships <> '{}' THEN 1 END) as with_segments,
            MAX(last_updated) as last_updated
        FROM customer_profiles
    """)

    print(f"Total customers: {result['total']:,}")
    print(f"With segments: {result['with_segments']:,}")
    print(f"Last updated: {result['last_updated']}")

    # Axes
    result = await conn.fetch("""
        SELECT DISTINCT jsonb_object_keys(segment_memberships) as axis
        FROM customer_profiles
        WHERE segment_memberships <> '{}'
    """)

    print(f"Axes: {len(result)}")
    for row in result:
        print(f"  - {row['axis']}")

    await conn.close()

asyncio.run(check_segments())
```

### Email Notifications

Add email notification to the cron script:

```bash
# At end of monthly_resegmentation.sh

# Send email notification
if command -v mail &> /dev/null; then
    echo "Segmentation completed at $(date)" | mail -s "Monthly Segmentation Complete" you@example.com
fi
```

## Troubleshooting

### Cron Job Not Running

**Check if cron is running:**
```bash
# macOS
sudo launchctl list | grep cron

# Linux
service cron status
```

**Enable cron logging (macOS):**
```bash
# Edit /etc/newsyslog.conf and add:
/var/log/cron.log    640  5     1000 *     J
```

**Check script permissions:**
```bash
ls -l scripts/monthly_resegmentation.sh
# Should show: -rwxr-xr-x
```

### Environment Variables Not Available

Cron has a minimal environment. Debug by adding to script:

```bash
# Add at top of monthly_resegmentation.sh
echo "PATH=$PATH" >> /tmp/cron-debug.log
echo "DATABASE_URL=${DATABASE_URL:0:20}..." >> /tmp/cron-debug.log
env >> /tmp/cron-debug.log
```

### Script Fails

**Check Python path:**
```bash
which python3
# Use full path in cron script if needed
```

**Check working directory:**
```bash
pwd >> /tmp/cron-debug.log
ls -la >> /tmp/cron-debug.log
```

### Logs Not Created

**Ensure log directory exists:**
```bash
mkdir -p logs/segmentation
chmod 755 logs/segmentation
```

**Check disk space:**
```bash
df -h
```

## Performance Tuning

### For Large Datasets (>500K customers)

Adjust parameters:

```bash
SAMPLE_SIZE=3000      # Smaller sample = faster Stage 1
BATCH_SIZE=20000      # Larger batches = fewer DB round-trips
```

### For Small Datasets (<10K customers)

```bash
SAMPLE_SIZE=1000      # 10% sample sufficient
BATCH_SIZE=5000       # Smaller batches fine
```

## Estimated Runtime

Based on 93K customers:

- **Stage 1** (Pattern discovery): ~3-4 minutes (5K sample)
- **Stage 2** (Full population assignment): ~25-30 minutes (93K customers)
- **Validation**: ~30 seconds
- **Naming** (optional): ~2-3 minutes (13 axes × 3-5 segments each)

**Total: ~30-40 minutes**

## Rollback Plan

If a segmentation run fails or produces bad results:

### 1. Keep Backups

Before each run, backup the segments:

```sql
-- Backup current segments
CREATE TABLE customer_profiles_backup AS
SELECT customer_id, segment_memberships, dominant_segments, membership_strengths, last_updated
FROM customer_profiles
WHERE last_updated >= NOW() - INTERVAL '7 days';
```

### 2. Restore from Backup

```sql
-- Restore previous segments
UPDATE customer_profiles cp
SET
    segment_memberships = b.segment_memberships,
    dominant_segments = b.dominant_segments,
    membership_strengths = b.membership_strengths
FROM customer_profiles_backup b
WHERE cp.customer_id = b.customer_id;
```

### 3. Re-run Segmentation

```bash
# Run manually with different parameters
export DATABASE_URL="..."
python3 scripts/load_efficient_segments_to_db.py \
    --csv-path product_sales_order.csv \
    --sample-size 5000 \
    --batch-size 10000
```

## Next Steps

1. ✅ Test manual run
2. ✅ Set up cron job
3. ✅ Monitor first automated run
4. ✅ Set up email notifications
5. ✅ Configure backup strategy
6. ✅ Document in team wiki

## References

- [Efficient Segmentation Documentation](../EFFICIENT_SEGMENTATION.md)
- [Segment Validation Guide](../SEGMENT_VALIDATION.md)
- [API Documentation](../API_DOCUMENTATION.md)
- [Cron Tutorial](https://crontab.guru/)
