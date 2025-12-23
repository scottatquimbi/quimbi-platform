"""
Archetype Analysis with Fuzzy Top-2 Membership Support

This module provides tools to analyze player archetypes using both
dominant-only and fuzzy top-2 membership approaches.

Phase 1 of Combined Approach: Increasing archetype diversity from 2.3% to 10-15%

Author: Quimbi Platform
Version: 1.0.0
Date: October 15, 2025
"""

from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Import PlayerMultiAxisProfile from clustering engine
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


@dataclass
class ArchetypeSignature:
    """
    Fuzzy archetype signature with multiple representations.

    Supports both backward-compatible dominant-only and new fuzzy top-2 approaches.
    """
    # Backward compatible: dominant segment per axis
    dominant_tuple: Tuple[Tuple[str, str], ...]  # ((axis, segment), ...)

    # Fuzzy top-2: top 2 segments per axis with rounded scores
    fuzzy_tuple: Tuple[Tuple[str, Tuple[Tuple[str, float], ...]], ...]  # ((axis, ((seg1, score1), ...)), ...)

    # Membership strength: strong, balanced, weak per axis
    strength_tuple: Tuple[Tuple[str, str], ...]  # ((axis, strength), ...)

    @property
    def archetype_id(self) -> str:
        """Generate unique ID from fuzzy signature."""
        return f"arch_{hash(self.fuzzy_tuple) % 1000000:06d}"

    def __hash__(self):
        return hash(self.fuzzy_tuple)

    def __eq__(self, other):
        if not isinstance(other, ArchetypeSignature):
            return False
        return self.fuzzy_tuple == other.fuzzy_tuple


@dataclass
class Archetype:
    """
    Player archetype with count and metadata.

    Represents a unique behavioral combination across all axes.
    """
    signature: ArchetypeSignature
    player_count: int
    population_percentage: float
    player_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def archetype_id(self) -> str:
        return self.signature.archetype_id

    def to_dict(self) -> Dict:
        """Convert to API-friendly dict."""
        return {
            "archetype_id": self.archetype_id,
            "player_count": self.player_count,
            "population_percentage": self.population_percentage,
            "dominant_segments": dict(self.signature.dominant_tuple),
            "fuzzy_signature": {
                axis: [(seg, float(score)) for seg, score in segments]
                for axis, segments in self.signature.fuzzy_tuple
            },
            "membership_strengths": dict(self.signature.strength_tuple),
            "created_at": self.created_at.isoformat()
        }


class ArchetypeAnalyzer:
    """
    Analyzes player archetypes with fuzzy membership support.

    Key Features:
    - Backward compatible dominant-only counting
    - Fuzzy top-2 membership counting (4-8x diversity gain)
    - Membership strength analysis
    - Archetype statistics and distribution
    """

    @staticmethod
    def create_strength_signature(profile) -> ArchetypeSignature:
        """
        Create archetype signature using membership strength bins.

        This groups players by dominant segment + strength (strong/balanced/weak),
        creating practical cohort sizes without losing behavioral nuance.

        Args:
            profile: PlayerMultiAxisProfile with membership_strength

        Returns:
            ArchetypeSignature with strength-based grouping
        """
        # Dominant segments (unchanged)
        dominant_tuple = tuple(sorted(profile.dominant_segments.items()))

        # Strength signature: (axis, dominant_segment, strength)
        strength_items = []
        for axis_name in sorted(profile.dominant_segments.keys()):
            dominant_seg = profile.dominant_segments[axis_name]
            strength = profile.membership_strength.get(axis_name, "weak")
            strength_items.append((axis_name, dominant_seg, strength))

        strength_tuple = tuple(strength_items)

        return ArchetypeSignature(
            dominant_tuple=dominant_tuple,
            fuzzy_tuple=strength_tuple,  # Use strength tuple for hashing
            strength_tuple=strength_tuple
        )

    @staticmethod
    def create_fuzzy_signature(profile, rounding: int = 1) -> ArchetypeSignature:
        """
        Create fuzzy archetype signature from player profile.

        Args:
            profile: PlayerMultiAxisProfile with fuzzy_memberships and top2_segments
            rounding: Decimal places for fuzzy score rounding (default: 1)
                     1 = 0.1 buckets (gentle grouping, 210-360 archetypes)
                     2 = 0.01 buckets (precise, 400-500 archetypes)

        Returns:
            ArchetypeSignature with all representations
        """
        # 1. Dominant segments (backward compatible)
        dominant_tuple = tuple(sorted(profile.dominant_segments.items()))

        # 2. Fuzzy top-2 signature (rounded for grouping)
        fuzzy_items = []
        for axis_name in sorted(profile.top2_segments.keys()):
            top2 = profile.top2_segments[axis_name]
            # Round to group similar memberships (1 decimal = 0.1 buckets)
            rounded_top2 = tuple((seg, round(score, rounding)) for seg, score in top2)
            fuzzy_items.append((axis_name, rounded_top2))
        fuzzy_tuple = tuple(fuzzy_items)

        # 3. Membership strengths
        strength_tuple = tuple(sorted(profile.membership_strength.items()))

        return ArchetypeSignature(
            dominant_tuple=dominant_tuple,
            fuzzy_tuple=fuzzy_tuple,
            strength_tuple=strength_tuple
        )

    @staticmethod
    def count_archetypes(
        profiles: List,
        level: str = "strength",
        rounding: int = 1
    ) -> Dict[ArchetypeSignature, Archetype]:
        """
        Count unique archetypes across players at specified granularity level.

        Args:
            profiles: List of PlayerMultiAxisProfile objects
            level: Granularity level (default: "strength")
                - "dominant": Dominant-only (52 archetypes, baseline)
                - "strength": Strength binning (180-240 archetypes, 0% cost) **RECOMMENDED**
                - "fuzzy": Fuzzy top-2 (489 archetypes, 0% cost, high granularity)
            rounding: Decimal places for fuzzy score rounding (default: 1)
                     Only used if level="fuzzy"

        Returns:
            Dictionary mapping ArchetypeSignature to Archetype with counts
        """
        archetype_counter = defaultdict(lambda: {"count": 0, "player_ids": []})

        for profile in profiles:
            # Create signature based on level
            if level == "dominant":
                # Level 1: Dominant-only (backward compatible)
                dominant_tuple = tuple(sorted(profile.dominant_segments.items()))
                sig = ArchetypeSignature(
                    dominant_tuple=dominant_tuple,
                    fuzzy_tuple=dominant_tuple,  # Placeholder
                    strength_tuple=tuple()
                )
            elif level == "strength":
                # Level 2: Strength binning (RECOMMENDED)
                sig = ArchetypeAnalyzer.create_strength_signature(profile)
            elif level == "fuzzy":
                # Level 3: Fuzzy top-2 (high granularity)
                sig = ArchetypeAnalyzer.create_fuzzy_signature(profile, rounding=rounding)
            else:
                raise ValueError(f"Invalid level: {level}. Must be 'dominant', 'strength', or 'fuzzy'")

            archetype_counter[sig]["count"] += 1
            archetype_counter[sig]["player_ids"].append(profile.player_id)

        # Convert to Archetype objects
        total_players = len(profiles)
        archetypes = {}

        for sig, data in archetype_counter.items():
            archetypes[sig] = Archetype(
                signature=sig,
                player_count=data["count"],
                population_percentage=data["count"] / total_players if total_players > 0 else 0,
                player_ids=data["player_ids"]
            )

        return archetypes

    @staticmethod
    def get_archetype_statistics(archetypes: Dict[ArchetypeSignature, Archetype]) -> Dict:
        """
        Calculate statistics about archetype distribution.

        Args:
            archetypes: Dictionary of archetypes from count_archetypes()

        Returns:
            Dict with statistics
        """
        counts = [arch.player_count for arch in archetypes.values()]

        if not counts:
            return {
                "total_archetypes": 0,
                "total_players": 0,
                "singleton_archetypes": 0,
                "small_archetypes": 0,
                "medium_archetypes": 0,
                "large_archetypes": 0
            }

        counts.sort(reverse=True)

        return {
            "total_archetypes": len(archetypes),
            "total_players": sum(counts),
            "max_archetype_size": max(counts),
            "min_archetype_size": min(counts),
            "avg_archetype_size": sum(counts) / len(counts),
            "median_archetype_size": counts[len(counts) // 2],

            # Distribution by size
            "singleton_archetypes": sum(1 for c in counts if c == 1),  # 1 player
            "small_archetypes": sum(1 for c in counts if 2 <= c <= 5),  # 2-5 players
            "medium_archetypes": sum(1 for c in counts if 6 <= c <= 10),  # 6-10 players
            "large_archetypes": sum(1 for c in counts if c > 10),  # >10 players

            # Top archetypes (Pareto principle)
            "top_10_coverage": sum(counts[:10]) / sum(counts) if counts else 0,
            "top_20_coverage": sum(counts[:20]) / sum(counts) if len(counts) >= 20 else 1.0,
        }

    @staticmethod
    def compare_dominant_vs_fuzzy(profiles: List) -> Dict:
        """
        Compare archetype diversity between dominant-only and fuzzy top-2 approaches.

        Args:
            profiles: List of PlayerMultiAxisProfile objects

        Returns:
            Dict with comparison metrics
        """
        # Count using dominant only
        dominant_archetypes = ArchetypeAnalyzer.count_archetypes(
            profiles, use_fuzzy=False
        )

        # Count using fuzzy top-2
        fuzzy_archetypes = ArchetypeAnalyzer.count_archetypes(
            profiles, use_fuzzy=True
        )

        dominant_stats = ArchetypeAnalyzer.get_archetype_statistics(dominant_archetypes)
        fuzzy_stats = ArchetypeAnalyzer.get_archetype_statistics(fuzzy_archetypes)

        diversity_gain = (
            fuzzy_stats["total_archetypes"] / dominant_stats["total_archetypes"]
            if dominant_stats["total_archetypes"] > 0 else 1.0
        )

        return {
            "dominant_only": {
                "archetype_count": dominant_stats["total_archetypes"],
                "stats": dominant_stats
            },
            "fuzzy_top2": {
                "archetype_count": fuzzy_stats["total_archetypes"],
                "stats": fuzzy_stats
            },
            "diversity_gain": diversity_gain,
            "diversity_gain_factor": f"{diversity_gain:.1f}x"
        }

    @staticmethod
    def get_top_archetypes(
        archetypes: Dict[ArchetypeSignature, Archetype],
        top_n: int = 20
    ) -> List[Archetype]:
        """
        Get top N most common archetypes.

        Args:
            archetypes: Dictionary of archetypes
            top_n: Number of top archetypes to return

        Returns:
            List of Archetype objects sorted by player_count (descending)
        """
        sorted_archetypes = sorted(
            archetypes.values(),
            key=lambda a: a.player_count,
            reverse=True
        )
        return sorted_archetypes[:top_n]

    @staticmethod
    def find_player_archetype(
        player_id: str,
        archetypes: Dict[ArchetypeSignature, Archetype]
    ) -> Optional[Archetype]:
        """
        Find the archetype a player belongs to.

        Args:
            player_id: Player identifier
            archetypes: Dictionary of archetypes

        Returns:
            Archetype object if found, None otherwise
        """
        for archetype in archetypes.values():
            if player_id in archetype.player_ids:
                return archetype
        return None

    @staticmethod
    def export_archetypes_to_dict(
        archetypes: Dict[ArchetypeSignature, Archetype],
        include_player_ids: bool = False
    ) -> List[Dict]:
        """
        Export archetypes to JSON-serializable list.

        Args:
            archetypes: Dictionary of archetypes
            include_player_ids: Whether to include full list of player IDs

        Returns:
            List of archetype dictionaries
        """
        result = []
        for archetype in sorted(archetypes.values(), key=lambda a: a.player_count, reverse=True):
            arch_dict = archetype.to_dict()
            if not include_player_ids:
                arch_dict.pop("player_ids", None)
            else:
                arch_dict["player_ids"] = archetype.player_ids
            result.append(arch_dict)
        return result


# Example usage
if __name__ == "__main__":
    # This would be called with real profiles from the clustering engine
    print("ArchetypeAnalyzer module loaded.")
    print("Use ArchetypeAnalyzer.count_archetypes(profiles, use_fuzzy=True) to analyze diversity.")
