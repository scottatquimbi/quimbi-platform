"""
Slack Slash Commands

Register and handle Slack slash commands for quick queries.
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slack_bolt.async_app import AsyncApp
    from .bot import SlackBot

logger = logging.getLogger(__name__)


def register_commands(app: "AsyncApp", bot: "SlackBot"):
    """
    Register all slash commands.

    Args:
        app: Slack Bolt app instance
        bot: SlackBot instance
    """

    @app.command("/churn-check")
    async def churn_check(ack, command, say):
        """
        Quick churn risk check.

        Usage:
            /churn-check
        """
        await ack()

        try:
            logger.info("Running churn check command")
            data = await bot.query_analytics_api("which customers are at high churn risk")
            response = bot.formatter.format_churn_response(data)
            await say(**response)

        except Exception as e:
            logger.error(f"Error in churn-check command: {e}", exc_info=True)
            error_response = bot.formatter.format_error(str(e))
            await say(**error_response)

    @app.command("/revenue-forecast")
    async def revenue_forecast(ack, command, say):
        """
        Revenue forecast command.

        Usage:
            /revenue-forecast
            /revenue-forecast Q4
            /revenue-forecast 6 months
        """
        await ack()

        try:
            timeframe = command.get("text", "").strip() or "12 months"
            logger.info(f"Running revenue forecast for: {timeframe}")

            data = await bot.query_analytics_api(f"revenue forecast for {timeframe}")
            response = bot.formatter.format_revenue_response(data)
            await say(**response)

        except Exception as e:
            logger.error(f"Error in revenue-forecast command: {e}", exc_info=True)
            error_response = bot.formatter.format_error(str(e))
            await say(**error_response)

    @app.command("/seasonal-analysis")
    async def seasonal_analysis(ack, command, say):
        """
        Seasonal customer analysis.

        Usage:
            /seasonal-analysis halloween
            /seasonal-analysis christmas
            /seasonal-analysis black friday
        """
        await ack()

        try:
            event = command.get("text", "").strip() or "holiday season"
            logger.info(f"Running seasonal analysis for: {event}")

            data = await bot.query_analytics_api(
                f"which customers will be engaged during {event}"
            )
            response = bot.formatter.format_seasonal_response(data)
            await say(**response)

        except Exception as e:
            logger.error(f"Error in seasonal-analysis command: {e}", exc_info=True)
            error_response = bot.formatter.format_error(str(e))
            await say(**error_response)

    @app.command("/campaign-targets")
    async def campaign_targets(ack, command, say):
        """
        Get campaign targeting recommendations.

        Usage:
            /campaign-targets retention
            /campaign-targets growth
            /campaign-targets winback
        """
        await ack()

        try:
            campaign_type = command.get("text", "").strip() or "retention"
            logger.info(f"Getting campaign targets for: {campaign_type}")

            data = await bot.query_analytics_api(
                f"who should we target for {campaign_type} campaign"
            )
            response = bot.formatter.format_campaign_response(data)
            await say(**response)

        except Exception as e:
            logger.error(f"Error in campaign-targets command: {e}", exc_info=True)
            error_response = bot.formatter.format_error(str(e))
            await say(**error_response)

    @app.command("/tickets")
    async def view_tickets(ack, command, say):
        """
        View open customer success tickets.

        Usage:
            /tickets
            /tickets open
            /tickets urgent
        """
        await ack()

        if not bot.ticketing_system:
            await say("❌ Ticketing system not configured")
            return

        try:
            # Parse filter from command text
            text = command.get("text", "").strip().lower()

            if text == "urgent":
                status = "open"
                priority = "urgent"
            elif text == "high":
                status = "open"
                priority = "high"
            else:
                status = "open"
                priority = None

            logger.info(f"Fetching tickets: status={status}, priority={priority}")

            # Get tickets from Zendesk
            tickets = await bot.ticketing_system.list_tickets(
                status=status,
                tags=["churn-risk"],
                priority=priority,
                limit=25
            )

            # Format and send
            response = bot.formatter.format_ticket_list(tickets)
            await say(**response)

        except Exception as e:
            logger.error(f"Error in tickets command: {e}", exc_info=True)
            error_response = bot.formatter.format_error(str(e))
            await say(**error_response)

    @app.command("/cs-help")
    async def cs_help(ack, say):
        """
        Show help for customer success commands.

        Usage:
            /cs-help
        """
        await ack()

        # Check if ticketing is enabled
        ticketing_commands = ""
        if bot.ticketing_system:
            ticketing_commands = (
                "• `/tickets` - View open customer success tickets\n"
                "• `/tickets urgent` - View only urgent tickets\n"
            )

        help_text = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🤖 Customer Success Bot Help"}
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*Available Commands:*\n\n"
                            "• `/churn-check` - View customers at high churn risk\n"
                            "• `/revenue-forecast [timeframe]` - Get revenue projections\n"
                            "• `/seasonal-analysis [event]` - Analyze seasonal customer behavior\n"
                            "• `/campaign-targets [type]` - Get campaign recommendations\n"
                            f"{ticketing_commands}"
                            "• `/cs-help` - Show this help message\n\n"
                            "*Natural Language Queries:*\n"
                            "Just @mention me with any question:\n"
                            "• `@bot which customers are at high churn risk?`\n"
                            "• `@bot what's our revenue forecast for Q4?`\n"
                            "• `@bot how many people shop during halloween?`\n"
                            "• `@bot who should we target for retention campaign?`"
                        )
                    }
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "💡 *Tip:* You can also DM me directly with questions!"
                        }
                    ]
                }
            ]
        }

        await say(**help_text)
