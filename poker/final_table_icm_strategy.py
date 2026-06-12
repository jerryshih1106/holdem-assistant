"""
Final Table ICM Strategy Advisor (final_table_icm_strategy.py)

Provides final table strategy recommendations using full ICM (Malmuth-Harville).
Unlike bubble ICM which focuses on survival, final table ICM requires balancing:
  - Pay jump size (each elimination = significant $)
  - Chip accumulation (need chips to win)
  - Stack-specific aggression levels

ICM EQUITY CALCULATION (Malmuth-Harville):
  P(player_i wins) = chips_i / total_chips
  P(i is 2nd | j won) = chips_i / (total - chips_j)
  P(i is kth | ...) = recursive enumeration

KEY FINAL TABLE DYNAMICS:
  - Short stacks: forced to gamble, ICM says call wider vs huge stacks
  - Medium stacks: most ICM pressure, tighten significantly
  - Chip leaders: most power, can apply ICM pressure; but calling off stack is costly
  - Pay jump magnitude: small jump = accumulate; big jump = survive

STRATEGY MODES:
  chip_leader:       Bully short stacks; avoid marginal flips vs medium stacks
  healthy_stack:     Balanced play; fold marginal spots vs chip leaders
  medium_stack:      ICM caution; avoid flips; look for spots to steal
  short_stack:       Push/fold territory; open-push for fold equity
  micro_stack:       Desperate shove/call; any two cards close to correct

DISTINCT FROM OTHER ICM MODULES:
  icm.py:              Raw Malmuth-Harville equity calculation
  icm_advisor.py:      Bubble pressure
  icm_deal_calculator.py: Deal making at final table
  THIS MODULE:         Live FT strategy — push/call/fold thresholds + pay jump awareness

Usage:
    from poker.final_table_icm_strategy import advise_final_table, FinalTableAdvice, ft_one_liner

    result = advise_final_table(
        hero_chips=45000,
        all_chips=[45000, 80000, 30000, 25000, 20000],
        payouts=[5000, 3000, 1800, 1200, 800],
        hero_index=0,
        blinds_bb=2000,
        hero_hand_rank_pct=0.75,
        situation='push_fold',
    )
    print(ft_one_liner(result))
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple
from functools import lru_cache


# --------------------------------------------------------------------------
# Malmuth-Harville ICM (standalone, no import dependency)
# --------------------------------------------------------------------------

def _icm_equity(chips: List[int], prizes: List[float]) -> List[float]:
    """Malmuth-Harville ICM equity for each player."""
    n = len(chips)
    equities = [0.0] * n

    def recurse(remaining_chips: List[int], remaining_prizes: List[float], prob: float):
        if not remaining_prizes or all(c == 0 for c in remaining_chips):
            return
        prize = remaining_prizes[0]
        rest = remaining_prizes[1:]
        total_r = sum(remaining_chips)
        if total_r == 0:
            return
        for i, c in enumerate(remaining_chips):
            if c == 0:
                continue
            p_win = c / total_r
            equities[i] += prob * p_win * prize
            if rest:
                new_chips = list(remaining_chips)
                new_chips[i] = 0
                recurse(new_chips, rest, prob * p_win)

    recurse(list(chips), list(prizes), 1.0)
    return equities


# --------------------------------------------------------------------------
# Stack classification
# --------------------------------------------------------------------------

def _stack_regime(hero_chips: int, avg_chips: int, bb: int) -> str:
    """Classify hero's stack relative to average and blinds."""
    m_ratio = hero_chips / max(bb * 3, 1)   # simplified M (3 streets = ~3BB/orbit 6-handed)
    stack_ratio = hero_chips / max(avg_chips, 1)

    if stack_ratio >= 2.0:
        return 'chip_leader'
    elif stack_ratio >= 1.3:
        return 'healthy_stack'
    elif stack_ratio >= 0.7 and m_ratio >= 15:
        return 'medium_stack'
    elif m_ratio >= 8:
        return 'short_stack'
    else:
        return 'micro_stack'


def _push_equity_threshold(
    regime: str,
    hero_chips: int,
    villain_chips: int,
    total_chips: int,
    prizes: List[float],
    hero_index: int,
    n_players: int,
) -> float:
    """
    Minimum equity needed to profitably push (ICM-adjusted).
    Returns a fraction (0.0-1.0).
    """
    # Chip EV baseline: pot_odds style
    # If we push and villain calls: we win/lose effective_stack chips
    eff = min(hero_chips, villain_chips)
    pot = eff * 2   # rough pot size
    chip_threshold = eff / pot  # = 0.50 (50% equity for even chip EV)

    # ICM adjustment: medium stacks pay more penalty for busting
    if regime == 'chip_leader':
        icm_adj = 0.02    # need slightly more (busting opponent matters less to us)
    elif regime == 'healthy_stack':
        icm_adj = 0.04
    elif regime == 'medium_stack':
        icm_adj = 0.06
    elif regime == 'short_stack':
        icm_adj = 0.03    # desperate; near Nash (less ICM caution)
    else:  # micro
        icm_adj = 0.01    # almost any two cards

    # More players = tighter (more people to bust out past)
    player_adj = max(0, (n_players - 3)) * 0.01

    return round(min(0.65, chip_threshold + icm_adj + player_adj), 3)


def _call_equity_threshold(
    regime: str,
    n_players: int,
    prizes: List[float],
) -> float:
    """Minimum equity to call an all-in at final table (ICM-adjusted)."""
    # Calling is WORSE than pushing: opponent has initiative, hero's range is transparent
    # ICM says: when calling, need MORE equity than pushing (can't fold if it goes badly)
    base = 0.50

    if regime == 'chip_leader':
        icm_adj = 0.03
    elif regime == 'healthy_stack':
        icm_adj = 0.06
    elif regime == 'medium_stack':
        # Pay jumps are most valuable here; calling for chips risks ladder spots
        next_jump_mult = 1.0
        if len(prizes) >= 2:
            next_jump = prizes[-2] - prizes[-1]   # next pay jump
            avg_prize = sum(prizes) / len(prizes)
            next_jump_mult = min(2.0, next_jump / avg_prize * 3)
        icm_adj = 0.06 + next_jump_mult * 0.02
    elif regime == 'short_stack':
        icm_adj = 0.03
    else:
        icm_adj = 0.01

    player_adj = max(0, (n_players - 3)) * 0.015

    return round(min(0.68, base + icm_adj + player_adj), 3)


def _steal_recommendation(regime: str, n_players: int, hand_rank: float) -> str:
    """How aggressively to steal at the final table."""
    if regime == 'chip_leader':
        return f'STEAL AGGRESSIVELY: Chip leader can apply maximum ICM pressure. Open 40-50% from BTN, 30% from CO. Short stacks cannot call without premium.'
    elif regime == 'healthy_stack':
        return f'STEAL SELECTIVELY: Healthy stack - open 30-40% from BTN. Avoid marginal spots vs chip leader. Target short stacks (they cannot call profitably).'
    elif regime == 'medium_stack':
        return f'STEAL CAUTIOUSLY: Medium stack has most ICM pressure. Open 25-35% from BTN. Avoid big confrontations with medium stacks. Look for spots to chip up vs micro stacks.'
    elif regime == 'short_stack':
        return f'PUSH OR FOLD: Short stack needs to shove from BTN/CO/SB with any two cards >= 30% equity. Stop open-folding marginal hands - shove instead.'
    else:
        return f'DESPERATE SHOVE: Micro stack must gamble. Shove any two cards from any position. Any fold equity is gravy. Standard survival strategy does not apply.'


@dataclass
class FinalTableAdvice:
    # Inputs
    hero_chips: int
    hero_index: int
    n_players: int
    payouts: List[float]
    blinds_bb: int

    # ICM analysis
    icm_equities: List[float]       # ICM equity ($) for each player
    hero_icm_equity: float
    avg_stack: int
    hero_stack_pct: float           # hero chips / total chips

    # Stack classification
    stack_regime: str               # chip_leader/healthy_stack/medium_stack/short_stack/micro_stack
    m_ratio: float                  # hero chips / (3 * BB) — approximate M

    # Thresholds
    push_equity_threshold: float    # min equity to push profitably
    call_equity_threshold: float    # min equity to call all-in
    hand_rank_push_threshold: float # min hand rank to push (for this stack)

    # Pay jump info
    next_prize: float               # prize for surviving one more elimination
    current_prize: float            # current floor (all remaining players get at least this)
    next_pay_jump_value: float      # $ value of surviving to next prize spot

    # Strategy
    steal_advice: str
    push_fold_note: str
    calling_note: str

    # Situation-specific
    situation: str      # 'push_fold' / 'normal' / 'call_decision'
    hand_rank_pct: float
    action_recommendation: str  # 'push' / 'call' / 'fold'
    action_reasoning: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_final_table(
    hero_chips: int = 45000,
    all_chips: List[int] = None,
    payouts: List[float] = None,
    hero_index: int = 0,
    blinds_bb: int = 2000,
    hero_hand_rank_pct: float = 0.75,
    situation: str = 'normal',   # 'push_fold', 'normal', 'call_decision'
    villain_push_chips: int = 0,
) -> 'FinalTableAdvice':
    """
    Advise on final table ICM strategy.

    Args:
        hero_chips:          Hero's current chip count
        all_chips:           All players' chip counts (including hero)
        payouts:             Prize payouts [1st, 2nd, 3rd, ...] in order
        hero_index:          Hero's index in all_chips list
        blinds_bb:           Current big blind size
        hero_hand_rank_pct:  Hero's hand strength (0-1)
        situation:           'push_fold' / 'normal' / 'call_decision'
        villain_push_chips:  Villain's stack if they shoved (for call decisions)

    Returns:
        FinalTableAdvice
    """
    if all_chips is None:
        all_chips = [45000, 80000, 30000, 25000, 20000]
    if payouts is None:
        payouts = [5000, 3000, 1800, 1200, 800]

    n = len(all_chips)
    total_chips = sum(all_chips)
    avg_stack = total_chips // n

    # Compute ICM equities
    icm_eq = _icm_equity(all_chips, list(payouts[:n]))
    hero_icm = icm_eq[hero_index]

    m_ratio = hero_chips / max(blinds_bb * 3, 1)
    regime = _stack_regime(hero_chips, avg_stack, blinds_bb)
    hero_stack_pct = hero_chips / total_chips

    # Pay jump info
    sorted_payouts = sorted(payouts, reverse=True)
    hero_position_guess = max(0, n - int(hero_stack_pct * n) - 1)
    current_prize = sorted_payouts[min(n - 1, len(sorted_payouts) - 1)]
    next_prize = sorted_payouts[max(0, min(n - 2, len(sorted_payouts) - 2))]
    next_pay_jump = next_prize - current_prize

    push_thresh = _push_equity_threshold(
        regime, hero_chips, avg_stack, total_chips, payouts, hero_index, n
    )
    call_thresh = _call_equity_threshold(regime, n, payouts)

    # Hand rank threshold for pushing: ~60-75% depending on regime
    push_rank_thresh = {
        'chip_leader': 0.35,
        'healthy_stack': 0.45,
        'medium_stack': 0.55,
        'short_stack': 0.65,
        'micro_stack': 0.75,
    }.get(regime, 0.50)

    steal_advice = _steal_recommendation(regime, n, hero_hand_rank_pct)

    # Action recommendation
    if situation == 'push_fold':
        if hero_hand_rank_pct >= push_rank_thresh:
            action_rec = 'push'
            action_reason = f'Hand ({hero_hand_rank_pct:.0%}) meets push threshold ({push_rank_thresh:.0%}) for {regime}'
        else:
            action_rec = 'fold'
            action_reason = f'Hand ({hero_hand_rank_pct:.0%}) below push threshold ({push_rank_thresh:.0%}); fold to preserve chips'
    elif situation == 'call_decision':
        # Estimate equity vs villain's shove range
        est_eq = 0.35 + hero_hand_rank_pct * 0.35   # simplified
        if est_eq >= call_thresh:
            action_rec = 'call'
            action_reason = f'Estimated equity ({est_eq:.0%}) >= call threshold ({call_thresh:.0%})'
        elif est_eq >= call_thresh - 0.04:
            action_rec = 'call'
            action_reason = f'Marginal call: equity {est_eq:.0%} slightly below {call_thresh:.0%} threshold but acceptable'
        else:
            action_rec = 'fold'
            action_reason = f'Fold: equity ({est_eq:.0%}) below ICM-adjusted call threshold ({call_thresh:.0%})'
    else:  # normal
        action_rec = 'play_standard'
        action_reason = f'{regime}: {steal_advice[:60]}'

    push_fold_note = (
        f'PUSH/FOLD: Stack={hero_chips//1000}k BB={blinds_bb//1000}k M={m_ratio:.1f}. '
        f'Min push rank: {push_rank_thresh:.0%} (hand needs to be in top {100-int(push_rank_thresh*100)}%). '
        f'{"Current hand qualifies." if hero_hand_rank_pct >= push_rank_thresh else "Current hand does NOT qualify."}'
    )

    calling_note = (
        f'CALLING: ICM-adjusted call threshold = {call_thresh:.0%} equity. '
        f'Calling is riskier than pushing (cannot fold midway). '
        f'Add 4-6% above chip-even equity ({push_thresh:.0%}) before calling off.'
    )

    reasoning = (
        f'FT {n}-handed: hero={hero_chips//1000}k chips ({hero_stack_pct:.0%} of total). '
        f'ICM equity=${hero_icm:.0f}. Regime={regime} M={m_ratio:.1f}. '
        f'Payout floor=${current_prize:.0f} next jump=${next_pay_jump:.0f}. '
        f'Push threshold={push_thresh:.0%} call threshold={call_thresh:.0%}. '
        f'Situation={situation}: {action_rec}.'
    )

    verdict = (
        f'[FT {n}handed|{regime}|M={m_ratio:.1f}] {action_rec.upper()} | '
        f'icm=${hero_icm:.0f} stack={hero_stack_pct:.0%} | '
        f'push_thresh={push_thresh:.0%} call_thresh={call_thresh:.0%}'
    )

    tips = []
    tips.append(steal_advice)
    tips.append(push_fold_note)
    tips.append(calling_note)

    if next_pay_jump >= current_prize * 0.30:
        tips.append(
            f'BIG PAY JUMP: Next prize increase = ${next_pay_jump:.0f} (+{next_pay_jump/current_prize:.0%} from floor). '
            f'Significant ladder spot — tighten 3-5% equity requirement to survive.'
        )

    if regime == 'chip_leader':
        tips.append(
            f'CHIP LEADER POWER: Raise hero ICM equity from ${hero_icm:.0f} to much higher by eliminating short stacks. '
            f'Chip leader can open-shove vs micro stacks who cannot call without premium. '
            f'Avoid calling all-ins from medium stacks — that coin flip costs you chip advantage.'
        )

    return FinalTableAdvice(
        hero_chips=hero_chips,
        hero_index=hero_index,
        n_players=n,
        payouts=payouts,
        blinds_bb=blinds_bb,
        icm_equities=icm_eq,
        hero_icm_equity=round(hero_icm, 2),
        avg_stack=avg_stack,
        hero_stack_pct=round(hero_stack_pct, 3),
        stack_regime=regime,
        m_ratio=round(m_ratio, 1),
        push_equity_threshold=push_thresh,
        call_equity_threshold=call_thresh,
        hand_rank_push_threshold=push_rank_thresh,
        next_prize=next_prize,
        current_prize=current_prize,
        next_pay_jump_value=round(next_pay_jump, 2),
        steal_advice=steal_advice,
        push_fold_note=push_fold_note,
        calling_note=calling_note,
        situation=situation,
        hand_rank_pct=round(hero_hand_rank_pct, 3),
        action_recommendation=action_rec,
        action_reasoning=action_reason,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ft_one_liner(r: FinalTableAdvice) -> str:
    return (
        f'[FT {r.n_players}handed|{r.stack_regime}|M={r.m_ratio:.1f}] '
        f'{r.action_recommendation.upper()} | '
        f'icm=${r.hero_icm_equity:.0f} stack={r.hero_stack_pct:.0%} | '
        f'push_thresh={r.push_equity_threshold:.0%} call={r.call_equity_threshold:.0%}'
    )
