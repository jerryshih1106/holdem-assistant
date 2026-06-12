"""
Nash equilibrium push/fold for 6-max cash and tournament play.

Strategy: at ≤25bb effective stack, the only correct actions are
push-all-in or fold (calling opens is generally dominated).

Data source: approximate Nash equilibrium solutions (Holdem Resources
Calculator / ICMIZER methodology) for 6-max with standard blind structure.

Positions: UTG, HJ, CO, BTN, SB  (BB only calls vs pushes)
"""

from typing import Dict, FrozenSet, List, Set, Tuple

# ── 169 distinct hands in push-priority order ──────────────────────────────
# Sorted strongest-to-weakest for the purpose of PUSHING (not just equity).
# This ordering differs from regular hand ranking:
# suited aces push slightly before medium pairs at deeper stacks (fold equity).

PUSH_ORDER: List[str] = [
    # Premium pairs
    'AA','KK','QQ','JJ','TT',
    # Big aces
    'AKs','AKo',
    # Strong pairs + aces
    '99','AQs','AQo','AJs','88','KQs','AJo',
    'ATs','77','A9s','KJs','ATo','KQo',
    '66','A8s','KTs','A9o','QJs',
    'A7s','KJo','A8o','55',
    # Medium hands
    'K9s','A6s','QTs','A7o','KTo',
    'A5s','JTs','44','A6o',
    'K8s','A4s','Q9s','A5o',
    'J9s','K9o','A3s','T9s','A4o',
    '33','K7s','A2s','Q8s','A3o','K8o','QJo',
    'J8s','Q9o','A2o',
    'K6s','22','T8s','98s','J9o','K7o',
    # Weaker hands
    'K5s','QTo','Q7s','87s','J8o','97s','T8o','K6o',
    'K4s','JTo','Q8o','86s','T9o','K5o',
    '76s','K3s','J7s','T7s','98o','Q6s','K4o',
    '96s','87o','85s','Q5s','K3o',
    '75s','J7o','K2s','65s','Q7o','T6s','97o',
    'Q4s','86o','K2o','95s','Q6o','64s',
    'Q3s','54s','J6s','76o','84s','74s',
    'Q5o','T7o','Q2s','J5s','96o','53s',
    '65o','63s','85o','Q4o','T5s','J6o',
    '75o','94s','43s','Q3o','73s','J4s',
    '52s','T6o','64o','Q2o','93s','94o','84o',
    '42s','J5o','95o','83s','83o','54o','74o',
    'J4o','32s','T5o','62s','J3s','53o',
    '92s','73o','93o','T4s','J3o','63o',
    'J2s','T3s','43o','82s','52o','T4o',
    'J2o','72s','42o','32o','T3o','62o',
    'T2s','72o','92o','T2o','82o',
]

assert len(PUSH_ORDER) == 169, f"Expected 169 hands, got {len(PUSH_ORDER)}"

_PUSH_INDEX: Dict[str, int] = {h: i for i, h in enumerate(PUSH_ORDER)}


# ── push range cutoffs: top-N% by position × stack depth ──────────────────
# Format: {position: [(max_stack_bb, percent_of_169_hands), ...]}
# The first entry whose max_stack_bb >= effective_stack is used.

PUSH_CUTOFFS: Dict[str, List[Tuple[float, float]]] = {
    #         stack:    5     7     10    13    17    22    inf
    'BTN': [(5, 1.00),(7,.88),(10,.70),(13,.55),(17,.44),(22,.34),(999,.24)],
    'CO':  [(5, .96),(7,.80),(10,.60),(13,.46),(17,.35),(22,.25),(999,.17)],
    'HJ':  [(5, .88),(7,.72),(10,.52),(13,.38),(17,.28),(22,.19),(999,.12)],
    'UTG': [(5, .80),(7,.63),(10,.44),(13,.30),(17,.20),(22,.13),(999,.08)],
    'SB':  [(5,1.00),(7,.85),(10,.68),(13,.54),(17,.43),(22,.33),(999,.23)],
}

# BB calling range vs a push (tighter = more conservative)
BB_CALL_CUTOFFS: List[Tuple[float, float]] = [
    (5, .55),(7,.40),(10,.28),(13,.20),(17,.15),(22,.10),(999,.07),
]


def _cutoff_pct(cutoffs: List[Tuple[float, float]], stack_bb: float) -> float:
    for max_stack, pct in cutoffs:
        if stack_bb <= max_stack:
            return pct
    return cutoffs[-1][1]


def push_range(position: str, stack_bb: float) -> FrozenSet[str]:
    """Return the set of hands that should be pushed from this position/stack."""
    pos = position.upper()
    cuts = PUSH_CUTOFFS.get(pos, PUSH_CUTOFFS['UTG'])
    pct  = _cutoff_pct(cuts, stack_bb)
    n    = max(1, round(pct * 169))
    return frozenset(PUSH_ORDER[:n])


def bb_call_range(stack_bb: float) -> FrozenSet[str]:
    """BB calling range when facing an all-in push."""
    pct = _cutoff_pct(BB_CALL_CUTOFFS, stack_bb)
    n   = max(1, round(pct * 169))
    return frozenset(PUSH_ORDER[:n])


def should_push(hand: str, position: str, stack_bb: float) -> bool:
    return hand in push_range(position, stack_bb)


def push_rank(hand: str) -> int:
    """0 = best push hand (AA), 168 = worst.  Returns 999 if hand unknown."""
    return _PUSH_INDEX.get(hand, 999)


def push_advice(hand: str, position: str, stack_bb: float) -> dict:
    """Full recommendation for a hand in the push/fold spot."""
    rng  = push_range(position, stack_bb)
    call = bb_call_range(stack_bb)
    pct  = len(rng) / 169 * 100

    in_push  = hand in rng
    in_call  = hand in call
    rank     = push_rank(hand)

    if stack_bb > 25:
        return {
            'action':   'NORMAL PLAY',
            'in_range': False,
            'note':     f'Stack {stack_bb:.0f}bb — use full strategy, not push/fold',
            'range_pct': pct,
        }

    action = 'PUSH' if in_push else 'FOLD'
    note_parts = []
    if in_push:
        note_parts.append(f'Push rank #{rank+1}/169')
    if in_call and not in_push:
        note_parts.append('BB would call with this hand')
    elif not in_call and in_push:
        note_parts.append('BB likely folds — good fold equity')

    return {
        'action':    action,
        'in_range':  in_push,
        'push_rank': rank,
        'range_pct': pct,
        'bb_calls':  in_call,
        'note':      ' | '.join(note_parts) if note_parts else '',
    }


def push_range_percent(position: str, stack_bb: float) -> float:
    return len(push_range(position, stack_bb)) / 169 * 100
