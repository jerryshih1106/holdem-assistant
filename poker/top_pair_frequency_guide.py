"""
Top Pair Frequency Guide (top_pair_frequency_guide.py)

Theory: Top pair is bread-and-butter value hand.
Frequency: flop cbet 70-85% with TP.
Turn: continue 60-75% depending on kicker/board.
River: value bet 55-70%.
Sizing: medium on coordinated boards, larger vs calling stations.
Good kicker (TPTK): bet all 3 streets.
Weak kicker (TPWK): check turn if villain is aggressive.
"""

from dataclasses import dataclass, field
from typing import List

TP_BET_FREQ_BY_STREET: dict = {
    'flop':  0.78,
    'turn':  0.68,
    'river': 0.62,
}

KICKER_QUALITY_MODIFIER: dict = {
    'top':    +0.10,
    'middle':  0.0,
    'weak':   -0.12,
    'bottom': -0.20,
}

VILLAIN_TP_MODIFIER: dict = {
    'fish':            +0.08,
    'calling_station': +0.12,
    'nit':             -0.05,
    'lag':             -0.10,
    'reg':              0.0,
}

TP_SIZE_BY_STREET: dict = {
    'flop':  0.60,
    'turn':  0.68,
    'river': 0.75,
}

BOARD_TP_MODIFIER: dict = {
    'dry':      +0.05,
    'wet':      -0.05,
    'paired':   -0.08,
    'monotone': -0.10,
}


def _tp_bet_freq(
    street: str,
    kicker_quality: str,
    villain_type: str,
    board_texture: str,
) -> float:
    base = TP_BET_FREQ_BY_STREET.get(street, 0.68)
    kicker_mod = KICKER_QUALITY_MODIFIER.get(kicker_quality, 0.0)
    vil_mod = VILLAIN_TP_MODIFIER.get(villain_type, 0.0)
    board_mod = BOARD_TP_MODIFIER.get(board_texture, 0.0)
    freq = base + kicker_mod + vil_mod + board_mod
    return round(max(0.0, min(1.0, freq)), 4)


def _tp_size_pct(street: str, villain_type: str) -> float:
    base = TP_SIZE_BY_STREET.get(street, 0.65)
    if villain_type in ('calling_station', 'fish'):
        base += 0.08
    elif villain_type == 'lag':
        base -= 0.05
    return round(max(0.30, min(1.0, base)), 4)


def _tp_action(freq: float) -> str:
    if freq >= 0.65:
        return 'BET_VALUE'
    if freq >= 0.50:
        return 'BET_OR_CHECK'
    if freq >= 0.35:
        return 'CHECK_CALL'
    return 'CHECK_FOLD'


@dataclass
class TopPairResult:
    street: str
    kicker_quality: str
    villain_type: str
    board_texture: str
    bet_freq: float
    size_pct: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_top_pair(
    street: str = 'flop',
    kicker_quality: str = 'top',
    villain_type: str = 'reg',
    board_texture: str = 'dry',
) -> TopPairResult:
    bet_freq = _tp_bet_freq(street, kicker_quality, villain_type, board_texture)
    size_pct = _tp_size_pct(street, villain_type)
    action = _tp_action(bet_freq)

    verdict = (
        f'[TP street={street} kicker={kicker_quality}] '
        f'freq={bet_freq:.0%} size={size_pct:.0%} action={action}'
    )

    reasoning = (
        f'Top pair ({kicker_quality} kicker) on {street} vs {villain_type} '
        f'({board_texture} board). '
        f'Bet frequency={bet_freq:.0%}, size={size_pct:.0%} pot. '
        f'Action: {action}.'
    )

    tips = []
    tips.append(
        f'TOP PAIR VALUE: Bet {bet_freq:.0%} of the time on {street}. '
        f'Top pair is your primary value hand -- extract value on all streets '
        f'when kicker quality supports it.'
    )
    tips.append(
        f'SIZING: Use {size_pct:.0%} pot on {street}. '
        f'Medium sizing on coordinated boards; larger vs calling stations. '
        f'River sizing ({TP_SIZE_BY_STREET["river"]:.0%}) should be largest to extract maximum value.'
    )

    if kicker_quality == 'top':
        tips.append(
            f'TPTK (Top pair, top kicker): Bet all 3 streets. '
            f'This is your strongest top pair holding -- extract maximum value '
            f'and do not slow down on any street.'
        )
    elif kicker_quality in ('weak', 'bottom'):
        tips.append(
            f'TPWK/TPBK: Check more often on turn vs aggressive opponents. '
            f'Weak kicker means more reverse implied odds -- villain may have '
            f'same pair with better kicker. Check turn if villain is LAG or reg.'
        )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Check top pair more often and check-call. '
            f'LAG will bet/raise with many hands including bluffs -- '
            f'let them put money in the pot rather than you.'
        )
    elif villain_type == 'calling_station':
        tips.append(
            f'VS CALLING STATION: Bet all 3 streets for max value. '
            f'Size up -- calling stations pay off with worse pairs and draws. '
            f'Do not slow play or check-raise; just bet and get called.'
        )

    if board_texture == 'wet':
        tips.append(
            f'WET BOARD: Slightly reduce frequency but maintain value betting. '
            f'Sizing matters more on wet boards -- protect your equity vs draws '
            f'by betting larger relative to pot.'
        )

    return TopPairResult(
        street=street,
        kicker_quality=kicker_quality,
        villain_type=villain_type,
        board_texture=board_texture,
        bet_freq=bet_freq,
        size_pct=size_pct,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tp_one_liner(r: TopPairResult) -> str:
    return (
        f'[TP street={r.street} kicker={r.kicker_quality}] '
        f'freq={r.bet_freq:.0%} size={r.size_pct:.0%} action={r.action}'
    )
