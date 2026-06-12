"""
Suited Connector Strategy Guide (suited_connector_strategy_guide.py)

Comprehensive guide for playing suited connectors: when to flat, 3-bet bluff,
fold, and how to exploit implied odds in various stack depths and positions.

THEORY:
  SUITED CONNECTOR (SC) PROFILE:
  Hands like 87s, 76s, 65s, 98s -- suited with connected ranks.
  Strengths: (1) Implied odds (make straights, flushes, two pair)
             (2) Good bluffing hands (fold equity + equity when called)
             (3) Disguised hands (hard to put on specific holding)
  Weaknesses: (1) Vulnerable before improving
               (2) Dominated by overpairs multiway
               (3) Require deep stacks for implied odds

  STACK DEPTH REQUIREMENT:
  SC need deep stacks to realize implied odds:
  Minimum 50BB for marginal profitability
  Prefer 100BB+ for full implied odds

  PREFLOP ACTION:
  Fold: <50BB stacks, OOP vs nit, 5+ players likely in pot
  Flat: IP vs loose opener, 100BB stacks, favorable position
  3-bet bluff: vs nit folder, high-fold-to-3bet villains, IP position only

  POSTFLOP PLAYABILITY:
  Miss flop (~60% of flops): bluff or check-fold
  Flop draw (flush/straight, ~40%): continue; check-raise or call
  Flop pair+: thin value depending on board

  REQUIRED STACK-TO-CALL RATIO FOR SC PROFITABILITY:
  SC need roughly 12:1 stack-to-call to be profitable (comparable to set mining)
  Higher ranks (T9s, J8s): slightly lower ratio needed (more playability)

DISTINCT FROM:
  set_mining_guide.py:          Pocket pair call-for-set strategy
  cold_call_frequency_guide.py: General cold call frequency
  draw_advisor.py:              Drawing hand advice
  THIS MODULE:                  SC-specific strategy: preflop action selection,
                                profitability conditions, postflop lines.
"""

from dataclasses import dataclass, field
from typing import List

SC_SET_HIT_LIKE_PROB: float = 0.118
SC_FLUSH_DRAW_PROB: float = 0.118
SC_STRAIGHT_DRAW_PROB: float = 0.320
SC_MISS_FLOP_PROB: float = 0.590

MINIMUM_STACK_CALL_RATIO_SC: float = 12.0

SC_RANK_PLAYABILITY_BONUS: dict = {
    'high':   +1.0,    # T9s, JTs (rank 9-11): more top pair combos
    'medium': +0.0,    # 87s, 98s (rank 7-8): standard
    'low':    -1.5,    # 54s, 65s (rank 4-6): lower playability
    'micro':  -3.0,    # 32s, 43s (rank 2-3): marginal at best
}

VILLAIN_SC_FLAT_MODIFIER: dict = {
    'fish':            +0.08,
    'calling_station': +0.04,
    'nit':             -0.06,
    'lag':             -0.03,
    'rec':             +0.04,
    'reg':              0.00,
}

POSITION_SC_FLAT_MODIFIER: dict = {
    'btn': +0.08,
    'co':  +0.04,
    'hj':  +0.00,
    'mp':  -0.04,
    'utg': -0.08,
    'sb':  -0.06,
    'bb':  +0.06,
}

SC_3BET_BLUFF_THRESHOLD_FOLD_TO_3BET: float = 0.62
SC_MINIMUM_STACK_BB: float = 50.0


def _sc_rank_category(low_rank: int) -> str:
    if low_rank >= 9:
        return 'high'
    if low_rank >= 7:
        return 'medium'
    if low_rank >= 4:
        return 'low'
    return 'micro'


def _flat_frequency(
    position: str,
    villain_type: str,
    stack_bb: float,
    n_callers: int,
) -> float:
    if stack_bb < SC_MINIMUM_STACK_BB:
        return 0.0
    base = 0.40
    pos_adj = POSITION_SC_FLAT_MODIFIER.get(position, 0.0)
    vil_adj = VILLAIN_SC_FLAT_MODIFIER.get(villain_type, 0.0)
    stack_adj = (min(stack_bb, 200.0) - 100.0) * 0.002
    caller_adj = n_callers * 0.06
    freq = base + pos_adj + vil_adj + stack_adj + caller_adj
    return round(min(0.80, max(0.0, freq)), 3)


def _sc_preflop_action(
    position: str,
    villain_type: str,
    stack_bb: float,
    fold_to_3bet: float,
    n_callers: int,
) -> str:
    if stack_bb < SC_MINIMUM_STACK_BB:
        return 'FOLD_INSUFFICIENT_STACKS'
    flat_freq = _flat_frequency(position, villain_type, stack_bb, n_callers)
    if flat_freq <= 0.15:
        return 'FOLD_WEAK_SPOT'
    if fold_to_3bet >= SC_3BET_BLUFF_THRESHOLD_FOLD_TO_3BET and position in ('btn', 'co'):
        return 'THREE_BET_BLUFF_IP'
    if flat_freq >= 0.50:
        return 'FLAT_PREFERRED'
    return 'FLAT_MARGINAL'


def _stack_call_ratio(stack_bb: float, call_bb: float) -> float:
    if call_bb <= 0:
        return 0.0
    return round(stack_bb / call_bb, 1)


@dataclass
class SuitedConnectorStrategyResult:
    low_rank: int
    position: str
    villain_type: str
    stack_bb: float
    call_bb: float
    fold_to_3bet: float
    n_callers: int

    rank_category: str
    flat_frequency: float
    preflop_action: str
    stack_call_ratio: float
    profitability_verdict: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_suited_connector_strategy(
    low_rank: int = 7,
    position: str = 'btn',
    villain_type: str = 'reg',
    stack_bb: float = 100.0,
    call_bb: float = 3.0,
    fold_to_3bet: float = 0.57,
    n_callers: int = 0,
) -> SuitedConnectorStrategyResult:
    """
    Evaluate suited connector preflop strategy.

    Args:
        low_rank:      Lower rank of connector (2=2s, 7=7s in 87s, 9=9s in T9s)
        position:      Hero position ('btn','co','hj','mp','utg','sb','bb')
        villain_type:  Villain type ('fish','nit','lag','reg', etc.)
        stack_bb:      Effective stack in BB
        call_bb:       Call size in BB (open raise size)
        fold_to_3bet:  Villain's fold-to-3bet stat (for 3-bet bluff opportunity)
        n_callers:     Number of players who already called (multiway opportunity)

    Returns:
        SuitedConnectorStrategyResult
    """
    rank_cat = _sc_rank_category(low_rank)
    flat_freq = _flat_frequency(position, villain_type, stack_bb, n_callers)
    action = _sc_preflop_action(position, villain_type, stack_bb, fold_to_3bet, n_callers)
    sc_ratio = _stack_call_ratio(stack_bb, call_bb)
    profitable = sc_ratio >= MINIMUM_STACK_CALL_RATIO_SC
    profit_verdict = f'PROFITABLE_SC_SPOT(ratio={sc_ratio})' if profitable else f'MARGINAL_SC_SPOT(need{MINIMUM_STACK_CALL_RATIO_SC:.0f}:1,have{sc_ratio:.0f}:1)'

    verdict = (
        f'[SC low_rank={low_rank}({rank_cat})|{position}|{villain_type}] '
        f'action={action} ratio={sc_ratio} {profit_verdict}'
    )

    reasoning = (
        f'SC strategy ({low_rank}x+1-suited, {rank_cat}): '
        f'flat_freq={flat_freq:.0%} (pos_adj={POSITION_SC_FLAT_MODIFIER.get(position, 0):+.0%} '
        f'vil_adj={VILLAIN_SC_FLAT_MODIFIER.get(villain_type, 0):+.0%}). '
        f'Stack={stack_bb:.0f}BB call={call_bb:.1f}BB ratio={sc_ratio} '
        f'(need>={MINIMUM_STACK_CALL_RATIO_SC:.0f}). Action={action}.'
    )

    tips = []

    tips.append(
        f'Suited connector ({low_rank}x+1-suited, {rank_cat} rank): {action}. '
        f'Stack/call ratio={sc_ratio} (need {MINIMUM_STACK_CALL_RATIO_SC:.0f}:1). '
        f'{profit_verdict}. '
        f'{"Profitable SC flat: depth allows implied odds" if profitable else "Insufficient stack depth for SC -- fold or 3-bet only"}.'
    )

    if action == 'THREE_BET_BLUFF_IP':
        tips.append(
            f'3-BET BLUFF SC: villain fold-to-3bet={fold_to_3bet:.0%} > {SC_3BET_BLUFF_THRESHOLD_FOLD_TO_3BET:.0%}. '
            f'SC has good blocker/equity properties as 3-bet bluff from {position}. '
            f'If called: flop draw equity + fold equity. Use A5s/76s/87s type hands.'
        )
    elif action in ('FLAT_PREFERRED', 'FLAT_MARGINAL'):
        tips.append(
            f'FLAT SC from {position}: implied odds strategy. '
            f'Miss flop {SC_MISS_FLOP_PROB:.0%}: check-fold or bluff vs nit/tight range. '
            f'Hit draw {SC_FLUSH_DRAW_PROB+SC_STRAIGHT_DRAW_PROB:.0%}: '
            f'semi-bluff; continue based on draw equity. '
            f'Multiway ({n_callers} callers): {"great implied odds" if n_callers >= 1 else "heads-up; realize equity carefully"}.'
        )
    elif 'FOLD' in action:
        tips.append(
            f'FOLD SC: {action}. '
            f'{"Stack too shallow for implied odds" if stack_bb < SC_MINIMUM_STACK_BB else "Position/villain unfavorable for SC flat"}. '
            f'SC profitability requires deep stacks (>={SC_MINIMUM_STACK_BB:.0f}BB) and IP play.'
        )

    if n_callers >= 2:
        tips.append(
            f'{n_callers} callers already in: multiway pot. '
            f'SC implied odds INCREASE multiway: more players = bigger pots when SC hits. '
            f'Flat with SC even OOP if stacks deep enough ({sc_ratio:.0f}:1 vs {MINIMUM_STACK_CALL_RATIO_SC:.0f}:1 needed).'
        )

    return SuitedConnectorStrategyResult(
        low_rank=low_rank,
        position=position,
        villain_type=villain_type,
        stack_bb=stack_bb,
        call_bb=call_bb,
        fold_to_3bet=fold_to_3bet,
        n_callers=n_callers,
        rank_category=rank_cat,
        flat_frequency=flat_freq,
        preflop_action=action,
        stack_call_ratio=sc_ratio,
        profitability_verdict=profit_verdict,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def scs_one_liner(r: SuitedConnectorStrategyResult) -> str:
    return (
        f'[SC rank={r.low_rank}({r.rank_category})|{r.position}|{r.villain_type}] '
        f'{r.preflop_action} ratio={r.stack_call_ratio}'
    )
