#!/bin/bash
#
# Test the Gorgias bot by sending a simulated webhook
# This posts a draft reply to an actual Gorgias ticket
#

TICKET_ID="235766516"  # Replace with a real ticket ID
CUSTOMER_EMAIL="mauldenm@earthlink.net"  # Real customer from our tests
CUSTOMER_NAME="Marcia Maulden"
CUSTOMER_MESSAGE="Hi, I'm trying to remember if I ordered any rose-colored thread from you. Can you check my order history?"

# Simulate Gorgias webhook payload
WEBHOOK_PAYLOAD=$(cat <<EOF
{
  "id": ${TICKET_ID},
  "uri": "https://lindas.gorgias.com/api/tickets/${TICKET_ID}",
  "external_id": null,
  "language": "en",
  "status": "open",
  "priority": "normal",
  "channel": "email",
  "via": "email",
  "customer": {
    "id": 870053010,
    "email": "${CUSTOMER_EMAIL}",
    "firstname": "Marcia",
    "lastname": "Maulden",
    "name": "${CUSTOMER_NAME}",
    "integrations": {
      "82185": {
        "__integration_type__": "shopify",
        "customer": {
          "id": 7460267524351,
          "email": "${CUSTOMER_EMAIL}",
          "orders_count": 2,
          "total_spent": "71.31"
        }
      }
    }
  },
  "messages": [
    {
      "id": 1234567890,
      "uri": "https://lindas.gorgias.com/api/tickets/${TICKET_ID}/messages/1234567890",
      "message_id": null,
      "ticket_id": ${TICKET_ID},
      "external_id": null,
      "public": true,
      "channel": "email",
      "via": "email",
      "source": {
        "type": "email",
        "from": {
          "name": "${CUSTOMER_NAME}",
          "address": "${CUSTOMER_EMAIL}"
        },
        "to": [
          {
            "name": "Linda's Support",
            "address": "support@lindas.com"
          }
        ]
      },
      "sender": {
        "id": 870053010,
        "email": "${CUSTOMER_EMAIL}",
        "firstname": "Marcia",
        "lastname": "Maulden"
      },
      "from_agent": false,
      "receiver": null,
      "subject": "Question about previous order",
      "body_text": "${CUSTOMER_MESSAGE}",
      "body_html": "<p>${CUSTOMER_MESSAGE}</p>",
      "stripped_text": "${CUSTOMER_MESSAGE}",
      "stripped_html": "<p>${CUSTOMER_MESSAGE}</p>",
      "created_datetime": "$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)",
      "sent_datetime": "$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)",
      "failed_datetime": null,
      "deleted_datetime": null,
      "opened_datetime": null,
      "last_sending_error": null,
      "is_note": false,
      "attachments": []
    }
  ],
  "created_datetime": "$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)",
  "opened_datetime": null,
  "last_received_message_datetime": "$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)",
  "last_message_datetime": "$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)",
  "updated_datetime": "$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)",
  "closed_datetime": null,
  "snooze_datetime": null,
  "trashed_datetime": null,
  "spam_datetime": null,
  "is_unread": true,
  "assignee_user": null,
  "assignee_team": null
}
EOF
)

echo "🧪 Testing Gorgias Bot with Query:"
echo "   Customer: ${CUSTOMER_NAME} (${CUSTOMER_EMAIL})"
echo "   Question: ${CUSTOMER_MESSAGE}"
echo ""
echo "📤 Sending webhook to Railway..."

curl -X POST \
  "https://ecommerce-backend-staging-a14c.up.railway.app/api/gorgias/webhook" \
  -H "Content-Type: application/json" \
  -d "${WEBHOOK_PAYLOAD}" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s

echo ""
echo "✅ Check Gorgias ticket #${TICKET_ID} for:"
echo "   1. Internal note with customer analytics"
echo "   2. Draft reply with order history answer"
