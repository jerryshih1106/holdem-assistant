# -*- coding: cp950 -*-
"""
Double Barrel Frequency Guide

Double barrel = cbet flop AND bet turn (2nd barrel).
Key: have a plan for river before barreling turn.
Size: 55-70% pot on turn.
"""

from dataclasses import dataclass, field
from typing import List


DOUBLE_BARREL_FREQ_VS_VILLAIN: dict = {
    'fish':            0.45,
    'reg':             0.55,
    'nit':             0.62,
    'lag':             0.42,
    'calling_station': 0.38,
}

TURN_CARD_DB_MODIFIER: dict = {
    'brick':           +0.05,
    'scare':           +0.12,
    'draw_completing': -0.15,
    'pairing':         -0.08,
    'other':            0.0,
}

DB_SIZE_BY_TURN: dict = {
    'brick': 0.58,
    'scare': 0.65,
    'other': 0.60,
}

FLOP_SIZE_DB_MODIFIER: dict = {
    'small_flop': +0.05,
    'large_flop': -0.05,
    'medium_flop': 0.0,
}


def _db_freq(villain_type: str, turn_card_type: str) -> float:
    base = DOUBLE_BARREL_FREQ_VS_VILLAIN.get(villain_type, 0.50)
    mod = TURN_CARD_DB_MODIFIER.get(turn_card_type, 0.0)
    return max(0.05, min(0.95, base + mod))


def _db_size_pct(turn_card_type: str, flop_size_cat: str) -> float:
    base = DB_SIZE_BY_TURN.get(turn_card_type, DB_SIZE_BY_TURN['other'])
    mod = FLOP_SIZE_DB_MODIFIER.get(flop_size_cat, 0.0)
    return max(0.40, min(0.85, base + mod))


def _db_action(freq: float, turn_card_type: str) -> str:
    if turn_card_type == 'draw_completing':
        if freq >= 0.45:
            return 'consider_barrel_or_check'
        return 'check_back'
    if freq >= 0.55:
        return 'barrel'
    if freq >= 0.42:
        return 'barrel_with_strong_hands'
    return 'check_back'


@dataclass
class DoubleBarrelResult:
    villain_type:   str
    turn_card_type: str
    flop_size_cat:  str
    pot_bb:         float
    db_freq:        float
    size_pct:       float
    action:         str
    verdict:        str
    reasoning:      str
    tips:           List[str] = field(default_factory=list)


def analyze_double_barrel(
    villain_type: str = 'reg',
    turn_card_type: str = 'brick',
    flop_size_cat: str = 'medium_flop',
    pot_bb: float = 10.0,
) -> DoubleBarrelResult:
    freq = _db_freq(villain_type, turn_card_type)
    size_pct = _db_size_pct(turn_card_type, flop_size_cat)
    action = _db_action(freq, turn_card_type)
    size_bb = round(pot_bb * size_pct, 1)

    tips = []
    tips.append("Always have a river plan before firing the 2nd barrel.")
    tips.append("Double barrel works best with semi-bluffs that have equity.")
    if turn_card_type == 'scare':
        tips.append("Scare cards increase your barrel frequency -- represent them.")
    if turn_card_type == 'draw_completing':
        tips.append("Draw-completing turns favor checking back unless you have the nuts.")
    if villain_type == 'calling_station':
        tips.append("vs calling station: double barrel for value only, not as a bluff.")
    if villain_type == 'nit':
        tips.append("vs nit: barrel more aggressively -- they fold too often.")

    if freq >= 0.55:
        verdict = 'barrel'
    elif freq >= 0.42:
        verdict = 'selective_barrel'
    else:
        verdict = 'check_back'

    reasoning = (
        f"vs {villain_type} base freq={DOUBLE_BARREL_FREQ_VS_VILLAIN.get(villain_type, 0.50):.0%}, "
        f"turn={turn_card_type} mod={TURN_CARD_DB_MODIFIER.get(turn_card_type, 0.0):+.0%} -> "
        f"freq={freq:.0%}. Size={size_pct:.0%} pot = {size_bb}bb."
    )

    return DoubleBarrelResult(
        villain_type=villain_type,
        turn_card_type=turn_card_type,
        flop_size_cat=flop_size_cat,
        pot_bb=pot_bb,
        db_freq=freq,
        size_pct=size_pct,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def double_barrel_one_liner(r: DoubleBarrelResult) -> str:
    return (
        f"[DB vt={r.villain_type} turn={r.turn_card_type}] "
        f"freq={r.db_freq:.0%} size={r.size_pct:.0%} action={r.action}"
    )
