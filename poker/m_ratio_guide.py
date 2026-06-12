"""
M-Ratio Guide (m_ratio_guide.py)

M-ratio (Harrington's M) = effective stack / (BB + SB + antes per orbit).
Indicates how many orbits until blinds eat your stack. Determines urgency
and guides push/fold thresholds in tournament play.

THEORY:
  M-RATIO DEFINITION:
  M = Stack / (BB + SB + total_antes_per_orbit)
  M represents how many complete orbits before your stack is gone to blinds.

  M ZONES (Harrington):
  Green (M > 20): Full strategy game; raise/3-bet/steal as normal
  Yellow (M 10-20): Start widening steal and push ranges; fewer setups
  Orange (M 6-10): Push/fold mode for many spots; limping eliminated
  Red (M 1-5): Push any reasonable hand; survival mode
  Dead (M < 1): All-in forced soon; may be better to blind off into bubble

  EFFECTIVE M (accounting for players at table):
  Effective_M = M * (players_at_table / 9)
  At 6-handed: effective_M = M * 0.67 (blinds come faster)

  PUSH RANGE BY M:
  M > 20: Normal ranges; push 99+/AQs+ type hands
  M 15-20: Push TT+/AJs+/KQs from CO/BTN
  M 10-15: Push 77+/A9s+/ATo+ from CO/BTN
  M 6-10:  Push 44+/A2s+/A8o+ from any position
  M 3-6:   Push almost any playable hand; 22+/A2o+/KTo+
  M 1-3:   Push any ace, any pair, any Broadway

  CALLING RANGES:
  Much tighter than push ranges; need stronger hands to call all-ins.
  M-based calling: need ~55% equity vs villain's push range.

DISTINCT FROM:
  reshove_advisor.py:       Reshoving over an open
  icm_pressure_guide.py:    ICM adjustments (if exists)
  session_opening_strategy.py: Session phases
  THIS MODULE:              M-RATIO ZONES; push thresholds by M; effective M
                            for different table sizes; tournament urgency.
"""

from dataclasses import dataclass, field
from typing import List, Optional


M_ZONES: dict = {
    'green':  (20.0, 999.0),
    'yellow': (10.0, 20.0),
    'orange': (6.0,  10.0),
    'red':    (1.0,   6.0),
    'dead':   (0.0,   1.0),
}

M_ZONE_DESCRIPTIONS: dict = {
    'green':  'Full game; all strategies available',
    'yellow': 'Widen steals; fewer setups; start applying pressure',
    'orange': 'Push/fold mode; limping eliminated; aggress often',
    'red':    'Survival mode; push any reasonable hand; call tight',
    'dead':   'Critically short; may blind off to bubble; shove next hand',
}

PUSH_RANGE_BY_M: dict = {
    'green':  {'min_pair': 9,  'min_ace_suit': 'AQs', 'positions': ['all']},
    'yellow': {'min_pair': 8,  'min_ace_suit': 'AJs', 'positions': ['co', 'btn', 'sb']},
    'orange': {'min_pair': 5,  'min_ace_suit': 'A7s', 'positions': ['all']},
    'red':    {'min_pair': 2,  'min_ace_suit': 'A2s', 'positions': ['all']},
    'dead':   {'min_pair': 2,  'min_ace_suit': 'A2o', 'positions': ['all']},
}

STRATEGY_BY_ZONE: dict = {
    'green':  ['Play full ranges', '3-bet/4-bet for value', 'Exploit position', 'Post-flop skill important'],
    'yellow': ['Widen BTN/CO steal to 35-40%', 'Jam 15BB spots from late position', 'Avoid marginal 3-bets OOP'],
    'orange': ['Push/fold from all positions', 'Jam 44+ from CO/BTN', 'Avoid calling off stack light'],
    'red':    ['Shove next reasonable hand', '22+/A2+/KTs+ from anywhere', 'Jam before antes take too much'],
    'dead':   ['Shove immediately', 'Any two cards if blind pressure is next', 'ICM irrelevant -- need chips'],
}

CALL_EQUITY_REQUIRED: dict = {
    'green':  0.55,
    'yellow': 0.52,
    'orange': 0.50,
    'red':    0.47,
    'dead':   0.40,
}

PLAYERS_EFFECTIVE_M_FACTOR: dict = {
    9: 1.00,
    8: 0.89,
    7: 0.78,
    6: 0.67,
    5: 0.56,
    4: 0.44,
    3: 0.33,
    2: 0.22,
}


def _m_ratio(stack_bb: float, bb: float, sb: float, antes_total: float) -> float:
    orbit_cost = bb + sb + antes_total
    if orbit_cost <= 0:
        return 999.0
    return round(stack_bb / orbit_cost, 2)


def _effective_m(m: float, players_at_table: int) -> float:
    factor = PLAYERS_EFFECTIVE_M_FACTOR.get(players_at_table, 1.0)
    return round(m * factor, 2)


def _m_zone(effective_m: float) -> str:
    for zone, (lo, hi) in M_ZONES.items():
        if lo <= effective_m < hi:
            return zone
    return 'dead'


@dataclass
class MRatioResult:
    stack_bb: float
    bb: float
    sb: float
    antes_total: float
    players_at_table: int

    m_ratio: float
    effective_m: float
    zone: str
    zone_description: str
    push_range: dict
    strategies: List[str]
    call_equity_required: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_m_ratio(
    stack_bb: float = 20.0,
    bb: float = 1.0,
    sb: float = 0.5,
    antes_total: float = 0.0,
    players_at_table: int = 9,
) -> MRatioResult:
    """
    Calculate M-ratio and recommend tournament strategy by zone.

    Args:
        stack_bb:         Hero stack in BB
        bb:               Big blind size (usually 1.0)
        sb:               Small blind size (usually 0.5)
        antes_total:      Total antes per orbit (n_players * ante_per_player)
        players_at_table: Players at table (for effective M calculation)

    Returns:
        MRatioResult
    """
    m = _m_ratio(stack_bb, bb, sb, antes_total)
    eff_m = _effective_m(m, players_at_table)
    zone = _m_zone(eff_m)
    desc = M_ZONE_DESCRIPTIONS[zone]
    push_rng = PUSH_RANGE_BY_M[zone]
    strats = STRATEGY_BY_ZONE[zone]
    call_eq = CALL_EQUITY_REQUIRED[zone]

    verdict = (
        f'[M zone={zone.upper()} M={m:.1f} effM={eff_m:.1f}] '
        f'stack={stack_bb:.0f}BB push={push_rng["min_ace_suit"]}+ call_eq={call_eq:.0%}'
    )

    reasoning = (
        f'M-ratio: stack={stack_bb:.0f}BB / (BB={bb}+SB={sb}+antes={antes_total})={m:.1f}. '
        f'Effective M ({players_at_table} players) = {eff_m:.1f}. '
        f'Zone: {zone.upper()} -- {desc}. '
        f'Min pair to push: {push_rng["min_pair"]}x; Ace suited: {push_rng["min_ace_suit"]}+. '
        f'Calling requires {call_eq:.0%} equity.'
    )

    tips = []

    tips.append(
        f'M-ZONE: {zone.upper()} (M={m:.1f}, effective={eff_m:.1f}). '
        f'{desc}. '
        f'{"No urgency -- play full poker." if zone == "green" else "Increasing urgency -- widen push ranges." if zone == "yellow" else "High urgency -- push/fold mode." if zone == "orange" else "Critical -- shove immediately." if zone == "red" else "Emergency -- shove any hand."}'
    )

    tips.append(
        f'PUSH RANGE ({zone.upper()}): Min pair={push_rng["min_pair"]}+ ({pair_name(push_rng["min_pair"])}+), '
        f'Min ace={push_rng["min_ace_suit"]}+. '
        f'From positions: {", ".join(push_rng["positions"])}. '
        f'Call all-in requiring {call_eq:.0%}+ equity (tighter than push range).'
    )

    tips.append(
        f'STRATEGIES: {" | ".join(strats[:3])}.'
    )

    if players_at_table <= 6:
        factor = PLAYERS_EFFECTIVE_M_FACTOR.get(players_at_table, 0.67)
        tips.append(
            f'SHORT-HANDED ({players_at_table} players): Effective M={eff_m:.1f} (M={m:.1f} * {factor:.2f}). '
            f'Blinds come {round(1/factor, 1)}x faster -- act sooner than raw M suggests. '
            f'At 6-handed, true urgency is 33% higher than raw M.'
        )

    return MRatioResult(
        stack_bb=stack_bb,
        bb=bb,
        sb=sb,
        antes_total=antes_total,
        players_at_table=players_at_table,
        m_ratio=m,
        effective_m=eff_m,
        zone=zone,
        zone_description=desc,
        push_range=push_rng,
        strategies=strats,
        call_equity_required=call_eq,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pair_name(rank: int) -> str:
    names = {2:'22',3:'33',4:'44',5:'55',6:'66',7:'77',8:'88',9:'99',10:'TT',11:'JJ',12:'QQ',13:'KK',14:'AA'}
    return names.get(rank, f'{rank}x')


def mr_one_liner(r: MRatioResult) -> str:
    return (
        f'[M zone={r.zone.upper()} M={r.m_ratio:.1f} effM={r.effective_m:.1f}] '
        f'stack={r.stack_bb:.0f}BB'
    )
