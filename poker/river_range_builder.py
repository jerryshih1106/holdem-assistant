"""
River Range Builder (river_range_builder.py)

Constructs a balanced polarized river betting range for hero.

Core principle: at any given bet size, the correct value:bluff ratio is:
  bluff_ratio = alpha = bet / (pot + bet)
  value_ratio = 1 - alpha = pot / (pot + bet)

  50%pot bet:  alpha=0.333 → 1 bluff per 2 value
  75%pot bet:  alpha=0.429 → 3 bluffs per 4 value
  100%pot bet: alpha=0.500 → 1 bluff per 1 value
  150%pot bet: alpha=0.600 → 3 bluffs per 2 value (overbet)
  200%pot bet: alpha=0.667 → 2 bluffs per 1 value

What goes in the VALUE betting range:
  - Hands that beat villain's calling range (nut hands, near-nuts)
  - Threshold: equity vs calling range > 50% + some margin
  - Include top 15-25% of range (at 75%pot standard sizing)

What goes in the BLUFF range:
  - Missed draws (flush draw missed, straight draw missed)
  - Hands with blockers to villain's nuts
  - Air hands with high blocker value
  - Do NOT bluff with hands that have showdown value (check those)

What to CHECK (medium hands):
  - Second pair, top pair without kicker advantage
  - Hands that beat many bluffs but lose to value → bluff-catchers
  - These are check-call candidates, not bet candidates

Usage:
    from poker.river_range_builder import build_river_range, RiverRangeAdvice
    result = build_river_range(
        hero_equity=0.72,
        hero_hand_class='flush',
        bet_size_pct=0.75,
        pot_bb=25.0,
        eff_stack_bb=75.0,
        board_type='wet',
        hero_has_nut_blocker=True,
        missed_draw=False,
    )
    print(result.category, result.recommended_action)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _alpha(bet_pct: float) -> float:
    return bet_pct / (1.0 + bet_pct)


def _bluff_to_value(bet_pct: float) -> tuple:
    """(bluffs_per_value, value_pct, bluff_pct) for given bet size."""
    a = _alpha(bet_pct)
    v = 1.0 - a
    return (a / v, v, a)


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'missed_draw': 0, 'draw': 1, 'bottom_pair': 2,
        'middle_pair': 3, 'top_pair_weak': 4, 'top_pair': 5, 'tptk': 6,
        'top_pair_strong': 6, 'overpair': 6, 'two_pair': 7, 'set': 8,
        'straight': 9, 'flush': 10, 'full_house': 11, 'quads': 12,
    }.get(hand_class.lower(), 5)


def _categorize(
    rank: int,
    hero_equity: float,
    bet_pct: float,
    hero_has_nut_blocker: bool,
    missed_draw: bool,
    board_type: str,
) -> tuple:
    """Return (category, recommended_action, bet_freq, reasoning)."""
    a = _alpha(bet_pct)
    bluffs_per_value, value_pct, bluff_pct = _bluff_to_value(bet_pct)

    # NUTTED VALUE — always bet for value
    if rank >= 9:  # straight+
        return ('nut_value', 'bet_value', 1.0,
                f'Nutted hand: always bet. eq={hero_equity:.0%} crushes calling range. '
                f'Size: {bet_pct:.0%}pot. River is the last chance for value.')

    # STRONG VALUE
    if rank >= 7:  # two pair+
        bet_freq = 0.90 if rank >= 8 else 0.75
        return ('strong_value', 'bet_value', bet_freq,
                f'Strong hand: bet {bet_freq:.0%} for value. '
                f'Mix with {1-bet_freq:.0%} check-call to balance checking range. '
                f'Hero eq={hero_equity:.0%} >> alpha={a:.0%}.')

    # BLUFF — missed draws with blockers, air with blockers
    if missed_draw and hero_has_nut_blocker:
        return ('nut_blocker_bluff', 'bet_bluff', bluff_pct,
                f'Missed draw + nut blocker: prime bluff candidate. '
                f'Bet {bluff_pct:.0%} of the time (= alpha for bet/value balance). '
                f'Blocker cuts villain calling range by ~25-40%.')

    if missed_draw and not hero_has_nut_blocker:
        bluff_freq = max(0.0, bluff_pct - 0.15)  # reduced without blocker
        return ('missed_draw_bluff', 'bet_bluff' if bluff_freq > 0.20 else 'check',
                bluff_freq,
                f'Missed draw without blocker: bluff {bluff_freq:.0%}. '
                f'Villain can have more nutted combos; reduce bluff frequency vs {bet_pct:.0%}pot bluff alpha.')

    if rank == 0 and hero_has_nut_blocker:
        return ('air_blocker_bluff', 'bet_bluff', bluff_pct * 0.60,
                f'Air with blocker: selective bluff ({bluff_pct * 0.60:.0%}). '
                f'Reserve bluff slots for missed draws first.')

    # BLUFF CATCHER — medium hands that beat bluffs but lose to value
    if 2 <= rank <= 6:
        if hero_equity >= a + 0.05:
            return ('bluff_catcher', 'check_call',
                    0.0,  # frequency to BET (0 = don't bet; check and call if bet into)
                    f'Bluff catcher: CHECK and call villain bets. '
                    f'eq={hero_equity:.0%} > alpha={a:.0%} → profitable call. '
                    f'Betting turns this hand into a bluff (villain only calls with better).')
        else:
            return ('marginal', 'check_fold',
                    0.0,
                    f'Marginal: check-fold. eq={hero_equity:.0%} < alpha={a:.0%}. '
                    f'Not profitable to call or bet. Pure showdown value hand — '
                    f'check and fold to villain bet.')

    # AIR without blocker
    return ('air_no_blocker', 'check_fold', 0.0,
            f'Air without blocker: check-fold. '
            f'Cannot profitably bluff {bet_pct:.0%}pot without blocking villain nuts.')


@dataclass
class RiverRangeAdvice:
    """River range construction advice for a specific hand."""
    # Hand context
    hero_hand_class: str
    hero_equity: float
    hero_has_nut_blocker: bool
    missed_draw: bool
    board_type: str

    # Bet sizing math
    bet_size_pct: float
    alpha: float              # fold equity villain needs
    bluff_to_value_ratio: float  # correct bluffs per value hand at this size
    value_fraction: float     # fraction of range that should be value
    bluff_fraction: float     # fraction of range that should be bluff

    # Decision
    category: str             # 'nut_value', 'strong_value', 'bluff_catcher', etc.
    recommended_action: str   # 'bet_value', 'bet_bluff', 'check_call', 'check_fold'
    bet_frequency: float      # how often to bet this hand (0-1)
    pot_bb: float
    bet_bb: float

    # Reasoning
    action_reasoning: str
    range_construction_notes: List[str] = field(default_factory=list)


def build_river_range(
    hero_equity: float,
    hero_hand_class: str,
    bet_size_pct: float,
    pot_bb: float,
    eff_stack_bb: float,
    board_type: str = 'medium',
    hero_has_nut_blocker: bool = False,
    missed_draw: bool = False,
) -> RiverRangeAdvice:
    """
    How does a specific hand fit into the correct river polarized betting range?

    Args:
        hero_equity:       Hero's equity vs villain's full range
        hero_hand_class:   Hand classification
        bet_size_pct:      Target bet size as fraction of pot (e.g., 0.75)
        pot_bb:            Current pot in BB
        eff_stack_bb:      Effective stack
        board_type:        Board texture
        hero_has_nut_blocker: Hero holds a blocker to villain's nut hands
        missed_draw:       Hero missed a draw and arrived at river with air/weak hand

    Returns:
        RiverRangeAdvice
    """
    a = _alpha(bet_size_pct)
    bv_ratio, v_pct, b_pct = _bluff_to_value(bet_size_pct)
    rank = _hand_rank(hero_hand_class)
    bet_bb = round(pot_bb * bet_size_pct, 1)

    category, action, bet_freq, reasoning = _categorize(
        rank, hero_equity, bet_size_pct, hero_has_nut_blocker,
        missed_draw, board_type,
    )

    notes = [
        f'River bet {bet_size_pct:.0%}pot: alpha={a:.0%}, value fraction={v_pct:.0%}, '
        f'bluff fraction={b_pct:.0%}.',
        f'Correct ratio: for every {1:.0f} bluff, have {1/bv_ratio:.1f} value hands. '
        f'(At {bet_size_pct:.0%}pot: {bv_ratio:.2f} bluffs per value.)',
        f'VALUE hands: nuts/near-nuts that beat villain calling range. '
        f'BLUFF hands: missed draws + nut blockers. '
        f'CHECK hands: medium-strength bluff catchers (check-call vs check-fold).',
    ]

    if hero_has_nut_blocker:
        notes.append(
            'Nut blocker reduces villain\'s value-heavy calling range. '
            'This makes your bluff more profitable and your value bets thinner.'
        )

    if missed_draw:
        notes.append(
            'Missed draw: prime bluff candidate IF you have blockers. '
            'Without blockers, check and show down (you may still win vs pure air).'
        )

    if action == 'bet_bluff' and bet_freq < 0.30:
        notes.append(
            f'Low bluff frequency ({bet_freq:.0%}): this spot has limited bluff value. '
            'Consider checking more and calling if villain bluffs into you.'
        )

    return RiverRangeAdvice(
        hero_hand_class=hero_hand_class,
        hero_equity=round(hero_equity, 3),
        hero_has_nut_blocker=hero_has_nut_blocker,
        missed_draw=missed_draw,
        board_type=board_type,
        bet_size_pct=bet_size_pct,
        alpha=round(a, 3),
        bluff_to_value_ratio=round(bv_ratio, 3),
        value_fraction=round(v_pct, 3),
        bluff_fraction=round(b_pct, 3),
        category=category,
        recommended_action=action,
        bet_frequency=round(bet_freq, 2),
        pot_bb=round(pot_bb, 1),
        bet_bb=bet_bb,
        action_reasoning=reasoning,
        range_construction_notes=notes,
    )


def river_range_summary(bet_size_pct: float) -> dict:
    """
    At a given bet size, what is the correct value:bluff composition?
    Returns a dict with the math for quick reference.
    """
    a = _alpha(bet_size_pct)
    bv, v, b = _bluff_to_value(bet_size_pct)
    return {
        'bet_size_pct': bet_size_pct,
        'alpha': round(a, 3),
        'value_fraction': round(v, 3),
        'bluff_fraction': round(b, 3),
        'bluffs_per_value': round(bv, 3),
        'description': (
            f'{bet_size_pct:.0%}pot: {v:.0%} value + {b:.0%} bluff. '
            f'{bv:.2f} bluffs per value hand. '
            f'Hero needs to call {a:.0%} of range to stay unexploitable.'
        ),
    }


def river_range_one_liner(result: RiverRangeAdvice) -> str:
    return (
        f'[RRB {result.hero_hand_class}] {result.recommended_action.upper()} '
        f'({result.bet_frequency:.0%}) | '
        f'{result.category} | '
        f'alpha={result.alpha:.0%} V={result.value_fraction:.0%} B={result.bluff_fraction:.0%}'
    )
