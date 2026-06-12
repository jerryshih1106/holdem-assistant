"""
Turn Scare Card Advisor (turn_scare_card_advisor.py)

Advises on strategy adjustment when a scare card appears on the turn.
Scare cards dramatically shift range advantages and require immediate
strategic adjustment.

SCARE CARD TYPES:
  ace_on_low_board:    A falls on low board (hero bet flop; A now in villain's range)
  flush_completes:     3rd flush suit appears (many draws completed)
  straight_completes:  Board now has 4-straight or completes common straight
  board_pairs:         A paired board (trips/boats enter ranges)
  king_on_medium:      K falls on medium board (Broadway hands connect)
  broadway_card:       T/J/Q/K appears on low runout

HOW SCARE CARDS AFFECT STRATEGY:
  1. RANGE RE-EVALUATION: Scare card benefits villain's flatting range more than
     PFR's range. E.g., BTN opens, BB calls. Turn A: BB has more Ax hands (A5s, A2s).
  2. BET SIZING ADJUSTMENT: Bet smaller on scare cards (villain calls wider; sizing down
     charges draws while avoiding bloating pot vs strong hands).
  3. CHECK-BACK MORE: IP players should check back scare cards more to protect range.
  4. BLUFF-CATCH LESS: When villain bets into a scare card, their range is stronger.
  5. DELAYED CBET OPPORTUNITY: If hero checked flop, scare card arrives → hero now has
     a "scare card bluff" opportunity.

DISTINCT FROM:
  turn_texture_change.py:    Detects and analyzes texture changes
  turn_barrel_decision.py:   Double-barrel decision
  THIS MODULE:               Scare card-specific strategy adjustments with
                             role-aware advice (PFR vs caller; IP vs OOP)

Usage:
    from poker.turn_scare_card_advisor import advise_scare_card, ScareCardAdvice, sca_one_liner

    result = advise_scare_card(
        scare_card_type='ace_on_low_board',
        hero_role='pfr',
        hero_position='ip',
        hero_hand_category='top_pair',
        hero_has_scare_card_blocker=False,
        villain_vpip=0.30,
        villain_af=2.0,
        flop_action='hero_cbet_called',
        pot_bb=20.0,
        hero_stack_bb=80.0,
    )
    print(sca_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# How much each scare card type benefits villain's calling range (vs PFR range)
VILLAIN_RANGE_BENEFIT = {
    'ace_on_low_board':   0.65,  # AA/AK in PFR; A5s/A2s in caller's flatting range
    'flush_completes':    0.55,  # Both ranges have suited hands; caller has more off-suit draws
    'straight_completes': 0.50,  # Connectors in both ranges; roughly equal
    'board_pairs':        0.40,  # PFR has overpairs; caller has more small pairs
    'king_on_medium':     0.55,  # KQ/KJ in PFR; KTs/K9s in caller's flatting range
    'broadway_card':      0.45,  # Broadway hands more in PFR; suited broadway in caller
}

# Bet size adjustment multiplier on scare cards (vs normal sizing)
SIZE_ADJ_ON_SCARE = {
    'ace_on_low_board':   0.65,  # bet smaller: villain called with Ax; size down
    'flush_completes':    0.80,  # medium adjustment
    'straight_completes': 0.75,
    'board_pairs':        0.60,  # bet much smaller: villain has trips sometimes
    'king_on_medium':     0.70,
    'broadway_card':      0.75,
}


def _hero_range_benefit(scare_card_type: str, hero_role: str, hero_hand_category: str) -> float:
    """How much the scare card benefits hero's range specifically."""
    villain_benefit = VILLAIN_RANGE_BENEFIT.get(scare_card_type, 0.50)
    hero_benefit = 1.0 - villain_benefit  # if villain benefits 65%, hero benefits 35%

    # Adjust if hero has connecting cards
    if hero_has_blocker_to_scare(scare_card_type, hero_hand_category):
        hero_benefit += 0.15

    return round(min(0.85, max(0.05, hero_benefit)), 3)


def hero_has_blocker_to_scare(scare_card_type: str, hero_hand_category: str) -> bool:
    """Does hero's hand block the scare card's strength?"""
    blocker_hands = {
        'ace_on_low_board':   ('top_pair', 'ace_high', 'two_pair', 'set'),
        'flush_completes':    ('flush', 'flush_draw_complete', 'top_pair_flush'),
        'straight_completes': ('straight', 'two_pair', 'set'),
        'board_pairs':        ('set', 'full_house', 'trips'),
        'king_on_medium':     ('top_pair', 'overpair', 'two_pair'),
        'broadway_card':      ('top_pair', 'overpair', 'two_pair'),
    }
    return hero_hand_category in blocker_hands.get(scare_card_type, ())


def _bluff_opportunity(
    scare_card_type: str,
    hero_role: str,
    hero_position: str,
    flop_action: str,
    villain_vpip: float,
) -> tuple:
    """
    (has_bluff_opportunity: bool, frequency: float, description: str)
    Scare card bluff: hero checked/called flop; scare card arrives → bet as bluff.
    """
    if hero_role == 'caller' and flop_action in ('check_check', 'villain_cbet_hero_called'):
        if scare_card_type in ('ace_on_low_board', 'flush_completes', 'straight_completes'):
            freq = 0.45 if hero_position == 'oop' else 0.55
            desc = (
                f'SCARE CARD BLUFF OPPORTUNITY: {scare_card_type.replace("_", " ")} is a great '
                f'bluff card for caller (hero). PFR typically does not have Ax/flush in their '
                f'c-betting range. Bet {freq:.0%} of air hands as bluff.'
            )
            return True, freq, desc
    elif hero_role == 'pfr' and scare_card_type in ('ace_on_low_board', 'king_on_medium'):
        freq = 0.35   # PFR has some Ax/Kx to bet for value; bluffs balance this
        desc = (
            f'PFR SCARE CARD CONTINUATION: You have Ax/Kx hands in your range. '
            f'Bet {freq:.0%} frequency with air to balance value hands.'
        )
        return True, freq, desc
    return False, 0.0, 'No clear bluff opportunity on this scare card.'


def _primary_action(
    scare_card_type: str,
    hero_role: str,
    hero_position: str,
    hero_hand_category: str,
    hero_has_blocker: bool,
    flop_action: str,
    villain_af: float,
) -> tuple:
    """(action: str, sizing_adj: float, explanation: str)"""
    size_adj = SIZE_ADJ_ON_SCARE.get(scare_card_type, 0.75)

    if hero_hand_category in ('flush', 'straight', 'set', 'two_pair', 'full_house'):
        return 'bet_value', size_adj, f'Strong hand: bet for value at {size_adj:.0%} normal size (protect vs draws too).'

    if hero_role == 'pfr' and flop_action == 'hero_cbet_called':
        if hero_has_blocker:
            return 'bet_small', size_adj, f'PFR with blocker: bet {size_adj:.0%} size to represent top of range.'
        else:
            if scare_card_type in ('ace_on_low_board', 'board_pairs'):
                return 'check_back', 0.0, 'PFR without blocker on ace/paired turn: check back to protect range.'
            else:
                return 'bet_small', max(0.50, size_adj), 'PFR: bet small to apply pressure; sizing down on scare card.'

    if hero_role == 'caller':
        if hero_has_blocker and hero_position == 'ip':
            return 'bet_scare', size_adj + 0.10, 'Caller with blocker IP: represent the scare card.'
        elif hero_position == 'oop':
            return 'check_evaluate', 0.0, 'Caller OOP: check and evaluate vs villain bet; do not lead scare card without blocker.'
        else:
            return 'check_back', 0.0, 'Caller IP without blocker: check back; scare card does not help your range significantly.'

    return 'check_evaluate', 0.0, 'Default: check and evaluate.'


@dataclass
class ScareCardAdvice:
    # Inputs
    scare_card_type: str
    hero_role: str
    hero_position: str
    hero_hand_category: str
    hero_has_scare_card_blocker: bool
    villain_vpip: float
    villain_af: float
    flop_action: str
    pot_bb: float
    hero_stack_bb: float

    # Analysis
    villain_range_benefit: float   # how much scare card benefits villain (0-1)
    hero_range_benefit: float      # how much scare card benefits hero (0-1)
    range_advantage: str           # 'hero' / 'villain' / 'neutral'
    has_bluff_opportunity: bool
    bluff_frequency: float
    bluff_description: str

    # Recommendation
    primary_action: str            # 'bet_value'/'bet_small'/'bet_scare'/'check_back'/'check_evaluate'
    sizing_adjustment: float       # multiplier vs normal sizing (0.60 = bet 60% of normal size)
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_scare_card(
    scare_card_type: str = 'ace_on_low_board',
    hero_role: str = 'pfr',
    hero_position: str = 'ip',
    hero_hand_category: str = 'top_pair',
    hero_has_scare_card_blocker: bool = False,
    villain_vpip: float = 0.30,
    villain_af: float = 2.0,
    flop_action: str = 'hero_cbet_called',
    pot_bb: float = 20.0,
    hero_stack_bb: float = 80.0,
) -> ScareCardAdvice:
    """
    Advise on strategy when a scare card appears on the turn.

    Args:
        scare_card_type:            'ace_on_low_board' / 'flush_completes' /
                                    'straight_completes' / 'board_pairs' /
                                    'king_on_medium' / 'broadway_card'
        hero_role:                  'pfr' / 'caller'
        hero_position:              'ip' / 'oop'
        hero_hand_category:         Current hand category
        hero_has_scare_card_blocker: Hero holds a card that blocks the scare
        villain_vpip/af:            HUD stats
        flop_action:                'hero_cbet_called' / 'check_check' /
                                    'villain_cbet_hero_called' / 'hero_donk_called'
        pot_bb:                     Current pot in BBs
        hero_stack_bb:              Effective stack

    Returns:
        ScareCardAdvice
    """
    v_benefit = VILLAIN_RANGE_BENEFIT.get(scare_card_type, 0.50)
    h_benefit = _hero_range_benefit(scare_card_type, hero_role, hero_hand_category)
    has_blocker = hero_has_scare_card_blocker or hero_has_blocker_to_scare(scare_card_type, hero_hand_category)

    range_adv = (
        'hero'    if h_benefit > 0.55 else
        'villain' if v_benefit > 0.55 else
        'neutral'
    )

    has_bluff, bluff_freq, bluff_desc = _bluff_opportunity(
        scare_card_type, hero_role, hero_position, flop_action, villain_vpip
    )

    action, size_adj, action_exp = _primary_action(
        scare_card_type, hero_role, hero_position, hero_hand_category,
        has_blocker, flop_action, villain_af
    )

    reasoning = (
        f'Scare card: {scare_card_type.replace("_", " ")} on turn. '
        f'Hero={hero_role} {hero_position}. Hand={hero_hand_category}. '
        f'Flop action={flop_action}. '
        f'Villain range benefit={v_benefit:.0%}; hero range benefit={h_benefit:.0%}. '
        f'Range advantage={range_adv}. Blocker={has_blocker}. '
        f'Action={action} size_adj={size_adj:.0%}.'
    )

    verdict = (
        f'[SCA {scare_card_type.upper()}|{hero_role}|{hero_position}] '
        f'{action.upper()} size_adj={size_adj:.0%} | '
        f'range_adv={range_adv} villain_benefit={v_benefit:.0%} | '
        f'bluff={has_bluff}'
    )

    tips = [action_exp]

    if has_bluff:
        tips.append(bluff_desc)

    if range_adv == 'villain':
        tips.append(
            f'RANGE DISADVANTAGE on {scare_card_type.replace("_"," ")}: '
            f'Villain benefits {v_benefit:.0%} from this card. '
            f'Check more, bet smaller, and be cautious about building a big pot. '
            f'Villain\'s calling range just improved significantly.'
        )
    elif range_adv == 'hero':
        tips.append(
            f'RANGE ADVANTAGE on {scare_card_type.replace("_"," ")}: '
            f'This card improves your range relatively. '
            f'Bet at normal frequency; you can represent these cards credibly.'
        )

    if villain_af >= 3.0:
        tips.append(
            f'HIGH AF VILLAIN (AF={villain_af:.1f}): Expect aggression on scare cards. '
            f'If you check, villain may bet as a bluff representing the scare card. '
            f'Have a check-raise plan with strong hands.'
        )

    if scare_card_type == 'board_pairs' and hero_hand_category in ('top_pair', 'overpair'):
        tips.append(
            f'BOARD PAIRS with {hero_hand_category}: Your hand is now vulnerable to trips. '
            f'Bet small (protection) or check-back (pot control). '
            f'Bet-fold if villain raises -- you are likely losing to trips/boat.'
        )

    return ScareCardAdvice(
        scare_card_type=scare_card_type,
        hero_role=hero_role,
        hero_position=hero_position,
        hero_hand_category=hero_hand_category,
        hero_has_scare_card_blocker=has_blocker,
        villain_vpip=villain_vpip,
        villain_af=villain_af,
        flop_action=flop_action,
        pot_bb=pot_bb,
        hero_stack_bb=hero_stack_bb,
        villain_range_benefit=v_benefit,
        hero_range_benefit=h_benefit,
        range_advantage=range_adv,
        has_bluff_opportunity=has_bluff,
        bluff_frequency=bluff_freq,
        bluff_description=bluff_desc,
        primary_action=action,
        sizing_adjustment=size_adj,
        action_explanation=action_exp,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sca_one_liner(r: ScareCardAdvice) -> str:
    return (
        f'[SCA {r.scare_card_type.upper()}|{r.hero_role}|{r.hero_position}] '
        f'{r.primary_action.upper()} size_adj={r.sizing_adjustment:.0%} | '
        f'range_adv={r.range_advantage} | bluff={r.bluff_frequency:.0%}'
    )
