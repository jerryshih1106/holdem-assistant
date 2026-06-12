"""
4-Bet Pot Postflop Guide (four_bet_pot_postflop_guide.py)

Theory: After a preflop 4-bet pot, the SPR (stack-to-pot ratio) is very low
(typically 0.5-2.0). This changes postflop strategy dramatically:
  - Cbet frequency is very high (85-95%) on most boards
  - Sizing is smaller (25-35% pot); you don't need to build the pot
  - Stack off with any pair+ at low SPR
  - Bet/fold is rare; mostly bet/call or check/call
  - IP player has huge advantage because OOP cannot easily bluff low SPR

DISTINCT FROM:
  threbet_pot_postflop_guide.py  -- 3-bet pot (higher SPR)
  spr_commitment.py              -- general SPR commitment
  THIS MODULE                    -- 4-bet pot specific postflop strategy
"""

from dataclasses import dataclass, field
from typing import List


CBET_FREQ_4BET_POT: dict = {
    'dry':       0.95,
    'semi_wet':  0.92,
    'wet':       0.88,
    'monotone':  0.85,
    'paired':    0.90,
}

CBET_SIZE_4BET_POT: float = 0.30

SPR_STACK_OFF_THRESHOLD: float = 0.55

STACK_OFF_COMFORT_BY_SPR: dict = {
    'very_low': 0.48,
    'low':      0.55,
    'medium':   0.60,
}


def _4bet_pot_spr(pot_bb: float, stack_bb: float) -> float:
    if pot_bb <= 0:
        return 0.0
    return round(stack_bb / pot_bb, 2)


def _spr_bucket(spr: float) -> str:
    if spr < 1.0:
        return 'very_low'
    if spr < 2.0:
        return 'low'
    return 'medium'


def _cbet_freq(board_texture: str, spr: float) -> float:
    base = CBET_FREQ_4BET_POT.get(board_texture, CBET_FREQ_4BET_POT['semi_wet'])
    spr_bonus = 0.02 if spr < 1.0 else 0.0
    return round(min(0.98, base + spr_bonus), 3)


def _cbet_size(pot_bb: float) -> float:
    return round(pot_bb * CBET_SIZE_4BET_POT, 1)


def _stack_off_threshold(spr: float) -> float:
    bucket = _spr_bucket(spr)
    return STACK_OFF_COMFORT_BY_SPR.get(bucket, SPR_STACK_OFF_THRESHOLD)


@dataclass
class FourBetPotPostflopResult:
    pot_bb: float
    stack_bb: float
    board_texture: str
    position: str
    hand_sdv: float
    spr: float
    cbet_freq: float
    cbet_size_bb: float
    stack_off_threshold: float
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_four_bet_pot_postflop(
    pot_bb: float = 42.0,
    stack_bb: float = 58.0,
    board_texture: str = 'dry',
    position: str = 'ip',
    hand_sdv: float = 0.70,
) -> FourBetPotPostflopResult:
    """
    Analyze postflop strategy in a 4-bet pot.

    Args:
        pot_bb:        Pot size in BB at start of flop
        stack_bb:      Effective remaining stack in BB
        board_texture: 'dry','semi_wet','wet','monotone','paired'
        position:      'ip' or 'oop'
        hand_sdv:      Hand strength percentile (0-1)

    Returns:
        FourBetPotPostflopResult
    """
    spr = _4bet_pot_spr(pot_bb, stack_bb)
    cf = _cbet_freq(board_texture, spr)
    cs = _cbet_size(pot_bb)
    sot = _stack_off_threshold(spr)

    verdict = (
        f'[4BP spr={spr:.2f} board={board_texture}] '
        f'cbet={cf:.0%} size={cs:.1f}bb sot={sot:.0%}'
    )

    reasoning = (
        f'4-bet pot postflop: pot={pot_bb:.1f}BB, stack={stack_bb:.1f}BB, '
        f'SPR={spr:.2f}. Board={board_texture}, position={position}. '
        f'Cbet freq={cf:.0%}, size={cs:.1f}BB, stack-off threshold={sot:.0%}.'
    )

    tips: List[str] = []
    tips.append(
        f'LOW SPR: At SPR={spr:.2f} the pot is already large vs remaining stack. '
        f'Cbet {cf:.0%} of the time; stack off with any decent hand.'
    )
    tips.append(
        f'SMALL SIZING: Use {CBET_SIZE_4BET_POT:.0%} pot ({cs:.1f}BB) -- '
        f'no need to build the pot; just put money in and get to showdown.'
    )

    if position == 'ip':
        tips.append(
            'IP ADVANTAGE: You have massive positional advantage in 4-bet pots. '
            'Bet nearly always on flop; use position to control pot size on later streets.'
        )
    else:
        tips.append(
            'OOP IN 4BET POT: Difficult spot. Prefer check-call over check-fold. '
            'SPR is too low to make sophisticated bluffs profitable.'
        )

    if hand_sdv >= sot:
        tips.append(
            f'STACK OFF: Hand SDV={hand_sdv:.2f} >= threshold={sot:.2f}. '
            f'Commit remaining stack; do not slow down at this SPR.'
        )
    else:
        tips.append(
            f'CAUTIOUS: Hand SDV={hand_sdv:.2f} below stack-off threshold={sot:.2f}. '
            f'Consider pot control if villain shows resistance.'
        )

    if board_texture == 'monotone':
        tips.append(
            'MONOTONE BOARD: Even with very low SPR, check back occasionally '
            'to protect check-calling range and avoid being raised off equity.'
        )

    return FourBetPotPostflopResult(
        pot_bb=pot_bb,
        stack_bb=stack_bb,
        board_texture=board_texture,
        position=position,
        hand_sdv=hand_sdv,
        spr=spr,
        cbet_freq=cf,
        cbet_size_bb=cs,
        stack_off_threshold=sot,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def fbp_one_liner(r: FourBetPotPostflopResult) -> str:
    return (
        f'[4BP spr={r.spr:.2f} board={r.board_texture}] '
        f'cbet={r.cbet_freq:.0%} size={r.cbet_size_bb:.1f}bb sot={r.stack_off_threshold:.0%}'
    )
