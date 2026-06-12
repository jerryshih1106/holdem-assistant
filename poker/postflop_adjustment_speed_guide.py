"""
Postflop Adjustment Speed Guide (postflop_adjustment_speed_guide.py)

Determines how quickly to adjust exploitative strategy based on sample size
of reads. Prevents over-adjusting on small samples while enabling profitable
exploitation when reads are confirmed.

THEORY:
  WHY SAMPLE SIZE MATTERS:
  A villain who check-raises twice might: (a) be a rare check-raiser, or
  (b) have been dealt strong hands twice. Two observations is insufficient.
  Over-adjusting on small samples = being manipulated / random variance.

  SAMPLE SIZE FOR ADJUSTMENT:
  <10 hands:  No adjustment. Stay GTO/default. Too little data.
  10-20 hands: Tiny adjustment (5%). Single clear pattern observed.
  20-40 hands: Moderate adjustment (10-15%). Pattern emerging.
  40-70 hands: Meaningful adjustment (15-20%). Confident in read.
  70-100 hands: Strong adjustment (20-25%). Well-established pattern.
  100+ hands:   Full exploit (25-30%+). High confidence.

  VILLAIN TYPE ADJUSTMENT SPEED:
  Fish: adjust faster (fish patterns stable; they don't adapt)
  Nit: adjust faster (nit patterns stable; always nitty)
  Reg: adjust slower (regs may notice and counter-adapt)
  LAG: adjust very slowly (LAG adapts quickly; may counter-exploit)

  ADJUSTMENT MAGNITUDE CAPS:
  Max adjustment vs nit/fish: 25% (stable players)
  Max adjustment vs reg: 15% (may notice)
  Max adjustment vs LAG: 10% (likely to counter)

  TYPES OF READS:
  Fold-to-cbet: easy to exploit; adjust quickly
  Check-raise frequency: harder to exploit; adjust moderately
  Showdown tendencies: strongest for adjustment; adjust based on full data

DISTINCT FROM:
  villain_adaptation_tracker.py: Tracks villain adjustments to you
  session_exploit_tracker.py:    Session-level exploit tracking
  player_profiler.py:            Building villain profiles
  THIS MODULE:                   HOW QUICKLY to adjust based on sample;
                                 sample size thresholds; adjustment magnitude caps.
"""

from dataclasses import dataclass, field
from typing import List

SAMPLE_SIZE_ADJUSTMENT_MAGNITUDE: dict = {
    'tiny':     0.05,
    'small':    0.10,
    'medium':   0.15,
    'large':    0.20,
    'very_large': 0.25,
    'confident': 0.30,
}

SAMPLE_SIZE_THRESHOLDS: dict = {
    'tiny':      10,
    'small':     20,
    'medium':    40,
    'large':     70,
    'very_large': 100,
    'confident': 9999,
}

VILLAIN_ADAPTATION_SPEED_MODIFIER: dict = {
    'fish':            +0.08,
    'calling_station': +0.06,
    'nit':             +0.06,
    'lag':             -0.08,
    'rec':             +0.04,
    'reg':             -0.03,
}

MAX_ADJUSTMENT_BY_VILLAIN: dict = {
    'fish':            0.30,
    'calling_station': 0.30,
    'nit':             0.25,
    'lag':             0.10,
    'rec':             0.25,
    'reg':             0.15,
}

READ_TYPE_CONFIDENCE_MULTIPLIER: dict = {
    'fold_to_cbet':        1.20,
    'check_raise_freq':    0.85,
    'showdown_tendency':   1.30,
    'bet_sizing_tell':     0.90,
    'timing_tell':         0.70,
    'general_tendency':    1.00,
}

ADJUSTMENT_QUALITY_THRESHOLD: float = 0.50


def _sample_category(n_observations: int) -> str:
    for cat, thresh in SAMPLE_SIZE_THRESHOLDS.items():
        if n_observations <= thresh:
            return cat
    return 'confident'


def _adjustment_magnitude(
    n_observations: int,
    villain_type: str,
    read_type: str,
    read_confidence: float,
) -> float:
    cat = _sample_category(n_observations)
    base = SAMPLE_SIZE_ADJUSTMENT_MAGNITUDE.get(cat, 0.15)
    vil_mod = VILLAIN_ADAPTATION_SPEED_MODIFIER.get(villain_type, 0.0)
    confidence_mult = READ_TYPE_CONFIDENCE_MULTIPLIER.get(read_type, 1.0) * read_confidence
    raw = (base + vil_mod) * confidence_mult
    max_adj = MAX_ADJUSTMENT_BY_VILLAIN.get(villain_type, 0.20)
    return round(min(max_adj, max(0.0, raw)), 3)


def _exploit_recommendation(adj_magnitude: float, read_confidence: float) -> str:
    if adj_magnitude <= 0.05 or read_confidence < 0.30:
        return 'STAY_GTO_INSUFFICIENT_DATA'
    if adj_magnitude <= 0.10:
        return 'SMALL_EXPLOIT_TENTATIVE'
    if adj_magnitude <= 0.18:
        return 'MODERATE_EXPLOIT'
    return 'STRONG_EXPLOIT_HIGH_CONFIDENCE'


@dataclass
class PostflopAdjustmentSpeedResult:
    n_observations: int
    villain_type: str
    read_type: str
    read_confidence: float
    current_deviation: float

    sample_category: str
    recommended_magnitude: float
    exploit_recommendation: str
    max_allowed_magnitude: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_postflop_adjustment_speed(
    n_observations: int = 20,
    villain_type: str = 'reg',
    read_type: str = 'fold_to_cbet',
    read_confidence: float = 0.70,
    current_deviation: float = 0.10,
) -> PostflopAdjustmentSpeedResult:
    """
    Determine appropriate adjustment magnitude based on sample size and read quality.

    Args:
        n_observations:    Number of hands/spots observed supporting the read
        villain_type:      Villain type ('fish','nit','lag','reg', etc.)
        read_type:         Type of read ('fold_to_cbet','check_raise_freq',
                           'showdown_tendency','bet_sizing_tell','timing_tell','general_tendency')
        read_confidence:   Confidence in read accuracy (0-1; 0.5=uncertain, 0.9=very confident)
        current_deviation: Current exploitative deviation from GTO (-0.3 to +0.3)

    Returns:
        PostflopAdjustmentSpeedResult
    """
    cat = _sample_category(n_observations)
    adj = _adjustment_magnitude(n_observations, villain_type, read_type, read_confidence)
    rec = _exploit_recommendation(adj, read_confidence)
    max_adj = MAX_ADJUSTMENT_BY_VILLAIN.get(villain_type, 0.20)

    verdict = (
        f'[PAS n={n_observations}|{villain_type}|{read_type}] '
        f'sample={cat} adj={adj:.0%} rec={rec}'
    )

    reasoning = (
        f'Adjustment speed: n={n_observations} obs ({cat}). '
        f'base_adj={SAMPLE_SIZE_ADJUSTMENT_MAGNITUDE.get(cat, 0.15):.0%} '
        f'vil_mod={VILLAIN_ADAPTATION_SPEED_MODIFIER.get(villain_type, 0):+.0%} '
        f'read_mult={READ_TYPE_CONFIDENCE_MULTIPLIER.get(read_type, 1.0):.2f}x '
        f'confidence={read_confidence:.0%}. '
        f'Recommended adj={adj:.0%}. Max vs {villain_type}={max_adj:.0%}. '
        f'Rec={rec}.'
    )

    tips = []

    tips.append(
        f'Adjustment speed: {n_observations} obs ({cat} sample) vs {villain_type}. '
        f'Recommended adjustment magnitude: {adj:.0%} from GTO baseline. '
        f'{rec}. '
        f'{"Adjust quickly vs fish/nit (stable patterns)" if villain_type in ("fish", "nit") else "Adjust slowly vs LAG/reg (they counter-adapt)" if villain_type in ("lag", "reg") else "Standard adjustment speed"}.'
    )

    if cat in ('tiny', 'small') or adj <= 0.05:
        tips.append(
            f'SMALL SAMPLE ({n_observations} obs): Stay near GTO. '
            f'{"Do not adjust yet -- too little data for reliable read" if n_observations < 10 else "Tiny adjustment only (5%); gather more data"}. '
            f'Target: {40 if villain_type in ("reg", "lag") else 20} obs before meaningful adjustment vs {villain_type}.'
        )
    elif adj >= 0.18:
        tips.append(
            f'STRONG EXPLOIT ({adj:.0%} adj): {n_observations} obs is sufficient. '
            f'Read type {read_type} confidence={read_confidence:.0%}: reliable pattern. '
            f'Apply full exploit vs {villain_type}. '
            f'Monitor for counter-adaptation ({"high risk" if villain_type in ("reg", "lag") else "low risk"}).'
        )
    else:
        tips.append(
            f'MODERATE EXPLOIT ({adj:.0%}): building confidence with {n_observations} obs. '
            f'Read type {read_type}: {"reliable (showdown data is gold)" if "showdown" in read_type else "moderate reliability"}. '
            f'Increase adjustment as sample grows; max {max_adj:.0%} vs {villain_type}.'
        )

    tips.append(
        f'Current deviation={current_deviation:.0%} vs recommended {adj:.0%}. '
        f'{"Over-exploiting -- reduce back toward GTO" if current_deviation > adj + 0.05 else "Under-exploiting -- can increase deviation" if current_deviation < adj - 0.05 else "Well-calibrated -- maintain current adjustment"}. '
        f'Read type {read_type}: mult={READ_TYPE_CONFIDENCE_MULTIPLIER.get(read_type, 1.0):.2f}x '
        f'({"high confidence metric" if READ_TYPE_CONFIDENCE_MULTIPLIER.get(read_type, 1.0) >= 1.20 else "low confidence metric -- use with caution"}).'
    )

    return PostflopAdjustmentSpeedResult(
        n_observations=n_observations,
        villain_type=villain_type,
        read_type=read_type,
        read_confidence=read_confidence,
        current_deviation=current_deviation,
        sample_category=cat,
        recommended_magnitude=adj,
        exploit_recommendation=rec,
        max_allowed_magnitude=max_adj,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pas_one_liner(r: PostflopAdjustmentSpeedResult) -> str:
    return (
        f'[PAS n={r.n_observations}|{r.villain_type}|{r.read_type}] '
        f'adj={r.recommended_magnitude:.0%} {r.exploit_recommendation}'
    )
