"""
Slack Response Formatters

Format analytics API responses as Slack Block Kit messages.
"""
from typing import Dict, Any, List
from ..base import BaseFormatter


class SlackFormatter(BaseFormatter):
    """Format API responses for Slack using Block Kit"""

    def format_churn_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format churn analysis as Slack blocks.

        Args:
            data: Churn analysis response from API

        Returns:
            Slack message with blocks
        """
        answer = data.get("answer", {})
        customers = answer.get("top_at_risk_customers", [])[:10]

        # Calculate actual churn statistics from customers list
        if customers:
            total_ltv_at_risk = sum(c.get('ltv', 0) for c in customers)
            avg_churn = sum(c.get('churn_risk', 0) for c in customers) / len(customers)
            total_customers = len(customers)

            # Calculate churn impact (LTV × churn_risk) for each customer
            for customer in customers:
                ltv = customer.get('ltv', 0)
                churn_risk = customer.get('churn_risk', 0)
                customer['churn_impact'] = ltv * churn_risk

            # Sort by churn impact (highest first)
            customers_sorted = sorted(customers, key=lambda c: c.get('churn_impact', 0), reverse=True)
        else:
            total_ltv_at_risk = 0
            avg_churn = 0
            total_customers = 0
            customers_sorted = []

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "⚠️ High Churn Risk Customers"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{total_customers} customers identified* (sorted by revenue impact)"
                }
            },
            {"type": "divider"}
        ]

        # Add customer sections
        for i, customer in enumerate(customers_sorted, 1):
            churn_impact = customer.get('churn_impact', 0)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{i}. {customer.get('customer_id', 'N/A')}*\n"
                        f"💰 LTV: ${customer.get('ltv', 0):,.0f} | "
                        f"⚠️ Risk: {customer.get('churn_risk', 0)*100:.0f}% | "
                        f"💥 Impact: ${churn_impact:,.0f} | "
                        f"Level: {customer.get('risk_level', 'unknown').upper()}"
                    )
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Create Ticket"},
                    "action_id": f"create_ticket_{customer.get('customer_id', '')}",
                    "style": "danger"
                }
            })

        # Add aggregate metrics
        if total_customers > 0:
            total_churn_impact = sum(c.get('churn_impact', 0) for c in customers_sorted)
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Total LTV at Risk:*\n${total_ltv_at_risk:,.0f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Avg Churn Risk:*\n{avg_churn*100:.0f}%"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Expected Revenue Loss:*\n${total_churn_impact:,.0f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Customers at Risk:*\n{total_customers}"
                    }
                ]
            })

        return {
            "text": f"{total_customers} customers at high churn risk",
            "blocks": blocks
        }

    def format_revenue_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format revenue forecast as Slack blocks.

        Args:
            data: Revenue forecast response from API

        Returns:
            Slack message with blocks
        """
        answer = data.get("answer", {})
        forecast = answer.get("forecast", {})

        current_ltv = forecast.get("current_total_ltv", 0)
        projected_ltv = forecast.get("projected_total_ltv", 0)
        growth_pct = forecast.get("growth_rate_pct", 0)
        months = forecast.get("timeframe_months", 12)

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📈 Revenue Forecast"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'Revenue Projection')}*"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Current LTV:*\n${current_ltv:,.0f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Projected LTV:*\n${projected_ltv:,.0f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Growth Rate:*\n{'+' if growth_pct > 0 else ''}{growth_pct}%"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Timeframe:*\n{months} months"
                    }
                ]
            }
        ]

        # Add key insights
        insights = answer.get("key_insights", [])
        if insights:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Key Insights:*\n" + "\n".join(f"• {insight}" for insight in insights)
                }
            })

        return {
            "text": answer.get("summary", "Revenue Forecast"),
            "blocks": blocks
        }

    def format_seasonal_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format seasonal analysis as Slack blocks.

        Args:
            data: Seasonal analysis response from API

        Returns:
            Slack message with blocks
        """
        answer = data.get("answer", {})
        archetypes = answer.get("top_archetypes", [])[:5]

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🎃 Seasonal Customer Analysis"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'Seasonal Analysis')}*"
                }
            },
            {"type": "divider"}
        ]

        # Add archetype sections
        for i, arch in enumerate(archetypes, 1):
            reasons = arch.get("recommendation_reasons", [])
            behavior = arch.get("behavior_description", "")

            # Build description text
            desc_text = f"*{i}. Customer Segment #{i}* (Score: {arch.get('score', 0):.1f})\n"

            if behavior:
                desc_text += f"👥 *Behaviors:* {behavior}\n"

            desc_text += f"💰 *Total LTV:* ${arch.get('total_ltv', 0):,.0f}\n"
            desc_text += f"📊 *Size:* {arch.get('population_percentage', 0):.1f}% of customer base"

            if reasons:
                desc_text += f"\n✨ *Why target:* {', '.join(reasons)}"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": desc_text
                }
            })

        # Add campaign strategy
        strategy = answer.get("campaign_strategy", {})
        if strategy:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*📋 Campaign Strategy:*\n"
                        f"⏰ *Timing:* {strategy.get('timing', 'N/A')}\n"
                        f"💬 *Messaging:* {strategy.get('messaging', 'N/A')}\n"
                        f"📢 *Channels:* {strategy.get('channels', 'N/A')}\n"
                        f"🎁 *Offers:* {strategy.get('offers', 'N/A')}"
                    )
                }
            })

        return {
            "text": answer.get("summary", "Seasonal Analysis"),
            "blocks": blocks
        }

    def format_campaign_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format campaign targeting as Slack blocks.

        Args:
            data: Campaign targeting response from API

        Returns:
            Slack message with blocks
        """
        answer = data.get("answer", {})
        customers = answer.get("recommended_customers", [])[:10]
        campaign_type = answer.get("campaign_type", "unknown")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🎯 {campaign_type.title()} Campaign Targets"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'Campaign Recommendations')}*"
                }
            },
            {"type": "divider"}
        ]

        # Add customer sections
        for i, customer in enumerate(customers, 1):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{i}. {customer.get('customer_id', 'N/A')}*\n"
                        f"💰 LTV: ${customer.get('ltv', 0):,.0f} | "
                        f"📊 Score: {customer.get('score', 0):.0f}"
                    )
                }
            })

        return {
            "text": answer.get("summary", "Campaign Targets"),
            "blocks": blocks
        }

    def format_ticket_list(self, tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format list of Zendesk tickets as Slack blocks.

        Args:
            tickets: List of ticket summaries

        Returns:
            Slack message with blocks
        """
        if not tickets:
            return {
                "text": "No tickets found",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "✅ *No open tickets found*\nAll customer success issues are resolved!"
                        }
                    }
                ]
            }

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🎫 Open Customer Success Tickets"}
            },
            {"type": "divider"}
        ]

        for ticket in tickets[:10]:  # Limit to 10 tickets
            status_emoji = {
                "new": "🆕",
                "open": "🔓",
                "pending": "⏳",
                "hold": "⏸️",
                "solved": "✅",
                "closed": "🔒"
            }.get(ticket.get("status", ""), "📋")

            priority_emoji = {
                "urgent": "🚨",
                "high": "⚠️",
                "normal": "📊",
                "low": "ℹ️"
            }.get(ticket.get("priority", ""), "📊")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{status_emoji} *{ticket.get('subject', 'Untitled')}*\n"
                        f"{priority_emoji} Priority: {ticket.get('priority', 'normal').title()} | "
                        f"Status: {ticket.get('status', 'unknown').title()}\n"
                        f"🏷️ Tags: {', '.join(ticket.get('tags', [])[:3])}"
                    )
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Details"},
                    "action_id": f"view_ticket_{ticket.get('id', '')}",
                    "value": ticket.get('id', '')
                }
            })

        return {
            "text": f"Found {len(tickets)} open ticket(s)",
            "blocks": blocks
        }

    def format_ticket_details(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format full ticket details with comments as Slack blocks.

        Args:
            ticket: Full ticket data with comments

        Returns:
            Slack message with blocks
        """
        status_emoji = {
            "new": "🆕",
            "open": "🔓",
            "pending": "⏳",
            "hold": "⏸️",
            "solved": "✅",
            "closed": "🔒"
        }.get(ticket.get("status", ""), "📋")

        priority_emoji = {
            "urgent": "🚨",
            "high": "⚠️",
            "normal": "📊",
            "low": "ℹ️"
        }.get(ticket.get("priority", ""), "📊")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🎫 Ticket #{ticket.get('id', 'N/A')}"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{ticket.get('subject', 'Untitled')}*"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{status_emoji} {ticket.get('status', 'unknown').title()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Priority:*\n{priority_emoji} {ticket.get('priority', 'normal').title()}"
                    }
                ]
            }
        ]

        # Add description
        description = ticket.get("description", "No description")
        if len(description) > 500:
            description = description[:500] + "..."

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n{description}"
            }
        })

        # Add comments
        comments = ticket.get("comments", [])
        if comments and len(comments) > 1:  # Skip first comment (usually description)
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Comments ({len(comments) - 1}):*"
                }
            })

            # Show last 3 comments
            for comment in comments[-3:]:
                if comment.get("body"):
                    comment_text = comment["body"]
                    if len(comment_text) > 200:
                        comment_text = comment_text[:200] + "..."

                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"💬 {comment_text}"
                        }
                    })

        # Add action buttons
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Resolve"},
                    "action_id": f"resolve_ticket_{ticket.get('id', '')}",
                    "style": "primary",
                    "value": ticket.get('id', '')
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "💬 Add Comment"},
                    "action_id": f"comment_ticket_{ticket.get('id', '')}",
                    "value": ticket.get('id', '')
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "⏸️ Hold"},
                    "action_id": f"hold_ticket_{ticket.get('id', '')}",
                    "value": ticket.get('id', '')
                }
            ]
        })

        return {
            "text": f"Ticket #{ticket.get('id', 'N/A')}: {ticket.get('subject', 'Untitled')}",
            "blocks": blocks
        }

    def format_archetype_growth_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format archetype growth projection as Slack blocks.

        Args:
            data: Archetype growth projection response from API

        Returns:
            Slack message with blocks
        """
        from .conversation_manager import ConversationManager

        # Handle both old format (answer.projections) and new format (direct archetypes)
        if "archetypes" in data:
            # New format: direct archetypes array
            archetypes = data.get("archetypes", [])[:10]
            sort_by = data.get("sort_by", "total_revenue")
            query = data.get("query", "").lower()

            # Check if this is a product-focused query
            is_product_query = any(word in query for word in ["product", "category", "categories", "item", "sku"])

            # Determine header based on sort_by and query type
            if is_product_query and sort_by == "ltv":
                header_title = "🛍️ Product Preferences of High-LTV Customers"
                summary = f"Customer segments sorted by LTV - look at their category preferences"
            elif sort_by == "frequency":
                header_title = "🔄 Top Customer Types by Repeat Purchases"
                summary = f"Sorted by average orders per customer"
            elif sort_by == "ltv":
                header_title = "💰 Top Customer Types by Lifetime Value"
                summary = f"Sorted by average LTV"
            elif sort_by == "size":
                header_title = "👥 Largest Customer Segments"
                summary = f"Sorted by customer count"
            else:
                header_title = "👥 Customer Types We Serve"
                summary = "Customer segment analysis"
        else:
            # Old format: answer.projections
            answer = data.get("answer", {})
            archetypes = answer.get("projections", [])[:10]
            header_title = "👥 Customer Types We Serve"
            summary = answer.get('summary', 'Customer segment analysis')
            is_product_query = False  # Old format doesn't have query field

        # Initialize conversation manager for behavior descriptions
        conv_mgr = ConversationManager()

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header_title}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{summary}*"
                }
            },
            {"type": "divider"}
        ]

        # Add customer type sections
        for i, arch in enumerate(archetypes, 1):
            # Handle both old (proj) and new (arch) field names
            behavior_desc = conv_mgr.describe_archetype_behaviors(arch)

            # New format uses member_count, old uses current_members
            current = arch.get('member_count', arch.get('current_members', 0))
            projected = arch.get('projected_members', current)  # No projection in new format
            growth_pct = arch.get('growth_rate_pct', 0)

            # New format uses total_revenue, old uses total_ltv
            total_ltv = arch.get('total_revenue', arch.get('total_ltv', 0))
            avg_ltv = arch.get('avg_ltv', 0)
            avg_orders = arch.get('avg_orders', 0)
            avg_days_since = arch.get('avg_days_since_purchase', 0)

            # Get category affinity for product queries
            dominant_segments = arch.get('dominant_segments', {})
            category_affinity = dominant_segments.get('category_affinity', '')

            desc_text = f"*{i}. Customer Type #{i}*\n"

            # For product queries, lead with category affinity
            if is_product_query and category_affinity:
                # Format category affinity nicely
                category_display = category_affinity.replace('_', ' ').title()
                desc_text += f"🛍️ *Category Preference:* {category_display}\n"

            desc_text += f"👥 *Who they are:* {behavior_desc}\n"
            desc_text += f"📊 *Customers:* {current:,}\n"

            # Show relevant metrics based on what's available
            if avg_orders > 0:
                desc_text += f"🔄 *Avg Orders:* {avg_orders:.0f} purchases\n"

            if avg_ltv > 0:
                desc_text += f"💰 *Avg LTV:* ${avg_ltv:,.0f}\n"
            elif total_ltv > 0:
                desc_text += f"💰 *Total Value:* ${total_ltv:,.0f}\n"

            if avg_days_since > 0:
                desc_text += f"📅 *Last Purchase:* {avg_days_since:.0f} days ago\n"

            # Only show growth if available (old format)
            if growth_pct > 0:
                desc_text += f"📈 *Growing:* +{growth_pct:.0f}% (to {projected:,} customers)"
            elif growth_pct < 0:
                desc_text += f"📉 *Shrinking:* {growth_pct:.0f}% (to {projected:,} customers)"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": desc_text
                }
            })

        # Add key insights (old format only)
        if "archetypes" not in data:
            answer = data.get("answer", {})
            insights = answer.get("key_insights", [])
            if insights:
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Key Insights:*\n" + "\n".join(f"• {insight}" for insight in insights)
                    }
                })

        # Add footer with total count
        total = data.get("total_archetypes", len(archetypes))
        if total > len(archetypes):
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"_Showing top {len(archetypes)} of {total} customer types_"
                }]
            })

        return {
            "text": f"Found {len(archetypes)} customer types",
            "blocks": blocks
        }

    def format_b2b_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format B2B identification response for Slack."""
        answer = data.get("answer", {})
        customers = answer.get("customers", [])[:10]
        metrics = answer.get("aggregate_metrics", {})

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🏢 Business Customer Identification"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'B2B customer analysis')}*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total B2B Value:*\n${metrics.get('total_b2b_ltv', 0):,.0f}"},
                    {"type": "mrkdwn", "text": f"*Avg B2B LTV:*\n${metrics.get('avg_b2b_ltv', 0):,.0f}"},
                    {"type": "mrkdwn", "text": f"*Total B2B Orders:*\n{metrics.get('total_b2b_orders', 0):,}"},
                    {"type": "mrkdwn", "text": f"*B2B Customers:*\n{len(customers)}"}
                ]
            },
            {"type": "divider"}
        ]

        # Add top B2B customers
        for i, customer in enumerate(customers[:10], 1):
            customer_id = customer.get('customer_id', 'Unknown')
            ltv = customer.get('ltv', 0)
            orders = customer.get('order_count', 0)
            b2b_score = customer.get('b2b_score', 0)
            indicators = customer.get('b2b_indicators', [])

            text = f"*{i}. Customer {customer_id}*\n"
            text += f"💰 LTV: ${ltv:,.0f} | 📦 {orders} orders | ⭐ Score: {b2b_score}\n"
            text += f"🔍 Indicators: {', '.join(indicators)}"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            })

        return {"text": f"Found {len(customers)} B2B customers", "blocks": blocks}

    def format_high_value_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format high-value customer response for Slack."""
        answer = data.get("answer", {})
        customers = answer.get("customers", [])[:10]
        metrics = answer.get("aggregate_metrics", {})

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "💎 High-Value Customers"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'Top customers by value')}*"
                }
            },
            {"type": "divider"}
        ]

        for i, customer in enumerate(customers[:10], 1):
            customer_id = customer.get('customer_id', 'Unknown')
            ltv = customer.get('ltv', 0)
            orders = customer.get('order_count', 0)
            churn_risk = customer.get('churn_risk', 0)

            text = f"*{i}. Customer {customer_id}*\n"
            text += f"💰 ${ltv:,.0f} LTV | 📦 {orders} orders | ⚠️ {churn_risk:.0%} churn risk"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            })

        return {"text": f"Top {len(customers)} highest value customers", "blocks": blocks}

    def format_behavioral_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format behavioral analysis response for Slack."""
        answer = data.get("answer", {})
        customers = answer.get("customers", [])[:10]
        filters = answer.get("filters_applied", {})

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🎯 Behavioral Analysis"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'Customer behavior analysis')}*"
                }
            }
        ]

        if filters:
            filter_text = "\n".join([f"• {k}: {v}" for k, v in filters.items()])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Filters Applied:*\n{filter_text}"}
            })

        blocks.append({"type": "divider"})

        for i, customer in enumerate(customers[:10], 1):
            customer_id = customer.get('customer_id', 'Unknown')
            ltv = customer.get('ltv', 0)
            orders = customer.get('order_count', 0)

            text = f"*{i}. Customer {customer_id}*\n💰 ${ltv:,.0f} LTV | 📦 {orders} orders"
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        return {"text": f"Behavioral analysis: {len(customers)} customers", "blocks": blocks}

    def format_product_affinity_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format product affinity response for Slack."""
        answer = data.get("answer", {})
        archetypes = answer.get("archetypes", [])[:10]

        from .conversation_manager import ConversationManager
        conv_mgr = ConversationManager()

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🛍️ Product Category Preferences"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'Category affinity by customer type')}*"
                }
            },
            {"type": "divider"}
        ]

        for i, archetype in enumerate(archetypes, 1):
            behavior_desc = conv_mgr.describe_archetype_behaviors(archetype)
            current = archetype.get('current_members', 0)
            total_ltv = archetype.get('total_ltv', 0)

            text = f"*{i}. Customer Type #{i}*\n"
            text += f"👥 {current:,} customers who are {behavior_desc}\n"
            text += f"💰 Total value: ${total_ltv:,.0f}"

            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        return {"text": f"Product affinity analysis for {len(archetypes)} segments", "blocks": blocks}

    def format_rfm_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format RFM analysis response for Slack."""
        answer = data.get("answer", {})
        customers = answer.get("customers", [])[:10]

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 RFM Analysis"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Recency, Frequency, Monetary (RFM) customer scoring*"
                }
            },
            {"type": "divider"}
        ]

        for i, customer in enumerate(customers[:10], 1):
            customer_id = customer.get('customer_id', 'Unknown')
            ltv = customer.get('ltv', 0)
            rfm = customer.get('rfm_score', {})

            r = rfm.get('recency', 0)
            f = rfm.get('frequency', 0)
            m = rfm.get('monetary', 0)
            total = rfm.get('total', 0)

            text = f"*{i}. Customer {customer_id}* (Score: {total}/15)\n"
            text += f"💰 ${ltv:,.0f} LTV | 📊 R:{r} F:{f} M:{m}"

            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        return {"text": f"RFM analysis for {len(customers)} customers", "blocks": blocks}

    def format_segment_comparison_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format segment comparison response for Slack."""
        answer = data.get("answer", {})
        segments = answer.get("segments", [])
        metrics = answer.get("metrics_compared", [])

        from .conversation_manager import ConversationManager
        conv_mgr = ConversationManager()

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔍 Segment Comparison"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'Comparing customer segments')}*"
                }
            },
            {"type": "divider"}
        ]

        for i, segment in enumerate(segments, 1):
            behavior_desc = conv_mgr.describe_archetype_behaviors(segment)
            current = segment.get('current_members', 0)
            total_ltv = segment.get('total_ltv', 0)
            growth = segment.get('growth_rate_pct', 0)

            text = f"*{i}. Customer Type #{i}*\n"
            text += f"👥 {behavior_desc}\n"
            text += f"📊 {current:,} customers | 💰 ${total_ltv:,.0f} value"
            if growth != 0:
                text += f" | 📈 {growth:+.0f}% growth"

            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        return {"text": f"Comparison of {len(segments)} segments", "blocks": blocks}

    def format_metric_forecast_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format metric forecast response for Slack."""
        answer = data.get("answer", {})
        query_type = data.get("query_type", "forecast")

        metric_name = query_type.replace("_forecast", "").replace("_", " ").title()
        current = answer.get("current_value", 0)
        projected = answer.get("projected_value", 0)
        growth = answer.get("growth_rate", 0)
        months = answer.get("timeframe_months", 12)

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📈 {metric_name} Forecast"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', f'{metric_name} projection')}*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Current {metric_name}:*\n{current:,.0f}"},
                    {"type": "mrkdwn", "text": f"*Projected ({months}mo):*\n{projected:,.0f}"},
                    {"type": "mrkdwn", "text": f"*Growth Rate:*\n{growth:+.1f}%"},
                    {"type": "mrkdwn", "text": f"*Change:*\n{projected - current:+,.0f}"}
                ]
            }
        ]

        return {"text": f"{metric_name} forecast: {growth:+.1f}% growth", "blocks": blocks}

    def format_customer_lookup_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format individual customer lookup response for Slack."""
        answer = data.get("answer", {})
        query_type = data.get("query_type", "customer_lookup")
        customer_id = answer.get("customer_id", "Unknown")

        if "error" in answer:
            return {
                "text": f"Could not find customer {customer_id}",
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": "❌ Customer Not Found"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*Error:* {answer['error']}"}}
                ]
            }

        if query_type == "customer_churn_risk":
            churn_risk = answer.get("churn_risk", 0)
            ltv = answer.get("lifetime_value", 0)
            orders = answer.get("order_count", 0)

            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": f"📊 Customer {customer_id}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Churn Risk:*\n{churn_risk:.1%}"},
                    {"type": "mrkdwn", "text": f"*LTV:*\n${ltv:,.0f}"},
                    {"type": "mrkdwn", "text": f"*Orders:*\n{orders}"},
                    {"type": "mrkdwn", "text": f"*Category:*\n{answer.get('churn_category', 'N/A')}"}
                ]}
            ]
            return {"text": f"Customer {customer_id}: {churn_risk:.0%} churn risk", "blocks": blocks}

        elif query_type == "customer_recommendations":
            recommendations = answer.get("recommendations", [])
            churn_risk = answer.get("churn_risk", 0)
            ltv = answer.get("lifetime_value", 0)
            priority = answer.get("priority", "medium")

            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": f"💡 Recommendations for Customer {customer_id}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Priority:*\n{priority.upper()}"},
                    {"type": "mrkdwn", "text": f"*Churn Risk:*\n{churn_risk:.0%}"},
                    {"type": "mrkdwn", "text": f"*LTV:*\n${ltv:,.0f}"}
                ]},
                {"type": "divider"}
            ]

            if recommendations:
                rec_text = "\n".join([f"• {rec}" for rec in recommendations])
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Recommended Actions:*\n{rec_text}"}})
            else:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "No specific recommendations at this time."}})

            return {"text": f"Recommendations for customer {customer_id}", "blocks": blocks}

        else:
            # Generic profile view
            profile = answer.get("profile", {})
            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": f"👤 Customer {customer_id}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*LTV:*\n${profile.get('lifetime_value', 0):,.0f}"},
                    {"type": "mrkdwn", "text": f"*Orders:*\n{profile.get('order_count', 0)}"},
                    {"type": "mrkdwn", "text": f"*Churn Risk:*\n{profile.get('churn_risk', 0):.0%}"},
                    {"type": "mrkdwn", "text": f"*Segment:*\n{profile.get('archetype_id', 'N/A')}"}
                ]}
            ]
            return {"text": f"Customer {customer_id} profile", "blocks": blocks}

    def format_behavior_pattern_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format behavioral pattern analysis response for Slack."""
        answer = data.get("answer", {})
        query_type = data.get("query_type", "behavior_pattern")
        customers = answer.get("customers", [])[:10]

        # Map query types to icons and titles
        icons_titles = {
            "one_time_buyers": ("🔄", "One-Time Buyers"),
            "momentum_analysis": ("🚀", "Customers with Momentum"),
            "declining_engagement": ("📉", "Declining Engagement"),
            "behavior_change": ("⚠️", "Behavior Changes Detected"),
            "purchase_cadence": ("⏰", "Purchase Rhythm Analysis")
        }

        icon, title = icons_titles.get(query_type, ("📊", "Behavioral Analysis"))

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"{icon} {title}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{answer.get('summary', 'Analysis complete')}*"}}
        ]

        if answer.get("recommendation"):
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"💡 *Recommendation:* {answer['recommendation']}"}})

        blocks.append({"type": "divider"})

        # Add customers
        for i, customer in enumerate(customers, 1):
            customer_id = customer.get('customer_id', 'Unknown')
            ltv = customer.get('ltv', 0)
            orders = customer.get('order_count', 0)
            churn = customer.get('churn_risk', 0)

            text = f"*{i}. Customer {customer_id}*\n💰 ${ltv:,.0f} LTV | 📦 {orders} orders | ⚠️ {churn:.0%} churn risk"
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        # Add metrics
        metrics = answer.get("aggregate_metrics", {})
        if metrics:
            blocks.append({"type": "divider"})
            metric_text = "\n".join([f"• {k.replace('_', ' ').title()}: {v:,.0f}" for k, v in metrics.items()])
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Metrics:*\n{metric_text}"}})

        return {"text": f"{title}: {len(customers)} customers", "blocks": blocks}

    def format_recommendations_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format recommendations response for Slack."""
        answer = data.get("answer", {})
        query_type = data.get("query_type", "recommendations")

        # Map query types to icons and titles
        icons_titles = {
            "upsell_recommendations": ("📈", "Upsell Opportunities"),
            "cross_sell_recommendations": ("🔀", "Cross-Sell Opportunities"),
            "expansion_recommendations": ("🎯", "Expansion Targets"),
            "winback_recommendations": ("🔙", "Win-Back Strategy"),
            "retention_action_plan": ("🛡️", "Retention Action Plan"),
            "discount_strategy": ("💸", "Discount Strategy")
        }

        icon, title = icons_titles.get(query_type, ("💡", "Recommendations"))

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"{icon} {title}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{answer.get('summary', 'Recommendations ready')}*"}}
        ]

        if answer.get("recommendation"):
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"💡 {answer['recommendation']}"}})

        # Add suggested actions if present
        suggested_actions = answer.get("suggested_actions", [])
        if suggested_actions:
            blocks.append({"type": "divider"})
            action_text = "\n".join([f"• {action}" for action in suggested_actions])
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Suggested Actions:*\n{action_text}"}})

        # Add customers if present
        customers = answer.get("customers", [])[:10]
        if customers:
            blocks.append({"type": "divider"})
            for i, customer in enumerate(customers, 1):
                customer_id = customer.get('customer_id', 'Unknown')
                ltv = customer.get('ltv', 0)
                orders = customer.get('order_count', 0)
                churn = customer.get('churn_risk', 0)

                text = f"*{i}. Customer {customer_id}*\n💰 ${ltv:,.0f} | 📦 {orders} orders | ⚠️ {churn:.0%} churn"

                # Add customer-specific actions if present
                if 'recommended_actions' in customer:
                    actions = customer['recommended_actions']
                    text += f"\n➡️ {', '.join(actions)}"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        # Add discount strategy details if present
        recommendations = answer.get("recommendations", [])
        if recommendations and isinstance(recommendations, list) and isinstance(recommendations[0], dict):
            blocks.append({"type": "divider"})
            for rec in recommendations:
                text = f"*{rec.get('segment', 'Segment')}*\n"
                text += f"💰 Discount: {rec.get('discount', 'N/A')}\n"
                text += f"💡 {rec.get('rationale', 'N/A')}"
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        # Add impact metrics
        if answer.get("expected_impact"):
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"📊 *Expected Impact:* {answer['expected_impact']}"}})

        return {"text": title, "blocks": blocks}

    def format_product_analysis_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format product/category analysis response for Slack."""
        # Handle both old format (with answer wrapper) and new format (direct)
        if "answer" in data:
            answer = data.get("answer", {})
            query_type = data.get("query_type", "product_analysis")
            categories = answer.get("categories", [])
            timeframe = answer.get("timeframe_months", 12)
        else:
            # New format: direct response from _handle_product_analysis
            answer = data
            query_type = data.get("analysis_type", "product_analysis")
            categories = data.get("categories", [])
            timeframe = data.get("timeframe_months", 12)

        # Determine header based on query type
        headers = {
            "revenue_by_category": "💰 Revenue by Product Category",
            "category_popularity": "📊 Product Category Popularity",
            "category_by_customer_segment": "🎯 Products by Customer Segment",
            "category_value_metrics": "📈 Category Value Metrics",
            "category_trends": "📈 Product Category Trends",
            "category_repurchase_rate": "🔄 Category Repurchase Rates",
            "product_bundles": "🎁 Product Bundles",
            "seasonal_product_performance": "🌟 Seasonal Product Performance",
            "individual_product_performance": "🏆 Top Products"
        }
        header = headers.get(query_type, "🛍️ Product Analysis")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{answer.get('summary', 'Product category analysis')}*"
                }
            },
            {"type": "divider"}
        ]

        # Add segment context if present
        if answer.get("segment"):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🎯 *Analyzing: {answer['segment']} customers* ({answer.get('customers_analyzed', 0):,} customers)"
                }
            })
            blocks.append({"type": "divider"})

        # Format categories based on query type
        if query_type == "revenue_by_category":
            for i, cat in enumerate(categories, 1):
                text = f"*{i}. {cat.get('category', 'Unknown').replace('_', ' ').title()}*\n"
                text += f"💰 Revenue: ${cat.get('total_revenue', 0):,.0f}\n"
                # Handle both customer_count (old) and unique_customers (new)
                customers = cat.get('unique_customers', cat.get('customer_count', 0))
                text += f"👥 {customers:,} customers | "
                text += f"📦 {cat.get('total_orders', 0):,} orders\n"
                text += f"💵 Avg Order: ${cat.get('avg_order_value', 0):,.2f}"

                # Add units sold if available (new format)
                units = cat.get('units_sold', 0)
                if units > 0:
                    text += f" | 📊 {units:,} units"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

            # Add totals
            if answer.get("total_revenue"):
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Total Revenue:*\n${answer.get('total_revenue', 0):,.0f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Top Category:*\n{answer.get('top_category', 'N/A').replace('_', ' ').title()}"
                        }
                    ]
                })

        elif query_type == "category_popularity":
            for i, cat in enumerate(categories, 1):
                text = f"*{i}. {cat.get('category', 'Unknown').replace('_', ' ').title()}*\n"
                text += f"👥 {cat.get('customer_count', 0):,} customers ({cat.get('percentage', 0):.1f}%)"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

            if answer.get("total_customers"):
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Total Customers:* {answer.get('total_customers', 0):,}\n*Most Popular:* {answer.get('most_popular', 'N/A').replace('_', ' ').title()}"
                    }
                })

        elif query_type == "category_by_customer_segment":
            for i, cat in enumerate(categories, 1):
                text = f"*{i}. {cat.get('category', 'Unknown').replace('_', ' ').title()}*\n"
                text += f"👥 {cat.get('customer_count', 0):,} customers | "
                text += f"💰 ${cat.get('total_revenue', 0):,.0f}"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        elif query_type == "category_value_metrics":
            for i, cat in enumerate(categories, 1):
                text = f"*{i}. {cat.get('category', 'Unknown').replace('_', ' ').title()}*\n"
                text += f"💰 Avg Spend: ${cat.get('avg_customer_spend', 0):,.0f}/customer\n"
                text += f"💵 Avg Order: ${cat.get('avg_order_value', 0):,.2f} | "
                text += f"📦 {cat.get('avg_orders_per_customer', 0):.1f} orders/customer\n"
                text += f"👥 {cat.get('customer_count', 0):,} customers"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        elif query_type == "category_trends":
            for i, cat in enumerate(categories, 1):
                growth = cat.get('revenue_growth_pct', 0)
                trend_emoji = "📈" if growth > 10 else ("📉" if growth < -10 else "➡️")
                text = f"*{i}. {cat.get('category', 'Unknown').replace('_', ' ').title()}* {trend_emoji}\n"
                text += f"Growth: {growth:+.1f}% | Trend: {cat.get('trend', 'stable').title()}\n"
                text += f"Current: ${cat.get('current_revenue', 0):,.0f} | Previous: ${cat.get('previous_revenue', 0):,.0f}"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        elif query_type == "category_repurchase_rate":
            for i, cat in enumerate(categories, 1):
                rate = cat.get('repurchase_rate_pct', 0)
                text = f"*{i}. {cat.get('category', 'Unknown').replace('_', ' ').title()}*\n"
                text += f"🔄 Repurchase Rate: {rate:.1f}%\n"
                text += f"👥 {cat.get('repeat_customers', 0):,} repeat / {cat.get('total_customers', 0):,} total\n"
                text += f"📊 Avg: {cat.get('avg_purchases_per_customer', 0):.1f} purchases/customer"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        elif query_type == "product_bundles":
            bundles = answer.get("bundles", [])
            for i, bundle in enumerate(bundles, 1):
                text = f"*{i}. {bundle.get('category_1', '')} + {bundle.get('category_2', '')}*\n"
                text += f"📦 {bundle.get('orders_together', 0):,} orders together\n"
                text += f"📊 Appears in {bundle.get('bundle_frequency_pct', 0):.1f}% of all orders"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        elif query_type == "seasonal_product_performance":
            for i, cat in enumerate(categories, 1):
                text = f"*{i}. {cat.get('category', 'Unknown').replace('_', ' ').title()}*\n"
                text += f"🌟 Peak Month: {cat.get('peak_month', 'Unknown')} (${cat.get('peak_revenue', 0):,.0f})\n"
                text += f"💰 Total Revenue: ${cat.get('total_revenue', 0):,.0f}"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        elif query_type == "individual_product_performance":
            products = answer.get("products", [])
            for i, prod in enumerate(products, 1):
                text = f"*{i}. {prod.get('product_name', 'Unknown')[:80]}*\n"
                text += f"💰 Revenue: ${prod.get('total_revenue', 0):,.0f} | "
                text += f"📦 {prod.get('units_sold', 0):,} units\n"
                text += f"👥 {prod.get('customer_count', 0):,} customers | "
                text += f"Category: {prod.get('category', 'N/A')}"

                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

        # Add insights if present
        insights = answer.get("insights", [])
        if insights:
            blocks.append({"type": "divider"})
            insight_text = "\n".join([f"💡 {insight}" for insight in insights])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Key Insights:*\n{insight_text}"
                }
            })

        return {"text": f"Product analysis: {answer.get('summary', 'Analysis complete')}", "blocks": blocks}

    def format_error(self, error_message: str) -> Dict[str, Any]:
        """Format error message for Slack"""
        return {
            "text": f"❌ Error: {error_message}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *Error:* {error_message}"
                    }
                }
            ]
        }
