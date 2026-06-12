# -*- coding: utf-8 -*-
"""af_interpretation_guide.py -- Aggression Factor interpretation guide."""

from dataclasses import dataclass, field
from typing import List

AF_CATEGORY_THRESHOLDS: dict = {
    'passive':        (0.0, 1.0),
    'balanced':       (1.0, 2.5),
    'aggressive':     (2.5, 4.0),
    'very_aggressive':(4.0, 6.0),
    'maniac':         (6.0, float('inf')),
}

EXPLOIT_BY_AF_CATEGORY: dict = {
    'passive':         "Bet for value freely; rarely need to worry about check-raises.",
    'balanced':        "Play straightforwardly; exploit minor tendencies as they emerge.",
    'aggressive':      "Widen bluff-catching range; let them barrel off with bluffs.",
    'very_aggressive': "Call down wider on strong boards; trap with monster hands.",
    'maniac':          "Never fold strong draws; set traps and let the maniac pay off.",
}

STREET_AF_WEIGHT: dict = {
    'flop':  1.0,
    'turn':  1.2,
    'river': 1.4,
}


def _af_category(af: float) -> str:
    if af < 1.0:
        return 'passive'
    if af <= 2.5:
        return 'balanced'
    if af <= 4.0:
        return 'aggressive'
    if af <= 6.0:
        return 'very_aggressive'
    return 'maniac'


def _exploit_advice(af_category: str, street: str = 'flop') -> str:
    base = EXPLOIT_BY_AF_CATEGORY.get(af_category, "Observe more hands.")
    weight = STREET_AF_WEIGHT.get(street, 1.0)
    suffix = ""
    if weight >= 1.4:
        suffix = " (River AF is most reliable -- weight heavily.)"
    elif weight >= 1.2:
        suffix = " (Turn AF is well-weighted -- trust this read.)"
    return base + suffix


def _weighted_af(flop_af: float, turn_af: float, river_af: float) -> float:
    wf = STREET_AF_WEIGHT['flop']
    wt = STREET_AF_WEIGHT['turn']
    wr = STREET_AF_WEIGHT['river']
    total_weight = wf + wt + wr
    weighted = (flop_af * wf + turn_af * wt + river_af * wr) / total_weight
    return round(weighted, 3)


@dataclass
class AfInterpretationResult:
    flop_af: float
    turn_af: float
    river_af: float
    overall_af: float
    weighted_af: float
    af_category: str
    exploit_advice: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_af_interpretation(
    flop_af: float = 1.5,
    turn_af: float = 1.8,
    river_af: float = 2.0,
) -> AfInterpretationResult:
    overall = round((flop_af + turn_af + river_af) / 3.0, 3)
    w_af = _weighted_af(flop_af, turn_af, river_af)
    cat = _af_category(w_af)
    advice = _exploit_advice(cat, 'river')

    tips = []
    tips.append(
        "AF = (bets + raises) / calls; a value of 0 means pure calling -- total passivity."
    )
    if river_af > turn_af and river_af > flop_af:
        tips.append(
            "River AF highest -- villain polarizes heavily on river; respect big river bets."
        )
    if flop_af > 4.0:
        tips.append(
            "High flop AF -- villain fires a lot on flop; float more and re-evaluate on turn."
        )
    if w_af < 1.0:
        tips.append(
            "Passive player overall -- feel free to check-raise and steal with bluffs."
        )
    tips.append(
        "Postflop AF is more meaningful than overall AF -- focus on street-by-street reads."
    )

    reasoning = (
        f"Weighted AF={w_af} (flop={flop_af}/turn={turn_af}/river={river_af}) "
        f"category='{cat}'. {advice}"
    )
    verdict = cat

    return AfInterpretationResult(
        flop_af=flop_af,
        turn_af=turn_af,
        river_af=river_af,
        overall_af=overall,
        weighted_af=w_af,
        af_category=cat,
        exploit_advice=advice,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def af_one_liner(r: AfInterpretationResult) -> str:
    return (
        f"[AF flop={r.flop_af} turn={r.turn_af} river={r.river_af}] "
        f"wtd={r.weighted_af} cat={r.af_category}"
    )
