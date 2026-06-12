"""
Donk Bet Range Builder (donk_bet_range_builder.py)

Constructs a balanced OOP donk-bet range: betting into the preflop aggressor
before they can continuation bet. Donk bets are an advanced OOP play used to:
  1. Build the pot with strong hands on boards that favor caller's range
  2. Deny free cards to the aggressor's drawing hands
  3. Protect checking range by adding some bets on specific runouts
  4. Exploit aggressor's high c-bet frequency by making some strong donk-bets

DONK BET THEORY:
  GTO says donk with a range on boards where:
  - Caller has a nut advantage (low boards favor BB caller, not BTN opener)
  - Aggressor has a strong c-bet frequency (donking slows them down)
  - Specific board textures that interact well with caller's calling range

  BOARD TYPES WHERE DONK IS PROFITABLE:
  Low connected boards (2-3-7 type): BB defends many low pairs/sets
  Ace-low boards (A-7-2): BB has many A-x suited combos
  Paired boards (8-8-3): BB traps sets; slow-play potential is high

  DONK BET SIZING:
  Small (25-33%):  Blocker donk; often flush draw or weak TP; invites call
  Medium (50-60%): Merged value/protection; top pair, draws, sets
  Large (75%+):    Polarized donk; strong value (sets, two-pair) or bluff

  HAND SELECTION FOR DONK RANGE:
  VALUE: Sets, two-pair, strong top pair (on specific boards)
  DRAW: Strong flush draws (OESD), combo draws
  BLUFF: Missed preflop equity, backdoor draws on dry boards
  CHECK: Medium pairs (check-call), weak draws, air

DISTINCT FROM:
  donk_bet.py:        General donk bet analysis
  probe_advisor.py:   Turn probe betting (OOP bet after check-check)
  oop_float_advisor.py: OOP float/call continuation
  THIS MODULE:        RANGE CONSTRUCTION for donk bets; which hands
                      to donk, sizing by hand category and board type,
                      GTO balancing principles for OOP donk range.

Usage:
    from poker.donk_bet_range_builder import build_donk_range, DonkRangePlan, dbrb_one_liner

    result = build_donk_range(
        hero_hand_category='set',
        board_texture='wet',
        board_low_card=7,
        villain_cbet_freq=0.72,
        villain_position='btn',
        street='flop',
        pot_bb=15.0,
        spr=6.5,
        hero_position='bb',
    )
    print(dbrb_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Boards where BB range has a nut advantage (low cards favor BB caller)
# Key: board_low_card <= threshold and not a high card board
BB_NUT_ADVANTAGE_THRESHOLD = 8   # boards with max card <= 8 favor BB

# Donk bet size by hand type
DONK_SIZE_BY_HAND = {
    'nuts':             0.75,
    'near_nuts':        0.75,
    'set':              0.65,
    'two_pair':         0.60,
    'flush_draw_strong':0.50,
    'oesd':             0.45,
    'top_pair_strong':  0.55,
    'top_pair':         0.50,
    'combo_draw':       0.55,
    'flush_draw_weak':  0.33,
    'backdoor_draw':    0.28,
    'air':              0.28,   # small bluff donk
    'middle_pair':      0.0,    # check
    'bottom_pair':      0.0,    # check
}

# Hand eligibility for donk betting
DONK_ELIGIBLE = {
    'nuts': True,
    'near_nuts': True,
    'set': True,
    'two_pair': True,
    'flush_draw_strong': True,
    'oesd': True,
    'top_pair_strong': True,
    'top_pair': False,       # usually check-call vs cbet
    'combo_draw': True,
    'flush_draw_weak': False,  # not enough equity
    'backdoor_draw': False,    # too weak
    'air': False,
    'middle_pair': False,
    'bottom_pair': False,
}

# Donk frequency by hand (as % of combos to donk vs check)
DONK_FREQUENCY = {
    'nuts':              0.45,  # mix: some slowplay, some donk
    'near_nuts':         0.50,
    'set':               0.50,
    'two_pair':          0.55,
    'flush_draw_strong': 0.60,
    'oesd':              0.50,
    'top_pair_strong':   0.35,
    'combo_draw':        0.65,
    'air':               0.0,
}


def _has_nut_advantage(board_low_card: int, hero_position: str) -> bool:
    """True if hero's position has nut advantage on this board."""
    if hero_position.lower() in ('bb', 'sb'):
        return board_low_card <= BB_NUT_ADVANTAGE_THRESHOLD
    return False


def _should_donk(
    hand_category: str,
    board_texture: str,
    board_low_card: int,
    villain_cbet_freq: float,
    hero_position: str,
) -> bool:
    eligible = DONK_ELIGIBLE.get(hand_category, False)
    if not eligible:
        return False
    nut_adv = _has_nut_advantage(board_low_card, hero_position)
    # Donk more when villain cbets very frequently (deny cbet EV)
    cbet_pressure = villain_cbet_freq >= 0.65
    if hand_category in ('set', 'two_pair', 'nuts', 'near_nuts'):
        return True  # always donk strong value
    if hand_category in ('flush_draw_strong', 'oesd', 'combo_draw'):
        return nut_adv or cbet_pressure  # donk draws when we have range advantage
    return nut_adv


def _donk_size(hand_category: str, board_texture: str, street: str) -> float:
    base = DONK_SIZE_BY_HAND.get(hand_category, 0.40)
    # Wet boards: slightly smaller (protect but not overbuild vs draws)
    if board_texture in ('wet', 'monotone') and hand_category not in ('set', 'nuts', 'near_nuts'):
        base = max(0.28, base - 0.07)
    # River: polarize (larger or smaller)
    if street == 'river' and hand_category in ('set', 'two_pair', 'nuts'):
        base = min(0.90, base + 0.15)
    return round(base, 2)


def _donk_frequency(hand_category: str, villain_cbet_freq: float) -> float:
    base = DONK_FREQUENCY.get(hand_category, 0.0)
    # If villain cbets very high, donk at higher frequency to deny EV
    if villain_cbet_freq >= 0.75:
        base = min(0.80, base + 0.10)
    return round(base, 2)


def _alternative_if_check(hand_category: str, villain_cbet_freq: float) -> str:
    """What to do if we check instead of donk."""
    if hand_category in ('set', 'two_pair', 'nuts'):
        return 'check_raise'
    elif hand_category in ('flush_draw_strong', 'oesd', 'combo_draw'):
        if villain_cbet_freq >= 0.65:
            return 'check_call'  # cbet likely; get equity
        return 'check_call'
    elif hand_category == 'middle_pair':
        return 'check_call'
    else:
        return 'check_fold'


def _bluff_donk_viable(board_texture: str, villain_cbet_freq: float, board_low_card: int) -> bool:
    """Whether bluff-donking is viable in this spot."""
    if villain_cbet_freq >= 0.70:
        return False  # if villain always cbets, our donk-bluff gets called always
    if board_texture in ('wet', 'monotone'):
        return False  # too many draws that call us
    return board_low_card <= 8  # low boards = we can rep a wider strong range


@dataclass
class DonkRangePlan:
    # Inputs
    hero_hand_category: str
    board_texture: str
    board_low_card: int
    villain_cbet_freq: float
    villain_position: str
    street: str
    pot_bb: float
    spr: float
    hero_position: str

    # Analysis
    should_donk: bool
    donk_size: float
    donk_frequency: float
    has_nut_advantage: bool
    alternative_action: str   # what to do if checking
    bluff_donk_viable: bool

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def build_donk_range(
    hero_hand_category: str = 'set',
    board_texture: str = 'wet',
    board_low_card: int = 7,
    villain_cbet_freq: float = 0.72,
    villain_position: str = 'btn',
    street: str = 'flop',
    pot_bb: float = 15.0,
    spr: float = 6.5,
    hero_position: str = 'bb',
) -> DonkRangePlan:
    """
    Build OOP donk bet range decision.

    Args:
        hero_hand_category: Current hand strength
        board_texture:      'dry' / 'wet' / 'semi_wet' / 'monotone'
        board_low_card:     Value of lowest card on board (2-14)
        villain_cbet_freq:  Villain c-bet frequency (0.0-1.0)
        villain_position:   Villain's position
        street:             'flop' / 'turn' / 'river'
        pot_bb:             Current pot in BB
        spr:                Stack-to-pot ratio
        hero_position:      Hero's position (OOP: 'bb' / 'sb')

    Returns:
        DonkRangePlan
    """
    nut_adv = _has_nut_advantage(board_low_card, hero_position)
    do_donk = _should_donk(hero_hand_category, board_texture, board_low_card,
                            villain_cbet_freq, hero_position)
    size = _donk_size(hero_hand_category, board_texture, street)
    freq = _donk_frequency(hero_hand_category, villain_cbet_freq)
    alt = _alternative_if_check(hero_hand_category, villain_cbet_freq)
    bluff_ok = _bluff_donk_viable(board_texture, villain_cbet_freq, board_low_card)

    action = f'DONK {size:.0%}pot ({freq:.0%} of combos)' if do_donk else f'{alt.upper()}'

    verdict = (
        f'[DBRB {hero_hand_category}|{street}|{hero_position}] '
        f'{action} nut_adv={nut_adv} | '
        f'villain_cbet={villain_cbet_freq:.0%}'
    )

    reasoning = (
        f'Donk range build: {hero_hand_category} OOP ({hero_position}) vs {villain_position} on '
        f'{board_texture} board (low card={board_low_card}). '
        f'Nut advantage: {nut_adv}. '
        f'Villain cbet={villain_cbet_freq:.0%}. '
        f'Should donk: {do_donk}. Size: {size:.0%}. Frequency: {freq:.0%}. '
        f'Bluff donk viable: {bluff_ok}.'
    )

    tips = []

    tips.append(
        f'DONK BET THEORY: OOP lead before aggressor acts. '
        f'{"NUT ADVANTAGE detected: low board ("+str(board_low_card)+") favors BB/SB caller range." if nut_adv else "No clear nut advantage: donking range is narrow."} '
        f'Best donk candidates: sets, two-pair, flush draws (strong), OESD.'
    )

    if do_donk:
        tips.append(
            f'DONK SIZE: {size:.0%} pot for {hero_hand_category}. '
            f'Frequency: donk {freq:.0%} of combos, check {1-freq:.0%}. '
            f'Mixed strategy adds deception: villain cannot always call or always fold.'
        )
    else:
        tips.append(
            f'CHECK INSTEAD: {hero_hand_category} plays better as check on {board_texture} board. '
            f'Plan: {alt.upper()} after check. '
            f'If villain cbets ({villain_cbet_freq:.0%}): '
            f'{"check-raise traps maximum value" if "raise" in alt else "check-call to see turn"}.'
        )

    tips.append(
        f'VILLAIN CBET ADJUSTMENT: villain cbets {villain_cbet_freq:.0%}. '
        f'{"HIGH cbet: donk to deny aggressor free bet EV; forces them to face a bet without initiative." if villain_cbet_freq >= 0.65 else "MODERATE cbet: donk only with strong value; checking and calling is fine."}'
    )

    if bluff_ok:
        tips.append(
            f'BLUFF DONK viable: dry board + controlled cbet frequency. '
            f'Small donk (28-33%) with: backdoor flush draws, gutshots, low pairs. '
            f'Represents strong low pair. Fold when raised. Do not bluff-donk on wet boards.'
        )
    else:
        tips.append(
            f'NO BLUFF DONKS in this spot: '
            f'{"villain cbets too high = your donk always gets called" if villain_cbet_freq >= 0.70 else "wet/monotone board = too many draws call your bluff donk"}. '
            f'Keep donk range value-heavy.'
        )

    return DonkRangePlan(
        hero_hand_category=hero_hand_category,
        board_texture=board_texture,
        board_low_card=board_low_card,
        villain_cbet_freq=villain_cbet_freq,
        villain_position=villain_position,
        street=street,
        pot_bb=pot_bb,
        spr=spr,
        hero_position=hero_position,
        should_donk=do_donk,
        donk_size=size,
        donk_frequency=freq,
        has_nut_advantage=nut_adv,
        alternative_action=alt,
        bluff_donk_viable=bluff_ok,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def dbrb_one_liner(r: DonkRangePlan) -> str:
    action = f'DONK {r.donk_size:.0%}pot' if r.should_donk else r.alternative_action.upper()
    return (
        f'[DBRB {r.hero_hand_category}|{r.street}|{r.hero_position}] '
        f'{action} freq={r.donk_frequency:.0%} | '
        f'nut_adv={r.has_nut_advantage}'
    )
