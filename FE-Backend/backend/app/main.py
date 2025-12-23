"""
AI-First CRM Backend

Philosophy: Intelligence Replaces Interface
- Smart inbox ordering (no sort UI needed)
- AI-generated response drafts (no template selection)
- Proactive context gathering (no manual lookup)
- Auto-categorization (no manual tagging)

Built with FastAPI for high performance async operations.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import tickets, ai


# Create FastAPI app
app = FastAPI(
    title="AI-First CRM",
    description="Intelligent customer support system with invisible AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tickets.router, prefix="/api", tags=["tickets"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AI-First CRM",
        "philosophy": "Intelligence Replaces Interface",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "features": {
            "smart_inbox_ordering": True,
            "topic_alerts": True,
            "ai_draft_generation": True,
            "proactive_context": True,
            "auto_categorization": False  # Phase 2
        }
    }
