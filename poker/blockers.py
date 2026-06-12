"""
Blocker / unblock analysis.

Given hero's hole cards and an estimated opponent range, compute:
  - Which value combos the hero's hand blocks (reduces)
  - Which bluff-fold combos the hero's hand unblocks
  - A bluff quality score and call quality score

Useful for river decisions: "should I bluff / should I call?"

Terminology:
  BLOCK  = hero has a card that opponent needs → fewer combos of that hand exist
  UNBLOCK = hero does NOT have that card → those combos still fully exist
"""

from typing import Dict, List, Tuple
from collections import defaultdict

RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
SUITS = ['h','d','c','s']

# Approximate category groupings of hands (suit-independent notation)
HAND_CATEGORIES = {
    'top_pair_plus': ['AA','KK','QQ','JJ','TT','99','88','AKs','AKo','AQs','AQo'],
    'strong_draws':  ['AJs','ATs','KQs','QJs','JTs','T9s','98s'],
    'weak_aces':     ['A2s','A3s','A4s','A5s','A6s','A7s','A8s','A9s'],
    'bluff_hands':   ['K5s','K4s','K3s','Q5s','Q4s','Q3s','J5s','T5s'],
}


def _card_key(card: str) -> Tuple[str, str]:
    """Return (rank, suit) for a card string like 'Ah'."""
    return card[:-1].upper(), card[-1].lower()


def _rank_of(card: str) -> str:
    return card[:-1].upper()


def _suit_of(card: str) -> str:
    return card[-1].lower()


def all_combos(hand: str) -> List[Tuple[str, str]]:
    """
    Return all 2-card combos for a hand category string.
    e.g. 'AKs' → [(Ah,Kh),(Ad,Kd),(Ac,Kc),(As,Ks)]
         'AKo' → all 12 offsuit combos
         'AA'  → all 6 pair combos
    """
    if len(hand) == 2:            # pair
        r = hand[0]
        cards = [r + s for s in SUITS]
        return [(cards[i], cards[j]) for i in range(4) for j in range(i+1, 4)]

    r1, r2, stype = hand[0], hand[1], hand[2]
    c1 = [r1 + s for s in SUITS]
    c2 = [r2 + s for s in SUITS]
    if stype == 's':
        return [(c1[i], c2[i]) for i in range(4)]
    else:
        return [(a, b) for a in c1 for b in c2 if _suit_of(a) != _suit_of(b)]


def blocked_fraction(hand: str, hero_cards: List[str]) -> float:
    """
    What fraction of combos of 'hand' does hero's holding remove?
    0.0 = none blocked, 1.0 = all blocked.
    """
    hero_set = {c.strip() for c in hero_cards}
    all_c    = all_combos(hand)
    if not all_c:
        return 0.0
    blocked  = sum(1 for a, b in all_c if a in hero_set or b in hero_set)
    return blocked / len(all_c)


def blocker_report(
    hero_cards: List[str],
    community_cards: List[str],
    opponent_value_hands: List[str],
    opponent_bluff_hands: List[str],
) -> dict:
    """
    Analyse blocker effects for a river decision.

    Args:
        hero_cards:            hero's 2 hole cards
        community_cards:       board cards (typically 5 on river)
        opponent_value_hands:  hand strings we're worried about (e.g. ['AKs','AQs'])
        opponent_bluff_hands:  hand strings we hope opponent has (bluffs/weak)

    Returns dict with:
        value_block_pct   — how much hero reduces opponent's value combos (0-1)
        bluff_unblock_pct — how much of opponent's bluff range is UNBLOCKED (0-1)
        bluff_score       — higher → better bluffing hand for hero
        call_score        — higher → better calling hand for hero
        top_blocked       — which value hands are most blocked
        note              — strategic note
    """
    known = set(hero_cards) | set(community_cards)

    # Value blocking: hero blocks some of opponent's value combos → good for bluffing
    v_fracs = [(h, blocked_fraction(h, hero_cards)) for h in opponent_value_hands]
    avg_value_block = (
        sum(f for _, f in v_fracs) / len(v_fracs) if v_fracs else 0.0
    )

    # Bluff unblocking: hero does NOT hold cards in opponent's bluff hands
    # → those bluffs still exist in villain's range → villain more likely to fold
    b_fracs = [(h, 1.0 - blocked_fraction(h, hero_cards)) for h in opponent_bluff_hands]
    avg_bluff_unblock = (
        sum(f for _, f in b_fracs) / len(b_fracs) if b_fracs else 0.0
    )

    # Bluff score = high unblock (opponent can fold) + high value block (less likely they call)
    bluff_score = 0.5 * avg_bluff_unblock + 0.5 * avg_value_block

    # Call score = low value block (opponent has fewer strong hands when they bet)
    # Inversely: if we block their value, calling is WORSE (they have less bluff)
    # Actually: call is good when we UNblock their bluffs
    call_score  = avg_bluff_unblock

    top_blocked = sorted(v_fracs, key=lambda x: -x[1])[:3]

    # Strategic note
    notes = []
    if avg_value_block > 0.4:
        notes.append('Good blocker for a bluff — you reduce their value')
    if avg_bluff_unblock > 0.7:
        notes.append('You unblock their bluffs — good fold equity when bluffing')
    elif avg_bluff_unblock < 0.3:
        notes.append('You block their bluffs — calling is better than bluffing')
    if call_score > 0.6:
        notes.append('Strong call vs villain\'s bluffs')
    if not notes:
        notes.append('Neutral blockers — consider hand strength primarily')

    return {
        'value_block_pct':   avg_value_block,
        'bluff_unblock_pct': avg_bluff_unblock,
        'bluff_score':       bluff_score,
        'call_score':        call_score,
        'top_blocked':       top_blocked,
        'note':              ' | '.join(notes),
    }


# ── Convenience: common river scenarios ───────────────────────────────────────

def river_decision(
    hero_cards: List[str],
    community_cards: List[str],
    pot: int,
    bet_size: int,
    hero_equity: float,
) -> dict:
    """
    Combine equity, pot odds and blocker analysis for a river call/fold decision.
    Uses simplified opponent range assumptions based on board cards.
    """
    from poker.ranges import RANKS as R_RANKS

    # Infer rough villain value/bluff range from board
    board_ranks = [c[:-1].upper() for c in community_cards]

    # Value: top-pair+, two-pair+, sets (simplified)
    value_hands = ['AA','KK','QQ','JJ','TT','AKs','AKo','AQs','AQo']
    # Bluffs: busted draws, weak aces
    bluff_hands = ['A5s','A4s','A3s','A2s','K5s','K4s','Q5s','Q4s']

    report = blocker_report(hero_cards, community_cards, value_hands, bluff_hands)

    pot_odds = bet_size / (pot + bet_size) if (pot + bet_size) > 0 else 0.5
    ev_call  = hero_equity - pot_odds

    action = 'CALL' if ev_call > 0 or report['call_score'] > 0.65 else 'FOLD'

    return {
        **report,
        'pot_odds':  pot_odds,
        'hero_equity': hero_equity,
        'ev_call':   ev_call,
        'action':    action,
    }
