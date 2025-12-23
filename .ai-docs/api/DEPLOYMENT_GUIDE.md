# Unified Segmentation System - Deployment Guide

**Version**: 1.0.0
**Date**: October 9, 2025

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Local Development](#local-development)
3. [Railway Deployment](#railway-deployment)
4. [AWS Deployment](#aws-deployment)
5. [Production Checklist](#production-checklist)
6. [Monitoring & Operations](#monitoring--operations)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Git
- Docker (optional, for containerized deployment)

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_ORG/unified-segmentation.git
cd unified-segmentation
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# CRITICAL: Set DATABASE_URL and any API keys
nano .env  # or your preferred editor
```

**Minimum Required Configuration**:
```bash
DATABASE_URL=postgresql://user:password@host:5432/database
```

### 4. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Verify tables created
psql $DATABASE_URL -c "\dt"
# Should show: game_behavioral_taxonomy, behavioral_axes,
#              segment_definitions, player_segment_memberships
```

### 5. Start Service

```bash
# Start FastAPI service
python main.py

# Service will be available at: http://localhost:8000
# API docs: http://localhost:8000/docs
# Health check: http://localhost:8000/health
```

### 6. Test Deployment

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-10-09T10:30:00Z",
  "version": "1.0.0",
  "components": {
    "api": "healthy",
    "database": "healthy"
  }
}
```

---

## Local Development

### Docker Compose Setup

For local development with PostgreSQL and Redis:

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f segmentation-service

# Stop services
docker-compose down
```

Services started:
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`
- **Segmentation Service**: `localhost:8000`

### Database Management

```bash
# Create new migration
alembic revision -m "description of change"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# Check current version
alembic current
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest tests/test_taxonomy_calibration.py -v

# Run specific test
pytest tests/test_categorization.py::TestCategorizationEngine::test_fuzzy_membership -v
```

### Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/my-feature

# 2. Make changes to code

# 3. Run tests
pytest

# 4. Check code quality
black .
ruff check .
mypy backend/

# 5. Commit and push
git add .
git commit -m "Add my feature"
git push origin feature/my-feature
```

---

## Railway Deployment

### Step 1: Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

### Step 2: Create New Project

```bash
# Initialize Railway project
railway init

# Link to existing project (if applicable)
railway link
```

### Step 3: Provision PostgreSQL

```bash
# Add PostgreSQL database
railway add

# Select: PostgreSQL

# Railway will automatically set DATABASE_URL environment variable
```

### Step 4: Configure Environment Variables

```bash
# Set required variables
railway variables set SERVICE_PORT=8000
railway variables set LOG_LEVEL=INFO
railway variables set ENVIRONMENT=production

# Segmentation-specific settings
railway variables set MIN_PLAYER_POPULATION=500
railway variables set VARIANCE_EXPLAINED_THRESHOLD=0.70
railway variables set DEFAULT_LOOKBACK_DAYS=90

# Optional: AI API keys
railway variables set GEMINI_API_KEY=your_key_here
```

### Step 5: Deploy Application

```bash
# Deploy to Railway
railway up

# Or use GitHub integration (recommended for production)
# 1. Connect GitHub repository in Railway dashboard
# 2. Enable auto-deploy on push to main branch
# 3. Push code to GitHub
```

### Step 6: Run Database Migrations

```bash
# SSH into Railway container
railway run bash

# Inside container, run migrations
alembic upgrade head

# Exit
exit
```

### Step 7: Verify Deployment

```bash
# Get deployment URL
railway domain

# Test health endpoint
curl https://your-app.railway.app/health

# View logs
railway logs
```

### Railway Configuration File

Create `railway.json` for advanced configuration:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "python main.py",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

---

## AWS Deployment

### Option 1: AWS Elastic Container Service (ECS)

#### Step 1: Build and Push Docker Image

```bash
# Login to AWS ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t unified-segmentation:1.0.0 .

# Tag image
docker tag unified-segmentation:1.0.0 \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/unified-segmentation:1.0.0

# Push to ECR
docker push \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/unified-segmentation:1.0.0
```

#### Step 2: Create RDS PostgreSQL Database

```bash
# Using AWS CLI
aws rds create-db-instance \
  --db-instance-identifier segmentation-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username segmentation_admin \
  --master-user-password YOUR_SECURE_PASSWORD \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name default
```

#### Step 3: Store Secrets in AWS Secrets Manager

```bash
# Create secret for database URL
aws secretsmanager create-secret \
  --name segmentation/database-url \
  --secret-string "postgresql://user:pass@rds-endpoint:5432/segmentation"

# Create secret for API keys
aws secretsmanager create-secret \
  --name segmentation/api-keys \
  --secret-string '{"GEMINI_API_KEY":"your_key","ANTHROPIC_API_KEY":"your_key"}'
```

#### Step 4: Create ECS Task Definition

Create `aws-ecs-task-definition.json`:

```json
{
  "family": "unified-segmentation",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "segmentation-service",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/unified-segmentation:1.0.0",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "SERVICE_PORT", "value": "8000"},
        {"name": "LOG_LEVEL", "value": "INFO"},
        {"name": "ENVIRONMENT", "value": "production"}
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:segmentation/database-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/unified-segmentation",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

#### Step 5: Deploy to ECS

```bash
# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://aws-ecs-task-definition.json

# Create ECS service
aws ecs create-service \
  --cluster your-cluster \
  --service-name unified-segmentation \
  --task-definition unified-segmentation:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=segmentation-service,containerPort=8000"
```

### Option 2: AWS App Runner

Simpler managed service for containerized applications:

```bash
# Create App Runner service
aws apprunner create-service \
  --service-name unified-segmentation \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "123456789012.dkr.ecr.us-east-1.amazonaws.com/unified-segmentation:1.0.0",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "LOG_LEVEL": "INFO",
          "ENVIRONMENT": "production"
        }
      }
    },
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  }' \
  --health-check-configuration '{
    "Protocol": "HTTP",
    "Path": "/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }'
```

---

## Production Checklist

### Pre-Deployment

- [ ] **Environment Variables Configured**
  - [ ] DATABASE_URL set to production database
  - [ ] API keys configured (if using AI features)
  - [ ] LOG_LEVEL set to INFO or WARNING
  - [ ] ENVIRONMENT set to "production"

- [ ] **Database Ready**
  - [ ] PostgreSQL 14+ provisioned
  - [ ] Database migrations applied (`alembic upgrade head`)
  - [ ] Database backup strategy configured
  - [ ] Connection pooling configured appropriately

- [ ] **Security**
  - [ ] Secrets stored in secure vault (not in code)
  - [ ] REQUIRE_SSL=true for database connections
  - [ ] Rate limiting configured
  - [ ] CORS origins restricted to known domains

- [ ] **Performance**
  - [ ] DB_POOL_SIZE optimized for expected load
  - [ ] CACHE_TTL_SECONDS configured
  - [ ] MAX_CONCURRENT_CATEGORIZATIONS set appropriately

- [ ] **Monitoring**
  - [ ] Health check endpoint accessible
  - [ ] Metrics endpoint configured
  - [ ] Logging aggregation set up
  - [ ] Alerting configured

### Post-Deployment

- [ ] **Smoke Tests**
  - [ ] Health endpoint responds correctly
  - [ ] Taxonomy calibration works
  - [ ] Player categorization works
  - [ ] Anomaly detection works

- [ ] **Performance Validation**
  - [ ] Response times < 100ms for categorization
  - [ ] Database query performance acceptable
  - [ ] No memory leaks observed

- [ ] **Monitoring Setup**
  - [ ] Dashboards created
  - [ ] Alerts configured
  - [ ] On-call rotation established

---

## Monitoring & Operations

### Health Checks

```bash
# Basic health
curl https://your-domain.com/health

# Readiness probe (Kubernetes)
curl https://your-domain.com/health/ready

# Liveness probe (Kubernetes)
curl https://your-domain.com/health/live
```

### Key Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Response Time P95 | <100ms | >200ms |
| Error Rate | <0.1% | >1% |
| Categorization Accuracy | >94% | <92% |
| Database Connections | 50-80% pool | >90% pool |
| Memory Usage | <70% | >85% |
| CPU Usage | <60% | >80% |

### Logging

Structured JSON logs with correlation IDs:

```bash
# View recent logs
tail -f logs/segmentation.log

# Filter by level
grep "ERROR" logs/segmentation.log

# Filter by request ID
grep "req_abc123" logs/segmentation.log
```

### Database Maintenance

```bash
# Check database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('segmentation'));"

# Analyze table statistics
psql $DATABASE_URL -c "ANALYZE player_segment_memberships;"

# Vacuum tables
psql $DATABASE_URL -c "VACUUM ANALYZE;"

# Check index usage
psql $DATABASE_URL -c "
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
"
```

---

## Troubleshooting

### Service Won't Start

**Symptom**: Service crashes on startup

**Common Causes**:
1. Database connection failure
2. Missing environment variables
3. Port already in use

**Solutions**:
```bash
# Check database connectivity
psql $DATABASE_URL -c "SELECT 1;"

# Verify environment variables
env | grep DATABASE_URL

# Check if port is available
lsof -i :8000

# View detailed logs
python main.py  # Run without background mode
```

### Database Migration Failures

**Symptom**: `alembic upgrade head` fails

**Solutions**:
```bash
# Check current migration version
alembic current

# View migration history
alembic history

# Force specific version (use with caution)
alembic stamp head

# Rollback and retry
alembic downgrade -1
alembic upgrade head
```

### Slow Performance

**Symptom**: Response times > 200ms

**Diagnosis**:
```bash
# Check database query performance
psql $DATABASE_URL -c "
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
"

# Check connection pool usage
# Look for "pool size exceeded" in logs

# Check memory usage
docker stats  # If using Docker
```

**Solutions**:
- Increase DB_POOL_SIZE
- Add database indexes
- Enable Redis caching
- Scale horizontally

### Memory Leaks

**Symptom**: Memory usage grows over time

**Diagnosis**:
```bash
# Monitor memory usage
docker stats unified-segmentation

# Profile Python memory
pip install memory_profiler
python -m memory_profiler main.py
```

**Solutions**:
- Restart service periodically
- Review database session management
- Check for unclosed connections

### Connection Pool Exhausted

**Symptom**: "QueuePool limit exceeded" errors

**Solutions**:
```bash
# Increase pool size
export DB_POOL_SIZE=10

# Increase max overflow
# Edit database.py: max_overflow=20

# Check for connection leaks
# Ensure all sessions are properly closed
```

---

## Rollback Procedures

### Application Rollback

```bash
# Railway
railway rollback

# AWS ECS
aws ecs update-service \
  --cluster your-cluster \
  --service unified-segmentation \
  --task-definition unified-segmentation:PREVIOUS_VERSION

# Docker
docker-compose down
docker-compose up -d --build PREVIOUS_TAG
```

### Database Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade REVISION_ID

# Check current version
alembic current
```

---

## Support

- **GitHub Issues**: https://github.com/YOUR_ORG/unified-segmentation/issues
- **Documentation**: https://docs.your-domain.com
- **Email**: support@your-domain.com

---

## Appendix: Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Yes | - | PostgreSQL connection string |
| SERVICE_PORT | No | 8000 | Port to run service on |
| LOG_LEVEL | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| ENVIRONMENT | No | production | Environment name |
| MIN_PLAYER_POPULATION | No | 500 | Minimum players for taxonomy calibration |
| VARIANCE_EXPLAINED_THRESHOLD | No | 0.70 | Target variance explained |
| DEFAULT_LOOKBACK_DAYS | No | 90 | Historical data window |
| AI_OPTIMIZED_SEGMENT_COUNT | No | 7 | Segments sent to AI |
| MAX_CONCURRENT_CATEGORIZATIONS | No | 100 | Concurrent processing limit |
| CACHE_TTL_SECONDS | No | 300 | Cache expiration time |
| DB_POOL_SIZE | No | 5 | Database connection pool size |
| DB_POOL_TIMEOUT | No | 60 | Connection pool timeout (seconds) |
| GEMINI_API_KEY | No | - | Google Gemini API key |
| ANTHROPIC_API_KEY | No | - | Anthropic Claude API key |
| OPENAI_API_KEY | No | - | OpenAI API key |

---

**Version**: 1.0.0
**Last Updated**: October 9, 2025
