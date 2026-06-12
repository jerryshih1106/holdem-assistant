"""
Two Pair Strategy Guide (two_pair_strategy_guide.py)

Theory: Two pair - strong holding but vulnerable.
On wet boards: bet all streets for value and protection.
On turn: size up if board gets wetter.
River: value bet unless board completes a straight/flush.
Multiway: need to be cautious (opponents more likely to have two pair beat).
Stack off comfortably heads-up; cautious multiway.
"""

from dataclasses import dataclass, field
from typing import List

TWO_PAIR_BET_FREQ: dict = {
    'flop':  0.90,
    'turn':  0.82,
    'river': 0.75,
}

BOARD_TP2_MODIFIER: dict = {
    'wet':    +0.05,
    'dry':    -0.05,
    'paired': -0.10,
    'monotone': -0.08,
}

N_OPPONENTS_MODIFIER: dict = {
    2: -0.05,
    3: -0.12,
    4: -0.18,
}

TWO_PAIR_SIZE: dict = {
    'flop':  0.65,
    'turn':  0.75,
    'river': 0.85,
}

STACK_OFF_THRESHOLD_TP2: float = 0.65

HAND_TYPE_MODIFIER: dict = {
    'top_two':    +0.05,
    'top_bottom':  0.0,
    'bottom_two': -0.05,
}


def _two_pair_freq(street: str, board_texture: str, n_opponents: int) -> float:
    base = TWO_PAIR_BET_FREQ.get(street, 0.82)
    board_mod = BOARD_TP2_MODIFIER.get(board_texture, 0.0)
    opp_mod = N_OPPONENTS_MODIFIER.get(min(n_opponents, 4), 0.0)
    freq = base + board_mod + opp_mod
    return round(max(0.0, min(1.0, freq)), 4)


def _two_pair_size(street: str, board_texture: str) -> float:
    base = TWO_PAIR_SIZE.get(street, 0.75)
    if board_texture == 'wet':
        base += 0.05
    elif board_texture == 'paired':
        base -= 0.10
    return round(max(0.40, min(1.0, base)), 4)


def _two_pair_action(freq: float, hand_type: str) -> str:
    hand_mod = HAND_TYPE_MODIFIER.get(hand_type, 0.0)
    adjusted_freq = freq + hand_mod
    if adjusted_freq >= 0.75:
        return 'BET_VALUE_PROTECTION'
    if adjusted_freq >= 0.60:
        return 'BET_VALUE'
    if adjusted_freq >= 0.45:
        return 'BET_OR_CHECK'
    return 'CHECK_CALL'


@dataclass
class TwoPairResult:
    street: str
    board_texture: str
    n_opponents: int
    hand_type: str
    spr: float
    bet_freq: float
    size_pct: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_two_pair(
    street: str = 'flop',
    board_texture: str = 'wet',
    n_opponents: int = 1,
    hand_type: str = 'top_two',
    spr: float = 4.0,
) -> TwoPairResult:
    bet_freq = _two_pair_freq(street, board_texture, n_opponents)
    size_pct = _two_pair_size(street, board_texture)
    action = _two_pair_action(bet_freq, hand_type)

    verdict = (
        f'[2PR type={hand_type} board={board_texture}] '
        f'freq={bet_freq:.0%} action={action}'
    )

    reasoning = (
        f'Two pair ({hand_type}) on {street} ({board_texture} board). '
        f'{n_opponents} opponent(s), SPR={spr:.1f}. '
        f'Bet frequency={bet_freq:.0%}, size={size_pct:.0%} pot. '
        f'Action: {action}.'
    )

    tips = []
    tips.append(
        f'TWO PAIR STRENGTH: {hand_type} is a strong holding -- bet {bet_freq:.0%} on {street}. '
        f'Two pair beats top pair, overpairs, and most single-pair hands. '
        f'Build the pot aggressively for value and protection.'
    )
    tips.append(
        f'PROTECTION: Two pair needs protection on wet boards. '
        f'Size up to {size_pct:.0%} pot to charge flush and straight draws. '
        f'Turn sizing ({TWO_PAIR_SIZE["turn"]:.0%}) and river ({TWO_PAIR_SIZE["river"]:.0%}) '
        f'should increase to extract maximum value.'
    )

    if n_opponents > 1:
        tips.append(
            f'MULTIWAY ({n_opponents} opponents): Be more cautious -- in a {n_opponents}-way pot '
            f'someone is more likely to have you beaten. '
            f'Stack off threshold increases; consider pot controlling if action heats up.'
        )

    if board_texture == 'wet':
        tips.append(
            f'WET BOARD: Fast play is essential for two pair protection. '
            f'Draws have significant equity vs two pair -- betting charges them '
            f'and denies free cards. Never slow play two pair on wet textures.'
        )

    if board_texture == 'paired':
        tips.append(
            f'PAIRED BOARD: Slow down -- villain could have full house (trips + any pair). '
            f'Reduce sizing and frequency; be cautious vs raises on paired boards.'
        )

    if hand_type == 'bottom_two':
        tips.append(
            f'BOTTOM TWO PAIR: Weakest two pair -- more cautious approach. '
            f'Stack off threshold is higher; fold to heavy multiway pressure '
            f'or large raises from nit opponents.'
        )

    if spr <= 2.0:
        tips.append(
            f'LOW SPR ({spr:.1f}): Commit with two pair at this stack depth. '
            f'Stack off threshold ({STACK_OFF_THRESHOLD_TP2:.0%}) is easily cleared.'
        )

    return TwoPairResult(
        street=street,
        board_texture=board_texture,
        n_opponents=n_opponents,
        hand_type=hand_type,
        spr=spr,
        bet_freq=bet_freq,
        size_pct=size_pct,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tp2_one_liner(r: TwoPairResult) -> str:
    return (
        f'[2PR type={r.hand_type} board={r.board_texture}] '
        f'freq={r.bet_freq:.0%} action={r.action}'
    )
