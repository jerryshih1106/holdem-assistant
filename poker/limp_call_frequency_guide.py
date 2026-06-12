"""
Limp-Call Frequency Guide (limp_call_frequency_guide.py)

Theory: Limp-calling (limp then call a raise) is generally a weak play that
telegraphs a capped range. Valid uses are limited:
  - Very deep stacks (200BB+) with speculative hands that have high implied odds
  - Small pairs at 150BB+: can set-mine profitably
  - Suited connectors at 150BB+: implied odds justify
  - Suited gappers at 200BB+: need deeper stacks

Typical frequency: 2-5% of hands. Most players limp-call too often.

DISTINCT FROM:
  limp_reraise.py / limp_reraise_frequency_guide.py  -- limp then 3-bet
  cold_call_frequency_guide.py                        -- calling opens cold
  THIS MODULE                                         -- limp-call frequency
"""

from dataclasses import dataclass, field
from typing import List


LIMP_CALL_BASE_FREQ: float = 0.03

STACK_LIMP_CALL_THRESHOLD: dict = {
    'pair':    150.0,
    'sc':      150.0,
    'gapper':  200.0,
    'offsuit': 999.0,
}

HAND_LIMP_CALL_MODIFIER: dict = {
    'small_pair':    +0.02,
    'sc':            +0.015,
    'suited_gapper': +0.01,
    'offsuit':       -0.02,
}

RAISE_SIZE_THRESHOLD: float = 6.0


def _implied_odds_ok(stack_bb: float, raise_bb: float) -> bool:
    if raise_bb <= 0:
        return False
    ratio = stack_bb / raise_bb
    return ratio >= 15.0


def _limp_call_freq(
    hand_type: str,
    stack_bb: float,
    raise_bb: float,
    position: str,
) -> float:
    threshold = STACK_LIMP_CALL_THRESHOLD.get(hand_type, 999.0)
    if stack_bb < threshold:
        return 0.0
    if raise_bb > RAISE_SIZE_THRESHOLD:
        return 0.0
    base = LIMP_CALL_BASE_FREQ
    mod = HAND_LIMP_CALL_MODIFIER.get(hand_type, 0.0)
    pos_mod = -0.01 if position.lower() in ('utg', 'utg1') else 0.0
    freq = base + mod + pos_mod
    return round(min(0.08, max(0.0, freq)), 3)


def _limp_call_action(freq: float, raise_bb: float, pot_bb: float) -> str:
    if freq <= 0.0:
        return 'FOLD_TO_RAISE'
    if raise_bb > RAISE_SIZE_THRESHOLD:
        return 'FOLD_TO_RAISE'
    if freq >= 0.03:
        return 'LIMP_CALL'
    return 'FOLD_TO_RAISE'


@dataclass
class LimpCallResult:
    hand_type: str
    stack_bb: float
    raise_bb: float
    position: str
    limp_call_freq: float
    action: str
    implied_odds_ok: bool
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_limp_call_frequency(
    hand_type: str = 'small_pair',
    stack_bb: float = 150.0,
    raise_bb: float = 4.0,
    position: str = 'mp',
    pot_bb: float = 5.5,
) -> LimpCallResult:
    """
    Analyze limp-call frequency and viability.

    Args:
        hand_type: 'small_pair', 'sc', 'suited_gapper', 'offsuit'
        stack_bb:  Effective stack in BB
        raise_bb:  Size of the raise in BB
        position:  Hero's position
        pot_bb:    Current pot in BB (including the raise)

    Returns:
        LimpCallResult
    """
    freq = _limp_call_freq(hand_type, stack_bb, raise_bb, position)
    action = _limp_call_action(freq, raise_bb, pot_bb)
    io_ok = _implied_odds_ok(stack_bb, raise_bb)

    verdict = (
        f'[LC hand={hand_type} stack={stack_bb:.0f}BB] '
        f'freq={freq:.1%} action={action} io_ok={"Y" if io_ok else "N"}'
    )

    reasoning = (
        f'Limp-call analysis: hand={hand_type}, stack={stack_bb:.0f}BB, '
        f'raise={raise_bb:.1f}BB. Threshold={STACK_LIMP_CALL_THRESHOLD.get(hand_type, 999):.0f}BB. '
        f'Freq={freq:.1%}. IO ok={io_ok}. Action={action}.'
    )

    tips: List[str] = []
    tips.append(
        'LIMP-CALL DISCIPLINE: Default to raise-or-fold preflop. Limp-call caps '
        'your range and surrenders initiative. Use only with strong implied-odds hands.'
    )
    tips.append(
        f'STACK REQUIREMENT: Need >= {STACK_LIMP_CALL_THRESHOLD.get(hand_type, 999):.0f}BB '
        f'to limp-call with {hand_type}. Current stack={stack_bb:.0f}BB -> '
        f'{"OK" if stack_bb >= STACK_LIMP_CALL_THRESHOLD.get(hand_type, 999) else "NOT OK"}.'
    )

    if raise_bb > RAISE_SIZE_THRESHOLD:
        tips.append(
            f'RAISE TOO LARGE: {raise_bb:.1f}BB exceeds threshold {RAISE_SIZE_THRESHOLD:.1f}BB. '
            f'Fold; implied odds do not compensate for the large investment.'
        )
    if not io_ok:
        tips.append(
            f'IMPLIED ODDS FAIL: Stack/raise ratio={stack_bb/max(raise_bb,0.1):.0f}x < 15x. '
            f'Insufficient implied odds to limp-call profitably.'
        )
    if freq > 0 and action == 'LIMP_CALL':
        tips.append(
            f'LIMP-CALL OK: Conditions met (stack deep, raise small, strong implied odds). '
            f'Frequency={freq:.1%}.'
        )

    return LimpCallResult(
        hand_type=hand_type,
        stack_bb=stack_bb,
        raise_bb=raise_bb,
        position=position,
        limp_call_freq=freq,
        action=action,
        implied_odds_ok=io_ok,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def lc_one_liner(r: LimpCallResult) -> str:
    return (
        f'[LC hand={r.hand_type} stack={r.stack_bb:.0f}BB] '
        f'freq={r.limp_call_freq:.1%} action={r.action} io_ok={"Y" if r.implied_odds_ok else "N"}'
    )
