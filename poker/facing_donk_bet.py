"""
Facing Donk Bet Advisor (facing_donk_bet.py)

A "donk bet" occurs when an OOP player leads into the pre-flop aggressor (PFR)
instead of check-raising or check-calling. In balanced GTO play, OOP players
rarely donk bet. When they do, it carries information:

Types of donk bets by size:
  Small (25-40% pot): Often a probe — villain has some equity but is not committed.
    Seen from recreational players who want to "see where they are."
    Balanced donk = medium-strength hands, some draws.
  Standard (50-75%): Polarized — strong made hands OR semi-bluffs.
    Value donk: sets, two pair, straights hitting new card.
    Bluff donk: flush draws, combo draws leading to apply pressure.
  Large/Overbet (100%+): Very strong hand or desperate bluff.
    Most players only overbet-donk with nutted hands.

Why donk bets change the analysis:
  1. Range effect: OOP villain has "broken" the standard check-then-react pattern.
     Their checking range now excludes donk-worthy hands.
     This NARROWS their remaining range if they check.
  2. Position dynamics: Hero is still IP but villain took initiative.
     Hero calling keeps pot control; hero raising forces commitment.
  3. Exploit opportunity: Most villains' donk ranges are imbalanced.
     Fish donk with any pair; Nits donk only with strong hands.

Hero response options:
  1. Fold: Clear when villain's donk signals strength and hero has weak hand.
  2. Call: When hero has equity vs villain's donk range; IP advantage preserved.
  3. Raise: When hero has strong hand OR villain's donk range is weak/bluff-heavy.
     Raise size: 2.5-3.5x villain's donk bet.
  4. All-in (on short stacks): When pot + bet forces commitment.

Street-specific notes:
  Flop donk: Most common. Fish often donk with any piece.
  Turn donk: Stronger signal — villain has made their hand or picked up a draw.
  River donk: Very polarized. Villain either has strong hand or is betting into
    your range to get a cheap showdown (blocking bet pattern).

Usage:
    from poker.facing_donk_bet import advise_facing_donk, FacingDonkAdvice
    from poker.facing_donk_bet import facing_donk_one_liner

    result = advise_facing_donk(
        hero_hand_class='top_pair',
        donk_size_pct=0.50,
        street='flop',
        hero_equity=0.55,
        villain_vpip=0.45,
        villain_af=1.2,
        board_type='medium',
        hero_pos='IP',
        spr=6.0,
        pot_bb=20.0,
    )
    print(result.action, result.raise_to_bb)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'trash': 0, 'bottom_pair': 2, 'marginal': 2,
        'middle_pair': 3, 'draw': 3, 'speculative': 3,
        'top_pair': 4, 'medium': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'strong': 7,
        'set': 9, 'straight': 8, 'flush': 8, 'premium': 9,
        'full_house': 10, 'quads': 10, 'nuts': 10,
    }.get(hand_class.lower(), 4)


def _donk_size_category(donk_size_pct: float) -> str:
    """Categorize donk bet size."""
    if donk_size_pct < 0.40:
        return 'small'
    if donk_size_pct < 0.75:
        return 'standard'
    return 'large'


def _villain_donk_range_type(
    villain_vpip: float,
    villain_af: float,
    donk_size_pct: float,
    street: str,
) -> tuple:
    """
    Returns (range_type, bluff_fraction):
      range_type: 'strong', 'mixed', 'weak_probe'
      bluff_fraction: estimated fraction of donk range that is bluffing
    """
    size_cat = _donk_size_category(donk_size_pct)

    # Fish (high VPIP, low AF): donk with any pair or draw
    if villain_vpip > 0.45:
        if size_cat == 'small':
            return 'weak_probe', 0.45  # Any piece, many bluffs
        if size_cat == 'standard':
            return 'mixed', 0.35
        return 'mixed', 0.20   # Large bet: even fish have strong hand

    # Aggressive player (high AF): may semi-bluff donk
    if villain_af >= 2.5:
        if size_cat == 'small':
            return 'mixed', 0.55  # Often probe-bluff
        if size_cat == 'standard':
            return 'mixed', 0.40
        return 'strong', 0.30  # Large = usually value + some semi-bluffs

    # Nit/passive (low VPIP, low AF): donk = very strong
    if villain_vpip < 0.20 and villain_af < 1.5:
        return 'strong', 0.10  # Nit donks = usually nuts

    # Default: standard range
    if size_cat == 'small':
        return 'mixed', 0.40
    if size_cat == 'standard':
        return 'mixed', 0.30
    return 'strong', 0.20


def _required_equity_to_call(donk_size_pct: float) -> float:
    """Break-even equity to call: call_cost / (pot + call_cost)."""
    # Hero already has 0 in pot (villain donks fresh)
    return round(donk_size_pct / (1.0 + 2.0 * donk_size_pct), 4)


def _raise_sizing(
    donk_size_pct: float,
    hero_hand_rank: int,
    spr: float,
    board_type: str,
) -> float:
    """Recommended raise-to as multiple of villain's donk bet."""
    if hero_hand_rank >= 7:
        mult = 2.5   # Strong value: standard raise
        if board_type == 'wet':
            mult = 3.0  # Wet board: larger raise to charge draws
    elif hero_hand_rank >= 5:
        mult = 2.8   # Tptk/overpair: medium raise
    else:
        mult = 3.2   # Bluff raise: larger to maximize fold equity

    # Short stack: smaller relative size (may be committing)
    if spr < 3.0:
        mult = min(mult, 2.5)

    return round(mult, 1)


def _action(
    hero_equity: float,
    req_eq: float,
    hero_hand_rank: int,
    range_type: str,
    bluff_fraction: float,
    donk_size_pct: float,
    street: str,
    spr: float,
) -> tuple:
    """Returns (action, confidence)."""
    size_cat = _donk_size_category(donk_size_pct)

    # Strong hands: raise for value
    if hero_hand_rank >= 7:
        return ('raise', 0.90)

    # Very strong: set, nuts on any board
    if hero_hand_rank >= 9:
        return ('raise', 1.0)

    # Small donk from fish: very weak range → raise with any decent hand
    if range_type == 'weak_probe' and hero_hand_rank >= 4:
        return ('raise', 0.70)

    # River donk: polarized, treat as value or bluff only
    if street == 'river':
        if hero_equity >= req_eq + 0.15 and hero_hand_rank >= 5:
            return ('raise', 0.65)
        if hero_equity >= req_eq:
            return ('call', 0.65)
        return ('fold', 0.75)

    # Large donk from nit: likely nuts → strong hands only continue
    if range_type == 'strong' and size_cat == 'large':
        if hero_hand_rank >= 7:
            return ('raise', 0.75)
        if hero_equity >= req_eq + 0.10:
            return ('call', 0.55)
        return ('fold', 0.70)

    # Standard: equity-based
    if hero_equity >= req_eq + 0.15 and hero_hand_rank >= 5:
        return ('raise', 0.65)
    if hero_equity >= req_eq:
        return ('call', 0.70)
    if hero_equity >= req_eq - 0.05:
        return ('call', 0.40)  # Marginal call
    return ('fold', 0.70)


@dataclass
class FacingDonkAdvice:
    """Advice for hero facing a villain donk bet."""
    hero_hand_class: str
    donk_size_pct: float
    street: str
    hero_equity: float
    villain_vpip: float
    villain_af: float
    board_type: str
    hero_pos: str
    spr: float
    pot_bb: float

    # Villain analysis
    donk_size_category: str     # 'small', 'standard', 'large'
    villain_range_type: str     # 'strong', 'mixed', 'weak_probe'
    villain_bluff_fraction: float

    # Decision
    action: str                 # 'fold', 'call', 'raise'
    confidence: float
    required_equity: float
    raise_mult: float           # multiple of villain's bet to raise to
    raise_to_bb: float          # raise-to amount in BB
    call_cost_bb: float

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_facing_donk(
    hero_hand_class: str = 'top_pair',
    donk_size_pct: float = 0.50,
    street: str = 'flop',
    hero_equity: float = 0.55,
    villain_vpip: float = 0.45,
    villain_af: float = 1.2,
    board_type: str = 'medium',
    hero_pos: str = 'IP',
    spr: float = 6.0,
    pot_bb: float = 20.0,
) -> FacingDonkAdvice:
    """
    Advise hero's response to a villain donk bet.

    Args:
        hero_hand_class:  Hero's hand strength
        donk_size_pct:    Villain's donk bet size as fraction of pot (0.25-2.0)
        street:           'flop', 'turn', 'river'
        hero_equity:      Hero's equity vs villain's full range
        villain_vpip:     Villain's VPIP (0-1)
        villain_af:       Villain's aggression factor
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' (behind OOP villain) or 'OOP' (unusual; villain ahead)
        spr:              Stack-to-pot ratio
        pot_bb:           Current pot size in BB (before donk)

    Returns:
        FacingDonkAdvice
    """
    rank = _hand_rank(hero_hand_class)
    size_cat = _donk_size_category(donk_size_pct)
    range_type, bluff_frac = _villain_donk_range_type(
        villain_vpip, villain_af, donk_size_pct, street
    )
    req_eq = _required_equity_to_call(donk_size_pct)
    action, confidence = _action(
        hero_equity, req_eq, rank, range_type, bluff_frac, donk_size_pct, street, spr
    )
    raise_mult = _raise_sizing(donk_size_pct, rank, spr, board_type)
    call_cost = round(pot_bb * donk_size_pct, 1)
    raise_to_bb = round(call_cost * raise_mult, 1)

    # Reasoning
    if action == 'raise':
        reason = (
            f'RAISE {raise_mult:.1f}x ({raise_to_bb:.1f}BB): '
            f'villain donk type={range_type} (bluff_frac={bluff_frac:.0%}). '
            f'Hand rank {rank} justifies re-aggression. '
            f'Size category: {size_cat}.'
        )
    elif action == 'call':
        reason = (
            f'CALL: hero equity {hero_equity:.0%} >= req {req_eq:.0%}. '
            f'Villain range={range_type}, size={size_cat}. '
            f'Preserve IP advantage; re-assess on {{"flop":"turn","turn":"river","river":"showdown"}}.get("{street}", "turn").'
        )
    else:
        reason = (
            f'FOLD: hero equity {hero_equity:.0%} < req {req_eq:.0%}. '
            f'Villain range={range_type}: {size_cat} donk has '
            f'{bluff_frac:.0%} bluffs → not enough to profitably call.'
        )

    # Tips
    tips = []
    if range_type == 'weak_probe' and rank >= 4:
        tips.append(
            f'Fish probe: villain (VPIP={villain_vpip:.0%}) donked {donk_size_pct:.0%} pot — '
            f'likely "any pair" or draw. '
            f'Raise to {raise_to_bb:.1f}BB ({raise_mult:.1f}x) — most fish donk then fold to raises, '
            f'or call with weak hands and barrel off when you improve.'
        )
    if size_cat == 'small' and villain_vpip > 0.40:
        tips.append(
            f'Small donk ({donk_size_pct:.0%} pot) from loose villain: '
            f'classic "feeler bet." They want information cheaply. '
            f'Raise with any decent hand to punish and define their range. '
            f'They will fold all air and some medium hands.'
        )
    if range_type == 'strong' and action == 'fold':
        tips.append(
            f'Tight villain (VPIP={villain_vpip:.0%}) donk {size_cat}: very polarized toward value. '
            f'Do not hero-call or bluff-raise. '
            f'Fold all but your strongest hands (two pair+). '
            f'Even top pair is marginal here.'
        )
    if street == 'river' and action == 'call':
        tips.append(
            f'River donk: polarized range. '
            f'Villain is either value-betting strong or blocking with medium hand. '
            f'{"You have sufficient equity — call once, do not re-raise without nuts." if rank < 7 else "Strong hand — consider raising to {raise_to_bb:.1f}BB."}'
        )
    if board_type == 'wet' and action == 'raise':
        tips.append(
            f'Wet board + villain donk: many draws in their range. '
            f'Raise to {raise_to_bb:.1f}BB charges draws and defines range. '
            f'If called, you have initiative on turn with protected hand.'
        )
    if not tips:
        tips.append(
            f'{action.upper()}: villain {range_type} donk of {donk_size_pct:.0%} pot on {street}. '
            f'Req eq={req_eq:.0%}, hero eq={hero_equity:.0%}. '
            f'{"Raise " + str(raise_to_bb) + "BB." if action == "raise" else action.capitalize() + "."}'
        )

    return FacingDonkAdvice(
        hero_hand_class=hero_hand_class,
        donk_size_pct=round(donk_size_pct, 3),
        street=street,
        hero_equity=round(hero_equity, 3),
        villain_vpip=round(villain_vpip, 3),
        villain_af=round(villain_af, 2),
        board_type=board_type,
        hero_pos=hero_pos,
        spr=round(spr, 2),
        pot_bb=round(pot_bb, 1),
        donk_size_category=size_cat,
        villain_range_type=range_type,
        villain_bluff_fraction=round(bluff_frac, 3),
        action=action,
        confidence=round(confidence, 2),
        required_equity=req_eq,
        raise_mult=raise_mult,
        raise_to_bb=raise_to_bb,
        call_cost_bb=call_cost,
        reasoning=reason,
        tips=tips,
    )


def facing_donk_one_liner(result: FacingDonkAdvice) -> str:
    return (
        f'[DONKvH {result.hero_hand_class}@{result.street}] '
        f'{result.action.upper()} | '
        f'donk={result.donk_size_pct:.0%}pot({result.donk_size_category}) | '
        f'vrange={result.villain_range_type} bluff={result.villain_bluff_fraction:.0%} | '
        f'req={result.required_equity:.0%} eq={result.hero_equity:.0%}'
    )
