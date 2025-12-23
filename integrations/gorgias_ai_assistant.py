"""
Gorgias AI Assistant Integration

Receives Gorgias ticket webhooks, enriches with customer analytics,
and generates AI-powered draft replies using customer context.

Workflow:
1. Gorgias webhook → New/updated ticket
2. Extract customer identifier (email, Shopify ID, etc.)
3. Query analytics API for customer insights
4. Generate personalized draft reply using Claude Haiku
5. Post draft reply back to Gorgias ticket
"""
import logging
import os
import hmac
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
import anthropic

logger = logging.getLogger(__name__)


class GorgiasAIAssistant:
    """
    AI-powered customer support assistant for Gorgias.

    Integrates customer analytics with AI response generation to help
    CS agents respond more effectively based on customer value and behavior.
    """

    def __init__(
        self,
        gorgias_domain: str,
        gorgias_username: str,
        gorgias_api_key: str,
        analytics_api_url: str,
        anthropic_api_key: Optional[str] = None,
        analytics_api_key: Optional[str] = None
    ):
        """
        Initialize Gorgias AI Assistant.

        Args:
            gorgias_domain: Gorgias domain (e.g., "yourcompany")
            gorgias_username: Gorgias account email
            gorgias_api_key: Gorgias API key
            analytics_api_url: URL of customer analytics API
            anthropic_api_key: Claude API key (or from env)
            analytics_api_key: API key for analytics endpoints (or from env ADMIN_KEY)
        """
        self.gorgias_base_url = f"https://{gorgias_domain}.gorgias.com/api"
        self.gorgias_auth = (gorgias_username, gorgias_api_key)
        self.analytics_api_url = analytics_api_url
        self.analytics_api_key = analytics_api_key or os.getenv("ADMIN_KEY")

        self.anthropic_client = anthropic.Anthropic(
            api_key=anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        )

        self.http_client = httpx.AsyncClient(timeout=30.0)

    def validate_webhook_signature(
        self,
        payload: bytes,
        signature_header: Optional[str]
    ) -> bool:
        """
        Validate Gorgias webhook signature using HMAC-SHA256.

        Gorgias sends signature in header: X-Gorgias-Signature
        Format: sha256=<hex_digest>

        Args:
            payload: Raw request body bytes
            signature_header: Value of X-Gorgias-Signature header

        Returns:
            True if signature valid, False otherwise
        """
        if not signature_header:
            logger.error("Missing X-Gorgias-Signature header")
            return False

        # Get webhook secret from environment
        webhook_secret = os.getenv("GORGIAS_WEBHOOK_SECRET")
        if not webhook_secret:
            logger.error("GORGIAS_WEBHOOK_SECRET not configured")
            return False

        # Parse signature header
        # Expected format: "sha256=abc123..."
        try:
            algorithm, signature = signature_header.split("=", 1)
            if algorithm != "sha256":
                logger.error(f"Unsupported signature algorithm: {algorithm}")
                return False
        except ValueError:
            logger.error(f"Invalid signature header format: {signature_header}")
            return False

        # Compute expected signature
        expected_signature = hmac.new(
            key=webhook_secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(signature, expected_signature)

        if not is_valid:
            logger.warning(
                f"Invalid webhook signature. "
                f"Expected: {expected_signature[:10]}..., "
                f"Got: {signature[:10]}..."
            )

        return is_valid

    async def handle_ticket_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming Gorgias ticket webhook.

        Args:
            webhook_data: Webhook payload from Gorgias

        Returns:
            Status of processing
        """
        try:
            # Normalize webhook format - Gorgias sends two different formats:
            # Format 1 (Ticket created): { "id": 123, "customer": {...}, "messages": [...] }
            # Format 2 (Message created): { "message": {...}, "ticket": {...} }
            if "ticket" in webhook_data and "message" in webhook_data:
                # Format 2: Extract ticket data and append new message
                ticket_data = webhook_data["ticket"]
                new_message = webhook_data["message"]

                # Use ticket data as the main webhook data
                ticket_id = ticket_data.get("id")
                customer_data = ticket_data.get("customer", {})

                # Get existing messages from ticket and append the new one
                messages = ticket_data.get("messages", [])
                if new_message:
                    messages.append(new_message)

                # Use ticket_data for all subsequent operations
                normalized_webhook_data = ticket_data
            else:
                # Format 1: Direct ticket data
                ticket_id = webhook_data.get("id")
                customer_data = webhook_data.get("customer", {})
                messages = webhook_data.get("messages", [])
                normalized_webhook_data = webhook_data

            logger.info(f"Processing Gorgias ticket #{ticket_id}")

            # Skip if no messages yet
            if not messages:
                logger.info(f"Ticket #{ticket_id} has no messages yet, skipping")
                return {"status": "skipped", "reason": "no_messages"}

            # CRITICAL: Skip if latest message is from our bot (prevent infinite loop)
            if messages:
                latest_msg = messages[-1]
                # Check if this is our own internal note
                if latest_msg.get("via") == "api" and latest_msg.get("channel") == "internal-note":
                    logger.info(f"Ticket #{ticket_id}: Latest message is our own internal note, skipping to prevent loop")
                    return {"status": "skipped", "reason": "own_internal_note"}
                # Also check if from_agent=True (message from us)
                if latest_msg.get("from_agent", False):
                    logger.info(f"Ticket #{ticket_id}: Latest message is from agent, skipping")
                    return {"status": "skipped", "reason": "agent_message"}

            # Check if this is an automated/test message that should be skipped
            if self._is_automated_or_test_message(normalized_webhook_data, customer_data):
                logger.info(f"Ticket #{ticket_id} is automated/test message, skipping AI response")
                return {"status": "skipped", "reason": "automated_or_test_message"}

            # Detect ticket source for source-based handling
            ticket_source = self._detect_ticket_source(normalized_webhook_data, customer_data)
            logger.info(f"Ticket #{ticket_id} source detected: {ticket_source}")

            # Get the latest customer message
            logger.info(f"Extracting customer message from {len(messages)} messages")
            customer_message = self._get_latest_customer_message(messages)

            # Special handling for RingCentral calls without transcript:
            # If no message but we have a phone number, we can still provide customer intelligence
            if not customer_message:
                if ticket_source == "ringcentral" and customer_data.get("phone"):
                    logger.info(f"Ticket #{ticket_id} is RingCentral call without transcript, but has phone number - will provide customer intelligence")
                    customer_message = "[Incoming call - no voicemail transcript available]"
                else:
                    logger.info(f"Ticket #{ticket_id} has no customer messages")
                    return {"status": "skipped", "reason": "no_customer_message"}
            logger.info(f"Customer message extracted: {len(customer_message)} chars")

            # Extract customer identifier
            logger.info(f"Extracting customer ID from customer_data: {customer_data}")
            customer_id = await self._extract_customer_id(customer_data)
            if not customer_id:
                logger.warning(f"Could not identify customer for ticket #{ticket_id}")
                return {"status": "skipped", "reason": "no_customer_id"}
            logger.info(f"Customer ID: {customer_id}")

            # Get customer analytics - ALWAYS start with Shopify data from webhook
            logger.info(f"Extracting Shopify data from webhook for customer {customer_id}")
            shopify_metrics = self._extract_shopify_metrics(customer_data)

            logger.info(f"Fetching behavioral analytics from database for customer {customer_id}")
            behavioral_analytics = await self._get_customer_analytics(customer_id)

            # Merge: Shopify data (PRIMARY) + behavioral data (SUPPLEMENTAL)
            analytics = self._merge_analytics(shopify_metrics, behavioral_analytics, customer_data)
            logger.info(f"Analytics ready: Shopify LTV=${shopify_metrics.get('lifetime_value', 0)}, Orders={shopify_metrics.get('total_orders', 0)}, LCC={analytics.get('is_lcc_member')}")

            # NEW: Detect urgency keywords in customer message
            urgency_data = self._detect_urgency_keywords(customer_message)
            logger.info(f"Urgency detection: {urgency_data['urgency_level']} - {urgency_data.get('category')}")

            # NEW: Calculate ticket priority based on urgency + LCC + customer value
            profile = analytics.get("profile", {})
            business_metrics = profile.get("business_metrics", {})
            ltv = business_metrics.get("lifetime_value", 0)
            churn_risk = analytics.get("churn", {}).get("churn_probability", 0)
            is_lcc_member = analytics.get("is_lcc_member", False)

            priority_data = self._calculate_ticket_priority(
                urgency_data=urgency_data,
                is_lcc_member=is_lcc_member,
                ltv=ltv,
                churn_risk=churn_risk
            )
            logger.info(f"Priority calculated: {priority_data['priority']} - {priority_data['reason']}")

            # NEW: Update Gorgias ticket with priority and tags
            update_result = await self._update_gorgias_ticket(
                ticket_id=ticket_id,
                priority=priority_data["priority"],
                tags_to_add=priority_data["tags_to_add"]
            )
            logger.info(f"Gorgias ticket updated: {update_result.get('success')}")

            # Generate AI-powered draft reply (now includes urgency/priority context)
            draft_reply = await self._generate_draft_reply(
                customer_message=customer_message,
                customer_data=customer_data,
                analytics=analytics,
                ticket_context=normalized_webhook_data,
                ticket_source=ticket_source,
                urgency_data=urgency_data,
                priority_data=priority_data
            )

            # Post draft reply to Gorgias
            result = await self._post_draft_reply(ticket_id, draft_reply)

            logger.info(f"Successfully processed ticket #{ticket_id}")
            return {
                "status": "success",
                "ticket_id": ticket_id,
                "customer_id": customer_id,
                "priority": priority_data["priority"],
                "urgency": urgency_data,
                "is_lcc_member": is_lcc_member,
                "draft_reply": draft_reply,  # Include generated content for testing
                "analytics": analytics,  # Include analytics for testing
                "draft_posted": result,
                "ticket_updated": update_result
            }

        except Exception as e:
            logger.error(f"Error processing ticket webhook: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def _extract_customer_id(self, customer_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract customer ID from Gorgias customer object.

        Priority:
        1. external_id (Shopify customer ID)
        2. meta.shopify_customer_id
        3. integrations.shopify.customer.id (from Shopify integration data)
        4. id (Gorgias customer ID)
        5. phone (Shopify API lookup for SMS tickets)
        6. email (as fallback for lookup)

        Args:
            customer_data: Gorgias customer object

        Returns:
            Customer identifier or None
        """
        # Try external_id first (usually Shopify customer ID)
        external_id = customer_data.get("external_id")
        if external_id:
            return str(external_id)

        # Try meta fields (handle None case)
        meta = customer_data.get("meta") or {}
        shopify_id = meta.get("shopify_customer_id")
        if shopify_id:
            return str(shopify_id)

        # Try integrations data - Shopify integration often has customer.id
        integrations = customer_data.get("integrations") or {}
        for integration_id, integration_data in integrations.items():
            if isinstance(integration_data, dict):
                integration_type = integration_data.get("__integration_type__")
                if integration_type == "shopify":
                    # Found Shopify integration - extract customer.id
                    shopify_customer = integration_data.get("customer") or {}
                    shopify_customer_id = shopify_customer.get("id")
                    if shopify_customer_id:
                        logger.info(f"Found Shopify customer ID in integrations: {shopify_customer_id}")
                        return str(shopify_customer_id)

        # Try Gorgias customer ID
        customer_id = customer_data.get("id")
        if customer_id:
            return str(customer_id)

        # NEW: Try phone number lookup for SMS tickets (Klaviyo, etc.)
        phone = customer_data.get("phone")
        if phone:
            logger.info(f"📱 Attempting Shopify lookup by phone number for SMS ticket")
            try:
                from integrations.shopify_customer_lookup import get_shopify_lookup
                shopify_lookup = get_shopify_lookup()

                if shopify_lookup:
                    customer_id = await shopify_lookup.lookup_by_phone(phone)
                    if customer_id:
                        logger.info(f"✅ Found customer via phone lookup: {customer_id}")
                        return customer_id
                    else:
                        logger.warning(f"❌ No customer found for phone number")
                else:
                    logger.warning("⚠️  Shopify lookup not configured (missing SHOPIFY_SHOP_NAME or SHOPIFY_ACCESS_TOKEN)")
            except Exception as e:
                logger.error(f"❌ Error during phone lookup: {e}", exc_info=True)

        # Fallback to email (will need lookup)
        email = customer_data.get("email")
        if email:
            logger.info(f"Using email for customer lookup: {email}")
            return email

        return None

    def _detect_ticket_source(self, webhook_data: Dict[str, Any], customer_data: Dict[str, Any]) -> str:
        """
        Detect the source/channel of the ticket for source-based handling.

        Returns one of:
        - "ringcentral" - RingCentral voicemail/call
        - "sms" - SMS/text message
        - "email" - Regular email
        - "chat" - Live chat
        - "phone" - Phone call (non-RingCentral)
        - "api" - API-generated (agent-forwarded)
        - "unknown" - Cannot determine

        Args:
            webhook_data: Full ticket webhook data
            customer_data: Customer information

        Returns:
            Source type string
        """
        via = webhook_data.get("via", "").lower()
        channel = webhook_data.get("channel", "").lower()
        subject = webhook_data.get("subject", "").lower()
        customer_email = customer_data.get("email", "").lower()

        # Check for RingCentral
        if "ringcentral" in customer_email or "ringcentral" in subject:
            return "ringcentral"

        # Check for SMS
        if channel == "sms" or via == "sms":
            return "sms"
        if "text message" in subject or "sms" in subject:
            return "sms"

        # Check for chat
        if channel == "chat" or via in ["chat", "gorgias_chat"]:
            return "chat"

        # Check for phone
        if channel == "voice" or via == "voice":
            return "phone"

        # Check for API (agent-forwarded)
        if via == "api":
            return "api"

        # Check for email
        if channel == "email" or via == "email":
            return "email"

        return "unknown"

    def _is_automated_or_test_message(self, webhook_data: Dict[str, Any], customer_data: Dict[str, Any]) -> bool:
        """
        Check if ticket is an automated/test message that should not receive AI response.

        Conservative filter to avoid responding to:
        - System notifications (Klaviyo, Mailchimp, etc.)
        - No-reply addresses
        - SMS forwarding notifications (metadata, not actual SMS)
        - Internal test messages

        Args:
            webhook_data: Full ticket webhook data
            customer_data: Customer information

        Returns:
            True if message should be skipped, False if it should be processed
        """
        # NEW: Check tags FIRST for manual override
        tags = webhook_data.get("tags", [])
        tag_names = [tag.get("name", "").lower() if isinstance(tag, dict) else str(tag).lower() for tag in tags]

        # Manual override: Force skip AI
        if "ai_ignore" in tag_names or "no-ai" in tag_names or "human-only" in tag_names:
            logger.info(f"Skipping: ticket tagged with AI ignore flag")
            return True

        # Manual override: Force process (even if automated)
        if "ai_force" in tag_names or "force-ai" in tag_names:
            logger.info(f"Force processing: ticket tagged with AI force flag")
            return False

        # NEW: Check status - skip closed/spam tickets
        status = webhook_data.get("status", "").lower()
        if status in ["closed", "spam", "deleted"]:
            logger.info(f"Skipping: ticket status is '{status}'")
            return True

        subject = webhook_data.get("subject", "").lower()
        customer_email = customer_data.get("email", "").lower()
        customer_name = customer_data.get("name", "").lower()
        via = webhook_data.get("via", "").lower()
        channel = webhook_data.get("channel", "").lower()

        # IMPORTANT: Check if this is an SMS message FIRST
        # SMS messages forwarded through Klaviyo should be processed (they're real customer messages)
        # Only block Klaviyo's own system emails
        is_sms = channel == "sms" or via == "sms" or "sms" in subject
        if is_sms:
            logger.info(f"Detected SMS message - will process even if from automation platform")

        # Special handling for RingCentral BEFORE no-reply filter:
        # - Allow if it has voicemail transcript content
        # - ALSO allow if it has a phone number (we can look up the customer even without transcript)
        # - Block only if it's an empty notification with no phone
        if "ringcentral.com" in customer_email:
            # Check if there's actual message content (voicemail transcript)
            messages = webhook_data.get("messages", [])
            has_content = False
            for msg in messages:
                body = msg.get("body_html") or msg.get("body_text") or ""
                # Voicemail transcripts typically have substantial content
                if len(body.strip()) > 50:  # More than just "New voicemail"
                    has_content = True
                    break

            # Check if customer data has a phone number we can use for lookup
            has_phone = bool(customer_data.get("phone"))

            if not has_content and not has_phone:
                logger.info(f"Skipping: RingCentral notification with no content and no phone number")
                return True
            elif has_content:
                logger.info(f"Processing: RingCentral voicemail with transcript content")
            else:
                logger.info(f"Processing: RingCentral call with phone number (no transcript)")
            # Allow RingCentral to proceed - don't apply other filters
            return False

        # Filter 1: No-reply email addresses (system notifications)
        # NOTE: Placed AFTER RingCentral check so RingCentral can use phone lookup
        if "no-reply" in customer_email or "noreply" in customer_email:
            logger.info(f"Skipping: no-reply email address ({customer_email})")
            return True

        # Filter 2: Known marketing/automation platforms
        # NOTE: Skip this filter for SMS messages (they're forwarded through platforms like Klaviyo)
        # NOTE: RingCentral already handled above
        if not is_sms:  # Only block automation platforms for emails, not SMS
            automation_platforms = [
                "klaviyo.com",
                "mailchimp.com",
                "sendgrid.net",
                "constantcontact.com",
                "activecampaign.com"
            ]
            for platform in automation_platforms:
                if platform in customer_email:
                    logger.info(f"Skipping: automated platform email ({platform})")
                    return True

        # Filter 3: SMS forwarding NOTIFICATIONS (not actual SMS messages)
        # These are metadata notifications about SMS, not the SMS content itself
        sms_notification_patterns = [
            "new sms to",
            "sms notification",
            "text message notification"
        ]
        for pattern in sms_notification_patterns:
            if pattern in subject:
                logger.info(f"Skipping: SMS notification metadata ({pattern})")
                return True

        # Filter 4: Customer name suggests automation (conservative - "Team" suffix)
        # This catches "The Klaviyo Team", "Support Team", etc.
        # NOTE: Skip this filter for SMS messages (customer might have "team" in their name)
        if not is_sms:
            if customer_name.endswith(" team") or customer_name.startswith("the ") and "team" in customer_name:
                logger.info(f"Skipping: automated sender name ({customer_name})")
                return True

        # NEW: Check via field for pure API automation (but allow agent-forwarded)
        if via == "api":
            # Check if this is an agent-forwarded message (legitimate)
            messages = webhook_data.get("messages", [])
            if messages and not any(msg.get("created_by_agent") for msg in messages):
                logger.info(f"Skipping: pure API automation (not agent-forwarded)")
                return True

        # If none of the filters matched, this appears to be a real customer message
        return False

    def _get_latest_customer_message(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Get the most recent customer message from ticket.

        Args:
            messages: List of ticket messages

        Returns:
            Message text or None
        """
        # Filter for customer messages (not notes, not pure automation, not outgoing)
        customer_messages = []

        for msg in messages:
            # Skip internal notes
            if msg.get("is_note", False):
                continue

            # Skip outgoing agent/system messages (from_agent=true means FROM us TO customer)
            if msg.get("from_agent", False):
                continue

            # Check if API message is legitimate (agent-forwarded)
            source_type = msg.get("source", {}).get("type")
            if source_type == "api":
                # Allow if created by agent (forwarded customer issue)
                if msg.get("created_by_agent"):
                    customer_messages.append(msg)
                continue

            # Include all other messages
            customer_messages.append(msg)

        if not customer_messages:
            return None

        # Find latest message with content (check all, not just last)
        for msg in reversed(customer_messages):  # Start from most recent
            # Try body_text first, fallback to body_html
            body_text = msg.get("body_text")
            if not body_text:
                body_text = msg.get("body_html")

            # If has content, return it
            if body_text and body_text.strip():
                return body_text.strip()

        return None

    async def _get_customer_analytics(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch customer analytics from our API.

        Args:
            customer_id: Customer identifier

        Returns:
            Analytics data or None
        """
        try:
            # Prepare headers with API key
            headers = {}
            if self.analytics_api_key:
                headers["X-API-Key"] = self.analytics_api_key

            # Try to get customer profile
            response = await self.http_client.get(
                f"{self.analytics_api_url}/api/mcp/customer/{customer_id}",
                headers=headers
            )

            if response.status_code == 404:
                logger.warning(f"Customer {customer_id} not found in analytics")
                return None

            response.raise_for_status()
            profile = response.json()

            # Get churn risk
            churn_response = await self.http_client.get(
                f"{self.analytics_api_url}/api/mcp/customer/{customer_id}/churn-risk",
                headers=headers
            )
            churn_data = churn_response.json() if churn_response.status_code == 200 else {}

            # Combine data
            return {
                "customer_id": customer_id,
                "profile": profile,
                "churn": churn_data,
                "fetched_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error fetching analytics for {customer_id}: {e}")
            return None

    def _extract_shopify_tags(self, customer_data: Dict[str, Any]) -> List[str]:
        """
        Extract customer tags from Shopify integration data in Gorgias webhook.

        Shopify customer tags are used for VIP status, membership programs, etc.

        Args:
            customer_data: Gorgias customer object from webhook

        Returns:
            List of tag strings (e.g., ["LCC_Member", "VIP", "Wholesale"])
        """
        tags = []

        # Extract from integrations
        integrations = customer_data.get("integrations") or {}
        for integration_id, integration_data in integrations.items():
            if isinstance(integration_data, dict):
                if integration_data.get("__integration_type__") == "shopify":
                    shopify_customer = integration_data.get("customer") or {}

                    # Shopify tags come as comma-separated string
                    tags_str = shopify_customer.get("tags", "")
                    if tags_str:
                        # Parse comma-separated tags and clean whitespace
                        tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
                        logger.info(f"Extracted Shopify customer tags: {tags}")
                        return tags

        return tags

    def _detect_lcc_membership(self, shopify_tags: List[str]) -> bool:
        """
        Detect if customer is a Linda's Crafter Club member.

        Args:
            shopify_tags: List of Shopify customer tags

        Returns:
            True if LCC_Member tag found
        """
        # Check for LCC_Member tag (case-insensitive)
        lcc_tags = ["LCC_Member", "lcc_member", "LCC Member", "Crafter Club"]
        for tag in shopify_tags:
            if tag in lcc_tags or "lcc" in tag.lower():
                logger.info(f"LCC membership detected: {tag}")
                return True
        return False

    def _extract_shopify_metrics(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract transactional metrics from Shopify integration data in Gorgias webhook.

        This is the PRIMARY source for:
        - Lifetime value (total_spent)
        - Order count
        - Order history
        - Tracking information
        - Customer creation date
        - Customer tags (LCC_Member, VIP, etc.)

        Args:
            customer_data: Gorgias customer object from webhook

        Returns:
            Dict with Shopify metrics
        """
        shopify_metrics = {
            "lifetime_value": 0.0,
            "total_orders": 0,
            "avg_order_value": 0.0,
            "customer_tenure_days": 0,
            "phone": customer_data.get("phone"),
            "email": customer_data.get("email"),
            "recent_orders": [],
            "shopify_tags": [],
            "is_lcc_member": False,
            "has_shopify_data": False
        }

        # Extract from integrations
        integrations = customer_data.get("integrations") or {}
        for integration_id, integration_data in integrations.items():
            if isinstance(integration_data, dict):
                if integration_data.get("__integration_type__") == "shopify":
                    shopify_customer = integration_data.get("customer") or {}

                    # Extract LTV
                    try:
                        total_spent = shopify_customer.get("total_spent", "0")
                        shopify_metrics["lifetime_value"] = float(str(total_spent).replace(",", ""))
                    except (ValueError, AttributeError):
                        shopify_metrics["lifetime_value"] = 0.0

                    # Extract order count
                    shopify_metrics["total_orders"] = shopify_customer.get("orders_count", 0)

                    # Calculate avg order value
                    if shopify_metrics["total_orders"] > 0:
                        shopify_metrics["avg_order_value"] = shopify_metrics["lifetime_value"] / shopify_metrics["total_orders"]

                    # Extract customer age
                    created_at = shopify_customer.get("created_at")
                    if created_at:
                        try:
                            from datetime import datetime
                            created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            shopify_metrics["customer_tenure_days"] = (datetime.now(created_date.tzinfo) - created_date).days
                        except:
                            pass

                    # Extract recent orders for tracking info
                    orders = integration_data.get("orders", [])
                    if orders:
                        shopify_metrics["recent_orders"] = orders[:3]  # Most recent 3

                    # Extract customer tags (NEW)
                    tags_str = shopify_customer.get("tags", "")
                    if tags_str:
                        shopify_metrics["shopify_tags"] = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
                        # Detect LCC membership
                        shopify_metrics["is_lcc_member"] = self._detect_lcc_membership(shopify_metrics["shopify_tags"])

                    shopify_metrics["has_shopify_data"] = True
                    logger.info(f"Extracted Shopify metrics: ${shopify_metrics['lifetime_value']:.2f} LTV, {shopify_metrics['total_orders']} orders, LCC={shopify_metrics['is_lcc_member']}")
                    break

        return shopify_metrics

    def _merge_analytics(self, shopify_metrics: Dict[str, Any], behavioral_analytics: Optional[Dict[str, Any]], customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge Shopify data (PRIMARY) with behavioral analytics (SUPPLEMENTAL).

        Shopify provides: LTV, orders, tracking
        Your DB provides: Segmentation, churn risk, behavioral patterns

        Args:
            shopify_metrics: Extracted from Gorgias webhook
            behavioral_analytics: From your analytics database
            customer_data: Original Gorgias customer object

        Returns:
            Merged analytics object
        """
        # Start with Shopify data as foundation
        merged = {
            "customer_id": customer_data.get("id"),
            "name": customer_data.get("name", "Customer"),
            "email": customer_data.get("email"),
            "is_new": shopify_metrics["total_orders"] == 0,
            "is_lcc_member": shopify_metrics.get("is_lcc_member", False),
            "shopify_tags": shopify_metrics.get("shopify_tags", []),
            "profile": {
                "business_metrics": {
                    "lifetime_value": shopify_metrics["lifetime_value"],
                    "total_orders": shopify_metrics["total_orders"],
                    "avg_order_value": shopify_metrics["avg_order_value"],
                    "days_since_last_purchase": 0,  # Unknown without our database
                    "customer_tenure_days": shopify_metrics["customer_tenure_days"]
                },
                "recent_orders": shopify_metrics.get("recent_orders", [])
            },
            "churn": {
                "churn_probability": 0.0,
                "risk_level": "unknown"
            }
        }

        # Enhance with behavioral data if available
        if behavioral_analytics and behavioral_analytics.get("profile"):
            behavior_profile = behavioral_analytics.get("profile", {})
            behavior_metrics = behavior_profile.get("business_metrics", {})

            # Add/override with database metrics where available
            if behavior_metrics.get("days_since_last_purchase"):
                merged["profile"]["business_metrics"]["days_since_last_purchase"] = behavior_metrics["days_since_last_purchase"]

            # Add segmentation data (only from your DB)
            if behavior_profile.get("dominant_segments"):
                merged["profile"]["dominant_segments"] = behavior_profile["dominant_segments"]

            if behavior_profile.get("archetype"):
                merged["profile"]["archetype"] = behavior_profile["archetype"]

            # Add churn risk (only from your DB)
            if behavioral_analytics.get("churn"):
                merged["churn"] = behavioral_analytics["churn"]

            logger.info(f"Enhanced with behavioral analytics: segments={bool(behavior_profile.get('dominant_segments'))}, churn={merged['churn'].get('risk_level')}")

        return merged

    def _create_default_analytics(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create analytics from Shopify data in Gorgias webhook when customer not in our database.

        Falls back to Shopify integration data from Gorgias for basic metrics (LTV, orders, etc.)
        Segmentation data won't be available but transactional data will be.
        """
        # Try to extract Shopify data from integrations
        shopify_data = {}
        integrations = customer_data.get("integrations") or {}
        for integration_id, integration_data in integrations.items():
            if isinstance(integration_data, dict):
                if integration_data.get("__integration_type__") == "shopify":
                    shopify_customer = integration_data.get("customer") or {}
                    shopify_data = {
                        "total_spent": shopify_customer.get("total_spent", "0"),
                        "orders_count": shopify_customer.get("orders_count", 0),
                        "phone": shopify_customer.get("phone"),
                        "email": shopify_customer.get("email"),
                        "created_at": shopify_customer.get("created_at")
                    }
                    logger.info(f"Extracted Shopify data from webhook: {shopify_data['orders_count']} orders, ${shopify_data['total_spent']} LTV")
                    break

        # Convert total_spent to float
        try:
            ltv = float(shopify_data.get("total_spent", "0").replace(",", ""))
        except (ValueError, AttributeError):
            ltv = 0.0

        orders_count = shopify_data.get("orders_count", 0)
        avg_order_value = ltv / orders_count if orders_count > 0 else 0.0

        # Calculate days since account creation
        days_since_created = 0
        created_at = shopify_data.get("created_at")
        if created_at:
            try:
                from datetime import datetime
                created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                days_since_created = (datetime.now(created_date.tzinfo) - created_date).days
            except:
                pass

        return {
            "customer_id": customer_data.get("id"),
            "name": customer_data.get("name", "Customer"),
            "email": customer_data.get("email"),
            "is_new": orders_count == 0,  # Only truly new if no orders
            "profile": {
                "business_metrics": {
                    "lifetime_value": ltv,
                    "total_orders": orders_count,
                    "avg_order_value": avg_order_value,
                    "days_since_last_purchase": 0,  # Unknown without our database
                    "customer_tenure_days": days_since_created
                }
            },
            "churn": {
                "churn_probability": 0.0,  # Unknown without our behavioral model
                "risk_level": "unknown"
            }
        }

    async def _generate_draft_reply(
        self,
        customer_message: str,
        customer_data: Dict[str, Any],
        analytics: Dict[str, Any],
        ticket_context: Dict[str, Any],
        ticket_source: str = "unknown",
        urgency_data: Optional[Dict[str, Any]] = None,
        priority_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate AI-powered draft reply using Claude Haiku.

        Args:
            customer_message: Customer's message/question
            customer_data: Gorgias customer object
            analytics: Customer analytics from our system
            ticket_context: Full ticket context
            ticket_source: Source of ticket (ringcentral, sms, email, chat, etc.)

        Returns:
            Draft reply text
        """
        # Build analytics summary for internal context (now includes urgency/priority)
        analytics_summary = self._build_analytics_summary(
            analytics,
            ticket_source,
            urgency_data=urgency_data,
            priority_data=priority_data
        )

        # Build prompt for Claude
        prompt = self._build_response_prompt(
            customer_message=customer_message,
            customer_name=customer_data.get("name", "there"),
            analytics_summary=analytics_summary,
            ticket_context=ticket_context,
            ticket_source=ticket_source
        )

        try:
            # Use Claude 3.5 Haiku (cheapest, fast)
            response = self.anthropic_client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=600,  # Reduced from 1024 to encourage concise responses
                temperature=0.7,  # Slightly creative but professional
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            draft_reply = response.content[0].text

            # Add analytics context as internal note format
            full_response = f"{analytics_summary}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{draft_reply}"

            return full_response

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            # Fallback to simple template
            return self._generate_fallback_response(customer_message, customer_data)

    def _build_analytics_summary(
        self,
        analytics: Dict[str, Any],
        ticket_source: str = "unknown",
        urgency_data: Optional[Dict[str, Any]] = None,
        priority_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build customer analytics summary for CS agent.

        Shows normalized metrics and actionable insights, including:
        - LCC membership status
        - Urgency flags from keywords
        - Calculated priority

        Args:
            analytics: Customer analytics data
            ticket_source: Source of the ticket (email, sms, etc.)
            urgency_data: Result from _detect_urgency_keywords (optional)
            priority_data: Result from _calculate_ticket_priority (optional)
        """
        profile = analytics.get("profile", {})
        churn = analytics.get("churn", {})

        # Map source to emoji/label
        source_labels = {
            "ringcentral": "📞 RingCentral",
            "sms": "💬 SMS/Text",
            "email": "📧 Email",
            "chat": "💭 Live Chat",
            "phone": "☎️ Phone",
            "api": "🔄 Agent-Forwarded",
            "unknown": "❓ Unknown Source"
        }
        source_label = source_labels.get(ticket_source, "❓ Unknown Source")

        # Check if LCC member
        is_lcc_member = analytics.get("is_lcc_member", False)

        if analytics.get("is_new"):
            new_customer_msg = f"📊 CUSTOMER INSIGHTS: New customer - no purchase history available\n📥 Source: {source_label}"
            if is_lcc_member:
                new_customer_msg += "\n✨ VIP: Linda's Crafter Club Member (NEW)"
            return new_customer_msg

        # Extract key metrics from business_metrics if available
        business_metrics = profile.get("business_metrics", {})
        ltv = business_metrics.get("lifetime_value", profile.get("lifetime_value", 0))
        total_orders = business_metrics.get("total_orders", profile.get("total_orders", 0))
        avg_order_value = business_metrics.get("avg_order_value", profile.get("avg_order_value", 0))
        days_since_last = business_metrics.get("days_since_last_purchase", profile.get("days_since_last_purchase", 0))
        churn_risk = churn.get("churn_probability", 0)

        # Normalize and categorize
        ltv_category = self._categorize_ltv(ltv)
        churn_category = self._categorize_churn_risk(churn_risk)
        engagement_status = self._categorize_engagement(days_since_last, total_orders)

        # Build summary
        summary_lines = [
            "📊 CUSTOMER INSIGHTS (Internal - Do Not Share)",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        # Add priority flag at the top if urgent/high
        if priority_data:
            priority = priority_data.get("priority")
            reason = priority_data.get("reason")
            if priority == "urgent":
                summary_lines.append(f"🚨 PRIORITY: URGENT - {reason}")
            elif priority == "high":
                summary_lines.append(f"⚡ PRIORITY: HIGH - {reason}")

        # Add LCC membership flag prominently
        if is_lcc_member:
            summary_lines.append("✨ VIP: Linda's Crafter Club Member")

        # Add urgency detection if present
        if urgency_data and urgency_data.get("urgency_level") != "normal":
            urgency_level = urgency_data.get("urgency_level").upper()
            matched_keywords = urgency_data.get("matched_keywords", [])
            if matched_keywords:
                summary_lines.append(f"⚠️  URGENCY: {urgency_level} - Detected: {', '.join(matched_keywords[:2])}")

        summary_lines.extend([
            f"📥 Source: {source_label}",
            f"💰 Lifetime Value: ${ltv:,.0f} ({ltv_category})",
            f"⚠️  Churn Risk: {churn_risk*100:.0f}% ({churn_category})",
            f"📈 Historical: {total_orders:.0f} orders, ${avg_order_value:.0f} avg order",
            f"📅 Last Purchase: {days_since_last:.0f} days ago ({engagement_status})",
        ])

        # Add archetype insights if available
        archetype_insight = self._extract_archetype_insight(profile)
        if archetype_insight:
            summary_lines.append(f"🎯 Pattern: {archetype_insight}")

        # Add retention recommendation
        recommendation = self._get_retention_recommendation(ltv, churn_risk, ltv_category, churn_category)
        if recommendation:
            summary_lines.append(f"\n{recommendation}")

        return "\n".join(summary_lines)

    def _categorize_ltv(self, ltv: float) -> str:
        """Categorize LTV into tiers."""
        if ltv >= 5000:
            return "VIP - Top Tier"
        elif ltv >= 2000:
            return "High Value"
        elif ltv >= 500:
            return "Mid Value"
        elif ltv > 0:
            return "Standard"
        else:
            return "New Customer"

    def _categorize_churn_risk(self, churn_risk: float) -> str:
        """Categorize churn risk."""
        if churn_risk >= 0.7:
            return "CRITICAL - High Risk"
        elif churn_risk >= 0.5:
            return "ELEVATED - Monitor Closely"
        elif churn_risk >= 0.3:
            return "MODERATE - Standard Care"
        else:
            return "LOW - Healthy"

    def _categorize_engagement(self, days_since_last: float, total_orders: float) -> str:
        """Categorize customer engagement status."""
        if total_orders == 0:
            return "No purchases yet"
        elif days_since_last <= 30:
            return "Active"
        elif days_since_last <= 60:
            return "Recently Active"
        elif days_since_last <= 90:
            return "Cooling Down"
        else:
            return "At Risk of Lapse"

    def _extract_archetype_insight(self, profile: Dict[str, Any]) -> Optional[str]:
        """Extract behavioral pattern insight without mentioning archetype name."""
        # This would ideally come from archetype analysis
        # For now, derive from profile metrics

        business_metrics = profile.get("business_metrics", {})
        total_orders = business_metrics.get("total_orders", profile.get("total_orders", 0))
        avg_days_between = business_metrics.get("avg_days_between_purchases", profile.get("avg_days_between_purchases", 999))

        if total_orders >= 10:
            if avg_days_between < 30:
                return "Frequent, regular buyer - highly engaged"
            elif avg_days_between < 90:
                return "Seasonal buyer - shops during key periods"
            else:
                return "Occasional buyer - large gaps between purchases"
        elif total_orders >= 3:
            return "Building relationship - still exploring products"
        elif total_orders > 0:
            return "Recent first-time buyer"

        return None

    def _get_retention_recommendation(
        self,
        ltv: float,
        churn_risk: float,
        ltv_category: str,
        churn_category: str
    ) -> Optional[str]:
        """
        Get retention strategy recommendation based on value and risk.

        This tells the CS agent HOW MUCH to invest in retention.
        """
        # High value + high risk = maximum intervention
        if ltv >= 2000 and churn_risk >= 0.7:
            return "⚠️ RETENTION PRIORITY: High-value customer at critical churn risk! Consider expedited solutions, generous compensation, or VIP treatment."

        # High value + moderate risk = proactive care
        elif ltv >= 2000 and churn_risk >= 0.5:
            return "💡 RETENTION STRATEGY: Valuable customer showing early churn signals. Prioritize quick resolution and consider retention offer."

        # High risk + any value = prevent churn
        elif churn_risk >= 0.7:
            return "⚠️ RETENTION ALERT: Customer at risk of churning. Aim for exceptional service and quick resolution."

        # Low risk, high value = maintain relationship
        elif ltv >= 2000:
            return "✨ VIP CUSTOMER: High lifetime value with healthy engagement. Maintain excellent service quality."

        return None

    def _build_response_prompt(
        self,
        customer_message: str,
        customer_name: str,
        analytics_summary: str,
        ticket_context: Dict[str, Any],
        ticket_source: str = "unknown"
    ) -> str:
        """Build prompt for Claude to generate response."""

        # Detect ticket category
        category = self._detect_ticket_category(customer_message)

        # Source-specific instructions
        source_instructions = {
            "ringcentral": "This is a RingCentral voicemail/call. Customer may not be at computer, so keep response actionable and mention you'll follow up.",
            "sms": "This is an SMS/text message. Keep response EXTRA concise (2-3 sentences max). Use casual but professional tone.",
            "chat": "This is a live chat message. Keep response conversational and quick. Customer expects immediate, brief responses.",
            "phone": "This is from a phone call. Customer may have explained verbally, so acknowledge and confirm understanding.",
            "api": "This ticket was forwarded by an agent. Customer's original message is included - respond to the customer directly.",
            "email": "This is a standard email. Use standard professional email format.",
            "unknown": ""
        }
        source_note = source_instructions.get(ticket_source, "")

        # Special handling for RingCentral calls without transcript
        if ticket_source == "ringcentral" and "[Incoming call - no voicemail transcript available]" in customer_message:
            source_note = """This is a RingCentral incoming call notification WITHOUT a voicemail transcript.
The customer called but didn't leave a voicemail. Use their customer analytics to:
1. Acknowledge they called and you're following up
2. Proactively address likely concerns based on their recent order history
3. Invite them to share what they needed help with
4. Provide your contact info for them to reach back out"""

        return f"""You are a professional customer service agent for a quilting e-commerce company.
Generate a helpful, empathetic, and professional draft response to the customer's message.

This draft will be reviewed by a CS agent who will make the final decision on discounts, refunds, and special offers.

CUSTOMER ANALYTICS (Use for context, DO NOT share specifics):
{analytics_summary}

CUSTOMER'S MESSAGE:
{customer_message}

TICKET CATEGORY: {category}

{source_note}

INSTRUCTIONS FOR CUSTOMER RESPONSE:
1. Be warm, professional, and empathetic but CONCISE
2. Address their specific concern directly - get to the point quickly
3. If you have purchase history, reference it briefly (e.g., "I see you recently purchased our Holiday Quilt Set")
4. Acknowledge the issue and state how you'll help
5. For high-value customers at churn risk, emphasize commitment to resolution
6. For new customers, be welcoming but brief
7. Explain next steps clearly in 1-2 sentences
8. KEEP RESPONSE CONCISE: 2-3 short paragraphs maximum (4-6 sentences total)
   - SMS/Chat: Even shorter (2-3 sentences max)
   - Email/RingCentral: Standard concise format (4-6 sentences)
9. Use the customer's name: {customer_name}
10. Do NOT mention "churn risk", "LTV", "analytics" or any internal metrics
11. Do NOT use filler phrases like "I want to ensure", "I'd be delighted", "I look forward to"
12. Be direct and helpful - avoid over-explaining or excessive politeness

🚨 CRITICAL - DO NOT HALLUCINATE OR MAKE UP DETAILS:
- DO NOT invent coupon codes, order numbers, tracking numbers, or any specific details
- DO NOT make up specific product names unless mentioned in the customer's message
- DO NOT assume details about what the customer needs - ask if unclear
- If the customer's message is vague (e.g., "I didn't realize there was a code"), acknowledge it and ASK for clarification
- ONLY reference information explicitly stated in the customer's message or analytics
- When uncertain, say "Could you provide more details about..." rather than guessing

CRITICAL - DO NOT MAKE DISCOUNT/REFUND PROMISES:
- DO NOT offer specific discounts (e.g., "15% off", "20% credit")
- DO NOT promise refunds or credits directly
- DO NOT say "I can offer you" or "I'm giving you"
- Instead, say things like:
  * "Let me investigate this and get back to you with a solution"
  * "I'll review your account and options available to resolve this"
  * "We want to make this right for you"
  * "Let me see what I can do to help"

AFTER the customer response, add an "AGENT RECOMMENDATION" section that suggests:
- Whether a discount/credit should be offered (YES/NO and percentage range)
- Why (based on customer value, churn risk, issue severity)
- What action to take (expedite shipping, quality replacement, etc.)

FORMAT:
[Customer Response]

---
AGENT RECOMMENDATION:
• Offer Discount: [YES/NO - if yes, suggest 10-25% range]
• Reasoning: [Why based on LTV, churn risk, issue type]
• Additional Actions: [Expedited shipping, replacement, follow-up, etc.]

RESPONSE TONE:
- Professional but friendly - NOT overly formal
- Empathetic and understanding - but get to the point
- Solution-focused - tell them what you'll do, not how you feel about it
- Direct and clear - avoid flowery language

EXAMPLE GOOD RESPONSE (concise):
"Hi Sarah,

I'm sorry to hear your quilt arrived damaged. I've checked your order and will send a replacement via expedited shipping today.

You should receive tracking within 2 hours. No need to return the damaged item.

Best regards,
Customer Service"

EXAMPLE BAD RESPONSE (too verbose):
"Dear Sarah,

Thank you so much for reaching out to our customer service team today. I want to begin by expressing how truly sorry I am to hear that your beautiful quilt arrived in a damaged condition. I can only imagine how disappointing this must have been for you, especially given the excitement of receiving a new product.

I want to assure you that we take quality very seriously here at our company, and this is certainly not the standard of service we strive to provide to our valued customers like yourself. Rest assured that I am personally committed to making this situation right for you and ensuring you have a positive experience with us moving forward.

After reviewing your account, I can see that you are a valued customer, and I want to make sure we resolve this issue to your complete satisfaction. I will be processing a replacement order for you right away, and I'll make sure it ships via our expedited shipping method so you receive it as quickly as possible.

I look forward to resolving this matter for you, and please don't hesitate to reach out if you have any other questions or concerns. We're here to help!

Warmly,
Customer Service Team"

Generate the complete response with both sections (customer response + agent recommendation)."""

    def _detect_urgency_keywords(self, message: str) -> Dict[str, Any]:
        """
        Detect urgency keywords/phrases in customer message.

        Returns urgency level and matched keywords for prioritization.

        Args:
            message: Customer message text

        Returns:
            {
                "urgency_level": "urgent" | "high" | "normal",
                "matched_keywords": ["cancel order", ...],
                "category": "cancel_request" | "address_change" | etc.
            }
        """
        message_lower = message.lower()

        # URGENT patterns - require immediate action
        urgent_patterns = {
            "cancel_request": [
                "cancel my order",
                "cancel order",
                "need to cancel",
                "want to cancel",
                "please cancel"
            ],
            "address_change": [
                "change address",
                "edit address",
                "incorrect address",
                "wrong address",
                "ship to different address",
                "address is wrong",
                "shipped to wrong address"
            ],
            "order_edit": [
                "edit my order",
                "edit order",
                "change my order",
                "modify my order",
                "wrong item ordered"
            ]
        }

        # Check for urgent patterns
        for category, patterns in urgent_patterns.items():
            matched = [p for p in patterns if p in message_lower]
            if matched:
                return {
                    "urgency_level": "urgent",
                    "matched_keywords": matched,
                    "category": category,
                    "gorgias_tag": f"urgent_{category}"
                }

        # HIGH priority patterns - important but not critical
        high_priority_patterns = {
            "damaged_product": ["broken", "damaged", "defective", "arrived broken"],
            "missing_items": ["missing item", "didn't receive", "item not in box"],
            "delayed_order": ["hasn't arrived", "delayed", "still waiting"]
        }

        for category, patterns in high_priority_patterns.items():
            matched = [p for p in patterns if p in message_lower]
            if matched:
                return {
                    "urgency_level": "high",
                    "matched_keywords": matched,
                    "category": category,
                    "gorgias_tag": f"high_priority_{category}"
                }

        # Default - no urgency detected
        return {
            "urgency_level": "normal",
            "matched_keywords": [],
            "category": "general",
            "gorgias_tag": None
        }

    def _calculate_ticket_priority(
        self,
        urgency_data: Dict[str, Any],
        is_lcc_member: bool,
        ltv: float,
        churn_risk: float
    ) -> Dict[str, Any]:
        """
        Calculate ticket priority based on urgency keywords, LCC membership, and customer value.

        Priority Logic:
        - URGENT: Urgency keywords + (LCC member OR high value customer)
        - URGENT: Urgency keywords alone (cancel, address change, order edit)
        - HIGH: LCC member with any issue
        - HIGH: High-value customer (>$2000) with medium urgency
        - HIGH: High urgency keywords for any customer
        - NORMAL: Everything else

        Args:
            urgency_data: Result from _detect_urgency_keywords
            is_lcc_member: True if customer is LCC member
            ltv: Customer lifetime value
            churn_risk: Churn probability (0.0-1.0)

        Returns:
            {
                "priority": "urgent" | "high" | "normal",
                "reason": "Human-readable explanation",
                "tags_to_add": ["lcc_member", "urgent_cancel", ...]
            }
        """
        urgency_level = urgency_data["urgency_level"]
        tags_to_add = []

        # Add LCC member tag if applicable
        if is_lcc_member:
            tags_to_add.append("lcc_member")
            tags_to_add.append("vip")

        # Add urgency tag if detected
        if urgency_data["gorgias_tag"]:
            tags_to_add.append(urgency_data["gorgias_tag"])

        # Priority calculation
        # URGENT cases
        if urgency_level == "urgent":
            # Urgent keywords detected (cancel, address change, order edit)
            if is_lcc_member:
                return {
                    "priority": "urgent",
                    "reason": f"URGENT VIP: LCC Member - {urgency_data['category'].replace('_', ' ').title()}",
                    "tags_to_add": tags_to_add
                }
            elif ltv >= 2000:
                return {
                    "priority": "urgent",
                    "reason": f"URGENT: High-value customer (${ltv:,.0f} LTV) - {urgency_data['category'].replace('_', ' ').title()}",
                    "tags_to_add": tags_to_add + ["high_value"]
                }
            else:
                return {
                    "priority": "urgent",
                    "reason": f"URGENT: {urgency_data['category'].replace('_', ' ').title()} - {', '.join(urgency_data['matched_keywords'][:2])}",
                    "tags_to_add": tags_to_add
                }

        # HIGH priority cases
        if is_lcc_member:
            # LCC members always get high priority minimum
            return {
                "priority": "high",
                "reason": "VIP: Linda's Crafter Club Member",
                "tags_to_add": tags_to_add
            }

        if urgency_level == "high":
            # High urgency keywords (damaged, missing, delayed)
            return {
                "priority": "high",
                "reason": f"High Priority: {urgency_data['category'].replace('_', ' ').title()}",
                "tags_to_add": tags_to_add
            }

        if ltv >= 2000 and churn_risk >= 0.5:
            # High-value customer at risk
            tags_to_add.append("high_value")
            tags_to_add.append("retention_priority")
            return {
                "priority": "high",
                "reason": f"High Value Customer at Risk: ${ltv:,.0f} LTV, {churn_risk*100:.0f}% churn risk",
                "tags_to_add": tags_to_add
            }

        # NORMAL priority - default
        return {
            "priority": "normal",
            "reason": "Standard priority",
            "tags_to_add": tags_to_add if tags_to_add else []
        }

    def _detect_ticket_category(self, message: str) -> str:
        """Detect ticket category from message content."""
        message_lower = message.lower()

        if any(word in message_lower for word in ["return", "refund", "send back", "not what i expected"]):
            return "Return/Exchange Request"
        elif any(word in message_lower for word in ["broken", "damaged", "defective", "wrong item", "incorrect"]):
            return "Product Issue - Damaged/Wrong Item"
        elif any(word in message_lower for word in ["where is", "tracking", "hasn't arrived", "not received", "delayed"]):
            return "Order Status/Delivery Inquiry"
        elif any(word in message_lower for word in ["how to", "question about", "can you tell me", "wondering"]):
            return "Product Question"
        elif any(word in message_lower for word in ["cancel", "change order", "modify"]):
            return "Order Modification"
        else:
            return "General Inquiry"

    def _generate_fallback_response(
        self,
        customer_message: str,
        customer_data: Dict[str, Any]
    ) -> str:
        """Generate simple fallback response if AI fails."""
        name = customer_data.get("name", "there")

        return f"""Hi {name},

Thank you for reaching out to us! I've received your message and I'm here to help.

I'm looking into your inquiry right now and will get back to you with a detailed response shortly.

In the meantime, if you have any additional information that might help me assist you better, please feel free to share it.

Best regards,
Customer Success Team"""

    async def _update_gorgias_ticket(
        self,
        ticket_id: str,
        priority: Optional[str] = None,
        tags_to_add: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update Gorgias ticket with priority and tags.

        Args:
            ticket_id: Gorgias ticket ID
            priority: Priority level (urgent, high, normal, low)
            tags_to_add: List of tag names to add

        Returns:
            API response
        """
        try:
            update_payload = {}

            # Update priority if specified
            if priority:
                # Map our priority to Gorgias priority values
                # Gorgias uses: urgent, high, normal, low
                priority_mapping = {
                    "urgent": "urgent",
                    "high": "high",
                    "normal": "normal",
                    "low": "low"
                }
                gorgias_priority = priority_mapping.get(priority, "normal")
                update_payload["priority"] = gorgias_priority

            # Add tags if specified
            if tags_to_add:
                # First, get existing tags from ticket
                ticket_response = await self.http_client.get(
                    f"{self.gorgias_base_url}/tickets/{ticket_id}",
                    auth=self.gorgias_auth
                )
                ticket_response.raise_for_status()
                ticket_data = ticket_response.json()

                # Get existing tag IDs
                existing_tags = ticket_data.get("tags", [])
                existing_tag_ids = [tag["id"] if isinstance(tag, dict) else tag for tag in existing_tags]

                # Get all available tags to find IDs for our tag names
                tags_response = await self.http_client.get(
                    f"{self.gorgias_base_url}/tags",
                    auth=self.gorgias_auth
                )
                tags_response.raise_for_status()
                all_tags = tags_response.json().get("data", [])

                # Map tag names to IDs (create if doesn't exist)
                tag_ids_to_add = []
                for tag_name in tags_to_add:
                    # Find existing tag
                    existing_tag = next((t for t in all_tags if t.get("name", "").lower() == tag_name.lower()), None)
                    if existing_tag:
                        tag_ids_to_add.append(existing_tag["id"])
                    else:
                        # Create new tag
                        create_tag_response = await self.http_client.post(
                            f"{self.gorgias_base_url}/tags",
                            json={"name": tag_name},
                            auth=self.gorgias_auth
                        )
                        if create_tag_response.status_code == 201:
                            new_tag = create_tag_response.json()
                            tag_ids_to_add.append(new_tag["id"])
                            logger.info(f"Created new Gorgias tag: {tag_name}")

                # Combine existing and new tags (deduplicate)
                all_tag_ids = list(set(existing_tag_ids + tag_ids_to_add))
                update_payload["tags"] = [{"id": tag_id} for tag_id in all_tag_ids]

            # Update ticket if we have changes
            if update_payload:
                response = await self.http_client.put(
                    f"{self.gorgias_base_url}/tickets/{ticket_id}",
                    json=update_payload,
                    auth=self.gorgias_auth
                )
                response.raise_for_status()

                logger.info(f"Updated Gorgias ticket #{ticket_id}: priority={priority}, tags={tags_to_add}")
                return {
                    "success": True,
                    "updated": update_payload
                }

            return {
                "success": True,
                "updated": {}
            }

        except Exception as e:
            logger.error(f"Error updating Gorgias ticket: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def _post_draft_reply(self, ticket_id: str, draft_text: str) -> Dict[str, Any]:
        """
        Post draft reply to Gorgias ticket as an internal note.

        Args:
            ticket_id: Gorgias ticket ID
            draft_text: Draft reply text

        Returns:
            API response
        """
        try:
            # Internal note format - sender with id=None will be auto-assigned by Gorgias
            message_payload = {
                "channel": "internal-note",
                "sender": {"id": None},
                "body_text": draft_text,
                "via": "api"
            }

            response = await self.http_client.post(
                f"{self.gorgias_base_url}/tickets/{ticket_id}/messages",
                json=message_payload,
                auth=self.gorgias_auth
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Posted draft reply to ticket #{ticket_id}")

            return {
                "success": True,
                "message_id": result.get("id")
            }

        except Exception as e:
            logger.error(f"Error posting draft reply: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def close(self):
        """Clean up resources."""
        await self.http_client.aclose()
