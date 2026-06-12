"""
Session Leak Prioritizer (session_leak_prioritizer.py)

Analyzes a poker session's HUD stats and identifies the top leaks
costing the most money per 100 hands. Prioritizes which leaks to fix
first based on estimated EV cost.

SESSION LEAK THEORY:
  Every player has multiple "leaks" -- deviations from GTO that opponents
  exploit. The key is to fix the HIGHEST EV-COST leaks first.

  COMMON LEAKS AND COSTS:
  1. Folding too much to 3-bets (fold > 65%): villain profits by 3-betting
     any two cards. Cost: ~2-3 BB/100 per 10% over-fold.
  2. Calling too wide preflop (VPIP > 35% in early position): playing bad hands
     out of position. Cost: ~1.5-2 BB/100 per 5% excess.
  3. Not c-betting enough (cbet < 40%): giving up profitable spots.
     Cost: ~1 BB/100 per 10% under-frequency.
  4. Over-folding to c-bets (fold-to-cbet > 65%): too nitty post-flop.
     Cost: ~1.5 BB/100 per 10% over-fold.
  5. WTSD too high (> 35%): calling down with weak hands.
     Cost: ~2 BB/100 per 5% excess.
  6. Over-3-betting (3bet > 12% in non-BTN positions): bluffing too much.
     Cost: ~1 BB/100 per 2% excess.
  7. Low WSD% given high WTSD (go-to-SD but don't win): poor showdown selection.
  8. Not barreling turns/rivers (low turn/river cbet): giving up with air.

DISTINCT FROM:
  postflop_frequency_dashboard.py: General frequency tracking dashboard
  villain_exploitability_scorer.py: Analyzes VILLAIN's leaks
  THIS MODULE:                     Prioritized HERO leak list; ranks by EV cost;
                                   actionable fix list for session review

Usage:
    from poker.session_leak_prioritizer import prioritize_leaks, SessionLeakResult, slp_one_liner

    result = prioritize_leaks(
        vpip=0.28,
        pfr=0.18,
        three_bet=0.08,
        fold_to_3bet=0.58,
        cbet_flop=0.62,
        fold_to_cbet=0.60,
        turn_cbet=0.45,
        river_cbet=0.40,
        wtsd=0.28,
        wsd=0.52,
        hands_played=5000,
    )
    print(slp_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List, Dict


# GTO baselines
GTO_BASELINE = {
    'vpip':          0.22,   # HJ/CO average
    'pfr':           0.17,
    'three_bet':     0.08,
    'fold_to_3bet':  0.55,
    'cbet_flop':     0.58,
    'fold_to_cbet':  0.50,
    'turn_cbet':     0.48,
    'river_cbet':    0.38,
    'wtsd':          0.28,
    'wsd':           0.52,
    'aggression_factor': 2.5,
}

# EV cost per unit deviation (BB / 100 hands per 1% deviation)
EV_COST_PER_PCT = {
    'wtsd':           0.40,   # calling down costs 0.40 BB/100 per 1% excess WTSD
    'fold_to_3bet':   0.30,   # over-folding costs 0.30 BB/100 per 1% excess
    'fold_to_cbet':   0.25,   # over-folding cbet costs 0.25 BB/100 per 1% excess
    'vpip':           0.20,   # calling too wide OOP costs 0.20 BB/100 per 1% excess
    'cbet_flop':      0.15,   # under c-betting costs 0.15 BB/100 per 1% deficit
    'turn_cbet':      0.12,
    'river_cbet':     0.10,
    'three_bet':      0.10,   # over-3-betting costs 0.10 per 1% excess
    'wsd':            0.08,   # low win-at-SD costs 0.08 per 1% deficit
}


def _compute_leak_ev_cost(stat_name: str, actual: float, baseline: float) -> float:
    """
    Compute EV cost of deviation from GTO baseline.
    For fold stats: positive deviation (fold more) = leak (under-defending).
    For VPIP/WTSD: positive deviation (play more/call more) = leak (loose).
    For C-bet stats: negative deviation (cbet less) = leak.
    Returns EV cost in BB/100 (always positive = bad).
    """
    cost_rate = EV_COST_PER_PCT.get(stat_name, 0.10)
    deviation_pct = abs(actual - baseline) * 100   # as percentage points

    # Only count as a leak if deviation is meaningful (>3 percentage points)
    if deviation_pct < 3.0:
        return 0.0

    return round(deviation_pct * cost_rate, 2)


def _deviation_direction(stat_name: str, actual: float, baseline: float) -> str:
    """Returns description of how the stat deviates."""
    diff = actual - baseline
    fold_stats = ('fold_to_3bet', 'fold_to_cbet')
    bet_stats = ('cbet_flop', 'turn_cbet', 'river_cbet', 'pfr', 'three_bet')
    call_stats = ('vpip', 'wtsd')
    win_stats = ('wsd',)

    if stat_name in fold_stats:
        return 'over_folding' if diff > 0 else 'under_folding'
    elif stat_name in call_stats:
        return 'too_loose' if diff > 0 else 'too_tight'
    elif stat_name in bet_stats:
        return 'over_betting' if diff > 0 else 'under_betting'
    elif stat_name in win_stats:
        return 'good' if diff >= 0 else 'losing_at_showdown'
    return 'deviation'


def _fix_advice(stat_name: str, actual: float, baseline: float) -> str:
    """One-line advice for fixing this leak."""
    diff = actual - baseline
    pct_diff = abs(diff * 100)

    fixes = {
        'fold_to_3bet': {
            True:  f'Call/4-bet more vs 3-bets (fold {actual:.0%} vs GTO {baseline:.0%}). Add more 3-bet calls in position with suited connectors, KQs, TT-88.',
            False: f'Tighten vs 3-bets (call too much). 3-bet calling range: IP=TT+/AK/AQ/suited connectors only.',
        },
        'fold_to_cbet': {
            True:  f'Defend more vs c-bets (fold {actual:.0%} vs GTO {baseline:.0%}). Check your check-raise frequency. Defend suited draws, backdoors, floats.',
            False: f'Fold more to c-bets when board misses range. Stop calling down with bottom pair/air.',
        },
        'wtsd': {
            True:  f'Go to showdown less (WTSD={actual:.0%} vs GTO {baseline:.0%}). Fold earlier with weak made hands on bad turns/rivers.',
            False: f'WTSD slightly low but not critical. Ensure not folding too much vs river bets.',
        },
        'vpip': {
            True:  f'Tighten preflop range (VPIP={actual:.0%} vs GTO {baseline:.0%}). Fold more speculative hands OOP (low suited gappers, weak offsuit aces).',
            False: f'VPIP slightly low -- consider widening BTN/CO if too tight.',
        },
        'cbet_flop': {
            True:  f'Reduce c-bet frequency (cbet={actual:.0%} vs GTO {baseline:.0%}). Check more on boards that miss PFR range (low connected, 3-way pots).',
            False: f'C-bet more on flop (cbet={actual:.0%} vs GTO {baseline:.0%}). Missing +EV spots by giving up with air/draws.',
        },
        'turn_cbet': {
            True:  f'Reduce turn barrels. Betting too wide on turn -- only double-barrel value/semi-bluffs.',
            False: f'Barrel turn more. Hero checks/gives up on turn too often after c-betting flop.',
        },
        'river_cbet': {
            True:  f'Reduce river bluffs. Only bet river with value + GTO bluff frequency (alpha = bet/pot+bet).',
            False: f'Bet river more. Checking back missed value. Polarize range and bet larger on river.',
        },
        'three_bet': {
            True:  f'3-bet less (3bet={actual:.0%} vs GTO {baseline:.0%}). Over-bluffing preflop. Reduce light 3-bets except vs BTN/SB.',
            False: f'3-bet more. Under-3-betting lets villains steal too cheaply. Add value 3-bets + A-x suited bluffs.',
        },
        'wsd': {
            True:  f'Good WSD%! Maintaining showdown wins well.',
            False: f'Win more at showdown. Select better showdown hands; avoid bluff-catching with total air.',
        },
    }

    direction = diff > 0
    leak_fix = fixes.get(stat_name, {}).get(direction, f'Adjust {stat_name} toward {baseline:.0%}.')
    return leak_fix


@dataclass
class LeakEntry:
    stat_name: str
    actual: float
    baseline: float
    deviation_pct: float      # percentage points of deviation
    ev_cost_bb_100: float     # estimated EV cost in BB/100
    direction: str            # 'over_folding', 'too_loose', etc.
    fix_advice: str
    priority: int             # 1 = highest priority


@dataclass
class SessionLeakResult:
    # Inputs
    vpip: float
    pfr: float
    three_bet: float
    fold_to_3bet: float
    cbet_flop: float
    fold_to_cbet: float
    turn_cbet: float
    river_cbet: float
    wtsd: float
    wsd: float
    hands_played: int

    # Analysis
    leaks: List[LeakEntry]           # sorted by priority (highest EV cost first)
    total_ev_cost_bb_100: float      # sum of all leak costs
    top_leak: str                    # name of most costly leak
    reliability: str                 # 'high' / 'medium' / 'low' (based on sample size)

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def prioritize_leaks(
    vpip: float = 0.28,
    pfr: float = 0.18,
    three_bet: float = 0.08,
    fold_to_3bet: float = 0.58,
    cbet_flop: float = 0.62,
    fold_to_cbet: float = 0.60,
    turn_cbet: float = 0.45,
    river_cbet: float = 0.40,
    wtsd: float = 0.28,
    wsd: float = 0.52,
    hands_played: int = 5000,
) -> SessionLeakResult:
    """
    Prioritize session leaks by EV cost.

    Args:
        vpip:           VPIP (voluntarily put money in pot)
        pfr:            PFR (pre-flop raise)
        three_bet:      3-bet frequency
        fold_to_3bet:   Fold to 3-bet frequency
        cbet_flop:      Flop c-bet frequency
        fold_to_cbet:   Fold to c-bet frequency
        turn_cbet:      Turn c-bet/barrel frequency
        river_cbet:     River bet/barrel frequency
        wtsd:           Went to showdown %
        wsd:            Won at showdown %
        hands_played:   Sample size

    Returns:
        SessionLeakResult
    """
    stats = {
        'vpip':         vpip,
        'pfr':          pfr,
        'three_bet':    three_bet,
        'fold_to_3bet': fold_to_3bet,
        'cbet_flop':    cbet_flop,
        'fold_to_cbet': fold_to_cbet,
        'turn_cbet':    turn_cbet,
        'river_cbet':   river_cbet,
        'wtsd':         wtsd,
        'wsd':          wsd,
    }

    leaks = []
    for name, val in stats.items():
        baseline = GTO_BASELINE.get(name, 0.50)
        ev_cost = _compute_leak_ev_cost(name, val, baseline)
        if ev_cost > 0:
            dev_pct = abs(val - baseline) * 100
            direction = _deviation_direction(name, val, baseline)
            fix = _fix_advice(name, val, baseline)
            leaks.append(LeakEntry(
                stat_name=name,
                actual=val,
                baseline=baseline,
                deviation_pct=round(dev_pct, 1),
                ev_cost_bb_100=ev_cost,
                direction=direction,
                fix_advice=fix,
                priority=0,   # set below
            ))

    # Sort by EV cost descending
    leaks.sort(key=lambda x: x.ev_cost_bb_100, reverse=True)
    for i, lk in enumerate(leaks, start=1):
        lk.priority = i

    total_cost = round(sum(l.ev_cost_bb_100 for l in leaks), 2)
    top = leaks[0].stat_name if leaks else 'none'

    if hands_played >= 10000:
        reliability = 'high'
    elif hands_played >= 3000:
        reliability = 'medium'
    else:
        reliability = 'low'

    top_cost = leaks[0].ev_cost_bb_100 if leaks else 0.0
    reasoning = (
        f'Session leak analysis: {hands_played} hands. '
        f'Top leak={top} ({top_cost:.1f} BB/100). '
        f'Total EV cost={total_cost:.1f} BB/100 across {len(leaks)} leaks. '
        f'Sample reliability={reliability}.'
    )

    verdict = (
        f'[SLP {reliability.upper()}|{hands_played}h] '
        f'top_leak={top} ({top_cost:.1f}BB/100) | '
        f'total_cost={total_cost:.1f}BB/100 | leaks={len(leaks)}'
    )

    tips = []
    if leaks:
        tips.append(
            f'TOP PRIORITY LEAK: {leaks[0].stat_name.upper()} ({leaks[0].direction}) '
            f'-- costs ~{leaks[0].ev_cost_bb_100:.1f} BB/100. '
            f'FIX: {leaks[0].fix_advice}'
        )

    if len(leaks) >= 2:
        tips.append(
            f'#2 LEAK: {leaks[1].stat_name.upper()} ({leaks[1].direction}) '
            f'-- costs ~{leaks[1].ev_cost_bb_100:.1f} BB/100. '
            f'FIX: {leaks[1].fix_advice}'
        )

    tips.append(
        f'TOTAL LEAK COST: {total_cost:.1f} BB/100 across {len(leaks)} detected leaks. '
        f'Fix top 2 leaks to recover ~{sum(l.ev_cost_bb_100 for l in leaks[:2]):.1f} BB/100. '
        f'Sample size: {hands_played} hands (reliability={reliability}).'
    )

    if reliability == 'low':
        tips.append(
            f'LOW SAMPLE SIZE ({hands_played} hands): Stats are not stable yet. '
            f'Treat leak analysis as directional, not definitive. '
            f'Need 3000+ hands for reliable stats.'
        )

    if not leaks:
        tips.append(
            f'NO SIGNIFICANT LEAKS DETECTED: All stats within 3% of GTO baseline. '
            f'Focus on table selection and exploitative adjustments vs specific villains.'
        )

    return SessionLeakResult(
        vpip=vpip, pfr=pfr, three_bet=three_bet,
        fold_to_3bet=fold_to_3bet, cbet_flop=cbet_flop,
        fold_to_cbet=fold_to_cbet, turn_cbet=turn_cbet,
        river_cbet=river_cbet, wtsd=wtsd, wsd=wsd,
        hands_played=hands_played,
        leaks=leaks,
        total_ev_cost_bb_100=total_cost,
        top_leak=top,
        reliability=reliability,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def slp_one_liner(r: SessionLeakResult) -> str:
    top_cost = r.leaks[0].ev_cost_bb_100 if r.leaks else 0.0
    return (
        f'[SLP {r.reliability.upper()}|{r.hands_played}h] '
        f'top={r.top_leak} ({top_cost:.1f}BB/100) | '
        f'total={r.total_ev_cost_bb_100:.1f}BB/100 leaks={len(r.leaks)}'
    )
