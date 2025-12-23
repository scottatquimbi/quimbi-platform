# Unified Segmentation System - Critical Fix Required

## Current Status: BROKEN

The system is **population-explanatory** but **NOT individual-explanatory**.

## The Problem

Uses hardcoded statistical axes (monetization, engagement, temporal, social) instead of discovering actual product affordances from events.

**Result**: Can't explain what individual players actually DO in the product.

## What Needs To Be Fixed

### Replace This:
```python
UNIVERSAL_AXES = ["monetization", "engagement", "temporal", "social"]
metrics = ["monthly_spend", "avg_daily_sessions", "weekend_ratio"]
```

### With This:
```python
# Discover affordances from actual events
affordances = discover_from_events(game_id)
# → ["narrative_progression", "combat_mastery", "build_optimization", "companion_content"]

# Calculate individual's relationship with each affordance
player_profile = calculate_affordance_engagement(player_id, affordances)
# → {"narrative": 0.87, "combat": 0.45, "optimization": 0.12, "companions": 0.03}
```

## Implementation Tasks

1. **Event Taxonomy Discovery** - Cluster event types into affordances using co-occurrence
2. **Individual Affordance Engagement** - Calculate how each player uses each affordance
3. **Segment Discovery Within Affordances** - Cluster players by engagement patterns
4. **Temporal Tracking** - Track how affordance usage changes over time

## Files Created

- `WHY_CURRENT_SYSTEM_FAILS.md` - Explains the core problem
- `AFFORDANCE_BASED_TAXONOMY.md` - Detailed design for the fix
- `TEMPORAL_JOURNEY_TRACKING.md` - How to track individual movement (built on wrong foundation)

## Critical Insight

**Purpose of segmentation**: Capture heterogeneity of players and how they move through product affordances.

**Current system**: Only captures population variance, not individual behavior.

**Fix**: Discover affordances from events, position individuals by affordance usage.

---

**Next**: Move to separate repo and rebuild taxonomy_calibration_engine.py from scratch using affordance discovery.
