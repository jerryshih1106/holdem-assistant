# -*- coding: cp950 -*-
"""flush_draw_frequency_guide.py -- Flush draw frequency and semi-bluff strategy guide."""

from dataclasses import dataclass, field
from typing import List

FD_COMPLETION_FLOP_TO_RIVER: float = 0.36
FD_COMPLETION_TURN_TO_RIVER: float = 0.20

FD_BET_FREQ_IP: dict = {
    'flop': 0.65,
    'turn': 0.55,
}

FD_CR_FREQ_OOP: float = 0.35
NUT_FD_BONUS: float = 0.10

FD_SIZE_BY_STREET: dict = {
    'flop': 0.65,
    'turn': 0.75,
}

FD_MIN_FOLD_EQUITY_NEEDED: float = 0.33

VILLAIN_FD_MOD: dict = {
    'fish':            -0.08,
    'calling_station': -0.12,
    'nit':             +0.10,
    'lag':             -0.06,
    'reg':              0.00,
}


def _fd_bet_freq(is_nut_fd: bool, position: str, street: str) -> float:
    if position == 'ip':
        base = FD_BET_FREQ_IP.get(street, 0.55)
    else:
        base = FD_CR_FREQ_OOP
    if is_nut_fd:
        base = min(1.0, base + NUT_FD_BONUS)
    return round(base, 4)


def _fd_size_pct(street: str, board_texture: str) -> float:
    base = FD_SIZE_BY_STREET.get(street, 0.65)
    if board_texture == 'wet':
        base = min(1.0, base + 0.05)
    elif board_texture == 'dry':
        base = max(0.40, base - 0.05)
    return round(base, 4)


def _fd_ev(equity: float, pot_bb: float, bet_bb: float, fold_pct: float) -> float:
    call_pct = 1.0 - fold_pct
    ev_fold = fold_pct * pot_bb
    ev_call = call_pct * (equity * (pot_bb + bet_bb * 2) - bet_bb)
    return round(ev_fold + ev_call, 4)


def _fd_action(freq: float, villain_type: str) -> str:
    mod = VILLAIN_FD_MOD.get(villain_type, 0.0)
    adj_freq = min(1.0, max(0.0, freq + mod))
    if adj_freq >= 0.55:
        return 'BET'
    if adj_freq >= 0.35:
        return 'CHECK_RAISE'
    return 'CHECK_FOLD'


@dataclass
class FlushDrawFrequencyResult:
    is_nut_fd: bool
    position: str
    street: str
    board_texture: str
    villain_type: str
    pot_bb: float
    bet_freq: float
    size_pct: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_flush_draw_frequency(
    is_nut_fd: bool = True,
    position: str = 'ip',
    street: str = 'flop',
    board_texture: str = 'wet',
    villain_type: str = 'reg',
    pot_bb: float = 10.0,
) -> FlushDrawFrequencyResult:
    bet_freq = _fd_bet_freq(is_nut_fd, position, street)
    size_pct = _fd_size_pct(street, board_texture)
    action = _fd_action(bet_freq, villain_type)

    tips = []
    tips.append(
        "Flush draw completes ~36% flop-to-river and ~20% turn-to-river -- always account for equity."
    )
    tips.append(
        "Nut flush draws should semi-bluff aggressively; non-nut FDs need caution on paired boards."
    )
    if is_nut_fd:
        tips.append("Nut FD: raise frequency is higher -- you have both fold equity and nut outs.")
    if position == 'oop':
        tips.append("OOP flush draw: prefer check-raise over donk-bet to protect your checking range.")
    if villain_type in ('calling_station', 'fish'):
        tips.append("vs calling station/fish: reduce bluff frequency; bet for thin value with FD equity.")
    if villain_type == 'nit':
        tips.append("vs nit: semi-bluff aggressively -- nits fold frequently to pressure.")
    if street == 'turn':
        tips.append("Turn FD: if draw not yet complete, consider sizing up to deny equity and apply max pressure.")

    completion = FD_COMPLETION_FLOP_TO_RIVER if street == 'flop' else FD_COMPLETION_TURN_TO_RIVER
    reasoning = (
        f"FD completion={completion*100:.0f}% from {street}. "
        f"nut={is_nut_fd} pos={position} -> freq={bet_freq*100:.0f}% "
        f"size={size_pct*100:.0f}% action={action}."
    )
    verdict = action

    return FlushDrawFrequencyResult(
        is_nut_fd=is_nut_fd,
        position=position,
        street=street,
        board_texture=board_texture,
        villain_type=villain_type,
        pot_bb=pot_bb,
        bet_freq=bet_freq,
        size_pct=size_pct,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def flush_draw_frequency_one_liner(r: FlushDrawFrequencyResult) -> str:
    nut = 'Y' if r.is_nut_fd else 'N'
    return (
        f"[FD nut={nut} pos={r.position}] "
        f"freq={r.bet_freq*100:.0f}% size={r.size_pct*100:.0f}% action={r.action}"
    )
