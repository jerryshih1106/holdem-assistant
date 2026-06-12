"""
Early Position Open Frequency Guide (early_position_open_frequency_guide.py)

Theory: UTG/UTG+1/MP open ranges are the tightest at the table because many
players remain to act behind. In a 9-max game UTG opens ~13-15% of hands;
in 6-max that same seat opens ~18-22% because fewer players remain.
MP/LJ slots sit between UTG and CO in frequency.

Adjustments:
  vs nitty table   -> widen 3%+ (more steal equity, less 3-bet risk)
  vs aggressive    -> tighten 2-3% (higher 3-bet/squeeze risk)

DISTINCT FROM:
  preflop_open_frequency_guide.py  -- general guide across all positions
  THIS MODULE                      -- focused only on EP seats (UTG/UTG+1/MP/LJ)
"""

from dataclasses import dataclass, field
from typing import List


EP_OPEN_FREQ_BY_POSITION: dict = {
    'utg_9max': 0.13,
    'utg_6max': 0.20,
    'utg1':     0.15,
    'mp':       0.18,
    'lj':       0.22,
}

TABLE_SIZE_MODIFIER: dict = {
    '9max': 0.00,
    '6max': 0.07,
}

VILLAIN_EP_MODIFIER: dict = {
    'nit_table':        +0.03,
    'balanced_table':    0.00,
    'aggressive_table': -0.03,
}


def _ep_open_freq(position: str, table_size: str, table_dynamic: str) -> float:
    pos_key = f'{position}_{table_size}' if position in ('utg',) else position
    base = EP_OPEN_FREQ_BY_POSITION.get(pos_key, EP_OPEN_FREQ_BY_POSITION.get(position, 0.15))
    size_mod = TABLE_SIZE_MODIFIER.get(table_size, 0.0)
    dyn_mod = VILLAIN_EP_MODIFIER.get(table_dynamic, 0.0)
    if position == 'utg':
        base = 0.13 if table_size == '9max' else 0.20
        size_mod = 0.0
    freq = base + size_mod * 0 + dyn_mod
    return round(min(0.40, max(0.08, freq)), 3)


def _ep_action(freq: float, hand_sdv: float) -> str:
    if hand_sdv >= freq:
        return 'RAISE'
    return 'FOLD'


def _ep_size_bb(effective_bb: float) -> float:
    if effective_bb >= 200:
        return 3.0
    if effective_bb >= 100:
        return 2.5
    return 2.0


@dataclass
class EpOpenFreqResult:
    position: str
    table_size: str
    table_dynamic: str
    hand_sdv: float
    open_freq: float
    ep_action: str
    recommended_size_bb: float
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_early_position_open_frequency(
    position: str = 'utg',
    table_size: str = '9max',
    table_dynamic: str = 'balanced_table',
    hand_sdv: float = 0.15,
    effective_bb: float = 100.0,
) -> EpOpenFreqResult:
    """
    Analyze early-position open frequency and recommended action.

    Args:
        position:     Seat ('utg', 'utg1', 'mp', 'lj')
        table_size:   '9max' or '6max'
        table_dynamic: 'nit_table', 'balanced_table', or 'aggressive_table'
        hand_sdv:     Hand strength percentile / SDV (0-1); higher = stronger hand
        effective_bb: Effective stack depth in BB

    Returns:
        EpOpenFreqResult
    """
    open_freq = _ep_open_freq(position, table_size, table_dynamic)
    action = _ep_action(open_freq, hand_sdv)
    size_bb = _ep_size_bb(effective_bb)

    verdict = (
        f'[EP pos={position.upper()} size={size_bb:.1f}BB] '
        f'freq={open_freq:.0%} action={action}'
    )

    reasoning = (
        f'EP seat {position.upper()} on {table_size} with {table_dynamic}. '
        f'Open freq={open_freq:.0%}. Hand SDV={hand_sdv:.2f}. '
        f'Action: {action}. Size: {size_bb:.1f}BB.'
    )

    tips: List[str] = []
    tips.append(
        f'EP DISCIPLINE: From {position.upper()} on {table_size} open only top '
        f'{open_freq:.0%} of hands. Many players remain; premium hands only.'
    )
    tips.append(
        f'SIZING: Use {size_bb:.1f}BB open from EP. Larger than late position '
        f'signals strength and builds pot with value hands.'
    )

    if table_dynamic == 'aggressive_table':
        tips.append(
            'AGGRESSIVE TABLE: Tighten EP range 2-3%. Expect frequent 3-bets; '
            'only open hands you can continue with.'
        )
    elif table_dynamic == 'nit_table':
        tips.append(
            'NIT TABLE: Widen EP range 3%. Opponents fold too often; '
            'profitably steal with slightly weaker hands.'
        )
    if hand_sdv < open_freq and action == 'FOLD':
        tips.append(
            f'HAND TOO WEAK: SDV={hand_sdv:.2f} below EP threshold {open_freq:.0%}. '
            f'Wait for a better spot.'
        )

    return EpOpenFreqResult(
        position=position,
        table_size=table_size,
        table_dynamic=table_dynamic,
        hand_sdv=hand_sdv,
        open_freq=open_freq,
        ep_action=action,
        recommended_size_bb=size_bb,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ep_one_liner(r: EpOpenFreqResult) -> str:
    return (
        f'[EP pos={r.position.upper()} size={r.recommended_size_bb:.1f}BB] '
        f'freq={r.open_freq:.0%} action={r.ep_action}'
    )
