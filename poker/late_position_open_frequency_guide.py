"""
Late Position Open Frequency Guide (late_position_open_frequency_guide.py)

Theory: CO/BTN/SB can open much wider ranges because fewer players remain
behind and they often have positional advantage postflop.
  BTN = 45-55%, CO = 28-38%, SB = 35-45%

Adjustments:
  vs weak BB (high fold-to-steal)  -> open wider
  vs strong 3-bettor in blinds     -> tighten
  BTN vs nitty BB can open 60%+

DISTINCT FROM:
  steal_advisor.py               -- blind steal logic
  preflop_open_frequency_guide.py-- general all-position guide
  THIS MODULE                    -- CO/BTN/SB specific frequency + BB reads
"""

from dataclasses import dataclass, field
from typing import List


LP_OPEN_FREQ: dict = {
    'co':  0.33,
    'btn': 0.50,
    'sb':  0.40,
}

BB_FOLD_TO_STEAL_MOD: dict = {
    'very_low':  -0.12,
    'low':       -0.06,
    'standard':   0.00,
    'high':      +0.06,
    'very_high': +0.12,
}

BB_3BET_MOD: dict = {
    'low3bet':  +0.05,
    'avg3bet':   0.00,
    'high3bet': -0.08,
}


def _lp_open_freq(position: str, bb_fold_to_steal: str, bb_3bet_pct: str) -> float:
    base = LP_OPEN_FREQ.get(position.lower(), LP_OPEN_FREQ['co'])
    steal_mod = BB_FOLD_TO_STEAL_MOD.get(bb_fold_to_steal, 0.0)
    tbet_mod = BB_3BET_MOD.get(bb_3bet_pct, 0.0)
    freq = base + steal_mod + tbet_mod
    return round(min(0.75, max(0.15, freq)), 3)


def _steal_size_bb(position: str, is_live: bool) -> float:
    if is_live:
        return 3.0 if position in ('co', 'sb') else 2.5
    return 2.5 if position in ('co', 'sb') else 2.0


def _lp_action(hand_sdv: float, freq: float) -> str:
    if hand_sdv >= freq:
        return 'RAISE'
    return 'FOLD'


@dataclass
class LpOpenFreqResult:
    position: str
    bb_fold_to_steal: str
    bb_3bet_pct: str
    hand_sdv: float
    open_freq: float
    size_bb: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_late_position_open_frequency(
    position: str = 'btn',
    bb_fold_to_steal: str = 'standard',
    bb_3bet_pct: str = 'avg3bet',
    hand_sdv: float = 0.45,
    is_live: bool = False,
) -> LpOpenFreqResult:
    """
    Analyze late-position open frequency adjusted for BB tendencies.

    Args:
        position:         'co', 'btn', or 'sb'
        bb_fold_to_steal: 'very_low','low','standard','high','very_high'
        bb_3bet_pct:      'low3bet', 'avg3bet', 'high3bet'
        hand_sdv:         Hand strength percentile (0-1)
        is_live:          True if live poker (larger sizing)

    Returns:
        LpOpenFreqResult
    """
    open_freq = _lp_open_freq(position, bb_fold_to_steal, bb_3bet_pct)
    size_bb = _steal_size_bb(position, is_live)
    action = _lp_action(hand_sdv, open_freq)

    verdict = (
        f'[LP pos={position.upper()} bb_f2s={bb_fold_to_steal}] '
        f'freq={open_freq:.0%} size={size_bb:.1f}BB action={action}'
    )

    reasoning = (
        f'Late position {position.upper()}: base freq={LP_OPEN_FREQ.get(position, 0.33):.0%}, '
        f'f2s_mod={BB_FOLD_TO_STEAL_MOD.get(bb_fold_to_steal, 0):+.0%}, '
        f'3bet_mod={BB_3BET_MOD.get(bb_3bet_pct, 0):+.0%}. '
        f'Final freq={open_freq:.0%}. Hand SDV={hand_sdv:.2f} -> {action}.'
    )

    tips: List[str] = []
    tips.append(
        f'LP POSITION: {position.upper()} is one of the most profitable open seats. '
        f'Target open freq={open_freq:.0%}; exploit positional advantage postflop.'
    )
    tips.append(
        f'BB READS: BB fold-to-steal={bb_fold_to_steal}, 3-bet pct={bb_3bet_pct}. '
        f'Size to {size_bb:.1f}BB. Adjust frequency based on defender tendencies.'
    )

    if bb_fold_to_steal in ('high', 'very_high'):
        tips.append(
            f'STEAL OPPORTUNITY: BB folds {bb_fold_to_steal} to steals. '
            f'Widen range to {open_freq:.0%}; pure profitability even with weak hands.'
        )
    if bb_3bet_pct == 'high3bet':
        tips.append(
            'HIGH 3-BET RISK: BB 3-bets frequently. Tighten range and only open '
            'hands you can 4-bet or call a 3-bet profitably.'
        )
    if position == 'sb':
        tips.append(
            'SB OPEN: From SB you are OOP postflop vs BB. Balance value opens '
            'with some bluffs; prefer hands with postflop playability.'
        )

    return LpOpenFreqResult(
        position=position,
        bb_fold_to_steal=bb_fold_to_steal,
        bb_3bet_pct=bb_3bet_pct,
        hand_sdv=hand_sdv,
        open_freq=open_freq,
        size_bb=size_bb,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def lp_one_liner(r: LpOpenFreqResult) -> str:
    return (
        f'[LP pos={r.position.upper()} bb_f2s={r.bb_fold_to_steal}] '
        f'freq={r.open_freq:.0%} size={r.size_bb:.1f}BB action={r.action}'
    )
