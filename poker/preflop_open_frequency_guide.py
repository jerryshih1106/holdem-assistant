"""
Preflop Open Frequency Guide (preflop_open_frequency_guide.py)

Provides recommended open-raise frequencies, VPIP, and PFR targets per position,
with exploitative adjustments based on table type. Key to a winning preflop strategy.

THEORY:
  VPIP (Voluntarily Put $ In Pot): % of hands where hero enters the pot preflop.
  PFR  (Pre-Flop Raise):          % of hands where hero raises preflop.

  MODERN GTO TARGET RATIOS:
  - PFR should be 60-85% of VPIP (most limping is exploitable; raise or fold)
  - VPIP-PFR gap < 5% = very strong; 5-10% = acceptable; >15% = leak (too much limping)

  POSITION-BASED OPEN FREQUENCIES (GTO approximation, 9-handed):
  UTG:   ~12-16% hands (very tight; many players remaining)
  UTG+1: ~14-17%
  MP:    ~18-22%
  HJ:    ~22-28%
  CO:    ~28-35%
  BTN:   ~40-55% (widest; last to act postflop)
  SB:    ~35-45% (OOP vs BB; but no one behind)
  BB:    ~15-20% open (rare; mostly defend vs steal)

  TABLE-TYPE ADJUSTMENTS:
  - PASSIVE/FISH TABLE: Open slightly tighter (fish calls more; less fold equity);
    however, limp-reraise risk is lower from fish
  - AGGRESSIVE/LAG TABLE: Open slightly tighter in early positions; defend wider
  - TIGHT TABLE: Open wider; steal blinds more; expand steal frequency
  - SHORTSTACK TABLE: Push/fold mode; see shortstack_range_expander.py

  VPIP BENCHMARKS BY GAME TYPE:
  - 6-max cash:   VPIP 22-28%, PFR 18-24%
  - Full ring:    VPIP 18-22%, PFR 14-19%
  - Live cash:    VPIP 20-26%, PFR 15-20%
  - Tournaments:  VPIP depends on stack depth

DISTINCT FROM:
  steal_advisor.py:               Blind steal optimization
  blind_steal.py:                 Steal range
  open_sizing.py:                 Open sizing
  exploitative_steal_calibrator.py: Exploiting specific players
  THIS MODULE:                    FREQUENCY GUIDE; VPIP/PFR targets; position-based
                                  open ranges; leak detection; table-type adjustment.
"""

from dataclasses import dataclass, field
from typing import List


POSITION_OPEN_FREQ: dict = {
    'utg':   {'min': 0.12, 'gto': 0.14, 'max': 0.18},
    'utg1':  {'min': 0.14, 'gto': 0.16, 'max': 0.20},
    'mp':    {'min': 0.18, 'gto': 0.21, 'max': 0.26},
    'hj':    {'min': 0.22, 'gto': 0.26, 'max': 0.32},
    'co':    {'min': 0.28, 'gto': 0.32, 'max': 0.38},
    'btn':   {'min': 0.40, 'gto': 0.48, 'max': 0.58},
    'sb':    {'min': 0.35, 'gto': 0.42, 'max': 0.50},
    'bb':    {'min': 0.10, 'gto': 0.14, 'max': 0.20},
}

TABLE_TYPE_MODIFIER: dict = {
    'passive':     {'open': -0.02, 'defend': 0.05},
    'aggressive':  {'open': -0.03, 'defend': 0.08},
    'tight':       {'open':  0.04, 'defend': -0.03},
    'balanced':    {'open':  0.00, 'defend':  0.00},
    'fish_heavy':  {'open': -0.01, 'defend':  0.06},
}

OPEN_SIZING_GUIDE: dict = {
    'utg':   {'online_6max': 2.5, 'online_9h': 2.5, 'live': 3.0},
    'utg1':  {'online_6max': 2.5, 'online_9h': 2.5, 'live': 3.0},
    'mp':    {'online_6max': 2.5, 'online_9h': 2.5, 'live': 3.0},
    'hj':    {'online_6max': 2.5, 'online_9h': 2.5, 'live': 3.0},
    'co':    {'online_6max': 2.5, 'online_9h': 2.5, 'live': 3.0},
    'btn':   {'online_6max': 2.5, 'online_9h': 2.5, 'live': 2.5},
    'sb':    {'online_6max': 3.0, 'online_9h': 3.0, 'live': 4.0},
    'bb':    {'online_6max': 3.0, 'online_9h': 3.0, 'live': 4.0},
}

TARGET_VPIP_PFR: dict = {
    'online_6max':  {'vpip': (0.22, 0.28), 'pfr': (0.18, 0.24)},
    'online_9h':    {'vpip': (0.18, 0.22), 'pfr': (0.14, 0.19)},
    'live':         {'vpip': (0.20, 0.26), 'pfr': (0.15, 0.20)},
    'tournament':   {'vpip': (0.16, 0.22), 'pfr': (0.14, 0.20)},
}


def _adjusted_open_freq(position: str, table_type: str) -> float:
    base = POSITION_OPEN_FREQ.get(position.lower(), POSITION_OPEN_FREQ['co'])
    mod = TABLE_TYPE_MODIFIER.get(table_type, TABLE_TYPE_MODIFIER['balanced'])
    freq = base['gto'] + mod['open']
    return round(min(0.70, max(0.05, freq)), 3)


def _open_sizing(position: str, game_type: str) -> float:
    sizes = OPEN_SIZING_GUIDE.get(position.lower(), OPEN_SIZING_GUIDE['co'])
    return sizes.get(game_type, sizes['online_6max'])


def _leak_check(hero_vpip: float, hero_pfr: float, position: str) -> list:
    leaks = []
    gap = hero_vpip - hero_pfr
    if gap > 0.15:
        leaks.append(f'LIMPING LEAK: VPIP-PFR gap={gap:.0%} > 15% -- too much limping; raise or fold.')
    if hero_vpip > 0.40 and position in ('utg', 'utg1', 'mp'):
        leaks.append(f'TOO LOOSE EARLY: VPIP={hero_vpip:.0%} from {position.upper()} -- tighten range.')
    if hero_pfr < 0.10 and position in ('co', 'btn', 'sb'):
        leaks.append(f'TOO PASSIVE LATE: PFR={hero_pfr:.0%} from {position.upper()} -- raise more hands.')
    if hero_vpip < 0.10 and position in ('btn', 'co'):
        leaks.append(f'TOO TIGHT LATE: VPIP={hero_vpip:.0%} from {position.upper()} -- open wider.')
    return leaks


def _vpip_pfr_quality(hero_vpip: float, hero_pfr: float, game_type: str) -> str:
    targets = TARGET_VPIP_PFR.get(game_type, TARGET_VPIP_PFR['online_6max'])
    vpip_lo, vpip_hi = targets['vpip']
    pfr_lo, pfr_hi   = targets['pfr']
    in_vpip = vpip_lo <= hero_vpip <= vpip_hi
    in_pfr  = pfr_lo  <= hero_pfr  <= pfr_hi
    if in_vpip and in_pfr:
        return 'OPTIMAL'
    elif hero_vpip > vpip_hi and hero_pfr > pfr_hi:
        return 'TOO_LOOSE_AGGRESSIVE'
    elif hero_vpip > vpip_hi and hero_pfr < pfr_lo:
        return 'TOO_LOOSE_PASSIVE'
    elif hero_vpip < vpip_lo:
        return 'TOO_TIGHT'
    elif hero_pfr < pfr_lo:
        return 'PFR_TOO_LOW'
    return 'NEAR_OPTIMAL'


@dataclass
class PreflopOpenFreqResult:
    position: str
    table_type: str
    game_type: str

    gto_open_freq: float
    adjusted_open_freq: float
    open_size_bb: float

    hero_vpip: float
    hero_pfr: float
    vpip_pfr_quality: str
    detected_leaks: list

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_preflop_open_frequency(
    position: str = 'btn',
    table_type: str = 'balanced',
    game_type: str = 'online_6max',
    hero_vpip: float = 0.25,
    hero_pfr: float = 0.20,
    stack_bb: float = 100.0,
) -> PreflopOpenFreqResult:
    """
    Analyze preflop open frequency, VPIP/PFR targets, and detect leaks.

    Args:
        position:   Hero position ('utg','utg1','mp','hj','co','btn','sb','bb')
        table_type: Table dynamics ('passive','aggressive','tight','balanced','fish_heavy')
        game_type:  Game format ('online_6max','online_9h','live','tournament')
        hero_vpip:  Hero's actual VPIP (0-1)
        hero_pfr:   Hero's actual PFR (0-1)
        stack_bb:   Effective stack in BB

    Returns:
        PreflopOpenFreqResult
    """
    gto_freq = POSITION_OPEN_FREQ.get(position.lower(), POSITION_OPEN_FREQ['co'])['gto']
    adj_freq = _adjusted_open_freq(position, table_type)
    size_bb  = _open_sizing(position, game_type)
    quality  = _vpip_pfr_quality(hero_vpip, hero_pfr, game_type)
    leaks    = _leak_check(hero_vpip, hero_pfr, position)

    targets = TARGET_VPIP_PFR.get(game_type, TARGET_VPIP_PFR['online_6max'])

    verdict = (
        f'[POF {position.upper()}|{table_type}|{game_type}] '
        f'open={adj_freq:.0%} size={size_bb:.1f}BB '
        f'VPIP={hero_vpip:.0%}/PFR={hero_pfr:.0%} [{quality}] '
        f'leaks={len(leaks)}'
    )

    reasoning = (
        f'Open frequency: {position.upper()} on {table_type} {game_type} table. '
        f'GTO open freq: {gto_freq:.0%}, adjusted: {adj_freq:.0%}. '
        f'Sizing: {size_bb:.1f}BB. '
        f'VPIP/PFR quality: {quality}. '
        f'Detected leaks: {len(leaks)}.'
    )

    tips = []

    tips.append(
        f'OPEN FREQUENCY: {position.upper()} target = {adj_freq:.0%} '
        f'(GTO base={gto_freq:.0%}, {table_type} adj). '
        f'Open size: {size_bb:.1f}BB. '
        f'{"Open more hands; position advantage is underexploited." if hero_vpip < adj_freq * 0.8 else "Good open frequency." if abs(hero_vpip - adj_freq) < 0.05 else "Tighten opening range."}'
    )

    tips.append(
        f'VPIP/PFR TARGETS ({game_type}): '
        f'VPIP {targets["vpip"][0]:.0%}-{targets["vpip"][1]:.0%}, '
        f'PFR {targets["pfr"][0]:.0%}-{targets["pfr"][1]:.0%}. '
        f'Hero: VPIP={hero_vpip:.0%} PFR={hero_pfr:.0%} -- {quality}.'
    )

    if leaks:
        for leak in leaks:
            tips.append(f'LEAK: {leak}')
    else:
        tips.append(
            f'NO LEAKS DETECTED: VPIP/PFR gap={hero_vpip-hero_pfr:.0%} is healthy. '
            f'Continue with current frequency discipline.'
        )

    gap = hero_vpip - hero_pfr
    if gap > 0.08:
        tips.append(
            f'LIMP REDUCTION: VPIP-PFR gap={gap:.0%}. '
            f'Replace limps with raises or folds. '
            f'Limping from {position.upper()} allows opponents to see cheap flops '
            f'and extracts less value from premium hands.'
        )

    return PreflopOpenFreqResult(
        position=position,
        table_type=table_type,
        game_type=game_type,
        gto_open_freq=gto_freq,
        adjusted_open_freq=adj_freq,
        open_size_bb=size_bb,
        hero_vpip=hero_vpip,
        hero_pfr=hero_pfr,
        vpip_pfr_quality=quality,
        detected_leaks=leaks,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pof_one_liner(r: PreflopOpenFreqResult) -> str:
    return (
        f'[POF {r.position.upper()}|{r.game_type}] '
        f'open={r.adjusted_open_freq:.0%} size={r.open_size_bb:.1f}BB '
        f'VPIP={r.hero_vpip:.0%}/PFR={r.hero_pfr:.0%} [{r.vpip_pfr_quality}]'
    )
