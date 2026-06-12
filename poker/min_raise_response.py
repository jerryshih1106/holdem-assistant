"""
Min-Raise Response Advisor (min_raise_response.py)

A min-raise (2x the previous bet) is one of the most commonly misplayed spots
in poker. Players either:
  - Over-fold: treating min-raise as a strong raise (it usually isn't)
  - Under-fold: calling/3-betting with too wide a range

Key principles for facing a min-raise:

1. PRICE EFFECT: A min-raise gives excellent pot odds.
   Example: Hero bets 10BB into 20BB pot (30BB total).
   Villain min-raises to 20BB. Hero must call 10BB more to win 50BB.
   Required equity = 10/(50+10) = 16.7% — VERY cheap to continue.
   This means even weak draws can continue.

2. INFORMATION VALUE: Min-raises are highly polarized in some spots.
   On the flop vs c-bet: min-raise often = draw OR strong hand wanting cheap see-turn
   On the turn: min-raise = stronger signal (more likely value or strong draw)
   On the river: min-raise = strong value (no implied odds needed; just wants more money)

3. RANGE ANALYSIS:
   Villain who min-raises flop c-bet:
     Value: sets, two pair, strong top pair
     Bluffs: flush draws (want cheap turn), OESD, combo draws
     Ratio: roughly 60% value / 40% draws-or-bluffs (board dependent)

   Villain who min-raises hero's bet (turn or later):
     Value: strong made hand (street-to-street: range narrows)
     Bluff: rare (why min-raise as a bluff? smaller fold equity than a real raise)

4. WHEN TO 3-BET VS CALL VS FOLD:
   3-bet: strong hands (two pair+) that want to get value AND define range.
     Also 3-bet as a bluff vs loose min-raisers (good fold equity)
   Call: medium hands (top pair, TPTK, strong draws) — preserve pot odds advantage
   Fold: weak hands below 20% equity (even draws if board changes disadvantageously)

5. POSITION MATTERS GREATLY:
   IP hero: can call wide (implied odds), 3-bet as bluff easily
   OOP hero: need better hand to call (position disadvantage post); 3-bet or fold

Special case: Min-raise on river (pure value sizing):
  Villain is basically saying "I have a strong hand, want a bit more."
  Hero's decision is pure pot-odds: call if hero's hand beats some of villain's min-raise range.
  3-betting is almost never correct (villain will only call with better hands).

Usage:
    from poker.min_raise_response import advise_min_raise_response
    from poker.min_raise_response import MinRaiseResponse, min_raise_one_liner

    result = advise_min_raise_response(
        hero_hand_class='top_pair',
        hero_bet_pct=0.50,
        street='flop',
        hero_equity=0.55,
        villain_vpip=0.35,
        villain_af=2.0,
        board_type='medium',
        hero_pos='IP',
        spr=6.0,
        pot_bb=20.0,
        hero_bet_bb=10.0,
    )
    print(result.action, result.required_equity)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'trash': 0, 'bottom_pair': 2, 'marginal': 2,
        'middle_pair': 3, 'draw': 3, 'speculative': 2,
        'top_pair': 4, 'medium': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'strong': 7,
        'set': 9, 'straight': 8, 'flush': 8, 'premium': 9,
        'full_house': 10, 'quads': 10, 'nuts': 10,
    }.get(hand_class.lower(), 4)


def _required_equity_to_call(
    pot_bb: float,
    hero_bet_bb: float,
    min_raise_bb: float,
) -> float:
    """
    Required equity to call the min-raise.
    pot_after_minraise = pot_bb + hero_bet_bb + min_raise_bb
    call_cost = min_raise_bb - hero_bet_bb
    req_eq = call_cost / (pot_after_minraise + call_cost)
    """
    call_cost = min_raise_bb - hero_bet_bb
    pot_if_called = pot_bb + hero_bet_bb + min_raise_bb + call_cost
    if pot_if_called <= 0:
        return 0.50
    return round(call_cost / pot_if_called, 4)


def _min_raise_bb(hero_bet_bb: float) -> float:
    """Standard min-raise = 2x hero's bet."""
    return round(hero_bet_bb * 2.0, 1)


def _villain_range_assessment(
    villain_vpip: float,
    villain_af: float,
    street: str,
    board_type: str,
) -> tuple:
    """
    Returns (value_pct, bluff_pct, range_strength):
    value_pct: fraction of min-raise range that is value
    bluff_pct: fraction that is bluff/draw
    range_strength: 'polarized', 'strong_heavy', 'draw_heavy'
    """
    # Base by street
    if street == 'flop':
        base_value = 0.55
        base_draw = 0.45
    elif street == 'turn':
        base_value = 0.70
        base_draw = 0.30
    else:  # river
        base_value = 0.90
        base_draw = 0.10

    # Adjust for villain type
    if villain_af >= 3.0:
        # Aggressive: adds bluffs / semi-bluffs
        base_draw = min(0.65, base_draw + 0.15)
        base_value = 1.0 - base_draw
    elif villain_af < 1.0:
        # Passive: rarely raises without value
        base_value = min(0.95, base_value + 0.15)
        base_draw = 1.0 - base_value

    if villain_vpip > 0.45:
        # Loose: min-raises with more draws and weak value
        base_draw = min(0.60, base_draw + 0.10)
        base_value = 1.0 - base_draw

    if board_type == 'wet':
        # More draws → more draw-based min-raises
        base_draw = min(0.60, base_draw + 0.08)
        base_value = 1.0 - base_draw
    elif board_type == 'dry':
        base_value = min(0.90, base_value + 0.05)
        base_draw = 1.0 - base_value

    # Classify range strength
    if base_value >= 0.80:
        strength = 'strong_heavy'
    elif base_draw >= 0.50:
        strength = 'draw_heavy'
    else:
        strength = 'polarized'

    return round(base_value, 2), round(base_draw, 2), strength


def _threbet_size(
    min_raise_bb: float,
    pot_bb: float,
    hero_bet_bb: float,
    street: str,
) -> float:
    """Optimal 3-bet size vs min-raise."""
    # Total pot before 3-bet = pot + hero_bet + min_raise
    total_pot = pot_bb + hero_bet_bb + min_raise_bb
    # 3-bet to about 3x min-raise, min = 2.5x
    target = min_raise_bb * 2.8
    if street == 'river':
        target = min_raise_bb * 3.0   # River 3-bet: larger (pure value)
    return round(target, 1)


def _action(
    hero_hand_rank: int,
    hero_equity: float,
    req_eq: float,
    villain_value_pct: float,
    range_strength: str,
    street: str,
    hero_pos: str,
    villain_af: float,
    spr: float,
) -> tuple:
    """Returns (action, reasoning)."""
    # Strong hands: 3-bet for value
    if hero_hand_rank >= 7:
        return (
            'threeb_value',
            f'Strong hand (rank={hero_hand_rank}): 3-bet for value. '
            f'Min-raise = invitation to build pot. Your hand beats most of their value range.'
        )

    # River: almost never 3-bet unless nuts
    if street == 'river':
        if hero_hand_rank >= 9:
            return (
                'threeb_value',
                f'River nuts: 3-bet to extract max value from min-raise (villain committed).'
            )
        if hero_equity >= req_eq + 0.15:
            return (
                'call',
                f'River call: good equity ({hero_equity:.0%}) vs min-raise range. '
                f'3-bet would only get called by better hands.'
            )
        if hero_equity >= req_eq:
            return (
                'call',
                f'River marginal call: equity {hero_equity:.0%} >= required {req_eq:.0%}. '
                f'Min-raise is cheap; hero wins vs some of villain\'s range.'
            )
        return ('fold', f'River fold: equity {hero_equity:.0%} < required {req_eq:.0%}.')

    # Aggressive villain with draw-heavy range: 3-bet as bluff is viable
    if villain_af >= 2.5 and range_strength == 'draw_heavy' and hero_hand_rank <= 3:
        return (
            'threeb_bluff',
            f'3-bet bluff: villain AF={villain_af:.1f}, range is draw_heavy. '
            f'They fold most draws to 3-bets. '
            f'Hero has ~0 SDV but strong fold equity vs their draw-heavy min-raise.'
        )

    # Medium hands (TP, TPTK): call (pot odds are excellent)
    if hero_equity >= req_eq + 0.10 and hero_hand_rank >= 4:
        return (
            'call',
            f'Call: equity {hero_equity:.0%} well above required {req_eq:.0%}. '
            f'Min-raise gives excellent pot odds — call and reassess turn.'
        )

    # Marginal equity: call if IP (implied odds), fold if OOP
    if hero_equity >= req_eq:
        if hero_pos == 'IP':
            return (
                'call',
                f'IP call: equity {hero_equity:.0%} meets threshold {req_eq:.0%}. '
                f'IP advantage offsets villain\'s initiative. '
                f'Check-call mode: extract value without committing.'
            )
        # OOP: tighten
        if hero_equity >= req_eq + 0.05:
            return (
                'call',
                f'OOP call: equity {hero_equity:.0%} > {req_eq:.0%}. '
                f'Marginal but profitable — proceed cautiously.'
            )
        return (
            'fold',
            f'OOP fold: equity {hero_equity:.0%} barely meets {req_eq:.0%}. '
            f'Position disadvantage makes marginal calls -EV OOP.'
        )

    # Below threshold
    return (
        'fold',
        f'Fold: equity {hero_equity:.0%} < required {req_eq:.0%}. '
        f'Min-raise from {range_strength} range — villain has too much value.'
    )


@dataclass
class MinRaiseResponse:
    """Advice for responding to a min-raise."""
    hero_hand_class: str
    hero_bet_pct: float
    street: str
    hero_equity: float
    villain_vpip: float
    villain_af: float
    board_type: str
    hero_pos: str
    spr: float
    pot_bb: float
    hero_bet_bb: float

    # Villain analysis
    villain_value_pct: float     # fraction of min-raise range that is value
    villain_draw_pct: float      # fraction that is draw/bluff
    range_strength: str          # 'polarized', 'strong_heavy', 'draw_heavy'

    # Decision
    action: str                  # 'fold', 'call', 'threeb_value', 'threeb_bluff'
    required_equity: float
    min_raise_bb: float
    call_cost_bb: float
    threeb_size_bb: float

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_min_raise_response(
    hero_hand_class: str = 'top_pair',
    hero_bet_pct: float = 0.50,
    street: str = 'flop',
    hero_equity: float = 0.55,
    villain_vpip: float = 0.35,
    villain_af: float = 2.0,
    board_type: str = 'medium',
    hero_pos: str = 'IP',
    spr: float = 6.0,
    pot_bb: float = 20.0,
    hero_bet_bb: float = 10.0,
) -> MinRaiseResponse:
    """
    Advise hero's response when villain min-raises hero's bet.

    Args:
        hero_hand_class:  Hero's hand strength
        hero_bet_pct:     Hero's original bet size as fraction of pot
        street:           'flop', 'turn', 'river'
        hero_equity:      Hero's equity vs villain's overall range
        villain_vpip:     Villain's VPIP (0-1)
        villain_af:       Villain's aggression factor
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' or 'OOP'
        spr:              Stack-to-pot ratio
        pot_bb:           Pot size before hero bet
        hero_bet_bb:      Hero's bet size in BB

    Returns:
        MinRaiseResponse
    """
    rank = _hand_rank(hero_hand_class)
    mr_bb = _min_raise_bb(hero_bet_bb)
    call_cost = round(mr_bb - hero_bet_bb, 1)
    req_eq = _required_equity_to_call(pot_bb, hero_bet_bb, mr_bb)
    val_pct, draw_pct, range_str = _villain_range_assessment(
        villain_vpip, villain_af, street, board_type
    )
    action, reasoning = _action(
        rank, hero_equity, req_eq, val_pct, range_str, street, hero_pos, villain_af, spr
    )
    threeb_size = _threbet_size(mr_bb, pot_bb, hero_bet_bb, street)

    # Tips
    tips = []
    tips.append(
        f'Min-raise gives excellent pot odds: call cost={call_cost:.1f}BB, '
        f'pot={pot_bb + hero_bet_bb + mr_bb:.1f}BB → req equity={req_eq:.0%}. '
        f'Even weak draws ({req_eq:.0%}+ equity) can continue profitably.'
    )
    if range_str == 'draw_heavy' and action in ('call', 'threeb_bluff'):
        tips.append(
            f'Draw-heavy min-raise range ({draw_pct:.0%} draws): villain is building equity. '
            f'{"3-bet to fold out their equity." if action == "threeb_bluff" else "Call and bet turn to deny their draw equity."}'
        )
    if street == 'flop' and hero_pos == 'IP':
        tips.append(
            'IP flop min-raise: excellent implied odds. '
            'Call with most top pair+ and strong draws. '
            'Plan: if villain checks turn, bet for value; if they bet turn, re-evaluate strength.'
        )
    if action in ('threeb_value', 'threeb_bluff'):
        tips.append(
            f'3-bet to {threeb_size:.1f}BB ({threeb_size/mr_bb:.1f}x their min-raise). '
            f'This forces villain to define their hand. '
            f'Most draw-heavy min-raises fold to 3-bets. '
            f'Value hands will 4-bet or call — then you know where you are.'
        )
    if street == 'river' and action == 'call':
        tips.append(
            'River min-raise: villain is typically value-betting thin or '
            'blocking with medium strength. '
            'Call if your hand beats any value — do not 3-bet without nuts. '
            'They will only call 3-bets with better hands.'
        )
    if not tips:
        tips.append(
            f'{action.upper()}: villain {range_str} min-raise on {street}. '
            f'Req eq={req_eq:.0%}, hero eq={hero_equity:.0%}. '
            f'{"3-bet to " + str(threeb_size) + "BB." if "threeb" in action else action.capitalize() + " (" + str(call_cost) + "BB)."}'
        )

    return MinRaiseResponse(
        hero_hand_class=hero_hand_class,
        hero_bet_pct=round(hero_bet_pct, 3),
        street=street,
        hero_equity=round(hero_equity, 3),
        villain_vpip=round(villain_vpip, 3),
        villain_af=round(villain_af, 2),
        board_type=board_type,
        hero_pos=hero_pos,
        spr=round(spr, 2),
        pot_bb=round(pot_bb, 1),
        hero_bet_bb=round(hero_bet_bb, 1),
        villain_value_pct=val_pct,
        villain_draw_pct=draw_pct,
        range_strength=range_str,
        action=action,
        required_equity=req_eq,
        min_raise_bb=mr_bb,
        call_cost_bb=call_cost,
        threeb_size_bb=threeb_size,
        reasoning=reasoning,
        tips=tips,
    )


def min_raise_one_liner(result: MinRaiseResponse) -> str:
    return (
        f'[MRR {result.hero_hand_class}@{result.street}|{result.hero_pos}] '
        f'{result.action.upper()} | '
        f'req={result.required_equity:.0%} eq={result.hero_equity:.0%} | '
        f'vrange={result.range_strength}({result.villain_draw_pct:.0%}draws) | '
        f'3b={result.threeb_size_bb:.1f}BB'
    )
