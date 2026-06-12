"""
Preflop 3-Bet Frequency Guide (preflop_3bet_frequency_guide.py)

Calibrates 3-bet frequency by position, villain type, and fold-to-3bet stats.
Detects over/under-3-betting and gives exploitative frequency adjustments.

THEORY:
  3-BET FREQUENCY CALIBRATION:
  3-bet frequency depends on: (1) villain's open position/range width,
  (2) villain's fold-to-3bet stat, (3) villain type, (4) hero position (IP/OOP).

  POSITION-BASED BASELINES (facing villain's open):
  vs UTG (tight ~14% range): 3-bet ~4% -- range too strong, bluffs risky
  vs BTN (wide ~40% range): 3-bet ~13% -- many bluff candidates

  FOLD-TO-3BET EXPLOITATION:
  Villain folds >72% to 3-bets: increase 3-bet range (bluffs auto-profitable)
  Villain folds <42% to 3-bets: use value only (bluffs lose money)

  VALUE vs BLUFF BALANCE:
  GTO 3-bet: ~2:1 value-to-bluff ratio
  Pure value combos: TT+, AQs+, AKo (~34 combos, ~5% of hands)
  Add bluffs: suited Ax blockers, KQs, suited connectors (to reach target freq)

DISTINCT FROM:
  preflop_3bet_polarization_guide.py: WHICH hands to 3-bet (polar vs merged)
  hero_3bet_range_optimizer.py:       GTO-based range construction
  THIS MODULE:                        HOW OFTEN to 3-bet; over/under detection;
                                      exploitative frequency adjustments.
"""

from dataclasses import dataclass, field
from typing import List

BASELINE_3BET_FREQ_VS_OPEN_POSITION: dict = {
    'utg': 0.04,
    'mp':  0.06,
    'lj':  0.07,
    'hj':  0.08,
    'co':  0.10,
    'btn': 0.13,
    'sb':  0.15,
}

VILLAIN_TYPE_3BET_MODIFIER: dict = {
    'fish':            +0.03,
    'calling_station': +0.04,
    'nit':             -0.02,
    'lag':             -0.03,
    'rec':             +0.01,
    'reg':              0.00,
}

FOLD_TO_3BET_ADJUSTMENT: dict = {
    'very_high': +0.06,
    'high':      +0.03,
    'standard':   0.00,
    'low':       -0.03,
    'very_low':  -0.07,
}

FOLD_TO_3BET_THRESHOLDS: dict = {
    'very_high': 0.72,
    'high':      0.62,
    'standard':  0.52,
    'low':       0.42,
    'very_low':  0.00,
}

POSITION_IP_OOP_MODIFIER: dict = {
    'ip':  +0.02,
    'oop': -0.03,
}

VALUE_3BET_COMBOS_APPROX: int = 34
TOTAL_HAND_COMBOS: int = 1326


def _fold_to_3bet_category(fold_pct: float) -> str:
    for cat, thresh in FOLD_TO_3BET_THRESHOLDS.items():
        if fold_pct >= thresh:
            return cat
    return 'very_low'


def _optimal_3bet_freq(
    open_position: str,
    villain_type: str,
    fold_to_3bet: float,
    hero_position: str,
) -> float:
    base = BASELINE_3BET_FREQ_VS_OPEN_POSITION.get(open_position, 0.08)
    vil_mod = VILLAIN_TYPE_3BET_MODIFIER.get(villain_type, 0.00)
    f2t_cat = _fold_to_3bet_category(fold_to_3bet)
    f2t_adj = FOLD_TO_3BET_ADJUSTMENT.get(f2t_cat, 0.00)
    pos_mod = POSITION_IP_OOP_MODIFIER.get(hero_position, 0.00)
    freq = base + vil_mod + f2t_adj + pos_mod
    return round(min(0.35, max(0.01, freq)), 3)


def _3bet_calibration_status(actual: float, optimal: float) -> str:
    diff = actual - optimal
    if diff > 0.06:
        return 'OVER_3BETTING_SIGNIFICANTLY'
    if diff > 0.03:
        return 'OVER_3BETTING_SLIGHTLY'
    if diff < -0.06:
        return 'UNDER_3BETTING_SIGNIFICANTLY'
    if diff < -0.03:
        return 'UNDER_3BETTING_SLIGHTLY'
    return '3BET_FREQUENCY_OK'


@dataclass
class Preflop3BetFrequencyResult:
    open_position: str
    villain_type: str
    fold_to_3bet: float
    hero_position: str
    actual_3bet_freq: float

    optimal_3bet_freq: float
    fold_category: str
    calibration_status: str
    value_combos_approx: int
    bluff_combos_needed: int

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_preflop_3bet_frequency(
    open_position: str = 'btn',
    villain_type: str = 'reg',
    fold_to_3bet: float = 0.57,
    hero_position: str = 'ip',
    actual_3bet_freq: float = 0.10,
) -> Preflop3BetFrequencyResult:
    """
    Calibrate preflop 3-bet frequency vs villain's open.

    Args:
        open_position:    Position villain opened from ('utg','mp','co','btn','sb')
        villain_type:     Villain type ('fish','nit','lag','reg','calling_station')
        fold_to_3bet:     Villain's fold-to-3bet frequency (0-1); default 0.57
        hero_position:    Hero's position relative to villain ('ip' or 'oop')
        actual_3bet_freq: Hero's current 3-bet frequency for calibration

    Returns:
        Preflop3BetFrequencyResult
    """
    optimal = _optimal_3bet_freq(open_position, villain_type, fold_to_3bet, hero_position)
    f2t_cat = _fold_to_3bet_category(fold_to_3bet)
    status = _3bet_calibration_status(actual_3bet_freq, optimal)

    total_in_range = int(TOTAL_HAND_COMBOS * optimal)
    bluff_needed = max(0, total_in_range - VALUE_3BET_COMBOS_APPROX)

    verdict = (
        f'[3BF vs {open_position}|{villain_type}|f2t={fold_to_3bet:.0%}] '
        f'optimal={optimal:.0%} actual={actual_3bet_freq:.0%} status={status}'
    )

    reasoning = (
        f'3-bet freq vs {open_position} open ({villain_type}): '
        f'base={BASELINE_3BET_FREQ_VS_OPEN_POSITION.get(open_position, 0.08):.0%} '
        f'vil_adj={VILLAIN_TYPE_3BET_MODIFIER.get(villain_type, 0):+.0%} '
        f'f2t={fold_to_3bet:.0%}({f2t_cat})adj={FOLD_TO_3BET_ADJUSTMENT.get(f2t_cat, 0):+.0%} '
        f'pos({hero_position})={POSITION_IP_OOP_MODIFIER.get(hero_position, 0):+.0%}. '
        f'Optimal={optimal:.0%}. Status={status}.'
    )

    tips = []

    tips.append(
        f'Optimal 3-bet freq vs {open_position} ({villain_type}): {optimal:.0%}. '
        f'Value range ~{VALUE_3BET_COMBOS_APPROX} combos (TT+/AQs+/AKo); '
        f'need ~{bluff_needed} bluff combos (suited Ax, KQs, suited connectors). '
        f'Villain fold-to-3bet={fold_to_3bet:.0%} ({f2t_cat}).'
    )

    if 'OVER' in status:
        tips.append(
            f'OVER-3BETTING: {actual_3bet_freq:.0%} vs optimal {optimal:.0%}. '
            f'Cut bluff 3-bets -- {villain_type} calls/4-bets too often. '
            f'Keep value (TT+/AQs+/AKo); drop suited-connector 3-bets.'
        )
    elif 'UNDER' in status:
        tips.append(
            f'UNDER-3BETTING: {actual_3bet_freq:.0%} vs optimal {optimal:.0%}. '
            f'Villain folds {fold_to_3bet:.0%} to 3-bets -- add bluffs. '
            f'Add from {hero_position}: A5s-A2s, KQs, suited connectors.'
        )
    else:
        tips.append(
            f'3-bet frequency calibrated ({actual_3bet_freq:.0%} vs optimal {optimal:.0%}). '
            f'Maintain {optimal:.0%} target; adjust per villain HUD stat. '
            f'vs {villain_type}: {"value-heavy only" if villain_type in ("fish", "calling_station") else "balanced value+bluff range"}.'
        )

    if villain_type == 'lag':
        tips.append(
            f'vs LAG: Reduce bluff 3-bets (LAG 4-bets wide and calls wide). '
            f'3-bet value only: JJ+/AQs+. Flat IP with TT/99/AJs. '
            f'Have 4-bet shove range (QQ+/AK) ready for LAG squeeze attempts.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'vs NIT: 3-bet tight -- nit range is very strong (UTG ~10%). '
            f'Value: QQ+/AKs. Add KQs/JJ IP only if nit folds {fold_to_3bet:.0%}+. '
            f'Nit rarely bluff-4bets so 3-bet/fold marginal holdings is OK.'
        )

    return Preflop3BetFrequencyResult(
        open_position=open_position,
        villain_type=villain_type,
        fold_to_3bet=fold_to_3bet,
        hero_position=hero_position,
        actual_3bet_freq=actual_3bet_freq,
        optimal_3bet_freq=optimal,
        fold_category=f2t_cat,
        calibration_status=status,
        value_combos_approx=VALUE_3BET_COMBOS_APPROX,
        bluff_combos_needed=bluff_needed,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def p3f_one_liner(r: Preflop3BetFrequencyResult) -> str:
    return (
        f'[3BF vs {r.open_position}|{r.villain_type}] '
        f'optimal={r.optimal_3bet_freq:.0%} actual={r.actual_3bet_freq:.0%} {r.calibration_status}'
    )
