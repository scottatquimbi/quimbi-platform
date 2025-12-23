# Why The Old Segmentation System Failed (NOW FIXED!)

**Status**: ✅ **FIXED** as of October 13, 2025

## The Core Problem (Was)

**The old system was population-explanatory but NOT individual-explanatory.**

It told you how well statistical axes explained variance across the population, but **it didn't tell you what an individual player actually does in your product**.

## ✅ The Fix

The system now **discovers affordances from events** instead of using hardcoded axes.

**Implementation**: [`affordance_discovery_engine.py`](backend/core/affordance_discovery_engine.py)
**API Endpoints**: [`affordance_api.py`](backend/api/affordance_api.py)
**Details**: [DEVELOPMENT_SUMMARY.md](DEVELOPMENT_SUMMARY.md)

---

## What Was Wrong (Historical Context)

### Old Approach: Hardcoded Statistical Axes

```python
# The system starts with these hardcoded "universal" axes:
UNIVERSAL_AXES = [
    "monetization"  → metrics: [monthly_spend, purchase_frequency]
    "engagement"    → metrics: [avg_daily_sessions, avg_session_duration]
    "temporal"      → metrics: [weekend_ratio, session_consistency]
    "social"        → metrics: [guild_participation, friend_count]
]

# Then runs PCA on aggregate statistics
# Then clusters players into segments like "whale", "hardcore", "weekend_warrior"
```

### Why This Fails

**1. Assumes affordances that may not exist**
- Not every game has monetization (Mass Effect 3 has none)
- Not every game has social features (Mass Effect 3 is single-player)
- Forces every game into the same 4-axis framework

**2. Uses summary statistics, not actual behavior**
- "avg_daily_sessions" = 3.2 sessions/day
- **Doesn't tell you**: What do they DO in those sessions?
- **Doesn't explain**: Are they doing main story? Combat grinding? Companion missions?

**3. Population-focused, not individual-focused**
- "This axis explains 42% of population variance"
- **Doesn't tell you**: What is this individual player's relationship with the product?
- **Doesn't explain**: What affordances are they using vs ignoring?

## Example: Mass Effect 3

### What The Current System Says:

```json
{
  "axes_discovered": 4,
  "variance_explained": 0.95,
  "axes": [
    {"name": "engagement", "variance": 0.40},
    {"name": "economy", "variance": 0.54}
  ],
  "segments": [
    {"name": "engagement_casual", "population": 0.64},
    {"name": "economy_high", "population": 0.32}
  ]
}
```

**For an individual player:**
```json
{
  "segments": {
    "engagement": "casual",
    "economy": "high"
  }
}
```

**Interpretation**: "Player is casual engagement, high economy."

**Problem**: What does "casual engagement" mean? What are they actually DOING? What's "economy" in Mass Effect 3? This tells you NOTHING about how the player moves through the game.

### What The System SHOULD Say:

**Population level:**
```json
{
  "discovered_affordances": [
    {
      "name": "narrative_progression",
      "variance_explained": 0.42,
      "event_types": ["mission_start", "mission_complete", "dialogue_choice", "cutscene_viewed"],
      "interpretation": "Primary way players engage with ME3 is story progression"
    },
    {
      "name": "combat_mastery",
      "variance_explained": 0.28,
      "event_types": ["combat_encounter", "ability_used", "enemy_killed"],
      "interpretation": "Secondary engagement is combat system"
    },
    {
      "name": "build_optimization",
      "variance_explained": 0.18,
      "event_types": ["resource_gathered", "upgrade_crafted", "item_equipped"],
      "interpretation": "Equipment/build optimization is tertiary"
    },
    {
      "name": "companion_content",
      "variance_explained": 0.04,
      "event_types": ["squad_recruited", "companion_dialogue", "loyalty_mission"],
      "interpretation": "Companion content is underutilized - design gap?"
    }
  ]
}
```

**Individual player:**
```json
{
  "player_id": "me3_player_00042",
  "affordance_engagement": {
    "narrative_progression": {
      "engagement_level": 0.87,
      "event_percentage": 0.58,
      "segment": "narrative_completionist",
      "interpretation": "Heavy story focus - completing all dialogue/missions"
    },
    "combat_mastery": {
      "engagement_level": 0.45,
      "event_percentage": 0.28,
      "segment": "combat_balanced",
      "interpretation": "Moderate combat engagement"
    },
    "build_optimization": {
      "engagement_level": 0.12,
      "event_percentage": 0.11,
      "segment": "optimization_minimal",
      "interpretation": "Ignoring equipment/builds - using defaults"
    },
    "companion_content": {
      "engagement_level": 0.03,
      "event_percentage": 0.03,
      "segment": "companion_ignorer",
      "interpretation": "Not discovering companion missions - opportunity"
    }
  },

  "summary": "Story-driven player rushing through main narrative. Missing companion content and not engaging with build systems. Opportunity: Surface companion missions after main story progress."
}
```

## The Difference

| Current System | Affordance-Based System |
|----------------|------------------------|
| "Casual engagement" | "87% narrative focus, 12% optimization" |
| "High economy" | "Minimal build optimization engagement" |
| Population variance: 95% | Same - still captures population structure |
| **Individual**: Meaningless labels | **Individual**: Behavioral explanation |
| **Product**: Generic 4-axis model | **Product**: Discovered affordances specific to THIS game |
| **Actionable**: No | **Actionable**: Yes - "surface companion content" |

## Why Affordances Matter

**Affordances** = What players CAN do in your product (intentional + unintentional)

**Mass Effect 3 affordances:**
- Narrative progression (main story)
- Combat mastery
- Build optimization (equipment/skills)
- Companion relationships (loyalty missions)
- Exploration (planet scanning)
- Romance options

**The segmentation system should:**
1. **Discover** which affordances exist from actual events
2. **Measure** how each player engages with each affordance
3. **Explain** individual behavior: "This player heavily uses X, ignores Y"
4. **Enable action**: "Player hasn't discovered Y - recommend it"

## The Fix

Replace hardcoded statistical axes with **discovered affordances from event patterns**:

1. **Event Taxonomy Discovery**: Cluster event types into affordances
2. **Individual Positioning**: Calculate player's engagement with each affordance
3. **Segment Discovery**: Cluster players by affordance engagement patterns
4. **Temporal Tracking**: Track how affordance engagement changes over time

Result: A system that explains **both** population structure **and** individual behavior through the lens of product affordances.

---

**Bottom Line**: The current system optimizes for statistical variance explanation. It should optimize for behavioral explanation of how individuals move through product affordances.
