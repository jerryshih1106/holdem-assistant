"""
Hero Fold Frequency Guide (hero_fold_frequency_guide.py)

MDF-based guide for how often hero should fold to villain's bet.
Minimum Defense Frequency (MDF) = 1/(1+bet_frac): fold MORE than (1-MDF) and
villain's bluffs become automatically profitable.

THEORY:
  MINIMUM DEFENSE FREQUENCY (MDF):
  MDF = pot / (pot + bet) = 1 / (1 + bet_fraction)
  Hero must call/raise at least MDF of their range to prevent villain from
  profitably bluffing with any two cards.

  Example: Villain bets 75% pot. MDF = 1/(1+0.75) = 57%.
  Hero must continue with 57% of their range. Max fold = 43%.

  ADJUSTING FOLD FREQUENCY:
  - vs Tight villain (nit): can fold MORE than MDF (nit rarely bluffs)
  - vs LAG/maniac: fold LESS than MDF (extra bluffs make villain's range weaker)
  - Streets: MDF same formula but applies to that street's betting size

  HAND CATEGORIES TO FOLD:
  Working from weakest up, fold until you hit the MDF requirement:
  1. Fold air/bottom pair first
  2. Fold bluff catchers with low SDV
  3. Keep all draws (equity realizers)
  4. Keep all medium+ pairs and better

  OVER-FOLDING CONSEQUENCES:
  If hero folds too much (>1-MDF), any two cards become profitable bluffs.
  If hero calls too much (<1-MDF), hero loses too much to value bets.
  GTO play: fold exactly at (1-MDF) with worst hands.

DISTINCT FROM:
  call_threshold.py:      When individual hands should call
  mdf_calculator.py:      Raw MDF calculations (if exists)
  check_call_line_guide.py: Check-call line execution
  THIS MODULE:            FOLD FREQUENCY calibration across entire range;
                          which hand categories to fold; over/under-fold detection.
"""

from dataclasses import dataclass, field
from typing import List, Dict


VILLAIN_BLUFF_ADJUSTMENT: dict = {
    'fish':            -0.03,
    'calling_station': +0.06,
    'rec':             -0.01,
    'nit':             +0.12,
    'lag':             -0.08,
    'reg':              0.00,
}

HAND_SDV_THRESHOLDS: dict = {
    'nuts':          0.95,
    'strong_value':  0.80,
    'two_pair':      0.78,
    'top_pair_gk':   0.65,
    'top_pair_wk':   0.53,
    'overpair':      0.70,
    'middle_pair':   0.44,
    'bottom_pair':   0.28,
    'flush_draw':    0.20,
    'oesd':          0.18,
    'gutshot':       0.10,
    'bluff_catcher': 0.30,
    'air':           0.05,
}

STREET_FOLD_MODIFIER: dict = {
    'flop':  0.95,
    'turn':  1.00,
    'river': 1.10,
}


def _mdf(bet_frac: float) -> float:
    return round(1.0 / (1.0 + bet_frac), 3)


def _max_fold_freq(bet_frac: float, villain_type: str, street: str) -> float:
    base_fold = 1.0 - _mdf(bet_frac)
    vil_adj = VILLAIN_BLUFF_ADJUSTMENT.get(villain_type, 0.00)
    str_mod = STREET_FOLD_MODIFIER.get(street, 1.00)
    adjusted_fold = (base_fold + vil_adj) * str_mod
    return round(min(0.85, max(0.05, adjusted_fold)), 3)


def _hands_to_fold(max_fold: float) -> List[str]:
    sdv_sorted = sorted(HAND_SDV_THRESHOLDS.items(), key=lambda x: x[1])
    cumulative = 0.0
    to_fold = []
    total_hands = len(sdv_sorted)
    fold_count = max_fold * total_hands
    for hand, sdv in sdv_sorted:
        if cumulative < fold_count:
            to_fold.append(hand)
            cumulative += 1
        else:
            break
    return to_fold


def _overfold_warning(actual_fold: float, max_fold: float) -> str:
    diff = actual_fold - max_fold
    if diff >= 0.15:
        return 'SEVERE_OVERFOLD'
    if diff >= 0.08:
        return 'SIGNIFICANT_OVERFOLD'
    if diff >= 0.03:
        return 'MILD_OVERFOLD'
    if diff <= -0.10:
        return 'UNDERFOLD_CALLING_TOO_MUCH'
    return 'FOLD_FREQUENCY_OK'


@dataclass
class HeroFoldFrequencyResult:
    bet_frac: float
    villain_type: str
    street: str
    actual_fold_freq: float

    mdf: float
    max_fold_freq: float
    hands_to_fold: List[str]
    fold_status: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_hero_fold_frequency(
    bet_frac: float = 0.67,
    villain_type: str = 'reg',
    street: str = 'flop',
    actual_fold_freq: float = 0.45,
) -> HeroFoldFrequencyResult:
    """
    Evaluate hero's fold frequency vs villain's bet and give guidance.

    Args:
        bet_frac:          Villain bet as fraction of pot (0.5 = half pot)
        villain_type:      Villain type ('fish','rec','nit','lag','reg')
        street:            Current street ('flop','turn','river')
        actual_fold_freq:  Hero's current fold frequency (0-1) for self-assessment

    Returns:
        HeroFoldFrequencyResult
    """
    mdf_val = _mdf(bet_frac)
    max_fold = _max_fold_freq(bet_frac, villain_type, street)
    to_fold = _hands_to_fold(max_fold)
    status = _overfold_warning(actual_fold_freq, max_fold)

    verdict = (
        f'[HFF bet={bet_frac:.0%}pot|{villain_type}|{street}] '
        f'MDF={mdf_val:.0%} max_fold={max_fold:.0%} status={status}'
    )

    reasoning = (
        f'Hero fold frequency: villain bets {bet_frac:.0%} pot on {street}. '
        f'Villain type={villain_type} (bluff adj={VILLAIN_BLUFF_ADJUSTMENT.get(villain_type,0):+.0%}). '
        f'MDF={mdf_val:.0%} -> max fold={max_fold:.0%}. '
        f'Actual fold={actual_fold_freq:.0%}. Status: {status}. '
        f'Fold these hands first: {", ".join(to_fold[:4])}.'
    )

    tips = []

    tips.append(
        f'MDF vs {bet_frac:.0%} pot bet: Must continue {mdf_val:.0%} of range (max fold {max_fold:.0%}). '
        f'Adjusted for {villain_type}: bluff rate {"+high" if VILLAIN_BLUFF_ADJUSTMENT.get(villain_type, 0) < 0 else "+low"}. '
        f'{"Fold more vs nit (nit rarely bluffs)." if villain_type == "nit" else "Fold less vs LAG (LAG bluffs frequently)." if villain_type == "lag" else "Standard fold frequency."}'
    )

    tips.append(
        f'FOLD ORDER (weakest first): {", ".join(to_fold[:5])}. '
        f'Continue with all hands above {HAND_SDV_THRESHOLDS.get(to_fold[-1] if to_fold else "air", 0.05):.0%} SDV. '
        f'Always continue: draws (equity to improve) and medium pair+ (showdown value).'
    )

    if 'OVERFOLD' in status:
        severity = status.split('_')[0]
        tips.append(
            f'WARNING: {status} -- folding {actual_fold_freq:.0%} vs max allowed {max_fold:.0%}. '
            f'Over-folding by {actual_fold_freq - max_fold:.0%}. '
            f'Villain can profitably bluff with any two cards! '
            f'Add {to_fold[-1] if to_fold else "bluff catchers"} back into your continuing range.'
        )
    elif 'UNDERFOLD' in status:
        tips.append(
            f'NOTE: Possible underfold -- calling {1-actual_fold_freq:.0%} vs MDF {mdf_val:.0%}. '
            f'If you are calling too wide, you are losing too much to value bets. '
            f'Fold bottom of range: {to_fold[:2] if to_fold else []}.'
        )

    return HeroFoldFrequencyResult(
        bet_frac=bet_frac,
        villain_type=villain_type,
        street=street,
        actual_fold_freq=actual_fold_freq,
        mdf=mdf_val,
        max_fold_freq=max_fold,
        hands_to_fold=to_fold,
        fold_status=status,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def hff_one_liner(r: HeroFoldFrequencyResult) -> str:
    return (
        f'[HFF bet={r.bet_frac:.0%}|{r.villain_type}|{r.street}] '
        f'MDF={r.mdf:.0%} max_fold={r.max_fold_freq:.0%}'
    )
