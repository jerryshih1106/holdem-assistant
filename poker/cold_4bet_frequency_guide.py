"""
Cold 4-Bet Frequency Guide (cold_4bet_frequency_guide.py)

Quantifies optimal cold 4-bet frequency by position, 3-bettor type, opener type,
and stack depth. Cold 4-bet = entering a 3-bet pot with a 4-bet from a position
that had not yet put money in (typically the blinds facing open + 3-bet).

THEORY:
  COLD 4-BET REQUIREMENTS:
  Unlike normal 4-bets (where you opened or 3-bet), cold 4-bets face two opponents
  whose combined range is very strong. Range must be extra polar: pure value + blockers.

  VALUE: QQ+, AK (sometimes JJ if 3-bettor is confirmed wide/lag)
  BLUFFS: A2s-A5s, KQs -- blocker to AK/KK; no showdown value vs strong ranges

  BASELINE FREQUENCIES:
  BB:  3.0%  (most common cold 4-bet spot; position matters less since BB is last)
  SB:  2.0%  (oop after cold 4-bet; tighter)
  MP:  1.5%  (skip-seat cold; uncommon)
  UTG: 0.8%  (both openers likely strong; near-pure value only)

  ADJUSTMENTS vs 3-bettor type:
  vs LAG: +1.5%  (LAG 3-bets wide; many bluffs in range to exploit)
  vs NIT: -1.5%  (nit 3-bet = QQ+; cold 4-bet bluffs have 0 fold equity)
  vs FISH: -0.5% (fish 3-bet range odd but often value-heavy)

  STACK DEPTH:
  Short (<60BB):  -0.8% (4-bet commits 35%+ stack; JAM or fold)
  Deep (>120BB):  +0.6% (bluff 4-bets viable; implied odds improve EV)

  SIZING: c4b_bb = threbet_bb * 2.0 + 2BB if OOP (SB/BB)
  JAM when c4b_bb >= 35% of effective stack

DISTINCT FROM:
  cold_4bet_advisor.py:       Situation advice whether to cold 4-bet NOW
  four_bet_range_builder.py:  Full 4-bet range construction with combos
  facing_4bet.py:             How to respond to a 4-bet you face
  fourbet_advisor.py:         General 4-bet advice (not cold-specific)
  THIS MODULE:                Frequency tables; calibration vs villain type/position;
                              optimal cold 4-bet percentage and sizing.
"""

from dataclasses import dataclass, field
from typing import List

BASELINE_COLD_4BET_FREQ: dict = {
    'bb':  0.030,
    'sb':  0.020,
    'mp':  0.015,
    'utg': 0.008,
}

OPENER_POSITION_C4B_MODIFIER: dict = {
    'utg': -0.005,
    'mp':  -0.002,
    'co':   0.000,
    'btn': +0.004,
    'sb':  +0.003,
}

BETTOR_TYPE_C4B_MODIFIER: dict = {
    'fish':            -0.005,
    'nit':             -0.015,
    'reg':              0.000,
    'lag':             +0.015,
    'calling_station': -0.008,
}

OPENER_TYPE_C4B_MODIFIER: dict = {
    'fish':            +0.005,
    'nit':             -0.005,
    'reg':              0.000,
    'lag':             +0.003,
    'calling_station': +0.002,
}

STACK_DEPTH_C4B_MODIFIER: dict = {
    'short':  -0.008,
    'medium':  0.000,
    'deep':   +0.006,
}

STACK_DEPTH_THRESHOLDS: dict = {
    'short':  60.0,
    'medium': 120.0,
}

VALUE_COMBO_APPROX_BY_POSITION: dict = {
    'bb':  16,
    'sb':  16,
    'mp':  16,
    'utg': 10,
}

JAM_C4BET_THRESHOLD: float = 0.35
C4BET_SIZING_MULTIPLIER: float = 2.0
OOP_C4BET_BONUS_BB: float = 2.0
OOP_POSITIONS = {'sb', 'bb'}


def _stack_depth_category(stack_bb: float) -> str:
    if stack_bb <= STACK_DEPTH_THRESHOLDS['short']:
        return 'short'
    if stack_bb <= STACK_DEPTH_THRESHOLDS['medium']:
        return 'medium'
    return 'deep'


def _optimal_c4b_freq(
    position: str,
    opener_position: str,
    bettor_type: str,
    opener_type: str,
    stack_bb: float,
) -> float:
    base = BASELINE_COLD_4BET_FREQ.get(position, 0.015)
    bettor_adj = BETTOR_TYPE_C4B_MODIFIER.get(bettor_type, 0.0)
    opener_adj = OPENER_TYPE_C4B_MODIFIER.get(opener_type, 0.0)
    opener_pos_adj = OPENER_POSITION_C4B_MODIFIER.get(opener_position, 0.0)
    depth_cat = _stack_depth_category(stack_bb)
    depth_adj = STACK_DEPTH_C4B_MODIFIER.get(depth_cat, 0.0)
    return round(max(0.0, min(0.08, base + bettor_adj + opener_adj + opener_pos_adj + depth_adj)), 4)


def _c4b_size_bb(threbet_bb: float, position: str, stack_bb: float) -> float:
    oop_bonus = OOP_C4BET_BONUS_BB if position in OOP_POSITIONS else 0.0
    return round(min(stack_bb, threbet_bb * C4BET_SIZING_MULTIPLIER + oop_bonus), 1)


def _c4b_action(c4b_bb: float, stack_bb: float) -> str:
    if c4b_bb / max(stack_bb, 1.0) >= JAM_C4BET_THRESHOLD:
        return 'JAM_PREFERRED'
    return 'STANDARD_COLD_4BET'


@dataclass
class Cold4BetFrequencyResult:
    position: str
    opener_position: str
    bettor_type: str
    opener_type: str
    stack_bb: float
    threbet_bb: float

    stack_depth_category: str
    optimal_c4b_freq: float
    optimal_c4b_bb: float
    c4b_action: str
    value_combos_approx: int

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_cold_4bet_frequency(
    position: str = 'bb',
    opener_position: str = 'btn',
    bettor_type: str = 'reg',
    opener_type: str = 'reg',
    stack_bb: float = 100.0,
    threbet_bb: float = 12.0,
) -> Cold4BetFrequencyResult:
    """
    Calculate cold 4-bet frequency and sizing.

    Args:
        position:        Hero's position ('bb','sb','mp','utg')
        opener_position: Original raiser's position ('utg','mp','co','btn','sb')
        bettor_type:     Villain who 3-bet ('fish','nit','reg','lag','calling_station')
        opener_type:     Villain who opened ('fish','nit','reg','lag','calling_station')
        stack_bb:        Effective stack in BB
        threbet_bb:      Size of villain's 3-bet in BB

    Returns:
        Cold4BetFrequencyResult
    """
    depth_cat = _stack_depth_category(stack_bb)
    freq = _optimal_c4b_freq(position, opener_position, bettor_type, opener_type, stack_bb)
    c4b_bb = _c4b_size_bb(threbet_bb, position, stack_bb)
    action = _c4b_action(c4b_bb, stack_bb)
    value_combos = VALUE_COMBO_APPROX_BY_POSITION.get(position, 16)
    commitment_pct = c4b_bb / max(stack_bb, 1.0)

    verdict = (
        f'[C4B {position}|op={opener_position}|3b={bettor_type}] '
        f'freq={freq:.1%} c4b={c4b_bb:.1f}BB action={action}'
    )

    reasoning = (
        f'Cold 4-bet from {position} vs {opener_position} open + {bettor_type} 3-bet: '
        f'base={BASELINE_COLD_4BET_FREQ.get(position, 0.015):.1%} '
        f'bettor_adj={BETTOR_TYPE_C4B_MODIFIER.get(bettor_type, 0):+.1%} '
        f'opener_adj={OPENER_TYPE_C4B_MODIFIER.get(opener_type, 0):+.1%} '
        f'depth_adj={STACK_DEPTH_C4B_MODIFIER.get(depth_cat, 0):+.1%}. '
        f'Final freq={freq:.1%}. c4b={threbet_bb:.1f}*{C4BET_SIZING_MULTIPLIER}+oop={c4b_bb:.1f}BB '
        f'({commitment_pct:.0%} of stack). Action={action}.'
    )

    tips = []

    tips.append(
        f'Cold 4-bet from {position}: optimal {freq:.1%} '
        f'(~{value_combos} value combos QQ+/AK + Axs/KQs bluffs with blockers). '
        f'{"JAM -- c4b commits " + f"{commitment_pct:.0%}" + " of stack; no room for standard raise" if action == "JAM_PREFERRED" else f"Standard c4b to {c4b_bb:.1f}BB ({commitment_pct:.0%} stack). Stay polar: value + blockers only."}.'
    )

    if bettor_type == 'lag':
        tips.append(
            f'LAG 3-bettor: raise c4b to {freq:.1%}. '
            f'LAG 3-bets 15-20%+ of hands -- many bluffs to exploit. '
            f'Cold 4-bet folds out bluffs and gets value called by medium holdings. '
            f'Add A2s-A5s, KQs as c4b bluffs (blocker to continuing range).'
        )
    elif bettor_type == 'nit':
        tips.append(
            f'NIT 3-bettor: restrict c4b to {freq:.1%}. '
            f'Nit 3-bet range is QQ+/AK only; bluff c4b has near-zero fold equity. '
            f'Only cold 4-bet KK+ and consider folding AK vs nit 3-bet from early position. '
            f'If nit calls your c4b, reassess -- they have AA/KK almost always.'
        )
    else:
        tips.append(
            f'vs {bettor_type} 3-bettor: c4b {freq:.1%}. '
            f'Value: QQ+, AK ({value_combos} combos). Bluffs: A2s-A5s, KQs. '
            f'Stack depth {depth_cat} ({stack_bb:.0f}BB): '
            f'{"lean JAM/fold; standard c4b is too committing" if depth_cat == "short" else "full c4b range viable" if depth_cat == "deep" else "standard c4b range"}. '
            f'OOP bonus {"applied (+2BB)" if position in OOP_POSITIONS else "not applied (IP)"}.'
        )

    return Cold4BetFrequencyResult(
        position=position,
        opener_position=opener_position,
        bettor_type=bettor_type,
        opener_type=opener_type,
        stack_bb=stack_bb,
        threbet_bb=threbet_bb,
        stack_depth_category=depth_cat,
        optimal_c4b_freq=freq,
        optimal_c4b_bb=c4b_bb,
        c4b_action=action,
        value_combos_approx=value_combos,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def c4b_one_liner(r: Cold4BetFrequencyResult) -> str:
    return (
        f'[C4B {r.position}|{r.bettor_type}] '
        f'freq={r.optimal_c4b_freq:.1%} c4b={r.optimal_c4b_bb:.1f}BB {r.c4b_action}'
    )
