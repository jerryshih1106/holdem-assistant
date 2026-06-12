"""
Wet Board Strategy (wet_board_strategy.py)

Strategy guide for playing on wet (draw-heavy) boards.
Wet boards require special handling because:
  1. Equity is more evenly distributed (draws = live outs)
  2. Strong made hands need protection (prevent free cards)
  3. Semi-bluffs are more profitable (equity + fold equity)
  4. Value hand ranges are closer together

WET BOARD CHARACTERISTICS:
  FULLY WET: 3 flush cards, or 2-connected + 2-flush (e.g., 8h7h6c)
    - Many possible straights and flushes
    - C-bet sizing: 30-45% (small, keep draws in; deny free cards)
    - Protection bets: mandatory with TPTK+

  SEMI-WET: 2 flush cards, or 2-connected (e.g., Ts8h7c)
    - Fewer combinations but still dangerous
    - C-bet sizing: 45-65% (standard to slightly smaller)
    - Medium-strength hands: check more

  BOARD TEXTURE ADJUSTMENTS:
    - More draws = smaller bet size (protect but keep them in)
    - Position matters more (IP can control bet size better)
    - Value hands MUST bet (giving free cards is very costly)

PROTECTION THEORY:
  On a wet board, folding villain's equity is valuable.
  If villain has a flush draw: 9 outs = ~36% equity on flop.
  Giving free card: losing ~36% of pot on average.
  Betting 50% pot: villain needs 25% pot odds to continue.
  If they fold: win 100% now; net +EV.

DISTINCT FROM:
  board_texture_advisor.py:    General texture analysis
  cbet_sizing.py:              C-bet size guide
  THIS MODULE:                 Wet-board-specific strategy; protection theory;
                               how to play different hand types on wet boards

Usage:
    from poker.wet_board_strategy import plan_wet_board, WetBoardPlan, wbs_one_liner

    result = plan_wet_board(
        hero_hand_category='top_pair',
        board_wetness='wet',
        hero_position='ip',
        hero_role='pfr',
        hero_equity=0.58,
        villain_af=2.5,
        spr=5.0,
        pot_bb=25.0,
        num_draws_possible=2,
    )
    print(wbs_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Protection urgency by hand and wetness
PROTECTION_NEED = {
    ('top_pair', 'wet'):     0.85,
    ('top_pair', 'semi_wet'): 0.65,
    ('overpair', 'wet'):     0.90,
    ('overpair', 'semi_wet'): 0.70,
    ('set', 'wet'):          0.50,   # set is strong; less urgent but still protect
    ('set', 'semi_wet'):     0.40,
    ('two_pair', 'wet'):     0.80,
    ('flush_draw', 'wet'):   0.15,   # hero has draw; balance vs protection
    ('air', 'wet'):          0.05,
}

# Recommended c-bet size by wetness
CBET_SIZE_BY_WETNESS = {
    'wet':      0.38,   # small = deny free cards, keep draws in (pay for equity)
    'semi_wet': 0.52,
    'dry':      0.65,
    'monotone': 0.33,   # very small on monotone (villain may have it already)
    'paired':   0.55,
}


def _protection_need(hero_hand_category: str, board_wetness: str) -> float:
    key = (hero_hand_category, board_wetness)
    return PROTECTION_NEED.get(key, 0.30)


def _cbet_size(
    board_wetness: str,
    hero_position: str,
    hero_role: str,
    hero_hand_category: str,
) -> float:
    base = CBET_SIZE_BY_WETNESS.get(board_wetness, 0.50)
    # Strong hands: can size up slightly for value
    if hero_hand_category in ('set', 'overpair', 'two_pair'):
        base += 0.05
    # OOP: slightly smaller (position disadvantage)
    if hero_position in ('oop', 'bb', 'sb'):
        base -= 0.05
    return round(min(0.80, max(0.25, base)), 3)


def _recommended_action(
    hero_hand_category: str,
    board_wetness: str,
    hero_position: str,
    hero_role: str,
    villain_af: float,
    spr: float,
    hero_equity: float,
) -> str:
    protection = _protection_need(hero_hand_category, board_wetness)

    # Strong made hands: must protect on wet boards
    if hero_hand_category in ('overpair', 'top_pair', 'two_pair') and protection >= 0.70:
        return 'bet_for_protection'

    # Sets/boats: bet for value+protection
    if hero_hand_category in ('set', 'full_house') and board_wetness in ('wet', 'semi_wet'):
        return 'bet_value_protection'

    # Flush draw: semi-bluff or check-call depending on position
    if hero_hand_category in ('flush_draw', 'combo_draw'):
        if hero_position == 'ip':
            return 'semi_bluff_or_check'
        elif villain_af >= 2.5:
            return 'check_call'   # OOP vs aggressive; let them bet
        else:
            return 'semi_bluff'

    # Straight draw: similar to flush draw
    if hero_hand_category in ('straight_draw', 'oesd', 'gutshot'):
        if hero_equity >= 0.35:
            return 'semi_bluff'
        else:
            return 'check_evaluate'

    # Air on wet board: check-fold usually
    if hero_hand_category in ('air', 'overcards'):
        return 'check_fold'

    return 'bet_half_pot'


def _bet_frequency(
    hero_hand_category: str,
    board_wetness: str,
    hero_role: str,
    villain_af: float,
) -> float:
    """How often to bet in this spot."""
    if hero_hand_category in ('set', 'full_house', 'two_pair', 'overpair'):
        return 0.85   # almost always bet strong hands
    if hero_hand_category in ('top_pair',):
        base = 0.70 if board_wetness == 'wet' else 0.65
        if hero_role != 'pfr':
            base -= 0.10   # caller bets less
        return base
    if hero_hand_category in ('flush_draw', 'combo_draw'):
        return 0.45   # mix bet and check
    if hero_hand_category == 'air':
        return 0.15   # c-bet bluff freq on wet board
    return 0.50


@dataclass
class WetBoardPlan:
    # Inputs
    hero_hand_category: str
    board_wetness: str
    hero_position: str
    hero_role: str
    hero_equity: float
    villain_af: float
    spr: float
    pot_bb: float
    num_draws_possible: int

    # Analysis
    protection_need: float        # 0-1 urgency of protecting
    recommended_action: str
    cbet_size: float
    bet_frequency: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def plan_wet_board(
    hero_hand_category: str = 'top_pair',
    board_wetness: str = 'wet',
    hero_position: str = 'ip',
    hero_role: str = 'pfr',
    hero_equity: float = 0.58,
    villain_af: float = 2.5,
    spr: float = 5.0,
    pot_bb: float = 25.0,
    num_draws_possible: int = 2,
) -> WetBoardPlan:
    """
    Plan strategy for wet board situations.

    Args:
        hero_hand_category:   Current hand category
        board_wetness:        'wet' / 'semi_wet' / 'monotone'
        hero_position:        'ip' / 'oop'
        hero_role:            'pfr' / 'caller'
        hero_equity:          Current equity
        villain_af:           Villain's AF
        spr:                  Stack-to-pot ratio
        pot_bb:               Current pot
        num_draws_possible:   Number of draw types possible on board

    Returns:
        WetBoardPlan
    """
    prot = _protection_need(hero_hand_category, board_wetness)
    action = _recommended_action(hero_hand_category, board_wetness, hero_position,
                                  hero_role, villain_af, spr, hero_equity)
    size = _cbet_size(board_wetness, hero_position, hero_role, hero_hand_category)
    freq = _bet_frequency(hero_hand_category, board_wetness, hero_role, villain_af)

    verdict = (
        f'[WBS {hero_hand_category}|{board_wetness}|{hero_position}] '
        f'{action.upper()} {size:.0%}pot ({freq:.0%} freq) '
        f'| prot={prot:.2f} draws={num_draws_possible}'
    )

    reasoning = (
        f'Wet board plan: {hero_hand_category} on {board_wetness} board. '
        f'Position={hero_position} ({hero_role}). '
        f'Protection urgency={prot:.2f}. Action={action}. '
        f'Bet size={size:.0%}pot at {freq:.0%} frequency. '
        f'Num draws possible={num_draws_possible}.'
    )

    tips = []

    tips.append(
        f'WET BOARD ACTION: {action.upper()} with {hero_hand_category} on {board_wetness} board. '
        f'Bet {size:.0%} pot ({size*pot_bb:.1f}BB) at {freq:.0%} frequency. '
        f'Protection urgency: {prot:.2f} (higher = must protect more).'
    )

    if prot >= 0.65 and hero_hand_category in ('top_pair', 'overpair', 'two_pair'):
        tips.append(
            f'PROTECTION REQUIRED: {hero_hand_category} on {board_wetness} board needs protection. '
            f'With {num_draws_possible} draw types possible, giving free card is costly. '
            f'Bet {size:.0%} pot to deny villain ~{int(num_draws_possible * 9 * 2)}% equity on free card.'
        )

    if board_wetness == 'wet':
        tips.append(
            f'WET BOARD SIZING: Use SMALL to medium bets on wet boards ({size:.0%} pot). '
            f'Small bets deny free cards while keeping draws in (they pay for equity). '
            f'Large bets fold draws but also fold medium-strength calls (loses action).'
        )

    if hero_hand_category in ('flush_draw', 'combo_draw', 'straight_draw'):
        tips.append(
            f'DRAW STRATEGY ON WET BOARD: '
            f'{"Semi-bluff to build pot and take down when called." if hero_position == "ip" else "Check-call OOP to see cheap cards."} '
            f'Equity={hero_equity:.0%}. With {hero_equity:.0%} equity on wet board, '
            f'you win enough at showdown to justify continuing.'
        )

    if villain_af >= 3.0:
        tips.append(
            f'AGGRESSIVE VILLAIN (AF={villain_af:.1f}) ON WET BOARD: '
            f'Check strong hands to trap. '
            f'Villain will bet their draws aggressively -- your made hands become traps. '
            f'Check-raise or check-call with made hands; check-fold air.'
        )

    if spr <= 2.5:
        tips.append(
            f'LOW SPR ({spr:.1f}): Commit or fold on wet boards. '
            f'With SPR < 2.5 and {hero_hand_category}, stack-off is correct. '
            f'Don\'t slow-play -- get it in while you\'re ahead.'
        )

    return WetBoardPlan(
        hero_hand_category=hero_hand_category,
        board_wetness=board_wetness,
        hero_position=hero_position,
        hero_role=hero_role,
        hero_equity=hero_equity,
        villain_af=villain_af,
        spr=spr,
        pot_bb=pot_bb,
        num_draws_possible=num_draws_possible,
        protection_need=prot,
        recommended_action=action,
        cbet_size=size,
        bet_frequency=freq,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def wbs_one_liner(r: WetBoardPlan) -> str:
    return (
        f'[WBS {r.hero_hand_category}|{r.board_wetness}|{r.hero_position}] '
        f'{r.recommended_action.upper()} {r.cbet_size:.0%}pot '
        f'| freq={r.bet_frequency:.0%} prot={r.protection_need:.2f}'
    )
