"""
Slack Event Handlers

Handle Slack events like mentions, reactions, etc.
"""
import logging
from typing import TYPE_CHECKING
from .conversation_manager import ConversationManager

if TYPE_CHECKING:
    from slack_bolt.async_app import AsyncApp
    from .bot import SlackBot

logger = logging.getLogger(__name__)

# Global conversation manager
conversation_manager = ConversationManager()


def _enhance_with_behavior_descriptions(data: dict) -> dict:
    """Add natural language behavior descriptions to archetype data."""
    answer = data.get("answer", {})

    # Enhance top_archetypes if present
    if "top_archetypes" in answer:
        for arch in answer["top_archetypes"]:
            behavior_desc = conversation_manager.describe_archetype_behaviors(arch)
            arch["behavior_description"] = behavior_desc

    # Enhance monthly_projections archetype data if present
    if "monthly_projections" in answer:
        for proj in answer["monthly_projections"]:
            if "archetype_data" in proj:
                for arch in proj["archetype_data"]:
                    behavior_desc = conversation_manager.describe_archetype_behaviors(arch)
                    arch["behavior_description"] = behavior_desc

    return data


def register_handlers(app: "AsyncApp", bot: "SlackBot"):
    """
    Register all Slack event handlers.

    Args:
        app: Slack Bolt app instance
        bot: SlackBot instance
    """

    @app.event("app_mention")
    async def handle_mention(event, say):
        """
        Handle @bot mentions with natural language queries.

        Example:
            @bot which customers are at high churn risk?
        """
        try:
            # Extract query text (remove bot mention)
            query = event.get("text", "")
            # Remove <@BOTID> from text
            query = " ".join([word for word in query.split() if not word.startswith("<@")])

            if not query.strip():
                await say("👋 Hi! Ask me anything about customer analytics!")
                return

            logger.info(f"Processing query: {query}")

            # Query analytics API
            data = await bot.query_analytics_api(query)

            # Format response based on query type
            query_type = data.get("query_type")

            if query_type == "churn_identification":
                response = bot.formatter.format_churn_response(data)
            elif query_type == "revenue_forecast":
                response = bot.formatter.format_revenue_response(data)
            elif query_type == "seasonal_archetype_recommendation":
                response = bot.formatter.format_seasonal_response(data)
            elif query_type == "campaign_targeting":
                response = bot.formatter.format_campaign_response(data)
            else:
                # Generic response
                response = {
                    "text": data.get("answer", {}).get("message", "Query processed"),
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": data.get("answer", {}).get("message", "Query processed")
                            }
                        }
                    ]
                }

            await say(**response)

        except Exception as e:
            logger.error(f"Error handling mention: {e}", exc_info=True)
            error_response = bot.formatter.format_error(str(e))
            await say(**error_response)

    @app.event("reaction_added")
    async def handle_reaction(event, say, client):
        """
        Handle reactions to messages.

        Example reactions:
            🎫 - Create ticket from message
            ✅ - Mark ticket as resolved
        """
        try:
            reaction = event.get("reaction")
            item = event.get("item", {})
            message_ts = item.get("ts")
            channel = item.get("channel")
            user = event.get("user")

            if not message_ts or not channel:
                logger.warning("Reaction event missing message_ts or channel")
                return

            # 🎫 Ticket creation reaction
            if reaction == "ticket" or reaction == "admission_tickets":
                logger.info(f"Ticket creation requested for message: {message_ts} in channel: {channel}")

                try:
                    # Fetch the original message
                    result = await client.conversations_history(
                        channel=channel,
                        latest=message_ts,
                        limit=1,
                        inclusive=True
                    )

                    if not result or not result.get("messages"):
                        await say(
                            text="❌ Could not retrieve message to create ticket",
                            thread_ts=message_ts
                        )
                        return

                    message = result["messages"][0]
                    message_text = message.get("text", "")

                    if not message_text:
                        await say(
                            text="❌ Cannot create ticket from empty message",
                            thread_ts=message_ts
                        )
                        return

                    # Check if ticketing system is configured
                    if not bot.ticketing_system:
                        await say(
                            text="❌ Ticketing system not configured. Contact your administrator.",
                            thread_ts=message_ts
                        )
                        return

                    # Extract customer ID if mentioned in message
                    customer_id = None
                    words = message_text.split()
                    for word in words:
                        # Look for customer ID patterns (e.g., C-12345, 5971333382399)
                        if word.startswith("C-") or (word.isdigit() and len(word) >= 10):
                            customer_id = word
                            break

                    # Create ticket
                    ticket_data = {
                        "subject": f"Customer issue from Slack (Channel: {channel})",
                        "description": f"**Original Slack Message:**\n{message_text}\n\n**Created by:** <@{user}>\n**Channel:** <#{channel}>\n**Timestamp:** {message_ts}",
                        "priority": "medium",
                        "tags": ["slack", "customer-support", "from-reaction"]
                    }

                    if customer_id:
                        ticket_data["tags"].append(f"customer-{customer_id}")
                        ticket_data["subject"] = f"Customer issue for {customer_id}"

                    # Create the ticket
                    ticket = await bot.ticketing_system.create_ticket(ticket_data)

                    # Reply with ticket confirmation
                    await say(
                        text=f"✅ Ticket created: #{ticket['id']}\n🔗 {ticket.get('url', 'View in Gorgias')}",
                        thread_ts=message_ts
                    )

                    logger.info(f"Created ticket {ticket['id']} from Slack message {message_ts}")

                except Exception as e:
                    logger.error(f"Error creating ticket from reaction: {e}", exc_info=True)
                    await say(
                        text=f"❌ Failed to create ticket: {str(e)}",
                        thread_ts=message_ts
                    )

            # ✅ Resolution reaction
            elif reaction == "white_check_mark":
                logger.info(f"Resolution requested for message: {message_ts} in channel: {channel}")

                try:
                    # Check if ticketing system is configured
                    if not bot.ticketing_system:
                        await say(
                            text="❌ Ticketing system not configured. Contact your administrator.",
                            thread_ts=message_ts
                        )
                        return

                    # Try to find ticket ID in the thread
                    # Look for messages with ticket IDs (format: #12345 or Ticket #12345)
                    result = await client.conversations_replies(
                        channel=channel,
                        ts=message_ts,
                        limit=100
                    )

                    ticket_id = None
                    if result and result.get("messages"):
                        for msg in result["messages"]:
                            text = msg.get("text", "")
                            # Look for ticket ID patterns
                            import re
                            # Match "Ticket created: #12345" or "#12345" or "Ticket #12345"
                            matches = re.findall(r'#(\d+)', text)
                            if matches:
                                ticket_id = matches[0]
                                break

                    if not ticket_id:
                        await say(
                            text="❓ Could not find ticket ID in this thread. Please specify ticket number.",
                            thread_ts=message_ts
                        )
                        return

                    # Resolve the ticket
                    result = await bot.ticketing_system.close_ticket(
                        ticket_id,
                        reason="Resolved via Slack ✅ reaction"
                    )

                    await say(
                        text=f"✅ Ticket #{ticket_id} marked as resolved!",
                        thread_ts=message_ts
                    )

                    logger.info(f"Resolved ticket {ticket_id} via Slack reaction")

                except Exception as e:
                    logger.error(f"Error resolving ticket from reaction: {e}", exc_info=True)
                    await say(
                        text=f"❌ Failed to resolve ticket: {str(e)}",
                        thread_ts=message_ts
                    )

        except Exception as e:
            logger.error(f"Error handling reaction: {e}", exc_info=True)

    @app.event("message")
    async def handle_dm(event, say):
        """
        Handle direct messages to the bot with conversational clarifications.
        """
        # Only respond to DMs (not in channels)
        if event.get("channel_type") == "im":
            query = event.get("text", "").strip()
            user_id = event.get("user")

            if not query:
                return

            try:
                logger.info(f"Processing DM query from {user_id}: {query}")

                # Check if user has pending context (follow-up question)
                context = conversation_manager.get_context(user_id)

                if context and context.get("pending_clarification"):
                    # User is responding to a clarification question
                    clarification = context["pending_clarification"]
                    selected_value = conversation_manager.parse_clarification_response(query, clarification)

                    if selected_value:
                        # Clear pending clarification
                        context["pending_clarification"] = None
                        conversation_manager.store_context(user_id, context["last_query"], context)

                        # Build enhanced query with clarification
                        original_query = clarification["question"]
                        enhanced_query = f"{original_query} (focusing on {selected_value})"

                        logger.info(f"Clarification resolved: {selected_value}, enhanced query: {enhanced_query}")

                        # Process enhanced query
                        data = await bot.query_analytics_api(enhanced_query)

                        # Add behavior descriptions if archetype data
                        if data.get("query_type") in ["seasonal_archetype_recommendation", "archetype_growth_projection"]:
                            data = _enhance_with_behavior_descriptions(data)

                    else:
                        await say("I didn't understand that response. " +
                                 conversation_manager.format_clarification(clarification))
                        return
                else:
                    # Check if query needs clarification
                    clarification = conversation_manager.needs_clarification(query)

                    if clarification:
                        # Store pending clarification
                        conversation_manager.store_context(user_id, query, {
                            "pending_clarification": clarification
                        })

                        # Send clarification question
                        await say(conversation_manager.format_clarification(clarification))
                        return

                    # Process query normally
                    data = await bot.query_analytics_api(query)

                    # Add behavior descriptions if archetype data
                    if data.get("query_type") in ["seasonal_archetype_recommendation", "archetype_growth_projection"]:
                        data = _enhance_with_behavior_descriptions(data)

                logger.info(f"API response: {data}")

                query_type = data.get("query_type")
                logger.info(f"Query type: {query_type}")

                # Handle missing query_type - check for direct archetype response
                if not query_type:
                    logger.warning("No query_type in API response")

                    # Check if this is a direct archetype/segment response
                    if "archetypes" in data:
                        logger.info("Detected archetype response, formatting...")
                        response = bot.formatter.format_archetype_growth_response(data)
                    # Check if this is a product analysis response
                    elif "categories" in data and "analysis_type" in data:
                        logger.info("Detected product analysis response, formatting...")
                        response = bot.formatter.format_product_analysis_response(data)
                    # Check if this is a product analysis error (not implemented)
                    elif "message" in data and "Product-level analysis is not available" in data.get("message", ""):
                        logger.info("Detected product analysis redirect message")
                        message = data.get("message", "")
                        suggestion = data.get("suggestion", "")
                        response = {
                            "text": "Product analysis not available - try customer segment analysis instead",
                            "blocks": [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": f"ℹ️ *{message}*\n\n💡 {suggestion}\n\n_Tip: Try asking about customer segments instead. For example: 'What type of customer has the highest LTV?' will show you which customer segments (including their product preferences) drive the most value._"
                                    }
                                }
                            ]
                        }
                    else:
                        message = data.get("answer", {}).get("message", "Query processed")
                        response = {
                            "text": message,
                            "blocks": [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": message
                                    }
                                }
                            ]
                        }
                elif query_type == "churn_identification" or query_type == "churn_risk_analysis":
                    response = bot.formatter.format_churn_response(data)
                elif query_type == "revenue_forecast":
                    response = bot.formatter.format_revenue_response(data)
                elif query_type == "seasonal_archetype_recommendation":
                    response = bot.formatter.format_seasonal_response(data)
                elif query_type == "campaign_targeting":
                    response = bot.formatter.format_campaign_response(data)
                elif query_type == "archetype_growth_projection":
                    response = bot.formatter.format_archetype_growth_response(data)
                elif query_type == "b2b_identification":
                    response = bot.formatter.format_b2b_response(data)
                elif query_type == "high_value_customers":
                    response = bot.formatter.format_high_value_response(data)
                elif query_type == "behavioral_analysis":
                    response = bot.formatter.format_behavioral_response(data)
                elif query_type == "product_affinity":
                    response = bot.formatter.format_product_affinity_response(data)
                elif query_type == "rfm_analysis":
                    response = bot.formatter.format_rfm_response(data)
                elif query_type == "segment_comparison":
                    response = bot.formatter.format_segment_comparison_response(data)
                elif query_type.endswith("_forecast"):  # Safe now - query_type is not None
                    response = bot.formatter.format_metric_forecast_response(data)
                elif query_type in ["customer_lookup", "customer_churn_risk", "customer_recommendations", "customer_segment", "customer_purchase_history", "customer_ltv_forecast", "customer_lookup_error"]:
                    response = bot.formatter.format_customer_lookup_response(data)
                elif query_type in ["one_time_buyers", "momentum_analysis", "declining_engagement", "behavior_change", "purchase_cadence", "discount_dependency"]:
                    response = bot.formatter.format_behavior_pattern_response(data)
                elif query_type in ["upsell_recommendations", "cross_sell_recommendations", "expansion_recommendations", "winback_recommendations", "retention_action_plan", "discount_strategy"]:
                    response = bot.formatter.format_recommendations_response(data)
                elif query_type in ["revenue_by_category", "category_popularity", "category_by_customer_segment", "category_value_metrics", "category_trends", "category_repurchase_rate", "product_bundles", "seasonal_product_performance", "individual_product_performance", "product_analysis"]:
                    response = bot.formatter.format_product_analysis_response(data)
                elif query_type == "unsupported":
                    # Format unsupported query with helpful message
                    summary = data.get("answer", {}).get("summary", "I couldn't understand that question.")
                    message = data.get("answer", {}).get("message", "")
                    examples = data.get("answer", {}).get("supported_queries", [])
                    response = {
                        "text": summary,
                        "blocks": [
                            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{summary}*\n\n{message}"}},
                            {"type": "divider"}
                        ] + [{"type": "section", "text": {"type": "mrkdwn", "text": f"• {ex}"}} for ex in examples[:5]]
                    }
                else:
                    # Generic response for general_response
                    message = data.get("answer", {}).get("message", "Query processed")
                    response = {
                        "text": message,
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": message
                                }
                            }
                        ]
                    }

                logger.info(f"Sending response: {response}")
                await say(**response)
                logger.info("Response sent successfully")

            except Exception as e:
                logger.error(f"Error handling DM: {e}", exc_info=True)
                error_response = bot.formatter.format_error(str(e))
                await say(**error_response)

    # Button action handlers
    @app.action("view_ticket_*")
    async def handle_view_ticket(ack, action, say):
        """
        Handle 'View Details' button click on ticket list.
        """
        await ack()

        ticket_id = action.get("value")
        if not ticket_id:
            return

        try:
            logger.info(f"Fetching ticket details for {ticket_id}")

            if not bot.ticketing_system:
                await say("❌ Ticketing system not configured")
                return

            # Get full ticket with comments
            ticket = await bot.ticketing_system.get_ticket_with_comments(ticket_id)

            # Format and send detailed view
            response = bot.formatter.format_ticket_details(ticket)
            await say(**response)

        except Exception as e:
            logger.error(f"Error viewing ticket {ticket_id}: {e}", exc_info=True)
            error_response = bot.formatter.format_error(f"Failed to load ticket: {str(e)}")
            await say(**error_response)

    @app.action("resolve_ticket_*")
    async def handle_resolve_ticket(ack, action, say):
        """
        Handle 'Resolve' button click - marks ticket as solved.
        """
        await ack()

        ticket_id = action.get("value")
        if not ticket_id:
            return

        try:
            logger.info(f"Resolving ticket {ticket_id}")

            if not bot.ticketing_system:
                await say("❌ Ticketing system not configured")
                return

            # Close the ticket
            result = await bot.ticketing_system.close_ticket(
                ticket_id,
                reason="Resolved via Slack"
            )

            await say(f"✅ Ticket #{ticket_id} has been marked as resolved!")

        except Exception as e:
            logger.error(f"Error resolving ticket {ticket_id}: {e}", exc_info=True)
            error_response = bot.formatter.format_error(f"Failed to resolve ticket: {str(e)}")
            await say(**error_response)

    @app.action("hold_ticket_*")
    async def handle_hold_ticket(ack, action, say):
        """
        Handle 'Hold' button click - puts ticket on hold.
        """
        await ack()

        ticket_id = action.get("value")
        if not ticket_id:
            return

        try:
            logger.info(f"Putting ticket {ticket_id} on hold")

            if not bot.ticketing_system:
                await say("❌ Ticketing system not configured")
                return

            # Update ticket to hold status
            result = await bot.ticketing_system.update_ticket(
                ticket_id,
                {"status": "hold", "comment": "Placed on hold via Slack"}
            )

            await say(f"⏸️ Ticket #{ticket_id} has been placed on hold")

        except Exception as e:
            logger.error(f"Error holding ticket {ticket_id}: {e}", exc_info=True)
            error_response = bot.formatter.format_error(f"Failed to hold ticket: {str(e)}")
            await say(**error_response)

    @app.action("comment_ticket_*")
    async def handle_comment_ticket(ack, action, client, body):
        """
        Handle 'Add Comment' button - opens modal for comment input.
        """
        await ack()

        ticket_id = action.get("value")
        if not ticket_id:
            return

        try:
            # Open modal for comment input
            await client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": f"comment_modal_{ticket_id}",
                    "title": {"type": "plain_text", "text": "Add Comment"},
                    "submit": {"type": "plain_text", "text": "Submit"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "comment_block",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "comment_input",
                                "multiline": True,
                                "placeholder": {"type": "plain_text", "text": "Enter your comment..."}
                            },
                            "label": {"type": "plain_text", "text": f"Comment for Ticket #{ticket_id}"}
                        }
                    ]
                }
            )

        except Exception as e:
            logger.error(f"Error opening comment modal: {e}", exc_info=True)

    @app.view("comment_modal_*")
    async def handle_comment_submission(ack, body, view, say):
        """
        Handle comment modal submission.
        """
        await ack()

        # Extract ticket ID from callback_id
        callback_id = view["callback_id"]
        ticket_id = callback_id.replace("comment_modal_", "")

        # Extract comment text
        comment_text = view["state"]["values"]["comment_block"]["comment_input"]["value"]

        if not comment_text:
            return

        try:
            logger.info(f"Adding comment to ticket {ticket_id}")

            if not bot.ticketing_system:
                return

            # Add comment to ticket
            await bot.ticketing_system.add_comment(ticket_id, comment_text)

            # Notify in channel
            await say(f"💬 Comment added to ticket #{ticket_id}")

        except Exception as e:
            logger.error(f"Error adding comment: {e}", exc_info=True)
