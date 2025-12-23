"""
E-Commerce Customer Intelligence API

FastAPI application providing:
1. MCP tools for AI agents (6 tools)
2. Gorgias webhook integration
3. Customer behavioral segmentation

Author: Quimbi AI
Version: 1.0.0 (E-Commerce)
Date: October 16, 2025
"""

import logging
import sys
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Header, Depends, Query, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import MCP server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_server.segmentation_server import handle_mcp_call, MCP_TOOLS, data_store

# Import API key verification
from backend.api.auth import verify_api_key

# Import structured logging
from backend.middleware.logging_config import configure_logging, get_logger, correlation_id_middleware

# Import error handling
from backend.middleware.error_handling import (
    APIError,
    NotFoundError,
    ValidationError,
    AuthenticationError,
    api_error_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)

# Import tenant routing middleware for multi-tenant support
from backend.middleware.tenant_routing import TenantRoutingMiddleware

# Import Redis cache
from backend.cache.redis_cache import (
    cache,
    get_cached_customer,
    cache_customer,
    get_cached_churn_prediction,
    cache_churn_prediction,
    get_cache_stats
)

# Import Prometheus metrics (optional)
from backend.middleware.metrics import metrics_middleware, metrics_endpoint, METRICS_ENABLED

# Import routers
from backend.api.routers import (
    admin_router,
    health_router,
    customers_router,
    customer_alias_router,
    analytics_router,
    campaigns_router,
    mcp_router,
    webhooks_router,
    segments_router,
    system_router,
    tickets_router,
    ai_router,
    drift_router,
)

# Import platform routers
from backend.platform import (
    intelligence_router,
    generation_router,
)

# Import authentication dependencies
from backend.api.dependencies import require_api_key

# Configure structured logging
# Use JSON format in production (Railway), console format for local dev
json_logs = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("JSON_LOGS", "false").lower() == "true"
log_level = os.getenv("LOG_LEVEL", "INFO")
configure_logging(log_level=log_level, json_logs=json_logs)

# Get structured logger
logger = get_logger(__name__)


# ==================== Application Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("application_starting", version="1.0.0", platform="E-Commerce Customer Intelligence API")

    # ==================== Security Validation ====================
    # Validate required secrets
    required_secrets = ["ADMIN_KEY"]
    missing_secrets = [s for s in required_secrets if not os.getenv(s)]

    if missing_secrets:
        logger.error("security_validation_failed", missing_secrets=missing_secrets)
        raise RuntimeError(f"Missing required secrets: {', '.join(missing_secrets)}")

    # Validate ADMIN_KEY is strong
    admin_key = os.getenv("ADMIN_KEY")
    if len(admin_key) < 16:
        logger.error("security_validation_failed", reason="ADMIN_KEY too short", min_length=16)
        raise RuntimeError("ADMIN_KEY must be at least 16 characters")
    if admin_key.lower() in ["changeme123", "admin", "password", "test", "secret"]:
        logger.error("security_validation_failed", reason="ADMIN_KEY is common password")
        raise RuntimeError("ADMIN_KEY must not be a common password")

    logger.info("security_validation_passed")

    # ==================== Cache Initialization ====================
    # Connect to Redis cache (if enabled)
    await cache.connect()

    # Initialize scheduler (will be used for Azure SQL sync)
    scheduler = None

    # Check if we should load data from PostgreSQL
    skip_data_load = os.getenv("SKIP_DATA_LOAD", "false").lower() == "true"
    database_url = os.getenv("DATABASE_URL")

    if skip_data_load:
        logger.info("data_loading_skipped", reason="SKIP_DATA_LOAD=true", mode="query_on_demand")
    elif database_url:
        logger.info("data_loading_started", source="postgresql", schema="star_schema")
        try:
            from backend.loaders import load_all_data_from_star_schema

            # Load from star schema (L2 by default)
            archetype_level = os.getenv("ARCHETYPE_LEVEL", "l2")
            customers_dict, archetypes_dict = await load_all_data_from_star_schema(
                archetype_level=archetype_level
            )

            # Populate MCP data store
            data_store.customers = customers_dict
            data_store.archetypes = archetypes_dict
            data_store.loaded = True

            logger.info(
                "data_loading_completed",
                customer_count=len(customers_dict),
                archetype_count=len(archetypes_dict),
                source="postgresql"
            )
        except Exception as e:
            logger.error("data_loading_failed", error=str(e), source="postgresql", exc_info=True)
            logger.warning("data_store_empty", reason="data_loading_failed")
    else:
        logger.info("data_store_mode", mode="in_memory", reason="no_database_url")

    # Check data store status
    customer_count = len(data_store.customers)
    archetype_count = len(data_store.archetypes)
    logger.info(
        "mcp_server_ready",
        customer_count=customer_count,
        archetype_count=archetype_count,
        data_loaded=customer_count > 0
    )

    if customer_count == 0:
        logger.warning(
            "no_customer_data",
            impact="MCP tools will return empty results",
            action_required="Set DATABASE_URL and upload data to PostgreSQL"
        )

    # ==================== Azure SQL Sync Scheduler ====================
    # Schedule automatic sync of product sales data from Azure SQL to Postgres
    if os.getenv("ENABLE_SALES_SYNC", "true").lower() == "true":
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            import asyncio
            import fcntl  # For file locking on Unix

            scheduler = AsyncIOScheduler()

            # Create lock file path
            SYNC_LOCK_FILE = "/tmp/ecommerce_sync.lock"

            async def sync_product_sales():
                """
                Run incremental product sales sync from Azure SQL (async version).

                Uses file locking to prevent concurrent syncs.
                """
                logger.info("🔄 Starting scheduled product sales sync...")

                # Try to acquire lock
                lock_fd = None
                try:
                    # Open lock file
                    lock_fd = open(SYNC_LOCK_FILE, "w")

                    # Try to acquire exclusive lock (non-blocking)
                    try:
                        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        logger.warning("⏭️  Skipping sync - another sync is already running")
                        return

                    logger.info("🔒 Sync lock acquired")

                    # Run sync as async subprocess
                    process = await asyncio.create_subprocess_exec(
                        "python",
                        "scripts/sync_combined_sales_simple.py",
                        "--incremental",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd="/app"  # Railway app directory
                    )

                    # Wait for completion with timeout
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            process.communicate(),
                            timeout=600  # 10 minute timeout
                        )

                        stdout_text = stdout.decode('utf-8')
                        stderr_text = stderr.decode('utf-8')

                        if process.returncode == 0:
                            logger.info("✅ Product sales sync completed successfully")
                            if stdout_text:
                                logger.info(f"Sync output: {stdout_text[-500:]}")  # Last 500 chars
                        else:
                            logger.error(f"❌ Product sales sync failed with code {process.returncode}")
                            if stderr_text:
                                logger.error(f"Sync stderr: {stderr_text}")

                    except asyncio.TimeoutError:
                        logger.error("⏰ Product sales sync timed out after 10 minutes")
                        process.kill()
                        await process.wait()

                except Exception as e:
                    logger.error(f"❌ Product sales sync error: {e}", exc_info=True)

                finally:
                    # Release lock
                    if lock_fd:
                        try:
                            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                            lock_fd.close()
                            logger.info("🔓 Sync lock released")
                        except Exception as e:
                            logger.error(f"Error releasing lock: {e}")

            # Schedule daily sync at 2 AM UTC
            sync_hour = int(os.getenv("SALES_SYNC_HOUR", "2"))
            scheduler.add_job(
                sync_product_sales,
                'cron',
                hour=sync_hour,
                minute=0,
                id='product_sales_sync',
                name='Azure SQL Product Sales Sync',
                replace_existing=True
            )

            scheduler.start()
            logger.info(f"📅 Product sales sync scheduler started (daily at {sync_hour}:00 UTC)")

            # Run initial sync on startup (optional)
            if os.getenv("SYNC_ON_STARTUP", "false").lower() == "true":
                logger.info("Running initial product sales sync on startup...")
                asyncio.create_task(sync_product_sales())

        except ImportError:
            logger.warning("⚠️  APScheduler not installed - sales sync disabled")
            logger.warning("   Install with: pip install APScheduler==3.10.4")
        except Exception as e:
            logger.error(f"Failed to setup sales sync scheduler: {e}")
    else:
        logger.info("Sales sync disabled (ENABLE_SALES_SYNC=false)")

    # ==================== Application Running ====================

    yield

    # ==================== Shutdown ====================
    logger.info("Shutting down...")

    # Disconnect from Redis cache
    await cache.disconnect()

    # Stop scheduler if running
    if scheduler:
        scheduler.shutdown()
        logger.info("Sales sync scheduler stopped")


# ==================== FastAPI Application ====================

app = FastAPI(
    title="E-Commerce Customer Intelligence API",
    description="""
## Quimbi Customer Intelligence Platform

AI-powered customer segmentation and support ticketing system for e-commerce.

### Features

#### 1. 13-Axis Behavioral Segmentation
- **Purchase Behavior**: Frequency, Value, Category Exploration, Price Sensitivity, Cadence, Maturity, Repurchase, Returns
- **Support Behavior**: Communication Preference, Problem Complexity, Loyalty Trajectory, Product Knowledge, Value Sophistication

#### 2. Intelligent Support Ticketing
- Full-featured ticketing system with multi-channel support
- AI-powered next best action recommendations using Claude 3.5 Haiku
- Automated draft response generation personalized to customer
- Churn risk integration and LTV-based prioritization

#### 3. MCP Tools for AI Agents
- 6 tools for retrieving customer intelligence, archetypes, and churn predictions
- Compatible with Claude Desktop, Cline, and other MCP clients

#### 4. Analytics & Campaigns
- Real-time customer dashboards
- Campaign management with archetype targeting
- Churn prediction and retention analytics

### Authentication

All API endpoints require authentication via `X-API-Key` header.

Contact your system administrator for API credentials.

### Support

- **Documentation**: See individual endpoint descriptions below
- **GitHub Issues**: [Report bugs](https://github.com/your-org/quimbi)
- **Email**: support@quimbi.com
    """,
    version="1.0.0",
    redirect_slashes=False,  # Prevent HTTPS→HTTP redirects and trailing slash issues
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "system",
            "description": "System configuration for dynamic frontend rendering. Returns all 13 behavioral axes with segment definitions."
        },
        {
            "name": "tickets",
            "description": "Complete ticketing system CRUD operations. Create tickets, send messages, add notes, filter and search."
        },
        {
            "name": "ai",
            "description": "AI-powered features using Claude 3.5 Haiku. Next best actions, draft responses, personalized recommendations."
        },
        {
            "name": "health",
            "description": "Health check and system status endpoints"
        },
        {
            "name": "admin",
            "description": "Administrative endpoints for system management"
        },
        {
            "name": "customers",
            "description": "Customer profile and intelligence endpoints"
        },
        {
            "name": "analytics",
            "description": "Analytics dashboards and metrics"
        },
        {
            "name": "campaigns",
            "description": "Campaign management and targeting"
        },
        {
            "name": "mcp",
            "description": "Model Context Protocol tools for AI agents"
        },
        {
            "name": "webhooks",
            "description": "Webhook integrations (Gorgias, Shopify, etc.)"
        },
        {
            "name": "segments",
            "description": "Customer segmentation and archetype queries"
        }
    ]
)

# ==================== Exception Handlers ====================
# Register custom exception handlers
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

logger.info("error_handlers_registered", handlers=["APIError", "HTTPException", "ValidationError", "Exception"])

# ==================== Rate Limiting ====================
# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger.info("rate_limiting_enabled", default_limit="100/hour")

# CORS middleware - configured from environment
# Parse comma-separated list of allowed origins
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8080"  # Development defaults (added Vite default port)
).split(",")

# Validate no wildcard in production
if os.getenv("RAILWAY_ENVIRONMENT") == "production" and "*" in ALLOWED_ORIGINS:
    raise ValueError("Wildcard CORS origins not allowed in production")

# Middleware to fix HTTPS redirects (Railway proxy issue)
@app.middleware("http")
async def https_redirect_fix_middleware(request: Request, call_next):
    """
    Fix redirect URLs to preserve HTTPS protocol.

    Railway's proxy terminates SSL, so FastAPI sees HTTP and generates
    HTTP redirect URLs. This middleware fixes the Location header.
    """
    response = await call_next(request)

    # If this is a redirect response
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("location")
        if location and location.startswith("http://"):
            # Replace http:// with https://
            fixed_location = location.replace("http://", "https://", 1)
            response.headers["location"] = fixed_location
            logger.debug("fixed_redirect_protocol", original=location, fixed=fixed_location)

    return response

# Add correlation ID middleware (must be FIRST for proper logging context)
app.middleware("http")(correlation_id_middleware)

# Add Prometheus metrics middleware (optional - only if enabled)
if METRICS_ENABLED:
    app.middleware("http")(metrics_middleware)
    logger.info("prometheus_middleware_enabled")

# Add tenant routing middleware for multi-tenant support
# This identifies the tenant from subdomain, API key, or webhook
# and sets the tenant context for the request
app.add_middleware(TenantRoutingMiddleware)
logger.info("tenant_routing_middleware_enabled", strategies=["subdomain", "api_key", "webhook"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],  # Include OPTIONS for preflight and PATCH for updates
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Admin-Key",
        "X-Correlation-ID",
        "Accept",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "X-Requested-With"
    ],  # Explicit headers required when credentials are enabled
    expose_headers=[
        "Content-Type",
        "X-Correlation-ID",
        "X-Total-Count",
        "X-Page",
        "X-Page-Size"
    ],  # Explicit headers required when credentials are enabled
)

logger.info("cors_configured", origins=ALLOWED_ORIGINS)


# ==================== Include Routers ====================
# Include modular routers (refactored from monolithic structure)
app.include_router(health_router)
app.include_router(admin_router)

# Platform Intelligence APIs (for external consumption)
app.include_router(intelligence_router)
app.include_router(generation_router)

# Support App APIs (internal + legacy)
app.include_router(customers_router)
app.include_router(customer_alias_router)  # Alias for /api/customers/{id} → /api/mcp/customer/{id}
app.include_router(analytics_router)
app.include_router(campaigns_router)
app.include_router(mcp_router)
app.include_router(webhooks_router)
app.include_router(segments_router)
app.include_router(system_router)
app.include_router(tickets_router)
app.include_router(ai_router)  # Legacy - kept for backward compatibility
app.include_router(drift_router)  # Temporal snapshots & drift detection

logger.info("routers_registered", routers=["health", "admin", "intelligence", "generation", "customers", "customer_alias", "analytics", "campaigns", "mcp", "webhooks", "segments", "system", "tickets", "ai", "drift"])


# ==================== Request/Response Models ====================

class MCPToolRequest(BaseModel):
    tool_name: str = Field(..., description="MCP tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class MCPToolResponse(BaseModel):
    tool_name: str
    result: Dict[str, Any]
    timestamp: datetime


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    components: Dict[str, str]
    data_status: Dict[str, Any]


# ==================== Health & Monitoring Endpoints ====================

@app.get("/")
@limiter.limit("100/hour")
async def root(request: Request):
    """Root endpoint with service information."""
    return {
        "service": "E-Commerce Customer Intelligence API",
        "version": "1.0.0",
        "status": "operational",
        "use_cases": [
            "Analytics/BI - Internal Slack bot",
            "Customer Service - Gorgias integration",
            "Marketing - Campaign targeting"
        ],
        "endpoints": {
            "health": "/health",
            "mcp_tools": "/api/mcp/tools",
            "mcp_query": "/api/mcp/query",
            "gorgias_webhook": "/api/gorgias/webhook",
            "docs": "/docs"
        }
    }


# ==================== Health Check Endpoints ====================
# NOTE: Health endpoints moved to backend/api/routers/health.py
# Router included above via app.include_router(health_router)
# Endpoints available: /health, /health/ready, /health/live, /metrics


# ==================== Admin Endpoints ====================
# NOTE: Admin endpoints moved to backend/api/routers/admin.py
# Router included above via app.include_router(admin_router)
# Endpoints available: /admin/sync-status, /admin/cache/stats, /admin/db/pool, /admin/sync-sales


# ==================== MCP & Customer Endpoints ====================
# NOTE: MCP endpoints moved to backend/api/routers/mcp.py
# NOTE: Customer endpoints moved to backend/api/routers/customers.py
# NOTE: Analytics endpoints moved to backend/api/routers/analytics.py
# NOTE: Campaign endpoints moved to backend/api/routers/campaigns.py
# NOTE: Webhook endpoints moved to backend/api/routers/webhooks.py
# All routers included above via app.include_router()


@app.post("/api/mcp/query/natural-language", dependencies=[Depends(require_api_key)])
@limiter.limit("50/hour")  # Lower limit for AI queries (more expensive)
async def natural_language_query(
    request: Request,
    query: str = Query(..., description="Natural language business question")
):
    """
    Process natural language business questions using Claude AI function calling.

    Protected by rate limiting and CORS. API key authentication available but not enforced.

    This endpoint uses Claude 3.5 Haiku to interpret user intent and route to
    appropriate analysis endpoints. Supports any phrasing naturally.

    Examples:
    - "what archetypes should we focus on this holiday season"
    - "how many people will be engaged during halloween"
    - "which customers are most likely to churn next month"
    - "what's our revenue forecast for Q4"
    - "who should we target for Black Friday campaign"
    """
    try:
        import anthropic

        # Initialize Anthropic client
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            # Fallback to pattern matching if no API key
            logger.warning("ANTHROPIC_API_KEY not set, using pattern matching fallback")
            return await _fallback_pattern_matching(query)

        client = anthropic.Anthropic(api_key=anthropic_key)

        # Feature flag for new consolidated tools (A/B testing)
        USE_CONSOLIDATED_TOOLS = os.getenv("USE_CONSOLIDATED_MCP_TOOLS", "false").lower() == "true"

        if USE_CONSOLIDATED_TOOLS:
            # NEW: 5 Consolidated Tools (v2) - Optimized for clarity and reduced AI confusion
            ANALYSIS_TOOLS = [
                {
                    "name": "query_customers",
                    "description": """Find and analyze customers based on value, behavior, risk, and patterns. Use this for ANY question about individual customers or lists of customers.

                    Examples:
                    - "Show me my best customers" → scope: list, filters.ltv_min: 5000
                    - "Who is at risk of churning?" → scope: list, filters.churn_risk_min: 0.7
                    - "Find one-time buyers" → scope: list, filters.total_orders_max: 1
                    - "Show me customer 5971333382399" → scope: individual, customer_id: "5971333382399"
                    - "High-value customers who haven't purchased in 90 days" → scope: list, filters.ltv_min: 2000, filters.last_purchase_days_min: 90
                    """,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "scope": {
                                "type": "string",
                                "enum": ["individual", "list"],
                                "description": "Query a single customer (requires customer_id) or get a filtered list",
                                "default": "list"
                            },
                            "customer_id": {
                                "type": "string",
                                "description": "Required if scope='individual'. Customer ID or email address"
                            },
                            "info_requested": {
                                "type": "array",
                                "items": {
                                    "enum": ["profile", "churn_risk", "purchase_history", "ltv_forecast", "recommendations", "segment_membership"]
                                },
                                "description": "What information to return. Defaults to ['profile'] for list, ['profile', 'churn_risk'] for individual",
                                "default": ["profile"]
                            },
                            "filters": {
                                "type": "object",
                                "properties": {
                                    "churn_risk_min": {"type": "number", "description": "Minimum churn risk 0.0-1.0 (0.7=critical, 0.5=high, 0.3=medium)"},
                                    "churn_risk_max": {"type": "number", "description": "Maximum churn risk 0.0-1.0"},
                                    "ltv_min": {"type": "number", "description": "Minimum lifetime value in dollars"},
                                    "ltv_max": {"type": "number", "description": "Maximum lifetime value in dollars"},
                                    "segment": {"type": "string", "description": "Filter by segment name"},
                                    "archetype_id": {"type": "string", "description": "Filter by archetype ID"},
                                    "last_purchase_days_min": {"type": "integer", "description": "Minimum days since last purchase"},
                                    "last_purchase_days_max": {"type": "integer", "description": "Maximum days since last purchase"},
                                    "total_orders_min": {"type": "integer", "description": "Minimum number of orders"},
                                    "total_orders_max": {"type": "integer", "description": "Maximum orders (use 1 for one-time buyers)"},
                                    "behavior_pattern": {
                                        "type": "string",
                                        "enum": ["one_time_buyer", "frequent_buyer", "seasonal_shopper", "declining_engagement", "growing_engagement", "discount_dependent", "premium_buyer", "routine_buyer", "erratic_buyer"],
                                        "description": "Filter by detected behavioral pattern"
                                    },
                                    "is_b2b": {"type": "boolean", "description": "Filter for B2B vs B2C customers"},
                                    "price_sensitivity": {"type": "string", "enum": ["high", "medium", "low"]}
                                },
                                "description": "All filters use AND logic"
                            },
                            "sort_by": {
                                "type": "string",
                                "enum": ["ltv_desc", "ltv_asc", "churn_risk_desc", "churn_risk_asc", "impact_desc", "recency_desc", "recency_asc", "frequency_desc", "frequency_asc", "aov_desc"],
                                "default": "ltv_desc"
                            },
                            "limit": {"type": "integer", "default": 100, "maximum": 1000}
                        }
                    }
                },
                {
                    "name": "query_segments",
                    "description": """Analyze CUSTOMER SEGMENTS and archetypes - understand who your CUSTOMER TYPES are, how they behave, and how they're changing.

                    ⚠️ IMPORTANT: Use this tool when user asks about CUSTOMER TYPES/SEGMENTS, not product types.
                    - "customer type/segment" → use THIS tool
                    - "product type/category" → use analyze_products tool

                    Use this for questions containing: "customer type", "customer segment", "which customers", "what kind of customers", "customer behavior"

                    Examples:
                    - "What types of customers do I have?" → analysis: overview
                    - "Which customer segments are growing?" → analysis: growth, filters.growth_trend: growing
                    - "Who are my Halloween shoppers?" → analysis: seasonal, event: halloween
                    - "Compare premium vs budget shoppers" → analysis: comparison, segment_ids: [...]
                    - "What type of customer has the highest repeat purchases?" → analysis: overview, sort_by: frequency
                    - "What customer type repurchases most?" → analysis: overview, sort_by: frequency
                    - "Which customer segment is most loyal?" → analysis: overview, sort_by: frequency
                    - "Show me customer segments by repeat behavior" → analysis: overview, sort_by: frequency
                    """,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "analysis": {
                                "type": "string",
                                "enum": ["overview", "growth", "comparison", "seasonal"],
                                "description": "Type of segment analysis",
                                "default": "overview"
                            },
                            "segment_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "For analysis='comparison': 2-5 segment IDs to compare"
                            },
                            "filters": {
                                "type": "object",
                                "properties": {
                                    "growth_trend": {"type": "string", "enum": ["growing", "shrinking", "stable"]},
                                    "value_tier": {"type": "string", "enum": ["high", "medium", "low"]},
                                    "risk_level": {"type": "string", "enum": ["at_risk", "healthy"]},
                                    "size_min": {"type": "integer"},
                                    "size_max": {"type": "integer"}
                                }
                            },
                            "event": {
                                "type": "string",
                                "enum": ["halloween", "thanksgiving", "black_friday", "cyber_monday", "christmas", "holiday_season", "new_year", "valentines", "easter", "spring", "summer", "fall", "winter", "back_to_school"],
                                "description": "For analysis='seasonal'"
                            },
                            "timeframe_months": {"type": "integer", "default": 12, "minimum": 1, "maximum": 36},
                            "sort_by": {"type": "string", "enum": ["size", "ltv", "total_revenue", "growth_rate", "churn_rate", "frequency", "recency"], "default": "total_revenue", "description": "Sort segments by: size (customer count), ltv (avg lifetime value), total_revenue, growth_rate, churn_rate, frequency (avg orders per customer - use for repeat purchases), recency (avg days since last order)"},
                            "limit": {"type": "integer", "default": 10, "maximum": 50},
                            "include_details": {"type": "boolean", "default": True}
                        }
                    }
                },
                {
                    "name": "forecast_business_metrics",
                    "description": """Forecast future business performance - predict revenue, customer growth, churn, and value metrics over time.

                    Examples:
                    - "What will Q4 revenue be?" → metrics: ["revenue"], timeframe_months: 3
                    - "How many customers next year?" → metrics: ["customer_count"], timeframe_months: 12
                    - "Revenue and churn forecast" → metrics: ["revenue", "churn_rate"]
                    """,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "metrics": {
                                "type": "array",
                                "items": {"enum": ["revenue", "customer_count", "new_customers", "churned_customers", "average_ltv", "average_aov", "churn_rate", "retention_rate"]},
                                "description": "Which metrics to forecast (can request multiple)",
                                "default": ["revenue", "customer_count"]
                            },
                            "timeframe_months": {"type": "integer", "default": 12, "minimum": 1, "maximum": 36},
                            "breakdown": {"type": "string", "enum": ["monthly", "quarterly", "annual", "total_only"], "default": "monthly"},
                            "segment_filter": {"type": "string", "description": "Optional: forecast for specific segment only"},
                            "confidence_interval": {"type": "boolean", "default": True},
                            "assumptions": {
                                "type": "object",
                                "properties": {
                                    "acquisition_rate_change": {"type": "number"},
                                    "churn_rate_change": {"type": "number"},
                                    "aov_change": {"type": "number"}
                                }
                            }
                        }
                    }
                },
                {
                    "name": "plan_campaign",
                    "description": """Get campaign targeting recommendations - who to target, when, how, and why. Use this for marketing campaigns, outreach, retention strategies.

                    Examples:
                    - "Who should I target for retention?" → goal: retention
                    - "Black Friday campaign targets" → goal: seasonal, event: black_friday
                    - "Upsell opportunities" → goal: growth
                    - "Win-back lapsed customers" → goal: winback
                    """,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "enum": ["retention", "growth", "winback", "acquisition", "loyalty", "cross_sell", "seasonal"],
                                "description": "Primary campaign objective"
                            },
                            "event": {
                                "type": "string",
                                "enum": ["halloween", "thanksgiving", "black_friday", "cyber_monday", "christmas", "new_year", "valentines", "spring_sale", "summer_clearance", "back_to_school"],
                                "description": "For goal='seasonal'"
                            },
                            "constraints": {
                                "type": "object",
                                "properties": {
                                    "budget_total": {"type": "number"},
                                    "cost_per_customer": {"type": "number"},
                                    "min_ltv": {"type": "number"},
                                    "max_churn_risk": {"type": "number"},
                                    "min_churn_risk": {"type": "number"},
                                    "segment_filter": {"type": "string"},
                                    "exclude_recent_campaign": {"type": "boolean", "default": True}
                                }
                            },
                            "target_size": {"type": "integer", "default": 100, "minimum": 10, "maximum": 10000},
                            "include_strategy": {"type": "boolean", "default": True},
                            "prioritize_by": {"type": "string", "enum": ["impact", "ltv", "churn_risk", "roi_potential", "conversion"], "default": "impact"},
                            "output_format": {"type": "string", "enum": ["summary", "detailed", "export_ready"], "default": "detailed"}
                        },
                        "required": ["goal"]
                    }
                },
                {
                    "name": "analyze_products",
                    "description": """Analyze PRODUCT CATEGORIES and individual products - revenue, bundles, and purchasing patterns using order-level sales data.

                    ⚠️ IMPORTANT: Use this tool for PRODUCT/CATEGORY questions, NOT customer type questions.
                    - "product/category repurchase rate" → use THIS tool
                    - "customer type/segment repurchase rate" → use query_segments tool

                    Use this for questions containing: "product", "category", "what products", "which products", "product bundles"

                    Examples:
                    - "Top selling products" → analysis_type: individual_product_performance
                    - "What products do customers buy together?" → analysis_type: product_bundles
                    - "Which product categories are growing?" → analysis_type: category_trends
                    - "Which product categories have highest repurchase rate?" → analysis_type: category_repurchase_rate
                    - "What do VIP customers buy?" → analysis_type: category_by_customer_segment, segment_filter: high_value
                    """,
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "analysis_type": {
                                "type": "string",
                                "enum": ["revenue_by_category", "category_popularity", "category_by_customer_segment", "category_trends", "category_repurchase_rate", "category_value_metrics", "product_bundles", "seasonal_product_performance", "individual_product_performance"]
                            },
                            "segment_filter": {"type": "string"},
                            "sort_by": {"type": "string", "enum": ["revenue", "customer_count", "aov", "total_orders", "growth_rate", "repurchase_rate"], "default": "revenue"},
                            "timeframe_months": {"type": "integer", "default": 12},
                            "limit": {"type": "integer", "default": 10}
                        },
                        "required": ["analysis_type"]
                    }
                }
            ]
        else:
            # OLD: 8 Original Tools (v1) - Keep for A/B testing comparison
            ANALYSIS_TOOLS = [
            {
                "name": "analyze_customers",
                "description": """Analyze and identify specific customer groups based on various criteria. Use this for identifying, ranking, or filtering customers.

                Examples:
                - "Which customers are likely businesses?" → analysis_type: b2b_identification
                - "Show me high churn risk customers" → analysis_type: churn_risk, sort_by: impact
                - "Who are my best customers?" → analysis_type: high_value, sort_by: ltv
                - "Find seasonal shoppers" → analysis_type: behavioral, filter_by: seasonal_shoppers
                - "What do VIP customers buy?" → analysis_type: product_affinity, filter_by: ltv_threshold
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "analysis_type": {
                            "type": "string",
                            "enum": [
                                "churn_risk",           # At-risk customers
                                "b2b_identification",   # Business vs consumer detection
                                "high_value",           # Top customers by LTV
                                "behavioral",           # By shopping patterns (seasonal, frequency, etc.)
                                "product_affinity",     # What customers buy
                                "rfm_score"             # Recency, frequency, monetary analysis
                            ],
                            "description": "Type of customer analysis to perform"
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["ltv", "churn_risk", "impact", "frequency", "recency", "orders"],
                            "description": "How to rank/sort results. 'impact' = LTV × churn_risk",
                            "default": "ltv"
                        },
                        "filter_by": {
                            "type": "string",
                            "description": "Optional filter: 'ltv_threshold:5000', 'seasonal_shoppers', 'premium_buyers', 'frequent_returners', etc."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of customers to return",
                            "default": 10
                        }
                    },
                    "required": ["analysis_type"]
                }
            },
            {
                "name": "analyze_segments",
                "description": """Analyze CUSTOMER SEGMENTS and archetypes - understand who your CUSTOMER TYPES are, how they behave, and how they're changing.

                ⚠️ CRITICAL: Use THIS tool when user asks about CUSTOMER TYPES/SEGMENTS/GROUPS.
                - "what type of customer" / "which customer type" / "customer segment" → THIS TOOL
                - Questions about REPEAT PURCHASES by customer type → THIS TOOL
                - Questions about FREQUENCY/CADENCE by customer type → THIS TOOL
                - Individual customer behavior → use analyze_behavior tool instead

                ❌ DO NOT USE THIS TOOL FOR PRODUCT/CATEGORY QUESTIONS:
                - "What products..." → use analyze_products instead
                - "Which categories..." → use analyze_products instead
                - "Product revenue/sales" → use analyze_products instead
                - Use analyze_products tool for ANY question about product categories or product performance!

                KEY PHRASES THAT MEAN USE THIS TOOL:
                "type of customer", "customer type", "customer segment", "customer group", "what kind of customers", "which customers [plural comparative]"

                Examples:
                - "What types of customers do I have?" → analysis_type: segment_overview
                - "Show me growing segments" → analysis_type: segment_growth, filter_by: growing
                - "Which segments spend the most?" → analysis_type: segment_overview, sort_by: ltv
                - "Compare segment X vs segment Y" → analysis_type: segment_comparison
                - "Who are my holiday shoppers?" → analysis_type: seasonal_segments, event: halloween
                - "What type of customer has the highest repeat purchases?" → THIS TOOL: analysis_type: segment_overview, sort_by: frequency
                - "What customer type repurchases most?" → THIS TOOL: analysis_type: segment_overview, sort_by: frequency
                - "Which customer segment is most loyal?" → THIS TOOL: analysis_type: segment_overview, sort_by: frequency
                - "Which type of customer buys most often?" → THIS TOOL: analysis_type: segment_overview, sort_by: frequency
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "analysis_type": {
                            "type": "string",
                            "enum": [
                                "segment_overview",      # List all customer types
                                "segment_growth",        # Growth/decline projections
                                "seasonal_segments",     # Seasonal/holiday shoppers
                                "segment_comparison"     # Compare two segments
                            ],
                            "description": "Type of segment analysis"
                        },
                        "event": {
                            "type": "string",
                            "description": "For seasonal_segments: 'halloween', 'christmas', 'black_friday', etc.",
                            "default": "holiday"
                        },
                        "filter_by": {
                            "type": "string",
                            "description": "Filter segments: 'growing', 'shrinking', 'high_value', 'at_risk'"
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["ltv", "size", "growth_rate", "churn_rate", "frequency", "recency"],
                            "description": "Sort segments by: ltv (avg lifetime value), size (customer count), growth_rate, churn_rate, frequency (avg orders per customer - use for repeat purchases), recency (avg days since last order)",
                            "default": "ltv"
                        },
                        "timeframe_months": {
                            "type": "integer",
                            "description": "For growth projections, how many months ahead",
                            "default": 12
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10
                        }
                    },
                    "required": ["analysis_type"]
                }
            },
            {
                "name": "forecast_metrics",
                "description": """Forecast future revenue, growth, or customer metrics over time.

                Examples:
                - "What will revenue be in 12 months?" → metric: revenue, timeframe_months: 12
                - "Revenue forecast for Q4" → metric: revenue, timeframe_months: 3
                - "How many customers will I have next year?" → metric: customer_count, timeframe_months: 12
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "enum": ["revenue", "customer_count", "average_ltv", "churn_rate"],
                            "description": "What to forecast",
                            "default": "revenue"
                        },
                        "timeframe_months": {
                            "type": "integer",
                            "description": "How many months ahead to forecast (3=quarter, 12=year)",
                            "default": 12
                        },
                        "include_breakdown": {
                            "type": "boolean",
                            "description": "Include monthly breakdown",
                            "default": True
                        }
                    }
                }
            },
            {
                "name": "target_campaign",
                "description": """Recommend customers to target for specific marketing campaigns.

                Examples:
                - "Who should I target for retention?" → campaign_type: retention
                - "Best customers for Black Friday promo" → campaign_type: seasonal, event: black_friday
                - "Win-back lapsed customers" → campaign_type: winback
                - "Upsell opportunities" → campaign_type: growth
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "campaign_type": {
                            "type": "string",
                            "enum": ["retention", "growth", "winback", "seasonal", "loyalty", "acquisition"],
                            "description": "Type of campaign"
                        },
                        "event": {
                            "type": "string",
                            "description": "For seasonal campaigns: holiday name"
                        },
                        "target_size": {
                            "type": "integer",
                            "description": "Number of customers to target",
                            "default": 100
                        }
                    },
                    "required": ["campaign_type"]
                }
            },
            {
                "name": "lookup_customer",
                "description": """Get detailed information about a specific customer. Use this when the user asks about an individual customer by ID, email, or name.

                Examples:
                - "What's the LTV of customer 5971333382399?"
                - "Show me customer profile for customer@email.com"
                - "What segment is customer 123 in?"
                - "When did customer X last purchase?"
                - "What's the churn risk for customer Y?"
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Customer ID (13-digit number) or email address"
                        },
                        "info_type": {
                            "type": "string",
                            "enum": ["profile", "ltv_forecast", "churn_risk", "segment", "purchase_history", "recommendations"],
                            "description": "What information to retrieve about the customer",
                            "default": "profile"
                        }
                    },
                    "required": ["customer_id"]
                }
            },
            {
                "name": "analyze_behavior",
                "description": """Analyze advanced behavioral patterns and detect changes in INDIVIDUAL customer behavior.

                ⚠️ DO NOT use this tool for questions about "customer types" or "customer segments" - use analyze_segments instead.
                - "what TYPE of customer" → use analyze_segments, NOT this tool
                - "which customer SEGMENT" → use analyze_segments, NOT this tool
                - Individual customer behavior patterns → use THIS tool

                Examples:
                - "Who bought once and never came back?" → pattern_type: one_time_buyers
                - "Show me customers who increased spending recently" → pattern_type: momentum_analysis
                - "Which customers have slowing purchase frequency?" → pattern_type: declining_engagement
                - "Who skipped their usual purchase window?" → pattern_type: behavior_change
                - "Which customers only buy on discount?" → pattern_type: discount_dependency
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern_type": {
                            "type": "string",
                            "enum": [
                                "one_time_buyers",          # Customers who never returned
                                "momentum_analysis",        # Increasing spending/frequency
                                "declining_engagement",     # Slowing activity
                                "behavior_change",          # Recent pattern shifts
                                "purchase_cadence",         # Purchase rhythm
                                "discount_dependency"       # Discount-driven buyers
                            ],
                            "description": "Type of behavioral pattern to analyze"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Analysis window: 'last_30_days', 'last_90_days', 'last_year'",
                            "default": "last_90_days"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of customers to return",
                            "default": 100
                        }
                    },
                    "required": ["pattern_type"]
                }
            },
            {
                "name": "get_recommendations",
                "description": """Get actionable recommendations for specific customers, segments, or business decisions.

                Examples:
                - "Which customers should I upsell to premium?" → recommendation_type: upsell_candidates
                - "Show me cross-sell opportunities" → recommendation_type: cross_sell_opportunities
                - "Which customers are ready for expansion?" → recommendation_type: expansion_targets
                - "What's the optimal discount for high-value customers?" → recommendation_type: discount_strategy
                - "How should I re-engage churned customers?" → recommendation_type: winback_strategy
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "recommendation_type": {
                            "type": "string",
                            "enum": [
                                "upsell_candidates",        # Who to upsell
                                "cross_sell_opportunities", # Cross-sell recommendations
                                "expansion_targets",        # Ready to spend more
                                "winback_strategy",         # Re-engage churned customers
                                "retention_actions",        # What to do for at-risk
                                "discount_strategy"         # Optimal discount by segment
                            ],
                            "description": "Type of recommendation to generate"
                        },
                        "customer_id": {
                            "type": "string",
                            "description": "Optional: Get recommendations for specific customer"
                        },
                        "segment_filter": {
                            "type": "string",
                            "description": "Optional: Filter to specific segment or criteria"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of recommendations",
                            "default": 20
                        }
                    },
                    "required": ["recommendation_type"]
                }
            },
            {
                "name": "analyze_products",
                "description": """✅ REAL PRODUCT ANALYSIS - Query actual product categories from sales data.

                Use this tool for questions about PRODUCT CATEGORIES (Yarn, Fabric, etc.), NOT customer behavior.

                Supported analysis:
                - revenue_by_category: Which categories have highest revenue/sales
                - category_repurchase_rate: Which categories customers buy repeatedly

                Examples:
                - "Which categories have the highest revenue?" → analysis_type: revenue_by_category
                - "What product categories drive the most sales?" → analysis_type: revenue_by_category
                - "Which categories have best repeat purchase rate?" → analysis_type: category_repurchase_rate
                - "Top selling product categories" → analysis_type: revenue_by_category

                This queries the combined_sales table with real order data!
                """,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "analysis_type": {
                            "type": "string",
                            "enum": [
                                "revenue_by_category",        # Total revenue by product category (IMPLEMENTED)
                                "category_repurchase_rate"    # Repeat purchase rate by category (IMPLEMENTED)
                            ],
                            "description": "Type of product analysis to perform",
                            "default": "revenue_by_category"
                        },
                        "segment_filter": {
                            "type": "string",
                            "description": "Filter to specific customer segment: 'high_value', 'premium', 'budget', 'power_buyer', etc."
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["revenue", "customer_count", "aov", "total_orders", "growth_rate", "repurchase_rate"],
                            "description": "How to sort results: revenue (total $), customer_count (popularity), aov (avg order value), total_orders (purchase frequency)",
                            "default": "revenue"
                        },
                        "timeframe_months": {
                            "type": "integer",
                            "description": "For trend analysis, how many months to analyze",
                            "default": 12
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of categories to return",
                            "default": 10
                        }
                    },
                    "required": ["analysis_type"]
                }
            }
        ]

        # Send query to Claude with function calling
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            tools=ANALYSIS_TOOLS,
            messages=[{
                "role": "user",
                "content": query
            }]
        )

        # Extract tool use from response
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                logger.info(f"Claude routed query to: {tool_name} with params: {tool_input}")

                # Route based on consolidated vs legacy tools
                if USE_CONSOLIDATED_TOOLS:
                    # NEW ROUTING: 5 Consolidated Tools
                    if tool_name == "query_customers":
                        scope = tool_input.get("scope", "list")
                        filters = tool_input.get("filters", {})

                        if scope == "individual":
                            # Single customer lookup
                            customer_id = tool_input.get("customer_id")
                            info_requested = tool_input.get("info_requested", ["profile", "churn_risk"])

                            result = await _handle_lookup_customer(
                                customer_id=customer_id,
                                info_type=info_requested[0] if len(info_requested) == 1 else "profile"
                            )
                        else:
                            # List query with filters
                            # Route based on filters to appropriate handler
                            if filters.get("churn_risk_min") or filters.get("churn_risk_max"):
                                # Churn-focused query
                                risk_level = "all"
                                if filters.get("churn_risk_min", 0) >= 0.7:
                                    risk_level = "critical"
                                elif filters.get("churn_risk_min", 0) >= 0.5:
                                    risk_level = "high"

                                result = await _handle_churn_risk_analysis(risk_level=risk_level)

                            elif filters.get("behavior_pattern"):
                                # Behavioral pattern query
                                pattern = filters["behavior_pattern"]
                                result = await _handle_behavior_pattern_analysis(
                                    pattern_type=pattern,
                                    timeframe="last_90_days",
                                    limit=tool_input.get("limit", 100)
                                )

                            elif filters.get("is_b2b") is True:
                                # B2B identification
                                result = await _handle_b2b_identification(
                                    limit=tool_input.get("limit", 100),
                                    sort_by="ltv"
                                )

                            elif filters.get("ltv_min") or filters.get("total_orders_min"):
                                # High-value customer query
                                result = await _handle_high_value_customers(
                                    limit=tool_input.get("limit", 100),
                                    sort_by=tool_input.get("sort_by", "ltv_desc").replace("_desc", "").replace("_asc", "")
                                )

                            else:
                                # Generic behavioral analysis
                                result = await _handle_behavioral_analysis(
                                    filter_by="",
                                    limit=tool_input.get("limit", 100)
                                )

                        result["query"] = query
                        return result

                    elif tool_name == "query_segments":
                        analysis_type = tool_input.get("analysis_type", "overview")

                        if analysis_type == "comparison":
                            # Segment comparison
                            segments = tool_input.get("segment_filter", "").split(",") if tool_input.get("segment_filter") else []
                            result = await _handle_segment_comparison(
                                segments=segments,
                                metrics=tool_input.get("metrics", ["ltv", "churn_risk"])
                            )

                        elif analysis_type == "seasonal":
                            # Seasonal segment analysis
                            result = await _handle_seasonal_archetype_analysis(
                                query=query,
                                event=tool_input.get("event_type", "holiday"),
                                timeframe_months=tool_input.get("timeframe_months", 12)
                            )

                        elif analysis_type == "growth":
                            # Segment growth projection
                            result = await _handle_archetype_growth(
                                months=tool_input.get("timeframe_months", 12),
                                top_n=tool_input.get("limit", 10),
                                sort_by=tool_input.get("sort_by", "total_revenue")
                            )

                        else:  # overview
                            # Default to growth projection
                            result = await _handle_archetype_growth(
                                months=tool_input.get("timeframe_months", 12),
                                top_n=tool_input.get("limit", 10),
                                sort_by=tool_input.get("sort_by", "total_revenue")
                            )

                        result["query"] = query
                        return result

                    elif tool_name == "forecast_business_metrics":
                        metrics = tool_input.get("metrics", ["revenue"])
                        timeframe_months = tool_input.get("timeframe_months", 12)

                        # For now, handle the primary metric (can be enhanced to handle multiple)
                        primary_metric = metrics[0] if metrics else "revenue"

                        if primary_metric == "revenue":
                            result = await _handle_revenue_forecast(months=timeframe_months)
                        else:
                            result = await _handle_metric_forecast(
                                metric=primary_metric,
                                months=timeframe_months
                            )

                        result["query"] = query
                        return result

                    elif tool_name == "plan_campaign":
                        goal = tool_input.get("goal", "retention")

                        # Map goal to campaign_type
                        goal_to_campaign = {
                            "retention": "retention",
                            "acquisition": "acquisition",
                            "winback": "winback",
                            "growth": "growth",
                            "loyalty": "loyalty",
                            "seasonal": "seasonal"
                        }

                        campaign_type = goal_to_campaign.get(goal, "retention")

                        result = await _handle_campaign_targeting(
                            campaign_type=campaign_type,
                            target_size=tool_input.get("constraints", {}).get("max_customers", 100)
                        )
                        result["query"] = query
                        return result

                    elif tool_name == "analyze_products":
                        # Product analysis (unchanged from legacy)
                        analysis_type = tool_input.get("analysis_type", "revenue_by_category")

                        result = await _handle_product_analysis(
                            analysis_type=analysis_type,
                            segment_filter=tool_input.get("segment_filter"),
                            sort_by=tool_input.get("sort_by", "revenue"),
                            timeframe_months=tool_input.get("timeframe_months", 12),
                            limit=tool_input.get("limit", 10)
                        )
                        result["query"] = query
                        return result

                # LEGACY ROUTING: 8 Original Tools
                elif tool_name == "analyze_customers":
                    analysis_type = tool_input.get("analysis_type", "high_value")

                    if analysis_type == "churn_risk":
                        result = await _handle_churn_risk_analysis(
                            risk_level=tool_input.get("risk_level", "all")
                        )
                    elif analysis_type == "b2b_identification":
                        result = await _handle_b2b_identification(
                            limit=tool_input.get("limit", 100),
                            sort_by=tool_input.get("sort_by", "ltv")
                        )
                    elif analysis_type == "high_value":
                        result = await _handle_high_value_customers(
                            limit=tool_input.get("limit", 100),
                            sort_by=tool_input.get("sort_by", "ltv")
                        )
                    elif analysis_type == "behavioral":
                        result = await _handle_behavioral_analysis(
                            filter_by=tool_input.get("filter_by", ""),
                            limit=tool_input.get("limit", 100)
                        )
                    elif analysis_type == "product_affinity":
                        result = await _handle_product_affinity(
                            limit=tool_input.get("limit", 100)
                        )
                    elif analysis_type == "rfm_score":
                        result = await _handle_rfm_analysis(
                            limit=tool_input.get("limit", 100),
                            sort_by=tool_input.get("sort_by", "ltv")
                        )
                    else:
                        # Default to high value
                        result = await _handle_high_value_customers(
                            limit=tool_input.get("limit", 100),
                            sort_by=tool_input.get("sort_by", "ltv")
                        )

                    result["query"] = query
                    return result

                elif tool_name == "analyze_segments":
                    analysis_type = tool_input.get("analysis_type", "segment_overview")

                    if analysis_type == "segment_growth":
                        result = await _handle_archetype_growth(
                            months=tool_input.get("timeframe_months", 12),
                            top_n=tool_input.get("limit", 10),
                            sort_by=tool_input.get("sort_by", "total_revenue")
                        )
                    elif analysis_type == "seasonal_segments":
                        result = await _handle_seasonal_archetype_analysis(
                            query=query,
                            event=tool_input.get("event_type", "holiday"),
                            timeframe_months=tool_input.get("timeframe_months", 12)
                        )
                    elif analysis_type == "segment_comparison":
                        result = await _handle_segment_comparison(
                            segments=tool_input.get("segments", []),
                            metrics=tool_input.get("metrics", ["ltv", "churn_risk"])
                        )
                    else:
                        # Default to segment overview (growth projection)
                        result = await _handle_archetype_growth(
                            months=tool_input.get("timeframe_months", 12),
                            top_n=tool_input.get("limit", 10),
                            sort_by=tool_input.get("sort_by", "total_revenue")
                        )

                    result["query"] = query
                    return result

                elif tool_name == "forecast_metrics":
                    metric = tool_input.get("metric", "revenue")

                    if metric == "revenue":
                        result = await _handle_revenue_forecast(
                            months=tool_input.get("timeframe_months", 12)
                        )
                    elif metric in ["customer_count", "average_ltv", "churn_rate"]:
                        result = await _handle_metric_forecast(
                            metric=metric,
                            months=tool_input.get("timeframe_months", 12)
                        )
                    else:
                        # Default to revenue
                        result = await _handle_revenue_forecast(
                            months=tool_input.get("timeframe_months", 12)
                        )

                    result["query"] = query
                    return result

                elif tool_name == "target_campaign":
                    result = await _handle_campaign_targeting(
                        campaign_type=tool_input.get("campaign_type", "retention"),
                        target_size=tool_input.get("target_size", 100)
                    )
                    result["query"] = query
                    return result

                elif tool_name == "lookup_customer":
                    customer_id = tool_input.get("customer_id")
                    info_type = tool_input.get("info_type", "profile")

                    result = await _handle_lookup_customer(
                        customer_id=customer_id,
                        info_type=info_type
                    )
                    result["query"] = query
                    return result

                elif tool_name == "analyze_behavior":
                    pattern_type = tool_input.get("pattern_type")

                    result = await _handle_behavior_pattern_analysis(
                        pattern_type=pattern_type,
                        timeframe=tool_input.get("timeframe", "last_90_days"),
                        limit=tool_input.get("limit", 100)
                    )
                    result["query"] = query
                    return result

                elif tool_name == "get_recommendations":
                    recommendation_type = tool_input.get("recommendation_type")

                    result = await _handle_get_recommendations(
                        recommendation_type=recommendation_type,
                        customer_id=tool_input.get("customer_id"),
                        segment_filter=tool_input.get("segment_filter"),
                        limit=tool_input.get("limit", 20)
                    )
                    result["query"] = query
                    return result

                elif tool_name == "analyze_products":
                    analysis_type = tool_input.get("analysis_type", "revenue_by_category")

                    result = await _handle_product_analysis(
                        analysis_type=analysis_type,
                        segment_filter=tool_input.get("segment_filter"),
                        sort_by=tool_input.get("sort_by", "revenue"),
                        timeframe_months=tool_input.get("timeframe_months", 12),
                        limit=tool_input.get("limit", 10)
                    )
                    result["query"] = query
                    return result

        # If Claude didn't call a tool, return its text response
        text_response = next((block.text for block in response.content if hasattr(block, 'text')), None)
        if text_response:
            return {
                "query": query,
                "query_type": "general_response",
                "answer": {
                    "message": text_response
                }
            }

        # Fallback if no tool and no text
        return {
            "query": query,
            "query_type": "unsupported",
            "answer": {
                "summary": "I'm sorry, I couldn't understand that question.",
                "message": "I couldn't determine how to answer that question. Here are some examples of what I can help with:",
                "supported_queries": [
                    "Customer Analysis: 'which customers are most likely to churn?'",
                    "Product Analysis: 'what are my top selling products?'",
                    "Product Bundles: 'what products do customers buy together?'",
                    "Revenue Forecasting: 'what's our revenue forecast for Q4?'",
                    "Campaign Targeting: 'who should we target for retention campaign?'",
                    "Segment Growth: 'how will our customer segments grow?'",
                    "Product Trends: 'which product categories are growing?'",
                    "Seasonal Analysis: 'when do customers buy batting?'"
                ]
            }
        }

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}", exc_info=True)
        return {
            "query": query,
            "query_type": "error",
            "answer": {
                "message": f"AI routing service error: {str(e)}. Please try again."
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process natural language query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Helper Functions for Natural Language Query ====================
# These functions delegate to MCP tools and provide backward compatibility

async def _handle_lookup_customer(customer_id: str, info_requested: list = None):
    """Lookup customer profile via MCP"""
    return handle_mcp_call("get_customer_profile", {"customer_id": customer_id})

async def _handle_high_value_customers(min_ltv: float = 1000, limit: int = 100):
    """Get high-value customers via MCP"""
    return handle_mcp_call("search_customers", {
        "filters": {"min_ltv": min_ltv},
        "limit": limit,
        "sort_by": "ltv_desc"
    })

async def _handle_churn_risk_analysis(risk_threshold: float = 0.7, limit: int = 100):
    """Get at-risk customers via MCP"""
    return handle_mcp_call("search_customers", {
        "filters": {"min_churn_risk": risk_threshold},
        "limit": limit,
        "sort_by": "churn_risk_desc"
    })

async def _handle_campaign_targeting(goal: str = "retention", target_size: int = 100):
    """Get campaign targeting recommendations via MCP"""
    return handle_mcp_call("recommend_segments_for_campaign", {
        "campaign_goal": goal,
        "target_count": target_size
    })

async def _handle_seasonal_archetype_analysis(event: str = None, timeframe: int = 12):
    """Get archetype statistics"""
    return handle_mcp_call("get_archetype_stats", {})

async def _handle_behavioral_analysis(pattern: str = None, timeframe: str = "last_90_days"):
    """Analyze customer behavior patterns via MCP"""
    return handle_mcp_call("search_customers", {
        "filters": {"behavior_pattern": pattern} if pattern else {},
        "limit": 100
    })

async def _handle_behavior_pattern_analysis(pattern_type: str, timeframe: str = "last_90_days", limit: int = 100):
    """Analyze specific behavior patterns"""
    return handle_mcp_call("search_customers", {
        "filters": {"behavior_pattern": pattern_type},
        "limit": limit
    })

async def _handle_rfm_analysis(segment: str = None):
    """RFM analysis - uses customer search with recency/frequency filters"""
    return handle_mcp_call("search_customers", {"limit": 100})

async def _handle_archetype_growth(months: int = 12, top_n: int = 10, sort_by: str = "total_revenue"):
    """Get archetype growth trends and top archetypes by metric"""
    from collections import defaultdict

    if not data_store.loaded or not data_store.archetypes:
        return {"error": "No archetype data available"}

    # Build archetype stats
    archetype_stats = []
    for archetype_id, archetype_data in data_store.archetypes.items():
        # Get members for this archetype
        members = [
            cust for cust in data_store.customers.values()
            if cust.get('archetype_id') == archetype_id
        ]

        if not members:
            continue

        # Calculate metrics
        ltvs = [m.get('lifetime_value', 0) for m in members if m.get('lifetime_value')]
        orders = [m.get('total_orders', 0) for m in members if m.get('total_orders')]
        days_since = [m.get('days_since_last_purchase', 0) for m in members if m.get('days_since_last_purchase')]

        stat = {
            "archetype_id": archetype_id,
            "member_count": len(members),
            "population_percentage": archetype_data.get('population_percentage', 0),
            "dominant_segments": archetype_data.get('dominant_segments', {}),
            "avg_ltv": sum(ltvs) / len(ltvs) if ltvs else 0,
            "total_revenue": sum(ltvs) if ltvs else 0,
            "avg_orders": sum(orders) / len(orders) if orders else 0,  # frequency
            "avg_days_since_purchase": sum(days_since) / len(days_since) if days_since else 0,  # recency
        }
        archetype_stats.append(stat)

    # Sort by requested metric
    sort_key_map = {
        "total_revenue": "total_revenue",
        "ltv": "avg_ltv",
        "size": "member_count",
        "frequency": "avg_orders",  # For repeat purchases
        "recency": "avg_days_since_purchase",
        "growth_rate": "member_count",  # Fallback to size
        "churn_rate": "member_count"  # Fallback to size
    }

    sort_key = sort_key_map.get(sort_by, "total_revenue")
    sorted_stats = sorted(archetype_stats, key=lambda x: x.get(sort_key, 0), reverse=True)

    return {
        "archetypes": sorted_stats[:top_n],
        "total_archetypes": len(archetype_stats),
        "sort_by": sort_by,
        "timeframe_months": months
    }

async def _handle_segment_comparison(segment_ids: list):
    """Compare segments"""
    return {"message": "Segment comparison available via archetype stats"}

async def _handle_revenue_forecast(months: int = 12):
    """Revenue forecast stub"""
    return {"message": "Revenue forecast available via dedicated analytics endpoint"}

async def _handle_metric_forecast(metric: str, months: int = 12):
    """Metric forecast stub - returns average LTV and other metrics"""

    # For average_ltv, we can calculate from the data_store
    if metric == "average_ltv":
        from mcp_server.segmentation_server import data_store

        if data_store.loaded and data_store.customers:
            # Calculate average LTV from customer data
            ltvs = []
            for customer_id, customer_data in data_store.customers.items():
                ltv = customer_data.get('lifetime_value')
                if ltv is not None and ltv > 0:
                    ltvs.append(ltv)

            if ltvs:
                avg_ltv = sum(ltvs) / len(ltvs)
                total_customers = len(ltvs)

                return {
                    "metric": "average_ltv",
                    "current_value": round(avg_ltv, 2),
                    "total_customers": total_customers,
                    "message": f"Current average customer lifetime value is ${avg_ltv:,.2f} across {total_customers:,} customers with recorded LTV"
                }
            else:
                return {
                    "metric": "average_ltv",
                    "error": "No customer LTV data available",
                    "message": "Unable to calculate average LTV - no customers with lifetime value data"
                }
        else:
            return {
                "metric": "average_ltv",
                "error": "Data not loaded",
                "message": "Customer data not loaded into data store"
            }

    # For other metrics, return stub message
    return {
        "metric": metric,
        "message": f"{metric} forecasts available via analytics endpoints"
    }

async def _handle_product_affinity(customer_id: str):
    """Product affinity stub"""
    return {"message": "Product-level analysis not available in this version"}

async def _handle_b2b_identification():
    """B2B identification via customer filters"""
    return handle_mcp_call("search_customers", {
        "filters": {"is_b2b": True},
        "limit": 100
    })

async def _handle_get_recommendations(customer_id: str):
    """Get customer recommendations"""
    return handle_mcp_call("get_customer_profile", {"customer_id": customer_id})

async def _handle_product_analysis(
    analysis_type: str = "revenue_by_category",
    segment_filter: Optional[str] = None,
    sort_by: str = "revenue",
    limit: int = 20,
    include_details: bool = True,
    timeframe_months: int = 12
):
    """
    Query combined_sales table for actual product category analysis.

    Supports:
    - revenue_by_category: Top categories by revenue
    - category_trends: Growing/shrinking categories
    - category_repurchase_rate: Categories with highest repeat purchase rate
    """
    from backend.core.database import get_db_session
    from sqlalchemy import text

    try:
        async with get_db_session() as session:
            if analysis_type == "revenue_by_category":
                # Category revenue analysis
                query = text("""
                    SELECT
                        category,
                        SUM(line_item_sales) as total_revenue,
                        COUNT(DISTINCT order_id) as total_orders,
                        COUNT(DISTINCT customer_id) as unique_customers,
                        AVG(line_item_sales) as avg_order_value,
                        SUM(quantity) as units_sold
                    FROM combined_sales
                    WHERE order_date >= NOW() - make_interval(months => :months)
                        AND category IS NOT NULL
                        AND category != ''
                    GROUP BY category
                    ORDER BY total_revenue DESC
                    LIMIT :limit
                """)

                result = await session.execute(
                    query,
                    {"months": timeframe_months, "limit": limit}
                )
                rows = result.fetchall()

                categories = [
                    {
                        "category": row.category,
                        "total_revenue": float(row.total_revenue or 0),
                        "total_orders": int(row.total_orders or 0),
                        "unique_customers": int(row.unique_customers or 0),
                        "avg_order_value": float(row.avg_order_value or 0),
                        "units_sold": int(row.units_sold or 0),
                        "revenue_per_customer": float(row.total_revenue or 0) / max(int(row.unique_customers or 1), 1)
                    }
                    for row in rows
                ]

                return {
                    "analysis_type": "revenue_by_category",
                    "categories": categories,
                    "timeframe_months": timeframe_months,
                    "sort_by": sort_by,
                    "total_categories": len(categories)
                }

            elif analysis_type == "category_repurchase_rate":
                # Repeat purchase analysis by category
                query = text("""
                    WITH customer_category_orders AS (
                        SELECT
                            customer_id,
                            category,
                            COUNT(DISTINCT order_id) as order_count
                        FROM combined_sales
                        WHERE order_date >= NOW() - make_interval(months => :months)
                            AND category IS NOT NULL
                            AND category != ''
                        GROUP BY customer_id, category
                    )
                    SELECT
                        category,
                        COUNT(*) as total_customers,
                        COUNT(CASE WHEN order_count > 1 THEN 1 END) as repeat_customers,
                        ROUND(100.0 * COUNT(CASE WHEN order_count > 1 THEN 1 END)::NUMERIC / COUNT(*), 2) as repeat_rate_pct,
                        AVG(order_count) as avg_orders_per_customer
                    FROM customer_category_orders
                    GROUP BY category
                    ORDER BY repeat_rate_pct DESC
                    LIMIT :limit
                """)

                result = await session.execute(
                    query,
                    {"months": timeframe_months, "limit": limit}
                )
                rows = result.fetchall()

                categories = [
                    {
                        "category": row.category,
                        "total_customers": int(row.total_customers or 0),
                        "repeat_customers": int(row.repeat_customers or 0),
                        "repeat_rate_pct": float(row.repeat_rate_pct or 0),
                        "avg_orders_per_customer": float(row.avg_orders_per_customer or 0)
                    }
                    for row in rows
                ]

                return {
                    "analysis_type": "category_repurchase_rate",
                    "categories": categories,
                    "timeframe_months": timeframe_months,
                    "sort_by": "repeat_rate",
                    "total_categories": len(categories)
                }

            else:
                # Unsupported analysis type
                return {
                    "analysis_type": analysis_type,
                    "message": f"Analysis type '{analysis_type}' not yet implemented",
                    "available_types": ["revenue_by_category", "category_repurchase_rate"]
                }

    except Exception as e:
        logger.error(f"Error in product analysis: {e}", exc_info=True)
        return {
            "error": str(e),
            "analysis_type": analysis_type,
            "message": "Failed to query product data"
        }


async def _fallback_pattern_matching(query: str):
    """Fallback response when ANTHROPIC_API_KEY is not available."""
    return {
        "query": query,
        "query_type": "error",
        "answer": {
            "message": "Natural language query routing requires ANTHROPIC_API_KEY to be set. Please configure the API key or use specific endpoint paths directly.",
            "available_endpoints": [
                "GET /api/mcp/archetypes/top - Top archetypes by value",
                "GET /api/mcp/churn/aggregate - Aggregate churn analysis",
                "GET /api/mcp/growth/projection - Customer growth projection",
                "POST /api/mcp/campaigns/recommend - Campaign targeting",
                "GET /api/mcp/revenue/forecast - Revenue forecasting"
            ]
        }
    }



# ==================== Gorgias Integration ====================

import anthropic

# Global AI assistant instance (initialized on first use)
_gorgias_ai_assistant = None

def get_gorgias_ai_assistant():
    """Get or create Gorgias AI assistant instance."""
    global _gorgias_ai_assistant

    if _gorgias_ai_assistant is None:
        from integrations.gorgias_ai_assistant import GorgiasAIAssistant

        # Get configuration from environment
        gorgias_domain = os.getenv("GORGIAS_DOMAIN")
        gorgias_username = os.getenv("GORGIAS_USERNAME")
        gorgias_api_key = os.getenv("GORGIAS_API_KEY")

        if not all([gorgias_domain, gorgias_username, gorgias_api_key]):
            logger.warning("Gorgias credentials not configured - AI assistant disabled")
            return None

        # Use current server URL for analytics
        analytics_url = os.getenv("API_BASE_URL", "http://localhost:8000")

        _gorgias_ai_assistant = GorgiasAIAssistant(
            gorgias_domain=gorgias_domain,
            gorgias_username=gorgias_username,
            gorgias_api_key=gorgias_api_key,
            analytics_api_url=analytics_url,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        logger.info("Gorgias AI Assistant initialized")

    return _gorgias_ai_assistant


async def process_gorgias_webhook_async(webhook_data: dict, assistant):
    """
    Process Gorgias webhook asynchronously in background.

    This prevents webhook timeout issues by processing after returning 200 OK to Gorgias.
    """
    try:
        ticket_id = webhook_data.get("id", "unknown")
        logger.info(f"[ASYNC] Starting background processing for ticket #{ticket_id}")

        # Process webhook (this can take >5 seconds)
        result = await assistant.handle_ticket_webhook(webhook_data)

        logger.info(f"[ASYNC] Completed ticket #{ticket_id}: {result.get('status')}")
        return result

    except Exception as e:
        logger.error(f"[ASYNC] Error processing ticket in background: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/api/gorgias/webhook")
@limiter.limit("1000/hour")  # Higher limit for webhook (burst traffic expected)
async def handle_gorgias_webhook(
    request: Request,
    x_webhook_token: Optional[str] = Header(None, alias="X-Webhook-Token")
):
    """
    Handle Gorgias ticket webhook with token authentication.

    IMPORTANT: Returns 200 OK immediately to avoid Gorgias 5-second timeout.
    Actual processing happens asynchronously using asyncio.create_task().

    Flow:
    1. Validate webhook token (custom header: X-Webhook-Token)
    2. Return 200 OK immediately (prevents timeout)
    3. Background: Extract customer identifier (Shopify ID from external_id or meta)
    4. Background: Fetch customer analytics (LTV, churn risk, purchase history)
    5. Background: Generate personalized draft reply using Claude 3.5 Haiku
    6. Background: Post as internal note in Gorgias for agent review

    Cost: ~$0.0001 per ticket (Claude Haiku)

    Authentication:
    - Gorgias HTTP Integration must send header: X-Webhook-Token
    - Token value should match GORGIAS_WEBHOOK_SECRET env variable

    Gorgias webhook format:
    {
        "id": "12345",
        "customer": {
            "external_id": "shopify_customer_id",
            "email": "customer@example.com",
            "name": "Jane Doe",
            "meta": {"shopify_customer_id": "123"}
        },
        "messages": [
            {
                "body_text": "Where is my order?",
                "is_note": false,
                "created_datetime": "2025-10-17T10:00:00Z"
            }
        ],
        "tags": [...],
        "via": "email",
        ...
    }
    """
    try:
        # Get AI assistant
        assistant = get_gorgias_ai_assistant()
        if not assistant:
            logger.warning("Gorgias AI assistant not configured, skipping")
            return {
                "status": "skipped",
                "reason": "Gorgias AI assistant not configured"
            }

        # Validate webhook token
        webhook_secret = os.getenv("GORGIAS_WEBHOOK_SECRET")
        if not webhook_secret:
            logger.error("GORGIAS_WEBHOOK_SECRET not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook authentication not configured"
            )

        if not x_webhook_token or x_webhook_token != webhook_secret:
            logger.warning(f"Rejected Gorgias webhook with invalid token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook token"
            )

        # Parse JSON after validation
        webhook_data = await request.json()

        ticket_id = webhook_data.get("id", "unknown")
        logger.info(f"Received Gorgias webhook for ticket #{ticket_id} - starting async processing")

        # Create fire-and-forget task using asyncio - this continues running after response is sent
        asyncio.create_task(process_gorgias_webhook_async(webhook_data, assistant))

        # Return immediately to prevent timeout
        return {
            "status": "accepted",
            "ticket_id": ticket_id,
            "message": "Webhook received and queued for processing"
        }

    except Exception as e:
        logger.error(f"Error handling Gorgias webhook: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/api/gorgias/webhook/test")
@limiter.limit("100/hour")
async def handle_gorgias_webhook_test(
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    """
    Test endpoint for Gorgias webhook - BYPASSES signature validation.
    Requires ADMIN_KEY for security.

    Use this for testing ticket scenarios without needing proper HMAC signatures.
    """
    try:
        # Validate admin key
        admin_key = os.getenv("ADMIN_KEY")
        if not admin_key or x_admin_key != admin_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin key"
            )

        # Get AI assistant
        assistant = get_gorgias_ai_assistant()
        if not assistant:
            logger.warning("Gorgias AI assistant not configured, skipping")
            return {
                "status": "skipped",
                "reason": "Gorgias AI assistant not configured"
            }

        # Parse JSON (no signature validation)
        webhook_data = await request.json()

        ticket_id = webhook_data.get("id", "unknown")
        logger.info(f"[TEST] Received Gorgias webhook for ticket #{ticket_id}")

        # Process webhook
        result = await assistant.handle_ticket_webhook(webhook_data)

        logger.info(f"[TEST] Processed ticket #{ticket_id}: {result.get('status')}")
        return result

    except Exception as e:
        logger.error(f"Error handling Gorgias test webhook: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


# ==================== Slack Integration ====================

_slack_bot = None

def get_slack_bot():
    """Lazy initialization of Slack bot"""
    global _slack_bot

    if _slack_bot is None:
        # Import with proper path (parent dir already in sys.path at top of file)
        import importlib.util
        import sys

        # Get absolute path to integrations module
        integrations_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'integrations'
        )

        # Load the slack.bot module
        spec = importlib.util.spec_from_file_location(
            "integrations.slack.bot",
            os.path.join(integrations_path, 'slack', 'bot.py')
        )
        slack_bot_module = importlib.util.module_from_spec(spec)
        sys.modules['integrations.slack.bot'] = slack_bot_module
        spec.loader.exec_module(slack_bot_module)

        SlackBot = slack_bot_module.SlackBot

        slack_token = os.getenv("SLACK_BOT_TOKEN")
        slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")

        if not all([slack_token, slack_signing_secret]):
            logger.warning("Slack credentials not configured")
            return None

        api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        api_key = os.getenv("ADMIN_KEY") or os.getenv("API_KEY")

        _slack_bot = SlackBot(
            token=slack_token,
            signing_secret=slack_signing_secret,
            api_base_url=api_url,
            api_key=api_key
        )

    return _slack_bot


@app.post("/api/slack/events")
@limiter.limit("1000/hour")  # Higher limit for Slack events (burst traffic expected)
async def handle_slack_events(request: Request):
    """
    Handle Slack events (including URL verification challenge).

    Slack sends a challenge parameter during Event Subscriptions setup
    that must be echoed back immediately.
    """
    try:
        body = await request.json()

        # Handle URL verification challenge
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge")}

        # Handle actual events
        bot = get_slack_bot()
        if not bot:
            return {"status": "skipped", "reason": "Slack bot not configured"}

        handler = bot.get_handler()
        return await handler.handle(request)

    except Exception as e:
        logger.error(f"Error handling Slack event: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


# ==================== Run Application ====================

if __name__ == "__main__":
    # Railway sets PORT, fallback to 8000
    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("AUTO_RELOAD", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
