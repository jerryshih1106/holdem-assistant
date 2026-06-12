# -*- coding: cp950 -*-
"""turn_draw_completion_guide.py -- Turn draw completion: strategy when draw gets there on turn."""

from dataclasses import dataclass, field
from typing import List

MADE_HAND_TURN_BET_FREQ: dict = {
    'flush':    0.85,
    'straight': 0.88,
    'two_pair': 0.82,
    'pair':     0.65,
    'missed':   0.15,
}

VILLAIN_MADE_HAND_MOD: dict = {
    'fish':  +0.08,
    'lag':   -0.05,
    'nit':   -0.03,
    'reg':    0.00,
    'calling_station': +0.10,
    'passive': +0.06,
}

MADE_HAND_SIZE: dict = {
    'flush':    0.72,
    'straight': 0.80,
    'two_pair': 0.68,
    'pair':     0.52,
    'missed':   0.00,
}

DRAW_MISSED_FREQ: float = 0.15

BOARD_SIZE_MOD: dict = {
    'wet':      +0.05,
    'dry':      -0.05,
    'paired':   -0.08,
    'monotone': -0.10,
}


def _made_hand_freq(hand_type: str, villain_type: str) -> float:
    base = MADE_HAND_TURN_BET_FREQ.get(hand_type, DRAW_MISSED_FREQ)
    mod = VILLAIN_MADE_HAND_MOD.get(villain_type, 0.0)
    return round(min(1.0, max(0.0, base + mod)), 4)


def _made_hand_size(hand_type: str, board_texture: str) -> float:
    base = MADE_HAND_SIZE.get(hand_type, 0.0)
    mod = BOARD_SIZE_MOD.get(board_texture, 0.0)
    return round(min(1.20, max(0.0, base + mod)), 4)


def _turn_action(hand_type: str, villain_type: str) -> str:
    freq = _made_hand_freq(hand_type, villain_type)
    if hand_type == 'missed':
        if freq >= 0.15:
            return 'BLUFF_OR_GIVE_UP'
        return 'GIVE_UP'
    if freq >= 0.75:
        return 'BET_VALUE'
    if freq >= 0.55:
        return 'BET_THIN'
    return 'CHECK_CALL'


@dataclass
class TurnDrawCompletionResult:
    hand_type: str
    villain_type: str
    board_texture: str
    pot_bb: float
    stack_bb: float
    bet_freq: float
    size_pct: float
    action: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_turn_draw_completion(
    hand_type: str = 'flush',
    villain_type: str = 'reg',
    board_texture: str = 'wet',
    pot_bb: float = 10.0,
    stack_bb: float = 80.0,
) -> TurnDrawCompletionResult:
    bet_freq = _made_hand_freq(hand_type, villain_type)
    size_pct = _made_hand_size(hand_type, board_texture)
    action = _turn_action(hand_type, villain_type)

    tips = []
    tips.append(
        "When your draw completes on the turn, shift to value-betting mode -- build the pot aggressively."
    )
    tips.append(
        "Made flush/straight on turn: size up vs sticky players; villains often pay off with top pair+."
    )
    if hand_type == 'flush':
        tips.append("Flush on turn: if board not monotone, bet large -- villain often has top pair or 2-pair calls.")
    if hand_type == 'straight':
        tips.append("Straight on turn: check board for flush draws -- if villain can have FD, size to deny odds.")
    if hand_type == 'missed':
        tips.append("Draw missed: bluff frequency 15% -- only bluff with strong blockers to villain's likely holdings.")
    if villain_type in ('fish', 'calling_station'):
        tips.append("vs calling station/fish: never slow-play made flush/straight -- they will call down wide.")
    if villain_type == 'nit':
        tips.append("vs nit: consider check-raise if villain likely to cbet -- let them bet into your strong hand.")

    reasoning = (
        f"Hand={hand_type} completed on turn. villain={villain_type} board={board_texture} "
        f"freq={bet_freq*100:.0f}% size={size_pct*100:.0f}% action={action}."
    )
    verdict = action

    return TurnDrawCompletionResult(
        hand_type=hand_type,
        villain_type=villain_type,
        board_texture=board_texture,
        pot_bb=pot_bb,
        stack_bb=stack_bb,
        bet_freq=bet_freq,
        size_pct=size_pct,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def turn_draw_completion_one_liner(r: TurnDrawCompletionResult) -> str:
    return (
        f"[TDC hand={r.hand_type} vt={r.villain_type}] "
        f"freq={r.bet_freq*100:.0f}% size={r.size_pct*100:.0f}% action={r.action}"
    )
