# -*- coding: cp950 -*-
"""combo_draw_frequency_guide.py -- Combo draw (FD+OESD or FD+overcard) frequency guide."""

from dataclasses import dataclass, field
from typing import List

COMBO_DRAW_OUTS: dict = {
    'fd_oesd':     15,
    'fd_overcard': 12,
    'fd_gutshot':  12,
}

COMBO_DRAW_EQUITY: dict = {
    'fd_oesd_f2r':    0.54,
    'fd_oc_f2r':      0.45,
    'fd_gutshot_f2r': 0.45,
    'fd_oesd_t2r':    0.33,
    'fd_oc_t2r':      0.28,
    'fd_gutshot_t2r': 0.28,
}

COMBO_BET_FREQ: float = 0.85

COMBO_SIZE: dict = {
    'flop': 0.75,
    'turn': 0.82,
}

STACK_OFF_THRESHOLD_COMBO: float = 0.50

VILLAIN_COMBO_MOD: dict = {
    'nit':             +0.05,
    'fish':            -0.05,
    'reg':              0.00,
    'lag':             -0.03,
    'calling_station': -0.08,
}


def _combo_equity(combo_type: str, street: str) -> float:
    suffix = 'f2r' if street == 'flop' else 't2r'
    if combo_type == 'fd_oesd':
        key = f'fd_oesd_{suffix}'
    elif combo_type == 'fd_overcard':
        key = f'fd_oc_{suffix}'
    else:
        key = f'fd_gutshot_{suffix}'
    return COMBO_DRAW_EQUITY.get(key, 0.45)


def _combo_action(equity: float, position: str, villain_type: str) -> str:
    mod = VILLAIN_COMBO_MOD.get(villain_type, 0.0)
    adj_freq = min(1.0, COMBO_BET_FREQ + mod)
    if villain_type == 'calling_station':
        return 'BET_VALUE'
    if position == 'oop' and equity < 0.50:
        return 'CHECK_RAISE'
    if adj_freq >= 0.75:
        return 'BET_RAISE'
    return 'BET'


def _combo_stack_off_ok(equity: float, spr: float) -> bool:
    if spr <= 1.5:
        return True
    return equity >= STACK_OFF_THRESHOLD_COMBO


@dataclass
class ComboDrawFrequencyResult:
    combo_type: str
    street: str
    position: str
    villain_type: str
    spr: float
    pot_bb: float
    equity: float
    action: str
    stack_off_ok: bool
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_combo_draw_frequency(
    combo_type: str = 'fd_oesd',
    street: str = 'flop',
    position: str = 'ip',
    villain_type: str = 'reg',
    spr: float = 4.0,
    pot_bb: float = 10.0,
) -> ComboDrawFrequencyResult:
    equity = _combo_equity(combo_type, street)
    action = _combo_action(equity, position, villain_type)
    stack_off_ok = _combo_stack_off_ok(equity, spr)

    tips = []
    tips.append(
        "Combo draws (FD+OESD) have ~15 outs and ~54% equity vs top pair -- often correct to commit chips."
    )
    tips.append(
        "With combo draw, bet/raise frequency should be very high (85%+) -- you are a near-favorite."
    )
    if combo_type == 'fd_oesd':
        tips.append("FD+OESD combo: consider stacking off even at moderate SPR -- equity justifies it.")
    if villain_type == 'calling_station':
        tips.append("vs calling station: bet for equity value, not fold equity -- they will call you off.")
    if villain_type == 'nit':
        tips.append("vs nit: semi-bluff aggressively -- they will fold too often, increasing your EV.")
    if position == 'oop':
        tips.append("OOP combo draw: check-raise is a powerful line to build pot and deny villain free cards.")
    if stack_off_ok:
        tips.append("Stack off is [OK] here -- equity >= 50% or SPR is low enough.")

    reasoning = (
        f"Combo type={combo_type} street={street} equity={equity*100:.0f}% "
        f"spr={spr} action={action} stack_off={stack_off_ok}."
    )
    verdict = action

    return ComboDrawFrequencyResult(
        combo_type=combo_type,
        street=street,
        position=position,
        villain_type=villain_type,
        spr=spr,
        pot_bb=pot_bb,
        equity=equity,
        action=action,
        stack_off_ok=stack_off_ok,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def combo_draw_frequency_one_liner(r: ComboDrawFrequencyResult) -> str:
    so = 'Y' if r.stack_off_ok else 'N'
    return (
        f"[CD type={r.combo_type} pos={r.position}] "
        f"eq={r.equity*100:.0f}% action={r.action} stack_off={so}"
    )
