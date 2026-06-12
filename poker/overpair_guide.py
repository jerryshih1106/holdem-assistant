"""
Overpair Guide (overpair_guide.py)

Theory: Overpair (pocket pair above all board cards). Semi-premium holding.
Bet all 3 streets for value vs calling stations.
On wet boards: size up (protection + value).
On paired boards: slow down (villain could have trips).
vs aggressive opponents: be cautious about going broke with QQ on KJ9 board.
"""

from dataclasses import dataclass, field
from typing import List

OVERPAIR_BET_FREQ: dict = {
    'flop':  0.82,
    'turn':  0.72,
    'river': 0.65,
}

BOARD_OP_MODIFIER: dict = {
    'dry':      +0.05,
    'wet':      -0.05,
    'paired':   -0.15,
    'monotone': -0.08,
}

VILLAIN_OP_MODIFIER: dict = {
    'fish':            +0.10,
    'calling_station': +0.10,
    'lag':             -0.15,
    'nit':             -0.05,
    'reg':              0.0,
}

STACK_OFF_THRESHOLD: dict = {
    'aa': 0.68,
    'kk': 0.72,
    'qq': 0.78,
    'jj': 0.82,
}

OP_SIZE_BY_BOARD: dict = {
    'dry':      0.55,
    'wet':      0.72,
    'paired':   0.45,
    'monotone': 0.65,
}


def _op_bet_freq(street: str, board_texture: str, villain_type: str) -> float:
    base = OVERPAIR_BET_FREQ.get(street, 0.72)
    board_mod = BOARD_OP_MODIFIER.get(board_texture, 0.0)
    vil_mod = VILLAIN_OP_MODIFIER.get(villain_type, 0.0)
    freq = base + board_mod + vil_mod
    return round(max(0.0, min(1.0, freq)), 4)


def _op_size(board_texture: str, villain_type: str) -> float:
    base = OP_SIZE_BY_BOARD.get(board_texture, 0.55)
    if villain_type in ('fish', 'calling_station'):
        base += 0.05
    elif villain_type == 'lag':
        base -= 0.05
    return round(max(0.30, min(1.0, base)), 4)


def _should_stack_off(pair_rank: str, board_texture: str, villain_type: str) -> bool:
    pr = pair_rank.lower()
    threshold = STACK_OFF_THRESHOLD.get(pr, 0.78)
    base_freq = _op_bet_freq('flop', board_texture, villain_type)
    if villain_type == 'lag' and board_texture in ('wet', 'monotone'):
        return False
    if board_texture == 'paired' and pr in ('qq', 'jj'):
        return False
    return base_freq >= threshold


@dataclass
class OverpairResult:
    pair_rank: str
    board_texture: str
    villain_type: str
    street: str
    spr: float
    bet_freq: float
    size_pct: float
    stack_off_ok: bool
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_overpair(
    pair_rank: str = 'qq',
    board_texture: str = 'dry',
    villain_type: str = 'reg',
    street: str = 'flop',
    spr: float = 4.0,
) -> OverpairResult:
    pr = pair_rank.lower()
    bet_freq = _op_bet_freq(street, board_texture, villain_type)
    size_pct = _op_size(board_texture, villain_type)
    stack_off_ok = _should_stack_off(pr, board_texture, villain_type)

    verdict = (
        f'[OP rank={pr.upper()} board={board_texture}] '
        f'freq={bet_freq:.0%} stack_off={"Y" if stack_off_ok else "N"}'
    )

    reasoning = (
        f'Overpair {pr.upper()} on {street} ({board_texture} board) vs {villain_type}. '
        f'SPR={spr:.1f}. Bet frequency={bet_freq:.0%}, size={size_pct:.0%} pot. '
        f'Stack off: {"yes" if stack_off_ok else "no"}.'
    )

    tips = []
    tips.append(
        f'OVERPAIR VALUE: {pr.upper()} is above all board cards. '
        f'Bet {bet_freq:.0%} of the time on {street} for value. '
        f'Overpairs lose value rapidly on coordinated boards -- bet to charge draws.'
    )
    tips.append(
        f'SIZING: Use {size_pct:.0%} pot on {board_texture} board. '
        f'Wet boards require larger sizing to protect equity vs flush/straight draws. '
        f'Dry boards can use smaller sizing to keep villain calling range wide.'
    )

    if board_texture == 'paired':
        tips.append(
            f'PAIRED BOARD WARNING: Slow down with {pr.upper()} -- villain could have trips. '
            f'Reduce bet frequency and size. Check-call rather than bet-3bet on paired boards.'
        )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Be cautious going broke with {pr.upper()}. '
            f'LAG raises overpairs frequently with draws and worse pairs. '
            f'Consider pot control -- check-call rather than bet-3bet.'
        )

    if board_texture == 'wet':
        tips.append(
            f'WET BOARD: Size up for protection. Your overpair has good equity now '
            f'but loses to completed draws. Betting {size_pct:.0%} charges draws '
            f'and builds the pot for continued value on later streets.'
        )

    if spr <= 2.0:
        tips.append(
            f'LOW SPR ({spr:.1f}): Commit your stack with {pr.upper()}. '
            f'At this SPR you are priced in -- bet/call off comfortably.'
        )

    return OverpairResult(
        pair_rank=pr,
        board_texture=board_texture,
        villain_type=villain_type,
        street=street,
        spr=spr,
        bet_freq=bet_freq,
        size_pct=size_pct,
        stack_off_ok=stack_off_ok,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def op_one_liner(r: OverpairResult) -> str:
    return (
        f'[OP rank={r.pair_rank.upper()} board={r.board_texture}] '
        f'freq={r.bet_freq:.0%} stack_off={"Y" if r.stack_off_ok else "N"}'
    )
