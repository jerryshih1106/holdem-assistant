"""
Tournament Pay Jump Advisor (tournament_payjump_advisor.py)

Advises on strategy specifically at significant pay jump spots in MTTs.
Unlike bubble ICM (survive one more elimination) or final table ICM (full
payout tree), this module focuses on the common scenario:
  "I'm X spots from a significant pay jump — how should I adjust?"

PAY JUMP CATEGORIES:
  min_cash:         Any money (value depends on buy-in multiple)
  next_step:        20-50% prize increase
  significant_jump: 50-150% prize increase
  major_jump:       150-400% prize increase (e.g., top 3 in a big tournament)
  winner_takes_most: Final 2-3 spots where most prize money lives

STRATEGY ADJUSTMENTS:
  Close to jump (1-2 eliminations away): tighten 5-15%
  Near min_cash (first elimination from ITM): survive at almost any cost
  Near major_jump: significant tightening; avoid flips with medium stacks
  Winner_takes_most: accumulate aggressively; survival mindset shifts

KEY NUMBERS:
  Bubble factor = ratio of ICM equity gained by NOT busting vs gained by doubling
  High bubble factor (>2.0): tight play; medium factor (1.0-2.0): balanced; low (<1.0): chip accumulate

DISTINCT FROM OTHER MODULES:
  icm_advisor.py:             Bubble pressure (last spot before min cash)
  tournament_stage_advisor.py: M-ratio based strategy
  final_table_icm_strategy.py: Full FT ICM with payout tree
  THIS MODULE:                 Pay jump spots throughout tournament; bubble factor; spot-specific advice

Usage:
    from poker.tournament_payjump_advisor import advise_payjump, PayJumpAdvice, pj_one_liner

    result = advise_payjump(
        hero_chips=35000,
        avg_chips=42000,
        players_left=18,
        spots_to_jump=3,
        current_prize=1200,
        target_prize=2000,
        hero_hand_rank_pct=0.72,
        situation='facing_shove',
    )
    print(pj_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


def _jump_category(current_prize: float, target_prize: float) -> str:
    ratio = target_prize / max(current_prize, 1.0)
    if current_prize <= 0:
        return 'min_cash'
    elif ratio >= 4.0:
        return 'winner_takes_most'
    elif ratio >= 2.5:
        return 'major_jump'
    elif ratio >= 1.5:
        return 'significant_jump'
    elif ratio >= 1.20:
        return 'next_step'
    else:
        return 'small_step'


def _bubble_factor(
    spots_to_jump: int,
    jump_category: str,
    hero_chips: int,
    avg_chips: int,
) -> float:
    """
    Approximate bubble factor for this jump spot.
    >1.5 = tight; 1.0-1.5 = moderate; <1.0 = accumulate.
    """
    base = {
        'winner_takes_most': 0.80,
        'major_jump':        1.40,
        'significant_jump':  1.80,
        'next_step':         1.40,
        'small_step':        1.10,
        'min_cash':          2.50,
    }.get(jump_category, 1.30)

    # Proximity adjustment: 1 spot away = maximum pressure
    proximity_mult = {1: 1.5, 2: 1.2, 3: 1.1, 4: 1.05, 5: 1.0}.get(min(spots_to_jump, 5), 1.0)

    # Stack size: short stack has lower effective bubble factor (must gamble)
    stack_ratio = hero_chips / max(avg_chips, 1)
    if stack_ratio < 0.4:
        stack_mult = 0.7    # short stack: desperate
    elif stack_ratio < 0.7:
        stack_mult = 0.85
    elif stack_ratio < 1.5:
        stack_mult = 1.0
    else:
        stack_mult = 1.1    # chip leader: can afford caution

    return round(base * proximity_mult * stack_mult, 2)


def _equity_adjustment(bubble_factor: float) -> float:
    """Additional equity required vs neutral (0.50) due to bubble factor."""
    if bubble_factor >= 2.0:
        return 0.08
    elif bubble_factor >= 1.5:
        return 0.05
    elif bubble_factor >= 1.2:
        return 0.03
    elif bubble_factor >= 0.9:
        return 0.01
    else:
        return -0.02   # accumulate: slightly lower threshold


def _strategy_advice(
    jump_category: str,
    bubble_factor: float,
    spots_to_jump: int,
    hero_chips: int,
    avg_chips: int,
) -> str:
    stack_ratio = hero_chips / max(avg_chips, 1)

    if jump_category == 'min_cash':
        return (
            f'MIN CASH BUBBLE: {spots_to_jump} eliminations from any money. '
            f'Fold almost everything except premium hands. '
            f'Short stacks will bust out; let them. Do NOT call all-ins without KK+/AA. '
            f'Push/fold only from strong position (BTN/CO with commanding fold equity).'
        )
    elif jump_category == 'winner_takes_most':
        if stack_ratio >= 1.5:
            return (
                f'FINAL FEW SPOTS — BIG MONEY: Chip leader should ACCUMULATE aggressively. '
                f'The top prize is much larger; surviving to 2nd place is not enough. '
                f'Maintain pressure; call off marginal spots with short stacks.'
            )
        else:
            return (
                f'FINAL FEW SPOTS — ICM PRESSURE: Every elimination worth big money. '
                f'Avoid marginal flips vs chip leaders. '
                f'Push/fold from short stack; call only with strong hands vs medium stacks.'
            )
    elif jump_category in ('major_jump', 'significant_jump'):
        if spots_to_jump <= 2:
            return (
                f'SIGNIFICANT JUMP IN {spots_to_jump} SPOTS: Tighten 8-12% across the board. '
                f'Fold QQ, AK vs chip leader shoves (ICM says fold is profitable). '
                f'Steal aggressively from short stacks; avoid confrontations with bigger stacks. '
                f'Every fold that survives one more position could be worth hundreds of dollars.'
            )
        else:
            return (
                f'APPROACHING BIG PAY JUMP ({spots_to_jump} spots): Moderate tightening. '
                f'Avoid 50/50 flips vs similar stacks. '
                f'Increase steal frequency vs short stacks; reduce vs chip leaders. '
                f'Bubble factor={bubble_factor:.1f}: need {_equity_adjustment(bubble_factor):+.0%} extra equity.'
            )
    else:  # next_step or small_step
        return (
            f'PAY STEP AHEAD ({spots_to_jump} spots): Minor adjustments needed. '
            f'Play slightly tighter in marginal spots vs comparable stacks. '
            f'Bubble factor={bubble_factor:.1f}: low-medium pressure. '
            f'Continue accumulating; do not give up significant edge for small survival premium.'
        )


@dataclass
class PayJumpAdvice:
    # Inputs
    hero_chips: int
    avg_chips: int
    players_left: int
    spots_to_jump: int
    current_prize: float
    target_prize: float
    hero_hand_rank_pct: float
    situation: str

    # Jump analysis
    jump_category: str      # 'min_cash' / 'next_step' / 'significant_jump' / 'major_jump' / 'winner_takes_most'
    prize_ratio: float      # target / current
    bubble_factor: float    # >1 = tight; <1 = accumulate

    # Equity adjustment
    equity_adj: float       # additional equity needed due to ICM
    adjusted_call_threshold: float  # 0.50 + equity_adj
    adjusted_push_threshold: float  # hand rank threshold for pushing

    # Strategy
    strategy_advice: str
    steal_advice: str

    # Situation-specific
    action_recommendation: str  # 'push' / 'call' / 'fold' / 'standard'
    action_ev_note: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_payjump(
    hero_chips: int = 35000,
    avg_chips: int = 42000,
    players_left: int = 18,
    spots_to_jump: int = 3,
    current_prize: float = 1200.0,
    target_prize: float = 2000.0,
    hero_hand_rank_pct: float = 0.72,
    situation: str = 'normal',   # 'normal' / 'facing_shove' / 'considering_push'
) -> PayJumpAdvice:
    """
    Advise on strategy near a significant pay jump.

    Args:
        hero_chips:          Hero's chip count
        avg_chips:           Average chips per player
        players_left:        Total players remaining
        spots_to_jump:       Eliminations needed to reach next prize tier
        current_prize:       Current floor prize
        target_prize:        Prize at next significant tier
        hero_hand_rank_pct:  Hero's hand (0-1)
        situation:           Current decision situation

    Returns:
        PayJumpAdvice
    """
    stack_ratio = hero_chips / max(avg_chips, 1)
    prize_ratio = target_prize / max(current_prize, 1.0)
    jump_cat = _jump_category(current_prize, target_prize)
    bf = _bubble_factor(spots_to_jump, jump_cat, hero_chips, avg_chips)
    eq_adj = _equity_adjustment(bf)
    call_thresh = round(0.50 + eq_adj, 3)
    push_thresh = round(max(0.30, 0.60 - (1.0 / max(bf, 0.5)) * 0.10), 3)

    strat = _strategy_advice(jump_cat, bf, spots_to_jump, hero_chips, avg_chips)

    if stack_ratio >= 1.5:
        steal_adv = f'Chip leader: steal aggressively (BTN 50%+, CO 35%+). Short stacks cannot call profitably.'
    elif stack_ratio >= 0.8:
        steal_adv = f'Standard stack: steal from BTN/CO 30-40%; avoid confronting chip leaders.'
    else:
        steal_adv = f'Short stack: push or fold only. Stop open-folding; push with any 2 cards if fold equity exists.'

    # Action recommendation
    est_equity = 0.35 + hero_hand_rank_pct * 0.35
    if situation == 'facing_shove':
        if est_equity >= call_thresh + 0.05:
            action_rec = 'call'
            action_note = f'Equity {est_equity:.0%} >= ICM call threshold {call_thresh:.0%}'
        elif est_equity >= call_thresh - 0.02:
            action_rec = 'fold'
            action_note = f'Marginal: fold near pay jump. Equity {est_equity:.0%} close to threshold {call_thresh:.0%}'
        else:
            action_rec = 'fold'
            action_note = f'Clear fold: equity {est_equity:.0%} < ICM threshold {call_thresh:.0%}'
    elif situation == 'considering_push':
        if hero_hand_rank_pct >= push_thresh:
            action_rec = 'push'
            action_note = f'Hand rank {hero_hand_rank_pct:.0%} >= push threshold {push_thresh:.0%}'
        else:
            action_rec = 'fold'
            action_note = f'Below push threshold {push_thresh:.0%}; fold or wait for better spot'
    else:
        action_rec = 'standard'
        action_note = strat[:80]

    reasoning = (
        f'{players_left} players left, {spots_to_jump} spots to {jump_cat} (${current_prize:.0f}→${target_prize:.0f}). '
        f'Hero {hero_chips//1000}k chips vs avg {avg_chips//1000}k ({stack_ratio:.1f}x). '
        f'Prize ratio={prize_ratio:.1f}x bubble_factor={bf:.2f}. '
        f'Equity adj={eq_adj:+.0%} call_thresh={call_thresh:.0%} push_rank_thresh={push_thresh:.0%}. '
        f'Situation={situation}: {action_rec}.'
    )

    verdict = (
        f'[PJ {jump_cat.upper()}|{spots_to_jump}away] {action_rec.upper()} | '
        f'bf={bf:.1f} eq_adj={eq_adj:+.0%} call_thresh={call_thresh:.0%} | '
        f'${current_prize:.0f}->${target_prize:.0f} ({prize_ratio:.1f}x)'
    )

    tips = []
    tips.append(strat)
    tips.append(
        f'EQUITY THRESHOLDS: Call threshold={call_thresh:.0%} (+{eq_adj:.0%} vs neutral {0.50:.0%}). '
        f'Push hand rank threshold={push_thresh:.0%}. '
        f'Bubble factor={bf:.1f}: {"HIGH PRESSURE — fold marginal spots" if bf >= 1.8 else "MODERATE — slight tightening" if bf >= 1.2 else "LOW — play near chip EV"}.'
    )
    tips.append(steal_adv)

    if jump_cat == 'min_cash' and spots_to_jump <= 2:
        tips.append(
            f'NEAR THE MONEY: {spots_to_jump} bust-outs until any prize. '
            f'Every hand you fold increases your EV. '
            f'Even KK/QQ vs chip leader shoves may be fold in extreme cases. '
            f'Use a Nash calculator if unsure — pure survival EV calculation applies here.'
        )

    return PayJumpAdvice(
        hero_chips=hero_chips,
        avg_chips=avg_chips,
        players_left=players_left,
        spots_to_jump=spots_to_jump,
        current_prize=current_prize,
        target_prize=target_prize,
        hero_hand_rank_pct=round(hero_hand_rank_pct, 3),
        situation=situation,
        jump_category=jump_cat,
        prize_ratio=round(prize_ratio, 2),
        bubble_factor=bf,
        equity_adj=round(eq_adj, 3),
        adjusted_call_threshold=call_thresh,
        adjusted_push_threshold=push_thresh,
        strategy_advice=strat,
        steal_advice=steal_adv,
        action_recommendation=action_rec,
        action_ev_note=action_note,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pj_one_liner(r: PayJumpAdvice) -> str:
    return (
        f'[PJ {r.jump_category.upper()}|{r.spots_to_jump}away] {r.action_recommendation.upper()} | '
        f'bf={r.bubble_factor:.1f} eq_adj={r.equity_adj:+.0%} call={r.adjusted_call_threshold:.0%} | '
        f'${r.current_prize:.0f}->${r.target_prize:.0f} ({r.prize_ratio:.1f}x)'
    )
