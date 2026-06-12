"""
Position Awareness Guide (position_awareness_guide.py)

Quantifies positional advantage/disadvantage and adjusts strategy accordingly.
Position is one of the most important factors in poker. Playing IP (in position)
gives you the last act on every postflop street, which is enormously valuable.

POSITIONAL VALUE THEORY:
  IP (In Position) advantages:
  1. Last to act: see villain's check/bet before deciding
  2. Free card: check back to see next card at no cost
  3. Pot control: cap the pot size at your discretion
  4. Bluff opportunities: villain's weakness shows before your decision
  5. Better implied odds: villain bets into you when they hit

  OOP (Out of Position) disadvantages:
  1. Must act first with less information
  2. C-bets expose you to check-raises
  3. Pot gets larger without control
  4. Harder to execute multi-street plans

POSITION-SPECIFIC ADJUSTMENTS:
  BTN (Best position):  Open wide (45-50%); steal frequently; control every pot
  CO:                   Open 28-32%; 3-bet light in position against BTN
  HJ/MP:               Open tighter; avoid marginal hands OOP
  UTG (Worst position): Open tight (13-17%); only strong hands
  SB:                   Defend wide vs BTN; open tight (one villain still OOP)
  BB:                   Must defend wide (already invested); but OOP vs all

POSITIONAL ADVANTAGE SCORE (0-10):
  10: BTN vs SB/BB (maximum advantage)
  8:  CO vs SB/BB
  6:  HJ vs SB
  4:  Blind vs late position (moderate disadvantage)
  2:  UTG vs everyone (maximum disadvantage as caller, not raiser)

DISTINCT FROM:
  preflop_equilibrium_chart.py:   Position-specific open ranges
  ip_range_protector.py:          IP checking range protection
  range_disadvantage_response.py: Playing from range disadvantage
  THIS MODULE:                    Position VALUE quantification;
                                  real-time positional advice;
                                  how much to adjust based on seats

Usage:
    from poker.position_awareness_guide import guide_position_play, PositionGuide, pag_one_liner

    result = guide_position_play(
        hero_position='btn',
        villain_position='bb',
        street='flop',
        hero_hand_category='top_pair',
        hero_equity=0.62,
        pot_bb=20.0,
        spr=5.0,
        villain_af=2.2,
        board_texture='semi_wet',
    )
    print(pag_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Positional advantage score (1-10) by position vs villain position
POSITIONAL_ADVANTAGE = {
    ('btn', 'bb'):  9,
    ('btn', 'sb'):  9,
    ('btn', 'co'):  5,
    ('btn', 'hj'):  6,
    ('co',  'bb'):  8,
    ('co',  'sb'):  8,
    ('co',  'btn'): 3,   # CO vs BTN = CO is OOP
    ('hj',  'bb'):  7,
    ('hj',  'sb'):  7,
    ('hj',  'btn'): 2,
    ('hj',  'co'):  3,
    ('utg', 'bb'):  4,
    ('utg', 'sb'):  4,
    ('utg', 'btn'): 1,
    ('utg', 'co'):  1,
    ('utg', 'hj'):  2,
    ('sb',  'bb'):  6,
    ('sb',  'btn'): 2,
    ('bb',  'sb'):  7,
    ('bb',  'btn'): 2,
    ('bb',  'co'):  2,
    ('bb',  'utg'): 3,
}

# Position-specific open raise frequency
POSITION_OPEN_PCT = {
    'utg': 0.15, 'utg1': 0.17, 'utg2': 0.19,
    'hj': 0.22, 'lj': 0.20,
    'co': 0.30, 'mp': 0.22,
    'btn': 0.48,
    'sb': 0.38,
    'bb': 0.00,  # BB doesn't open; defends
}


def _positional_advantage_score(hero_pos: str, villain_pos: str) -> int:
    key = (hero_pos.lower(), villain_pos.lower())
    return POSITIONAL_ADVANTAGE.get(key, 5)


def _position_category(score: int) -> str:
    if score >= 8:
        return 'dominant_ip'
    elif score >= 6:
        return 'strong_ip'
    elif score >= 4:
        return 'slight_ip'
    elif score == 3:
        return 'neutral'
    elif score >= 2:
        return 'slight_oop'
    else:
        return 'strong_oop'


def _ip_or_oop(hero_pos: str, villain_pos: str) -> str:
    """Returns 'ip' if hero acts after villain postflop, else 'oop'."""
    # Simplified: BTN/CO/HJ act after BB/SB postflop
    late = {'btn', 'co', 'hj', 'lj'}
    if hero_pos.lower() in late and villain_pos.lower() in ('bb', 'sb'):
        return 'ip'
    if villain_pos.lower() in late and hero_pos.lower() in ('bb', 'sb'):
        return 'oop'
    # SB vs BB: SB acts first postflop (OOP)
    if hero_pos.lower() == 'sb' and villain_pos.lower() == 'bb':
        return 'oop'
    if hero_pos.lower() == 'bb' and villain_pos.lower() == 'sb':
        return 'ip'
    return 'ip'  # default


def _recommended_open_pct(hero_pos: str) -> float:
    return POSITION_OPEN_PCT.get(hero_pos.lower(), 0.20)


def _positional_action_advice(
    hero_pos: str,
    villain_pos: str,
    pos_category: str,
    street: str,
    hero_hand_category: str,
    hero_equity: float,
    villain_af: float,
) -> str:
    position = _ip_or_oop(hero_pos, villain_pos)

    if pos_category == 'dominant_ip':
        if hero_hand_category in ('top_pair', 'overpair', 'set'):
            return (
                f'DOMINANT IP: Bet aggressively for value and to deny free cards. '
                f'Your positional advantage is maximum -- use it. '
                f'Check back to control pot is viable on wet boards.'
            )
        else:
            return (
                f'DOMINANT IP + WEAK HAND: Check back to control pot size and see free card. '
                f'Bluff opportunities arise if villain checks twice.'
            )
    elif pos_category in ('strong_ip', 'slight_ip'):
        return (
            f'IP ADVANTAGE (score={_positional_advantage_score(hero_pos, villain_pos)}): '
            f'Bet at slightly higher frequency than GTO. '
            f'Use position for pot control; check back with medium hands. '
            f'Call more light -- realize equity in position.'
        )
    elif pos_category == 'strong_oop':
        return (
            f'OOP DISADVANTAGE: Tighten your betting range significantly. '
            f'Check more -- giving IP player last action is costly. '
            f'Prefer check-raise over donk-bet. '
            f'Only bet strong value and premium bluffs.'
        )
    else:
        return (
            f'SLIGHT OOP: Moderate adjustment needed. '
            f'Check more marginal hands. '
            f'Value bet strong hands at standard frequency. '
            f'Avoid check-calling too often without strong draws or made hands.'
        )


@dataclass
class PositionGuide:
    # Inputs
    hero_position: str
    villain_position: str
    street: str
    hero_hand_category: str
    hero_equity: float
    pot_bb: float
    spr: float
    villain_af: float
    board_texture: str

    # Analysis
    positional_advantage_score: int      # 1-10
    position_category: str               # 'dominant_ip' / 'strong_ip' / etc.
    is_ip: str                           # 'ip' / 'oop'
    recommended_open_pct: float
    action_advice: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def guide_position_play(
    hero_position: str = 'btn',
    villain_position: str = 'bb',
    street: str = 'flop',
    hero_hand_category: str = 'top_pair',
    hero_equity: float = 0.62,
    pot_bb: float = 20.0,
    spr: float = 5.0,
    villain_af: float = 2.2,
    board_texture: str = 'semi_wet',
) -> PositionGuide:
    """
    Guide strategic adjustments based on positional advantage.

    Args:
        hero_position:     Hero's position at table
        villain_position:  Villain's position
        street:            'preflop' / 'flop' / 'turn' / 'river'
        hero_hand_category: Current hand
        hero_equity:       Current equity
        pot_bb:            Current pot
        spr:               Stack-to-pot ratio
        villain_af:        Villain AF
        board_texture:     Board texture

    Returns:
        PositionGuide
    """
    score = _positional_advantage_score(hero_position, villain_position)
    cat = _position_category(score)
    ip_oop = _ip_or_oop(hero_position, villain_position)
    open_pct = _recommended_open_pct(hero_position)
    advice = _positional_action_advice(
        hero_position, villain_position, cat, street,
        hero_hand_category, hero_equity, villain_af
    )

    verdict = (
        f'[PAG {cat.upper()}|{hero_position}vs{villain_position}|{ip_oop}] '
        f'score={score}/10 open={open_pct:.0%} | {advice[:50]}'
    )

    reasoning = (
        f'Position guide: {hero_position} vs {villain_position} on {street}. '
        f'Positional score={score}/10 ({cat}). '
        f'IP={ip_oop}. '
        f'Recommended open={open_pct:.0%} from {hero_position}. '
        f'Hand={hero_hand_category}.'
    )

    tips = [advice]

    tips.append(
        f'POSITIONAL SCORE: {score}/10 ({cat}). '
        f'High score = major IP advantage = play more hands and bet more. '
        f'Low score = OOP disadvantage = tighten ranges, check more, avoid marginal spots.'
    )

    tips.append(
        f'OPEN RANGE: From {hero_position.upper()}, open {open_pct:.0%} of hands. '
        f'Position directly correlates with how many hands you can profitably open. '
        f'BTN: 48% -- BB: 0% (BB defends, does not open).'
    )

    if ip_oop == 'ip' and score >= 7:
        tips.append(
            f'DOMINANT IP TIPS: '
            f'(1) Use position to control pot: check back medium hands. '
            f'(2) Extract max value: villain bets into you; let them bet before raising. '
            f'(3) Bluff more freely: villain must act blind into your range. '
            f'(4) Call wider: realize equity with draws and speculative hands.'
        )
    elif ip_oop == 'oop':
        tips.append(
            f'OOP SURVIVAL TIPS: '
            f'(1) Check more: avoid giving IP player easy decisions. '
            f'(2) Check-raise strong hands: deny free card + build pot. '
            f'(3) Donk-bet selectively: on boards that hit your range (caller on low boards). '
            f'(4) Give up marginal draws: implied odds are worse OOP.'
        )

    if hero_position == 'bb':
        tips.append(
            f'BB SPECIFIC: Defend {max(0.40, open_pct * 1.8):.0%}+ of hands vs BTN steal. '
            f'BB has the worst position postflop but best pot odds preflop. '
            f'Defend range includes suited connectors, pairs, strong broadway combos.'
        )

    return PositionGuide(
        hero_position=hero_position,
        villain_position=villain_position,
        street=street,
        hero_hand_category=hero_hand_category,
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        spr=spr,
        villain_af=villain_af,
        board_texture=board_texture,
        positional_advantage_score=score,
        position_category=cat,
        is_ip=ip_oop,
        recommended_open_pct=open_pct,
        action_advice=advice,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pag_one_liner(r: PositionGuide) -> str:
    return (
        f'[PAG {r.position_category.upper()}|{r.hero_position}vs{r.villain_position}] '
        f'score={r.positional_advantage_score}/10 {r.is_ip.upper()} | open={r.recommended_open_pct:.0%}'
    )
