"""
Slack Integration Module

Provides Slack bot functionality for customer success queries.

Usage:
    from integrations.slack.bot import SlackBot

    bot = SlackBot(
        token=os.getenv("SLACK_BOT_TOKEN"),
        signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
        api_base_url="https://your-api.com"
    )

    await bot.start()
"""

# Don't import here to avoid circular imports
# Import directly: from integrations.slack.bot import SlackBot

__all__ = ["SlackBot", "SlackFormatter"]
