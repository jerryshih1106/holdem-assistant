"""
IP Range Protector (ip_range_protector.py)

When playing in position (IP), checking back flop/turn can make your
checking range dangerously weak and exploitable. This module advises
how to protect your IP checking range by balancing check-backs with
strong slow-plays, and when to bet vs check for range balance reasons.

RANGE PROTECTION PROBLEM:
  If IP player always:
    - Bets: strong hands, draws
    - Checks: only weak hands (pair lower, air)
  Then villain KNOWS:
    - When IP checks back flop → IP is weak → bet into IP freely on turn
    - IP's check-back range is capped → cannot have sets, two pair

  SOLUTION: Occasionally slow-play strong hands (sets, top pair) when
  checking back to protect the check-back range. This makes villain
  uncertain about the strength of IP's checking range.

WHAT TO SLOW-PLAY (CHECK BACK IP):
  Strong hands that benefit from villain catching up:
  - Sets on dry boards (let villain improve to 2-pair)
  - Overpairs on non-threatening boards
  - Top pair with good kicker on dry flops

  HOW OFTEN:
  - Need to mix: check ~20-30% of strong hands to protect range
  - Exact % depends on board texture and villain tendencies

OOP VILLAIN VULNERABILITY:
  When villain is OOP, they have more incentive to bet if they think
  IP is weak. Our checking range protection prevents villain from
  running over us with aggression.

DISTINCT FROM:
  float_bet.py:               IP float calling strategy
  ip_turn_check_strategy.py:  Turn checking decisions IP
  THIS MODULE:                Range protection from IP perspective;
                              advises WHICH hands to check back for balance
                              and HOW OFTEN to slow-play vs bet

Usage:
    from poker.ip_range_protector import advise_ip_range_protection, IPRangeProtection, ipr_one_liner

    result = advise_ip_range_protection(
        hero_hand_category='set',
        board_texture='dry',
        street='flop',
        hero_equity=0.85,
        villain_af=2.5,
        villain_vpip=0.30,
        pot_bb=20.0,
        hero_stack_bb=90.0,
    )
    print(ipr_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Base checking rate for range protection by hand category
# Higher = more often we should check this hand to protect range
HAND_CHECKBACK_RATE = {
    'set':              0.30,   # mix slow-play
    'two_pair':         0.25,
    'overpair':         0.25,
    'top_pair':         0.20,
    'top_pair_2k':      0.25,   # top pair + 2nd kicker, protect vs overcards
    'flush':            0.15,   # mostly bet but occasionally slow-play
    'straight':         0.15,
    'full_house':       0.10,   # mostly bet
    'flush_draw':       0.10,   # semi-bluff mostly
    'straight_draw':    0.15,
    'combo_draw':       0.05,   # bet combo draws
    'middle_pair':      0.50,   # medium hands → mostly check-back
    'bottom_pair':      0.65,
    'weak_pair':        0.70,
    'overcards':        0.70,
    'air':              0.80,
    'gutshot':          0.60,
}


def _checkback_rate(
    hero_hand_category: str,
    board_texture: str,
    villain_af: float,
) -> float:
    """
    Recommended check-back rate for this hand.
    Higher AF villain → check back strong hands more (trap them).
    Wet board → bet draws and strong hands more.
    """
    base = HAND_CHECKBACK_RATE.get(hero_hand_category, 0.40)

    # Board texture adjustment
    texture_adj = {
        'dry':       0.05,    # dry board → more check-back (less urgency to protect)
        'semi_wet':  0.0,
        'wet':      -0.10,    # wet board → bet strong hands for protection
        'paired':    0.05,
        'monotone': -0.05,
    }.get(board_texture, 0.0)

    # High AF villain likes to bet when checked to → trap them by slow-playing
    af_adj = 0.0
    if villain_af >= 3.0 and hero_hand_category in ('set', 'two_pair', 'overpair', 'top_pair'):
        af_adj = 0.10   # more slow-play vs aggressive villains (they'll bet into us)
    elif villain_af <= 1.5:
        af_adj = -0.10  # passive villain won't bet; need to bet for value

    return round(min(0.90, max(0.05, base + texture_adj + af_adj)), 3)


def _protection_value(
    hero_hand_category: str,
    board_texture: str,
    hero_equity: float,
) -> float:
    """
    How valuable is it to check this hand for range protection?
    Strong hands with high equity checking back add the most protection.
    Returns 0-1 scale.
    """
    if hero_hand_category not in ('set', 'two_pair', 'overpair', 'top_pair', 'flush', 'straight'):
        return 0.1   # weak hands checking back doesn't add protection value

    equity_factor = hero_equity   # higher equity = checking adds more protection
    texture_bonus = 0.10 if board_texture == 'dry' else 0.0
    return round(min(1.0, equity_factor + texture_bonus), 3)


def _recommended_action(
    hero_hand_category: str,
    board_texture: str,
    street: str,
    checkback_rate: float,
    villain_af: float,
    hero_equity: float,
    protection_value: float,
) -> tuple:
    """(action: str, explanation: str)"""
    # Strong hands: decide bet vs slow-play
    if hero_hand_category in ('set', 'full_house', 'flush', 'straight'):
        if checkback_rate >= 0.20 and board_texture == 'dry':
            return (
                'mix_check_slow_play',
                f'Strong hand ({hero_hand_category}) on dry board: '
                f'check back {checkback_rate:.0%} to protect range. '
                f'Betting range is too strong if you always bet here. '
                f'Let villain catch up or barrel into your trap.'
            )
        else:
            return (
                'bet_for_value',
                f'Strong hand ({hero_hand_category}) on {board_texture} board: '
                f'bet for value and protection. Checking too often here gives up equity.'
            )

    if hero_hand_category in ('overpair', 'two_pair', 'top_pair', 'top_pair_2k'):
        if villain_af >= 2.5 and checkback_rate >= 0.25:
            return (
                'mix_check_trap',
                f'{hero_hand_category}: Mix check-back {checkback_rate:.0%} to trap aggressive villain (AF={villain_af:.1f}). '
                f'When you check, villain will bet bluffs/draws into your strong hand.'
            )
        elif board_texture in ('dry', 'paired') and hero_equity >= 0.65:
            return (
                'mix_check_protect',
                f'{hero_hand_category} on {board_texture} board: '
                f'Check back {checkback_rate:.0%} to balance range. '
                f'Bet {1-checkback_rate:.0%} for value.'
            )
        else:
            return (
                'bet_for_value',
                f'{hero_hand_category}: Bet for value. Too few turns/rivers left for slow-play.'
            )

    if hero_hand_category in ('flush_draw', 'straight_draw', 'combo_draw'):
        if hero_equity >= 0.40:
            return (
                'bet_semi_bluff',
                f'Draw ({hero_hand_category}, equity={hero_equity:.0%}): semi-bluff for equity. '
                f'Mix with occasional checks to avoid over-betting drawing range.'
            )
        else:
            return (
                'mix_check_draw',
                f'Weak draw: check back. Equity too low to semi-bluff profitably. '
                f'Take free card and reevaluate.'
            )

    # Weak/marginal: mostly check
    return (
        'check_back',
        f'Weak hand ({hero_hand_category}): check back for pot control. '
        f'Do not bet with weak hands just to represent strength.'
    )


@dataclass
class IPRangeProtection:
    # Inputs
    hero_hand_category: str
    board_texture: str
    street: str
    hero_equity: float
    villain_af: float
    villain_vpip: float
    pot_bb: float
    hero_stack_bb: float

    # Analysis
    checkback_rate: float         # recommended check-back frequency
    protection_value: float       # range protection value of checking (0-1)

    # Recommendation
    action: str
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_ip_range_protection(
    hero_hand_category: str = 'set',
    board_texture: str = 'dry',
    street: str = 'flop',
    hero_equity: float = 0.85,
    villain_af: float = 2.5,
    villain_vpip: float = 0.30,
    pot_bb: float = 20.0,
    hero_stack_bb: float = 90.0,
) -> IPRangeProtection:
    """
    Advise how to play IP to protect checking range.

    Args:
        hero_hand_category:  Current hand category
        board_texture:       'dry' / 'semi_wet' / 'wet' / 'paired' / 'monotone'
        street:              'flop' / 'turn' / 'river'
        hero_equity:         Hero's equity fraction (0-1)
        villain_af:          Villain's aggression factor
        villain_vpip:        Villain's VPIP
        pot_bb:              Current pot
        hero_stack_bb:       Hero's effective stack

    Returns:
        IPRangeProtection
    """
    cb_rate = _checkback_rate(hero_hand_category, board_texture, villain_af)
    prot_value = _protection_value(hero_hand_category, board_texture, hero_equity)

    action, action_exp = _recommended_action(
        hero_hand_category, board_texture, street, cb_rate, villain_af, hero_equity, prot_value
    )

    reasoning = (
        f'IP Range Protection: {hero_hand_category} on {board_texture} {street}. '
        f'Equity={hero_equity:.0%}. Villain AF={villain_af:.1f}, VPIP={villain_vpip:.0%}. '
        f'Checkback rate={cb_rate:.0%}. Protection value={prot_value:.2f}. '
        f'Action={action}.'
    )

    verdict = (
        f'[IPR {hero_hand_category.upper()}|{board_texture}|{street}] '
        f'{action.upper()} | checkback={cb_rate:.0%} protection={prot_value:.2f}'
    )

    tips = [action_exp]

    tips.append(
        f'RANGE PROTECTION SUMMARY: IP checking range needs strong hands to be credible. '
        f'Check back {cb_rate:.0%} of {hero_hand_category} hands on {board_texture} {street}. '
        f'This prevents villain from running over your "capped" check-back range.'
    )

    if villain_af >= 3.0 and hero_hand_category in ('set', 'two_pair', 'overpair', 'top_pair'):
        tips.append(
            f'TRAP OPPORTUNITY (AF={villain_af:.1f}): Villain is aggressive. '
            f'When you check back this hand, villain will bet with weak hands. '
            f'Check-call or check-raise the turn to extract maximum value.'
        )

    if villain_af <= 1.5:
        tips.append(
            f'PASSIVE VILLAIN (AF={villain_af:.1f}): Villain won\'t bet into you much. '
            f'Bet your strong hands for value -- slow-play loses EV vs passive players '
            f'who will check back when you check.'
        )

    if board_texture == 'wet' and hero_hand_category in ('set', 'two_pair', 'flush', 'straight'):
        tips.append(
            f'WET BOARD + STRONG HAND: Bet for protection and value. '
            f'Draws are live; if you check, villain takes free card on a dangerous board. '
            f'Reduce slow-play frequency on wet textures.'
        )

    if street == 'river':
        tips.append(
            f'RIVER: Range protection is less important on the river (no future streets). '
            f'Prioritize maximizing EV. Bet strong hands for value; check if pot control needed.'
        )

    return IPRangeProtection(
        hero_hand_category=hero_hand_category,
        board_texture=board_texture,
        street=street,
        hero_equity=hero_equity,
        villain_af=villain_af,
        villain_vpip=villain_vpip,
        pot_bb=pot_bb,
        hero_stack_bb=hero_stack_bb,
        checkback_rate=cb_rate,
        protection_value=prot_value,
        action=action,
        action_explanation=action_exp,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ipr_one_liner(r: IPRangeProtection) -> str:
    return (
        f'[IPR {r.hero_hand_category.upper()}|{r.board_texture}|{r.street}] '
        f'{r.action.upper()} | '
        f'checkback={r.checkback_rate:.0%} protection={r.protection_value:.2f}'
    )
