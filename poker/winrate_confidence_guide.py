# -*- coding: utf-8 -*-
"""winrate_confidence_guide.py -- Statistical confidence intervals for poker winrates."""

import math
from dataclasses import dataclass, field
from typing import List

STD_DEV_BY_GAME_TYPE: dict = {
    'nl_cash': 100.0,
    'mtt': 150.0,
    'sng': 120.0,
}

CONFIDENCE_LEVEL: dict = {
    90: 1.645,
    95: 1.96,
    99: 2.576,
}

SAMPLE_CATEGORY_THRESHOLDS: dict = {
    'tiny':   5000,
    'small':  20000,
    'medium': 50000,
    'large':  100000,
    'huge':   float('inf'),
}

HANDS_NEEDED_CONFIRMATION: dict = {
    'nl_cash': 100000,
    'mtt':     200000,
    'sng':     80000,
}


def _sample_category(n_hands: int) -> str:
    if n_hands < 5000:
        return 'tiny'
    if n_hands < 20000:
        return 'small'
    if n_hands < 50000:
        return 'medium'
    if n_hands < 100000:
        return 'large'
    return 'huge'


def _standard_error(std_dev: float, n_hands: int) -> float:
    if n_hands <= 0:
        return 999.0
    return std_dev / math.sqrt(n_hands / 100.0)


def _confidence_interval(winrate: float, se: float, z: float):
    lo = round(winrate - z * se, 2)
    hi = round(winrate + z * se, 2)
    return lo, hi


def _is_positive_confirmed(ci_lower: float) -> bool:
    return ci_lower > 0.0


def _hands_needed(winrate: float, std_dev: float, z: float, target_ci_lower: float = 0.0) -> int:
    """Return minimum hands so that CI lower >= target_ci_lower."""
    if winrate <= target_ci_lower:
        return 999999
    # winrate - z * std_dev / sqrt(n/100) >= target_ci_lower
    # z * std_dev / sqrt(n/100) <= winrate - target_ci_lower
    # sqrt(n/100) >= z * std_dev / (winrate - target_ci_lower)
    # n >= 100 * (z * std_dev / (winrate - target_ci_lower))^2
    ratio = z * std_dev / (winrate - target_ci_lower)
    return int(math.ceil(100.0 * ratio * ratio))


@dataclass
class WinrateConfidenceResult:
    n_hands: int
    winrate_bb100: float
    std_dev_bb100: float
    confidence_level: int
    sample_category: str
    se_bb100: float
    ci_lower: float
    ci_upper: float
    is_positive_confirmed: bool
    hands_still_needed: int
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_winrate_confidence(
    n_hands: int = 10000,
    winrate_bb100: float = 5.0,
    game_type: str = 'nl_cash',
    confidence_level: int = 95,
) -> WinrateConfidenceResult:
    std_dev = STD_DEV_BY_GAME_TYPE.get(game_type, 100.0)
    z = CONFIDENCE_LEVEL.get(confidence_level, 1.96)
    se = _standard_error(std_dev, n_hands)
    ci_lo, ci_hi = _confidence_interval(winrate_bb100, se, z)
    cat = _sample_category(n_hands)
    confirmed = _is_positive_confirmed(ci_lo)
    needed_total = _hands_needed(winrate_bb100, std_dev, z)
    hands_still = max(0, needed_total - n_hands)

    tips = []
    tips.append(
        "Use EV-adjusted winrate (not raw cash) to reduce luck distortion."
    )
    if cat in ('tiny', 'small'):
        tips.append(
            "Sample too small for conclusions -- keep recording hands."
        )
    if not confirmed and winrate_bb100 > 0:
        tips.append(
            f"Need ~{hands_still} more hands to statistically confirm positive winrate."
        )
    if cat in ('medium', 'large', 'huge'):
        tips.append(
            "Large sample: review sessions for leaks rather than blaming variance."
        )
    tips.append(
        "Play more tables or sessions to accumulate sample size faster."
    )

    if confirmed:
        verdict = 'positive_confirmed'
        reasoning = (
            f"{confidence_level}% CI [{ci_lo},{ci_hi}] BB/100 is entirely above 0 -- "
            f"positive winrate statistically confirmed over {n_hands} hands."
        )
    elif ci_hi < 0:
        verdict = 'negative_confirmed'
        reasoning = (
            f"{confidence_level}% CI [{ci_lo},{ci_hi}] BB/100 is entirely below 0 -- "
            f"losing player over {n_hands} hands; review leaks immediately."
        )
    else:
        verdict = 'uncertain'
        reasoning = (
            f"{confidence_level}% CI [{ci_lo},{ci_hi}] BB/100 straddles 0 -- "
            f"cannot confirm positive or negative winrate with {n_hands} hands."
        )

    return WinrateConfidenceResult(
        n_hands=n_hands,
        winrate_bb100=winrate_bb100,
        std_dev_bb100=std_dev,
        confidence_level=confidence_level,
        sample_category=cat,
        se_bb100=round(se, 3),
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        is_positive_confirmed=confirmed,
        hands_still_needed=hands_still,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def winrate_confidence_one_liner(r: WinrateConfidenceResult) -> str:
    return (
        f"[WCG n={r.n_hands} wr={r.winrate_bb100} BB/100] "
        f"{r.confidence_level}CI=[{r.ci_lower},{r.ci_upper}] "
        f"confirmed={'Y' if r.is_positive_confirmed else 'N'}"
    )
