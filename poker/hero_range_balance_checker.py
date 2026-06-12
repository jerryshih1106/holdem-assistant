"""
Hero Range Balance Checker (hero_range_balance_checker.py)

Checks whether hero's betting range for a given spot is balanced
(correct value-to-bluff ratio) or exploitably unbalanced.

THEORY:
  A balanced range prevents villains from profitably exploiting you.
  For a given bet size X (fraction of pot):
    alpha = X/(1+X)  -- villain break-even fold frequency
    balanced bluff% = alpha  (fraction of betting range that should be bluffs)
    balanced value% = 1-alpha

  Example: 67% pot bet -> alpha = 0.40 -> 40% bluffs, 60% value in range.

  IMBALANCE TYPES:
  1. Too bluff-heavy: villain should call wide; exploit by always calling
  2. Too value-heavy: villain should fold to every bet; exploit by always folding
  3. Never bluffing: villain folds too much; steal more with any two cards
  4. Always bluffing: villain calls everything down

  PRACTICAL APPLICATION:
  Given hero's hand and street, estimate how many value vs bluff combos
  are in hero's range for this action, and determine if it's balanced.

  COMBO COUNTING:
  Value combos (simplified from specific hands):
    Nuts: 6 combos (AA etc) or board-specific
    Strong pairs: ~12 combos
    Sets: ~9 combos
    Two pair: ~16 combos
  Bluff combos (missed draws, air):
    Flush draws: ~9 combos
    Straight draws: ~8 combos
    Backdoor stuff: variable

  RANGE BALANCE SCORE (0-10):
  - 10: perfectly balanced
  - 7-9: slightly off, acceptable
  - 4-6: moderate imbalance, villain can adjust
  - 0-3: severe imbalance, easily exploited

DISTINCT FROM:
  gto_deviation.py:    Checks deviation from GTO frequencies
  frequency_mixing_helper.py: Decision for mixed strategy
  THIS MODULE:         VALUE-TO-BLUFF RATIO; combo counting;
                       exploitability score; specific adjustment advice.
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _alpha(bet_size_frac: float) -> float:
    """Villain's break-even fold frequency."""
    return round(bet_size_frac / (1.0 + bet_size_frac), 4)


def _balanced_bluff_pct(bet_size_frac: float) -> float:
    return _alpha(bet_size_frac)


def _balanced_value_pct(bet_size_frac: float) -> float:
    return round(1.0 - _alpha(bet_size_frac), 4)


def _balance_score(
    actual_bluff_pct: float,
    balanced_bluff_pct: float,
) -> float:
    """Score 0-10 where 10 is perfectly balanced."""
    deviation = abs(actual_bluff_pct - balanced_bluff_pct)
    score = max(0.0, 10.0 - deviation * 30.0)
    return round(score, 1)


def _imbalance_type(
    actual_bluff_pct: float,
    balanced_bluff_pct: float,
) -> str:
    diff = actual_bluff_pct - balanced_bluff_pct
    if abs(diff) <= 0.05:
        return 'balanced'
    elif diff > 0.20:
        return 'severely_too_bluff_heavy'
    elif diff > 0.05:
        return 'slightly_too_bluff_heavy'
    elif diff < -0.20:
        return 'severely_too_value_heavy'
    else:
        return 'slightly_too_value_heavy'


def _exploit_recommendation(imbalance: str) -> str:
    return {
        'balanced':               'Villain cannot profitably exploit; continue balanced strategy.',
        'severely_too_bluff_heavy':  'Villain should call every bet down; add more value hands or bluff less.',
        'slightly_too_bluff_heavy':  'Villain gains slightly by calling more; minor adjustment needed.',
        'severely_too_value_heavy':  'Villain should fold to every bet; add bluff combos or value bet less often.',
        'slightly_too_value_heavy':  'Villain gains by folding more; add a few bluff combos.',
    }.get(imbalance, 'Unknown imbalance; analyze further.')


@dataclass
class RangeBalanceResult:
    bet_size_frac: float
    actual_bluff_combos: int
    actual_value_combos: int
    total_combos: int
    actual_bluff_pct: float

    balanced_bluff_pct: float
    balanced_value_pct: float
    balance_score: float
    imbalance_type: str

    extra_bluff_combos_needed: int
    extra_value_combos_needed: int

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def check_range_balance(
    bet_size_frac: float = 0.67,
    bluff_combos: int = 8,
    value_combos: int = 15,
    street: str = 'river',
    hand_category: str = 'top_pair',
    position: str = 'ip',
) -> RangeBalanceResult:
    """
    Check whether hero's betting range is balanced for this spot.

    Args:
        bet_size_frac:  Bet size as fraction of pot (0.67 = 2/3 pot)
        bluff_combos:   Number of bluff combos in hero's betting range
        value_combos:   Number of value combos in hero's betting range
        street:         Current street
        hand_category:  Hero's hand category
        position:       'ip' / 'oop'

    Returns:
        RangeBalanceResult
    """
    total = bluff_combos + value_combos
    actual_bluff_pct = round(bluff_combos / max(1, total), 4)
    bal_bluff = _balanced_bluff_pct(bet_size_frac)
    bal_val = _balanced_value_pct(bet_size_frac)
    score = _balance_score(actual_bluff_pct, bal_bluff)
    imbalance = _imbalance_type(actual_bluff_pct, bal_bluff)

    balanced_bluffs_needed = round(bal_bluff * total)
    extra_bluff = max(0, balanced_bluffs_needed - bluff_combos)
    balanced_value_needed = round(bal_val * total)
    extra_value = max(0, balanced_value_needed - value_combos)

    verdict = (
        f'[RBC {street}|{position}|{bet_size_frac:.0%}pot] '
        f'score={score:.0f}/10 {imbalance} | '
        f'bluff={actual_bluff_pct:.0%}(need:{bal_bluff:.0%})'
    )

    reasoning = (
        f'Range balance check: {bet_size_frac:.0%}pot bet on {street} ({position.upper()}). '
        f'Combos: {value_combos} value + {bluff_combos} bluffs = {total} total. '
        f'Actual bluff%: {actual_bluff_pct:.0%}. '
        f'Balanced bluff%: {bal_bluff:.0%} (alpha for {bet_size_frac:.0%}pot). '
        f'Score: {score:.0f}/10. Imbalance: {imbalance}.'
    )

    tips = []

    tips.append(
        f'BALANCE SCORE: {score:.0f}/10. '
        f'Actual bluff%={actual_bluff_pct:.0%} vs needed {bal_bluff:.0%} '
        f'(alpha for {bet_size_frac:.0%}pot bet). '
        f'Imbalance: {imbalance}.'
    )

    tips.append(_exploit_recommendation(imbalance))

    if extra_bluff > 0:
        tips.append(
            f'ADD BLUFFS: Need {extra_bluff} more bluff combos for balance. '
            f'Current: {bluff_combos} bluffs, {value_combos} value. '
            f'Target: {balanced_bluffs_needed} bluffs per {value_combos} value.'
        )
    elif extra_value > 0:
        tips.append(
            f'ADD VALUE: Need {extra_value} more value combos for balance. '
            f'Or remove {-extra_bluff} bluff combos from range.'
        )
    else:
        tips.append(
            f'BALANCED: {bluff_combos} bluffs + {value_combos} value = '
            f'{actual_bluff_pct:.0%} bluff ratio (target: {bal_bluff:.0%}). '
            f'Villain cannot profitably deviate from calling exactly {1-bet_size_frac:.0%}.'
        )

    return RangeBalanceResult(
        bet_size_frac=bet_size_frac,
        actual_bluff_combos=bluff_combos,
        actual_value_combos=value_combos,
        total_combos=total,
        actual_bluff_pct=actual_bluff_pct,
        balanced_bluff_pct=bal_bluff,
        balanced_value_pct=bal_val,
        balance_score=score,
        imbalance_type=imbalance,
        extra_bluff_combos_needed=extra_bluff,
        extra_value_combos_needed=extra_value,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rbc_one_liner(r: RangeBalanceResult) -> str:
    return (
        f'[RBC {r.bet_size_frac:.0%}pot] '
        f'score={r.balance_score:.0f}/10 {r.imbalance_type} | '
        f'bluff={r.actual_bluff_pct:.0%}(vs {r.balanced_bluff_pct:.0%} ideal)'
    )
