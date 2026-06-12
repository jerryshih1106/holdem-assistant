"""
Stack-Off Advisor (stack_off_advisor.py)

"Should I put all my chips in right now?"

This module answers the most consequential decision in poker:
when to commit your entire remaining stack.

STACK-OFF SCENARIOS:
  1. Bet-call all-in:       Hero bets, villain raises all-in → hero calls
  2. Check-raise jam:       Hero check-raises all-in
  3. 3-bet jam (preflop):   Hero 3-bets all-in preflop
  4. Call a jam:            Villain jams, hero decides to call
  5. Open jam:              Hero jams directly (short stack)

EQUITY REQUIREMENTS BY STREET:
  Flop (2 cards to come):
    Top pair:        Need 55%+ (high SPR) or 45%+ (low SPR ≤3)
    Two pair:        50%+ always; commit at SPR ≤5
    Set:             Always stack off (set is often equity leader on flop)
    Draw (12+outs):  45%+ (coin flip)
    Draw (9 outs):   Need fold equity or very low SPR
    Air:             Never stack off

  Turn (1 card to come):
    Top pair:        Need 60%+ to stack off (limited outs)
    Two pair+:       50%+
    Draw:            48%+ (rule of 2: outs × 2%)

  River (no more cards):
    Exact showdown value — stack off only with strong hands (set+, straight+)
    Exception: all-in bluffs on river (separate analysis in river_bluff.py)

SPR THRESHOLDS:
  SPR < 2:    Almost always stack off with top pair+, often with draws
  SPR 2-4:    Stack off with two pair+; draws need 45%+ equity
  SPR 4-8:    Stack off with set+; two pair needs board texture check
  SPR > 8:    Only commit with very strong hands (straight+, flush+)

VILLAIN RANGE NARROWING:
  When villain raises/jams, their range NARROWS significantly:
  - Flop jam range (most players): TT+/sets/two-pair (value) + monster draws
  - Turn jam range:                Sets/two-pair+ (value heavy)
  - River jam (vs bet):            Value 75-90% / Bluff 10-25%

EV FORMULA:
  EV(stack_off) = P(win) × total_pot - P(lose) × amount_to_call
  where P(win) = hero_equity_vs_jam_range

Usage:
    from poker.stack_off_advisor import advise_stack_off
    from poker.stack_off_advisor import StackOffAdvice, stack_off_one_liner

    advice = advise_stack_off(
        hero_hand_class='two_pair',
        street='flop',
        hero_pos='IP',
        spr=4.5,
        hero_equity=0.58,
        board_type='medium',
        pot_bb=20.0,
        hero_stack_bb=90.0,
        villain_vpip=0.30,
        villain_af=2.5,
    )
    print(stack_off_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List


# ── Equity thresholds by hand × street × SPR ─────────────────────────────────

def _equity_threshold(
    hand_cat: str, street: str, spr: float, board_type: str,
) -> float:
    """Minimum equity needed to stack off profitably."""
    base = {
        'premium':     0.42,
        'overpair':    0.48,
        'top_pair':    0.55,
        'middle_pair': 0.68,
        'draw':        0.45,
        'air':         0.90,  # effectively never
    }.get(hand_cat, 0.55)

    # Street adjustment
    if street == 'turn':
        base += 0.04   # one card = less equity
    elif street == 'river':
        base += 0.08   # no more cards = pure showdown

    # SPR adjustment (low SPR → lower threshold)
    if spr <= 2.0:
        base -= 0.10
    elif spr <= 3.5:
        base -= 0.06
    elif spr <= 5.0:
        base -= 0.02
    elif spr > 8.0:
        base += 0.05   # deep stacks demand stronger hands

    # Wet board: more outs for draws, but also more outs for villain
    if board_type == 'wet' and hand_cat in ('top_pair', 'middle_pair'):
        base += 0.04

    return round(min(max(base, 0.40), 0.95), 3)


# ── Stack-off action determination ────────────────────────────────────────────

_HAND_CAT_MAP = {
    'air': 'air', 'trash': 'air', 'nothing': 'air', 'bottom_pair': 'air', 'marginal': 'air',
    'middle_pair': 'middle_pair', 'second_pair': 'middle_pair',
    'draw': 'draw', 'flush_draw': 'draw', 'combo_draw': 'draw',
    'top_pair': 'top_pair', 'tptk': 'top_pair', 'good_tp': 'top_pair', 'medium': 'top_pair',
    'overpair': 'overpair', 'two_pair': 'overpair', 'strong': 'overpair',
    'set': 'premium', 'straight': 'premium', 'flush': 'premium',
    'premium': 'premium', 'full_house': 'premium', 'nuts': 'premium',
}


def _hand_cat(hc: str) -> str:
    return _HAND_CAT_MAP.get(hc.lower(), 'top_pair')


def _recommend_stack_off(
    cat: str, street: str, spr: float, hero_equity: float,
    threshold: float, board_type: str, villain_af: float,
    villain_vpip: float, pot_bb: float, hero_stack_bb: float,
) -> tuple:
    """
    Returns (should_stack_off, action, ev_stack, ev_fold, notes).
    action: 'jam', 'call_jam', 'check_raise_jam', 'do_not_commit', 'call_and_evaluate'
    """
    call_cost = hero_stack_bb  # simplified: remaining stack
    total_pot = pot_bb + 2 * call_cost
    ev_stack = round(hero_equity * total_pot - call_cost, 2)
    ev_fold = 0.0

    should_go = hero_equity >= threshold

    # Special cases
    if cat == 'air':
        return (False, 'do_not_commit', ev_stack, ev_fold,
                f'Air hand: never stack off. Equity={hero_equity:.0%} < threshold={threshold:.0%}')

    if cat == 'premium':
        action = 'jam' if spr <= 4 else 'check_raise_jam'
        return (True, action, ev_stack, ev_fold,
                f'Premium hand: always stack off. EV={ev_stack:.1f}BB')

    if cat in ('overpair',) and spr <= 2.0:
        return (True, 'jam', ev_stack, ev_fold,
                f'Two pair/overpair + ultra-low SPR={spr:.1f}: committed. Jam.')

    if should_go:
        if spr <= 2.5:
            action = 'jam'
        elif cat in ('top_pair', 'middle_pair', 'draw'):
            action = 'call_and_evaluate' if spr > 7.0 else 'call_jam'
        else:
            action = 'check_raise_jam' if villain_af >= 2.5 else 'jam'
        return (True, action, ev_stack, ev_fold,
                f'Equity={hero_equity:.0%} >= threshold={threshold:.0%}: stack off. EV={ev_stack:.1f}BB')

    # Near threshold: might be marginal
    near_thresh = hero_equity >= threshold - 0.06

    if near_thresh and cat in ('overpair', 'top_pair'):
        action = 'call_and_evaluate'
        return (False, action, ev_stack, ev_fold,
                f'Marginal: equity={hero_equity:.0%} near threshold={threshold:.0%}. '
                f'Call smaller bets; fold to all-in unless SPR<3')

    return (False, 'do_not_commit', ev_stack, ev_fold,
            f'Equity={hero_equity:.0%} < threshold={threshold:.0%}: do NOT stack off. EV={ev_stack:.1f}BB')


@dataclass
class StackOffAdvice:
    """Advice on whether and how to get all chips in."""
    hero_hand_class: str
    street: str
    hero_pos: str
    spr: float
    hero_equity: float
    board_type: str
    pot_bb: float
    hero_stack_bb: float
    villain_vpip: float
    villain_af: float

    # Analysis
    hand_category: str
    equity_threshold: float        # minimum equity to commit
    equity_margin: float           # hero_equity - threshold (positive = above threshold)

    # Recommendation
    should_stack_off: bool
    recommended_action: str        # 'jam', 'call_jam', 'check_raise_jam', 'do_not_commit', 'call_and_evaluate'
    ev_of_stacking: float          # EV if hero stacks off
    ev_of_folding: float           # 0.0 (hero loses nothing by folding)
    commitment_notes: str

    # Villain range adjustment
    villain_jam_range: str         # estimated range when villain jams
    adjusted_equity_note: str      # note about equity vs jam range vs raw equity

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_stack_off(
    hero_hand_class: str = 'two_pair',
    street: str = 'flop',
    hero_pos: str = 'IP',
    spr: float = 4.5,
    hero_equity: float = 0.58,
    board_type: str = 'medium',
    pot_bb: float = 20.0,
    hero_stack_bb: float = 90.0,
    villain_vpip: float = 0.30,
    villain_af: float = 2.5,
) -> StackOffAdvice:
    """
    Advise on whether to commit the full stack.

    Args:
        hero_hand_class:  Hero's hand strength
        street:           'flop', 'turn', 'river'
        hero_pos:         'IP' or 'OOP'
        spr:              Effective stack-to-pot ratio
        hero_equity:      Hero's estimated equity vs villain's range
        board_type:       'dry', 'medium', 'wet'
        pot_bb:           Current pot in BB
        hero_stack_bb:    Hero's remaining stack in BB
        villain_vpip:     Villain's VPIP (0-1)
        villain_af:       Villain's aggression factor

    Returns:
        StackOffAdvice
    """
    cat = _hand_cat(hero_hand_class)
    threshold = _equity_threshold(cat, street, spr, board_type)
    margin = round(hero_equity - threshold, 3)

    should_go, action, ev_stack, ev_fold, commitment_notes = _recommend_stack_off(
        cat, street, spr, hero_equity, threshold, board_type,
        villain_af, villain_vpip, pot_bb, hero_stack_bb,
    )

    # Villain jam range estimate
    if street == 'flop':
        if villain_vpip < 0.22:
            jam_range = 'Sets, two-pair+ (nit range: very strong only)'
        elif villain_vpip > 0.45:
            jam_range = 'Two pair+, strong draws, overbluffs (wide fish range)'
        else:
            jam_range = 'Sets, two-pair, strong combo draws (typical range)'
    elif street == 'turn':
        jam_range = 'Sets+, straights/flushes (very value-heavy on turn)'
    else:
        jam_range = 'Straights+, sets+ (river jam = very strong or stone bluff)'

    # Equity note
    eq_note = (
        f'Raw equity={hero_equity:.0%} vs estimated villain jam range. '
        f'Actual equity vs jam range may differ significantly — '
        f'villain\'s jamming range is narrower than overall range. '
        f'Adjust: vs tight villain (VPIP={villain_vpip:.0%}), '
        f'equity vs jam range may be 5-10% lower than shown.'
    )

    reasoning = (
        f'{hero_hand_class}({cat}) {street} {hero_pos} SPR={spr:.1f}. '
        f'Equity={hero_equity:.0%}, threshold={threshold:.0%}, margin={margin:+.0%}. '
        f'should_stack_off={should_go}, action={action}. '
        f'EV_stack={ev_stack:.1f}BB, EV_fold=0.'
    )

    # Tips
    tips = []
    if should_go and cat == 'top_pair' and spr > 5.0:
        tips.append(
            f'TOP PAIR STACK-OFF (SPR={spr:.1f}): '
            f'Top pair is rarely the best hand at SPR>{spr:.0f} when villain jams. '
            f'Villain jam range = {jam_range}. '
            f'You need equity={hero_equity:.0%} >= {threshold:.0%} to commit. '
            f'If villain shows strength across multiple streets, FOLD top pair.'
        )
    if should_go and cat == 'draw':
        tips.append(
            f'DRAW STACK-OFF: '
            f'With equity={hero_equity:.0%}, stacking off is correct when EV={ev_stack:.1f}BB > 0. '
            f'BUT: villain\'s jam range skews value-heavy (they have made hands). '
            f'Your fold equity was already included in EV calc. '
            f'Make sure your draw has 12+ outs before stacking on flop.'
        )
    if not should_go and margin >= -0.08:
        tips.append(
            f'MARGINAL SPOT (equity={hero_equity:.0%}, threshold={threshold:.0%}): '
            f'You are close to the line. '
            f'Adjust based on: villain VPIP={villain_vpip:.0%} (high=stack off more), '
            f'board texture={board_type} (wet=be more careful), '
            f'SPR={spr:.1f} (lower=stack off more). '
            f'When in doubt: call smaller bets, fold to all-in.'
        )
    if should_go and cat == 'premium':
        tips.append(
            f'PREMIUM HAND (set/flush/straight): ALWAYS stack off regardless of equity shown. '
            f'SPR={spr:.1f}, hand dominates villain\'s jamming range. '
            f'Get maximum value: jam or check-raise jam depending on position.'
        )
    if board_type == 'wet' and not should_go:
        tips.append(
            f'WET BOARD: Villain\'s jamming range is skewed toward draws and combo draws '
            f'(not just value). This actually INCREASES your equity relative to threshold. '
            f'If villain also has a draw, your equity vs their range is better than shown. '
            f'Consider calling if your hand has good showdown value.'
        )
    if not tips:
        tips.append(
            f'{action}: {commitment_notes}. '
            f'EV stack-off = {ev_stack:.1f}BB. '
            f'Villain jam range: {jam_range}.'
        )

    return StackOffAdvice(
        hero_hand_class=hero_hand_class,
        street=street,
        hero_pos=hero_pos,
        spr=round(spr, 2),
        hero_equity=round(hero_equity, 3),
        board_type=board_type,
        pot_bb=round(pot_bb, 1),
        hero_stack_bb=round(hero_stack_bb, 1),
        villain_vpip=round(villain_vpip, 3),
        villain_af=round(villain_af, 2),
        hand_category=cat,
        equity_threshold=threshold,
        equity_margin=margin,
        should_stack_off=should_go,
        recommended_action=action,
        ev_of_stacking=ev_stack,
        ev_of_folding=ev_fold,
        commitment_notes=commitment_notes,
        villain_jam_range=jam_range,
        adjusted_equity_note=eq_note,
        reasoning=reasoning,
        tips=tips,
    )


def stack_off_one_liner(r: StackOffAdvice) -> str:
    decision = 'COMMIT' if r.should_stack_off else 'DO_NOT_COMMIT'
    return (
        f'[SO {r.hero_hand_class}@{r.street}|SPR={r.spr:.1f}] '
        f'{decision} | '
        f'action={r.recommended_action} eq={r.hero_equity:.0%} '
        f'thresh={r.equity_threshold:.0%} margin={r.equity_margin:+.0%} | '
        f'ev={r.ev_of_stacking:.1f}BB'
    )
