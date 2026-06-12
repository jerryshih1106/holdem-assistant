"""
Set Mining Guide (set_mining_guide.py)

Set mining = calling preflop with pocket pairs hoping to flop a set (trips).
Set hits occur ~11.8% of the time (once per 8.5 flops). Profitability requires
sufficient implied odds to win back the call cost when you DO hit.

THEORY:
  SET MINING MATH:
  Probability of flopping set = 1 - C(48,3)/C(50,3) = ~11.76%
  Break-even implied odds: need to win ~8.5x the call when you hit a set.
  Rule of 5/10: If stack-to-call ratio < 5, fold. 5-10: marginal. 10+: call.

  IMPLIED ODDS SOURCES:
  1. Villain's stack size (must be able to pay you off)
  2. Villain type (fish/station pay off sets generously; nit may check-fold)
  3. Position (IP: easier to extract; OOP: sets often check-raise opportunities)
  4. Pair rank: higher pairs have playability beyond set-mining (overpairs)

  PAIR RANK CONSIDERATIONS:
  22-44: Pure set-mining only; fold if implied odds insufficient
  55-77: Occasional overpair value on low boards
  88-99: Frequently overpair on low boards; more playability
  TT-QQ: Strong overpairs; often 3-bet instead of set-mine

  WHEN NOT TO SET MINE:
  - Stack-to-call ratio < 8 (IP) or < 10 (OOP)
  - Villain is a nit (won't stack off with lower sets/overpairs)
  - Multiway pot (multiple callers reduce implied odds significantly)
  - Effective stack too small (need opponent stack >= 8.5x call to break even)

DISTINCT FROM:
  implied_odds_positional_adjustment.py: General implied odds for draws
  preflop_all_in_guide.py:              Short stack push/fold preflop
  THIS MODULE:                          SET MINING specifically; pocket pairs;
                                        when stack-to-call ratio justifies calling.
"""

from dataclasses import dataclass, field
from typing import List


SET_HIT_PROBABILITY: float = 0.118

MINIMUM_STACK_CALL_RATIO: dict = {
    'ip':  8.0,
    'oop': 10.0,
}

VILLAIN_IMPLIED_ODDS_MULTIPLIER: dict = {
    'fish':            0.80,
    'calling_station': 0.72,
    'rec':             0.95,
    'nit':             1.60,
    'lag':             1.10,
    'reg':             1.00,
}

PAIR_RANK_BONUS: dict = {
    'micro':   0.00,
    'low':     0.04,
    'medium':  0.10,
    'high':    0.18,
}

PAIR_RANK_GROUPS: dict = {
    (2, 4):   'micro',
    (5, 7):   'low',
    (8, 9):   'medium',
    (10, 13): 'high',
}

MULTIWAY_IMPLIED_PENALTY: dict = {
    0: 0.00,
    1: -0.08,
    2: -0.15,
    3: -0.22,
}


def _pair_rank_group(pair_rank: int) -> str:
    for (lo, hi), group in PAIR_RANK_GROUPS.items():
        if lo <= pair_rank <= hi:
            return group
    return 'micro'


def _required_stack_call_ratio(position: str, villain_type: str, extra_callers: int) -> float:
    base = MINIMUM_STACK_CALL_RATIO.get(position, 10.0)
    vil_mult = VILLAIN_IMPLIED_ODDS_MULTIPLIER.get(villain_type, 1.0)
    mw_pen = MULTIWAY_IMPLIED_PENALTY.get(min(extra_callers, 3), 0.0)
    return round(base * vil_mult * (1.0 + mw_pen), 2)


def _set_mining_decision(
    effective_stack_bb: float,
    call_bb: float,
    required_ratio: float,
    pair_rank: int,
    position: str,
) -> str:
    actual_ratio = effective_stack_bb / call_bb if call_bb > 0 else 0.0
    group = _pair_rank_group(pair_rank)
    bonus = PAIR_RANK_BONUS.get(group, 0.0)

    if actual_ratio >= required_ratio * (1.0 - bonus):
        return 'CALL_SET_MINE'
    if actual_ratio >= required_ratio * 0.75 and group in ('medium', 'high'):
        return 'CALL_MARGINAL_PLAYABILITY'
    if actual_ratio >= required_ratio * 0.60:
        return 'MARGINAL_FOLD'
    return 'FOLD_INSUFFICIENT_IMPLIED'


@dataclass
class SetMiningResult:
    pair_rank: int
    position: str
    villain_type: str
    effective_stack_bb: float
    call_bb: float
    extra_callers: int

    pair_group: str
    required_ratio: float
    actual_ratio: float
    decision: str
    set_hit_prob: float
    breakeven_win_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_set_mining(
    pair_rank: int = 7,
    position: str = 'ip',
    villain_type: str = 'reg',
    effective_stack_bb: float = 100.0,
    call_bb: float = 3.0,
    extra_callers: int = 0,
) -> SetMiningResult:
    """
    Evaluate set mining profitability for pocket pairs preflop.

    Args:
        pair_rank:           Pair rank 2-13 (2=22 ... 13=KK)
        position:            Hero position ('ip','oop')
        villain_type:        Villain type ('fish','rec','nit','lag','reg')
        effective_stack_bb:  Effective stack in BB (min of hero/villain)
        call_bb:             Call size in BB (open raise size)
        extra_callers:       Extra callers in the pot (0=HU, 1=3-way, ...)

    Returns:
        SetMiningResult
    """
    group = _pair_rank_group(pair_rank)
    required = _required_stack_call_ratio(position, villain_type, extra_callers)
    actual = round(effective_stack_bb / call_bb, 2) if call_bb > 0 else 0.0
    decision = _set_mining_decision(effective_stack_bb, call_bb, required, pair_rank, position)
    breakeven = round(call_bb / SET_HIT_PROBABILITY, 1)

    verdict = (
        f'[SM pair={pair_rank}|{position}|{villain_type}] '
        f'ratio={actual:.1f} (need {required:.1f}) decision={decision}'
    )

    reasoning = (
        f'Set mining: pair rank {pair_rank} ({group}) {position}. '
        f'Effective stack={effective_stack_bb:.0f}BB, call={call_bb:.1f}BB. '
        f'Stack/call ratio={actual:.1f} vs required {required:.1f}. '
        f'Break-even win={breakeven:.0f}BB per pot (need to win {1/SET_HIT_PROBABILITY:.1f}x call). '
        f'Decision: {decision}.'
    )

    tips = []

    tips.append(
        f'SET MINING: pair {pair_rank} ({group}), {position}. '
        f'Stack/call={actual:.1f} vs required {required:.1f}. '
        f'{"Call -- sufficient implied odds for set mining." if "CALL" in decision else "Fold -- insufficient implied odds."}'
        f' Set hits {SET_HIT_PROBABILITY:.0%} of flops.'
    )

    tips.append(
        f'BREAK-EVEN: Need to win {breakeven:.0f}BB when you hit your set. '
        f'Effective stack={effective_stack_bb:.0f}BB ({"enough to cover break-even" if effective_stack_bb >= breakeven else "INSUFFICIENT -- even perfect play cannot break even"}).'
        f' Villain ({villain_type}) implied odds multiplier: {VILLAIN_IMPLIED_ODDS_MULTIPLIER.get(villain_type, 1.0):.2f}x.'
    )

    if group in ('micro', 'low'):
        tips.append(
            f'PURE SET-MINING ({group} pair): Must have correct implied odds to call. '
            f'No significant overpair value. '
            f'Fold quickly when flop misses; do not slowplay sets (build pot immediately).'
        )
    elif group in ('medium', 'high'):
        tips.append(
            f'PLAYABILITY BONUS ({group} pair): May call even slightly below required ratio. '
            f'Overpair value on low boards adds {PAIR_RANK_BONUS[group]:.0%} bonus to call threshold. '
            f'Can also bet/raise for value without hitting a set on many boards.'
        )

    if villain_type == 'nit':
        tips.append(
            f'VS NIT: Required ratio inflated to {required:.1f}x (nit folds draws/overpairs). '
            f'Nit stacks off only with very strong hands -- implied odds reduced. '
            f'Only set mine vs nit if SPR allows you to get stacks in when nit has AA-KK.'
        )

    return SetMiningResult(
        pair_rank=pair_rank,
        position=position,
        villain_type=villain_type,
        effective_stack_bb=effective_stack_bb,
        call_bb=call_bb,
        extra_callers=extra_callers,
        pair_group=group,
        required_ratio=required,
        actual_ratio=actual,
        decision=decision,
        set_hit_prob=SET_HIT_PROBABILITY,
        breakeven_win_bb=breakeven,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sm_one_liner(r: SetMiningResult) -> str:
    return (
        f'[SM pair={r.pair_rank}|{r.position}|{r.villain_type}] '
        f'ratio={r.actual_ratio:.1f}/need={r.required_ratio:.1f} {r.decision}'
    )
