"""
Steal Frequency Guide (steal_frequency_guide.py)

Calibrates blind steal frequency from late position based on fold-to-steal
stats, villain blind tendencies, and stack depth.

THEORY:
  BLIND STEAL:
  Opening from late position (BTN/CO/SB) when folded to, targeting dead money
  in the blinds. Profitable when: fold_equity * pot > open cost.

  BASELINE STEAL FREQUENCIES (vs average blinds):
  BTN: 50-55% (widest; best position postflop)
  CO:  32-36% (risk of LP callers still to act)
  SB:  40-44% (position disadvantage postflop; only BB to beat)
  HJ:  20-24% (tighter; MP/CO/BTN still to act)

  FOLD-TO-STEAL EXPLOITATION:
  BB folds >72%: increase steals significantly (bluffs auto-profitable)
  BB folds <38%: tighten up (BB defends/3bets; need hand quality)

  STACK DEPTH CONSIDERATIONS:
  Short blinds (<20BB): reshove risk; need stronger hand to steal
  Deep blinds (>80BB): position equity high; wider steal acceptable

  SIZING:
  Online: 2.2-2.5BB (rake-efficient; smaller pot OOP)
  Live:   3.0-4.0BB (weaker players; size for value)

DISTINCT FROM:
  steal_advisor.py:  When a specific spot is good for stealing
  blind_steal.py:    Steal EV and hand selection
  THIS MODULE:       HOW OFTEN to steal (frequency calibration);
                     fold-to-steal exploitation; stack-depth adjustments.
"""

from dataclasses import dataclass, field
from typing import List

BASELINE_STEAL_FREQ: dict = {
    'btn': 0.52,
    'co':  0.33,
    'hj':  0.22,
    'sb':  0.42,
}

BB_FOLD_TO_STEAL_ADJUSTMENT: dict = {
    'very_high': +0.12,
    'high':      +0.06,
    'standard':   0.00,
    'low':       -0.08,
    'very_low':  -0.15,
}

SB_FOLD_TO_STEAL_ADJUSTMENT: dict = {
    'very_high': +0.06,
    'high':      +0.03,
    'standard':   0.00,
    'low':       -0.04,
    'very_low':  -0.08,
}

FOLD_THRESHOLDS: dict = {
    'very_high': 0.72,
    'high':      0.62,
    'standard':  0.50,
    'low':       0.38,
    'very_low':  0.00,
}

STACK_DEPTH_MODIFIER: dict = {
    'deep':    +0.04,
    'medium':   0.00,
    'shallow': -0.06,
    'short':   -0.12,
}

VILLAIN_BB_STEAL_MODIFIER: dict = {
    'fish':            +0.08,
    'calling_station': -0.04,
    'nit':             +0.10,
    'lag':             -0.10,
    'rec':             +0.04,
    'reg':              0.00,
}

OPTIMAL_STEAL_SIZING: dict = {
    'btn': 2.3,
    'co':  2.5,
    'hj':  2.5,
    'sb':  3.0,
}


def _stack_depth_category(stack_bb: float) -> str:
    if stack_bb > 80:
        return 'deep'
    if stack_bb > 40:
        return 'medium'
    if stack_bb > 20:
        return 'shallow'
    return 'short'


def _fold_category(fold_pct: float) -> str:
    for cat, thresh in FOLD_THRESHOLDS.items():
        if fold_pct >= thresh:
            return cat
    return 'very_low'


def _optimal_steal_freq(
    position: str,
    bb_fold_to_steal: float,
    sb_fold_to_steal: float,
    stack_bb: float,
    villain_bb_type: str,
) -> float:
    base = BASELINE_STEAL_FREQ.get(position, 0.33)
    bb_cat = _fold_category(bb_fold_to_steal)
    sb_cat = _fold_category(sb_fold_to_steal)
    bb_adj = BB_FOLD_TO_STEAL_ADJUSTMENT.get(bb_cat, 0.00)
    sb_adj = SB_FOLD_TO_STEAL_ADJUSTMENT.get(sb_cat, 0.00) if position == 'btn' else 0.0
    depth_cat = _stack_depth_category(stack_bb)
    depth_adj = STACK_DEPTH_MODIFIER.get(depth_cat, 0.00)
    vil_adj = VILLAIN_BB_STEAL_MODIFIER.get(villain_bb_type, 0.00)
    freq = base + bb_adj + sb_adj + depth_adj + vil_adj
    return round(min(0.75, max(0.10, freq)), 3)


def _steal_status(actual: float, optimal: float) -> str:
    diff = actual - optimal
    if diff > 0.10:
        return 'OVER_STEALING_SIGNIFICANTLY'
    if diff > 0.05:
        return 'OVER_STEALING_SLIGHTLY'
    if diff < -0.10:
        return 'UNDER_STEALING_SIGNIFICANTLY'
    if diff < -0.05:
        return 'UNDER_STEALING_SLIGHTLY'
    return 'STEAL_FREQUENCY_OK'


@dataclass
class StealFrequencyResult:
    position: str
    bb_fold_to_steal: float
    sb_fold_to_steal: float
    stack_bb: float
    villain_bb_type: str
    actual_steal_freq: float

    optimal_steal_freq: float
    bb_fold_category: str
    depth_category: str
    steal_status: str
    recommended_sizing_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_steal_frequency(
    position: str = 'btn',
    bb_fold_to_steal: float = 0.60,
    sb_fold_to_steal: float = 0.55,
    stack_bb: float = 100.0,
    villain_bb_type: str = 'reg',
    actual_steal_freq: float = 0.50,
) -> StealFrequencyResult:
    """
    Calibrate blind steal frequency from late position.

    Args:
        position:          Hero's position ('btn','co','hj','sb')
        bb_fold_to_steal:  BB's fold-to-steal frequency (0-1); default 0.60
        sb_fold_to_steal:  SB's fold-to-steal frequency (0-1); default 0.55
        stack_bb:          Effective stack in BB; default 100
        villain_bb_type:   BB villain type ('fish','nit','lag','reg',etc.)
        actual_steal_freq: Hero's current steal frequency for calibration

    Returns:
        StealFrequencyResult
    """
    optimal = _optimal_steal_freq(position, bb_fold_to_steal, sb_fold_to_steal, stack_bb, villain_bb_type)
    bb_cat = _fold_category(bb_fold_to_steal)
    depth_cat = _stack_depth_category(stack_bb)
    status = _steal_status(actual_steal_freq, optimal)
    sizing = OPTIMAL_STEAL_SIZING.get(position, 2.5)

    verdict = (
        f'[STEAL {position}|bb_f2s={bb_fold_to_steal:.0%}|{villain_bb_type}] '
        f'optimal={optimal:.0%} actual={actual_steal_freq:.0%} status={status}'
    )

    reasoning = (
        f'Steal freq from {position}: BB folds {bb_fold_to_steal:.0%} ({bb_cat}), '
        f'stack={stack_bb:.0f}BB ({depth_cat}), BB type={villain_bb_type}. '
        f'base={BASELINE_STEAL_FREQ.get(position, 0.33):.0%} '
        f'bb_adj={BB_FOLD_TO_STEAL_ADJUSTMENT.get(bb_cat, 0):+.0%} '
        f'depth_adj={STACK_DEPTH_MODIFIER.get(depth_cat, 0):+.0%} '
        f'vil_adj={VILLAIN_BB_STEAL_MODIFIER.get(villain_bb_type, 0):+.0%}. '
        f'Optimal={optimal:.0%}. Status={status}. Sizing={sizing}BB.'
    )

    tips = []

    tips.append(
        f'Steal from {position}: optimal={optimal:.0%} (size {sizing}BB). '
        f'BB folds {bb_fold_to_steal:.0%} ({bb_cat}). '
        f'{"Widen range -- BB over-folds." if bb_cat in ("very_high", "high") else "Tighten range -- BB defends wide." if bb_cat in ("low", "very_low") else "Standard steal range; adapt postflop."}'
    )

    if 'OVER_STEAL' in status:
        tips.append(
            f'OVER-STEALING: {actual_steal_freq:.0%} vs optimal {optimal:.0%}. '
            f'vs {villain_bb_type} who defends {1-bb_fold_to_steal:.0%} of steals. '
            f'Cut weakest holdings: 72o, 84o, offsuit no-playability hands.'
        )
    elif 'UNDER_STEAL' in status:
        tips.append(
            f'UNDER-STEALING: {actual_steal_freq:.0%} vs optimal {optimal:.0%}. '
            f'BB folds {bb_fold_to_steal:.0%} -- leaving money on table. '
            f'Add: suited 1-gappers, weak Ax, any two from {position} with position.'
        )
    else:
        tips.append(
            f'Steal frequency calibrated ({actual_steal_freq:.0%} ~ optimal {optimal:.0%}). '
            f'Stack depth {stack_bb:.0f}BB ({depth_cat}): '
            f'{"watch for reshoves -- need hand quality" if depth_cat == "short" else "standard postflop depth; position edge"}. '
            f'vs {villain_bb_type}: focus on postflop execution.'
        )

    if villain_bb_type == 'nit':
        tips.append(
            f'vs NIT in BB: Steal at will -- nit folds ~{bb_fold_to_steal:.0%}+. '
            f'Use min-size {sizing}BB; bet small on most flops (nit folds without top pair+). '
            f'NIT signal: folds > 3-bets; easy to read their continuing range.'
        )
    elif villain_bb_type == 'lag':
        tips.append(
            f'vs LAG in BB: Reduce steals -- LAG 3-bets wide. '
            f'Value steal only: A9+, KTs+, 77+. '
            f'When LAG 3-bets: have 4-bet/shove range ready (QQ+/AK).'
        )

    return StealFrequencyResult(
        position=position,
        bb_fold_to_steal=bb_fold_to_steal,
        sb_fold_to_steal=sb_fold_to_steal,
        stack_bb=stack_bb,
        villain_bb_type=villain_bb_type,
        actual_steal_freq=actual_steal_freq,
        optimal_steal_freq=optimal,
        bb_fold_category=bb_cat,
        depth_category=depth_cat,
        steal_status=status,
        recommended_sizing_bb=sizing,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sfg_one_liner(r: StealFrequencyResult) -> str:
    return (
        f'[STEAL {r.position}|{r.villain_bb_type}] '
        f'optimal={r.optimal_steal_freq:.0%} actual={r.actual_steal_freq:.0%} {r.steal_status}'
    )
