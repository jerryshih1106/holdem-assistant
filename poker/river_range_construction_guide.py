"""
River Range Construction Guide (river_range_construction_guide.py)

Teaches how to BUILD a balanced river betting range: which hands go in the
value range, bluff range, and check/showdown range. Balanced river ranges
prevent exploitation by villain.

THEORY:
  RIVER RANGE STRUCTURE:
  A balanced river betting range consists of:
  1. VALUE BETS: Hands that beat villain's calling range (extract value)
  2. BLUFFS: Hands that cannot win at showdown (pure bluffs for balance)
  3. CHECK-CALL: Medium-strength hands (SDV to call but not lead)
  4. CHECK-FOLD: Weak hands with no showdown value (give up)

  OPTIMAL VALUE:BLUFF RATIO:
  For balanced betting: value:bluff ratio = (1-alpha)/alpha where alpha=bet/(pot+bet)
  - Half-pot bet: alpha=1/3; ratio=2:1 (2 value for every 1 bluff)
  - Pot-size bet: alpha=1/2; ratio=1:1 (equal value and bluff)
  - 2x pot:       alpha=2/3; ratio=0.5:1 (more bluffs than value)

  HAND SELECTION FOR RIVER VALUE RANGE:
  1. Start with nuts and near-nuts (mandatory value bets)
  2. Add strong hands that beat most of villain's calling range
  3. Stop when adding the next hand would be thin value (equity < 60%)

  HAND SELECTION FOR RIVER BLUFF RANGE:
  1. Choose hands with BEST blockers to villain's calling range
  2. Prefer missed draws with top blockers (Ace-high flush draw missed = good bluff)
  3. Avoid bluffing with hands that have showdown value
  4. Count needed bluffs based on ratio, then rank by blocker quality

  BOARD TEXTURE EFFECTS ON RIVER RANGES:
  - Dry river: More polarized; small ranges; fewer bluff candidates
  - Wet (flush completes): More value hands; more missed draws = bluff candidates
  - Board pairs river: Trips+ become value range; smaller

  POSITION EFFECTS:
  - OOP: Must lead (donk) with balanced range; 30-40% of hands
  - IP: Check-call with some strong hands; bet with value+bluffs

DISTINCT FROM:
  river_decision.py:            River action decisions
  river_value.py:               River value bet sizing
  river_bluff.py:               River bluff selection
  river_polarization_guide.py:  Polarization guide
  THIS MODULE:                  RANGE CONSTRUCTION; complete range assignment;
                                value/bluff ratio calculation; hand categorization.
"""

from dataclasses import dataclass, field
from typing import List, Dict


VALUE_RANGE_THRESHOLDS: dict = {
    0.33: 0.62,   # half-pot bet: need 62%+ equity to value bet
    0.50: 0.65,   # standard: need 65%+ equity
    0.67: 0.68,   # 2/3 pot
    1.00: 0.72,   # pot bet
    1.50: 0.77,   # overbet
}

BLUFF_RATIO_BY_ALPHA: dict = {
    0.25: 3.00,   # small bet: 3 value per 1 bluff
    0.33: 2.00,   # half-pot
    0.40: 1.50,
    0.50: 1.00,   # pot = 1:1
    0.60: 0.67,
    0.67: 0.50,
}

HAND_CATEGORIES_RIVER: dict = {
    'nuts':               {'equity': 0.95, 'sdv': 0.95, 'bluff_blocker': 0.0},
    'strong_value':       {'equity': 0.80, 'sdv': 0.80, 'bluff_blocker': 0.1},
    'top_pair_gk':        {'equity': 0.65, 'sdv': 0.65, 'bluff_blocker': 0.1},
    'top_pair_wk':        {'equity': 0.54, 'sdv': 0.52, 'bluff_blocker': 0.1},
    'middle_pair':        {'equity': 0.44, 'sdv': 0.42, 'bluff_blocker': 0.1},
    'bottom_pair':        {'equity': 0.30, 'sdv': 0.28, 'bluff_blocker': 0.1},
    'missed_flush_ace':   {'equity': 0.08, 'sdv': 0.05, 'bluff_blocker': 0.85},
    'missed_flush_king':  {'equity': 0.08, 'sdv': 0.05, 'bluff_blocker': 0.70},
    'missed_oesd_ace':    {'equity': 0.10, 'sdv': 0.08, 'bluff_blocker': 0.75},
    'missed_oesd':        {'equity': 0.10, 'sdv': 0.05, 'bluff_blocker': 0.40},
    'air':                {'equity': 0.05, 'sdv': 0.02, 'bluff_blocker': 0.20},
}


def _alpha(bet_frac: float) -> float:
    return round(bet_frac / (1.0 + bet_frac), 3)


def _bluff_ratio(bet_frac: float) -> float:
    a = _alpha(bet_frac)
    keys = sorted(BLUFF_RATIO_BY_ALPHA.keys())
    for k in keys:
        if a <= k:
            return BLUFF_RATIO_BY_ALPHA[k]
    return BLUFF_RATIO_BY_ALPHA[max(keys)]


def _value_threshold(bet_frac: float) -> float:
    keys = sorted(VALUE_RANGE_THRESHOLDS.keys())
    for k in reversed(keys):
        if bet_frac >= k:
            return VALUE_RANGE_THRESHOLDS[k]
    return 0.62


def _assign_hand_category(
    hand: str,
    bet_frac: float,
    n_value_hands: int,
    n_bluffs_needed: int,
    position: str,
) -> str:
    props = HAND_CATEGORIES_RIVER.get(hand, {'equity': 0.50, 'sdv': 0.45, 'bluff_blocker': 0.2})
    vt = _value_threshold(bet_frac)

    if props['equity'] >= vt:
        return 'VALUE_BET'
    if props['sdv'] >= 0.40:
        return 'CHECK_CALL'
    if props['bluff_blocker'] >= 0.60 and n_bluffs_needed > 0:
        return 'BLUFF'
    if props['sdv'] >= 0.20:
        return 'CHECK_FOLD'
    return 'BLUFF' if props['bluff_blocker'] >= 0.30 else 'CHECK_FOLD'


@dataclass
class RiverRangeResult:
    bet_frac: float
    position: str
    alpha: float
    bluff_ratio: float
    value_threshold: float

    range_assignments: Dict[str, str]
    n_value: int
    n_bluffs: int
    n_check_call: int
    n_check_fold: int

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_river_range_construction(
    bet_frac: float = 0.67,
    position: str = 'oop',
    pot_bb: float = 30.0,
    hands_in_range: List[str] = None,
) -> RiverRangeResult:
    """
    Construct a balanced river betting range with correct value:bluff ratio.

    Args:
        bet_frac:       Planned bet size as fraction of pot (0.33-1.50)
        position:       'ip' or 'oop'
        pot_bb:         Current pot in BB
        hands_in_range: List of hand categories to assign (uses full list if None)

    Returns:
        RiverRangeResult
    """
    if hands_in_range is None:
        hands_in_range = list(HAND_CATEGORIES_RIVER.keys())

    a = _alpha(bet_frac)
    br = _bluff_ratio(bet_frac)
    vt = _value_threshold(bet_frac)

    value_hands = [h for h in hands_in_range
                   if HAND_CATEGORIES_RIVER.get(h, {}).get('equity', 0) >= vt]
    n_value = len(value_hands)
    n_bluffs_needed = max(0, round(n_value / br))

    bluff_candidates = sorted(
        [h for h in hands_in_range
         if HAND_CATEGORIES_RIVER.get(h, {}).get('equity', 0) < 0.25],
        key=lambda h: HAND_CATEGORIES_RIVER.get(h, {}).get('bluff_blocker', 0),
        reverse=True
    )
    bluff_hands = bluff_candidates[:n_bluffs_needed]

    assignments = {}
    for hand in hands_in_range:
        props = HAND_CATEGORIES_RIVER.get(hand, {})
        if hand in value_hands:
            assignments[hand] = 'VALUE_BET'
        elif hand in bluff_hands:
            assignments[hand] = 'BLUFF'
        elif props.get('sdv', 0) >= 0.40:
            assignments[hand] = 'CHECK_CALL'
        else:
            assignments[hand] = 'CHECK_FOLD'

    n_bluffs   = sum(1 for v in assignments.values() if v == 'BLUFF')
    n_check_call  = sum(1 for v in assignments.values() if v == 'CHECK_CALL')
    n_check_fold  = sum(1 for v in assignments.values() if v == 'CHECK_FOLD')

    verdict = (
        f'[RRC {bet_frac:.0%}pot|{position.upper()}] '
        f'value={n_value} bluff={n_bluffs} '
        f'ratio={br:.1f}:1 alpha={a:.0%} threshold={vt:.0%}'
    )

    reasoning = (
        f'River range construction: {bet_frac:.0%}pot ({position.upper()}). '
        f'Alpha={a:.0%}; target bluff ratio={br:.1f}:1. '
        f'Value threshold={vt:.0%}. '
        f'Value={n_value}; bluffs={n_bluffs}; check-call={n_check_call}; check-fold={n_check_fold}.'
    )

    tips = []

    tips.append(
        f'RIVER RANGE: {bet_frac:.0%}pot bet -- alpha={a:.0%}. '
        f'Target ratio: {br:.1f} value hands per bluff. '
        f'Value threshold: {vt:.0%} equity. '
        f'Assigned: {n_value} value, {n_bluffs} bluffs, {n_check_call} check-call, {n_check_fold} check-fold.'
    )

    tips.append(
        f'BLUFF SELECTION: Choose missed draws with best blockers to villain range. '
        f'Missed flush with Ace blocker > missed straight > air. '
        f'Never bluff with hands that have showdown value ({vt-0.15:.0%}+ equity).'
    )

    if n_bluffs < n_bluffs_needed:
        tips.append(
            f'BLUFF SHORTAGE: Only {n_bluffs} bluff candidates vs {n_bluffs_needed} needed. '
            f'Your range may be under-bluffed ({bet_frac:.0%}pot bet). '
            f'Consider smaller bet size or reduce bet frequency.'
        )
    elif n_bluffs > n_bluffs_needed + 1:
        tips.append(
            f'OVER-BLUFFING RISK: {n_bluffs} bluffs vs {n_bluffs_needed} needed. '
            f'Reduce to {n_bluffs_needed} bluffs to avoid being exploitable.'
        )

    if position == 'oop':
        tips.append(
            f'OOP RIVER RANGE: Lead betting OOP requires strong balanced range. '
            f'Check-call with top_pair_wk and middle_pair vs {bet_frac:.0%}pot bets; '
            f'lead only with value+ and selected bluffs.'
        )

    return RiverRangeResult(
        bet_frac=bet_frac,
        position=position,
        alpha=a,
        bluff_ratio=br,
        value_threshold=vt,
        range_assignments=assignments,
        n_value=n_value,
        n_bluffs=n_bluffs,
        n_check_call=n_check_call,
        n_check_fold=n_check_fold,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rrc_one_liner(r: RiverRangeResult) -> str:
    return (
        f'[RRC {r.bet_frac:.0%}pot|{r.position.upper()}] '
        f'value={r.n_value} bluff={r.n_bluffs} '
        f'ratio={r.bluff_ratio:.1f}:1 alpha={r.alpha:.0%}'
    )
