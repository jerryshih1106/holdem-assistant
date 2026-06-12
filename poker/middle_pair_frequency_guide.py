"""
Middle Pair Frequency Guide (middle_pair_frequency_guide.py)

Theory: Middle pair (2nd pair) - marginal holding.
Bet for thin value vs fish/nit. Check vs LAG (likely to raise).
Call down when pot odds justify.
On turn: mostly check unless villain is passive.
On river: thin value if villain is calling station; otherwise check-call.
"""

from dataclasses import dataclass, field
from typing import List

MIDDLE_PAIR_BET_FREQ_BY_STREET: dict = {
    'flop':  0.55,
    'turn':  0.30,
    'river': 0.20,
}

VILLAIN_MP_MODIFIER: dict = {
    'fish':            +0.15,
    'calling_station': +0.20,
    'nit':             +0.10,
    'lag':             -0.20,
    'reg':             0.0,
}

BOARD_MP_MODIFIER: dict = {
    'dry':  +0.10,
    'wet':  -0.10,
    'paired': 0.0,
    'monotone': -0.05,
}

MP_VALUE_THRESHOLD: float = 0.45


def _middle_pair_bet_freq(street: str, villain_type: str, board_texture: str) -> float:
    base = MIDDLE_PAIR_BET_FREQ_BY_STREET.get(street, 0.30)
    vil_mod = VILLAIN_MP_MODIFIER.get(villain_type, 0.0)
    board_mod = BOARD_MP_MODIFIER.get(board_texture, 0.0)
    freq = base + vil_mod + board_mod
    return round(max(0.0, min(1.0, freq)), 4)


def _middle_pair_action(freq: float) -> str:
    if freq >= MP_VALUE_THRESHOLD:
        return 'BET_THIN_VALUE'
    if freq >= 0.30:
        return 'CHECK_CALL'
    return 'CHECK_FOLD'


def _bet_size_pct(street: str, villain_type: str) -> float:
    base_sizes = {
        'flop':  0.40,
        'turn':  0.50,
        'river': 0.35,
    }
    size = base_sizes.get(street, 0.40)
    if villain_type in ('calling_station', 'fish'):
        size += 0.05
    elif villain_type == 'lag':
        size -= 0.10
    return round(max(0.20, min(0.75, size)), 4)


@dataclass
class MiddlePairResult:
    street: str
    villain_type: str
    board_texture: str
    kicker_quality: str
    bet_freq: float
    action: str
    bet_size_pct: float
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_middle_pair(
    street: str = 'flop',
    villain_type: str = 'reg',
    board_texture: str = 'dry',
    kicker_quality: str = 'middle',
) -> MiddlePairResult:
    bet_freq = _middle_pair_bet_freq(street, villain_type, board_texture)
    action = _middle_pair_action(bet_freq)
    size_pct = _bet_size_pct(street, villain_type)

    verdict = (
        f'[MP street={street} vt={villain_type}] '
        f'freq={bet_freq:.0%} action={action}'
    )

    reasoning = (
        f'Middle pair on {street} vs {villain_type} ({board_texture} board). '
        f'Kicker quality: {kicker_quality}. '
        f'Bet frequency={bet_freq:.0%}, threshold={MP_VALUE_THRESHOLD:.0%}. '
        f'Recommended action: {action} at {size_pct:.0%} pot.'
    )

    tips = []
    tips.append(
        f'MIDDLE PAIR STRATEGY: On {street}, bet frequency is {bet_freq:.0%}. '
        f'Middle pair is a marginal holding -- bet for thin value only when '
        f'villain is unlikely to raise and likely to call with worse.'
    )
    tips.append(
        f'STREET MANAGEMENT: Flop freq {MIDDLE_PAIR_BET_FREQ_BY_STREET["flop"]:.0%} '
        f'-> turn {MIDDLE_PAIR_BET_FREQ_BY_STREET["turn"]:.0%} '
        f'-> river {MIDDLE_PAIR_BET_FREQ_BY_STREET["river"]:.0%}. '
        f'Mostly check/fold by river unless facing passive calling station.'
    )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Check middle pair -- LAG will raise frequently, '
            f'turning your marginal hand into a difficult spot. '
            f'Check-call if pot odds are correct; do not bet-fold.'
        )
    elif villain_type in ('fish', 'calling_station'):
        tips.append(
            f'VS {villain_type.upper()}: Bet for thin value -- they call with worse pairs '
            f'and dominated kickers. Use smaller sizing ({size_pct:.0%} pot) to '
            f'keep their calling range wide.'
        )

    if board_texture == 'wet':
        tips.append(
            f'WET BOARD: Reduce bet frequency with middle pair on wet textures. '
            f'Many draws outflop middle pair -- check more often to control pot size.'
        )

    if kicker_quality == 'bottom':
        tips.append(
            f'WEAK KICKER: With bottom kicker and middle pair, lean toward check/fold. '
            f'Reverse implied odds are significant if villain has same pair with better kicker.'
        )

    return MiddlePairResult(
        street=street,
        villain_type=villain_type,
        board_texture=board_texture,
        kicker_quality=kicker_quality,
        bet_freq=bet_freq,
        action=action,
        bet_size_pct=size_pct,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def mp_one_liner(r: MiddlePairResult) -> str:
    return (
        f'[MP street={r.street} vt={r.villain_type}] '
        f'freq={r.bet_freq:.0%} action={r.action}'
    )
