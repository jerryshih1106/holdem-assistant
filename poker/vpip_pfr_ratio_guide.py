# -*- coding: utf-8 -*-
"""vpip_pfr_ratio_guide.py -- VPIP:PFR ratio player type classification."""

from dataclasses import dataclass, field
from typing import List

PLAYER_TYPE_VPIP_RANGE: dict = {
    'nit':    (0.0,  0.18),
    'tag':    (0.18, 0.28),
    'lag':    (0.28, 0.40),
    'fish':   (0.40, 0.50),
    'maniac': (0.50, 1.00),
}

PLAYER_TYPE_PFR_RANGE: dict = {
    'nit':  (0.0,  0.14),
    'tag':  (0.14, 0.22),
    'lag':  (0.22, 0.32),
    'fish': (0.0,  0.10),
}

VPIP_PFR_RATIO_CATEGORY: dict = {
    'nit':             (0.85, 1.00),
    'tag':             (0.70, 0.85),
    'lag':             (0.55, 0.70),
    'calling_station': (0.0,  0.40),
    'maniac':          (0.90, 1.00),
}


def _pfr_vpip_ratio(pfr: float, vpip: float) -> float:
    if vpip <= 0:
        return 0.0
    return round(pfr / vpip, 3)


def _classify_player_type(vpip: float, pfr: float) -> str:
    ratio = _pfr_vpip_ratio(pfr, vpip)
    # Maniac: very high VPIP + very high ratio
    if vpip > 0.50 and ratio > 0.85:
        return 'maniac'
    # Calling station: high VPIP + very low ratio
    if vpip > 0.30 and ratio < 0.40:
        return 'calling_station'
    # Nit: low VPIP + high ratio
    if vpip < 0.18 and ratio >= 0.70:
        return 'nit'
    # TAG
    if 0.18 <= vpip < 0.28 and 0.65 <= ratio <= 0.90:
        return 'tag'
    # LAG
    if 0.28 <= vpip < 0.45 and 0.50 <= ratio < 0.80:
        return 'lag'
    # Fish: high VPIP + low pfr
    if vpip >= 0.35 and ratio < 0.50:
        return 'fish'
    # Fallback by VPIP
    if vpip < 0.18:
        return 'nit'
    if vpip < 0.28:
        return 'tag'
    if vpip < 0.40:
        return 'lag'
    return 'fish'


def _exploit_recommendation(player_type: str) -> str:
    recommendations = {
        'nit':             "3-bet nit wide; fold equity is high. Avoid bluff-catching.",
        'tag':             "Play solid against TAG; look for postflop edges when they show weakness.",
        'lag':             "Tighten 3-bet bluffs vs LAG; 4-bet strong value hands mercilessly.",
        'calling_station': "Never bluff calling station; pile in value bets with thin hands.",
        'fish':            "Iso-raise fish liberally; extract max value; never bluff.",
        'maniac':          "Trap maniac with strong hands; let them hang themselves.",
    }
    return recommendations.get(player_type, "Observe more hands before exploiting.")


@dataclass
class VpipPfrRatioResult:
    vpip: float
    pfr: float
    ratio: float
    player_type_estimate: str
    exploit_advice: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_vpip_pfr_ratio(
    vpip: float = 0.24,
    pfr: float = 0.18,
) -> VpipPfrRatioResult:
    ratio = _pfr_vpip_ratio(pfr, vpip)
    ptype = _classify_player_type(vpip, pfr)
    advice = _exploit_recommendation(ptype)

    tips = []
    tips.append(
        "Need at least 100 hands for VPIP/PFR to be meaningful; use 200+ for confidence."
    )
    if ratio < 0.40:
        tips.append(
            "Very low PFR/VPIP ratio -- villain is a passive caller; value-bet relentlessly."
        )
    if vpip > 0.40:
        tips.append(
            "High VPIP villain plays too many hands preflop -- widen iso-raising range."
        )
    if ratio > 0.85 and vpip < 0.18:
        tips.append(
            "Nit plays almost every enter as a raise -- their range is very strong preflop."
        )
    tips.append(
        "Adjust exploit reads when villain is short-stacked (stack depth changes ranges)."
    )

    reasoning = (
        f"VPIP={vpip:.0%} PFR={pfr:.0%} ratio={ratio:.2f} classifies as '{ptype}'. "
        f"{advice}"
    )
    verdict = ptype

    return VpipPfrRatioResult(
        vpip=vpip,
        pfr=pfr,
        ratio=ratio,
        player_type_estimate=ptype,
        exploit_advice=advice,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def vpip_pfr_ratio_one_liner(r: VpipPfrRatioResult) -> str:
    return (
        f"[VPR vpip={r.vpip:.0%} pfr={r.pfr:.0%}] "
        f"ratio={r.ratio:.2f} type={r.player_type_estimate}"
    )
