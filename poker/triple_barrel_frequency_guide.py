# -*- coding: cp950 -*-
"""
Triple Barrel Frequency Guide

Triple barrel = cbet all 3 streets. Very high commitment.
Frequency: overall 15-25% of hands where you cbet.
Need: credible range on river, right board, polarized.
Key question: does river card help your story?
"""

from dataclasses import dataclass, field
from typing import List


TRIPLE_BARREL_FREQ: dict = {
    'nit':             0.30,
    'reg':             0.22,
    'fish':            0.10,
    'lag':             0.15,
    'calling_station': 0.05,
}

RIVER_CARD_TB_MOD: dict = {
    'brick':      +0.05,
    'blank':      +0.03,
    'scare':      +0.08,
    'completing': +0.02,
    'pairing':    -0.08,
}

TB_SIZE: float = 0.70

STORY_CREDIBILITY_THRESHOLD: float = 0.60


def _tb_freq(villain_type: str, river_card_type: str) -> float:
    base = TRIPLE_BARREL_FREQ.get(villain_type, 0.20)
    mod = RIVER_CARD_TB_MOD.get(river_card_type, 0.0)
    return max(0.02, min(0.90, base + mod))


def _tb_size_pct() -> float:
    return TB_SIZE


def _tb_story_credibility(board_texture: str, river_card: str) -> float:
    base = {
        'dry':      0.70,
        'semi_dry': 0.65,
        'semi_wet': 0.55,
        'wet':      0.45,
        'paired':   0.60,
        'monotone': 0.50,
    }.get(board_texture, 0.60)
    river_boost = {
        'scare':      +0.10,
        'brick':      +0.05,
        'blank':      +0.03,
        'completing': -0.05,
        'pairing':    -0.08,
    }.get(river_card, 0.0)
    return max(0.10, min(0.95, base + river_boost))


def _tb_action(freq: float, story_cred: float) -> str:
    if story_cred < STORY_CREDIBILITY_THRESHOLD:
        return 'give_up'
    if freq >= 0.22:
        return 'triple_barrel'
    if freq >= 0.12:
        return 'triple_barrel_value_only'
    return 'give_up'


@dataclass
class TripleBarrelResult:
    villain_type:    str
    river_card_type: str
    board_texture:   str
    pot_bb:          float
    tb_freq:         float
    story_credibility: float
    size_pct:        float
    action:          str
    verdict:         str
    reasoning:       str
    tips:            List[str] = field(default_factory=list)


def analyze_triple_barrel(
    villain_type: str = 'reg',
    river_card_type: str = 'brick',
    board_texture: str = 'dry',
    pot_bb: float = 12.0,
) -> TripleBarrelResult:
    freq = _tb_freq(villain_type, river_card_type)
    size_pct = _tb_size_pct()
    story_cred = _tb_story_credibility(board_texture, river_card_type)
    action = _tb_action(freq, story_cred)
    size_bb = round(pot_bb * size_pct, 1)

    tips = []
    tips.append("Triple barrel only when your range is credibly strong on this river.")
    tips.append("Polarize river range: only value hands and pure bluffs, no medium hands.")
    if river_card_type == 'scare':
        tips.append("Scare river cards improve your story -- triple barrel at higher freq.")
    if river_card_type == 'pairing':
        tips.append("Pairing river hurts your story -- consider giving up bluffs.")
    if villain_type == 'calling_station':
        tips.append("vs calling station: triple barrel for value only, never as a bluff.")
    if villain_type == 'nit':
        tips.append("vs nit: can triple barrel bluff at higher frequency -- they fold rivers.")
    if story_cred < STORY_CREDIBILITY_THRESHOLD:
        tips.append("Story credibility too low -- check and give up most bluffs.")

    verdict = action

    reasoning = (
        f"vs {villain_type} base={TRIPLE_BARREL_FREQ.get(villain_type, 0.20):.0%}, "
        f"river={river_card_type} mod={RIVER_CARD_TB_MOD.get(river_card_type, 0.0):+.0%} -> "
        f"freq={freq:.0%}. Story credibility={story_cred:.0%} "
        f"(threshold={STORY_CREDIBILITY_THRESHOLD:.0%}). "
        f"Size={size_pct:.0%} pot = {size_bb}bb."
    )

    return TripleBarrelResult(
        villain_type=villain_type,
        river_card_type=river_card_type,
        board_texture=board_texture,
        pot_bb=pot_bb,
        tb_freq=freq,
        story_credibility=story_cred,
        size_pct=size_pct,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def triple_barrel_one_liner(r: TripleBarrelResult) -> str:
    return (
        f"[TB vt={r.villain_type} river={r.river_card_type}] "
        f"freq={r.tb_freq:.0%} story={r.story_credibility:.0%} action={r.action}"
    )
