# Ticketing System Integrations

This module provides unified integrations with multiple ticketing platforms for automated customer success workflows.

## Supported Platforms

- **Zendesk** - Enterprise helpdesk platform
- **Gorgias** - E-commerce focused customer support platform

## Quick Start

### Using the Factory (Recommended)

The factory pattern automatically creates the correct ticketing system based on environment variables:

```python
from integrations.ticketing import create_ticketing_system

# Auto-detect provider from environment
ticketing = create_ticketing_system()

# Create a churn risk ticket
customer_data = {
    "customer_id": "ABC123",
    "churn_risk": 0.85,
    "ltv": 5000,
    "days_since_purchase": 45
}

ticket = await ticketing.create_churn_ticket(customer_data)
print(f"Created ticket: {ticket['url']}")
```

### Direct Instantiation

You can also directly instantiate a specific provider:

```python
from integrations.ticketing import ZendeskIntegration, GorgiasIntegration

# Zendesk
zendesk = ZendeskIntegration(
    subdomain="yourcompany",
    email="agent@company.com",
    token="your-api-token"
)

# Gorgias
gorgias = GorgiasIntegration(
    domain="yourcompany",
    username="your-email@company.com",
    api_key="your-api-key"
)
```

## Configuration

### Environment Variables

Set these environment variables to configure your ticketing system:

#### Zendesk

```bash
export TICKETING_PROVIDER=zendesk
export ZENDESK_SUBDOMAIN=yourcompany
export ZENDESK_EMAIL=agent@company.com
export ZENDESK_TOKEN=your-api-token
```

**Getting Zendesk Credentials:**
1. Go to Admin Center → Apps and integrations → APIs → Zendesk API
2. Enable Token Access
3. Create a new API token
4. Your subdomain is: `yourcompany` from `yourcompany.zendesk.com`

#### Gorgias

```bash
export TICKETING_PROVIDER=gorgias
export GORGIAS_DOMAIN=yourcompany
export GORGIAS_USERNAME=your-email@company.com
export GORGIAS_API_KEY=your-api-key
```

**Getting Gorgias Credentials:**
1. Go to Settings → REST API
2. Create a new API key
3. Copy the Base64 encoded key
4. Your domain is: `yourcompany` from `yourcompany.gorgias.com`

### Railway Configuration

Add the environment variables to your Railway service:

```bash
# On Railway dashboard
railway variables set TICKETING_PROVIDER=zendesk
railway variables set ZENDESK_SUBDOMAIN=yourcompany
railway variables set ZENDESK_EMAIL=agent@company.com
railway variables set ZENDESK_TOKEN=your-token

# Or via CLI
railway variables set TICKETING_PROVIDER=gorgias \
  GORGIAS_DOMAIN=yourcompany \
  GORGIAS_USERNAME=you@company.com \
  GORGIAS_API_KEY=your-key
```

## API Reference

All ticketing systems implement the `TicketingSystem` abstract base class with these methods:

### Core Methods

#### create_ticket(data: Dict) → Dict

Create a new ticket.

```python
ticket = await ticketing.create_ticket({
    "subject": "High Churn Risk: Customer ABC123",
    "description": "Customer has 85% churn risk with $5,000 LTV...",
    "priority": "urgent",  # urgent, high, medium, low
    "tags": ["churn-risk", "retention", "high-value"],
    "custom_fields": {
        "ltv": 5000,
        "churn_risk": 0.85
    }
})

# Returns:
# {
#     "id": "12345",
#     "url": "https://yourcompany.zendesk.com/agent/tickets/12345",
#     "status": "open",
#     "priority": "urgent",
#     "created_at": "2025-10-17T09:00:00Z"
# }
```

#### get_ticket(ticket_id: str) → Dict

Get ticket details.

```python
ticket = await ticketing.get_ticket("12345")

# Returns:
# {
#     "id": "12345",
#     "subject": "High Churn Risk: Customer ABC123",
#     "status": "open",
#     "priority": "urgent",
#     "tags": ["churn-risk", "retention"],
#     "created_at": "2025-10-17T09:00:00Z",
#     "updated_at": "2025-10-17T10:30:00Z",
#     "description": "..."
# }
```

#### list_tickets(status, tags, priority, limit) → List[Dict]

List tickets with filters.

```python
tickets = await ticketing.list_tickets(
    status="open",
    tags=["churn-risk"],
    priority="urgent",
    limit=25
)

# Returns list of ticket summaries
```

#### get_ticket_with_comments(ticket_id: str) → Dict

Get full ticket with all comments/messages.

```python
ticket = await ticketing.get_ticket_with_comments("12345")

# Returns:
# {
#     "id": "12345",
#     "subject": "...",
#     "description": "...",
#     "comments": [
#         {
#             "id": "1",
#             "body": "Reached out via email...",
#             "author_id": "67890",
#             "created_at": "2025-10-17T10:30:00Z",
#             "public": False
#         }
#     ]
# }
```

#### update_ticket(ticket_id: str, data: Dict) → Dict

Update ticket fields.

```python
result = await ticketing.update_ticket("12345", {
    "status": "pending",
    "priority": "high",
    "tags": ["churn-risk", "in-progress"],
    "comment": "Customer responded, investigating..."
})
```

#### close_ticket(ticket_id: str, reason: str) → Dict

Mark ticket as solved/closed.

```python
result = await ticketing.close_ticket(
    "12345",
    reason="Customer retention successful"
)
```

#### add_comment(ticket_id: str, comment: str, internal: bool) → Dict

Add a comment to the ticket.

```python
await ticketing.add_comment(
    "12345",
    "Sent retention offer, waiting for response",
    internal=True  # Internal note vs public comment
)
```

### Helper Methods

#### create_churn_ticket(customer_data: Dict) → Dict

Convenience method to create a churn risk ticket with smart formatting.

```python
customer_data = {
    "customer_id": "ABC123",
    "churn_risk": 0.85,
    "ltv": 5000,
    "days_since_purchase": 45,
    "risk_level": "critical"
}

ticket = await ticketing.create_churn_ticket(customer_data)
```

This automatically:
- Generates appropriate subject line
- Formats description with customer context
- Sets priority based on risk level and LTV
- Adds relevant tags
- Includes retention strategy recommendations

## Usage with Slack Bot

The ticketing system integrates seamlessly with the Slack bot:

```python
from integrations.slack import SlackBot
from integrations.ticketing import create_ticketing_system

# Create instances
ticketing = create_ticketing_system()
slack_bot = SlackBot(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
    api_base_url=os.getenv("API_BASE_URL"),
    ticketing_system=ticketing  # Pass to Slack bot
)

# Now Slack bot can:
# - List tickets via /tickets command
# - View ticket details with "View Details" button
# - Resolve tickets with "Resolve" button
# - Add comments with "Add Comment" button
```

## Usage with Workflows

Automated workflows can create and monitor tickets:

```python
from workflows import WorkflowScheduler
from integrations.slack import SlackBot
from integrations.ticketing import create_ticketing_system

ticketing = create_ticketing_system()
slack_bot = SlackBot(...)

scheduler = WorkflowScheduler(
    api_base_url=API_BASE_URL,
    slack_bot=slack_bot,
    ticketing_system=ticketing
)

# Workflows will automatically:
# - Create tickets for high-risk customers (daily 9am)
# - Sync open tickets to Slack (every 4 hours)
# - Alert on urgent tickets (hourly)
# - Check for stale tickets (daily 2pm)

await scheduler.start()
```

## Platform-Specific Features

### Zendesk

**API Endpoint:** `https://{subdomain}.zendesk.com/api/v2`

**Features:**
- Custom fields support
- Advanced search with tags
- Public/private comments
- Multiple priority levels
- SLA tracking
- Automation rules

**Limitations:**
- Rate limit: 700 requests/minute
- Search API: 20 requests/minute

### Gorgias

**API Endpoint:** `https://{domain}.gorgias.com/api`

**Features:**
- E-commerce focused (Shopify, BigCommerce, etc.)
- Customer context from store data
- Macros and templates
- Revenue tracking per ticket
- Internal notes (is_note flag)

**Limitations:**
- No native tag filtering in list endpoint (filtered client-side)
- Messages instead of comments structure
- Priority limited to: high, medium, low

**Differences from Zendesk:**
- Uses "messages" instead of "comments"
- Status values: "opened" vs "closed" (not "solved")
- Customer email required for ticket creation
- Uses `is_note` for internal comments

## Ticket Lifecycle Example

```python
# 1. Daily churn check identifies high-risk customer
customer = {
    "customer_id": "ABC123",
    "churn_risk": 0.87,
    "ltv": 5000
}

# 2. Workflow creates ticket
ticket = await ticketing.create_churn_ticket(customer)
# → Ticket #12345 created with "urgent" priority

# 3. Slack notification sent to #customer-success
# "🚨 URGENT: New high-priority ticket #12345"

# 4. CS agent views in Slack
# /tickets urgent
# [View Details] button clicked

# 5. Agent adds comment
await ticketing.add_comment(
    "12345",
    "Reached out via email with 20% discount offer",
    internal=True
)

# 6. Customer responds positively
await ticketing.add_comment(
    "12345",
    "Customer accepted offer and placed new order!",
    internal=True
)

# 7. Agent resolves via Slack
# [Resolve] button clicked
await ticketing.close_ticket(
    "12345",
    reason="Retention successful - customer re-engaged"
)

# 8. Ticket marked as solved
# Next 4-hour sync: No longer appears in open tickets list
```

## Testing

### Manual Testing

```python
import asyncio
from integrations.ticketing import create_ticketing_system

async def test_ticketing():
    # Create instance
    ticketing = create_ticketing_system()

    # Test ticket creation
    ticket = await ticketing.create_ticket({
        "subject": "Test Ticket",
        "description": "This is a test",
        "priority": "low",
        "tags": ["test"]
    })
    print(f"Created: {ticket['id']}")

    # Test retrieval
    retrieved = await ticketing.get_ticket(ticket['id'])
    print(f"Retrieved: {retrieved['subject']}")

    # Test comment
    await ticketing.add_comment(ticket['id'], "Test comment", internal=True)

    # Test closing
    await ticketing.close_ticket(ticket['id'], "Test complete")
    print("Ticket closed successfully")

asyncio.run(test_ticketing())
```

### Integration Testing

```bash
# Set test credentials
export TICKETING_PROVIDER=zendesk
export ZENDESK_SUBDOMAIN=yourcompany-test
export ZENDESK_EMAIL=test@company.com
export ZENDESK_TOKEN=test-token

# Run tests
python3 -m pytest tests/test_ticketing.py
```

## Troubleshooting

### "Failed to create ticket: 401 Unauthorized"

**Zendesk:**
- Verify token is correct
- Check email format: `email@company.com/token`
- Ensure API token access is enabled in Zendesk admin

**Gorgias:**
- Verify API key is correct
- Check username is the account email
- Ensure API key has proper permissions

### "Failed to list tickets: 404 Not Found"

**Zendesk:**
- Verify subdomain is correct
- Check endpoint: `{subdomain}.zendesk.com`

**Gorgias:**
- Verify domain is correct
- Check endpoint: `{domain}.gorgias.com`

### "Rate limit exceeded"

- Reduce frequency of scheduled checks
- Implement exponential backoff
- Cache ticket lists to reduce API calls

## Migration Guide

### Switching from Zendesk to Gorgias

1. Update environment variables:
```bash
export TICKETING_PROVIDER=gorgias
export GORGIAS_DOMAIN=yourcompany
export GORGIAS_USERNAME=you@company.com
export GORGIAS_API_KEY=your-key
```

2. No code changes needed - factory handles it automatically

3. Existing tickets in Zendesk remain accessible
   - Both systems can run in parallel if needed
   - Use different environment configs for each service

### Running Both Simultaneously

```python
from integrations.ticketing import ZendeskIntegration, GorgiasIntegration

# Create both
zendesk = ZendeskIntegration(...)
gorgias = GorgiasIntegration(...)

# Use Zendesk for critical tickets
if customer_ltv > 10000:
    await zendesk.create_churn_ticket(customer)
else:
    await gorgias.create_churn_ticket(customer)
```

## Contributing

To add a new ticketing provider:

1. Create `integrations/ticketing/yourprovider.py`
2. Inherit from `TicketingSystem` base class
3. Implement all abstract methods
4. Add to factory in `factory.py`
5. Update documentation

See existing implementations (Zendesk, Gorgias) for reference.
