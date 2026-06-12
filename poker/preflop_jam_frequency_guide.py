"""
Preflop Jam Frequency Guide (preflop_jam_frequency_guide.py)

Calibrates when and how often to jam preflop (5-bet shove, 3-bet jam short-stack,
or 4-bet jam) based on effective stack depth, hand strength, and villain tendencies.

THEORY:
  PREFLOP JAM SCENARIOS:
  (1) SHORT STACK JAM (10-30BB): Jam any raise (or open-jam) with good hand.
      Push-fold chart: jam when hand EV > fold EV.
  (2) 3-BET JAM (30-50BB): 3-bet shove instead of 3-bet small.
      Stack too small for 3-bet/fold; commit with strong value range.
  (3) 4-BET JAM (50-100BB): After villain 3-bets, 4-bet jam vs. 4-bet small.
      4-bet jam when: 4-bet size > 35% of stack -> pot committed.
  (4) 5-BET SHOVE (>100BB): After 4-bet, shove QQ+/AK.
      Never 5-bet small; always shove (only premium range).

  JAM HAND THRESHOLDS:
  Stack 10-20BB: jam A2s+, A7o+, any pair, KQs, KJs
  Stack 20-30BB: jam A8+, 99+, KQs, QJs
  Stack 30-40BB: jam TT+, AQs+, AKo (3-bet jam range)
  Stack 40-50BB: jam JJ+, AQs+, AK (pot committed after 3-bet)
  Stack 50-100BB: jam QQ+, AK (4-bet jam range)

  VILLAIN-ADJUSTED JAM RANGE:
  vs nit: jam tighter (nit calls only premiums)
  vs lag: jam tighter (lag 3-bets/4-bets light; still need premium to call off)
  vs fish: jam slightly looser (fish calls too wide; value of jam increases)

DISTINCT FROM:
  pushfold.py:          Push-fold charts for <20BB
  preflop_allin_guide.py: When to go all-in (commitment threshold)
  preflop_allin_ev.py:  EV of going all-in preflop
  THIS MODULE:          HOW OFTEN to jam by stack depth; 3/4/5-bet jam decisions;
                        jam vs 4-bet-small decision at different stack depths.
"""

from dataclasses import dataclass, field
from typing import List

JAM_THRESHOLD_SDV_BY_STACK: dict = {
    'push_fold':    0.42,
    'short_3bet':   0.58,
    'medium_4bet':  0.72,
    'deep_5bet':    0.82,
}

STACK_SCENARIO_THRESHOLDS: dict = {
    'push_fold':  20.0,
    'short_3bet': 40.0,
    'medium_4bet': 80.0,
    'deep_5bet': 999.0,
}

VILLAIN_JAM_ADJUSTMENT: dict = {
    'fish':            -0.04,
    'calling_station': -0.06,
    'nit':             +0.05,
    'lag':             +0.03,
    'rec':             -0.02,
    'reg':              0.00,
}

JAM_FREQUENCY_BY_SCENARIO: dict = {
    'push_fold':    0.35,
    'short_3bet':   0.18,
    'medium_4bet':  0.10,
    'deep_5bet':    0.05,
}

GEOMETRIC_JAM_THRESHOLD: float = 0.35


def _stack_scenario(stack_bb: float) -> str:
    for cat, thresh in STACK_SCENARIO_THRESHOLDS.items():
        if stack_bb <= thresh:
            return cat
    return 'deep_5bet'


def _jam_threshold(stack_bb: float, villain_type: str) -> float:
    scenario = _stack_scenario(stack_bb)
    base = JAM_THRESHOLD_SDV_BY_STACK.get(scenario, 0.72)
    vil_adj = VILLAIN_JAM_ADJUSTMENT.get(villain_type, 0.0)
    return round(min(0.92, max(0.30, base + vil_adj)), 3)


def _jam_decision(hand_sdv: float, threshold: float, stack_bb: float) -> str:
    scenario = _stack_scenario(stack_bb)
    if hand_sdv >= threshold + 0.08:
        return 'JAM_CLEARLY'
    if hand_sdv >= threshold:
        return f'JAM_{scenario.upper()}'
    if hand_sdv >= threshold - 0.05:
        return 'BORDERLINE_JAM_OR_SMALLER'
    return '4BET_SMALL_OR_FOLD'


def _jam_freq(stack_bb: float, villain_type: str) -> float:
    scenario = _stack_scenario(stack_bb)
    base_freq = JAM_FREQUENCY_BY_SCENARIO.get(scenario, 0.10)
    vil_adj = VILLAIN_JAM_ADJUSTMENT.get(villain_type, 0.0) * 0.3
    return round(min(0.60, max(0.02, base_freq - vil_adj)), 3)


@dataclass
class PreflopJamFrequencyResult:
    stack_bb: float
    hand_sdv: float
    villain_type: str
    facing_3bet: bool
    facing_4bet: bool

    stack_scenario: str
    jam_threshold: float
    jam_decision: str
    jam_frequency: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_preflop_jam_frequency(
    stack_bb: float = 50.0,
    hand_sdv: float = 0.72,
    villain_type: str = 'reg',
    facing_3bet: bool = False,
    facing_4bet: bool = False,
) -> PreflopJamFrequencyResult:
    """
    Calibrate preflop jam frequency by stack depth and situation.

    Args:
        stack_bb:    Effective stack in BB
        hand_sdv:    Hero's hand SDV (0-1); proxy for hand strength
        villain_type: Villain type ('fish','nit','lag','reg', etc.)
        facing_3bet:  True if hero opened and villain 3-bet
        facing_4bet:  True if there has been a 4-bet (hero or villain)

    Returns:
        PreflopJamFrequencyResult
    """
    scenario = _stack_scenario(stack_bb)
    threshold = _jam_threshold(stack_bb, villain_type)
    decision = _jam_decision(hand_sdv, threshold, stack_bb)
    freq = _jam_freq(stack_bb, villain_type)

    verdict = (
        f'[PJF stack={stack_bb:.0f}BB|{scenario}|{villain_type}] '
        f'threshold={threshold:.0%}SDV jam_freq={freq:.0%} dec={decision}'
    )

    reasoning = (
        f'Preflop jam freq: stack={stack_bb:.0f}BB ({scenario}). '
        f'base_threshold={JAM_THRESHOLD_SDV_BY_STACK.get(scenario, 0.72):.0%} '
        f'vil_adj={VILLAIN_JAM_ADJUSTMENT.get(villain_type, 0):+.0%}. '
        f'Threshold={threshold:.0%}. Hand SDV={hand_sdv:.0%}. '
        f'Decision={decision}. Base freq={freq:.0%}.'
    )

    tips = []

    tips.append(
        f'Preflop jam at {stack_bb:.0f}BB ({scenario}): jam range threshold SDV>={threshold:.0%}. '
        f'Your hand SDV={hand_sdv:.0%}: {decision}. '
        f'Jam frequency in this scenario: ~{freq:.0%} of preflop spots.'
    )

    if scenario == 'push_fold':
        tips.append(
            f'PUSH-FOLD ({stack_bb:.0f}BB): Open-jam or jam over limps with SDV>={threshold:.0%}. '
            f'Range: A2s+/A7o+/any pair/KQs/KJs. '
            f'Do not open-raise and fold to jam; too many chips committed to fold.'
        )
    elif scenario == 'short_3bet':
        tips.append(
            f'3-BET JAM ({stack_bb:.0f}BB): 3-bet shove vs villain open with SDV>={threshold:.0%}. '
            f'Range: TT+/AQs+/AK. Stack too small for 3-bet/fold; commit with premium. '
            f'vs {villain_type}: {"jam tighter -- nit only calls premium" if villain_type == "nit" else "jam slightly looser -- fish calls wide" if villain_type == "fish" else "standard jam range"}.'
        )
    elif scenario == 'medium_4bet':
        tips.append(
            f'4-BET JAM ({stack_bb:.0f}BB): After villain 3-bets, 4-bet jam with SDV>={threshold:.0%}. '
            f'Range: QQ+/AK. If 4-bet size > {GEOMETRIC_JAM_THRESHOLD:.0%} of stack: always jam (committed). '
            f'4-bet/fold range: JJ/TT/AQs (call off vs only 4-bet jams with QQ+/AK).'
        )
    else:
        tips.append(
            f'5-BET SHOVE ({stack_bb:.0f}BB): After 4-bet, shove QQ+/AK always. '
            f'Never 5-bet small (only makes sense as shove). '
            f'5-bet/fold: QQ sometimes vs nit 4-bet (nit has AA/KK mostly); call KK+/AK.'
        )

    if facing_4bet:
        tips.append(
            f'FACING 4-BET: evaluate stack commitment. '
            f'If remaining stack < {GEOMETRIC_JAM_THRESHOLD:.0%} of pot after calling 4-bet: commit/shove. '
            f'SDV={hand_sdv:.0%} vs threshold={threshold:.0%}: {decision}. '
            f'vs {villain_type}: {"nit 4-bets AA/KK mostly; fold JJ/QQ usually" if villain_type == "nit" else "LAG 4-bets wide; call QQ/AK" if villain_type == "lag" else "standard: call QQ+/AK; fold JJ/AQs"}.'
        )

    return PreflopJamFrequencyResult(
        stack_bb=stack_bb,
        hand_sdv=hand_sdv,
        villain_type=villain_type,
        facing_3bet=facing_3bet,
        facing_4bet=facing_4bet,
        stack_scenario=scenario,
        jam_threshold=threshold,
        jam_decision=decision,
        jam_frequency=freq,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pjf_one_liner(r: PreflopJamFrequencyResult) -> str:
    return (
        f'[PJF {r.stack_bb:.0f}BB|{r.stack_scenario}|{r.villain_type}] '
        f'threshold={r.jam_threshold:.0%} {r.jam_decision}'
    )
