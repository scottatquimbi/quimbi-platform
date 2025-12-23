# Gorgias Agent Query Options - How Agents Can Query Quimbi

**Date:** 2025-11-09
**Status:** Currently agents must create test tickets
**Goal:** Enable agents to query Quimbi directly without creating fake tickets

---

## Current Limitation

**Problem:** Agents can only trigger Quimbi by creating/updating actual tickets in Gorgias

**Workaround:** Agents create a test ticket, ask their question, then delete it

**Why This Isn't Ideal:**
- Creates clutter in ticket system
- Wastes ticket IDs
- Pollutes reporting/analytics
- Slower than direct query
- No ticket history tracking

---

## Solution Options

### Option 1: Gorgias Macros/Snippets (EASIEST ⭐)

**What it is:** Pre-defined text templates that agents can insert into tickets

**How it works:**
1. Create macros in Gorgias for common queries
2. Agent opens ticket, inserts macro
3. Bot processes and responds with internal note

**Setup:**
1. Go to Gorgias Settings → Macros
2. Create new macro: "Query Customer Order History"
3. Template: `@quimbi check order history for {{customer.email}}`
4. Agent clicks macro → Bot detects `@quimbi` prefix → Responds

**Pros:**
- ✅ No code changes needed
- ✅ Works within existing workflow
- ✅ Can create macro for each query type
- ✅ Fast to implement (5 minutes)

**Cons:**
- ❌ Still requires a ticket to exist
- ❌ Limited to predefined queries
- ❌ Not truly "direct" query

**Example Macros:**

```
Macro: "Check Order History"
Text: @quimbi What did {{customer.name}} order in the last 6 months?

Macro: "Check Product Purchase"
Text: @quimbi Did {{customer.name}} buy [PRODUCT NAME]?

Macro: "Customer Analytics Summary"
Text: @quimbi Show me analytics for {{customer.email}}
```

---

### Option 2: Gorgias Sidebar Widget (RECOMMENDED ⭐⭐⭐)

**What it is:** Custom widget that appears in the Gorgias ticket sidebar showing customer data

**How it works:**
1. Agent opens ticket
2. Sidebar shows customer analytics automatically
3. Widget includes search box for order history queries
4. No need to type anything - data appears instantly

**Visual:**
```
┌─────────────────────────────┐
│ 🤖 Quimbi Insights          │
├─────────────────────────────┤
│ Customer: Marcia Maulden    │
│ LTV: $71.31                 │
│ Churn Risk: 23% (Low)       │
│ Last Order: 401 days ago    │
│                             │
│ ┌─────────────────────────┐ │
│ │ 🔍 Search Orders        │ │
│ │ [rose thread...........]│ │
│ │ [Search]               │ │
│ └─────────────────────────┘ │
│                             │
│ Recent Orders:              │
│ • Aug 29: Thread ($18.69)   │
│ • Aug 21: Thread ($52.62)   │
│                             │
│ [View Full History]         │
└─────────────────────────────┘
```

**Implementation:**

Gorgias supports **custom sidebar widgets** via iFrame:

```javascript
// Widget URL: https://your-domain.com/gorgias-widget?ticket_id={{ticket.id}}&customer_id={{customer.id}}

// Backend endpoint
@app.get("/gorgias-widget")
async def gorgias_widget(ticket_id: str, customer_id: str):
    # Fetch customer analytics
    analytics = await get_customer_analytics(customer_id)

    # Return HTML widget
    return HTMLResponse(f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial; padding: 10px; }}
          .metric {{ margin: 10px 0; }}
          .search-box {{ margin: 15px 0; }}
        </style>
      </head>
      <body>
        <h3>🤖 Quimbi Insights</h3>

        <div class="metric">
          <strong>Customer:</strong> {analytics['name']}
        </div>
        <div class="metric">
          <strong>LTV:</strong> ${analytics['ltv']:.2f}
        </div>
        <div class="metric">
          <strong>Churn Risk:</strong> {analytics['churn_risk']:.0%}
        </div>

        <div class="search-box">
          <input type="text" id="search" placeholder="Search orders...">
          <button onclick="searchOrders()">Search</button>
        </div>

        <div id="results"></div>

        <script>
          async function searchOrders() {{
            const query = document.getElementById('search').value;
            const response = await fetch('/api/search-orders?q=' + query);
            const data = await response.json();
            document.getElementById('results').innerHTML = formatResults(data);
          }}
        </script>
      </body>
    </html>
    """)
```

**Gorgias Configuration:**

1. Go to Settings → Apps & Integrations
2. Create new integration
3. Type: Sidebar widget (iFrame)
4. URL: `https://ecommerce-backend-staging-a14c.up.railway.app/gorgias-widget`
5. Parameters: `?ticket_id={{ticket.id}}&customer_email={{customer.email}}`

**Pros:**
- ✅ Always visible when viewing ticket
- ✅ No need to type anything
- ✅ Can show analytics + search
- ✅ Interactive (search, filters)
- ✅ Professional UX

**Cons:**
- ❌ Requires frontend development (HTML/JS)
- ❌ ~2-3 days to build
- ❌ Need to style to match Gorgias UI

**Estimated Time:** 2-3 days development

---

### Option 3: Gorgias Chat Command (ADVANCED)

**What it is:** Special command syntax in ticket messages that bot detects

**How it works:**
1. Agent types `/quimbi` command in internal note
2. Bot detects command prefix
3. Responds with results in internal note
4. Command is hidden from customer

**Example:**

Agent types (in internal note):
```
/quimbi search orders rose thread
/quimbi customer analytics
/quimbi order history last 6 months
```

Bot responds:
```
🤖 Quimbi Response

Found 2 orders containing "rose thread":
• Order #87265 - Aug 29, 2024: 478 Rose Signature Cotton Thread ($18.69)
• Order #85237 - Aug 21, 2024: 198 Victorian Rose Signature Cotton Thread ($52.62)
```

**Implementation:**

Modify webhook handler to detect slash commands in internal notes:

```python
# In gorgias_ai_assistant.py

def _is_command(self, message: Dict[str, Any]) -> bool:
    """Check if message is a Quimbi command."""
    text = message.get("body_text", "")
    return text.strip().startswith("/quimbi")

async def _process_command(self, message: Dict[str, Any], ticket_id: str):
    """Process Quimbi slash command."""
    text = message.get("body_text", "").strip()

    # Parse command
    parts = text.split()
    command = parts[1] if len(parts) > 1 else None
    args = parts[2:] if len(parts) > 2 else []

    # Execute command
    if command == "search":
        # Search orders
        search_terms = " ".join(args)
        result = await self._search_orders(customer_id, search_terms)
    elif command == "analytics":
        # Get customer analytics
        result = await self._get_customer_analytics(customer_id)
    elif command == "history":
        # Get order history
        months = int(args[0]) if args else 12
        result = await self._get_order_history(customer_id, months)

    # Post result as internal note
    await self._post_internal_note(ticket_id, result)
```

**Pros:**
- ✅ Fast to type
- ✅ Flexible (any query type)
- ✅ Works in existing workflow
- ✅ Command history in notes

**Cons:**
- ❌ Requires code changes
- ❌ Agent must remember syntax
- ❌ Still requires ticket context
- ❌ ~1 day development

**Estimated Time:** 1 day development

---

### Option 4: Standalone Agent Portal (MOST POWERFUL)

**What it is:** Separate web app where agents can query Quimbi directly

**How it works:**
1. Agent opens https://quimbi-portal.yourdomain.com
2. Searches by customer email or ID
3. Gets full analytics + order history
4. Can ask natural language questions
5. Export results to copy/paste into Gorgias

**Features:**

```
┌───────────────────────────────────────┐
│  🤖 Quimbi Agent Portal               │
├───────────────────────────────────────┤
│  Search Customer:                     │
│  [email or customer ID........]  [🔍] │
│                                       │
│  ─────────────────────────────────── │
│                                       │
│  📊 Marcia Maulden                    │
│  mauldenm@earthlink.net               │
│                                       │
│  💰 LTV: $71.31                       │
│  ⚠️  Churn: 23% (Low)                 │
│  📈 Orders: 2 total                   │
│  📅 Last: 401 days ago                │
│                                       │
│  ─────────────────────────────────── │
│                                       │
│  🔍 Ask Quimbi:                       │
│  [Did she buy rose thread?.......]   │
│                                       │
│  💬 Response:                         │
│  Yes! Marcia bought rose thread on   │
│  August 29, 2024 (Order #87265)      │
│  Product: 478 Rose Signature Cotton  │
│  Thread ($18.69)                     │
│                                       │
│  [📋 Copy Response] [🔗 View in      │
│                         Gorgias]     │
└───────────────────────────────────────┘
```

**Tech Stack:**
- Frontend: React or Vue.js
- Backend: Existing FastAPI (add portal routes)
- Auth: Gorgias OAuth or simple password
- Hosting: Same Railway instance

**Pros:**
- ✅ Most flexible (any query)
- ✅ Best UX
- ✅ No Gorgias dependency
- ✅ Can export results
- ✅ Full analytics dashboard

**Cons:**
- ❌ Separate app to maintain
- ❌ ~1-2 weeks development
- ❌ Need authentication system
- ❌ Agents must switch apps

**Estimated Time:** 1-2 weeks development

---

## Comparison Matrix

| Feature | Macros | Sidebar Widget | Chat Commands | Portal |
|---------|--------|----------------|---------------|--------|
| **Setup Time** | 5 min | 2-3 days | 1 day | 1-2 weeks |
| **Code Changes** | None | Medium | Small | Large |
| **Flexibility** | Low | Medium | High | Highest |
| **UX Quality** | Basic | Good | Good | Excellent |
| **Always Visible** | ❌ | ✅ | ❌ | ✅ |
| **No Ticket Required** | ❌ | ❌ | ❌ | ✅ |
| **Cost** | Free | Low | Low | Medium |

---

## Recommendation

### Short-Term (This Week): Macros
Create 5-10 macros for common queries. **Quick win, zero code.**

**Example Macros to Create:**

1. **"Check Recent Orders"**
   ```
   @quimbi What did {{customer.name}} order recently?
   ```

2. **"Search Product"**
   ```
   @quimbi Did {{customer.name}} buy [ENTER PRODUCT NAME]?
   ```

3. **"Customer Summary"**
   ```
   @quimbi Show customer analytics for {{customer.email}}
   ```

4. **"Order History 6 Months"**
   ```
   @quimbi Show order history for last 6 months
   ```

5. **"Churn Risk Check"**
   ```
   @quimbi What is the churn risk for {{customer.email}}?
   ```

### Mid-Term (Next 2 Weeks): Sidebar Widget
Build iFrame widget showing customer analytics + order search. **Best ROI.**

### Long-Term (If Scaling): Standalone Portal
Full agent dashboard with advanced queries. **For enterprise scale.**

---

## Quick Start: Implementing Macros (5 Minutes)

### Step 1: Create Macro in Gorgias

1. Go to https://lindas.gorgias.com
2. Settings → Productivity → Macros
3. Click "Create Macro"

### Step 2: Configure Macro

**Name:** `Quimbi - Check Order History`

**Subject:** _(leave empty)_

**Message:**
```
@quimbi Can you check the order history for {{customer.name}} ({{customer.email}})?
Specifically looking for: [DESCRIBE WHAT YOU'RE LOOKING FOR]
```

**Shortcuts:** `quimbi-orders`

**Tags:** `quimbi`, `order-search`

**Availability:** All tickets

### Step 3: Use It

1. Open any ticket
2. Type `/` to open macro menu
3. Search "quimbi"
4. Select macro
5. Edit the [DESCRIBE WHAT YOU'RE LOOKING FOR] part
6. Send as internal note
7. Bot responds in ~10 seconds

### Step 4: Create More Macros

Copy the pattern for different queries:
- Product searches
- Date ranges
- Analytics
- Churn risk
- LTV check

---

## Implementation Roadmap

### Week 1: Macros (DONE IN 1 HOUR)
- [ ] Create 10 common query macros
- [ ] Train agents on usage
- [ ] Monitor adoption

### Week 2-3: Sidebar Widget (IF NEEDED)
- [ ] Design widget UI
- [ ] Build backend endpoint
- [ ] Add to Gorgias
- [ ] Test with agents

### Month 2+: Portal (IF SCALING)
- [ ] Build React frontend
- [ ] Add authentication
- [ ] Deploy to production
- [ ] Train team

---

## Cost Analysis

| Option | Development Cost | Maintenance | Total Year 1 |
|--------|------------------|-------------|--------------|
| **Macros** | $0 (5 min) | $0 | **$0** |
| **Sidebar** | $2,000 (2-3 days) | $500/year | **$2,500** |
| **Commands** | $1,000 (1 day) | $300/year | **$1,300** |
| **Portal** | $8,000 (2 weeks) | $2,000/year | **$10,000** |

**ROI:**
- Macros: Save ~30 seconds per query × 50 queries/day = **25 minutes/day saved**
- Sidebar: Save ~1 minute per ticket × 100 tickets/day = **1.5 hours/day saved**
- Portal: Save ~2 minutes per lookup × 200 lookups/day = **6+ hours/day saved**

---

## Next Steps

1. **Today:** Create 5 macros in Gorgias (5 minutes)
2. **This Week:** Train agents on macro usage
3. **Next Week:** Decide on sidebar widget vs. standalone portal
4. **Month 1:** Measure time savings and agent feedback

---

**Recommendation:** Start with **Macros** (free, instant), then build **Sidebar Widget** if agents use it heavily (best ROI for moderate usage).

---

**Status:** Ready to implement macros today
**Estimated Impact:** 25+ minutes saved per agent per day
