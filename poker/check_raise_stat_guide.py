# -*- coding: utf-8 -*-
"""check_raise_stat_guide.py -- Check-raise frequency stat guide."""

from dataclasses import dataclass, field
from typing import List

CR_FREQUENCY_PROFILE: dict = {
    'nit':        (0.0,  0.03),
    'standard':   (0.03, 0.08),
    'trappy':     (0.08, 0.12),
    'aggressive': (0.12, 1.00),
}

CR_EXPLOIT: dict = {
    'nit':        'BET_MORE_NO_PROTECTION',
    'standard':   'BALANCED',
    'trappy':     'DOWNBET_MORE',
    'aggressive': 'VALUE_ONLY',
}


def _cr_profile(cr_pct: float) -> str:
    if cr_pct < 0.03:
        return 'nit'
    if cr_pct < 0.08:
        return 'standard'
    if cr_pct < 0.12:
        return 'trappy'
    return 'aggressive'


def _exploit_strategy(profile: str) -> str:
    strategies = {
        'nit':        "Bet freely for value and bluffs; rarely need to worry about check-raises.",
        'standard':   "Standard cbet frequencies; no major adjustment needed.",
        'trappy':     "Use smaller bet sizes to reduce the cost of getting check-raised off hand.",
        'aggressive': "Only fire value hands OOP; check back draws to avoid massive raises.",
    }
    return strategies.get(profile, "Observe more hands before adjusting.")


def _board_cr_adjustment(board_texture: str) -> str:
    textures = {
        'wet':  "High CR% on wet board = likely draws + value; be careful; they have equity.",
        'dry':  "High CR% on dry board = almost exclusively strong made hands; often fold.",
        'paired': "CR on paired board often = full houses; treat with extreme caution.",
        'monotone': "CR on monotone board often = flush; fold unless you have top of range.",
    }
    return textures.get(board_texture, "Use general CR frequency without board adjustment.")


@dataclass
class CheckRaiseStatResult:
    cr_pct: float
    board_texture: str
    cr_profile: str
    exploit: str
    board_adjustment: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_check_raise_stat(
    cr_pct: float = 0.05,
    board_texture: str = 'dry',
) -> CheckRaiseStatResult:
    profile = _cr_profile(cr_pct)
    exploit = CR_EXPLOIT[profile]
    strategy = _exploit_strategy(profile)
    board_adj = _board_cr_adjustment(board_texture)

    tips = []
    tips.append(
        "Check-raise stat is most meaningful as OOP caller vs in-position bettor."
    )
    if cr_pct > 0.10:
        tips.append(
            "High CR% villain -- check behind more often with marginal hands; protect your bets."
        )
    if cr_pct < 0.03:
        tips.append(
            "Low CR% villain -- bet for protection liberally; they rarely fight back."
        )
    if board_texture == 'wet':
        tips.append(
            "Wet board: respect CR more -- villain has draws that have real equity."
        )
    tips.append(
        "Track CR% by street; flop CR tends to be stronger than turn CR in most player pools."
    )

    reasoning = (
        f"CR%={cr_pct:.0%} ({profile}) on {board_texture} board. "
        f"Exploit: {strategy} {board_adj}"
    )
    verdict = exploit

    return CheckRaiseStatResult(
        cr_pct=cr_pct,
        board_texture=board_texture,
        cr_profile=profile,
        exploit=exploit,
        board_adjustment=board_adj,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def check_raise_stat_one_liner(r: CheckRaiseStatResult) -> str:
    return (
        f"[CRS cr={r.cr_pct:.0%}] "
        f"profile={r.cr_profile} exploit={r.exploit}"
    )
