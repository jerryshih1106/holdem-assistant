"""
Postflop Frequency Dashboard (postflop_frequency_dashboard.py)

Compares hero's actual postflop frequencies across ALL major spots
simultaneously vs GTO baselines, ranking deviations by EV cost.

This module answers the question: "Across ALL my postflop decisions,
WHERE am I leaking the most money?"

SPOTS TRACKED (8 major postflop frequencies):
  1. cbet_flop:     C-bet frequency on flop as PFR
  2. cbet_turn:     Turn c-bet (double barrel) frequency
  3. cbet_river:    River c-bet (triple barrel) frequency
  4. check_raise:   Check-raise frequency as OOP vs c-bet
  5. fold_vs_cbet:  Fold to c-bet frequency (too tight = losing EV)
  6. fold_vs_3bet:  Fold to 3-bet/raise frequency
  7. wtsd:          Went to showdown %
  8. river_bet:     River bet frequency when checked to

GTO BASELINES (6-max, 100BB):
  cbet_flop:   55-65% (IP), 45-55% (OOP)
  cbet_turn:   45-55% (after flop bet called)
  cbet_river:  35-45%
  check_raise: 8-15%
  fold_vs_cbet: 35-45%
  fold_vs_3bet: 50-60%
  wtsd:        25-32%
  river_bet:   50-60% (when checked to IP on river)

EV COST PER DEVIATION (BB/100 per 10% deviation):
  Derived from population studies; deviations from GTO cost differently.
  fold_vs_cbet:    highest cost (most common spot)
  cbet_flop:       high (frequent; sizing effects)
  river_bet:       medium-high (river bets are large)
  Others:          medium

DISTINCT FROM:
  cbet_frequency_auditor.py:  Audits c-bet frequency only
  gto_deviation.py:           Analyzes a single GTO deviation
  session_positional_leak_tracker.py: Tracks PREFLOP leaks by position
  THIS MODULE:                Dashboard of ALL postflop frequencies;
                              ranks deviations by estimated EV cost;
                              gives a comprehensive spot-by-spot report

Usage:
    from poker.postflop_frequency_dashboard import analyze_postflop_frequencies, FrequencyDashboard, pfd_one_liner

    result = analyze_postflop_frequencies(
        cbet_flop=0.72,
        cbet_turn=0.55,
        cbet_river=0.40,
        check_raise=0.07,
        fold_vs_cbet=0.55,
        fold_vs_3bet=0.68,
        wtsd=0.28,
        river_bet=0.58,
        hero_position='ip',
        hands=500,
    )
    print(pfd_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# GTO baselines per position (IP / OOP)
GTO_FREQS = {
    'ip': {
        'cbet_flop':    0.60,
        'cbet_turn':    0.50,
        'cbet_river':   0.40,
        'check_raise':  0.10,
        'fold_vs_cbet': 0.38,
        'fold_vs_3bet': 0.55,
        'wtsd':         0.30,
        'river_bet':    0.55,
    },
    'oop': {
        'cbet_flop':    0.50,
        'cbet_turn':    0.45,
        'cbet_river':   0.36,
        'check_raise':  0.12,
        'fold_vs_cbet': 0.42,
        'fold_vs_3bet': 0.57,
        'wtsd':         0.28,
        'river_bet':    0.48,
    },
}

# EV cost per 10% absolute deviation from GTO (BB/100)
# Higher = more expensive to be wrong in this spot
EV_COST_PER_10PCT = {
    'fold_vs_cbet': 1.5,   # Most common spot; being too tight/loose is very costly
    'cbet_flop':    1.3,
    'river_bet':    1.2,
    'cbet_turn':    1.0,
    'fold_vs_3bet': 1.0,
    'cbet_river':   0.9,
    'wtsd':         0.8,
    'check_raise':  0.6,
}

SPOT_DESCRIPTIONS = {
    'cbet_flop':    'Flop c-bet (as PFR)',
    'cbet_turn':    'Turn double-barrel (after flop cbet called)',
    'cbet_river':   'River triple-barrel',
    'check_raise':  'Check-raise (OOP vs c-bet)',
    'fold_vs_cbet': 'Fold to c-bet',
    'fold_vs_3bet': 'Fold to 3-bet/raise',
    'wtsd':         'Went to showdown',
    'river_bet':    'River bet when checked to (IP)',
}

MIN_HANDS = 100


def _spot_analysis(
    spot: str,
    hero_pct: float,
    gto_pct: float,
    hands: int,
) -> dict:
    """Analyze a single frequency spot."""
    abs_dev = round(abs(hero_pct - gto_pct), 3)
    rel_dev = round((hero_pct - gto_pct) / max(gto_pct, 0.01), 3)
    ev_cost = round(abs_dev / 0.10 * EV_COST_PER_10PCT.get(spot, 0.8), 2)

    if abs_dev <= 0.03:
        status = 'on_target'
    elif abs_dev <= 0.07:
        status = 'minor_leak'
    elif abs_dev <= 0.15:
        status = 'moderate_leak'
    else:
        status = 'critical_leak'

    direction = 'too_high' if hero_pct > gto_pct else 'too_low'

    # Direction-specific advice
    advice_map = {
        'cbet_flop': {
            'too_high': 'You c-bet too often -- reduce c-bets on unfavorable boards; check more to protect checking range.',
            'too_low':  'You c-bet too rarely -- increase c-bets on dry boards and boards that hit your range.',
        },
        'cbet_turn': {
            'too_high': 'Double-barreling too much -- check-back turns more with medium hands; barrel only strong hands+draws.',
            'too_low':  'Not following up flop bets enough -- barrel more when you have equity or strong hands.',
        },
        'cbet_river': {
            'too_high': 'Triple-barreling too often -- you likely have too many bluffs; cut river bluffs.',
            'too_low':  'Not value-betting rivers enough -- bet more with strong hands; thinly value-bet.',
        },
        'check_raise': {
            'too_high': 'Check-raising too often -- reserve check-raises for strong hands + nutted draws; simpler to call.',
            'too_low':  'Not check-raising enough -- add check-raises to protect checking range; creates balanced strategy.',
        },
        'fold_vs_cbet': {
            'too_high': 'Folding too much to c-bets -- you are over-folding; call down wider with any pair or draw.',
            'too_low':  'Calling too many c-bets -- tighten up; fold more weak hands to c-bets.',
        },
        'fold_vs_3bet': {
            'too_high': 'Folding too much to 3-bets -- widen calling range; call with suited aces, connectors.',
            'too_low':  'Calling too many 3-bets -- tighten calling range; prefer 4-bet-or-fold.',
        },
        'wtsd': {
            'too_high': 'Going to showdown too much -- fold more on rivers when villain shows strength; stop calling down.',
            'too_low':  'Not going to showdown enough -- you may be over-folding rivers; add bluff-catches.',
        },
        'river_bet': {
            'too_high': 'Betting rivers too often -- check back more medium-strength hands; protect checking range.',
            'too_low':  'Not betting rivers enough -- value-bet thinner; do not miss bets with strong hands.',
        },
    }
    advice = advice_map.get(spot, {}).get(direction, 'Adjust toward GTO baseline.')

    return {
        'spot': spot,
        'description': SPOT_DESCRIPTIONS.get(spot, spot),
        'hero_pct': hero_pct,
        'gto_pct': gto_pct,
        'abs_dev': abs_dev,
        'rel_dev': rel_dev,
        'status': status,
        'direction': direction,
        'ev_cost_bb100': ev_cost,
        'reliable': hands >= MIN_HANDS,
        'advice': advice,
    }


@dataclass
class FrequencyDashboard:
    # Inputs
    hero_position: str
    hands: int
    cbet_flop: float
    cbet_turn: float
    cbet_river: float
    check_raise: float
    fold_vs_cbet: float
    fold_vs_3bet: float
    wtsd: float
    river_bet: float

    # Per-spot analysis
    spot_analyses: Dict[str, dict]     # spot -> analysis dict

    # Ranked leaks
    leak_ranking: List[str]            # spots ranked by ev_cost_bb100 descending
    total_ev_leak_bb100: float         # sum of all spot EV costs
    top_leak_spot: str
    top_leak_cost: float               # BB/100 cost of top leak

    # Summary
    on_target_spots: List[str]         # spots within 3% of GTO
    critical_leak_spots: List[str]     # spots with > 15% deviation

    verdict: str
    tips: List[str] = field(default_factory=list)


def analyze_postflop_frequencies(
    cbet_flop: float = 0.60,
    cbet_turn: float = 0.50,
    cbet_river: float = 0.40,
    check_raise: float = 0.10,
    fold_vs_cbet: float = 0.40,
    fold_vs_3bet: float = 0.55,
    wtsd: float = 0.30,
    river_bet: float = 0.55,
    hero_position: str = 'ip',
    hands: int = 300,
) -> FrequencyDashboard:
    """
    Comprehensive postflop frequency dashboard.

    Args:
        cbet_flop:    Hero's flop c-bet frequency (0-1)
        cbet_turn:    Turn double-barrel frequency (0-1)
        cbet_river:   River triple-barrel frequency (0-1)
        check_raise:  Check-raise frequency (0-1)
        fold_vs_cbet: Fold-to-c-bet frequency (0-1)
        fold_vs_3bet: Fold-to-3-bet frequency (0-1)
        wtsd:         Went-to-showdown % (0-1)
        river_bet:    River bet frequency when checked to (0-1)
        hero_position: 'ip' or 'oop'
        hands:        Number of hands in sample

    Returns:
        FrequencyDashboard
    """
    pos = hero_position if hero_position in GTO_FREQS else 'ip'
    gto = GTO_FREQS[pos]

    hero_vals = {
        'cbet_flop':    cbet_flop,
        'cbet_turn':    cbet_turn,
        'cbet_river':   cbet_river,
        'check_raise':  check_raise,
        'fold_vs_cbet': fold_vs_cbet,
        'fold_vs_3bet': fold_vs_3bet,
        'wtsd':         wtsd,
        'river_bet':    river_bet,
    }

    analyses = {
        spot: _spot_analysis(spot, hero_vals[spot], gto[spot], hands)
        for spot in hero_vals
    }

    ranked = sorted(analyses.keys(), key=lambda s: -analyses[s]['ev_cost_bb100'])
    total_ev = round(sum(a['ev_cost_bb100'] for a in analyses.values()), 2)
    top_spot = ranked[0]
    top_cost = analyses[top_spot]['ev_cost_bb100']

    on_target = [s for s in analyses if analyses[s]['status'] == 'on_target']
    critical = [s for s in analyses if analyses[s]['status'] == 'critical_leak']

    verdict = (
        f'[PFD top={top_spot}|{total_ev:.1f}BB/100 total_leak] '
        f'{len(on_target)}/8 spots on-target | '
        f'critical={len(critical)} | hands={hands}'
    )

    tips = []
    for spot in ranked[:3]:
        a = analyses[spot]
        if a['abs_dev'] >= 0.03:
            tips.append(
                f'[{a["description"].upper()}] hero={a["hero_pct"]:.0%} gto={a["gto_pct"]:.0%} '
                f'dev={a["abs_dev"]:+.0%} cost={a["ev_cost_bb100"]:.1f}BB/100 -- {a["advice"]}'
            )

    # Always include top leak summary even if near GTO
    top_a = analyses[top_spot]
    if not any(top_spot in t for t in tips):
        tips.append(
            f'[TOP SPOT: {top_a["description"].upper()}] hero={top_a["hero_pct"]:.0%} '
            f'gto={top_a["gto_pct"]:.0%} cost={top_a["ev_cost_bb100"]:.1f}BB/100.'
        )

    if total_ev >= 5.0:
        tips.append(
            f'HIGH TOTAL LEAK: {total_ev:.1f}BB/100 across all postflop spots. '
            f'Focus on top 2 spots first; fixing one reduces EV leak across all hands.'
        )
    elif total_ev >= 2.0:
        tips.append(
            f'MODERATE LEAK: {total_ev:.1f}BB/100. Fix top 2 spots; others are acceptable.'
        )
    else:
        tips.append(f'LOW LEAK: {total_ev:.1f}BB/100 total -- postflop frequencies are near GTO.')

    if hands < MIN_HANDS:
        tips.append(
            f'SMALL SAMPLE ({hands} hands): Frequency stats unreliable. '
            f'Need {MIN_HANDS}+ hands per spot for reliable deviation analysis.'
        )

    return FrequencyDashboard(
        hero_position=hero_position,
        hands=hands,
        cbet_flop=cbet_flop,
        cbet_turn=cbet_turn,
        cbet_river=cbet_river,
        check_raise=check_raise,
        fold_vs_cbet=fold_vs_cbet,
        fold_vs_3bet=fold_vs_3bet,
        wtsd=wtsd,
        river_bet=river_bet,
        spot_analyses=analyses,
        leak_ranking=ranked,
        total_ev_leak_bb100=total_ev,
        top_leak_spot=top_spot,
        top_leak_cost=top_cost,
        on_target_spots=on_target,
        critical_leak_spots=critical,
        verdict=verdict,
        tips=tips,
    )


def pfd_one_liner(r: FrequencyDashboard) -> str:
    return (
        f'[PFD top={r.top_leak_spot}|{r.total_ev_leak_bb100:.1f}BB/100] '
        f'{len(r.on_target_spots)}/8 on-target | '
        f'critical={len(r.critical_leak_spots)} | hands={r.hands}'
    )
