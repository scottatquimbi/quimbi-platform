"""
Platform Layer - Quimbi Brain

This package contains the core platform intelligence and generation APIs
that external applications can consume.

Exports:
- intelligence_router: Customer analysis, predictions, segmentation
- generation_router: AI-generated messages, actions, campaigns
"""

from .intelligence import router as intelligence_router
from .generation import router as generation_router

__all__ = [
    "intelligence_router",
    "generation_router",
]
