"""
Preflop Hand Bucketing (preflop_hand_bucketing.py)

Categorizes all 169 starting hand combinations into strategic action buckets
(3-bet, flat-call, open-raise, fold, jam) for a given scenario. Unlike
modules that evaluate a single hand, this module produces the COMPLETE
range strategy for a position+situation.

KEY INSIGHT: A poker player's preflop strategy should divide their range into:
  1. VALUE 3-BET:    Strong hands that want to build the pot (AA, KK, QQ, AKs)
  2. BLUFF 3-BET:    Hands with blockers/equity to balance value (A5s, A4s, K5s)
  3. FLAT CALL:      Medium-strength hands that play well post-flop (KQo, JTs, 99-77)
  4. OPEN RAISE:     Hands to open with when facing no action
  5. JAM:            Short stack push/fold (20BB or less)
  6. FOLD:           All other hands

STACK DEPTH EFFECTS:
  200BB+: More flat-calling; implied odds maximize; few 3-bets with middling hands
  100BB:  Standard GTO 3-bet/call ratios
  50-80BB: More 3-betting; less flat-calling (pot commitments change)
  25-40BB: Mostly open-jam or fold; limited calling range
  <20BB:  Pure push/fold (Nash equilibrium)

POSITION EFFECTS:
  UTG: Tightest range; only premium opens; 3-bet mostly for value
  BTN: Widest opens; can 3-bet bluff more; flat wider
  SB:  3-bet or fold vs BTN opens; rarely flat OOP
  BB:  Defend wide; 3-bet for value+some bluffs; flat often (already in)

DISTINCT FROM:
  preflop_advisor.py:       Evaluates a specific hand
  hand_percentile.py:       Ranks hand strength within a range
  THIS MODULE:              Generates complete range breakdowns; answers "what
                            is my ENTIRE strategy for this spot?" not just
                            "what do I do with pocket 8s?"

Usage:
    from poker.preflop_hand_bucketing import bucket_preflop_range, RangeBuckets, pbk_one_liner

    result = bucket_preflop_range(
        position='btn',
        action_facing='open',
        open_position='co',
        open_size_bb=2.5,
        hero_stack_bb=100.0,
        villain_fold_to_3bet=0.58,
        villain_vpip=0.28,
    )
    print(pbk_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List


# Hand group definitions (approximate % of combos)
HAND_GROUPS = {
    'premium_pairs':     ('AA, KK', 1.2),
    'strong_pairs':      ('QQ, JJ', 1.2),
    'medium_pairs':      ('TT, 99', 1.2),
    'small_pairs':       ('88-22',  3.0),
    'ace_king':          ('AKs, AKo', 2.0),
    'ace_queen':         ('AQs, AQo', 2.0),
    'ace_jack':          ('AJs, AJo', 2.0),
    'ace_ten':           ('ATs, ATo', 2.0),
    'small_suited_aces': ('A9s-A2s',  3.2),
    'offsuit_aces':      ('A9o-A2o',  4.8),
    'king_queen':        ('KQs, KQo', 2.0),
    'king_jack':         ('KJs, KJo', 2.0),
    'king_ten':          ('KTs, KTo', 2.0),
    'small_kings':       ('K9s-K2s',  3.2),
    'broadway':          ('QJs, QJo, JTs, JTo', 4.0),
    'suited_connectors': ('T9s-54s',  4.5),
    'offsuit_connectors':('T9o-54o',  4.5),
    'suited_gappers':    ('T8s-53s',  4.5),
    'trash':             ('rest',    48.3),
}


def _stack_regime(stack_bb: float) -> str:
    if stack_bb <= 20:
        return 'push_fold'
    elif stack_bb <= 35:
        return 'short'
    elif stack_bb <= 60:
        return 'medium_short'
    elif stack_bb <= 130:
        return 'standard'
    else:
        return 'deep'


def _position_aggression(position: str) -> float:
    """Opening range width factor (higher = wider range)."""
    return {
        'utg': 0.12,
        'utg1': 0.14,
        'mp': 0.18,
        'lj': 0.20,
        'hj': 0.22,
        'co': 0.27,
        'btn': 0.44,
        'sb': 0.40,
        'bb': 0.70,
    }.get(position.lower(), 0.25)


def _threbet_range(position: str, action_facing: str, stack_regime: str,
                    villain_fold_to_3bet: float) -> Dict[str, str]:
    """
    Returns hand groups -> action bucket for 3-bet range.
    """
    buckets = {}
    bluff_profitable = villain_fold_to_3bet >= 0.55

    if stack_regime == 'push_fold':
        # Jam = squeeze; treat jamming as 3-bet equivalent
        buckets['premium_pairs'] = '3bet_value'
        buckets['strong_pairs'] = '3bet_value'
        buckets['ace_king'] = '3bet_value'
        buckets['medium_pairs'] = '3bet_value' if villain_fold_to_3bet >= 0.50 else 'flat'
        buckets['small_suited_aces'] = '3bet_bluff' if bluff_profitable else 'fold'
        return buckets

    # Standard depth
    buckets['premium_pairs'] = '3bet_value'
    buckets['strong_pairs'] = '3bet_value' if action_facing in ('open', 'no_action') else '3bet_value'
    buckets['ace_king'] = '3bet_value'

    if position in ('sb', 'bb'):
        buckets['ace_queen'] = '3bet_value'    # OOP: 3-bet don't flat
        buckets['ace_jack'] = '3bet_bluff' if position == 'sb' else 'flat'
    else:
        buckets['ace_queen'] = '3bet_value' if action_facing == 'open' else '3bet_value'
        buckets['ace_jack'] = 'flat' if position in ('co', 'btn') else '3bet_value'

    if bluff_profitable:
        buckets['small_suited_aces'] = '3bet_bluff'   # A2s-A5s: blocker 3-bets
        buckets['medium_pairs'] = 'flat' if stack_regime == 'deep' else '3bet_value'
        if position in ('btn', 'co', 'sb'):
            buckets['small_kings'] = '3bet_bluff'     # K2s-K5s: blocker bluffs
    else:
        buckets['small_suited_aces'] = 'flat' if position in ('btn', 'co') else 'fold'
        buckets['medium_pairs'] = 'flat'

    return buckets


def _bucket_all_hands(
    position: str,
    action_facing: str,
    stack_regime: str,
    villain_fold_to_3bet: float,
    villain_vpip: float,
    open_size_bb: float,
) -> Dict[str, str]:
    """
    Returns complete hand group -> bucket mapping.
    """
    b = {}
    tb = _threbet_range(position, action_facing, stack_regime, villain_fold_to_3bet)
    pos_agg = _position_aggression(position)

    # Apply 3-bet buckets from threbet_range
    for hand, action in tb.items():
        b[hand] = action

    # Fill remaining by category
    def _get(hand):
        return b.get(hand)

    # Strong/medium pairs
    if not _get('strong_pairs'):
        b['strong_pairs'] = '3bet_value'
    if not _get('medium_pairs'):
        b['medium_pairs'] = 'flat' if action_facing in ('open',) else 'open'
    if not _get('small_pairs'):
        b['small_pairs'] = 'flat' if (
            action_facing == 'open' and open_size_bb <= 3.5
        ) else 'fold'

    # Ace hands
    if not _get('ace_queen'):
        b['ace_queen'] = '3bet_value'
    if not _get('ace_jack'):
        b['ace_jack'] = 'flat' if position in ('btn', 'co') else ('3bet_value' if action_facing == 'no_action' else 'fold')
    if not _get('ace_ten'):
        b['ace_ten'] = 'flat' if pos_agg >= 0.25 else ('open' if action_facing == 'no_action' else 'fold')
    if not _get('offsuit_aces'):
        b['offsuit_aces'] = 'fold' if action_facing == 'open' else ('open' if pos_agg >= 0.35 else 'fold')

    # King hands
    if not _get('king_queen'):
        b['king_queen'] = 'flat' if action_facing == 'open' else 'open'
    if not _get('king_jack'):
        b['king_jack'] = 'flat' if (pos_agg >= 0.25 and action_facing == 'open') else ('open' if pos_agg >= 0.20 else 'fold')
    if not _get('king_ten'):
        b['king_ten'] = 'flat' if (pos_agg >= 0.40 and action_facing == 'open') else ('open' if pos_agg >= 0.27 else 'fold')
    if not _get('small_kings'):
        b['small_kings'] = ('3bet_bluff' if villain_fold_to_3bet >= 0.65 and pos_agg >= 0.40
                           else 'fold')

    # Broadway/connectors
    b['broadway'] = 'flat' if (pos_agg >= 0.25 and action_facing == 'open') else ('open' if pos_agg >= 0.22 else 'fold')
    b['suited_connectors'] = 'flat' if (
        action_facing == 'open' and open_size_bb <= 4.0 and pos_agg >= 0.25
    ) else ('open' if pos_agg >= 0.35 else 'fold')
    b['offsuit_connectors'] = 'fold' if action_facing == 'open' else ('open' if pos_agg >= 0.40 else 'fold')
    b['suited_gappers'] = 'flat' if (pos_agg >= 0.40 and action_facing == 'open' and open_size_bb <= 3.5) else 'fold'
    b['trash'] = 'fold'

    # Override for push_fold regime
    if stack_regime == 'push_fold':
        for hand in b:
            if b[hand] in ('flat', 'open'):
                b[hand] = 'fold'  # no flat-calls at push/fold stacks
        # Allow opens as jams
        b['medium_pairs'] = 'jam'
        b['ace_ten'] = 'jam' if pos_agg >= 0.35 else 'fold'
        b['king_queen'] = 'jam'
        b['broadway'] = 'jam' if pos_agg >= 0.40 else 'fold'

    return b


def _count_buckets(buckets: Dict[str, str]) -> Dict[str, float]:
    """Estimate % of range in each bucket based on combo weights."""
    counts = {'3bet_value': 0.0, '3bet_bluff': 0.0, 'flat': 0.0,
              'open': 0.0, 'jam': 0.0, 'fold': 0.0}
    total = 0.0
    for hand_group, action in buckets.items():
        weight = HAND_GROUPS.get(hand_group, ('', 0))[1]
        if action in counts:
            counts[action] += weight
        total += weight
    # Normalize
    return {k: round(v / max(total, 1.0), 3) for k, v in counts.items()}


@dataclass
class RangeBuckets:
    # Inputs
    position: str
    action_facing: str
    open_position: str
    open_size_bb: float
    hero_stack_bb: float
    villain_fold_to_3bet: float
    villain_vpip: float

    # Strategy
    stack_regime: str           # 'push_fold' / 'short' / 'standard' / 'deep'
    hand_buckets: Dict[str, str]  # hand_group -> action bucket
    bucket_pcts: Dict[str, float] # bucket -> % of range

    # Key ranges
    value_3bet_range: str       # description of hands to 3-bet for value
    bluff_3bet_range: str       # description of hands to 3-bet as bluff
    flat_call_range: str        # description of hands to flat-call
    open_range_pct: float       # % of hands to open when first to act

    verdict: str
    tips: List[str] = field(default_factory=list)


def bucket_preflop_range(
    position: str = 'btn',
    action_facing: str = 'open',
    open_position: str = 'co',
    open_size_bb: float = 2.5,
    hero_stack_bb: float = 100.0,
    villain_fold_to_3bet: float = 0.55,
    villain_vpip: float = 0.28,
) -> RangeBuckets:
    """
    Generate complete preflop range strategy buckets.

    Args:
        position:           Hero's position ('utg'/'mp'/'co'/'btn'/'sb'/'bb')
        action_facing:      'no_action' (first to act) / 'open' (vs opener) / '3bet' (vs 3-bet)
        open_position:      Opener's position (relevant when action_facing='open')
        open_size_bb:       Size of opening raise when facing one
        hero_stack_bb:      Effective stack in BBs
        villain_fold_to_3bet: Villain's fold-to-3bet frequency
        villain_vpip:       Villain's VPIP

    Returns:
        RangeBuckets
    """
    regime = _stack_regime(hero_stack_bb)
    buckets = _bucket_all_hands(
        position, action_facing, regime, villain_fold_to_3bet, villain_vpip, open_size_bb
    )
    pcts = _count_buckets(buckets)

    # Narrative summaries
    value_hands = [h for h, a in buckets.items() if a == '3bet_value']
    bluff_hands = [h for h, a in buckets.items() if a == '3bet_bluff']
    flat_hands  = [h for h, a in buckets.items() if a in ('flat',)]
    open_hands  = [h for h, a in buckets.items() if a in ('open',)]

    def _desc(hands):
        return ', '.join(h.replace('_', ' ') for h in hands) if hands else 'none'

    total_3bet = round(pcts.get('3bet_value', 0) + pcts.get('3bet_bluff', 0), 3)
    total_flat = round(pcts.get('flat', 0), 3)
    total_fold = round(pcts.get('fold', 0), 3)
    pos_agg = _position_aggression(position)
    open_pct = pos_agg   # approximate open range as position aggression factor

    verdict = (
        f'[PBK {position.upper()}|{action_facing}|{regime}] '
        f'3bet={total_3bet:.0%} flat={total_flat:.0%} fold={total_fold:.0%} | '
        f'f3b_villain={villain_fold_to_3bet:.0%}'
    )

    tips = []
    tips.append(
        f'3-BET RANGE ({total_3bet:.0%}): Value={_desc(value_hands)}. '
        f'Bluff={_desc(bluff_hands)}. '
        f'Villain folds {villain_fold_to_3bet:.0%} to 3-bets.'
    )

    if action_facing == 'no_action':
        tips.append(
            f'OPENING RANGE ({pos_agg:.0%} of combos from {position.upper()}): '
            f'Open: {_desc(open_hands)}. '
            f'Raise size: {"2.5BB" if position in ("btn", "co") else "3BB"} standard.'
        )
    else:
        tips.append(
            f'FLAT CALL RANGE ({total_flat:.0%}): {_desc(flat_hands)}. '
            f'These hands play well post-flop but are not strong enough to 3-bet for value '
            f'or do not have the right blockers for a bluff 3-bet.'
        )

    if regime == 'push_fold':
        tips.append(
            f'PUSH/FOLD MODE ({hero_stack_bb:.0f}BB): No flat-calls at this stack depth. '
            f'Only open-jam strong hands; fold everything else. '
            f'Use Nash push/fold charts for precise thresholds.'
        )
    elif regime == 'deep':
        tips.append(
            f'DEEP STACK ({hero_stack_bb:.0f}BB): Flat-calling more is correct deep -- '
            f'implied odds reward set-mining and suited connectors. '
            f'Reduce 3-bet bluffing; post-flop skill matters more.'
        )

    if villain_fold_to_3bet >= 0.70:
        tips.append(
            f'AGGRESSIVE 3-BET STRATEGY: Villain folds {villain_fold_to_3bet:.0%} to 3-bets. '
            f'Expand bluff 3-bet range significantly. Any suited ace or suited king is profitable.'
        )
    elif villain_fold_to_3bet <= 0.40:
        tips.append(
            f'TIGHTEN 3-BET RANGE: Villain calls {1-villain_fold_to_3bet:.0%} of 3-bets. '
            f'Remove all bluff 3-bets. Only 3-bet strong value hands (QQ+, AKs, AKo).'
        )

    return RangeBuckets(
        position=position,
        action_facing=action_facing,
        open_position=open_position,
        open_size_bb=open_size_bb,
        hero_stack_bb=hero_stack_bb,
        villain_fold_to_3bet=villain_fold_to_3bet,
        villain_vpip=villain_vpip,
        stack_regime=regime,
        hand_buckets=buckets,
        bucket_pcts=pcts,
        value_3bet_range=_desc(value_hands),
        bluff_3bet_range=_desc(bluff_hands),
        flat_call_range=_desc(flat_hands),
        open_range_pct=open_pct,
        verdict=verdict,
        tips=tips,
    )


def pbk_one_liner(r: RangeBuckets) -> str:
    total_3bet = round(r.bucket_pcts.get('3bet_value', 0) + r.bucket_pcts.get('3bet_bluff', 0), 2)
    return (
        f'[PBK {r.position.upper()}|{r.action_facing}|{r.stack_regime}] '
        f'3bet={total_3bet:.0%} flat={r.bucket_pcts.get("flat", 0):.0%} '
        f'fold={r.bucket_pcts.get("fold", 0):.0%} | '
        f'f3b={r.villain_fold_to_3bet:.0%}'
    )
