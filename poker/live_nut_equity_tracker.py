"""
Live Nut Equity Tracker (live_nut_equity_tracker.py)

Tracks which player has the "nut advantage" on a given board -- meaning
who can have the strongest possible hands (nuts) and what that means for
betting frequency, sizing, and aggression.

NUT ADVANTAGE CONCEPT:
  The player whose range contains more "nut hands" (strongest combinations
  possible on this board) has the nut advantage. This player can:
  1. Bet larger sizes (threats are more credible)
  2. Bet more frequently (range is less capped)
  3. Demand more respect from villain (villain's folds are correct)

  EXAMPLE:
    UTG opens, BB defends. Flop: A-A-K rainbow.
    UTG's range: AA, KK, AK → more nut hands (AA, AK)
    BB's range: rarely has AA, AK (squeezed preflop) → more capped
    UTG has nut advantage on A-A-K board.

NUT HANDS BY BOARD:
  High card board (A-K-9):  AA, KK, AK in PFR range; BB has 2-pair draws
  Low connected (7-8-9):    Straights, sets in caller range; PFR has overcards
  Paired high (A-A-K):      AA, AK in PFR range; vast nut advantage
  Monotone flop:            Flushes in both ranges; slight edge to PFR's suited hands

NUT ADVANTAGE USES:
  - Who should bet large? → Player with nut advantage
  - Who should check-call? → Player with nut disadvantage (capped range)
  - Overbet spots?        → When nut advantage is extreme

DISTINCT FROM:
  nut_advantage_analyzer.py: If it exists, this module may overlap.
  range_disadvantage_response.py: RDR is about range disadvantage overall;
                              this module specifically tracks NUT equity.
  THIS MODULE:              Street-by-street nut equity tracking with
                            adjustments for how cards hit each range's nuts.

Usage:
    from poker.live_nut_equity_tracker import track_nut_equity, NutEquityResult, nte_one_liner

    result = track_nut_equity(
        hero_position='utg',
        villain_position='btn',
        board_type='high_paired',
        street='flop',
        hero_hand_category='top_pair',
        villain_vpip=0.35,
        pot_bb=25.0,
    )
    print(nte_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Nut advantage for the PFR (opener) by board type
# How much of the nut range does PFR have vs caller?
# 0.5 = neutral; >0.5 = PFR has advantage; <0.5 = caller has advantage
PFR_NUT_ADVANTAGE = {
    'high_paired':      0.75,  # A-A-K; PFR has AA/AK
    'high_card':        0.65,  # A-K-9; PFR has AK, KK
    'broadway':         0.70,  # A-K-Q; PFR's tight range has tons of broadway
    'medium_dry':       0.55,  # T-7-2; PFR has some advantage
    'low_connected':    0.35,  # 7-8-9; caller has suited connectors
    'low_paired':       0.45,  # 6-6-2; caller has more small pairs
    'monotone':         0.52,  # flush board; slight edge to PFR's suited hands
    'medium_connected': 0.45,  # 8-9-T; caller's connectors connect well
    'rainbow_dry':      0.60,  # A-7-2r; PFR has AA/A7s
    'paired_medium':    0.50,  # Q-Q-5; neutral (both can have QQ)
}


def _nut_advantage_score(
    hero_position: str,
    villain_position: str,
    board_type: str,
    hero_hand_category: str,
) -> tuple:
    """
    (hero_nut_score: float, villain_nut_score: float)
    Scores 0-1 each; higher = more nut combos in that range.
    """
    # Determine if hero is PFR or caller based on position
    # UTG/MP/CO/BTN openers are typically PFR; BB/SB are callers
    pfr_positions = ('utg', 'utg1', 'mp', 'lj', 'hj', 'co', 'btn')
    hero_is_pfr = hero_position.lower() in pfr_positions and villain_position.lower() in ('bb', 'sb')

    pfr_score = PFR_NUT_ADVANTAGE.get(board_type, 0.50)
    caller_score = 1.0 - pfr_score

    if hero_is_pfr:
        hero_score = pfr_score
        villain_score = caller_score
    else:
        hero_score = caller_score
        villain_score = pfr_score

    # Adjust for hero's actual hand
    if hero_hand_category in ('set', 'straight', 'flush', 'full_house', 'quads'):
        hero_score = max(hero_score, 0.80)
    elif hero_hand_category in ('two_pair', 'overpair'):
        hero_score = max(hero_score, 0.65)
    elif hero_hand_category in ('air', 'overcards', 'weak_pair'):
        hero_score = min(hero_score, 0.40)

    villain_score = 1.0 - hero_score

    return round(hero_score, 3), round(villain_score, 3)


def _nut_advantage_level(score: float) -> str:
    if score >= 0.70:
        return 'dominant'
    elif score >= 0.60:
        return 'significant'
    elif score >= 0.55:
        return 'slight'
    else:
        return 'none'


def _recommended_bet_sizing(
    hero_nut_score: float,
    board_type: str,
    street: str,
) -> float:
    """
    Recommended bet sizing as fraction of pot based on nut advantage.
    More nut advantage → bet larger.
    """
    base = 0.50
    if hero_nut_score >= 0.70:
        base = 0.75
    elif hero_nut_score >= 0.60:
        base = 0.65
    elif hero_nut_score >= 0.55:
        base = 0.55
    elif hero_nut_score <= 0.40:
        base = 0.33   # capped range → bet smaller

    # Street adjustment
    if street == 'river':
        base *= 1.15   # river → polarize and bet bigger
    elif street == 'flop':
        base *= 0.90   # flop → bet smaller (more streets ahead)

    return round(min(1.50, max(0.25, base)), 2)


def _recommended_action(
    hero_nut_score: float,
    hero_hand_category: str,
    board_type: str,
    street: str,
    villain_af: float = 2.0,
) -> tuple:
    """(action: str, explanation: str)"""
    nut_level = _nut_advantage_level(hero_nut_score)

    if hero_hand_category in ('set', 'straight', 'flush', 'full_house', 'two_pair'):
        if nut_level in ('dominant', 'significant'):
            return (
                'bet_large',
                f'Nut hand ({hero_hand_category}) + nut advantage ({nut_level}): '
                f'bet large. Villain cannot credibly fight back; your range is uncapped.'
            )
        else:
            return (
                'bet_value',
                f'Nut hand ({hero_hand_category}) but nut disadvantage: '
                f'bet for value at medium size. Villain may also have strong hands.'
            )

    if hero_hand_category in ('overpair', 'top_pair'):
        if nut_level == 'none':
            return (
                'check_call',
                f'{hero_hand_category} but NO nut advantage: '
                f'check-call. Range is capped; betting large is non-credible.'
            )
        else:
            return (
                'bet_medium',
                f'{hero_hand_category} with {nut_level} nut advantage: '
                f'bet medium for value. Have some nut hands in range to back it up.'
            )

    if hero_hand_category in ('air', 'overcards', 'bluff'):
        if nut_level in ('dominant', 'significant'):
            return (
                'bluff_large',
                f'Bluff opportunity: {nut_level} nut advantage means your range is credible. '
                f'Large bluff is well-supported by the nut hands in your range.'
            )
        else:
            return (
                'give_up',
                f'Air with no nut advantage: give up. '
                f'Villain will not fold often when your range is capped.'
            )

    return (
        'check_evaluate',
        f'Mixed equity: check and evaluate. Nut advantage={nut_level}.'
    )


@dataclass
class NutEquityResult:
    # Inputs
    hero_position: str
    villain_position: str
    board_type: str
    street: str
    hero_hand_category: str
    villain_vpip: float
    pot_bb: float

    # Analysis
    hero_nut_score: float         # 0-1 (how much nut equity hero has)
    villain_nut_score: float
    hero_nut_advantage: str       # 'dominant' / 'significant' / 'slight' / 'none'
    recommended_bet_size: float   # recommended bet size as fraction of pot

    # Recommendation
    action: str
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def track_nut_equity(
    hero_position: str = 'utg',
    villain_position: str = 'btn',
    board_type: str = 'high_paired',
    street: str = 'flop',
    hero_hand_category: str = 'top_pair',
    villain_vpip: float = 0.35,
    pot_bb: float = 25.0,
    villain_af: float = 2.0,
) -> NutEquityResult:
    """
    Track nut equity advantage and recommend betting strategy.

    Args:
        hero_position:      Hero's position at the table
        villain_position:   Villain's position
        board_type:         'high_paired' / 'high_card' / 'broadway' /
                            'low_connected' / 'medium_dry' / 'rainbow_dry' /
                            'low_paired' / 'monotone' / 'medium_connected'
        street:             'flop' / 'turn' / 'river'
        hero_hand_category: Current hand
        villain_vpip:       Villain VPIP (wider range = more nut hands on connected boards)
        pot_bb:             Current pot size

    Returns:
        NutEquityResult
    """
    hero_nut, villain_nut = _nut_advantage_score(
        hero_position, villain_position, board_type, hero_hand_category
    )

    nut_level = _nut_advantage_level(hero_nut)
    rec_size = _recommended_bet_sizing(hero_nut, board_type, street)

    action, action_exp = _recommended_action(
        hero_nut, hero_hand_category, board_type, street, villain_af
    )

    reasoning = (
        f'Nut equity: hero={hero_nut:.2f} vs villain={villain_nut:.2f} '
        f'({hero_position} vs {villain_position} on {board_type} {street}). '
        f'Nut advantage={nut_level}. Rec bet size={rec_size:.0%} pot. '
        f'Hero hand={hero_hand_category}. Action={action}.'
    )

    verdict = (
        f'[NTE {nut_level.upper()}|{board_type}|{street}] '
        f'hero_nut={hero_nut:.2f} villain_nut={villain_nut:.2f} | '
        f'rec_bet={rec_size:.0%}pot {action.upper()}'
    )

    tips = [action_exp]

    tips.append(
        f'NUT ADVANTAGE SUMMARY ({nut_level.upper()}): '
        f'Hero nut score={hero_nut:.2f} vs villain={villain_nut:.2f} on {board_type.replace("_"," ")} {street}. '
        f'Recommended bet sizing: {rec_size:.0%} pot. '
        f'Player with nut advantage should bet larger and more frequently.'
    )

    if nut_level in ('dominant', 'significant'):
        tips.append(
            f'LEVERAGE NUT ADVANTAGE: You can credibly represent the strongest hands. '
            f'Use larger bet sizes ({rec_size:.0%}+). '
            f'Villain cannot raise or call light -- your range includes nuts. '
            f'Mix value bets and bluffs with similar sizings for maximum EV.'
        )
    elif nut_level == 'none':
        tips.append(
            f'NUT DISADVANTAGE: Villain can have stronger hands than you on this board. '
            f'Avoid large bets with bluffs -- they are non-credible. '
            f'Bet smaller ({rec_size:.0%}) or check-call. '
            f'Do not try to bluff villain off strong hands when they have nut advantage.'
        )

    if villain_vpip >= 0.40 and board_type in ('low_connected', 'medium_connected'):
        tips.append(
            f'WIDE VILLAIN (VPIP={villain_vpip:.0%}) ON CONNECTED BOARD: '
            f'Villain calling range has more suited connectors/small pairs. '
            f'Their nut count increases significantly on this board type. '
            f'Adjust: hero has less nut advantage than base estimate suggests.'
        )

    return NutEquityResult(
        hero_position=hero_position,
        villain_position=villain_position,
        board_type=board_type,
        street=street,
        hero_hand_category=hero_hand_category,
        villain_vpip=villain_vpip,
        pot_bb=pot_bb,
        hero_nut_score=hero_nut,
        villain_nut_score=villain_nut,
        hero_nut_advantage=nut_level,
        recommended_bet_size=rec_size,
        action=action,
        action_explanation=action_exp,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def nte_one_liner(r: NutEquityResult) -> str:
    return (
        f'[NTE {r.hero_nut_advantage.upper()}|{r.board_type}|{r.street}] '
        f'hero={r.hero_nut_score:.2f} villain={r.villain_nut_score:.2f} | '
        f'bet={r.recommended_bet_size:.0%} {r.action.upper()}'
    )
