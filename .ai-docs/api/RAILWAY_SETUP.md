# Railway Deployment Steps

## Quick Setup (5 minutes)

### Step 1: Create Railway Project from GitHub

1. Go to **[railway.app](https://railway.app)** and login
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository: `unified-segmentation` (or whatever you named it)
5. Railway will detect the `Dockerfile` automatically

### Step 2: Add PostgreSQL Database

1. In your Railway project dashboard, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway automatically creates `DATABASE_URL` environment variable
4. No manual configuration needed!

### Step 3: Configure Environment Variables (Optional)

Railway auto-sets `DATABASE_URL`, but you can add optional variables:

1. Go to your service → **"Variables"** tab
2. Add these (optional):

```bash
SERVICE_PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=production

MIN_PLAYER_POPULATION=500
VARIANCE_EXPLAINED_THRESHOLD=0.70
DEFAULT_LOOKBACK_DAYS=90
AI_OPTIMIZED_SEGMENT_COUNT=7

# Optional AI keys (if needed)
GEMINI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

### Step 4: Deploy

1. Click **"Deploy"** (or it auto-deploys if you connected GitHub)
2. Watch the build logs
3. Wait for deployment (usually 2-3 minutes)

### Step 5: Run Database Migration

**Option A: Railway Web Interface**

1. Go to your service → **"Settings"** tab
2. Scroll to **"Deploy"** section
3. Under **"Custom Start Command"**, temporarily set: `alembic upgrade head`
4. Click **"Deploy"** to run migration
5. After migration completes, remove custom start command (revert to `python main.py`)
6. Deploy again

**Option B: Railway CLI** (Recommended)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
cd /path/to/unified-segmentation-deployment
railway link

# Run migration in Railway environment
railway run alembic upgrade head

# Check that tables were created
railway run psql $DATABASE_URL -c "\dt"
```

### Step 6: Get Your Deployment URL

1. Go to **"Settings"** → **"Networking"**
2. Click **"Generate Domain"**
3. Your URL will be something like: `https://unified-segmentation-production.up.railway.app`

### Step 7: Test Deployment

```bash
# Health check
curl https://your-app.railway.app/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-10-09T...",
  "version": "1.0.0",
  "components": {
    "api": "healthy",
    "database": "healthy"
  }
}

# API docs (visit in browser)
https://your-app.railway.app/docs
```

---

## CLI Deployment (Alternative)

If you prefer using Railway CLI:

```bash
# 1. Install CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Navigate to deployment folder
cd /path/to/unified-segmentation-deployment

# 4. Initialize new project
railway init

# 5. Add PostgreSQL
railway add

# Select: PostgreSQL

# 6. Deploy
railway up

# 7. Run migrations
railway run alembic upgrade head

# 8. Get deployment URL
railway domain

# 9. View logs
railway logs
```

---

## Troubleshooting

### Build Fails

**Issue**: Docker build fails

**Solution**: Check build logs in Railway dashboard
- Verify `Dockerfile` is in root directory
- Check that all files are committed to GitHub
- Ensure `requirements.txt` has all dependencies

### Migration Fails

**Issue**: `alembic upgrade head` fails

**Solution**:
```bash
# Check database connectivity
railway run psql $DATABASE_URL -c "SELECT 1"

# Check current migration version
railway run alembic current

# Force stamp if needed (use carefully)
railway run alembic stamp head
```

### Service Won't Start

**Issue**: Service keeps restarting

**Solution**:
```bash
# Check logs
railway logs

# Common issues:
# 1. DATABASE_URL not set (should be auto-set by Railway)
# 2. Port mismatch (Railway sets PORT env var, our app uses SERVICE_PORT)
```

**Fix for port issue**: Update `main.py` to use Railway's PORT:

```python
# At bottom of main.py
if __name__ == "__main__":
    import os

    # Railway sets PORT, we use SERVICE_PORT, fallback to 8000
    port = int(os.getenv("PORT") or os.getenv("SERVICE_PORT", 8000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        ...
    )
```

### Can't Access API

**Issue**: Getting 404 or connection refused

**Solution**:
1. Verify deployment succeeded (check Railway dashboard)
2. Generate public domain (Settings → Networking → Generate Domain)
3. Check health endpoint first: `https://your-app.railway.app/health`

---

## Post-Deployment Checklist

- [ ] Health endpoint responds: `/health`
- [ ] Database tables created (4 tables)
- [ ] API docs accessible: `/docs`
- [ ] Environment variables set correctly
- [ ] Logs show no errors
- [ ] Can access from external network

---

## Monitoring Your Deployment

### View Logs
```bash
railway logs --tail
```

### Check Resource Usage
Go to Railway dashboard → **"Metrics"** tab

### Database Access
```bash
# Connect to database
railway run psql $DATABASE_URL

# Check tables
\dt

# Check data
SELECT * FROM game_behavioral_taxonomy LIMIT 5;
```

---

## Cost Estimate

**Railway Pricing** (as of 2025):
- **Hobby Plan**: $5/month
  - Includes $5 usage credit
  - PostgreSQL database included
  - Good for development/testing

- **Pro Plan**: $20/month
  - Includes $20 usage credit
  - Better for production
  - More resources

**Estimated monthly cost for this app**: $5-15/month depending on usage

---

## Need Help?

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **This Project Issues**: [Your GitHub repo]/issues

---

## Quick Reference Commands

```bash
# View deployment status
railway status

# View logs
railway logs

# Run commands in Railway environment
railway run [command]

# Connect to database
railway connect postgres

# Redeploy
railway up

# View environment variables
railway variables
```

---

**Next Step**: Follow Step 1 above to create your Railway project!
