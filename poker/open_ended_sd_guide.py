# -*- coding: cp950 -*-
"""open_ended_sd_guide.py -- Open-ended straight draw (OESD) frequency and strategy guide."""

from dataclasses import dataclass, field
from typing import List

OESD_COMPLETION_F2R: float = 0.32
OESD_COMPLETION_T2R: float = 0.17
OESD_COMBO_WITH_FD_OUTS: int = 15

OESD_BET_FREQ: dict = {
    'ip_flop':    0.60,
    'ip_turn':    0.50,
    'oop_flop_cr': 0.30,
}

OESD_SIZE: dict = {
    'flop': 0.60,
    'turn': 0.70,
}

OESD_FD_COMBO_FREQ_BONUS: float = 0.15

VILLAIN_OESD_MOD: dict = {
    'passive':         +0.08,
    'fish':            -0.10,
    'nit':             +0.10,
    'lag':             -0.08,
    'reg':              0.00,
    'calling_station': -0.15,
}


def _oesd_equity(street: str, has_fd: bool) -> float:
    if has_fd:
        outs = OESD_COMBO_WITH_FD_OUTS
        if street == 'flop':
            return round(min(1.0, outs * 0.036), 4)
        else:
            return round(min(1.0, outs * 0.022), 4)
    if street == 'flop':
        return OESD_COMPLETION_F2R
    return OESD_COMPLETION_T2R


def _oesd_bet_freq(position: str, street: str, has_fd: bool, villain_type: str) -> float:
    key = f"{position}_{street}"
    base = OESD_BET_FREQ.get(key, 0.40)
    if has_fd:
        base = min(1.0, base + OESD_FD_COMBO_FREQ_BONUS)
    mod = VILLAIN_OESD_MOD.get(villain_type, 0.0)
    return round(min(1.0, max(0.0, base + mod)), 4)


def _oesd_action(freq: float, villain_type: str) -> str:
    if villain_type in ('passive', 'nit'):
        if freq >= 0.50:
            return 'BET'
        if freq >= 0.30:
            return 'CHECK_CALL'
        return 'CHECK_FOLD'
    if freq >= 0.55:
        return 'BET'
    if freq >= 0.30:
        return 'CHECK_CALL'
    return 'CHECK_FOLD'


@dataclass
class OesdResult:
    position: str
    street: str
    has_fd: bool
    villain_type: str
    board_texture: str
    equity: float
    bet_freq: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_open_ended_sd(
    position: str = 'ip',
    street: str = 'flop',
    has_fd: bool = False,
    villain_type: str = 'reg',
    board_texture: str = 'wet',
) -> OesdResult:
    equity = _oesd_equity(street, has_fd)
    bet_freq = _oesd_bet_freq(position, street, has_fd, villain_type)
    action = _oesd_action(bet_freq, villain_type)

    tips = []
    tips.append(
        "OESD has 8 outs -- completes ~32% flop-to-river and ~17% turn-to-river."
    )
    tips.append(
        "Use positional advantage with OESD: IP you control the pace of the hand."
    )
    if has_fd:
        tips.append(
            "OESD + FD combo = ~15 outs (~54% equity) -- treat this as near-favorite; bet/raise aggressively."
        )
    if villain_type in ('passive', 'nit'):
        tips.append("vs passive/nit: bet more streets for semi-bluff value -- they fold too often.")
    if villain_type in ('lag', 'calling_station'):
        tips.append("vs aggressive/calling players: prefer check-call to avoid inflated pots with marginal equity.")
    if street == 'turn' and not has_fd:
        tips.append("Turn OESD with no FD: equity shrinks to ~17%; consider pot odds carefully before calling large bets.")

    completion = OESD_COMPLETION_F2R if street == 'flop' else OESD_COMPLETION_T2R
    fd_note = f" (+FD combo eq={equity*100:.0f}%)" if has_fd else f" eq={completion*100:.0f}%"
    reasoning = (
        f"OESD pos={position} street={street}{fd_note}. "
        f"freq={bet_freq*100:.0f}% action={action}."
    )
    verdict = action

    return OesdResult(
        position=position,
        street=street,
        has_fd=has_fd,
        villain_type=villain_type,
        board_texture=board_texture,
        equity=equity,
        bet_freq=bet_freq,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def oesd_one_liner(r: OesdResult) -> str:
    fd = 'Y' if r.has_fd else 'N'
    return (
        f"[OESD fd={fd} pos={r.position}] "
        f"eq={r.equity*100:.0f}% freq={r.bet_freq*100:.0f}% action={r.action}"
    )
