# AI Hallucination Fix - Coupon Code Incident

**Date:** 2025-11-08
**Status:** ✅ FIXED (Commit: 449b72e)
**Priority:** 🚨 CRITICAL - Customer-facing accuracy

---

## The Problem

### What Happened:

**Debora Hackel's Ticket** (Today at 5:09 PM):
- **Customer's message:** "I didn't realize there was a code I needed to put in. Can you correct this for me? Thanks."
- **Quimbi's response:** "I see you're having trouble applying your $5 reward coupon code. The code **'Lindas54b7c3964395b'** should be entered during checkout to receive your discount."

### The Issue:

🚨 **Quimbi HALLUCINATED the coupon code `"Lindas54b7c3964395b"`**

**Facts:**
- Customer never mentioned which code
- Customer didn't say it was a $5 reward
- Customer didn't provide any code string
- Quimbi **invented** this specific code out of thin air

**Impact:**
- ❌ Provides incorrect information to customer
- ❌ Customer might try fake code and get error
- ❌ Erodes trust in AI assistant
- ❌ Agent has to correct misinformation

---

## Root Cause

### Why Claude Hallucinated:

1. **Vague customer message** - "there was a code" with no specifics
2. **No anti-hallucination guardrails** in prompt
3. **Claude tried to be "helpful"** by guessing details
4. **Pattern matching** - Claude may have seen similar coupon code formats in training data

### What Claude SHOULD Have Done:

**Correct response:**
> "Hi Debora,
>
> I'd be happy to help you with the code. Could you provide more details about which code you're referring to? For example:
> - Is this a discount code from an email or promotion?
> - Is it related to a recent order?
> - Do you remember any details about the offer?
>
> This will help me assist you more effectively.
>
> Best regards,
> Customer Service"

---

## The Fix

### Added Anti-Hallucination Safeguards

**File:** [integrations/gorgias_ai_assistant.py:1074-1080](integrations/gorgias_ai_assistant.py#L1074-L1080)

**New prompt instructions:**
```
🚨 CRITICAL - DO NOT HALLUCINATE OR MAKE UP DETAILS:
- DO NOT invent coupon codes, order numbers, tracking numbers, or any specific details
- DO NOT make up specific product names unless mentioned in the customer's message
- DO NOT assume details about what the customer needs - ask if unclear
- If the customer's message is vague (e.g., "I didn't realize there was a code"),
  acknowledge it and ASK for clarification
- ONLY reference information explicitly stated in the customer's message or analytics
- When uncertain, say "Could you provide more details about..." rather than guessing
```

### Why This Works:

1. **Explicit prohibition** - Tells Claude NOT to invent specific details
2. **Provides examples** - Shows exact scenario that triggered hallucination
3. **Alternative behavior** - Tells Claude to ASK instead of GUESS
4. **Scope limitation** - Only reference explicit information

---

## Examples: Before vs After

### Example 1: Debora's Coupon Code

**Customer:** "I didn't realize there was a code I needed to put in."

**Before (HALLUCINATED):**
> "I see you're having trouble applying your $5 reward coupon code. The code 'Lindas54b7c3964395b' should be entered during checkout to receive your discount."

**After (CORRECT):**
> "Hi Debora,
>
> I'd be happy to help with the code. Could you let me know which code you're referring to? For example, was this mentioned in an email, on our website, or related to a specific promotion?
>
> Once I know which code you're trying to use, I can provide specific instructions.
>
> Best regards,
> Customer Service"

---

### Example 2: Vague Tracking Question

**Customer:** "I still haven't received it."

**Before (MIGHT HALLUCINATE):**
> "I see your order #12345 shipped via USPS on November 5th with tracking number 9400XXXXX. It should arrive by November 10th."

**After (CORRECT):**
> "Hi there,
>
> I'd like to help track down your order. Could you provide your order number or the email address you used for purchase? This will help me locate the specific order and tracking information.
>
> Best regards,
> Customer Service"

---

### Example 3: Product Question

**Customer:** "Is this machine washable?"

**Before (MIGHT HALLUCINATE):**
> "Yes, the Premium Quilted Throw is machine washable on gentle cycle, cold water only."

**After (CORRECT if no context):**
> "Hi there,
>
> Could you let me know which product you're asking about? If you have an order number or can describe the item, I can provide specific washing instructions.
>
> Best regards,
> Customer Service"

**After (CORRECT if analytics has recent order):**
> "Hi there,
>
> I see you recently purchased the Holiday Quilt Set. Yes, it's machine washable on gentle cycle with cold water. Tumble dry low or lay flat to dry.
>
> Best regards,
> Customer Service"

---

## What Information IS Safe to Reference?

### ✅ SAFE - From Analytics:

- **Lifetime value:** "I see you're a valued customer with $325 in purchases"
- **Order count:** "I see you've placed 7 orders with us"
- **Recent order (general):** "I see you recently ordered from us"
- **Last purchase timing:** "I see your last purchase was 1 day ago"

### ✅ SAFE - From Customer Message:

- **Explicit details:** If customer says "Order #12345", can reference that number
- **Mentioned products:** If customer says "the blue quilt", can use that description
- **Stated problems:** If customer says "it arrived damaged", can reference that

### ❌ UNSAFE - Hallucination Risk:

- **Specific coupon codes** (unless customer provided)
- **Exact tracking numbers** (unless in recent order data)
- **Specific product names** (unless customer mentioned or in recent orders)
- **Order numbers** (unless customer provided or in analytics)
- **Shipping dates** (unless from recent order data)
- **Quantities/prices** (unless explicitly from analytics)

---

## Prevention Going Forward

### 1. Always Ask for Clarification on Vague Messages

**Trigger phrases that require clarification:**
- "I didn't realize..."
- "What about..."
- "Where is it..."
- "I need help with..."
- "Can you fix..."

**Without specific details → ASK, don't guess**

---

### 2. Only Reference Verifiable Data

**Verified sources:**
- ✅ Customer's explicit message
- ✅ Analytics summary (LTV, order count, last purchase date)
- ✅ Recent order data from Shopify integration

**DO NOT reference:**
- ❌ Specific codes/numbers not provided
- ❌ Product details unless from recent orders
- ❌ Shipping details unless from analytics

---

### 3. Test Prompt Changes

**Before deploying prompt changes:**
1. Test with vague messages
2. Test with incomplete information
3. Check for hallucination in responses
4. Verify it asks for clarification

---

## Monitoring for Hallucinations

### How to Detect:

**Check Gorgias notes for:**
- Specific codes/numbers in responses
- Details not mentioned by customer
- Agent corrections to Quimbi responses
- Customer confusion about information provided

**Red flags in logs:**
- Customer says "I didn't say that"
- Agent edits Quimbi's draft heavily
- Customer provides correction in next message

### Weekly Review:

```bash
# Check for agent-edited drafts (indicates errors)
# Review 5-10 random tickets per week
# Look for patterns in hallucinations
# Update prompt if new issues found
```

---

## Related Safeguards Already in Place

### 1. No Discount/Refund Promises

**Prompt already includes:**
```
CRITICAL - DO NOT MAKE DISCOUNT/REFUND PROMISES:
- DO NOT offer specific discounts (e.g., "15% off", "20% credit")
- DO NOT promise refunds or credits directly
- DO NOT say "I can offer you" or "I'm giving you"
```

**Why:** Prevents AI from making financial commitments

---

### 2. No Internal Metrics Exposure

**Prompt already includes:**
```
Do NOT mention "churn risk", "LTV", "analytics" or any internal metrics
```

**Why:** Prevents exposing customer classification to customers

---

### 3. Concise Responses

**Prompt already includes:**
```
KEEP RESPONSE CONCISE: 2-3 short paragraphs maximum (4-6 sentences total)
```

**Why:** Less text = less opportunity for hallucination

---

## Technical Details

### Model Used:
- **Claude 3.5 Haiku** (claude-3-5-haiku-20241022)
- Temperature: 0.7
- Max tokens: 600

### Why Hallucinations Happen:

**LLM behavior:**
- Trained to be "helpful" and provide complete answers
- Pattern matches from training data
- Fills in gaps when information is incomplete
- Generates plausible-sounding but incorrect details

**Mitigation strategies:**
1. ✅ Explicit "DO NOT" instructions
2. ✅ Provide alternatives (ask vs guess)
3. ✅ Limit token count (less room for invention)
4. ✅ Lower temperature (more deterministic)
5. ⚠️ Could add: Few-shot examples of correct clarification requests

---

## Testing the Fix

### Test Case 1: Debora's Scenario (Vague Code Reference)

**Input:**
```json
{
  "customer_message": "I didn't realize there was a code I needed to put in.",
  "customer_name": "Debora",
  "analytics": {"ltv": 325, "orders": 7}
}
```

**Expected output (NO CODE HALLUCINATION):**
```
Hi Debora,

I'd be happy to help you with the code. Could you provide more details about
which code you're referring to? For example:
- Was this from an email promotion?
- Is it related to a specific product or order?
- Do you remember where you saw it mentioned?

This will help me assist you more effectively.

Best regards,
Customer Service
```

---

### Test Case 2: Vague Tracking Question

**Input:**
```json
{
  "customer_message": "Where is my order?",
  "customer_name": "Sarah",
  "analytics": {"ltv": 150, "orders": 2}
}
```

**Expected output (ASK FOR ORDER NUMBER):**
```
Hi Sarah,

I'd like to help track your order. Could you provide your order number or
confirmation email? This will help me look up the tracking information.

Best regards,
Customer Service
```

---

### Test Case 3: Specific Details Provided (OK to Reference)

**Input:**
```json
{
  "customer_message": "Where is order #12345? I need it by Friday.",
  "customer_name": "John",
  "analytics": {"ltv": 200, "orders": 3, "recent_orders": [{"name": "#12345", "tracking": "9400..."}]}
}
```

**Expected output (CAN REFERENCE ORDER #12345):**
```
Hi John,

I've located order #12345. It shipped via USPS with tracking number 9400...
and is currently in transit. Based on the tracking, it should arrive by
Thursday, which meets your Friday deadline.

I'll keep monitoring it to ensure it arrives on time.

Best regards,
Customer Service
```

---

## Deployment

**Commit:** 449b72e
**Deployed:** 2025-11-08 (Auto-deploy via Railway)
**Status:** Live and running

**Verification:**
```bash
railway logs | grep -i "CRITICAL.*HALLUCINATE"
# Should see new prompt being used
```

---

## Success Metrics

### Before Fix:
- ❌ Hallucinated coupon code for Debora
- ❌ Made up specific details when customer was vague

### After Fix (Expected):
- ✅ Asks for clarification on vague messages
- ✅ Only references verified information
- ✅ No invented codes, numbers, or details
- ✅ Reduces agent correction rate

### Monitor:
- Agent edit rate on Quimbi drafts
- Customer confusion in follow-up messages
- Weekly ticket review for hallucinations

---

## Lessons Learned

1. **LLMs will hallucinate by default** - Need explicit guardrails
2. **"Helpful" can be harmful** - Better to ask than to guess wrong
3. **Vague messages are triggers** - Require extra safety measures
4. **Specific examples in prompts** - Help Claude understand exact scenarios
5. **Test with edge cases** - Vague/incomplete messages reveal weaknesses

---

## Future Enhancements

### Priority 1: Add Few-Shot Examples to Prompt

**Show Claude good vs bad examples:**
```
EXAMPLE - Vague Message (CORRECT Response):
Customer: "I need help with my code"
Response: "Could you specify which code you're referring to?"

EXAMPLE - Vague Message (INCORRECT Response):
Customer: "I need help with my code"
Response: "The code SAVE20 should be entered at checkout" ❌ (HALLUCINATED)
```

### Priority 2: Implement Response Validation

**Before posting to Gorgias:**
- Check for specific patterns (coupon codes, tracking numbers)
- Flag if response contains details not in customer message
- Require agent approval for flagged responses

### Priority 3: Confidence Scoring

**Add confidence indicator:**
```
AGENT RECOMMENDATION:
• Confidence: HIGH (all details verified)
• Confidence: MEDIUM (assumed customer intent, asked for clarification)
• Confidence: LOW (vague message, needs agent review before sending)
```

---

**Status:** ✅ FIXED - Anti-hallucination safeguards deployed

**Next:** Monitor for 7 days, review agent edits, adjust prompt if needed
