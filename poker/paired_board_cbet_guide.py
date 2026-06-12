# -*- coding: utf-8 -*-
"""paired_board_cbet_guide.py -- Paired board c-bet strategy guide."""

from dataclasses import dataclass, field
from typing import List

CBET_FREQ_PAIRED: dict = {
    'position_ip': 0.62,
    'position_oop': 0.55,
}

CBET_SIZE_PAIRED: float = 0.28

HIGH_PAIR_FREQ_BONUS: dict = {
    'aa_kk_pair': +0.08,
    'medium_pair': 0.0,
    'low_pair': -0.05,
}

VILLAIN_PAIRED_MOD: dict = {
    'fish': +0.05,
    'nit': -0.05,
}

TRIPS_VILLAIN_PROBABILITY: float = 0.03


def _paired_cbet_freq(position: str, pair_rank: str, villain_type: str) -> float:
    base = CBET_FREQ_PAIRED.get('position_' + position, CBET_FREQ_PAIRED['position_ip'])
    if pair_rank == 'high':
        base += HIGH_PAIR_FREQ_BONUS['aa_kk_pair']
    elif pair_rank == 'medium':
        base += HIGH_PAIR_FREQ_BONUS['medium_pair']
    else:
        base += HIGH_PAIR_FREQ_BONUS['low_pair']
    base += VILLAIN_PAIRED_MOD.get(villain_type, 0.0)
    return round(min(1.0, max(0.0, base)), 4)


def _paired_cbet_size(pair_rank: str) -> float:
    if pair_rank == 'high':
        return round(CBET_SIZE_PAIRED + 0.04, 4)
    if pair_rank == 'low':
        return round(CBET_SIZE_PAIRED - 0.03, 4)
    return CBET_SIZE_PAIRED


def _trips_warning(pair_rank: str, villain_type: str) -> bool:
    prob = TRIPS_VILLAIN_PROBABILITY
    if villain_type == 'fish':
        prob += 0.01
    if pair_rank == 'low':
        prob += 0.02
    return prob > 0.03


@dataclass
class PairedBoardCbetResult:
    position: str
    pair_rank: str
    villain_type: str
    pot_bb: float
    cbet_freq: float
    size_pct: float
    trips_warning: bool
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_paired_board_cbet(
    position: str = 'ip',
    pair_rank: str = 'high',
    villain_type: str = 'reg',
    pot_bb: float = 10.0,
) -> PairedBoardCbetResult:
    tips = []
    tips.append("Paired boards give the preflop aggressor a range advantage -- cbet more than on unpaired boards.")
    tips.append("Use small sizing (25-35% pot) on paired dry boards to exploit villain's capped range.")

    freq = _paired_cbet_freq(position, pair_rank, villain_type)
    size = _paired_cbet_size(pair_rank)
    warn = _trips_warning(pair_rank, villain_type)

    if warn:
        tips.append("Be cautious: villain may hold trips on low paired boards -- don't over-barrel.")
    if pair_rank == 'high':
        tips.append("High pair board (QQ+): hero has massive nut advantage with overpairs and trips.")
    if villain_type == 'fish':
        tips.append("vs fish: increase frequency slightly -- they call too wide and rarely exploit paired textures.")
    if position == 'oop':
        tips.append("OOP: reduce frequency by ~7% vs IP baseline; check more medium-strength hands.")

    if freq >= 0.60:
        verdict = "CBET_FREQUENTLY"
    elif freq >= 0.50:
        verdict = "CBET_MODERATELY"
    else:
        verdict = "CBET_SELECTIVELY"

    reasoning = (
        "Paired boards favor the preflop aggressor who holds more overpairs and top pairs. "
        "Small sizing exploits villain's capped range. "
        "Estimated cbet freq {:.0f}%, size {:.0f}% pot.".format(freq * 100, size * 100)
    )

    return PairedBoardCbetResult(
        position=position,
        pair_rank=pair_rank,
        villain_type=villain_type,
        pot_bb=pot_bb,
        cbet_freq=freq,
        size_pct=size,
        trips_warning=warn,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def paired_board_cbet_one_liner(r: PairedBoardCbetResult) -> str:
    warn_str = "Y" if r.trips_warning else "N"
    return (
        "[PCB pos={} pair={} vt={}] freq={:.0f}% size={:.0f}% trips_warn={}".format(
            r.position, r.pair_rank, r.villain_type,
            r.cbet_freq * 100, r.size_pct * 100, warn_str,
        )
    )
