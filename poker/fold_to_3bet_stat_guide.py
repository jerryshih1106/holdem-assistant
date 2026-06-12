# -*- coding: utf-8 -*-
"""fold_to_3bet_stat_guide.py -- Fold-to-3bet stat exploitation guide."""

from dataclasses import dataclass, field
from typing import List

FOLD_TO_3BET_CATEGORY: dict = {
    'very_low': (0.0,  0.40),
    'low':      (0.40, 0.50),
    'standard': (0.50, 0.65),
    'high':     (0.65, 0.75),
    'very_high':(0.75, 1.00),
}

EXPLOIT_VS_FOLD_TO_3BET: dict = {
    'very_low':  'VALUE_ONLY',
    'low':       'MOSTLY_VALUE',
    'standard':  'BALANCED',
    'high':      'ADD_BLUFFS',
    'very_high': 'HEAVY_BLUFF',
}

# Breakeven fold % for a bluff 3-bet (approx 2.5x open = pot-size 3bet context)
# BE = bluff_3bet_size / (bluff_3bet_size + pot_before)
_BE_FOLD_TYPICAL = 0.42


def _fold_to_3bet_category(f3b: float) -> str:
    if f3b < 0.40:
        return 'very_low'
    if f3b < 0.50:
        return 'low'
    if f3b < 0.65:
        return 'standard'
    if f3b < 0.75:
        return 'high'
    return 'very_high'


def _bluff_3bet_ev(f3b: float, bluff_size_bb: float, pot_bb: float) -> float:
    """EV of a pure bluff 3-bet in BB."""
    win_when_fold = pot_bb * f3b
    lose_when_call = bluff_size_bb * (1.0 - f3b)
    return round(win_when_fold - lose_when_call, 2)


def _optimal_3bet_range(f3b_category: str) -> str:
    ranges = {
        'very_low':  "QQ+/AK only -- villain plays back too often; protect range.",
        'low':       "QQ+/AK/AQs -- mostly value with rare premiums.",
        'standard':  "TT+/AK/AQs/KQs + some bluffs like A5s/A4s.",
        'high':      "88+/AQ+/AJs + bluffs like suited Ax/KQo/some suited connectors.",
        'very_high': "55+/AJ+/KQ + wide bluff range including suited connectors/broadway.",
    }
    return ranges.get(f3b_category, "Balanced range; adjust by position.")


@dataclass
class FoldTo3BetResult:
    fold_to_3bet: float
    bluff_size_bb: float
    pot_bb: float
    f3b_category: str
    exploit: str
    bluff_ev: float
    optimal_range: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_fold_to_3bet(
    fold_to_3bet: float = 0.60,
    bluff_size_bb: float = 9.0,
    pot_bb: float = 3.5,
) -> FoldTo3BetResult:
    cat = _fold_to_3bet_category(fold_to_3bet)
    exploit = EXPLOIT_VS_FOLD_TO_3BET[cat]
    ev = _bluff_3bet_ev(fold_to_3bet, bluff_size_bb, pot_bb)
    opt_range = _optimal_3bet_range(cat)

    tips = []
    tips.append(
        f"Breakeven fold % for typical bluff 3-bet sizing is ~{_BE_FOLD_TYPICAL:.0%}."
    )
    if fold_to_3bet > 0.65:
        tips.append(
            "Villain folds too much to 3-bets -- add suited connectors and Ax bluffs to range."
        )
    if fold_to_3bet < 0.50:
        tips.append(
            "Villain defends wide vs 3-bets -- cut bluffs; only 3-bet strong value hands."
        )
    if ev > 0:
        tips.append(
            f"Bluff 3-bet EV is +{ev:.1f} BB at current sizing -- profitable to bluff."
        )
    tips.append(
        "Position matters: 3-bet bluffs are more powerful in position (IP) after the 3-bet."
    )

    reasoning = (
        f"Fold to 3-bet={fold_to_3bet:.0%} ({cat}): exploit={exploit}. "
        f"Bluff EV={ev:+.1f} BB. Optimal range: {opt_range}"
    )
    verdict = exploit

    return FoldTo3BetResult(
        fold_to_3bet=fold_to_3bet,
        bluff_size_bb=bluff_size_bb,
        pot_bb=pot_bb,
        f3b_category=cat,
        exploit=exploit,
        bluff_ev=ev,
        optimal_range=opt_range,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def fold_to_3bet_one_liner(r: FoldTo3BetResult) -> str:
    return (
        f"[F3B f3b={r.fold_to_3bet:.0%}] "
        f"cat={r.f3b_category} exploit={r.exploit} bluff_ev={r.bluff_ev:+.1f}"
    )
