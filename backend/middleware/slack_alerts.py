"""
Slack Alert Integration

Sends critical errors and alerts to Slack channel.
"""

import os
import aiohttp
import structlog
from typing import Optional, Dict, Any
from datetime import datetime

logger = structlog.get_logger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


async def send_slack_alert(
    title: str,
    message: str,
    level: str = "error",
    details: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send alert to Slack channel.

    Args:
        title: Alert title
        message: Alert message
        level: Severity level (error, warning, info)
        details: Additional context

    Returns:
        True if sent successfully, False otherwise
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("slack_webhook_not_configured")
        return False

    # Color coding by severity
    colors = {
        "error": "#FF0000",  # Red
        "warning": "#FFA500",  # Orange
        "info": "#0000FF",  # Blue
        "success": "#00FF00"  # Green
    }
    color = colors.get(level, "#808080")

    # Build Slack message
    slack_payload = {
        "attachments": [
            {
                "color": color,
                "title": f"⚠️ {title}" if level == "error" else title,
                "text": message,
                "footer": "Customer Intelligence Platform",
                "ts": int(datetime.utcnow().timestamp()),
                "fields": []
            }
        ]
    }

    # Add details as fields
    if details:
        for key, value in details.items():
            slack_payload["attachments"][0]["fields"].append({
                "title": key.replace("_", " ").title(),
                "value": str(value),
                "short": True
            })

    # Send to Slack
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SLACK_WEBHOOK_URL,
                json=slack_payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    logger.info("slack_alert_sent", title=title, level=level)
                    return True
                else:
                    logger.error(
                        "slack_alert_failed",
                        status=response.status,
                        response=await response.text()
                    )
                    return False
    except Exception as e:
        logger.error("slack_alert_exception", error=str(e))
        return False


async def send_error_alert(
    error_type: str,
    error_message: str,
    correlation_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    user_id: Optional[str] = None
) -> None:
    """
    Send error alert to Slack.

    Args:
        error_type: Type of error (e.g., "DatabaseError", "AuthenticationError")
        error_message: Error message
        correlation_id: Request correlation ID
        endpoint: API endpoint where error occurred
        user_id: User/customer ID if available
    """
    details = {}
    if correlation_id:
        details["Correlation ID"] = correlation_id
    if endpoint:
        details["Endpoint"] = endpoint
    if user_id:
        details["User/Customer"] = user_id

    await send_slack_alert(
        title=f"Production Error: {error_type}",
        message=error_message,
        level="error",
        details=details
    )


async def send_performance_alert(
    endpoint: str,
    response_time: float,
    threshold: float = 2.0
) -> None:
    """
    Send performance alert if response time exceeds threshold.

    Args:
        endpoint: API endpoint
        response_time: Response time in seconds
        threshold: Threshold in seconds (default: 2.0)
    """
    if response_time > threshold:
        await send_slack_alert(
            title="Slow API Response",
            message=f"Endpoint {endpoint} took {response_time:.2f}s (threshold: {threshold}s)",
            level="warning",
            details={
                "Endpoint": endpoint,
                "Response Time": f"{response_time:.2f}s",
                "Threshold": f"{threshold}s"
            }
        )


async def send_deployment_alert(
    status: str,
    version: Optional[str] = None,
    error: Optional[str] = None
) -> None:
    """
    Send deployment status alert.

    Args:
        status: Deployment status (started, completed, failed)
        version: Deployment version/commit
        error: Error message if failed
    """
    level = "success" if status == "completed" else "error" if status == "failed" else "info"

    details = {}
    if version:
        details["Version"] = version
    if error:
        details["Error"] = error

    emoji = "✅" if status == "completed" else "❌" if status == "failed" else "🚀"

    await send_slack_alert(
        title=f"{emoji} Deployment {status.title()}",
        message=f"Deployment {status}",
        level=level,
        details=details
    )


async def send_health_alert(
    component: str,
    status: str,
    message: Optional[str] = None
) -> None:
    """
    Send health check alert.

    Args:
        component: Component name (database, redis, api)
        status: Health status (healthy, degraded, down)
        message: Additional context
    """
    level = "success" if status == "healthy" else "warning" if status == "degraded" else "error"

    emoji = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"

    await send_slack_alert(
        title=f"{emoji} {component.title()} {status.title()}",
        message=message or f"{component} is {status}",
        level=level,
        details={"Component": component, "Status": status}
    )
