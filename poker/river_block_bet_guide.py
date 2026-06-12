"""
River Block Bet Guide (river_block_bet_guide.py)

Guides OOP players on when and how to use block bets on the river.
A block bet is a small OOP lead (~20-33% pot) designed to:
  1. Control the pot: prevent facing a large IP bet by "blocking" it
  2. Extract thin value: get paid by worse hands at a reduced price
  3. Define hand: force IP to raise strong and call medium
  4. Balance checking range: add some bets to prevent IP from always betting

BLOCK BET THEORY:
  Key insight: OOP has to act first on the river. If you check and villain bets
  large, you face a difficult decision. Block bets prevent this by:
  - Making villain choose: call small bet OR raise (most passive players just call)
  - Collecting value from hands that would check back if you check
  - Avoiding paying off villain's large bet when they have value

  WHEN TO BLOCK BET:
  1. Medium-strength hands OOP (top pair weak kicker, bottom two pair)
  2. Missed draws with showdown value (A-high, K-high with blockers)
  3. Boards where villain has a range advantage but you have marginal equity
  4. Against passive villains (AF < 2.0) who rarely bluff-raise

  WHEN NOT TO BLOCK BET:
  1. Strong value (2-pair+): bet large for value; don't block
  2. Pure air: check-fold (block bet commits money with no equity)
  3. Against aggressive villains (AF >= 3.0): they raise your block bet
  4. Very wet runouts: draws completed; your block may face an overbet raise

  BLOCK BET SIZING: 20-33% pot
  The goal is a price that villain calls with most hands (blocking their bet)
  while extracting value from worse. If they raise: you have a defined decision
  (fold medium hands, call strong hands).

  EXPLOITATIVE ADJUSTMENTS:
  vs Passive villain (low AF): block bet most medium hands (won't raise)
  vs Aggressive villain:       check-call or check-raise instead of block

DISTINCT FROM:
  river_advisor.py:       General river decisions
  river_medium.py:        Medium-strength river play
  river_decision.py:      River action framework
  donk_bet_range_builder.py: Flop donk bets
  THIS MODULE:            RIVER SPECIFICALLY; OOP block bet; sizing,
                          hand selection, villain type adjustments.

Usage:
    from poker.river_block_bet_guide import guide_river_block_bet, RiverBlockBetGuide, rbbg_one_liner

    result = guide_river_block_bet(
        hero_hand_category='top_pair_weak',
        hero_position='oop',
        villain_af=1.5,
        villain_fold_to_river_bet=0.45,
        pot_bb=40.0,
        effective_stack=25.0,
        board_texture='dry',
        has_showdown_value=True,
    )
    print(rbbg_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Block bet sizing (fraction of pot)
BLOCK_BET_SIZE = 0.28   # standard block: ~28% pot

# Hands eligible for block bet OOP
BLOCK_ELIGIBLE_HANDS = {
    'top_pair_weak', 'weak_top_pair', 'middle_pair', 'bottom_two_pair',
    'missed_flush_draw_high', 'ace_high', 'king_high', 'overcards_showdown',
    'bluff_catcher',
}

# Hands that should bet large (not block)
BET_LARGE_HANDS = {
    'nuts', 'near_nuts', 'full_house', 'flush', 'straight', 'set', 'two_pair',
    'strong_top_pair', 'overpair',
}

# Hands that should check (not block bet)
CHECK_HANDS = {
    'air', 'missed_flush_draw', 'gutshot', 'bottom_pair', 'overcards',
}


def _should_block_bet(
    hand_category: str,
    villain_af: float,
    has_showdown_value: bool,
    board_texture: str,
) -> bool:
    if hand_category in BET_LARGE_HANDS:
        return False   # bet large, not block
    if hand_category in CHECK_HANDS and not has_showdown_value:
        return False   # no showdown value = check-fold
    if villain_af >= 3.0:
        return False   # aggressive villain will raise the block
    if board_texture == 'monotone':
        return False   # too many strong hands completed; gets raised
    return hand_category in BLOCK_ELIGIBLE_HANDS or (
        has_showdown_value and hand_category not in CHECK_HANDS
    )


def _block_size(pot_bb: float, effective_stack: float) -> float:
    """Block bet size in BB."""
    target = pot_bb * BLOCK_BET_SIZE
    return round(min(target, effective_stack), 1)


def _block_ev(
    pot_bb: float,
    block_size: float,
    villain_fold_rate: float,
    villain_call_rate: float,
    hero_equity_vs_call: float = 0.35,
) -> float:
    """EV of block bet vs checking."""
    # If villain folds: hero wins pot + block * 0 (already won)
    ev_fold = villain_fold_rate * (pot_bb + block_size)
    # If villain calls: hero gets call + equity of win
    ev_call = villain_call_rate * hero_equity_vs_call * (pot_bb + 2 * block_size)
    # Vs check: hero wins pot * some_equity (simplified)
    ev_check = hero_equity_vs_call * pot_bb
    return round(ev_fold + ev_call - ev_check, 2)


def _raise_response(hand_category: str) -> str:
    """What to do if villain raises the block bet."""
    if hand_category in BET_LARGE_HANDS or hand_category == 'strong_top_pair':
        return 'call_or_reraise'
    return 'fold'  # block bet was for thin value; raise = villain has it


def _alternative_line(hand_category: str, villain_af: float) -> str:
    """What to do instead of block bet."""
    if villain_af >= 3.0:
        if hand_category in BLOCK_ELIGIBLE_HANDS:
            return 'check_call'   # let aggressive villain bluff; call on river
        return 'check_fold'
    return 'check_fold'  # vs passive: check-fold since they won't bet many bluffs


@dataclass
class RiverBlockBetGuide:
    # Inputs
    hero_hand_category: str
    hero_position: str
    villain_af: float
    villain_fold_to_river_bet: float
    pot_bb: float
    effective_stack: float
    board_texture: str
    has_showdown_value: bool

    # Analysis
    should_block_bet: bool
    block_bet_size_bb: float
    block_bet_pct: float        # as % of pot
    block_bet_ev: float
    raise_response: str         # what to do if raised
    alternative_action: str     # if not block betting

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def guide_river_block_bet(
    hero_hand_category: str = 'top_pair_weak',
    hero_position: str = 'oop',
    villain_af: float = 1.5,
    villain_fold_to_river_bet: float = 0.45,
    pot_bb: float = 40.0,
    effective_stack: float = 25.0,
    board_texture: str = 'dry',
    has_showdown_value: bool = True,
) -> RiverBlockBetGuide:
    """
    Guide OOP river block bet decision.

    Args:
        hero_hand_category:        Hand strength
        hero_position:             'oop' (out of position)
        villain_af:                Villain aggression factor
        villain_fold_to_river_bet: Villain fold-to-river-bet frequency
        pot_bb:                    Current pot size in BB
        effective_stack:           Remaining stack after flop/turn
        board_texture:             'dry' / 'wet' / 'semi_wet' / 'monotone'
        has_showdown_value:        Whether hand has SDV if checked

    Returns:
        RiverBlockBetGuide
    """
    do_block = _should_block_bet(hand_category=hero_hand_category,
                                  villain_af=villain_af,
                                  has_showdown_value=has_showdown_value,
                                  board_texture=board_texture)
    block_size = _block_size(pot_bb, effective_stack)
    block_pct = round(block_size / pot_bb, 2) if pot_bb > 0 else 0.0
    call_rate = 1.0 - villain_fold_to_river_bet
    ev = _block_ev(pot_bb, block_size, villain_fold_to_river_bet, call_rate)
    raise_resp = _raise_response(hero_hand_category)
    alt = _alternative_line(hero_hand_category, villain_af)

    action = f'BLOCK_BET {block_pct:.0%}pot ({block_size:.1f}BB)' if do_block else alt.upper()

    verdict = (
        f'[RBBG {hero_hand_category}|river|{hero_position}] '
        f'{action} ev={ev:+.1f}BB | af={villain_af:.1f}'
    )

    reasoning = (
        f'River block bet: {hero_hand_category} OOP on {board_texture} river. '
        f'Villain AF={villain_af:.1f} ({"passive - block safe" if villain_af < 2.0 else "aggressive - avoid block"}). '
        f'Block size: {block_size:.1f}BB ({block_pct:.0%}pot). '
        f'EV vs checking: {ev:+.1f}BB. '
        f'Should block: {do_block}. '
        f'If raised: {raise_resp}.'
    )

    tips = []

    tips.append(
        f'BLOCK BET LOGIC: Small OOP bet ({BLOCK_BET_SIZE:.0%} pot) to control pot size. '
        f'Prevents IP from betting large into your {hero_hand_category}. '
        f'Villain faces: call small OR raise (passive players usually call). '
        f'Size: {block_size:.1f}BB into {pot_bb:.0f}BB pot ({block_pct:.0%}).'
    )

    if do_block:
        tips.append(
            f'BLOCK BET EV: {ev:+.1f}BB vs checking. '
            f'Villain AF={villain_af:.1f}: passive player unlikely to raise; block is safe. '
            f'If raised: {raise_resp}. '
            f'Block extracts thin value from worse hands that would check back.'
        )
    else:
        if villain_af >= 3.0:
            tips.append(
                f'AVOID BLOCK vs AGGRESSIVE VILLAIN (AF={villain_af:.1f}): '
                f'Aggressive players raise your block bet at high frequency. '
                f'Block bet becomes a mistake: you commit more chips then fold. '
                f'Instead: {alt.upper()}. Let them bet; you call or fold based on sizing.'
            )
        elif hero_hand_category in BET_LARGE_HANDS:
            tips.append(
                f'BET LARGE INSTEAD: {hero_hand_category} is too strong for a block bet. '
                f'Blocking with strong value leaves money on the table. '
                f'Size up to 65-80% pot to maximize value extraction.'
            )
        else:
            tips.append(
                f'CHECK-FOLD: {hero_hand_category} has insufficient equity to block bet profitably. '
                f'Alternative: {alt.upper()}. '
                f'Committing chips with no showdown value or block bet candidacy is -EV.'
            )

    tips.append(
        f'WHEN TO BLOCK vs CHECK-CALL: '
        f'Block bet (passive villain, low AF): extract value; prevent large bet. '
        f'Check-call (aggressive villain, high AF): let villain bluff; call decent hand. '
        f'Villain AF={villain_af:.1f}: {"use block" if villain_af < 2.0 else "prefer check-call or check-fold"}.'
    )

    return RiverBlockBetGuide(
        hero_hand_category=hero_hand_category,
        hero_position=hero_position,
        villain_af=villain_af,
        villain_fold_to_river_bet=villain_fold_to_river_bet,
        pot_bb=pot_bb,
        effective_stack=effective_stack,
        board_texture=board_texture,
        has_showdown_value=has_showdown_value,
        should_block_bet=do_block,
        block_bet_size_bb=block_size,
        block_bet_pct=block_pct,
        block_bet_ev=ev,
        raise_response=raise_resp,
        alternative_action=alt,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rbbg_one_liner(r: RiverBlockBetGuide) -> str:
    action = f'BLOCK {r.block_bet_pct:.0%}pot' if r.should_block_bet else r.alternative_action.upper()
    return (
        f'[RBBG {r.hero_hand_category}|river] '
        f'{action} ev={r.block_bet_ev:+.1f}BB | '
        f'if_raised={r.raise_response}'
    )
