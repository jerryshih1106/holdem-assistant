"""
Limp-Reraise Frequency Guide (limp_reraise_frequency_guide.py)

Theory: Limp-reraise = limp preflop, then 3-bet someone who raises.
This is a very strong range signal (AA, KK, occasionally QQ).
  - Frequency: 0.5-2% of hands (very rare)
  - Best used vs known aggressive raisers who raise limps often
  - Can be done from any position; most common in EP
  - Sizing: 3-4x the raise size

Since it signals such a strong range, use it sparingly or villains
will adjust by not raising your limps.

DISTINCT FROM:
  limp_call_frequency_guide.py  -- limp then call
  limp_reraise.py               -- core LRR logic
  THIS MODULE                   -- frequency guide + viability
"""

from dataclasses import dataclass, field
from typing import List


LIMP_RERAISE_BASE_FREQ: float = 0.01

VILLAIN_LRR_MODIFIER: dict = {
    'lag':  +0.01,
    'fish': +0.005,
    'rec':   0.00,
    'tag':   0.00,
    'nit':  -0.005,
}

VALUE_HANDS_ONLY: bool = True

LRR_SIZING_MULT: float = 3.5

LRR_VALUE_THRESHOLD: float = 0.88


def _limp_reraise_freq(villain_type: str, position: str, hand_sdv: float) -> float:
    base = LIMP_RERAISE_BASE_FREQ
    mod = VILLAIN_LRR_MODIFIER.get(villain_type.lower(), 0.0)
    pos_mod = +0.002 if position.lower() in ('utg', 'utg1', 'mp') else 0.0
    if hand_sdv < LRR_VALUE_THRESHOLD:
        return 0.0
    freq = base + mod + pos_mod
    return round(min(0.03, max(0.0, freq)), 4)


def _lrr_size_bb(raise_bb: float) -> float:
    return round(raise_bb * LRR_SIZING_MULT, 1)


def _lrr_viable(villain_type: str, hand_sdv: float) -> bool:
    if hand_sdv < LRR_VALUE_THRESHOLD:
        return False
    if villain_type.lower() == 'nit':
        return False
    return True


@dataclass
class LimpRereraiseResult:
    villain_type: str
    position: str
    hand_sdv: float
    raise_bb: float
    lrr_freq: float
    lrr_size: float
    lrr_viable: bool
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_limp_reraise_frequency(
    villain_type: str = 'lag',
    position: str = 'utg',
    hand_sdv: float = 0.92,
    raise_bb: float = 4.0,
) -> LimpRereraiseResult:
    """
    Analyze limp-reraise frequency and viability.

    Args:
        villain_type: 'lag', 'fish', 'rec', 'tag', 'nit'
        position:     Hero's position
        hand_sdv:     Hand strength percentile (0-1); LRR only with >= 0.88
        raise_bb:     Size of the raise hero will 3-bet over (in BB)

    Returns:
        LimpRereraiseResult
    """
    freq = _limp_reraise_freq(villain_type, position, hand_sdv)
    lrr_size = _lrr_size_bb(raise_bb)
    viable = _lrr_viable(villain_type, hand_sdv)

    verdict = (
        f'[LRR vt={villain_type} hand={hand_sdv:.2f}] '
        f'freq={freq:.2%} viable={"Y" if viable else "N"}'
    )

    reasoning = (
        f'Limp-reraise: villain={villain_type}, position={position.upper()}, '
        f'hand_sdv={hand_sdv:.2f}. Threshold={LRR_VALUE_THRESHOLD:.2f}. '
        f'Freq={freq:.2%}. Size={lrr_size:.1f}BB. Viable={viable}.'
    )

    tips: List[str] = []
    tips.append(
        'LIMP-RERAISE RANGE: Reserve for AA, KK (occasionally QQ). '
        'Use very rarely -- overuse teaches villains not to raise your limps.'
    )
    tips.append(
        f'SIZING: {LRR_SIZING_MULT}x the raise = {lrr_size:.1f}BB here. '
        f'Make it large enough to commit villain with a wide range.'
    )

    if not viable:
        tips.append(
            f'NOT VIABLE: Hand SDV={hand_sdv:.2f} below threshold {LRR_VALUE_THRESHOLD:.2f} '
            f'or villain is {villain_type} (raises limps too rarely). '
            f'Just limp-call or fold.'
        )
    if villain_type == 'lag':
        tips.append(
            'LAG TARGET: Best target for LRR. LAGs raise limps frequently; '
            'exploit by trapping with premiums.'
        )
    if villain_type == 'nit':
        tips.append(
            'NIT TARGET: Nits rarely raise limps -- LRR not effective. '
            'Just limp and play postflop.'
        )
    if viable and freq > 0:
        tips.append(
            f'EXECUTE: Limp, wait for raise, then 3-bet to {lrr_size:.1f}BB. '
            f'Commit {freq:.2%} of the time in this spot.'
        )

    return LimpRereraiseResult(
        villain_type=villain_type,
        position=position,
        hand_sdv=hand_sdv,
        raise_bb=raise_bb,
        lrr_freq=freq,
        lrr_size=lrr_size,
        lrr_viable=viable,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def lrr_one_liner(r: LimpRereraiseResult) -> str:
    return (
        f'[LRR vt={r.villain_type} hand={r.hand_sdv:.2f}] '
        f'freq={r.lrr_freq:.2%} viable={"Y" if r.lrr_viable else "N"}'
    )
