"""
Turn/River Texture Change Advisor (turn_texture_change.py)

When a new community card arrives on the turn or river and CHANGES the board
texture significantly, it affects:
  - Who has range advantage (which player benefits)
  - Optimal bet sizing (e.g., board pairs → use smaller bets)
  - Whether to continue betting or slow down
  - Whether to bluff (new scare cards open bluffing opportunities)
  - Whether existing value bets gain or lose strength

Change types:
  1. FLUSH ARRIVES: 3rd or 4th card of same suit
     - Villain's flush combos activate
     - Hero must evaluate if they have the flush, or block it
     - Board becomes more polarized (flush or nothing)
     - Sizing typically increases (charging draws/made flush)

  2. BOARD PAIRS: A card that was already on the board appears again
     - Full houses become possible
     - Previous straight/flush draws are less threatening
     - Good for players with trips/boat but bad for made straights/flushes
     - Sizing: use smaller (trips/boats don't want to blow villain off)

  3. STRAIGHT COMPLETES: A card that completes an open-ended or gutshot draw
     - Previously strong made hands (sets, two pair) are now vulnerable
     - Hero with straight can now value bet big
     - Hero without straight must downgrade equity estimate

  4. HIGH CARD ARRIVES: Broadway card (A, K, Q, J) on a low board
     - Hits preflop raiser's range (they have more AK, AQ, etc.)
     - BB defender range doesn't include as many Ax
     - Good texture for preflop raiser to barrel

  5. BLANK: Card that changes nothing
     - Previous analysis still applies
     - Continuation of prior street's plan is appropriate

Usage:
    from poker.turn_texture_change import analyze_texture_change, TextureChange
    result = analyze_texture_change(
        old_board=['Ah', 'Td', '5c'],
        new_card='Kh',
        hero_equity_before=0.68,
        hero_equity_after=0.55,
        hero_has_relevant_card=False,
        hero_was_betting=True,
        street='turn',
    )
    print(result.change_type, result.should_continue_betting)
"""

from dataclasses import dataclass, field
from typing import List, Optional


_RANK_ORDER = '23456789TJQKA'
_BROADWAY = set('TJQKA')


def _suit_of(card: str) -> str:
    return card[-1].lower() if card else ''


def _rank_of(card: str) -> str:
    return card[0].upper() if card else ''


def _detect_change(old_board: List[str], new_card: str) -> str:
    """Classify the type of texture change the new card creates."""
    new_suit = _suit_of(new_card)
    new_rank = _rank_of(new_card)

    # Check if board pairs
    old_ranks = [_rank_of(c) for c in old_board]
    if new_rank in old_ranks:
        return 'board_pairs'

    # Check if flush arrives (3+ cards same suit)
    suits = [_suit_of(c) for c in old_board]
    suit_counts = {s: suits.count(s) for s in set(suits)}
    if suit_counts.get(new_suit, 0) >= 2:
        return 'flush_arrives'

    # Check if Broadway card arrives on low board
    old_is_low = all(_rank_of(c) not in _BROADWAY for c in old_board)
    if old_is_low and new_rank in _BROADWAY:
        return 'broadway_arrives'

    # Check if straight arrives (simplified)
    all_ranks = [_RANK_ORDER.index(r) for r in old_ranks + [new_rank] if r in _RANK_ORDER]
    if len(all_ranks) >= 4:
        all_ranks_sorted = sorted(set(all_ranks))
        for i in range(len(all_ranks_sorted) - 3):
            window = all_ranks_sorted[i:i+5]
            if len(window) == 5 and window[-1] - window[0] == 4:
                return 'straight_arrives'
        # Check for completing an OESD (4 connectors now 5)
        for i in range(len(all_ranks_sorted) - 3):
            if all_ranks_sorted[i+3] - all_ranks_sorted[i] == 3:
                return 'straight_arrives'

    return 'blank'


def _sizing_adjustment(change_type: str, hero_has_relevant: bool) -> tuple:
    """(size_mult, reason) — multiplier vs standard bet sizing."""
    if change_type == 'flush_arrives':
        if hero_has_relevant:
            return (1.30, 'Flush card: hero has flush → bet larger (polarized range advantage)')
        return (0.80, 'Flush card: no flush → bet smaller or consider check (vulnerable)')

    if change_type == 'board_pairs':
        return (0.65, 'Board pairs: use smaller bets — trips/boats prefer slow play; '
                'straights/flushes now vulnerable')

    if change_type == 'straight_arrives':
        if hero_has_relevant:
            return (1.20, 'Straight card: hero has straight → value bet larger')
        return (0.70, 'Straight card: no straight → reduce bet sizing; villain may have got there')

    if change_type == 'broadway_arrives':
        return (1.10, 'Broadway card: preflop raiser range improves → can barrel wider')

    return (1.00, 'Blank: no change in sizing strategy')


def _range_advantage_shift(change_type: str, hero_was_pfr: bool,
                           hero_has_relevant: bool) -> str:
    """Who gains range advantage from the texture change?"""
    if change_type == 'flush_arrives':
        return 'hero' if hero_has_relevant else 'villain_or_neutral'

    if change_type == 'board_pairs':
        return 'pfr' if hero_was_pfr else 'caller'  # PFR has more over-pairs, trips

    if change_type == 'broadway_arrives':
        return 'pfr' if hero_was_pfr else 'neutral'  # PFR has more AK, AQ

    if change_type == 'straight_arrives':
        # Caller often has more connectors that complete
        return 'hero' if hero_has_relevant else 'villain_or_caller'

    return 'neutral'


def _should_continue(
    change_type: str,
    hero_equity_before: float,
    hero_equity_after: float,
    hero_was_betting: bool,
    hero_has_relevant: bool,
    equity_delta: float,
) -> tuple:
    """(should_continue, reasoning)"""
    if equity_delta < -0.15:
        return (False,
                f'Equity dropped {abs(equity_delta):.0%} → stop betting. '
                f'Villain likely improved. Switch to check-call if any equity remains.')

    if change_type == 'blank' and hero_was_betting:
        return (True, 'Blank card: continue with prior street plan.')

    if change_type == 'flush_arrives' and hero_has_relevant:
        return (True, 'Flush card and hero has flush: continue betting for value. '
                f'Villain may call with top pair or weaker flush.')

    if change_type == 'flush_arrives' and not hero_has_relevant:
        if hero_equity_after < 0.50:
            return (False, 'Flush card and no flush: stop betting. '
                    'Hero range is now uncapped but vulnerable to flush.')
        return (True, 'Flush card: continue small bet — hero range still has sets, '
                'boats and can represent flush.')

    if change_type == 'board_pairs':
        if hero_equity_after >= 0.65:
            return (True, 'Board pairs: hero still strong (set/boat) — continue betting smaller.')
        return (False, 'Board pairs: hero range weakened — check and re-evaluate.')

    if change_type == 'broadway_arrives' and hero_was_betting:
        return (True, 'Broadway arrival: PFR range improves. '
                'Continue betting to represent AK/AQ/top pair improvement.')

    return (hero_equity_after >= 0.50,
            f'Continue: {hero_equity_after:.0%} equity > 50% threshold.'
            if hero_equity_after >= 0.50 else
            f'Stop: {hero_equity_after:.0%} equity < 50% threshold.')


@dataclass
class TextureChange:
    """Analysis of a texture-changing turn/river card."""
    street: str
    old_board: List[str]
    new_card: str
    change_type: str             # 'blank', 'flush_arrives', 'board_pairs', etc.

    # Equity impact
    hero_equity_before: float
    hero_equity_after: float
    equity_delta: float

    # Sizing
    size_multiplier: float
    size_reasoning: str

    # Range dynamics
    range_advantage: str         # who benefits
    should_continue_betting: bool
    continuation_reasoning: str

    # Notes
    key_adjustments: List[str] = field(default_factory=list)
    one_liner: str = ''


def analyze_texture_change(
    old_board: List[str],
    new_card: str,
    hero_equity_before: float,
    hero_equity_after: float,
    hero_has_relevant_card: bool = False,
    hero_was_betting: bool = True,
    hero_was_pfr: bool = True,
    street: str = 'turn',
) -> TextureChange:
    """
    Analyze how a new community card changes board texture and strategy.

    Args:
        old_board:              Previous community cards (list of card strings)
        new_card:               The new card just arrived
        hero_equity_before:     Hero's equity before this card
        hero_equity_after:      Hero's equity after this card
        hero_has_relevant_card: Hero holds the flush/straight/trip card
        hero_was_betting:       Hero was the aggressor last street
        hero_was_pfr:           Hero was the preflop raiser
        street:                 'turn' or 'river'

    Returns:
        TextureChange with strategic adjustments
    """
    change_type = _detect_change(old_board, new_card)
    equity_delta = round(hero_equity_after - hero_equity_before, 3)
    size_mult, size_reason = _sizing_adjustment(change_type, hero_has_relevant_card)
    range_adv = _range_advantage_shift(change_type, hero_was_pfr, hero_has_relevant_card)
    continue_bet, cont_reason = _should_continue(
        change_type, hero_equity_before, hero_equity_after,
        hero_was_betting, hero_has_relevant_card, equity_delta,
    )

    adjustments = [size_reason]

    if equity_delta <= -0.10:
        adjustments.append(
            f'Equity dropped {abs(equity_delta):.0%}: reassess hand strength. '
            f'New card significantly helps villain.'
        )
    elif equity_delta >= 0.10:
        adjustments.append(
            f'Equity improved {equity_delta:.0%}: this card helps hero. '
            f'May be time to build the pot more aggressively.'
        )

    if change_type == 'board_pairs':
        adjustments.append(
            'Board pairs: reduce bet size (0.33-0.50 pot preferred). '
            'Villain has more bluff-catching incentive; use small sizing for max calls.'
        )
    elif change_type == 'flush_arrives' and not hero_has_relevant_card:
        adjustments.append(
            'Flush arrived but hero has no flush: villain may have called with draw. '
            'Hero\'s value range is now at risk. Prefer checking and calling small bets.'
        )

    one_liner = (
        f'[TTC {new_card}] {change_type.upper()} | '
        f'eq {hero_equity_before:.0%}->{hero_equity_after:.0%}({equity_delta:+.0%}) | '
        f'{"BET" if continue_bet else "CHECK"} size_x{size_mult:.2f} | '
        f'range={range_adv}'
    )

    return TextureChange(
        street=street,
        old_board=old_board,
        new_card=new_card,
        change_type=change_type,
        hero_equity_before=round(hero_equity_before, 3),
        hero_equity_after=round(hero_equity_after, 3),
        equity_delta=equity_delta,
        size_multiplier=round(size_mult, 2),
        size_reasoning=size_reason,
        range_advantage=range_adv,
        should_continue_betting=continue_bet,
        continuation_reasoning=cont_reason,
        key_adjustments=adjustments,
        one_liner=one_liner,
    )


def texture_change_one_liner(result: TextureChange) -> str:
    return result.one_liner
