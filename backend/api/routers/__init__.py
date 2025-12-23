"""
API Routers

Exports all routers for the FastAPI application.
"""
from .admin import router as admin_router
from .health import router as health_router
from .customers import router as customers_router
from .customer_alias import router as customer_alias_router
from .analytics import router as analytics_router
from .campaigns import router as campaigns_router
from .mcp import router as mcp_router
from .webhooks import router as webhooks_router
from .segments import router as segments_router
from .system import router as system_router
from .tickets import router as tickets_router
from .ai import router as ai_router
from .drift_analysis import router as drift_router

__all__ = [
    "admin_router",
    "health_router",
    "customers_router",
    "customer_alias_router",
    "analytics_router",
    "campaigns_router",
    "mcp_router",
    "webhooks_router",
    "segments_router",
    "system_router",
    "tickets_router",
    "ai_router",
    "drift_router",
]
