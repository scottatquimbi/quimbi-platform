"""
Webhook Endpoints Router

Provides:
- Gorgias ticket webhook (HMAC signature verification)
- Slack events webhook (signature verification)

These endpoints remain PUBLIC but use signature verification for security.
"""

from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

# Import logging
from backend.middleware.logging_config import get_logger

logger = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    tags=["webhooks"],
    responses={404: {"description": "Not found"}},
)


# ==================== Webhook Endpoints ====================
# NOTE: Webhook endpoints removed from router to avoid conflicts
#
# The webhook implementations (/api/gorgias/webhook and /api/slack/events) are
# defined directly in backend/main.py because they require complex integrations
# with Gorgias AI Assistant and Slack Bolt framework that depend on global state
# and lazy initialization patterns.
#
# This router was blocking the actual implementations (similar to the natural
# language endpoint issue). The full implementations include:
# - Gorgias: ~130 lines with signature verification, customer enrichment, AI response
# - Slack: ~40 lines with URL verification, Bolt framework delegation
#
# To avoid route conflicts, these endpoints remain in main.py.
