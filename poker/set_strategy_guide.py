"""
Set Strategy Guide (set_strategy_guide.py)

Theory: Sets are very strong (only ~2-3% of hands beat them).
Usually slow play on flop to let villain catch up.
On wet boards: fast play to protect equity.
In multiway pots: bet more (more people to extract from).
River: large value bet.
Stack off comfortably in most situations.
SPR considerations: low SPR = fast play; high SPR = can slow play more.
"""

from dataclasses import dataclass, field
from typing import List

SET_BET_FREQ: dict = {
    'flop':  0.65,
    'turn':  0.85,
    'river': 0.90,
}

BOARD_SET_MODIFIER: dict = {
    'wet':      +0.20,
    'dry':      -0.10,
    'monotone': +0.10,
    'paired':   -0.05,
}

N_PLAYERS_SET_MOD: dict = {
    2: 0.0,
    3: +0.10,
    4: +0.15,
}

SPR_SLOWPLAY_THRESHOLD: float = 6.0

SET_SIZE: dict = {
    'flop':  0.55,
    'turn':  0.70,
    'river': 0.90,
}


def _set_bet_freq(
    street: str,
    board_texture: str,
    n_players: int,
    spr: float,
) -> float:
    base = SET_BET_FREQ.get(street, 0.85)
    board_mod = BOARD_SET_MODIFIER.get(board_texture, 0.0)
    player_mod = N_PLAYERS_SET_MOD.get(min(n_players, 4), 0.0)
    # Low SPR: fast play always; high SPR: can slow play
    if spr < SPR_SLOWPLAY_THRESHOLD and street == 'flop':
        spr_mod = +0.15
    elif spr >= SPR_SLOWPLAY_THRESHOLD and street == 'flop':
        spr_mod = -0.10
    else:
        spr_mod = 0.0
    freq = base + board_mod + player_mod + spr_mod
    return round(max(0.0, min(1.0, freq)), 4)


def _set_action(freq: float, spr: float) -> str:
    if spr <= 2.0:
        return 'BET_COMMIT'
    if freq >= 0.80:
        return 'BET_VALUE_FAST_PLAY'
    if freq >= 0.60:
        return 'BET_VALUE'
    return 'SLOW_PLAY_CHECK_RAISE'


def _slowplay_ok(board_texture: str, spr: float, n_players: int) -> bool:
    if board_texture in ('wet', 'monotone'):
        return False
    if spr < SPR_SLOWPLAY_THRESHOLD:
        return False
    if n_players >= 3:
        return False
    return True


@dataclass
class SetResult:
    street: str
    board_texture: str
    n_players: int
    spr: float
    bet_freq: float
    action: str
    slowplay_ok: bool
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_set(
    street: str = 'flop',
    board_texture: str = 'dry',
    n_players: int = 2,
    spr: float = 8.0,
) -> SetResult:
    bet_freq = _set_bet_freq(street, board_texture, n_players, spr)
    action = _set_action(bet_freq, spr)
    slowplay = _slowplay_ok(board_texture, spr, n_players)

    verdict = (
        f'[SET board={board_texture} spr={spr:.1f}] '
        f'freq={bet_freq:.0%} slowplay={"Y" if slowplay else "N"}'
    )

    reasoning = (
        f'Set on {street} ({board_texture} board), {n_players} players, SPR={spr:.1f}. '
        f'Bet frequency={bet_freq:.0%}. Action: {action}. '
        f'Slow play viable: {"yes" if slowplay else "no"}.'
    )

    tips = []
    tips.append(
        f'SET STRENGTH: Sets beat ~97-98% of all possible hands. '
        f'Primary goal is to maximize pot size -- fast play on wet boards, '
        f'slow play viable only on dry boards with high SPR in position.'
    )
    tips.append(
        f'STREET STRATEGY: Flop ({SET_BET_FREQ["flop"]:.0%}) -> '
        f'Turn ({SET_BET_FREQ["turn"]:.0%}) -> '
        f'River ({SET_BET_FREQ["river"]:.0%}). '
        f'Turn and river bet frequencies increase -- by river always bet for max value.'
    )

    if board_texture in ('wet', 'monotone'):
        tips.append(
            f'WET/MONOTONE BOARD: Fast play required -- do not slow play sets here. '
            f'Draws have significant equity and could improve to beat you. '
            f'Bet to charge draws and extract value while ahead.'
        )

    if spr >= SPR_SLOWPLAY_THRESHOLD and board_texture == 'dry':
        tips.append(
            f'HIGH SPR ({spr:.1f}) + DRY BOARD: Slow play is viable on flop. '
            f'Check to let villain catch up with top/middle pair. '
            f'Begin fast playing on turn to build the pot for river stack off.'
        )

    if n_players >= 3:
        tips.append(
            f'MULTIWAY ({n_players} players): Bet more often and larger. '
            f'More opponents = more value extraction opportunities. '
            f'Also more chances someone has a draw -- protect accordingly.'
        )

    if spr <= 2.0:
        tips.append(
            f'LOW SPR ({spr:.1f}): Commit all chips immediately. '
            f'At this SPR there is no slow play value -- just bet/get it in.'
        )

    return SetResult(
        street=street,
        board_texture=board_texture,
        n_players=n_players,
        spr=spr,
        bet_freq=bet_freq,
        action=action,
        slowplay_ok=slowplay,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def set_one_liner(r: SetResult) -> str:
    return (
        f'[SET board={r.board_texture} spr={r.spr:.1f}] '
        f'freq={r.bet_freq:.0%} slowplay={"Y" if r.slowplay_ok else "N"}'
    )
