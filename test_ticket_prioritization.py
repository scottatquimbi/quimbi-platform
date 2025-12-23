"""
Test script for ticket prioritization features:
1. Keyword-based urgency detection
2. LCC Member detection
3. Priority calculation logic

Run this to test the new features without hitting the live Gorgias API.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, '/Users/scottallen/unified-segmentation-ecommerce')

from integrations.gorgias_ai_assistant import GorgiasAIAssistant

# Create a test instance (won't make API calls for these unit tests)
assistant = GorgiasAIAssistant(
    gorgias_domain="test",
    gorgias_username="test@test.com",
    gorgias_api_key="test_key",
    analytics_api_url="https://test.com"
)

print("=" * 80)
print("TICKET PRIORITIZATION TESTS")
print("=" * 80)

# Test 1: Keyword detection - Cancel order
print("\n[TEST 1] Urgency Detection: Cancel Order")
print("-" * 80)
message1 = "I need to cancel my order immediately!"
urgency1 = assistant._detect_urgency_keywords(message1)
print(f"Message: {message1}")
print(f"Result: {urgency1}")
assert urgency1["urgency_level"] == "urgent", "Should detect urgent"
assert urgency1["category"] == "cancel_request", "Should categorize as cancel_request"
print("✅ PASS")

# Test 2: Keyword detection - Wrong address
print("\n[TEST 2] Urgency Detection: Wrong Address")
print("-" * 80)
message2 = "The package was shipped to the wrong address!"
urgency2 = assistant._detect_urgency_keywords(message2)
print(f"Message: {message2}")
print(f"Result: {urgency2}")
assert urgency2["urgency_level"] == "urgent", "Should detect urgent"
assert urgency2["category"] == "address_change", "Should categorize as address_change"
print("✅ PASS")

# Test 3: Keyword detection - Edit order
print("\n[TEST 3] Urgency Detection: Edit Order")
print("-" * 80)
message3 = "Can I edit my order before it ships?"
urgency3 = assistant._detect_urgency_keywords(message3)
print(f"Message: {message3}")
print(f"Result: {urgency3}")
assert urgency3["urgency_level"] == "urgent", "Should detect urgent"
assert urgency3["category"] == "order_edit", "Should categorize as order_edit"
print("✅ PASS")

# Test 4: Keyword detection - Damaged product (high priority)
print("\n[TEST 4] Urgency Detection: Damaged Product")
print("-" * 80)
message4 = "My quilt arrived damaged"
urgency4 = assistant._detect_urgency_keywords(message4)
print(f"Message: {message4}")
print(f"Result: {urgency4}")
assert urgency4["urgency_level"] == "high", "Should detect high priority"
assert urgency4["category"] == "damaged_product", "Should categorize as damaged_product"
print("✅ PASS")

# Test 5: Keyword detection - Normal inquiry
print("\n[TEST 5] Urgency Detection: Normal Inquiry")
print("-" * 80)
message5 = "What fabric is this made from?"
urgency5 = assistant._detect_urgency_keywords(message5)
print(f"Message: {message5}")
print(f"Result: {urgency5}")
assert urgency5["urgency_level"] == "normal", "Should detect normal priority"
print("✅ PASS")

# Test 6: LCC Member detection
print("\n[TEST 6] LCC Member Detection")
print("-" * 80)
tags1 = ["LCC_Member", "VIP", "Newsletter"]
is_lcc1 = assistant._detect_lcc_membership(tags1)
print(f"Tags: {tags1}")
print(f"Is LCC Member: {is_lcc1}")
assert is_lcc1 == True, "Should detect LCC_Member tag"
print("✅ PASS")

# Test 7: LCC Member detection - case insensitive
print("\n[TEST 7] LCC Member Detection (case insensitive)")
print("-" * 80)
tags2 = ["lcc_member", "newsletter"]
is_lcc2 = assistant._detect_lcc_membership(tags2)
print(f"Tags: {tags2}")
print(f"Is LCC Member: {is_lcc2}")
assert is_lcc2 == True, "Should detect lcc_member tag (lowercase)"
print("✅ PASS")

# Test 8: Not LCC Member
print("\n[TEST 8] LCC Member Detection (not a member)")
print("-" * 80)
tags3 = ["Newsletter", "First_Time_Buyer"]
is_lcc3 = assistant._detect_lcc_membership(tags3)
print(f"Tags: {tags3}")
print(f"Is LCC Member: {is_lcc3}")
assert is_lcc3 == False, "Should not detect LCC membership"
print("✅ PASS")

# Test 9: Priority calculation - Urgent keyword + LCC member
print("\n[TEST 9] Priority Calculation: Urgent Keyword + LCC Member")
print("-" * 80)
urgency_urgent = {"urgency_level": "urgent", "category": "cancel_request", "matched_keywords": ["cancel order"], "gorgias_tag": "urgent_cancel_request"}
priority1 = assistant._calculate_ticket_priority(
    urgency_data=urgency_urgent,
    is_lcc_member=True,
    ltv=500,
    churn_risk=0.3
)
print(f"Input: Urgent + LCC Member + $500 LTV")
print(f"Result: {priority1}")
assert priority1["priority"] == "urgent", "Should be urgent priority"
assert "lcc_member" in priority1["tags_to_add"], "Should include lcc_member tag"
assert "vip" in priority1["tags_to_add"], "Should include vip tag"
print("✅ PASS")

# Test 10: Priority calculation - LCC member with normal issue
print("\n[TEST 10] Priority Calculation: LCC Member + Normal Issue")
print("-" * 80)
urgency_normal = {"urgency_level": "normal", "category": "general", "matched_keywords": [], "gorgias_tag": None}
priority2 = assistant._calculate_ticket_priority(
    urgency_data=urgency_normal,
    is_lcc_member=True,
    ltv=300,
    churn_risk=0.2
)
print(f"Input: Normal urgency + LCC Member + $300 LTV")
print(f"Result: {priority2}")
assert priority2["priority"] == "high", "LCC members should get high priority minimum"
assert "lcc_member" in priority2["tags_to_add"], "Should include lcc_member tag"
print("✅ PASS")

# Test 11: Priority calculation - High value customer with urgent issue
print("\n[TEST 11] Priority Calculation: High Value Customer + Urgent")
print("-" * 80)
urgency_urgent = {"urgency_level": "urgent", "category": "cancel_request", "matched_keywords": ["cancel order"], "gorgias_tag": "urgent_cancel_request"}
priority3 = assistant._calculate_ticket_priority(
    urgency_data=urgency_urgent,
    is_lcc_member=False,
    ltv=3000,
    churn_risk=0.4
)
print(f"Input: Urgent + $3000 LTV (not LCC)")
print(f"Result: {priority3}")
assert priority3["priority"] == "urgent", "High value + urgent should be urgent"
assert "high_value" in priority3["tags_to_add"], "Should include high_value tag"
print("✅ PASS")

# Test 12: Priority calculation - High urgency keywords for standard customer
print("\n[TEST 12] Priority Calculation: High Urgency + Standard Customer")
print("-" * 80)
urgency_high = {"urgency_level": "high", "category": "damaged_product", "matched_keywords": ["damaged"], "gorgias_tag": "high_priority_damaged_product"}
priority4 = assistant._calculate_ticket_priority(
    urgency_data=urgency_high,
    is_lcc_member=False,
    ltv=200,
    churn_risk=0.3
)
print(f"Input: High urgency (damaged) + $200 LTV")
print(f"Result: {priority4}")
assert priority4["priority"] == "high", "High urgency should be high priority"
print("✅ PASS")

# Test 13: Priority calculation - Normal customer, normal issue
print("\n[TEST 13] Priority Calculation: Normal Customer + Normal Issue")
print("-" * 80)
urgency_normal = {"urgency_level": "normal", "category": "general", "matched_keywords": [], "gorgias_tag": None}
priority5 = assistant._calculate_ticket_priority(
    urgency_data=urgency_normal,
    is_lcc_member=False,
    ltv=150,
    churn_risk=0.2
)
print(f"Input: Normal urgency + $150 LTV")
print(f"Result: {priority5}")
assert priority5["priority"] == "normal", "Should be normal priority"
print("✅ PASS")

# Test 14: Shopify tags extraction (mock data)
print("\n[TEST 14] Shopify Tags Extraction")
print("-" * 80)
customer_data = {
    "integrations": {
        "12345": {
            "__integration_type__": "shopify",
            "customer": {
                "id": "67890",
                "tags": "LCC_Member, VIP, Newsletter"
            }
        }
    }
}
tags = assistant._extract_shopify_tags(customer_data)
print(f"Customer data: {customer_data['integrations']['12345']['customer']['tags']}")
print(f"Extracted tags: {tags}")
assert "LCC_Member" in tags, "Should extract LCC_Member"
assert "VIP" in tags, "Should extract VIP"
assert "Newsletter" in tags, "Should extract Newsletter"
print("✅ PASS")

print("\n" + "=" * 80)
print("ALL TESTS PASSED! ✅")
print("=" * 80)
print("\nFeatures implemented:")
print("✅ Keyword-based urgency detection (cancel, edit, address change)")
print("✅ LCC Member detection from Shopify tags")
print("✅ Priority calculation (urgent/high/normal)")
print("✅ Automatic tag assignment for Gorgias")
print("\nNext steps:")
print("1. Test with live Gorgias webhook")
print("2. Verify tags are created in Gorgias")
print("3. Confirm priority updates in Gorgias UI")
