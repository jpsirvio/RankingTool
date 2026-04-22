import random
import math
import copy
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class MatchResult(Enum):
    A = "A"
    B = "B"
    DRAW = "DRAW"
    SKIP = "SKIP"


DEFAULT_TIERS = ["S", "A", "B", "C", "D", "E"]

# Accessible defaults: solid dark background + white text for each tier
DEFAULT_TIER_COLORS: dict[str, tuple[str, str]] = {
    "S": ("#b91c1c", "#ffffff"),  # deep red
    "A": ("#c2410c", "#ffffff"),  # deep orange
    "B": ("#a16207", "#ffffff"),  # amber
    "C": ("#15803d", "#ffffff"),  # green
    "D": ("#1d4ed8", "#ffffff"),  # blue
    "E": ("#6d28d9", "#ffffff"),  # purple
}

# Fallback palette for tiers beyond the defaults
_EXTRA_COLORS = [
    ("#0e7490", "#ffffff"),
    ("#be185d", "#ffffff"),
    ("#374151", "#ffffff"),
    ("#065f46", "#ffffff"),
]


def default_color_for_index(index: int) -> tuple[str, str]:
    keys = list(DEFAULT_TIER_COLORS.keys())
    if index < len(keys):
        return DEFAULT_TIER_COLORS[keys[index]]
    return _EXTRA_COLORS[index % len(_EXTRA_COLORS)]


@dataclass
class TierConfig:
    tiers: list[str] = field(default_factory=lambda: list(DEFAULT_TIERS))
    # Maps tier name → (bg_color, text_color)
    colors: dict[str, tuple[str, str]] = field(default_factory=dict)

    def __post_init__(self):
        # Fill missing colors with accessible defaults
        for i, t in enumerate(self.tiers):
            if t not in self.colors:
                self.colors[t] = default_color_for_index(i)

    def get_colors(self, tier: str) -> tuple[str, str]:
        return self.colors.get(tier, ("#374151", "#ffffff"))

    def set_colors(self, tier: str, bg: str, text: str):
        self.colors[tier] = (bg, text)

    def add_tier(self, name: str, bg: str = "#374151", text: str = "#ffffff"):
        if name not in self.tiers:
            self.tiers.append(name)
            self.colors[name] = (bg, text)

    def remove_tier(self, name: str):
        if name in self.tiers:
            self.tiers.remove(name)
            self.colors.pop(name, None)

    def rename_tier(self, old: str, new: str):
        if old in self.tiers:
            idx = self.tiers.index(old)
            self.tiers[idx] = new
            if old in self.colors:
                self.colors[new] = self.colors.pop(old)

    def to_dict(self) -> dict:
        return {
            "tiers": self.tiers,
            "colors": {k: list(v) for k, v in self.colors.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TierConfig":
        tiers = data.get("tiers", list(DEFAULT_TIERS))
        raw_colors = data.get("colors", {})
        colors: dict[str, tuple[str, str]] = {}
        for i, t in enumerate(tiers):
            if t in raw_colors and len(raw_colors[t]) == 2:
                colors[t] = (raw_colors[t][0], raw_colors[t][1])
            else:
                colors[t] = default_color_for_index(i)
        return cls(tiers=tiers, colors=colors)


@dataclass
class Rating:
    mu: float = 25.0
    sigma: float = 8.333

    def to_dict(self) -> dict:
        return {"mu": self.mu, "sigma": self.sigma}

    @classmethod
    def from_dict(cls, data: dict) -> "Rating":
        return cls(mu=data["mu"], sigma=data["sigma"])


@dataclass
class RankingSnapshot:
    ratings: dict[str, Rating]
    history: list
    ranked_pairs: set[str]
    stable_counter: int


def _pair_key(a: str, b: str) -> str:
    return "|".join(sorted([a, b]))


class RankingEngine:

    STABLE_THRESHOLD = 20

    def __init__(self, names: list[str], tier_config: Optional[TierConfig] = None):
        self.names = list(names)
        self.tier_config = tier_config or TierConfig()

        self.tier_assignments: dict[str, Optional[str]] = {n: None for n in self.names}

        self.ratings: dict[str, Rating] = {n: Rating() for n in self.names}
        self.history: list[list] = []
        self.matches: dict[str, int] = {n: 0 for n in self.names}

        self.ranked_pairs: set[str] = set()

        self.last_top: list[str] = []
        self.stable_counter: int = 0

        self._snapshots: list[RankingSnapshot] = []

        self.allow_cross_tier: bool = False
        self.estimated_total: int = max(len(self.names) * 6, 40)

    # ------------------------------------------------------------------
    # Tier management
    # ------------------------------------------------------------------

    def assign_tier(self, name: str, tier: Optional[str]):
        if name in self.tier_assignments:
            self.tier_assignments[name] = tier

    def get_tier(self, name: str) -> Optional[str]:
        return self.tier_assignments.get(name)

    def get_items_in_tier(self, tier: str) -> list[str]:
        return [n for n, t in self.tier_assignments.items() if t == tier]

    def get_untiered_items(self) -> list[str]:
        return [n for n, t in self.tier_assignments.items() if t is None]

    def all_tiered(self) -> bool:
        return all(t is not None for t in self.tier_assignments.values())

    # ------------------------------------------------------------------
    # Pair selection
    # ------------------------------------------------------------------

    def _eligible_names(self) -> list[str]:
        if self.allow_cross_tier:
            return self.names
        return [n for n in self.names if self.tier_assignments[n] is not None]

    def _pair_ok(self, a: str, b: str) -> bool:
        if a == b:
            return False
        if _pair_key(a, b) in self.ranked_pairs:
            return False
        if not self.allow_cross_tier:
            if self.tier_assignments.get(a) != self.tier_assignments.get(b):
                return False
        return True

    def get_next_pair(self) -> Optional[tuple[str, str]]:
        eligible = self._eligible_names()
        if len(eligible) < 2:
            return None

        ranking = sorted(eligible, key=lambda n: self.ratings[n].mu, reverse=True)
        candidates: list[tuple[float, str, str]] = []

        for i in range(len(ranking) - 1):
            a, b = ranking[i], ranking[i + 1]
            if self._pair_ok(a, b):
                uncertainty = self.ratings[a].sigma + self.ratings[b].sigma
                candidates.append((uncertainty, a, b))

        for _ in range(10):
            tier = random.choice(self.tier_config.tiers)
            pool = self.get_items_in_tier(tier)
            if len(pool) >= 2:
                a, b = random.sample(pool, 2)
                if self._pair_ok(a, b):
                    uncertainty = self.ratings[a].sigma + self.ratings[b].sigma
                    candidates.append((uncertainty, a, b))

        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1], candidates[0][2]

        unranked = [
            (a, b)
            for i, a in enumerate(eligible)
            for b in eligible[i + 1:]
            if self._pair_ok(a, b)
        ]
        if unranked:
            return random.choice(unranked)
        return None

    def all_pairs_ranked(self) -> bool:
        return self.get_next_pair() is None

    # ------------------------------------------------------------------
    # Rating update
    # ------------------------------------------------------------------

    def _update(self, a: str, b: str, result: MatchResult):
        ra, rb = self.ratings[a], self.ratings[b]
        diff = ra.mu - rb.mu
        c = math.sqrt(ra.sigma ** 2 + rb.sigma ** 2)
        expected = 1 / (1 + math.exp(-diff / c))
        score = {MatchResult.A: 1.0, MatchResult.B: 0.0, MatchResult.DRAW: 0.5}[result]
        k = 0.1
        change = k * (score - expected)
        ra.mu += change * ra.sigma
        rb.mu -= change * rb.sigma
        ra.sigma *= 0.99
        rb.sigma *= 0.99

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit_result(self, a: str, b: str, result: MatchResult):
        self._snapshots.append(RankingSnapshot(
            ratings={k: Rating(v.mu, v.sigma) for k, v in self.ratings.items()},
            history=copy.deepcopy(self.history),
            ranked_pairs=set(self.ranked_pairs),
            stable_counter=self.stable_counter,
        ))

        self.history.append([a, b, result.value])
        self.matches[a] = self.matches.get(a, 0) + 1
        self.matches[b] = self.matches.get(b, 0) + 1

        if result != MatchResult.SKIP:
            self._update(a, b, result)
            self.ranked_pairs.add(_pair_key(a, b))

        self._check_stability()

    # ------------------------------------------------------------------
    # Stability / finish
    # ------------------------------------------------------------------

    def _check_stability(self):
        current = self.get_ranking()[:10]
        if current == self.last_top:
            self.stable_counter += 1
        else:
            self.stable_counter = 0
        self.last_top = current

    def is_finished(self) -> bool:
        if self.all_pairs_ranked():
            return True
        if self.stable_counter < self.STABLE_THRESHOLD:
            return False
        recent = self.history[-self.STABLE_THRESHOLD:]
        return any(r[2] in [MatchResult.A.value, MatchResult.B.value] for r in recent)

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def undo_last(self):
        if not self._snapshots:
            return
        snap = self._snapshots.pop()
        self.ratings = snap.ratings
        self.history = snap.history
        self.ranked_pairs = snap.ranked_pairs
        self.stable_counter = snap.stable_counter
        self.matches = {n: 0 for n in self.names}
        for a, b, _ in self.history:
            self.matches[a] = self.matches.get(a, 0) + 1
            self.matches[b] = self.matches.get(b, 0) + 1

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_ranking(self) -> list[str]:
        return sorted(self.names, key=lambda n: self.ratings[n].mu, reverse=True)

    def get_ranking_by_tier(self) -> dict[str, list[str]]:
        result = {}
        for tier in self.tier_config.tiers:
            items = self.get_items_in_tier(tier)
            result[tier] = sorted(items, key=lambda n: self.ratings[n].mu, reverse=True)
        untiered = self.get_untiered_items()
        if untiered:
            result["(untiered)"] = sorted(untiered, key=lambda n: self.ratings[n].mu, reverse=True)
        return result

    def get_scores(self) -> dict[str, float]:
        return {n: self.ratings[n].mu for n in self.names}

    def get_confidence(self) -> float:
        avg_sigma = sum(r.sigma for r in self.ratings.values()) / max(len(self.ratings), 1)
        sigma_score = max(0.0, 1.0 - (avg_sigma / 8.333))
        stability_score = min(1.0, self.stable_counter / self.STABLE_THRESHOLD)
        return round((sigma_score * 0.5 + stability_score * 0.5) * 100, 1)

    def get_progress(self) -> tuple[int, int, int]:
        done = len(self.ranked_pairs)
        total = 0
        if self.allow_cross_tier:
            n = len(self.names)
            total = n * (n - 1) // 2
        else:
            for tier in self.tier_config.tiers:
                n = len(self.get_items_in_tier(tier))
                total += n * (n - 1) // 2
        total = max(total, 1)
        stability_pct = int((self.stable_counter / self.STABLE_THRESHOLD) * 100)
        history_pct = min(int((done / total) * 100), 100)
        percent = max(history_pct, stability_pct)
        return done, total, percent

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def export_state(self) -> dict:
        return {
            "version": 3,
            "values": self.names,
            "tier_config": self.tier_config.to_dict(),
            "tier_assignments": self.tier_assignments,
            "allow_cross_tier": self.allow_cross_tier,
            "ratings": {n: r.to_dict() for n, r in self.ratings.items()},
            "history": self.history,
            "ranked_pairs": list(self.ranked_pairs),
        }

    def load_from_dict(self, data: dict):
        self.names = data["values"]
        self.tier_config = TierConfig.from_dict(
            data.get("tier_config", {"tiers": DEFAULT_TIERS})
        )
        self.tier_assignments = data.get(
            "tier_assignments", {n: None for n in self.names}
        )
        self.allow_cross_tier = data.get("allow_cross_tier", False)
        self.ratings = {
            n: Rating.from_dict(v)
            for n, v in data.get("ratings", {}).items()
        }
        if "ranked_pairs" in data:
            self.ranked_pairs = set(data["ranked_pairs"])
        else:
            self.ranked_pairs = {
                _pair_key(a, b)
                for a, b, r in data.get("history", [])
                if r != MatchResult.SKIP.value
            }
        self.history = data.get("history", [])
        self.matches = {n: 0 for n in self.names}
        for a, b, _ in self.history:
            self.matches[a] = self.matches.get(a, 0) + 1
            self.matches[b] = self.matches.get(b, 0) + 1
        self._snapshots = []
        self.stable_counter = 0
        self.estimated_total = max(len(self.names) * 6, 40)

    def reset(self):
        self.ratings = {n: Rating() for n in self.names}
        self.matches = {n: 0 for n in self.names}
        self.history = []
        self.ranked_pairs = set()
        self.stable_counter = 0
        self._snapshots = []