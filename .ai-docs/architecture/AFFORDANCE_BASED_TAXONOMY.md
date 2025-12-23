# Affordance-Based Taxonomy Discovery

## The Fundamental Problem

**Current System (BROKEN)**:
```python
# Hardcoded "universal" axes
UNIVERSAL_AXES = [
    "monetization",  # Assumes all games have monetization
    "engagement",    # Measures sessions/duration (summary stats)
    "temporal",      # Measures when they play (summary stats)
    "social"         # Assumes all games have social features
]

# Runs PCA on pre-aggregated metrics
metrics = ["monthly_spend", "avg_daily_sessions", "weekend_ratio"]
```

**Why This Is Wrong**:
1. **Assumes affordances**: Not all games have guilds, not all have monetization
2. **Summary statistics**: "avg_daily_sessions" doesn't explain WHAT they do
3. **Population-explanatory only**: Shows variance in population, not individual behavior
4. **Ignores actual events**: Never looks at what players actually DO

## The Correct Approach: Discover Affordances from Events

### Step 1: Event Taxonomy Discovery

**What exists in the game?**

```python
# For Mass Effect 3, discover from actual events:
event_types = {
    "mission_start": 1842,
    "mission_complete": 1756,
    "dialogue_choice": 3201,
    "combat_encounter": 2876,
    "item_equipped": 1243,
    "squad_member_recruited": 287,
    "resource_gathered": 894,
    "upgrade_crafted": 456,
    "romance_progressed": 123,
    "planet_scanned": 678
}

# NO guild events → social axis doesn't exist
# NO purchase events → monetization axis doesn't exist (or minimal)
# LOTS of dialogue/romance → narrative affordance axis exists
# LOTS of combat → combat mastery affordance axis exists
```

### Step 2: Affordance Clustering

**Group events by underlying affordance**:

```python
# Discovered affordances from event clustering:

narrative_affordance = [
    "mission_start",
    "mission_complete",
    "dialogue_choice",
    "romance_progressed",
    "cutscene_viewed"
]

combat_affordance = [
    "combat_encounter",
    "enemy_killed",
    "ability_used",
    "difficulty_changed"
]

optimization_affordance = [
    "resource_gathered",
    "upgrade_crafted",
    "item_equipped",
    "loadout_changed"
]

exploration_affordance = [
    "planet_scanned",
    "area_discovered",
    "collectible_found"
]

companion_affordance = [
    "squad_member_recruited",
    "companion_dialogue",
    "loyalty_mission"
]
```

### Step 3: Individual Player Positioning

**For each player, calculate their relationship with each affordance**:

```python
player_profile = {
    "player_id": "me3_player_00042",

    # How they engage with each discovered affordance
    "affordance_engagement": {
        "narrative": {
            "event_count": 287,
            "event_percentage": 0.42,  # 42% of their events
            "velocity": 3.2,  # events per session
            "consistency": 0.89  # how regularly they engage
        },
        "combat": {
            "event_count": 198,
            "event_percentage": 0.29,
            "velocity": 2.1,
            "consistency": 0.76
        },
        "optimization": {
            "event_count": 142,
            "event_percentage": 0.21,
            "velocity": 1.5,
            "consistency": 0.62
        },
        "exploration": {
            "event_count": 34,
            "event_percentage": 0.05,
            "velocity": 0.4,
            "consistency": 0.31
        },
        "companion": {
            "event_count": 21,
            "event_percentage": 0.03,
            "velocity": 0.2,
            "consistency": 0.25
        }
    }
}
```

**Interpretation**: Player is 42% narrative-focused, 29% combat-focused, 21% optimization-focused. They engage heavily with story and combat, moderately with builds, and minimally with exploration and companions.

### Step 4: Segment Discovery Within Affordances

**Cluster players by their engagement patterns with each affordance**:

```python
# Narrative affordance segments (discovered via clustering):

narrative_completionist = {
    "event_percentage": 0.65,  # 65% of their time in narrative
    "velocity": 4.5,
    "consistency": 0.95,
    "player_count": 1247,
    "percentage": 34.6%
}

narrative_balanced = {
    "event_percentage": 0.35,
    "velocity": 2.1,
    "consistency": 0.72,
    "player_count": 1589,
    "percentage": 44.1%
}

narrative_minimal = {
    "event_percentage": 0.15,
    "velocity": 0.8,
    "consistency": 0.45,
    "player_count": 764,
    "percentage": 21.2%
}
```

## Example: Mass Effect 3 Taxonomy

### Discovered Affordances (Axes):
1. **Narrative Progression** (42% of population variance)
   - Main story missions, dialogue choices, romance

2. **Combat Mastery** (28% of population variance)
   - Combat encounters, ability usage, difficulty settings

3. **Build Optimization** (18% of population variance)
   - Resource gathering, crafting, equipment management

4. **Exploration** (8% of population variance)
   - Planet scanning, area discovery, collectibles

5. **Companion Relationships** (4% of population variance)
   - Squad recruitment, companion dialogue, loyalty missions

**Note**: NO monetization axis (Mass Effect 3 is single-purchase, no MTX)
**Note**: NO social axis (single-player game)

### Individual Player Example:

```json
{
  "player_id": "me3_player_00042",
  "affordance_profile": {
    "narrative_progression": {
      "engagement_level": 0.87,  // High engagement
      "segment": "narrative_completionist",
      "fuzzy_membership": 0.85
    },
    "combat_mastery": {
      "engagement_level": 0.45,
      "segment": "combat_balanced",
      "fuzzy_membership": 0.62
    },
    "build_optimization": {
      "engagement_level": 0.34,
      "segment": "optimization_casual",
      "fuzzy_membership": 0.71
    },
    "exploration": {
      "engagement_level": 0.12,
      "segment": "exploration_minimal",
      "fuzzy_membership": 0.88
    },
    "companion_relationships": {
      "engagement_level": 0.08,
      "segment": "companion_minimal",
      "fuzzy_membership": 0.79
    }
  },

  "interpretation": "Story-driven player focused on narrative completion with moderate combat engagement. Minimal interest in optimization, exploration, and companion content. Likely rushing through main story."
}
```

## Why This Is Better

### Before (Hardcoded Axes):
- "Player is 0.8 engagement_hardcore, 0.6 monetization_whale"
- **Problem**: Doesn't explain WHAT they do, just summary stats

### After (Affordance Discovery):
- "Player engages heavily with narrative progression (87%) and moderately with combat (45%). Minimal exploration (12%) and companion interaction (8%)."
- **Explains**: WHAT they do in the product, HOW they use affordances

### Population vs Individual:

**Population Level**:
"Mass Effect 3's primary affordance is narrative progression (42% variance), followed by combat mastery (28%). Exploration and companion content are underutilized affordances (8% and 4% variance)."

**Design Insight**: Players aren't discovering companion content - this is an unintentional affordance gap.

**Individual Level**:
"This player heavily uses narrative affordance but ignores companion affordance. They're missing content that exists."

**Intervention**: Suggest companion missions when they complete main story missions.

## Implementation Algorithm

### Phase 1: Event Taxonomy Discovery
```python
async def discover_event_taxonomy(game_id: str):
    # 1. Get all unique event types
    event_types = await get_event_types(game_id)

    # 2. Build co-occurrence matrix
    # Events that happen together likely belong to same affordance
    cooccurrence = build_event_cooccurrence_matrix(game_id)

    # 3. Cluster events into affordances
    affordances = cluster_events_into_affordances(cooccurrence)

    # 4. Name affordances based on event types
    named_affordances = name_affordances(affordances, event_types)

    return named_affordances
```

### Phase 2: Individual Positioning
```python
async def calculate_player_affordance_profile(player_id: str, affordances: List[Affordance]):
    # Get player's events
    events = await get_player_events(player_id)

    # Calculate engagement with each affordance
    profile = {}
    for affordance in affordances:
        # Count events in this affordance
        affordance_events = [e for e in events if e.event_type in affordance.event_types]

        profile[affordance.name] = {
            "event_count": len(affordance_events),
            "event_percentage": len(affordance_events) / len(events),
            "velocity": calculate_velocity(affordance_events),
            "consistency": calculate_consistency(affordance_events)
        }

    return profile
```

### Phase 3: Segment Discovery
```python
async def discover_segments_within_affordance(affordance: Affordance, player_profiles: List[Dict]):
    # Extract engagement metrics for this affordance
    X = np.array([
        [
            p["affordance_engagement"][affordance.name]["event_percentage"],
            p["affordance_engagement"][affordance.name]["velocity"],
            p["affordance_engagement"][affordance.name]["consistency"]
        ]
        for p in player_profiles
    ])

    # Cluster
    kmeans = KMeans(n_clusters=optimal_k)
    labels = kmeans.fit_predict(X)

    # Name segments based on engagement level
    segments = []
    for cluster_id in range(optimal_k):
        cluster_center = kmeans.cluster_centers_[cluster_id]
        segment_name = name_affordance_segment(
            affordance.name,
            cluster_center[0]  # event_percentage
        )
        segments.append(segment_name)

    return segments
```

## Next Steps

1. **Implement event taxonomy discovery** from actual events
2. **Replace hardcoded UNIVERSAL_AXES** with discovered affordances
3. **Calculate affordance engagement** for each player
4. **Discover segments** within each affordance via clustering
5. **Test on ME3 data** to see what affordances emerge

This will make the system **both population-explanatory AND individual-explanatory** because axes represent actual product affordances, and individuals are positioned by HOW they engage with those affordances.
