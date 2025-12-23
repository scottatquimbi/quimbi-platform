"""
Slack Bot Implementation

Main Slack bot that handles customer success queries.
"""
import os
import logging
from typing import Optional
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from fastapi import FastAPI, Request

from ..base import BaseIntegration
from .formatters import SlackFormatter
from .handlers import register_handlers
from .commands import register_commands

logger = logging.getLogger(__name__)


class SlackBot(BaseIntegration):
    """
    Slack bot for customer success queries.

    Handles:
    - @mentions with natural language queries
    - Slash commands (/churn-check, /revenue-forecast, etc.)
    - Interactive buttons and actions
    """

    def __init__(
        self,
        token: str,
        signing_secret: str,
        api_base_url: str,
        api_key: Optional[str] = None,
        app_token: Optional[str] = None,
        ticketing_system: Optional[object] = None
    ):
        """
        Initialize Slack bot.

        Args:
            token: Slack bot token (xoxb-...)
            signing_secret: Slack signing secret for verification
            api_base_url: URL of analytics API
            api_key: API key for analytics API authentication (optional)
            app_token: Slack app token for Socket Mode (optional)
            ticketing_system: TicketingSystem instance (optional)
        """
        super().__init__(api_base_url, api_key)

        self.token = token
        self.signing_secret = signing_secret
        self.app_token = app_token
        self.ticketing_system = ticketing_system

        # Initialize Slack app
        self.app = AsyncApp(
            token=token,
            signing_secret=signing_secret
        )

        # Initialize formatter
        self.formatter = SlackFormatter()

        # Register handlers and commands
        register_handlers(self.app, self)
        register_commands(self.app, self)

        logger.info("Slack bot initialized")

    async def setup(self) -> None:
        """Setup the Slack bot"""
        logger.info("Slack bot setup complete")

    async def health_check(self) -> bool:
        """Check if Slack API is accessible"""
        try:
            response = await self.app.client.auth_test()
            return response["ok"]
        except Exception as e:
            logger.error(f"Slack health check failed: {e}")
            return False

    def get_handler(self) -> AsyncSlackRequestHandler:
        """
        Get FastAPI handler for Slack events.

        Returns:
            Slack request handler for FastAPI
        """
        return AsyncSlackRequestHandler(self.app)

    async def start_socket_mode(self):
        """Start bot in Socket Mode (for local development)"""
        if not self.app_token:
            raise ValueError("app_token required for Socket Mode")

        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        handler = AsyncSocketModeHandler(self.app, self.app_token)
        await handler.start_async()


# Standalone entry point
async def create_slack_bot_app() -> FastAPI:
    """
    Create standalone FastAPI app with Slack bot.

    Usage:
        uvicorn integrations.slack.bot:create_slack_bot_app --factory
    """
    app = FastAPI(title="Slack Bot Service")

    bot = SlackBot(
        token=os.getenv("SLACK_BOT_TOKEN"),
        signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8080"),
        api_key=os.getenv("ADMIN_KEY") or os.getenv("API_KEY")
    )

    await bot.setup()

    @app.post("/slack/events")
    async def slack_events(request: Request):
        """Handle Slack events"""
        handler = bot.get_handler()
        return await handler.handle(request)

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        is_healthy = await bot.health_check()
        return {"status": "healthy" if is_healthy else "unhealthy"}

    return app


if __name__ == "__main__":
    """Run bot in Socket Mode for local development"""
    import asyncio

    async def main():
        bot = SlackBot(
            token=os.getenv("SLACK_BOT_TOKEN"),
            signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
            api_base_url=os.getenv("API_BASE_URL", "http://localhost:8080"),
            api_key=os.getenv("ADMIN_KEY") or os.getenv("API_KEY"),
            app_token=os.getenv("SLACK_APP_TOKEN")
        )
        await bot.setup()
        logger.info("Starting Slack bot in Socket Mode...")
        await bot.start_socket_mode()

    asyncio.run(main())
