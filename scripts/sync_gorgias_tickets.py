#!/usr/bin/env python3
"""
Gorgias Ticket Sync Script
Purpose: Import all historical tickets from Gorgias into support_app.tickets
Date: 2025-12-17

This script fetches all tickets from Gorgias API and imports them into the
PostgreSQL database for use with Knowledge Base and Predictive Analytics.

Usage:
    # Dry run (preview only)
    python3 sync_gorgias_tickets.py --dry-run

    # Import all tickets
    python3 sync_gorgias_tickets.py

    # Import tickets from specific date range
    python3 sync_gorgias_tickets.py --start-date 2024-01-01 --end-date 2024-12-31

Environment Variables Required:
    GORGIAS_DOMAIN - Gorgias subdomain (e.g., "lindas")
    GORGIAS_USERNAME - Gorgias account email
    GORGIAS_API_KEY - Gorgias API key (base64 encoded)
    DATABASE_URL - PostgreSQL connection string
"""

import os
import sys
import logging
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid5, NAMESPACE_DNS
import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
import httpx
import asyncio
from base64 import b64encode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GorgiasTicketSync:
    """Sync tickets from Gorgias to PostgreSQL"""

    def __init__(
        self,
        gorgias_domain: str,
        gorgias_username: str,
        gorgias_api_key: str,
        database_url: str
    ):
        """
        Initialize Gorgias ticket sync.

        Args:
            gorgias_domain: Gorgias subdomain (e.g., "lindas")
            gorgias_username: Gorgias account email
            gorgias_api_key: Gorgias API key (base64 encoded)
            database_url: PostgreSQL connection string
        """
        self.gorgias_base_url = f"https://{gorgias_domain}.gorgias.com/api"
        self.gorgias_auth = (gorgias_username, gorgias_api_key)
        self.database_url = database_url

        logger.info(f"Initialized Gorgias sync for domain: {gorgias_domain}")

    async def fetch_tickets(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch tickets from Gorgias API.

        Args:
            start_date: Fetch tickets created after this date
            end_date: Fetch tickets created before this date
            limit: Maximum number of tickets to fetch

        Returns:
            List of ticket dictionaries
        """
        logger.info("Fetching tickets from Gorgias API...")

        all_tickets = []
        cursor = None
        per_page = 100  # Gorgias max is 100
        page_num = 1

        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                # Build query parameters (Gorgias uses cursor-based pagination)
                params = {
                    "limit": per_page,
                    "order_by": "created_datetime:desc"
                }

                # Add cursor for pagination (not first request)
                if cursor:
                    params["cursor"] = cursor

                # Add date filters if provided
                if start_date:
                    params["created_datetime"] = f">{start_date.isoformat()}"
                if end_date:
                    params["created_datetime"] = f"<{end_date.isoformat()}"

                # Fetch tickets page
                try:
                    response = await client.get(
                        f"{self.gorgias_base_url}/tickets",
                        params=params,
                        auth=self.gorgias_auth
                    )
                    response.raise_for_status()

                    data = response.json()
                    tickets = data.get("data", [])

                    if not tickets:
                        logger.info(f"No more tickets found (page {page_num})")
                        break

                    all_tickets.extend(tickets)
                    logger.info(f"Fetched page {page_num}: {len(tickets)} tickets (total: {len(all_tickets)})")

                    # Check if we've hit the limit
                    if limit and len(all_tickets) >= limit:
                        all_tickets = all_tickets[:limit]
                        logger.info(f"Reached limit of {limit} tickets")
                        break

                    # Get next cursor from meta
                    meta = data.get("meta", {})
                    next_cursor = meta.get("next_cursor")

                    if not next_cursor:
                        logger.info("No more pages available (no next_cursor)")
                        break

                    cursor = next_cursor
                    page_num += 1

                except httpx.HTTPStatusError as e:
                    # Handle rate limiting with exponential backoff
                    if e.response.status_code == 429:
                        retry_after = int(e.response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limit hit. Waiting {retry_after} seconds before retrying...")
                        await asyncio.sleep(retry_after)
                        continue  # Retry same request
                    else:
                        logger.error(f"HTTP error fetching tickets: {e}")
                        logger.error(f"Response: {e.response.text}")
                        raise
                except Exception as e:
                    logger.error(f"Error fetching tickets: {e}")
                    raise

        logger.info(f"Total tickets fetched: {len(all_tickets)}")
        return all_tickets

    async def fetch_ticket_messages(
        self,
        ticket_id: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch messages for a specific ticket.

        Args:
            ticket_id: Gorgias ticket ID

        Returns:
            List of message dictionaries
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.gorgias_base_url}/tickets/{ticket_id}/messages",
                    auth=self.gorgias_auth
                )
                response.raise_for_status()

                data = response.json()
                messages = data.get("data", [])

                return messages

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching messages for ticket {ticket_id}: {e}")
                return []
            except Exception as e:
                logger.error(f"Error fetching messages for ticket {ticket_id}: {e}")
                return []

    def transform_ticket(self, gorgias_ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Gorgias ticket to our database schema.

        Args:
            gorgias_ticket: Raw ticket from Gorgias API

        Returns:
            Transformed ticket for database insertion
        """
        # Extract customer info
        customer = gorgias_ticket.get("customer", {})
        customer_id = customer.get("id") or customer.get("email") or "unknown"

        # Extract channel
        channel = gorgias_ticket.get("channel", "email")
        if channel == "api":
            channel = "chat"  # Map API to chat for consistency

        # Extract status
        status = gorgias_ticket.get("status", "open")
        if status == "closed":
            status = "closed"
        elif status == "open":
            status = "open"
        else:
            status = "pending"

        # Extract priority
        priority = "normal"
        if gorgias_ticket.get("is_unread"):
            priority = "high"

        # Extract tags
        tags = [tag.get("name") for tag in gorgias_ticket.get("tags", [])]

        # Extract assigned agent (handle None)
        assignee_user = gorgias_ticket.get("assignee_user")
        assigned_to = None
        if assignee_user:
            assigned_to = assignee_user.get("email")

        # Generate deterministic UUID from Gorgias ticket ID
        ticket_uuid = str(uuid5(NAMESPACE_DNS, f"gorgias.com/ticket/{gorgias_ticket['id']}"))

        # Build transformed ticket
        return {
            "id": ticket_uuid,
            "ticket_number": f"G-{gorgias_ticket['id']}",
            "customer_id": str(customer_id),
            "channel": channel,
            "assigned_to": assigned_to,
            "status": status,
            "priority": priority,
            "subject": gorgias_ticket.get("subject") or "No subject",
            "tags": tags,
            "custom_fields": {
                "gorgias_id": gorgias_ticket["id"],
                "via": gorgias_ticket.get("via"),
                "spam": gorgias_ticket.get("spam", False),
                "is_unread": gorgias_ticket.get("is_unread", False),
                "snooze_datetime": gorgias_ticket.get("snooze_datetime"),
            },
            "created_at": gorgias_ticket.get("created_datetime"),
            "updated_at": gorgias_ticket.get("updated_datetime"),
            "closed_at": gorgias_ticket.get("closed_datetime"),
        }

    def transform_message(
        self,
        gorgias_message: Dict[str, Any],
        ticket_id: str
    ) -> Dict[str, Any]:
        """
        Transform Gorgias message to our database schema.

        Args:
            gorgias_message: Raw message from Gorgias API
            ticket_id: Associated ticket ID

        Returns:
            Transformed message for database insertion
        """
        # Determine sender
        sender = gorgias_message.get("sender", {})
        sender_type = "customer"
        sender_id = None

        if gorgias_message.get("source", {}).get("type") == "customer":
            sender_type = "customer"
            sender_id = sender.get("id") or sender.get("email")
        else:
            sender_type = "agent"
            sender_id = sender.get("email") or sender.get("id")

        # Extract content
        body = gorgias_message.get("body_text") or gorgias_message.get("body_html", "")

        # Generate deterministic UUID from Gorgias message ID
        message_uuid = str(uuid5(NAMESPACE_DNS, f"gorgias.com/message/{gorgias_message['id']}"))

        return {
            "id": message_uuid,
            "ticket_id": ticket_id,
            "sender_id": str(sender_id) if sender_id else None,
            "sender_type": sender_type,
            "content": body,
            "channel": gorgias_message.get("channel", "email"),
            "is_note": gorgias_message.get("is_note", False),
            "metadata": {
                "gorgias_id": gorgias_message["id"],
                "via": gorgias_message.get("via"),
                "source": gorgias_message.get("source"),
                "failed": gorgias_message.get("failed"),
            },
            "created_at": gorgias_message.get("created_datetime"),
        }

    def insert_tickets(
        self,
        tickets: List[Dict[str, Any]],
        dry_run: bool = False
    ) -> int:
        """
        Insert tickets into PostgreSQL database.

        Args:
            tickets: List of transformed tickets
            dry_run: If True, only preview without inserting

        Returns:
            Number of tickets inserted
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would insert {len(tickets)} tickets")
            return 0

        logger.info(f"Inserting {len(tickets)} tickets into database...")

        import json
        from psycopg2.extras import Json

        # Convert dict/list fields to JSON for PostgreSQL
        for ticket in tickets:
            if isinstance(ticket.get('tags'), list):
                ticket['tags'] = Json(ticket['tags'])
            if isinstance(ticket.get('custom_fields'), dict):
                ticket['custom_fields'] = Json(ticket['custom_fields'])

        conn = psycopg2.connect(self.database_url)
        cur = conn.cursor()

        insert_query = """
            INSERT INTO support_app.tickets (
                id, ticket_number, customer_id, channel, assigned_to,
                status, priority, subject, tags, custom_fields,
                created_at, updated_at, closed_at
            ) VALUES (
                %(id)s, %(ticket_number)s, %(customer_id)s, %(channel)s, %(assigned_to)s,
                %(status)s, %(priority)s, %(subject)s, %(tags)s, %(custom_fields)s,
                %(created_at)s, %(updated_at)s, %(closed_at)s
            )
            ON CONFLICT (id) DO UPDATE SET
                ticket_number = EXCLUDED.ticket_number,
                customer_id = EXCLUDED.customer_id,
                channel = EXCLUDED.channel,
                assigned_to = EXCLUDED.assigned_to,
                status = EXCLUDED.status,
                priority = EXCLUDED.priority,
                subject = EXCLUDED.subject,
                tags = EXCLUDED.tags,
                custom_fields = EXCLUDED.custom_fields,
                updated_at = EXCLUDED.updated_at,
                closed_at = EXCLUDED.closed_at
        """

        try:
            execute_batch(cur, insert_query, tickets, page_size=100)
            conn.commit()
            logger.info(f"✅ Inserted {len(tickets)} tickets successfully")

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error inserting tickets: {e}")
            raise
        finally:
            cur.close()
            conn.close()

        return len(tickets)

    def insert_messages(
        self,
        messages: List[Dict[str, Any]],
        dry_run: bool = False
    ) -> int:
        """
        Insert ticket messages into PostgreSQL database.

        Args:
            messages: List of transformed messages
            dry_run: If True, only preview without inserting

        Returns:
            Number of messages inserted
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would insert {len(messages)} messages")
            return 0

        if not messages:
            return 0

        logger.info(f"Inserting {len(messages)} messages into database...")

        from psycopg2.extras import Json

        # Convert dict fields to JSON for PostgreSQL
        for message in messages:
            if isinstance(message.get('metadata'), dict):
                message['metadata'] = Json(message['metadata'])

        conn = psycopg2.connect(self.database_url)
        cur = conn.cursor()

        insert_query = """
            INSERT INTO support_app.ticket_messages (
                id, ticket_id, sender_id, sender_type, content,
                channel, is_note, metadata, created_at
            ) VALUES (
                %(id)s, %(ticket_id)s, %(sender_id)s, %(sender_type)s, %(content)s,
                %(channel)s, %(is_note)s, %(metadata)s, %(created_at)s
            )
            ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                sender_id = EXCLUDED.sender_id,
                sender_type = EXCLUDED.sender_type,
                channel = EXCLUDED.channel,
                is_note = EXCLUDED.is_note,
                metadata = EXCLUDED.metadata
        """

        try:
            execute_batch(cur, insert_query, messages, page_size=100)
            conn.commit()
            logger.info(f"✅ Inserted {len(messages)} messages successfully")

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error inserting messages: {e}")
            raise
        finally:
            cur.close()
            conn.close()

        return len(messages)

    async def sync(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
        dry_run: bool = False,
        include_messages: bool = True
    ) -> Dict[str, int]:
        """
        Sync tickets (and optionally messages) from Gorgias to PostgreSQL.

        Args:
            start_date: Fetch tickets created after this date
            end_date: Fetch tickets created before this date
            limit: Maximum number of tickets to fetch
            dry_run: If True, only preview without inserting
            include_messages: If True, also fetch and insert messages

        Returns:
            Dictionary with counts of tickets and messages synced
        """
        logger.info("=" * 80)
        logger.info("GORGIAS TICKET SYNC STARTED")
        logger.info("=" * 80)
        logger.info(f"Dry run: {dry_run}")
        logger.info(f"Include messages: {include_messages}")
        if start_date:
            logger.info(f"Start date: {start_date.isoformat()}")
        if end_date:
            logger.info(f"End date: {end_date.isoformat()}")
        if limit:
            logger.info(f"Limit: {limit} tickets")
        logger.info("=" * 80)

        # Fetch tickets
        gorgias_tickets = await self.fetch_tickets(start_date, end_date, limit)

        if not gorgias_tickets:
            logger.warning("No tickets found to sync")
            return {"tickets": 0, "messages": 0}

        # Transform tickets
        transformed_tickets = [self.transform_ticket(t) for t in gorgias_tickets]

        # Insert tickets
        tickets_inserted = self.insert_tickets(transformed_tickets, dry_run=dry_run)

        # Fetch and insert messages if requested
        messages_inserted = 0
        if include_messages and not dry_run:
            logger.info("=" * 80)
            logger.info("FETCHING TICKET MESSAGES")
            logger.info("=" * 80)

            all_messages = []
            for i, ticket in enumerate(gorgias_tickets, 1):
                ticket_id = str(ticket["id"])
                logger.info(f"Fetching messages for ticket {ticket_id} ({i}/{len(gorgias_tickets)})...")

                messages = await self.fetch_ticket_messages(ticket["id"])
                transformed_messages = [
                    self.transform_message(m, ticket_id) for m in messages
                ]
                all_messages.extend(transformed_messages)

                # Batch insert every 100 tickets
                if i % 100 == 0:
                    messages_inserted += self.insert_messages(all_messages, dry_run=False)
                    all_messages = []

            # Insert remaining messages
            if all_messages:
                messages_inserted += self.insert_messages(all_messages, dry_run=False)

        logger.info("=" * 80)
        logger.info("GORGIAS TICKET SYNC COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Tickets synced: {tickets_inserted:,}")
        logger.info(f"Messages synced: {messages_inserted:,}")
        logger.info("=" * 80)

        return {
            "tickets": tickets_inserted,
            "messages": messages_inserted
        }


async def main():
    """Entry point for script."""
    parser = argparse.ArgumentParser(description="Sync tickets from Gorgias to PostgreSQL")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, help="Maximum number of tickets to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't insert")
    parser.add_argument("--no-messages", action="store_true", help="Skip fetching messages")

    args = parser.parse_args()

    # Get credentials from environment
    gorgias_domain = os.getenv("GORGIAS_DOMAIN")
    gorgias_username = os.getenv("GORGIAS_USERNAME")
    gorgias_api_key = os.getenv("GORGIAS_API_KEY")
    database_url = os.getenv("DATABASE_URL")

    # Validate credentials
    missing = []
    if not gorgias_domain:
        missing.append("GORGIAS_DOMAIN")
    if not gorgias_username:
        missing.append("GORGIAS_USERNAME")
    if not gorgias_api_key:
        missing.append("GORGIAS_API_KEY")
    if not database_url:
        missing.append("DATABASE_URL")

    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Parse dates
    start_date = None
    end_date = None
    if args.start_date:
        start_date = datetime.fromisoformat(args.start_date)
    if args.end_date:
        end_date = datetime.fromisoformat(args.end_date)

    # Create syncer
    syncer = GorgiasTicketSync(
        gorgias_domain=gorgias_domain,
        gorgias_username=gorgias_username,
        gorgias_api_key=gorgias_api_key,
        database_url=database_url
    )

    # Run sync
    try:
        result = await syncer.sync(
            start_date=start_date,
            end_date=end_date,
            limit=args.limit,
            dry_run=args.dry_run,
            include_messages=not args.no_messages
        )

        logger.info("✅ Sync completed successfully")
        logger.info(f"   Tickets: {result['tickets']:,}")
        logger.info(f"   Messages: {result['messages']:,}")

        sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
