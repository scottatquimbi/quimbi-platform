"""
Exception hierarchy for Unified Segmentation System

Structured error handling with specific error types.
"""

from typing import Dict, Any, Optional


class QuimbiError(Exception):
    """Base exception for all Quimbi errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class BehavioralInsufficientDataError(QuimbiError):
    """Raised when insufficient behavioral data is available."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class BehavioralCalculationError(QuimbiError):
    """Raised when behavioral calculation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class TaxonomyNotFoundError(QuimbiError):
    """Raised when game taxonomy not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class SegmentNotFoundError(QuimbiError):
    """Raised when segment not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
