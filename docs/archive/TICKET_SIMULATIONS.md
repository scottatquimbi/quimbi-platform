# Gorgias Ticket Simulations - Quimbi AI Response Examples

**Purpose:** Demonstrate what CS agents will see when Quimbi analyzes incoming tickets

**Format:** Each simulation shows:
- Customer profile (what Quimbi fetches from analytics)
- Incoming ticket message (what customer writes)
- Quimbi's internal note response (what agent sees)

---

## Ticket #1: Delayed Order - High-Value VIP Customer

### Customer Profile (Analytics Data)

```json
{
  "customer_id": "5789123456",
  "name": "Margaret Chen",
  "email": "margaret.chen@email.com",
  "lifetime_value": 8450.00,
  "total_orders": 24,
  "avg_order_value": 352.08,
  "days_since_last_purchase": 18,
  "avg_days_between_purchases": 28,
  "first_purchase_date": "2022-03-15",
  "last_purchase_date": "2025-10-16",
  "churn_probability": 0.15
}
```

**Behavioral Pattern:** Frequent, regular buyer with short purchase cycles (~monthly). High engagement, very loyal. Likely buys for personal quilting projects and gifts.

### Incoming Ticket Message

```
Subject: Where is my order?

Hi,

I ordered the Autumn Harvest Fat Quarter Bundle (Order #LA-45892)
last Tuesday and selected 2-day shipping, but it still hasn't
arrived. The tracking hasn't updated in 3 days.

I need this for a project I'm working on this weekend. Can you
please check what's going on?

Thanks,
Margaret
```

### Quimbi Internal Note (What Agent Sees)

```
📊 CUSTOMER INSIGHTS (Internal - Do Not Share)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Lifetime Value: $8,450 (VIP - Top Tier)
⚠️  Churn Risk: 15% (LOW - Healthy)
📈 Historical: 24 orders, $352 avg order
📅 Last Purchase: 18 days ago (Active)
🎯 Pattern: Frequent, regular buyer - highly engaged. Shops monthly for
   personal projects and gifts. Established 3-year relationship.

✨ VIP CUSTOMER: High lifetime value with healthy engagement. Maintain
   excellent service quality.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hi Margaret,

Thank you for reaching out, and I sincerely apologize for the delay with
your Autumn Harvest Fat Quarter Bundle. I completely understand your
frustration, especially since you selected 2-day shipping and have a
project deadline this weekend.

I've just checked your order #LA-45892 and I can see the tracking has been
stuck at our distribution center. This is unacceptable, and I'm escalating
this to our logistics team right now to get it moving immediately.

As one of our most valued customers, I want to make this right. Here's
what I'm doing:

1. **Expedited shipping upgrade** - I'm having your order shipped via
   overnight express at no charge (should arrive by Friday)
2. **20% refund** on your order for the inconvenience
3. **Priority handling** on all your future orders

I'll personally monitor the tracking and send you updates every few hours
until it's in your hands. You should receive a new tracking number within
the next hour.

I truly appreciate your patience and your continued support over the past
3 years. Please don't hesitate to reach out if you need anything else!

Best regards,
Customer Success Team

**Agent Note:** VIP customer with $8.4K LTV - authorize overnight shipping
and 20% refund immediately. No approval needed.
```

---

## Ticket #2: Product Quality Issue - Mid-Value Customer at Risk

### Customer Profile (Analytics Data)

```json
{
  "customer_id": "4123789456",
  "name": "Susan Rodriguez",
  "email": "susan.r.quilts@email.com",
  "lifetime_value": 1240.00,
  "total_orders": 5,
  "avg_order_value": 248.00,
  "days_since_last_purchase": 72,
  "avg_days_between_purchases": 65,
  "first_purchase_date": "2024-08-10",
  "last_purchase_date": "2025-08-23",
  "churn_probability": 0.68
}
```

**Behavioral Pattern:** Seasonal buyer who shops during key periods (holidays, special projects). Recent cooling-off period suggests disengagement. Moderate value but slipping away.

### Incoming Ticket Message

```
Subject: Disappointed with fabric quality

Hello,

I received my Heritage Batik Bundle yesterday and I'm honestly pretty
disappointed. The fabric quality isn't what I expected based on the
product photos. Some of the pieces have uneven coloring and one has
what looks like a small tear.

I've ordered from you before and it was fine, but this experience has
me second-guessing future purchases. I'm not sure if I want a
replacement or just a refund at this point.

Susan
```

### Quimbi Internal Note (What Agent Sees)

```
📊 CUSTOMER INSIGHTS (Internal - Do Not Share)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Lifetime Value: $1,240 (Mid Value)
⚠️  Churn Risk: 68% (CRITICAL - High Risk)
📈 Historical: 5 orders, $248 avg order
📅 Last Purchase: 72 days ago (Cooling Down)
🎯 Pattern: Seasonal buyer - shops during key periods. Currently in
   longest gap between purchases. Building relationship at risk.

⚠️ RETENTION PRIORITY: Customer at critical churn risk showing clear
   disengagement signals. This quality issue could be the final straw.
   Consider expedited solutions, generous compensation, or VIP treatment.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hi Susan,

I'm so sorry to hear about the quality issues with your Heritage Batik
Bundle. This is absolutely not the standard we hold ourselves to, and I
completely understand your disappointment and hesitation about future
orders.

You've been a valued customer since last August, and I want to restore
your confidence in us. Here's what I'd like to offer:

**Option 1 - Full Replacement + Extra:**
- Send you a brand new Heritage Batik Bundle (premium quality checked)
- Include a complimentary Fat Quarter Bundle of your choice ($45 value)
- Free priority shipping (2-day delivery)

**Option 2 - Full Refund + Goodwill Credit:**
- Complete refund to your original payment method
- $60 store credit for a future purchase (no pressure, no expiration)
- Free shipping on your next order whenever you're ready

I genuinely want to earn back your trust. Which option works better for you?
I can process either one immediately.

Also, I'm flagging your account for quality assurance - from now on, every
order you place will go through our premium QA check before shipping. You
deserve consistency, not disappointments.

Please let me know what you'd prefer, and I'll take care of it right away.

Warmest regards,
Customer Success Team

**Agent Note:** CRITICAL RETENTION CASE - Customer showing disengagement
(72 days since last order, longest gap yet). Quality issue may push to
competitor. Approve EITHER option without hesitation. Goal: Keep customer.
```

---

## Ticket #3: Returns/Exchange - New Customer (First Order)

### Customer Profile (Analytics Data)

```json
{
  "customer_id": "9876543210",
  "name": "Jennifer Walsh",
  "email": "jwalsh428@email.com",
  "lifetime_value": 0,
  "total_orders": 0,
  "avg_order_value": 0,
  "days_since_last_purchase": null,
  "avg_days_between_purchases": null,
  "first_purchase_date": null,
  "last_purchase_date": null,
  "churn_probability": null
}
```

**Behavioral Pattern:** Brand new customer - this appears to be their first interaction. Critical first impression moment.

### Incoming Ticket Message

```
Subject: Return or exchange?

Hi there,

I just received my first order from you (Order #LA-47234 - the Spring
Garden Charm Pack). I'm pretty new to quilting and I think I might have
ordered the wrong thing. I was looking for pre-cut squares but these
seem smaller than I need for my pattern.

Can I exchange these for something bigger? Or should I just return them?
I'm not sure what the process is. Also, do I have to pay return shipping?

Thanks!
Jen
```

### Quimbi Internal Note (What Agent Sees)

```
📊 CUSTOMER INSIGHTS (Internal - Do Not Share)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Lifetime Value: $0 (New Customer)
⚠️  Churn Risk: N/A (First Interaction)
📈 Historical: No previous orders
📅 Last Purchase: First order just placed
🎯 Pattern: Brand new to quilting and to Linda's. Critical first
   impression moment.

💡 NEW CUSTOMER: First interaction with our brand. Extra welcoming and
   helpful approach needed. Guide through process and set expectations
   for future relationship.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hi Jen!

Welcome to Linda's, and thank you for choosing us for your quilting journey!
It's exciting that you're getting started with quilting.

Don't worry at all - this is a super common question, and we're here to
help you get exactly what you need. Charm Packs contain 5" x 5" squares,
which are great for smaller projects but might not work for all patterns.

Here's what I'd recommend based on what you're describing:

**Option 1 - Layer Cakes (10" x 10" squares):**
These are twice the size of charm packs and work for most beginner patterns.
I can exchange your Spring Garden Charm Pack for the Spring Garden Layer
Cake at no cost to you.

**Option 2 - Fat Quarters (18" x 22" pieces):**
Even more versatile - you can cut these to any size your pattern needs.
I can exchange for the Spring Garden Fat Quarter Bundle.

**Easy Exchange Process:**
1. Let me know which size you'd prefer
2. I'll send you a prepaid return label (FREE - you don't pay anything)
3. Drop the Charm Pack in the mail
4. Your new order ships immediately (you don't have to wait for us to
   receive the return)

Also, I'd love to send you our **Beginner's Guide to Pre-Cuts** PDF - it
explains all the different sizes and when to use each one. Super helpful
for your next project!

Which option sounds better for your pattern? I'm here to help!

Happy quilting,
Customer Success Team

**Agent Note:** First order, new to quilting. This interaction sets tone
for entire customer relationship. Be extra educational and welcoming.
Approve free exchange + free return shipping immediately.
```

---

## Ticket #4: Promotional Inquiry - High-Value Customer with Elevated Churn

### Customer Profile (Analytics Data)

```json
{
  "customer_id": "3456789012",
  "name": "Patricia Williams",
  "email": "pat.quilts@email.com",
  "lifetime_value": 3280.00,
  "total_orders": 11,
  "avg_order_value": 298.18,
  "days_since_last_purchase": 54,
  "avg_days_between_purchases": 42,
  "first_purchase_date": "2023-11-20",
  "last_purchase_date": "2025-09-10",
  "churn_probability": 0.58
}
```

**Behavioral Pattern:** Historically regular buyer (every 6 weeks), but current gap is longer than usual. Elevated churn risk suggests she may be shopping elsewhere or losing interest.

### Incoming Ticket Message

```
Subject: Question about discount

Hi,

I'm on your email list and I keep seeing promotions for new customers
(20% off first order, etc.) but I never see anything for existing
customers. I've been buying from you for over a year now.

Is there any kind of loyalty program or discount for repeat customers?
I'm planning to order some Christmas fabric soon but I'd like to know
if there's a better deal somewhere.

Thanks,
Pat
```

### Quimbi Internal Note (What Agent Sees)

```
📊 CUSTOMER INSIGHTS (Internal - Do Not Share)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Lifetime Value: $3,280 (High Value)
⚠️  Churn Risk: 58% (ELEVATED - Monitor Closely)
📈 Historical: 11 orders, $298 avg order
📅 Last Purchase: 54 days ago (Recently Active)
🎯 Pattern: Regular buyer (typically every 6 weeks), but current gap is
   12 days longer than usual. May be shopping competitors. Mentioned
   "better deal somewhere" - price sensitivity signal.

💡 RETENTION STRATEGY: Valuable customer showing early churn signals and
   price shopping behavior. Prioritize quick resolution and consider
   retention offer. She's comparing us to competitors RIGHT NOW.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hi Pat,

Thank you so much for bringing this up, and you're absolutely right - we
need to do better at showing appreciation for loyal customers like you!

First, let me say we truly value the 11 orders you've placed with us over
the past 2 years. You're exactly the kind of customer we want to reward.

Here's what I can offer you **right now:**

**1. Immediate VIP Discount:**
Use code **PATVIP20** for 20% off your entire Christmas fabric order (no
minimum, no exclusions, expires Dec 31st)

**2. Ongoing Loyalty Benefits:**
I'm upgrading your account to VIP status, which includes:
- 15% off all future orders (automatic at checkout)
- Early access to seasonal sales (24 hours before public)
- Free shipping on orders $75+ (normally $100+)
- Priority customer service (this email goes to front of queue)

**3. Special Christmas Preview:**
Would you like me to send you early access to our Christmas collection?
It's not live on the website yet, but I can share the catalog with you
today so you can plan your order.

You're right that we focus a lot on new customers, but our repeat customers
are the heart of our business. I apologize we didn't communicate this
better - we've just formalized our VIP program and you're a perfect fit.

Ready to place that Christmas order? I'm here to help you find exactly
what you need!

Warmest regards,
Customer Success Team

**Agent Note:** HIGH PRIORITY - Customer at elevated churn risk is actively
price shopping ("better deal somewhere"). She's giving us ONE CHANCE to
keep her. VIP discount code created and approved. Upgrade to VIP tier
authorized. If she doesn't convert on Christmas order, we likely lose her.
```

---

## Ticket #5: Product Question - Standard Value, Low Churn Risk

### Customer Profile (Analytics Data)

```json
{
  "customer_id": "6789012345",
  "name": "Linda Foster",
  "email": "lfoster.home@email.com",
  "lifetime_value": 420.00,
  "total_orders": 3,
  "avg_order_value": 140.00,
  "days_since_last_purchase": 22,
  "avg_days_between_purchases": 58,
  "first_purchase_date": "2025-04-15",
  "last_purchase_date": "2025-10-12",
  "churn_probability": 0.28
}
```

**Behavioral Pattern:** Recent first-time buyer building relationship. Shops every 2 months. Low churn risk, healthy engagement. Still exploring products.

### Incoming Ticket Message

```
Subject: Fabric care question

Hello,

I purchased some of your batik fabrics last month for a wall hanging
I'm making. Before I start sewing, I wanted to ask - do I need to
pre-wash these? I've heard different opinions from my quilting group.

Also, if I do pre-wash, will the colors bleed? I'm planning to use
light and dark colors together in the same project.

Thanks for your help!
Linda
```

### Quimbi Internal Note (What Agent Sees)

```
📊 CUSTOMER INSIGHTS (Internal - Do Not Share)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Lifetime Value: $420 (Standard)
⚠️  Churn Risk: 28% (LOW - Healthy)
📈 Historical: 3 orders, $140 avg order
📅 Last Purchase: 22 days ago (Active)
🎯 Pattern: Building relationship - still exploring products. Recent
   customer (since April 2025) with healthy purchase frequency. Part
   of quilting community.

💡 STANDARD CARE: Healthy engagement, low risk. Educational opportunity
   to build loyalty through helpful expertise. She mentioned a quilting
   group - word-of-mouth potential.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hi Linda,

Great question! This is one of the most common debates in quilting, and
I'm happy to give you the clear answer.

**For our batik fabrics specifically:**

**Pre-Washing: YES, highly recommended**
Our batiks are made with traditional wax-resist dyeing, which can release
excess dye on the first wash. Pre-washing prevents bleeding and shrinkage
in your finished project.

**How to Pre-Wash Batiks Safely:**

1. **Separate by color family first** - Wash darks together, lights together
2. **Use cold water + Color Catcher sheets** (Shout or Carbona brand work great)
3. **Mild detergent** (Synthrapol is ideal for batiks, but gentle
   detergent works too)
4. **Tumble dry low or line dry** - Iron while slightly damp for best results

**Will they bleed?**
Some excess dye may release in the first wash (especially reds and blacks),
but once pre-washed, they're colorfast and safe to use together. The Color
Catcher sheets will grab any released dye.

**Pro Tip for Wall Hangings:**
Since your project won't be washed frequently after completion, you have
extra assurance. But pre-washing is still best practice for any project
combining light and dark fabrics.

If you have any other questions as you work on your wall hanging, feel free
to reach out! We love seeing finished projects too - if you'd like to share
a photo when you're done, we feature customer projects on our Instagram
(with your permission, of course).

Happy quilting!
Customer Success Team

**Agent Note:** Standard customer, low risk, educational question. Used
opportunity to provide detailed expertise and build trust. Mentioned
quilting group - potential word-of-mouth referral source. Good relationship
trajectory.
```

---

## Summary of Simulation Patterns

### LTV Tier Distribution

| Tier | LTV Range | Example | Treatment |
|------|-----------|---------|-----------|
| **VIP - Top Tier** | ≥ $5,000 | $8,450 | Maximum accommodation, authorize significant compensation immediately |
| **High Value** | $2,000 - $4,999 | $3,280 | Proactive retention offers, VIP upgrades, priority handling |
| **Mid Value** | $500 - $1,999 | $1,240 | Strong retention effort when at-risk, generous resolution |
| **Standard** | $1 - $499 | $420 | Quality service, educational opportunities, build loyalty |
| **New Customer** | $0 | $0 | Extra welcoming, educational, set positive expectations |

### Churn Risk Response Matrix

| Risk Level | Probability | Action |
|------------|-------------|--------|
| **CRITICAL** | ≥ 70% | Maximum intervention, immediate escalation |
| **ELEVATED** | 50-69% | Proactive retention, generous offers |
| **MODERATE** | 30-49% | Standard excellent service |
| **LOW** | < 30% | Maintain relationship, build loyalty |

### Behavioral Archetype Summaries

Instead of listing segment names, Quimbi provides contextual summaries:

- **"Frequent, regular buyer - highly engaged"** - Monthly shopper, short purchase cycles
- **"Seasonal buyer - shops during key periods"** - Buys for holidays, special projects
- **"Building relationship - still exploring products"** - New customer gaining trust
- **"Occasional buyer - large gaps between purchases"** - Infrequent but returns eventually
- **"Recent first-time buyer"** - Brand new, critical impression phase

### Key Retention Triggers

Quimbi flags these signals for agent attention:

1. **"Currently in longest gap between purchases"** - Disengagement warning
2. **"Mentioned 'better deal somewhere'"** - Actively price shopping
3. **"This quality issue could be the final straw"** - Risk of permanent loss
4. **"Part of quilting community"** - Word-of-mouth influence potential
5. **"Critical first impression moment"** - New customer retention opportunity

---

**Last Updated:** 2025-11-03
**Purpose:** Agent training and stakeholder demonstration
