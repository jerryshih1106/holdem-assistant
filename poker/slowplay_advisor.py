"""
Slowplay Advisor (slowplay_advisor.py)

One of the most common leaks in live poker: over-slowplaying strong hands on
wet boards (giving free cards to draws) or under-slowplaying on dry boards
against aggressive villains (missing value by betting into players who would
have bet themselves).

When to slowplay:
  - Dry board (no realistic draws) + aggressive villain (AF >= 2.5): check to
    induce a bluff or thin value bet from villain. Hero traps.
  - IP + strong hand + villain in primary betting role: let them barrel.
  - River: never slowplay (last chance for value).

When to value bet immediately:
  - Wet board: draws will hit if you give a free card.
  - OOP: giving a free card out of position is almost always wrong.
  - Passive villain (AF < 1.5): they check behind; must build pot yourself.
  - Loose/calling station (VPIP > 45%): they call large bets — extract max.
  - Two pair on a board with pair+draw: vulnerable hand, charge draws now.
  - Turn (second-to-last street): running out of chances to build pot.

Slowplay frequencies by scenario:
  Dry board, IP, aggressive villain (AF >= 2.5), nut hand:  40-60%
  Dry board, IP, average villain (1.5-2.5), nut hand:       20-35%
  Dry board, OOP, any villain:                               10-20%
  Wet board, IP, aggressive villain:                          0-10%
  Wet board, OOP, any villain:                                0%

Key insight: Slowplaying works best when villain is betting-happy. Against
check-behind players (AF < 1.5), you MUST build the pot yourself or you get
a free showdown that costs you 30-40% of a full pot.

Usage:
    from poker.slowplay_advisor import advise_slowplay, SlowplayAdvice, slowplay_one_liner
    result = advise_slowplay(
        hero_hand_class='set',
        board_type='dry',
        hero_pos='IP',
        villain_vpip=0.35,
        villain_af=2.5,
        villain_wtsd=0.30,
        street='flop',
        pot_bb=20.0,
        eff_stack_bb=100.0,
    )
    print(result.action, result.slowplay_freq)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    """0=air, 10=absolute nuts."""
    return {
        'trash': 0, 'air': 0, 'draw': 1, 'backdoor': 1,
        'bottom_pair': 2, 'middle_pair': 3, 'top_pair': 4, 'tptk': 5,
        'medium': 4, 'overpair': 6, 'two_pair': 6, 'strong': 7,
        'straight': 8, 'flush': 8, 'set': 9, 'full_house': 10,
        'quads': 10, 'nuts': 10, 'premium': 8,
    }.get(hand_class.lower(), 5)


def _is_nut_type(hand_class: str) -> bool:
    return hand_class.lower() in ('set', 'straight', 'flush', 'full_house', 'quads', 'nuts')


def _base_slowplay_freq(
    board_type: str,
    hero_pos: str,
    hand_class: str,
) -> float:
    """Base slowplay frequency before adjustments."""
    if board_type == 'wet':
        return 0.05  # almost never slowplay wet boards
    if board_type == 'medium':
        base = 0.20
    else:  # dry
        base = 0.40

    # Position penalty: OOP = dangerous to give free card
    if hero_pos == 'OOP':
        base -= 0.20

    # Hand strength: only nut-type hands can be slowplayed profitably
    if not _is_nut_type(hand_class):
        base -= 0.15   # two_pair, overpair: mostly value bet

    return max(0.0, base)


def _adjust_for_villain(
    base_freq: float,
    villain_af: float,
    villain_vpip: float,
    villain_wtsd: float,
) -> float:
    freq = base_freq

    # High AF villain: bets a lot → slowplay is rewarded (they'll bet into us)
    if villain_af >= 3.0:
        freq += 0.20
    elif villain_af >= 2.0:
        freq += 0.10
    elif villain_af < 1.5:
        # Passive villain: will check behind → must value bet immediately
        freq -= 0.25

    # Loose/calling station: they call large bets → extract now
    if villain_vpip >= 0.50:
        freq -= 0.15
    elif villain_vpip >= 0.40:
        freq -= 0.08

    # High WTSD: likes to see showdowns → they'll call a bet (value bet preferred)
    if villain_wtsd >= 0.40:
        freq -= 0.10

    return max(0.0, min(0.80, freq))


def _adjust_for_street(freq: float, street: str) -> float:
    """Less slowplay on later streets (running out of streets to extract)."""
    adj = {'flop': 0.0, 'turn': -0.10, 'river': -0.50}
    return max(0.0, freq + adj.get(street, 0.0))


def _value_bet_size_pct(
    board_type: str,
    villain_vpip: float,
    hero_hand_class: str,
) -> float:
    """Recommended value bet size as fraction of pot."""
    # Dry board: smaller bet (don't over-fold villain)
    base = {'dry': 0.40, 'medium': 0.50, 'wet': 0.65}.get(board_type, 0.50)

    # Loose players call bigger bets → extract more
    if villain_vpip >= 0.50:
        base += 0.15
    elif villain_vpip >= 0.40:
        base += 0.08

    # Nut hands can bet larger on dry boards to protect (fewer draws anyway)
    if _is_nut_type(hero_hand_class) and board_type == 'dry':
        base -= 0.05   # actually smaller, let them call light

    return round(min(0.85, max(0.25, base)), 2)


def _action_from_freq(freq: float) -> str:
    if freq >= 0.50:
        return 'slowplay'
    if freq >= 0.20:
        return 'mixed'
    return 'value_bet'


def _recommended_line(
    action: str,
    hero_pos: str,
    villain_af: float,
    street: str,
    value_bet_pct: float,
) -> str:
    if action == 'slowplay':
        if hero_pos == 'IP':
            return f'check_back (induce villain bet on next street)'
        else:
            return f'check_call (let villain bet into you)'
    if action == 'mixed':
        return (
            f'mixed: check {100 - int(100 * (1 - 0.5)):.0f}% / '
            f'value_bet_{value_bet_pct:.0%}pot {100 - int(100 * 0.5):.0f}%'
        )
    return f'value_bet {value_bet_pct:.0%} pot'


@dataclass
class SlowplayAdvice:
    """Advice on whether to slowplay or immediately value bet a strong hand."""
    hero_hand_class: str
    board_type: str
    hero_pos: str
    villain_vpip: float
    villain_af: float
    villain_wtsd: float
    street: str
    pot_bb: float
    eff_stack_bb: float

    # Decision
    action: str              # 'slowplay', 'value_bet', 'mixed'
    slowplay_freq: float     # 0-1: how often to slowplay in this spot
    recommended_line: str    # e.g., 'check_back', 'value_bet 50% pot'

    # If value betting
    value_bet_size_pct: float
    value_bet_bb: float      # actual BB amount

    # Key factors
    is_nut_type_hand: bool
    wet_board_warning: bool  # True if board is dangerous to slowplay
    passive_villain_warning: bool  # True if villain likely won't bet for us

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_slowplay(
    hero_hand_class: str = 'set',
    board_type: str = 'dry',
    hero_pos: str = 'IP',
    villain_vpip: float = 0.35,
    villain_af: float = 2.0,
    villain_wtsd: float = 0.30,
    street: str = 'flop',
    pot_bb: float = 20.0,
    eff_stack_bb: float = 100.0,
) -> SlowplayAdvice:
    """
    Advise whether to slowplay or value bet a strong hand.

    Args:
        hero_hand_class:  Hero's hand strength (set, flush, two_pair, overpair, etc.)
        board_type:       'dry', 'medium', or 'wet'
        hero_pos:         'IP' (in position) or 'OOP' (out of position)
        villain_vpip:     Villain's VPIP (0-1)
        villain_af:       Villain's Aggression Factor
        villain_wtsd:     Villain's went-to-showdown (0-1)
        street:           'flop', 'turn', or 'river'
        pot_bb:           Current pot in big blinds
        eff_stack_bb:     Effective stack in big blinds

    Returns:
        SlowplayAdvice
    """
    is_nut = _is_nut_type(hero_hand_class)
    hand_rank = _hand_rank(hero_hand_class)

    base_freq = _base_slowplay_freq(board_type, hero_pos, hero_hand_class)
    adj_freq = _adjust_for_villain(base_freq, villain_af, villain_vpip, villain_wtsd)
    final_freq = _adjust_for_street(adj_freq, street)

    action = _action_from_freq(final_freq)
    val_pct = _value_bet_size_pct(board_type, villain_vpip, hero_hand_class)
    val_bb = round(pot_bb * val_pct, 1)
    line = _recommended_line(action, hero_pos, villain_af, street, val_pct)

    wet_warning = board_type == 'wet' and final_freq >= 0.10
    passive_warning = villain_af < 1.5

    # Build reasoning
    factors = []
    if board_type == 'wet':
        factors.append(f'WET board: draws can complete, never give free cards')
    elif board_type == 'dry':
        factors.append(f'DRY board: safe to slowplay')
    if hero_pos == 'OOP':
        factors.append('OOP: giving free cards OOP is dangerous')
    if villain_af >= 2.5:
        factors.append(f'high AF={villain_af:.1f}: villain bets often when checked (good for trapping)')
    elif villain_af < 1.5:
        factors.append(f'low AF={villain_af:.1f}: villain checks behind (value bet NOW)')
    if villain_vpip >= 0.45:
        factors.append(f'loose villain (VPIP={villain_vpip:.0%}): calls big bets (extract value)')
    if street in ('turn', 'river'):
        factors.append(f'{street}: running out of streets, lean toward value betting')
    reasoning = f'{action.upper()} ({final_freq:.0%} slowplay freq). Factors: ' + '; '.join(factors) + '.'

    # Tips
    tips = []
    if action == 'slowplay' and hero_pos == 'OOP':
        tips.append(
            'Slowplaying OOP is tricky: check, then call villain bet. '
            'If villain checks back, you lost value and the pot stays small. '
            'Higher risk than IP slowplay.'
        )
    if board_type == 'wet' and is_nut:
        tips.append(
            f'Even with {hero_hand_class} on a wet board, drawing players have equity. '
            f'Bet {val_pct:.0%} pot to charge them. A set on a two-flush board gives '
            f'flush draws ~35% equity — charging them is worth more than trapping.'
        )
    if passive_warning:
        tips.append(
            f'Passive villain (AF={villain_af:.1f}): they check behind weak hands and '
            f'only bet when strong. Slowplaying means getting to showdown for free — '
            f'you miss a full street of value. Value bet NOW.'
        )
    if action == 'slowplay' and street == 'flop':
        tips.append(
            f'Slowplay plan: check flop, then raise villain\'s turn bet or lead out '
            f'if checked back. Never slowplay all three streets — you must start '
            f'building the pot by the turn or the river bet will be an overbet.'
        )
    if not is_nut and action in ('mixed', 'value_bet'):
        tips.append(
            f'{hero_hand_class} is strong but not the nuts. '
            f'Value bet to protect equity and charge draws. '
            f'Slowplaying non-nut hands leaves you vulnerable to being outdrawn.'
        )
    if street == 'river':
        tips.append(
            'River: always value bet strong hands. There are no more streets to '
            'extract value — check-calling river is only for pot control or blocking.'
        )

    return SlowplayAdvice(
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        hero_pos=hero_pos,
        villain_vpip=villain_vpip,
        villain_af=villain_af,
        villain_wtsd=villain_wtsd,
        street=street,
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        action=action,
        slowplay_freq=round(final_freq, 3),
        recommended_line=line,
        value_bet_size_pct=val_pct,
        value_bet_bb=val_bb,
        is_nut_type_hand=is_nut,
        wet_board_warning=wet_warning,
        passive_villain_warning=passive_warning,
        reasoning=reasoning,
        tips=tips,
    )


def slowplay_one_liner(result: SlowplayAdvice) -> str:
    return (
        f'[SLP {result.hero_hand_class}@{result.board_type}|{result.hero_pos}] '
        f'{result.action.upper()} | '
        f'freq={result.slowplay_freq:.0%} | '
        f'line={result.recommended_line[:30]} | '
        f'AF={result.villain_af:.1f}'
    )
