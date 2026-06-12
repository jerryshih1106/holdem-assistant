# -*- coding: utf-8 -*-
"""steal_stat_guide.py -- Steal frequency and fold-to-steal stat guide."""

from dataclasses import dataclass, field
from typing import List

STEAL_FREQUENCY_PROFILE: dict = {
    'nit':    0.25,
    'tag':    0.42,
    'lag':    0.62,
    'maniac': 0.75,
}

FOLD_TO_STEAL_CATEGORY: dict = {
    'very_low': (0.0,  0.50),
    'low':      (0.50, 0.62),
    'standard': (0.62, 0.75),
    'high':     (0.75, 0.85),
    'very_high':(0.85, 1.00),
}


def _steal_profile(steal_pct: float) -> str:
    if steal_pct < 0.30:
        return 'nit'
    if steal_pct < 0.52:
        return 'tag'
    if steal_pct < 0.68:
        return 'lag'
    return 'maniac'


def _fold_to_steal_category(f2s: float) -> str:
    if f2s < 0.50:
        return 'very_low'
    if f2s < 0.62:
        return 'low'
    if f2s < 0.75:
        return 'standard'
    if f2s < 0.85:
        return 'high'
    return 'very_high'


def _counter_strategy(steal_profile: str, f2s_category: str) -> str:
    if steal_profile == 'maniac':
        if f2s_category in ('high', 'very_high'):
            return "3-bet trap hands vs maniac; you are folding too much to a wide range."
        return "3-bet value hands liberally vs maniac; flat strong draws for implied odds."
    if steal_profile == 'lag':
        if f2s_category in ('high', 'very_high'):
            return "Widen BB defense range; call/3-bet more vs LAG steal attempts."
        return "3-bet bluff/value mix vs LAG; keep ranges balanced."
    if steal_profile == 'tag':
        return "Standard GTO defense; 3-bet value/bluff mix; avoid light calls OOP."
    # nit
    return "Fold most marginal hands vs nit steal; their range is strong."


@dataclass
class StealStatResult:
    steal_pct: float
    fold_to_steal: float
    steal_profile: str
    f2s_category: str
    counter_strategy: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_steal_stat(
    steal_pct: float = 0.42,
    fold_to_steal: float = 0.70,
) -> StealStatResult:
    profile = _steal_profile(steal_pct)
    f2s_cat = _fold_to_steal_category(fold_to_steal)
    counter = _counter_strategy(profile, f2s_cat)

    tips = []
    tips.append(
        "Steal positions: CO, BTN, SB. Fold-to-steal from BB determines defense obligation."
    )
    if fold_to_steal > 0.75:
        tips.append(
            "Over-folding to steal -- defend wider from BB; villain profits with any two cards."
        )
    if steal_pct > 0.60:
        tips.append(
            "Very high steal rate -- villain is attacking blinds with a wide range; widen 3-bet."
        )
    if fold_to_steal < 0.55:
        tips.append(
            "Low fold to steal -- villain defends wide; only steal with profitable hands."
        )
    tips.append(
        "BTN steal is most important position: steal widely from BTN, defend BTN vs CO steals."
    )

    reasoning = (
        f"Steal={steal_pct:.0%} ({profile}), fold-to-steal={fold_to_steal:.0%} ({f2s_cat}). "
        f"Counter: {counter}"
    )
    verdict = f"{profile}_{f2s_cat}"

    return StealStatResult(
        steal_pct=steal_pct,
        fold_to_steal=fold_to_steal,
        steal_profile=profile,
        f2s_category=f2s_cat,
        counter_strategy=counter,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def steal_stat_one_liner(r: StealStatResult) -> str:
    return (
        f"[STEAL steal={r.steal_pct:.0%} f2steal={r.fold_to_steal:.0%}] "
        f"profile={r.steal_profile} counter={r.counter_strategy[:30]}"
    )
