# -*- coding: utf-8 -*-
"""hud_overview_guide.py -- Combined HUD stats player assessment guide."""

from dataclasses import dataclass, field
from typing import List

HUD_SAMPLE_MIN: int = 50

PLAYER_TYPE_MATRIX: dict = {
    'nit': {
        'vpip':      (0.0,  0.18),
        'pfr':       (0.0,  0.14),
        'af':        (0.0,  2.0),
        'three_bet': (0.0,  0.04),
    },
    'tag': {
        'vpip':      (0.18, 0.28),
        'pfr':       (0.14, 0.22),
        'af':        (1.5,  3.5),
        'three_bet': (0.04, 0.09),
    },
    'lag': {
        'vpip':      (0.28, 0.42),
        'pfr':       (0.22, 0.35),
        'af':        (2.5,  5.5),
        'three_bet': (0.08, 0.16),
    },
    'fish': {
        'vpip':      (0.35, 1.0),
        'pfr':       (0.0,  0.14),
        'af':        (0.0,  2.0),
        'three_bet': (0.0,  0.05),
    },
    'maniac': {
        'vpip':      (0.45, 1.0),
        'pfr':       (0.35, 1.0),
        'af':        (4.0,  float('inf')),
        'three_bet': (0.12, 1.0),
    },
}

EXPLOIT_BY_TYPE: dict = {
    'nit':    "3-bet bluff freely; fold equity is high. Only call 3-bets with premium hands.",
    'tag':    "Solid player; seek postflop edges; don't bluff too often OOP.",
    'lag':    "4-bet bluff wide; flat strong draws IP; trap with monsters.",
    'fish':   "Iso-raise; value-bet every street; never bluff; extract maximum.",
    'maniac': "Trap with strong hands; do not bluff; call down wider than normal.",
    'unknown':"Observe 50+ hands to form a reliable read.",
}


def _score_in_range(value: float, lo: float, hi: float) -> float:
    """Return 1.0 if in range, partial overlap otherwise."""
    if lo <= value <= hi:
        return 1.0
    return 0.0


def _classify_from_hud(
    vpip: float,
    pfr: float,
    af: float,
    wtsd: float,
    three_bet: float,
) -> str:
    scores = {}
    for ptype, ranges in PLAYER_TYPE_MATRIX.items():
        score = 0
        score += _score_in_range(vpip,      *ranges['vpip'])
        score += _score_in_range(pfr,       *ranges['pfr'])
        score += _score_in_range(af,        *ranges['af'])
        score += _score_in_range(three_bet, *ranges['three_bet'])
        scores[ptype] = score

    best = max(scores, key=lambda k: scores[k])
    if scores[best] < 2:
        # Tie-break with VPIP as primary
        if vpip < 0.18:
            return 'nit'
        if vpip < 0.28:
            return 'tag'
        if pfr < 0.14 and vpip > 0.35:
            return 'fish'
        if vpip > 0.45 and pfr > 0.35:
            return 'maniac'
        if vpip > 0.28:
            return 'lag'
        return 'unknown'
    return best


def _primary_leak(player_type: str) -> str:
    leaks = {
        'nit':    "Playing too few hands; missing value from speculative hands and position.",
        'tag':    "Minor leaks; possible over-folding to aggression or missing thin value.",
        'lag':    "May bluff too frequently; sometimes commits too much with weak ranges.",
        'fish':   "Plays too many hands OOP; calls too widely; never bluffs optimally.",
        'maniac': "Massive over-aggression; loses to traps; rarely folds strong hands down.",
        'unknown':"Insufficient sample; primary leak unclear.",
    }
    return leaks.get(player_type, "Unknown type.")


def _exploit_summary(player_type: str) -> str:
    return EXPLOIT_BY_TYPE.get(player_type, EXPLOIT_BY_TYPE['unknown'])


@dataclass
class HudOverviewResult:
    vpip: float
    pfr: float
    af: float
    wtsd: float
    three_bet_pct: float
    sample_size: int
    player_type: str
    primary_leak: str
    exploit_summary: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_hud_overview(
    vpip: float = 0.24,
    pfr: float = 0.18,
    af: float = 2.0,
    wtsd: float = 0.26,
    three_bet_pct: float = 0.07,
    sample_size: int = 200,
) -> HudOverviewResult:
    ptype = _classify_from_hud(vpip, pfr, af, wtsd, three_bet_pct)
    leak = _primary_leak(ptype)
    exploit = _exploit_summary(ptype)

    tips = []
    tips.append(
        f"Minimum {HUD_SAMPLE_MIN} hands required for meaningful HUD reads; 200+ preferred."
    )
    if sample_size < HUD_SAMPLE_MIN:
        tips.append(
            f"Only {sample_size} hands -- HUD stats unreliable; default to GTO until more data."
        )
    if ptype == 'fish':
        tips.append(
            "Fish identified -- prioritize this seat; maximize EV extraction session-long."
        )
    if ptype == 'maniac':
        tips.append(
            "Maniac at table -- tighten preflop range; trap more; widen call-down range."
        )
    if abs(vpip - pfr) > 0.20:
        tips.append(
            "Large VPIP-PFR gap -- villain is a passive caller; value-bet thin constantly."
        )
    tips.append(
        "Update HUD reads as more hands accumulate -- early reads can be misleading."
    )

    reasoning = (
        f"VPIP={vpip:.0%} PFR={pfr:.0%} AF={af:.1f} WTSD={wtsd:.0%} 3bet={three_bet_pct:.0%} "
        f"over {sample_size} hands -> '{ptype}'. Leak: {leak}"
    )
    verdict = ptype

    return HudOverviewResult(
        vpip=vpip,
        pfr=pfr,
        af=af,
        wtsd=wtsd,
        three_bet_pct=three_bet_pct,
        sample_size=sample_size,
        player_type=ptype,
        primary_leak=leak,
        exploit_summary=exploit,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def hud_overview_one_liner(r: HudOverviewResult) -> str:
    return (
        f"[HUD vpip={r.vpip:.0%} pfr={r.pfr:.0%} af={r.af:.1f}] "
        f"type={r.player_type} exploit={r.exploit_summary[:30]}"
    )
