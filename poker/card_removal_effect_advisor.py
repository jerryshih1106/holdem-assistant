"""
Card Removal Effect Advisor (card_removal_effect_advisor.py)

Analyzes how hero's hole cards BLOCK villain's value ranges and bluffs,
affecting the EV of calling, folding, and bluffing decisions.

THEORY:
  CARD REMOVAL = hero's cards reduce the probability villain holds specific hands.

  IMPACT ON CALLING DECISIONS:
  - If hero holds an Ace, villain has FEWER AA/AK/Ax combos
  - Reduces villain's value range -> hero's call is more profitable
  - Example: Hero A8 facing river bet. Villain less likely to have AA/AK/AQ.

  IMPACT ON BLUFFING DECISIONS:
  - If hero blocks villain's CONTINUING range, bluffs more profitable
  - Blockers to flushes make bluff-raises better (villain less likely to have flush)
  - If hero DOES NOT block value range, villain's value range is fuller -> fold less

  COMBO COUNT ADJUSTMENTS:
  - Full combos (no blockers): AA=6, AKs=4, AKo=12
  - With one Ace in hand: AA=3 (from 6), AKs=3 (from 4), AKo=9 (from 12)
  - With two Aces in hand: impossible; card removal = removes specific combos

  BLOCKER EFFECT SCORE:
  - Score 1-10 measuring how much hero's hand blocks villain's range
  - High score (7-10): significant range reduction -> good call/bluff spot
  - Low score (1-3):   minimal blocking -> villain's range intact
  - Medium (4-6):      partial reduction

  PRACTICAL APPLICATIONS:
  1. River call: If hero blocks villain's value range, call more often
  2. River bluff: Hero should bluff more when blocking calling range
  3. Fold: If hero doesn't block value, villain's value combos are full -> fold more

DISTINCT FROM:
  blockers.py:         General blocker concepts
  river_xr_bluff.py:  XR bluff with blocker score
  bluff_selection_advisor.py: General bluff selection
  THIS MODULE:         QUANTIFIED combo count reduction; specific blocker scores
                       per hand type; call/fold/bluff EV adjustment from blockers.
"""

from dataclasses import dataclass, field
from typing import List, Dict


BASE_COMBOS: dict = {
    'AA':   6, 'KK':   6, 'QQ':   6, 'JJ':   6, 'TT':   6,
    '99':   6, '88':   6, '77':   6,
    'AKs':  4, 'AQs':  4, 'AJs':  4, 'ATs':  4,
    'KQs':  4, 'KJs':  4, 'QJs':  4, 'JTs':  4, 'T9s':  4,
    'AKo': 12, 'AQo': 12, 'KQo': 12,
    'flush':   9,   # generic flush combos
    'straight': 8,   # OESD combos
    'two_pair': 12,
    'trips':    3,
}

BLOCKER_VALUES: dict = {
    # hero_card_rank -> which villain hand categories it blocks and by how much
    'A': {'pairs_of_A': 0.50, 'AKs': 0.75, 'AKo': 0.75, 'AQs': 0.75, 'AA': 0.50, 'AJs': 0.75},
    'K': {'pairs_of_K': 0.50, 'AKs': 0.75, 'AKo': 0.75, 'KQs': 0.75, 'KK': 0.50, 'KJs': 0.75},
    'Q': {'pairs_of_Q': 0.50, 'AQs': 0.75, 'KQs': 0.75, 'QQ': 0.50, 'QJs': 0.75},
    'J': {'pairs_of_J': 0.50, 'AJs': 0.75, 'KJs': 0.75, 'JJ': 0.50, 'QJs': 0.75, 'JTs': 0.75},
    'T': {'pairs_of_T': 0.50, 'TT': 0.50, 'JTs': 0.75, 'T9s': 0.75},
}

SUITED_BLOCKER: dict = {
    'hearts':   0.25,
    'diamonds': 0.25,
    'clubs':    0.25,
    'spades':   0.25,
}


def _rank_from_card(card: str) -> str:
    """Extract rank from card string like 'Ah', 'Kd'."""
    if len(card) >= 1:
        return card[0].upper()
    return ''


def _suit_from_card(card: str) -> str:
    """Extract suit from card string like 'Ah', 'Kd'."""
    if len(card) >= 2:
        return card[1].lower()
    return ''


def _combo_reduction(hero_cards: list, villain_hand_type: str) -> float:
    """
    Return fraction of villain's combos that remain after card removal.
    1.0 = no reduction; 0.5 = half removed.
    """
    reduction = 1.0
    for card in hero_cards:
        rank = _rank_from_card(card)
        if rank in BLOCKER_VALUES:
            blockers = BLOCKER_VALUES[rank]
            if villain_hand_type in blockers:
                reduction *= (1.0 - blockers[villain_hand_type] * 0.5)
    return round(max(0.05, min(1.0, reduction)), 3)


def _blocker_score(hero_cards: list, villain_range_type: str) -> int:
    """Score 1-10: how strongly hero blocks villain's range."""
    ranks = [_rank_from_card(c) for c in hero_cards]
    score = 3  # base

    # High-card blockers vs value-heavy ranges
    if villain_range_type in ('value_heavy', 'nutted'):
        ace_count  = ranks.count('A')
        king_count = ranks.count('K')
        score += ace_count * 2 + king_count * 1

    # Suited blockers vs flush-heavy ranges
    if villain_range_type in ('draw_heavy', 'flush_heavy'):
        suits = [_suit_from_card(c) for c in hero_cards]
        if len(set(suits)) < len(suits):  # suited cards
            score += 2

    # No high cards = low blocker score vs value ranges
    if villain_range_type == 'value_heavy' and 'A' not in ranks and 'K' not in ranks:
        score -= 2

    return max(1, min(10, score))


def _call_ev_adjustment(
    pot_bb: float,
    call_bb: float,
    base_villain_fold: float,
    combo_reduction_factor: float,
) -> float:
    """
    Adjustment to call EV from blocker effect.
    If combos reduced, villain's value range is weaker -> call is better.
    Returns delta_EV (additional EV from blocking).
    """
    effective_fold = min(1.0, base_villain_fold / combo_reduction_factor)
    delta_fold = effective_fold - base_villain_fold
    return round(delta_fold * pot_bb, 2)


def _bluff_ev_adjustment(
    pot_bb: float,
    bet_bb: float,
    base_villain_fold: float,
    calling_range_reduction: float,
) -> float:
    """EV boost to hero's bluff from blocking villain's calling range."""
    effective_fold = min(0.95, base_villain_fold * (1.0 / max(0.05, calling_range_reduction)))
    fold_ev = effective_fold * pot_bb
    call_ev = (1.0 - effective_fold) * (-bet_bb)
    base_ev = base_villain_fold * pot_bb - (1.0 - base_villain_fold) * bet_bb
    return round(fold_ev + call_ev - base_ev, 2)


@dataclass
class CardRemovalResult:
    hero_cards: list
    villain_range_type: str

    combo_reduction: float
    blocker_score: int

    call_ev_adjustment_bb: float
    bluff_ev_adjustment_bb: float

    recommended_adjustment: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_card_removal(
    hero_cards: list = None,
    villain_range_type: str = 'value_heavy',
    pot_bb: float = 20.0,
    call_size_bb: float = 8.0,
    base_villain_fold: float = 0.45,
    action_type: str = 'call',
) -> CardRemovalResult:
    """
    Analyze card removal effects from hero's hole cards.

    Args:
        hero_cards:         Hero's cards (e.g. ['Ah', 'Ks'])
        villain_range_type: Villain range ('value_heavy','draw_heavy','nutted',
                            'flush_heavy','balanced')
        pot_bb:             Current pot in BB
        call_size_bb:       Size of call/bet in BB
        base_villain_fold:  Villain's baseline fold % (without blocker adjustment)
        action_type:        Decision context ('call', 'bluff', 'fold')

    Returns:
        CardRemovalResult
    """
    if hero_cards is None:
        hero_cards = ['Ah', '5s']

    # Use first villain hand type for combo reduction
    primary_type = 'AA' if villain_range_type == 'nutted' else \
                   'AKs' if villain_range_type == 'value_heavy' else \
                   'flush' if villain_range_type in ('flush_heavy', 'draw_heavy') else 'AKs'

    combo_red = _combo_reduction(hero_cards, primary_type)
    score = _blocker_score(hero_cards, villain_range_type)

    call_adj = _call_ev_adjustment(pot_bb, call_size_bb, base_villain_fold, combo_red)
    bluff_adj = _bluff_ev_adjustment(pot_bb, call_size_bb, base_villain_fold, combo_red)

    if action_type == 'call':
        adj_label = f'call_adj={call_adj:+.2f}BB'
        if call_adj >= 0.5:
            rec = 'CALL_STRONGER'
        elif call_adj >= -0.3:
            rec = 'CALL_NEUTRAL'
        else:
            rec = 'FOLD_BLOCKER_WEAK'
    elif action_type == 'bluff':
        adj_label = f'bluff_adj={bluff_adj:+.2f}BB'
        if score >= 6:
            rec = 'BLUFF_FAVORABLE_BLOCKERS'
        elif score >= 4:
            rec = 'BLUFF_MARGINAL_BLOCKERS'
        else:
            rec = 'BLUFF_POOR_BLOCKERS'
    else:
        adj_label = f'blocker_score={score}/10'
        rec = 'FOLD_ASSESS_BLOCKERS' if score <= 4 else 'CONSIDER_BLUFF_CATCH'

    cards_str = '+'.join(hero_cards)

    verdict = (
        f'[CRE {cards_str}|{villain_range_type}|{action_type}] '
        f'combo_reduction={combo_red:.2f} score={score}/10 {adj_label}'
    )

    reasoning = (
        f'Card removal: hero holds {cards_str} vs {villain_range_type} range. '
        f'Combo reduction factor: {combo_red:.2f} '
        f'({(1-combo_red)*100:.0f}% of villain combos blocked). '
        f'Blocker score: {score}/10. '
        f'Action: {rec}.'
    )

    tips = []

    block_pct = round((1.0 - combo_red) * 100)
    tips.append(
        f'BLOCKER EFFECT: Hero blocks ~{block_pct}% of villain {villain_range_type} combos. '
        f'Blocker score: {score}/10. '
        f'{"Strong blocker -- adjust action toward {action_type}." if score >= 6 else "Weak blocker -- villain range largely intact."}'
    )

    tips.append(
        f'ACTION ADJUSTMENT: {rec}. '
        f'{"Call EV boost: " + str(call_adj) + "BB from blocking villain value range." if action_type == "call" else "Bluff EV boost: " + str(bluff_adj) + "BB from blocking villain calling range." if action_type == "bluff" else "Assess blockers before deciding."}'
    )

    ranks = [_rank_from_card(c) for c in hero_cards]
    if 'A' in ranks:
        tips.append(
            f'ACE BLOCKER: Holding an Ace removes AA/AK/Ax combos from villain range. '
            f'Villain less likely to have AA, AK, AQ -- improves call/bluff profitability.'
        )
    if villain_range_type in ('flush_heavy', 'draw_heavy'):
        suits = [_suit_from_card(c) for c in hero_cards]
        tips.append(
            f'SUIT BLOCKERS: Hero cards in suits {"+".join(suits)}. '
            f'Blocks some flush combos in villain range. '
            f'{"Both suited -- strong flush blocker." if len(set(suits)) == 1 else "One suited blocker -- partial flush block."}'
        )

    return CardRemovalResult(
        hero_cards=hero_cards,
        villain_range_type=villain_range_type,
        combo_reduction=combo_red,
        blocker_score=score,
        call_ev_adjustment_bb=call_adj,
        bluff_ev_adjustment_bb=bluff_adj,
        recommended_adjustment=rec,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def cre_one_liner(r: CardRemovalResult) -> str:
    return (
        f'[CRE {"+".join(r.hero_cards)}|{r.villain_range_type}] '
        f'score={r.blocker_score}/10 reduction={r.combo_reduction:.2f} '
        f'{r.recommended_adjustment}'
    )
