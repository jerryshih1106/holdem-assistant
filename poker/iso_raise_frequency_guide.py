"""
ISO Raise Frequency Guide (iso_raise_frequency_guide.py)

Theory: ISO raising vs limpers isolates one (usually weak) player to play
heads-up with position and initiative.
  - vs 1 limper: 3-4x BB
  - vs 2 limpers: 4-5x BB
  - vs 3+ limpers: 5-6x BB

ISO frequency by position:
  BTN vs 1 limper: 55-65%
  CO:              45-55%
  MP:              30-40%
  UTG:             20% (rare; many behind)

Adjust:
  fish limper  -> widen (more value from calls)
  nit limper   -> tighten (nit limps are stronger)

DISTINCT FROM:
  iso_raise.py           -- core ISO logic
  iso_overlimper_guide.py -- multi-limper ISO
  THIS MODULE            -- frequency guide per position
"""

from dataclasses import dataclass, field
from typing import List


ISO_FREQ_BY_POSITION: dict = {
    'btn': 0.60,
    'co':  0.50,
    'mp':  0.35,
    'hj':  0.40,
    'utg': 0.20,
}

EXTRA_LIMPER_ISO_REDUCTION: float = -0.08

LIMPER_TYPE_ISO_MOD: dict = {
    'fish': +0.10,
    'rec':  +0.05,
    'tag':   0.00,
    'nit':  -0.08,
}

ISO_SIZE_PER_LIMPER: dict = {
    '1':    3.5,
    '2':    4.5,
    '3':    5.5,
    '4plus': 6.0,
}


def _iso_freq(position: str, n_limpers: int, limper_type: str) -> float:
    base = ISO_FREQ_BY_POSITION.get(position.lower(), ISO_FREQ_BY_POSITION['co'])
    extra = (n_limpers - 1) * EXTRA_LIMPER_ISO_REDUCTION if n_limpers > 1 else 0.0
    ltype_mod = LIMPER_TYPE_ISO_MOD.get(limper_type.lower(), 0.0)
    freq = base + extra + ltype_mod
    return round(min(0.80, max(0.10, freq)), 3)


def _iso_size_bb(n_limpers: int, bb_size: float = 1.0) -> float:
    if n_limpers >= 4:
        key = '4plus'
    else:
        key = str(max(1, n_limpers))
    mult = ISO_SIZE_PER_LIMPER.get(key, 3.5)
    return round(mult * bb_size + n_limpers * bb_size, 1)


def _iso_action(hand_sdv: float, freq: float) -> str:
    if hand_sdv >= freq:
        return 'ISO_RAISE'
    return 'FOLD_OR_LIMP'


@dataclass
class IsoRaiseFreqResult:
    position: str
    n_limpers: int
    limper_type: str
    hand_sdv: float
    iso_freq: float
    iso_size_bb: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_iso_raise_frequency(
    position: str = 'btn',
    n_limpers: int = 1,
    limper_type: str = 'fish',
    hand_sdv: float = 0.55,
    bb_size: float = 1.0,
) -> IsoRaiseFreqResult:
    """
    Analyze ISO raise frequency and sizing vs limpers.

    Args:
        position:    Hero's position ('btn','co','mp','hj','utg')
        n_limpers:   Number of limpers in front
        limper_type: 'fish', 'rec', 'tag', 'nit'
        hand_sdv:    Hand strength percentile (0-1)
        bb_size:     Big blind size (default 1.0)

    Returns:
        IsoRaiseFreqResult
    """
    freq = _iso_freq(position, n_limpers, limper_type)
    size = _iso_size_bb(n_limpers, bb_size)
    action = _iso_action(hand_sdv, freq)

    verdict = (
        f'[ISO pos={position.upper()} limpers={n_limpers}] '
        f'freq={freq:.0%} size={size:.1f}BB action={action}'
    )

    reasoning = (
        f'ISO raise: {position.upper()} vs {n_limpers} {limper_type} limper(s). '
        f'Base={ISO_FREQ_BY_POSITION.get(position, 0.50):.0%}, '
        f'ltype_mod={LIMPER_TYPE_ISO_MOD.get(limper_type, 0):+.0%}. '
        f'Freq={freq:.0%}. Size={size:.1f}BB. Hand SDV={hand_sdv:.2f} -> {action}.'
    )

    tips: List[str] = []
    tips.append(
        f'ISO SIZING: vs {n_limpers} limper(s) size to {size:.1f}BB. '
        f'Each additional limper adds ~1BB to the ISO size.'
    )
    tips.append(
        f'POSITION MATTERS: ISO freq from {position.upper()} = {freq:.0%}. '
        f'Later position -> wider ISO range and more postflop control.'
    )

    if limper_type == 'fish':
        tips.append(
            'FISH LIMPER: Widen ISO range significantly. Fish calls with dominated hands; '
            'extract maximum value from weak callers.'
        )
    if limper_type == 'nit':
        tips.append(
            'NIT LIMPER: Tighten ISO range. Nits limp-call/raise with strong hands; '
            'avoid bloating pot with marginal holdings.'
        )
    if n_limpers >= 3:
        tips.append(
            f'MANY LIMPERS: With {n_limpers}+ limpers the pot is already large. '
            f'ISO only with strong hands; multi-way pots reduce bluff equity.'
        )
    if action == 'ISO_RAISE':
        tips.append(
            f'EXECUTE: Raise to {size:.1f}BB with SDV={hand_sdv:.2f} >= freq={freq:.0%}. '
            f'Take initiative and play heads-up with position.'
        )

    return IsoRaiseFreqResult(
        position=position,
        n_limpers=n_limpers,
        limper_type=limper_type,
        hand_sdv=hand_sdv,
        iso_freq=freq,
        iso_size_bb=size,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def iso_one_liner(r: IsoRaiseFreqResult) -> str:
    return (
        f'[ISO pos={r.position.upper()} limpers={r.n_limpers}] '
        f'freq={r.iso_freq:.0%} size={r.iso_size_bb:.1f}BB action={r.action}'
    )
