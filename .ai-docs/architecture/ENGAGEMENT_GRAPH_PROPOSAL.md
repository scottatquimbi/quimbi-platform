# Engagement Graph Discovery - Self-Learning Approach

## The Problem

Current system shows:
- **WHERE** players are: "High economy segment, casual engagement segment"
- **WHAT** they've done: Total events, spending, sessions

Missing:
- **HOW** they engage: What sequences of actions define their relationship with the product
- **WHAT'S POSSIBLE**: Given their current state, what paths are available

## The Solution: Self-Discovered Event Graphs

Use the same self-learning philosophy as taxonomy calibration, but for **behavioral sequences**.

### Architecture

```
1. Taxonomy Calibration (existing)
   ├─ Discovers axes via PCA
   ├─ Discovers segments via KMeans
   └─ Stores segment centers + covariance

2. Event Graph Discovery (NEW) ← Self-learning!
   ├─ Discovers canonical event sequences
   ├─ Discovers transition patterns between sequences
   └─ Stores graph structure

3. Player Categorization (existing)
   ├─ Places player on axes
   └─ Calculates fuzzy membership in segments

4. Player Journey Mapping (NEW) ← Self-learning!
   ├─ Identifies which event sequences player exhibits
   ├─ Shows current position in graph
   └─ Reveals available next paths
```

### Discovery Algorithm

**Step 1: Extract Event Sequences**
```python
# For each player, get ordered event sequences
sequences = extract_sequences(game_id, window_size=5)

# Example sequences:
# ["login", "tutorial_start", "tutorial_complete", "first_quest", "first_battle"]
# ["login", "inventory_open", "craft_item", "equip_item", "dungeon_enter"]
```

**Step 2: Discover Frequent Patterns (Self-Learning)**
```python
# Use sequence mining to find common patterns
# NOT hardcoded - discovered from data!

frequent_patterns = fpgrowth(
    sequences,
    min_support=0.05  # Patterns exhibited by ≥5% of players
)

# Discovered patterns might be:
# "tutorial_progression": ["tutorial_start", "tutorial_complete", "first_quest"]
# "economy_engagement": ["inventory_open", "craft_item", "market_browse"]
# "social_discovery": ["guild_search", "guild_join", "co_op_session"]
```

**Step 3: Build Transition Graph**
```python
# For each discovered pattern, find what comes next
# This creates a directed graph of behavioral possibilities

graph = build_transition_graph(frequent_patterns, sequences)

# Example graph:
# tutorial_progression → {
#     "economy_engagement": 0.35,  # 35% of players
#     "social_discovery": 0.25,
#     "combat_mastery": 0.40
# }
```

**Step 4: Store Discovered Structure**
```sql
CREATE TABLE event_patterns (
    pattern_id UUID PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    pattern_name VARCHAR NOT NULL,
    event_sequence JSONB NOT NULL,  -- Ordered events
    support FLOAT NOT NULL,  -- % of players exhibiting pattern
    avg_duration_hours FLOAT,
    discovered_at TIMESTAMPTZ
);

CREATE TABLE pattern_transitions (
    from_pattern_id UUID REFERENCES event_patterns(pattern_id),
    to_pattern_id UUID REFERENCES event_patterns(pattern_id),
    transition_probability FLOAT NOT NULL,
    avg_time_between_hours FLOAT,
    player_count INT
);
```

### Individual Player Mapping

**Step 5: Map Player to Graph**
```python
player_graph_position = {
    "player_id": "me3_player_00042",
    "game_id": "mass_effect_3",

    # Discovered patterns this player exhibits
    "exhibited_patterns": [
        {
            "pattern_name": "story_progression",
            "occurrences": 12,
            "last_exhibited": "2025-10-10T14:30:00Z",
            "strength": 0.85  # How strongly they exhibit this pattern
        },
        {
            "pattern_name": "economy_engagement",
            "occurrences": 8,
            "last_exhibited": "2025-10-12T10:15:00Z",
            "strength": 0.60
        }
    ],

    # Current position in the graph
    "current_state": {
        "recent_patterns": ["story_progression", "inventory_management"],
        "likely_next_patterns": {
            "combat_mastery": 0.45,  # Based on population transitions
            "social_discovery": 0.30,
            "economy_engagement": 0.25
        }
    },

    # Unexplored paths available
    "available_paths": [
        "social_discovery",  # Pattern exists but player hasn't engaged
        "endgame_content",
        "achievement_hunting"
    ]
}
```

## Why This Is Self-Learning

1. **No Hardcoded Features**: Patterns discovered from actual player behavior
2. **Population-Driven**: Uses same principle as PCA - find structure in variance
3. **Adaptive**: Re-calibrate quarterly, new patterns emerge as game evolves
4. **Explanatory**: Shows both individual behavior AND population structure

## Example: Mass Effect 3

**Discovered Patterns** (hypothetical):
- `main_story_velocity`: Fast progression through main missions
- `companion_focus`: Side missions, dialogue, relationship building
- `multiplayer_grind`: Repeated multiplayer sessions
- `completionist_sweep`: Scanning, collectibles, side quests
- `economy_optimization`: Resource gathering, crafting, trading

**Discovered Transitions**:
```
main_story_velocity → companion_focus (40%)
main_story_velocity → multiplayer_grind (25%)
companion_focus → completionist_sweep (60%)
multiplayer_grind → economy_optimization (50%)
```

**Individual Player Example**:
```
Player "me3_player_00042":
- Exhibits: main_story_velocity (strong), companion_focus (moderate)
- Current state: Recently completed main story pattern
- Likely next: companion_focus (60%), multiplayer_grind (25%)
- Unexplored: economy_optimization, completionist_sweep

Interpretation: Story-driven player focused on narrative and characters,
hasn't discovered economy systems or completionist content yet.
```

## Integration with Existing System

**Combined Profile**:
```python
{
    # Static position (existing)
    "segments": {
        "economy": "high",
        "engagement": "casual",
        "temporal": "weekend_warrior"
    },

    # Dynamic patterns (NEW)
    "behavioral_patterns": {
        "exhibited": ["story_progression", "companion_focus"],
        "current_state": "post_main_story",
        "available_paths": ["multiplayer_grind", "economy_optimization"],
        "likely_next": {"companion_focus": 0.6, "multiplayer_grind": 0.25}
    },

    # Combined insight
    "profile_summary": "High-spending casual player focused on story and companions,
                        weekend sessions, hasn't discovered economy systems or multiplayer"
}
```

## Implementation

**Phase 1**: Event Pattern Discovery
- Sequence extraction from events table
- FP-Growth for frequent pattern mining
- Pattern validation (min support, temporal coherence)
- Storage in event_patterns table

**Phase 2**: Transition Graph
- Build directed graph from pattern co-occurrences
- Calculate transition probabilities
- Store in pattern_transitions table

**Phase 3**: Player Mapping
- For each player, match exhibited patterns
- Calculate current position in graph
- Identify available unexplored paths

**Phase 4**: API Integration
- Add endpoints for pattern discovery
- Add endpoints for player journey mapping
- Integrate with existing categorization

## Key Differences from Static Clustering

| Static Clustering (rejected) | Event Graph Discovery (proposed) |
|------------------------------|----------------------------------|
| Hardcoded features | Self-discovered patterns |
| Clusters players | Discovers behavioral sequences |
| Static snapshot | Dynamic journey mapping |
| "You are type X" | "You exhibit patterns A, B and could explore C, D" |
| Population grouping | Individual possibility space |

## Next Steps

1. Implement sequence extraction from events table
2. Apply FP-Growth for pattern discovery
3. Test on ME3 data (210K events) to see discovered patterns
4. Build transition graph
5. Map individual players to graph
6. Create API endpoints

This maintains the elegance of self-learning while showing HOW individuals engage.
