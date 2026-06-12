"""
SB Preflop Strategy Guide (sb_preflop_strategy_guide.py)

Theory: The small blind is the most complex preflop position.
  - You are OOP postflop vs BB but still post 0.5BB dead money.
  - Options: FOLD / COMPLETE (limp) / RAISE / 3BET.
  - vs limped pot: raise ISO to 4-5BB.
  - vs open: 3-bet or fold; rarely call (calling OOP is weak).
  - SB 3-bet range: merge with value hands + some bluffs.
  - SB call range: suited connectors, small pairs below threshold.

DISTINCT FROM:
  blind_vs_blind_strategy_guide.py  -- heads-up BB vs SB
  steal_advisor.py                  -- general steal
  THIS MODULE                       -- SB-specific preflop action matrix
"""

from dataclasses import dataclass, field
from typing import List


SB_OPEN_FREQ: float = 0.40

SB_3BET_FREQ_VS_OPEN: dict = {
    'btn': 0.14,
    'co':  0.12,
    'hj':  0.10,
    'mp':  0.09,
    'utg': 0.08,
}

SB_COMPLETE_FREQ_VS_LIMPERS: float = 0.65

SB_RAISE_VS_LIMPER: dict = {
    '1_limper': 4.0,
    '2_limpers': 5.0,
    '3plus_limpers': 6.0,
}

SB_CALL_OPEN_FREQ: float = 0.08


def _sb_3bet_size(open_bb: float) -> float:
    return round(open_bb * 3.0 + 1.0, 1)


def _sb_complete_or_raise(hand_sdv: float, n_limpers: int) -> str:
    if n_limpers == 0:
        return 'RAISE' if hand_sdv >= SB_OPEN_FREQ else 'FOLD'
    if hand_sdv >= 0.70:
        return 'RAISE_ISO'
    if hand_sdv >= (1.0 - SB_COMPLETE_FREQ_VS_LIMPERS):
        return 'COMPLETE'
    return 'FOLD'


def _sb_action(
    n_limpers: int,
    opener_position: str,
    hand_sdv: float,
    stack_bb: float,
) -> tuple:
    """Return (action, size_bb)."""
    # Facing an open raise
    if opener_position and n_limpers == 0:
        tbet_freq = SB_3BET_FREQ_VS_OPEN.get(opener_position.lower(), 0.10)
        if hand_sdv >= (1.0 - tbet_freq):
            return '3BET', 0.0
        if hand_sdv >= (1.0 - SB_CALL_OPEN_FREQ - tbet_freq) and stack_bb >= 100:
            return 'CALL_RARE', 0.0
        return 'FOLD', 0.0

    # No open; limpers present or SB first to act
    if n_limpers == 0:
        act = _sb_complete_or_raise(hand_sdv, 0)
        size = 3.0 if act == 'RAISE' else 0.5
        return act, size

    act = _sb_complete_or_raise(hand_sdv, n_limpers)
    if act == 'RAISE_ISO':
        key = '1_limper' if n_limpers == 1 else ('2_limpers' if n_limpers == 2 else '3plus_limpers')
        size = SB_RAISE_VS_LIMPER[key]
    elif act == 'COMPLETE':
        size = 0.5
    else:
        size = 0.0
    return act, size


@dataclass
class SbPreflopResult:
    n_limpers: int
    opener_position: str
    hand_sdv: float
    stack_bb: float
    action: str
    size_bb: float
    reasoning: str
    verdict: str
    tips: List[str] = field(default_factory=list)


def analyze_sb_preflop_strategy(
    n_limpers: int = 0,
    opener_position: str = '',
    hand_sdv: float = 0.40,
    stack_bb: float = 100.0,
) -> SbPreflopResult:
    """
    Analyze SB preflop strategy.

    Args:
        n_limpers:        Number of limpers in front (0 if facing an open)
        opener_position:  Position of the raiser if facing a raise ('' if none)
        hand_sdv:         Hand strength percentile (0-1)
        stack_bb:         Effective stack in BB

    Returns:
        SbPreflopResult
    """
    action, size_bb = _sb_action(n_limpers, opener_position, hand_sdv, stack_bb)

    if opener_position:
        context = f'facing open from {opener_position.upper()}'
    elif n_limpers > 0:
        context = f'{n_limpers} limper(s)'
    else:
        context = 'first in'

    verdict = (
        f'[SB limpers={n_limpers} opener={opener_position or "none"}] '
        f'action={action} size={size_bb:.1f}BB'
    )

    reasoning = (
        f'SB preflop ({context}). Hand SDV={hand_sdv:.2f}, stack={stack_bb:.0f}BB. '
        f'Action={action}, size={size_bb:.1f}BB.'
    )

    tips: List[str] = []
    tips.append(
        'SB POSITION: OOP postflop against BB. Prefer raise-or-fold; limping '
        'invites cheap flops and weak ranges.'
    )
    tips.append(
        f'3BET VS OPENS: SB should 3-bet {SB_3BET_FREQ_VS_OPEN.get(opener_position.lower(), 0.10):.0%} '
        f'vs {opener_position.upper() if opener_position else "opener"}. '
        f'Only call with best SC/pairs and deep stacks.'
    )

    if action == '3BET':
        tips.append(
            f'3BET SIZING: 3x open + 1BB dead money. Make opponent pay for positional disadvantage.'
        )
    if action == 'COMPLETE':
        tips.append(
            'COMPLETE: Check flop often; you have the worst position. '
            'Be ready to fold to aggression on most boards.'
        )
    if action == 'RAISE_ISO':
        tips.append(
            f'ISO RAISE: vs {n_limpers} limper(s) size to {size_bb:.0f}BB. '
            f'Isolate weak limpers and take postflop initiative.'
        )
    if action == 'CALL_RARE':
        tips.append(
            'RARE CALL: Only justified with deep stacks + implied-odds hands. '
            'Prefer 3-bet or fold as default SB line.'
        )

    return SbPreflopResult(
        n_limpers=n_limpers,
        opener_position=opener_position,
        hand_sdv=hand_sdv,
        stack_bb=stack_bb,
        action=action,
        size_bb=size_bb,
        reasoning=reasoning,
        verdict=verdict,
        tips=tips,
    )


def sb_one_liner(r: SbPreflopResult) -> str:
    return (
        f'[SB limpers={r.n_limpers} opener={r.opener_position or "none"}] '
        f'action={r.action} size={r.size_bb:.1f}BB'
    )
