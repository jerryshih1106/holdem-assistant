"""
Win Rate Maximizer (win_rate_maximizer.py)

Analyzes hero's HUD statistics vs GTO benchmarks to find the SINGLE
highest-ROI leak to fix. Unlike leak_detector.py which lists all leaks,
this module:

  1. Estimates the BB/100 impact of each deviation
  2. Returns the #1 highest-priority improvement
  3. Provides specific actionable targets with numbers

BENCHMARKS (6-max cash, 100BB):
  VPIP:          22-28%   (too high = spewing chips preflop)
  PFR:           17-22%   (too low = limping = bleeding)
  3bet%:          8-12%   (too low = regs steal freely)
  AF:            2.5-4.0  (too low = not extracting, too high = spewing)
  WTSD:          26-32%   (too high = calling down junk)
  WWSF:          48-55%   (too low = weak post-flop execution)
  WSD:           52-57%   (too low = calling with losing hands at SD)
  Cbet_flop:     55-70%   (too high = predictable/exploitable)
  Fold_to_cbet:  40-55%   (too high = nitty, too low = calling station)

IMPACT MODEL:
  Each stat's deviation from benchmark is multiplied by an impact weight
  (estimated BB/100 per 1% or 1-unit deviation). The stat with highest
  total estimated impact is the #1 priority.

Usage:
    from poker.win_rate_maximizer import maximize_win_rate, WinRateMaxAdvice, wrm_one_liner

    advice = maximize_win_rate(
        vpip=35.0, pfr=22.0, threbet=5.0,
        af=1.8, wtsd=38.0, game_format='6max',
        current_bb100=-2.0, sample_hands=50000,
    )
    print(wrm_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# --------------------------------------------------------------------------
# Benchmarks per game format
# --------------------------------------------------------------------------

_BENCHMARKS: Dict[str, Dict[str, Tuple[float, float]]] = {
    '6max': {
        'vpip':         (22.0, 28.0),
        'pfr':          (17.0, 22.0),
        'threbet':      (8.0,  12.0),
        'af':           (2.5,   4.0),
        'wtsd':         (26.0, 32.0),
        'wwsf':         (48.0, 55.0),
        'wsd':          (52.0, 57.0),
        'cbet_flop':    (55.0, 70.0),
        'fold_to_cbet': (40.0, 55.0),
        'cbet_turn':    (38.0, 58.0),
    },
    'full_ring': {
        'vpip':         (16.0, 22.0),
        'pfr':          (12.0, 17.0),
        'threbet':      (5.0,   8.0),
        'af':           (2.0,   3.5),
        'wtsd':         (24.0, 30.0),
        'wwsf':         (44.0, 52.0),
        'wsd':          (51.0, 56.0),
        'cbet_flop':    (55.0, 68.0),
        'fold_to_cbet': (38.0, 52.0),
        'cbet_turn':    (35.0, 55.0),
    },
    'heads_up': {
        'vpip':         (55.0, 75.0),
        'pfr':          (40.0, 60.0),
        'threbet':      (15.0, 25.0),
        'af':           (3.0,   5.0),
        'wtsd':         (35.0, 45.0),
        'wwsf':         (52.0, 65.0),
        'wsd':          (50.0, 58.0),
        'cbet_flop':    (60.0, 80.0),
        'fold_to_cbet': (35.0, 50.0),
        'cbet_turn':    (45.0, 70.0),
    },
}

# BB/100 impact per 1% (or 1-unit for af) deviation beyond benchmark boundary
_IMPACT_WEIGHT: Dict[str, float] = {
    'vpip':         0.14,
    'pfr':          0.12,
    'threbet':      0.22,   # 3bet too low is a massive cash game leak
    'af':           0.28,   # passivity is very costly
    'wtsd':         0.18,
    'wwsf':         0.15,
    'wsd':          0.20,
    'cbet_flop':    0.10,
    'fold_to_cbet': 0.12,
    'cbet_turn':    0.10,
}

_STAT_LABEL: Dict[str, str] = {
    'vpip':         'VPIP',
    'pfr':          'PFR',
    'threbet':      '3Bet%',
    'af':           'AF (Aggression Factor)',
    'wtsd':         'WTSD (Went to Showdown%)',
    'wwsf':         'WWSF (Won When Saw Flop%)',
    'wsd':          'WSD (Won at Showdown%)',
    'cbet_flop':    'Flop C-Bet%',
    'fold_to_cbet': 'Fold to C-Bet%',
    'cbet_turn':    'Turn C-Bet%',
}

# Directional advice for each stat deviation
_ADVICE: Dict[Tuple[str, str], str] = {
    ('vpip', 'high'):         'FOLD MORE PREFLOP. Cut marginal EP hands: KTo UTG, Q9s UTG, weak Axo MP. Tighten EP/MP first.',
    ('vpip', 'low'):          'OPEN MORE from LP. Add Axs, sc, Kxs to BTN/CO range. You leave free money on the table.',
    ('pfr', 'low'):           'RAISE MORE, LIMP LESS. Any time you enter the pot, make it a raise. Limping bleeds EV.',
    ('pfr', 'high'):          'Over-raising. Add flat calls in 3bet pots. Balance your BTN range with some calls.',
    ('threbet', 'low'):       '3BET MORE -- #1 cash game leak. Add A5s-A2s, KQo, QJs, KJs to 3bet range from BTN/CO/SB.',
    ('threbet', 'high'):      '3bet range too wide. Tighten to value (JJ+, AQs+) + strong suited bluffs only.',
    ('af', 'low'):            'BET AND RAISE MORE. Stop calling with TP. Bet draws. Raise thin value. Passivity costs most.',
    ('af', 'high'):           'Too aggressive. Add check-calls with medium hands. Balance your polarized betting range.',
    ('wtsd', 'high'):         'FOLD MORE AT SHOWDOWN. Stop calling river bets with weak pairs. Use pot odds + villain range.',
    ('wtsd', 'low'):          'You fold too much. Call down top pair on dry boards. Check pot odds before folding.',
    ('wwsf', 'low'):          'POST-FLOP LEAK: Bet draws aggressively. Build pots in position. Stop checking back marginal hands.',
    ('wwsf', 'high'):         'WWSF is high -- this is usually a positive sign, not a leak.',
    ('wsd', 'low'):           'Calling with losing hands at showdown. Tighten your river calling range significantly.',
    ('wsd', 'high'):          'WSD is high -- this is usually a positive sign.',
    ('cbet_flop', 'high'):    'C-BET LESS. Check more on wet/connected boards and when your range misses. Being exploited.',
    ('cbet_flop', 'low'):     'C-BET MORE. You leave easy pots on the table. Bet more on dry boards for protection.',
    ('fold_to_cbet', 'high'): 'CALL/RAISE MORE C-BETS. Float with pairs, raise draws on favorable boards. You are folding too profitably to them.',
    ('fold_to_cbet', 'low'):  'FOLD MORE TO C-BETS. You call too loosely. Cut weak pairs/gutshots on wet boards.',
    ('cbet_turn', 'low'):     'C-BET TURNS MORE. Follow up on turns when you have equity or protection. Do not give free cards.',
    ('cbet_turn', 'high'):    'C-bet too many turns. Check back more medium strength hands on non-improving turns.',
}


# --------------------------------------------------------------------------
# Dataclass
# --------------------------------------------------------------------------

@dataclass
class WinRateMaxAdvice:
    # Inputs (None = not provided / unknown)
    vpip: Optional[float]
    pfr: Optional[float]
    threbet: Optional[float]
    af: Optional[float]
    wtsd: Optional[float]
    wwsf: Optional[float]
    wsd: Optional[float]
    cbet_flop: Optional[float]
    fold_to_cbet: Optional[float]
    cbet_turn: Optional[float]
    game_format: str
    current_bb100: Optional[float]
    sample_hands: int

    # Analysis
    deviations: Dict        # {stat: {'value': x, 'lo': lo, 'hi': hi, 'direction': str, 'deviation': float, 'impact_bb100': float}}
    leak_ranking: List[Tuple[str, float]]   # [(stat, impact_bb100), ...] sorted desc

    # Top priority
    top_leak: str
    top_leak_direction: str     # 'high' or 'low'
    top_leak_impact: float      # estimated BB/100 gain from fixing it
    priority_advice: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Main function
# --------------------------------------------------------------------------

def maximize_win_rate(
    vpip: Optional[float] = None,
    pfr: Optional[float] = None,
    threbet: Optional[float] = None,
    af: Optional[float] = None,
    wtsd: Optional[float] = None,
    wwsf: Optional[float] = None,
    wsd: Optional[float] = None,
    cbet_flop: Optional[float] = None,
    fold_to_cbet: Optional[float] = None,
    cbet_turn: Optional[float] = None,
    game_format: str = '6max',
    current_bb100: Optional[float] = None,
    sample_hands: int = 10000,
) -> WinRateMaxAdvice:
    """
    Find the single highest-priority stat improvement for hero's win rate.

    Args:
        vpip:          Hero VPIP in % (e.g. 25.0 means 25%)
        pfr:           Hero PFR in %
        threbet:       Hero 3Bet% (e.g. 7.5)
        af:            Hero Aggression Factor (e.g. 2.3)
        wtsd:          Went to Showdown % (e.g. 30.0)
        wwsf:          Won When Saw Flop % (e.g. 48.0)
        wsd:           Won at Showdown % (e.g. 53.0)
        cbet_flop:     Flop C-Bet %
        fold_to_cbet:  Fold to Flop C-Bet %
        cbet_turn:     Turn C-Bet %
        game_format:   '6max', 'full_ring', or 'heads_up'
        current_bb100: Hero's current win rate in BB/100
        sample_hands:  Number of hands in sample

    Returns:
        WinRateMaxAdvice
    """
    benchmarks = _BENCHMARKS.get(game_format, _BENCHMARKS['6max'])

    stat_values: Dict[str, Optional[float]] = {
        'vpip': vpip, 'pfr': pfr, 'threbet': threbet, 'af': af,
        'wtsd': wtsd, 'wwsf': wwsf, 'wsd': wsd,
        'cbet_flop': cbet_flop, 'fold_to_cbet': fold_to_cbet, 'cbet_turn': cbet_turn,
    }

    deviations: Dict = {}
    ranking: List[Tuple[str, float]] = []

    for stat, val in stat_values.items():
        if val is None:
            continue
        lo, hi = benchmarks[stat]
        weight = _IMPACT_WEIGHT[stat]

        if val < lo:
            direction = 'low'
            deviation = lo - val
        elif val > hi:
            direction = 'high'
            deviation = val - hi
        else:
            direction = 'ok'
            deviation = 0.0

        impact = round(deviation * weight, 3)
        deviations[stat] = {
            'value':      round(val, 2),
            'lo':         lo,
            'hi':         hi,
            'direction':  direction,
            'deviation':  round(deviation, 2),
            'impact_bb100': impact,
        }
        if direction != 'ok':
            ranking.append((stat, impact))

    ranking.sort(key=lambda x: x[1], reverse=True)

    # Top leak
    if ranking:
        top_stat, top_impact = ranking[0]
        top_dir = deviations[top_stat]['direction']
        priority_advice = _ADVICE.get((top_stat, top_dir), f'Fix {top_stat} ({top_dir}).')
    else:
        top_stat = 'none'
        top_impact = 0.0
        top_dir = 'ok'
        priority_advice = 'All stats within benchmark range. Focus on game selection and execution quality.'

    # Verdict
    total_leakage = sum(v['impact_bb100'] for v in deviations.values())
    wr_str = f'{current_bb100:+.1f} BB/100' if current_bb100 is not None else 'unknown'
    leak_count = len(ranking)

    verdict = (
        f'WIN RATE: {wr_str} ({sample_hands:,} hands). '
        f'{leak_count} stat(s) outside benchmark. '
        f'Estimated total leakage: {total_leakage:.1f} BB/100. '
        f'TOP PRIORITY: Fix {_STAT_LABEL.get(top_stat, top_stat)} '
        f'({deviations.get(top_stat, {}).get("value", "N/A")} vs optimal {benchmarks.get(top_stat, (0,0))}). '
        f'Est. gain: +{top_impact:.1f} BB/100.'
    ) if top_stat != 'none' else (
        f'WIN RATE: {wr_str} ({sample_hands:,} hands). No major leaks detected in provided stats.'
    )

    reasoning_parts = []
    for stat, impact in ranking[:4]:
        d = deviations[stat]
        reasoning_parts.append(
            f'{_STAT_LABEL.get(stat, stat)}={d["value"]:.1f} '
            f'({d["direction"]} by {d["deviation"]:.1f}, est -{impact:.2f} BB/100)'
        )
    reasoning = 'Ranked leaks: ' + ' | '.join(reasoning_parts) if reasoning_parts else 'No leaks detected.'

    # Tips
    tips = []
    if top_stat != 'none':
        tips.append(f'#1 PRIORITY: {priority_advice}')

    if len(ranking) >= 2:
        stat2, impact2 = ranking[1]
        dir2 = deviations[stat2]['direction']
        adv2 = _ADVICE.get((stat2, dir2), f'Adjust {stat2}.')
        tips.append(f'#2 PRIORITY: {adv2}')

    if sample_hands < 10000:
        tips.append(
            f'SMALL SAMPLE ({sample_hands:,} hands): Stats unreliable below 10k hands. '
            f'True win rate confidence interval is very wide. Get more volume before adjusting.'
        )
    elif sample_hands < 50000:
        tips.append(
            f'SAMPLE WARNING ({sample_hands:,} hands): Stats are directionally useful '
            f'but not statistically precise. Treat as trends, not absolutes.'
        )

    if current_bb100 is not None and current_bb100 < -2.0:
        tips.append(
            f'SIGNIFICANT LOSING RATE ({current_bb100:+.1f} BB/100): '
            f'At this loss rate you are bleeding {abs(current_bb100):.1f} BB per 100 hands. '
            f'Fix the #1 leak immediately. Even a 1 BB/100 improvement is {abs(current_bb100/ 100):.2f}% of stack per 100 hands.'
        )

    if not tips:
        tips.append(
            f'Stats look healthy. Continue monitoring. '
            f'Focus on game selection and reading opponents for further gains.'
        )

    return WinRateMaxAdvice(
        vpip=vpip, pfr=pfr, threbet=threbet, af=af,
        wtsd=wtsd, wwsf=wwsf, wsd=wsd,
        cbet_flop=cbet_flop, fold_to_cbet=fold_to_cbet, cbet_turn=cbet_turn,
        game_format=game_format,
        current_bb100=current_bb100,
        sample_hands=sample_hands,
        deviations=deviations,
        leak_ranking=ranking,
        top_leak=top_stat,
        top_leak_direction=top_dir,
        top_leak_impact=round(top_impact, 3),
        priority_advice=priority_advice,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def wrm_one_liner(r: WinRateMaxAdvice) -> str:
    wr = f'{r.current_bb100:+.1f}BB/100' if r.current_bb100 is not None else 'wr=?'
    label = _STAT_LABEL.get(r.top_leak, r.top_leak)
    return (
        f'[WRM {r.game_format}|{r.sample_hands//1000}k hands] '
        f'{wr} | '
        f'top_leak={label}({r.top_leak_direction}) est=+{r.top_leak_impact:.2f}BB/100 | '
        f'{len(r.leak_ranking)} leaks ranked'
    )
