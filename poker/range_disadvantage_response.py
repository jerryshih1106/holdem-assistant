"""
Range Disadvantage Response (range_disadvantage_response.py)

Advises how to play when hero is at a significant range disadvantage
on a given board texture. Range disadvantage means the board connects
better with villain's range than hero's range.

WHEN HERO IS AT RANGE DISADVANTAGE:
  - Hero opened UTG (tight range), gets called by BTN (wide range)
  - Flop: 7-8-9 rainbow → BTN's 87s, T9s, 65s all connect; UTG has mostly overcards
  - Hero is at a RANGE DISADVANTAGE: villain has more nutted/strong hands

  Similarly:
  - Hero 3-bets CO, BTN calls
  - Flop: 5-5-2 → BTN's 55, 52s in range; CO 3-bet range has few 5x hands

STRATEGY WHEN AT RANGE DISADVANTAGE:
  1. REDUCE C-BET FREQUENCY: Don't bet just because you're the PFR
  2. CHECK MORE OFTEN: Check-call with strong hands (protect checking range)
  3. BET SMALLER: If betting, use smaller sizes (less committed on bad board)
  4. CHECK-RAISE MORE: Check-raise with nutted hands to balance checking range
  5. ACCEPT MORE CHECK-BACKS: IP players should check back frequently

RANGE DISADVANTAGE INDICATORS:
  - Hero's range has few connected hands for this board
  - Villain's calling range has more suited connectors/small pairs
  - Board is low and connected vs hero's high-card opening range
  - Board is paired vs hero's preflop aggressor range

DISTINCT FROM:
  range_board_coverage.py:     Analyzes range coverage percentage
  nut_advantage_analyzer.py:   Identifies who has nut advantage
  THIS MODULE:                 Actionable response strategy when hero is
                               identified as being at range disadvantage;
                               provides complete multi-spot adjustments

Usage:
    from poker.range_disadvantage_response import respond_to_range_disadvantage, RangeDisadvantageResponse, rdr_one_liner

    result = respond_to_range_disadvantage(
        hero_role='pfr',
        hero_opening_position='utg',
        villain_position='btn',
        board_type='low_connected',
        street='flop',
        hero_hand_category='overcards',
        hero_equity=0.30,
        pot_bb=12.0,
        hero_stack_bb=90.0,
        villain_vpip=0.35,
        villain_af=2.2,
    )
    print(rdr_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Range disadvantage severity by opening position + board type
# Higher = more disadvantaged
RANGE_DISADVANTAGE = {
    ('utg', 'low_connected'):     0.70,
    ('utg', 'low_dry'):           0.35,
    ('utg', 'medium_connected'):  0.50,
    ('utg', 'high_connected'):    0.20,
    ('utg', 'paired_low'):        0.55,
    ('mp',  'low_connected'):     0.58,
    ('mp',  'medium_connected'):  0.40,
    ('co',  'low_connected'):     0.45,
    ('btn', 'low_connected'):     0.25,   # BTN range wide; has connectors too
    ('btn', 'high_connected'):    0.30,
    ('sb',  'low_connected'):     0.60,
    ('bb',  'low_connected'):     0.30,   # BB defends wide; has connectors
}


def _get_range_disadvantage(hero_opening_position: str, board_type: str) -> float:
    """Returns disadvantage score 0-1. Higher = hero more disadvantaged."""
    key = (hero_opening_position.lower(), board_type.lower())
    if key in RANGE_DISADVANTAGE:
        return RANGE_DISADVANTAGE[key]
    # Fallback: UTG-like tight positions are most disadvantaged on connected boards
    pos_tier = {'utg': 0.65, 'utg1': 0.60, 'mp': 0.50, 'lj': 0.45,
                'hj': 0.40, 'co': 0.35, 'btn': 0.25, 'sb': 0.55, 'bb': 0.30}
    board_mult = {'low_connected': 1.2, 'medium_connected': 1.0,
                  'high_connected': 0.7, 'low_dry': 0.6, 'paired_low': 1.0,
                  'monotone': 0.8}.get(board_type, 1.0)
    base = pos_tier.get(hero_opening_position.lower(), 0.45)
    return round(min(0.90, base * board_mult), 3)


def _disadvantage_level(score: float) -> str:
    if score >= 0.65:
        return 'severe'
    elif score >= 0.45:
        return 'moderate'
    elif score >= 0.25:
        return 'mild'
    else:
        return 'minimal'


def _adjusted_cbet_frequency(
    base_cbet: float,
    disadvantage_score: float,
    board_type: str,
    hero_hand_category: str,
) -> float:
    """Adjusted c-bet frequency accounting for range disadvantage."""
    reduction = disadvantage_score * 0.40   # up to 40% reduction
    adj = max(0.15, base_cbet - reduction)

    # Strong hands: still bet despite disadvantage
    if hero_hand_category in ('set', 'two_pair', 'straight', 'flush', 'full_house'):
        adj = max(adj, 0.75)   # always bet strong hands
    elif hero_hand_category in ('overpair', 'top_pair'):
        adj = max(adj, 0.45)   # usually bet top pair even with disadvantage
    elif hero_hand_category in ('air', 'overcards', 'weak_pair'):
        adj = min(adj, 0.30)   # drastically cut bluffs

    return round(adj, 3)


def _check_raise_frequency(disadvantage_score: float, board_type: str) -> float:
    """Higher disadvantage → check-raise MORE with strong hands to balance."""
    base = 0.10
    # When disadvantaged, we check more → need more check-raises for balance
    adj = base + disadvantage_score * 0.12
    return round(min(0.30, adj), 3)


def _recommended_action(
    hero_hand_category: str,
    hero_equity: float,
    disadvantage_score: float,
    hero_role: str,
    street: str,
    villain_af: float,
) -> tuple:
    """(action: str, explanation: str)"""
    if hero_hand_category in ('set', 'two_pair', 'straight', 'flush', 'full_house', 'trips'):
        if villain_af >= 2.5:
            return 'check_raise', 'Strong hand + disadvantaged range: check-raise to balance checking range and extract value.'
        else:
            return 'bet_value', 'Strong hand: bet despite range disadvantage; protect equity.'

    if hero_hand_category in ('overpair', 'top_pair'):
        if disadvantage_score >= 0.60:
            return 'check_call', 'Top pair on disadvantaged board: check-call to avoid building big pot; protect against villain\'s nutted hands.'
        else:
            return 'bet_small', 'Top pair: bet small for value; sizing down acknowledges range weakness.'

    if hero_hand_category in ('flush_draw', 'straight_draw', 'draw', 'combo_draw'):
        if hero_equity >= 0.35:
            return 'bet_semi_bluff', 'Draw with equity: semi-bluff at reduced frequency; villain may have stronger made hands.'
        else:
            return 'check_evaluate', 'Weak draw: check and evaluate; too much risk semi-bluffing when villain has connected better.'

    # Air/overcards
    if hero_equity <= 0.25 and disadvantage_score >= 0.50:
        return 'check_fold', 'Air on disadvantaged board: check-fold; do not bluff into villain\'s strong range.'
    else:
        return 'check_evaluate', 'Marginal hand: check; only continue if pot odds justify or hand improves.'


@dataclass
class RangeDisadvantageResponse:
    # Inputs
    hero_role: str
    hero_opening_position: str
    villain_position: str
    board_type: str
    street: str
    hero_hand_category: str
    hero_equity: float
    pot_bb: float
    hero_stack_bb: float
    villain_vpip: float
    villain_af: float

    # Analysis
    disadvantage_score: float     # 0-1 (severity)
    disadvantage_level: str       # 'severe' / 'moderate' / 'mild' / 'minimal'
    adjusted_cbet_freq: float     # recommended c-bet frequency
    check_raise_freq: float       # recommended check-raise frequency

    # Recommendation
    action: str
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def respond_to_range_disadvantage(
    hero_role: str = 'pfr',
    hero_opening_position: str = 'utg',
    villain_position: str = 'btn',
    board_type: str = 'low_connected',
    street: str = 'flop',
    hero_hand_category: str = 'overcards',
    hero_equity: float = 0.30,
    pot_bb: float = 12.0,
    hero_stack_bb: float = 90.0,
    villain_vpip: float = 0.35,
    villain_af: float = 2.2,
) -> RangeDisadvantageResponse:
    """
    Respond strategically when hero is at a range disadvantage.

    Args:
        hero_role:              'pfr' / 'caller'
        hero_opening_position:  Position hero opened from ('utg'/'mp'/'co'/'btn'/'sb'/'bb')
        villain_position:       Villain's position
        board_type:             'low_connected' / 'medium_connected' / 'high_connected' /
                                'low_dry' / 'paired_low' / 'monotone'
        street:                 'flop' / 'turn' / 'river'
        hero_hand_category:     Current hand category
        hero_equity:            Hero's equity vs villain's range
        pot_bb:                 Current pot
        hero_stack_bb:          Effective stack
        villain_vpip/af:        HUD stats

    Returns:
        RangeDisadvantageResponse
    """
    d_score = _get_range_disadvantage(hero_opening_position, board_type)
    d_level = _disadvantage_level(d_score)

    base_cbet = 0.58   # standard flop cbet starting point
    adj_cbet = _adjusted_cbet_frequency(base_cbet, d_score, board_type, hero_hand_category)
    cr_freq = _check_raise_frequency(d_score, board_type)

    action, action_exp = _recommended_action(
        hero_hand_category, hero_equity, d_score, hero_role, street, villain_af
    )

    reasoning = (
        f'Range disadvantage: {hero_opening_position} PFR on {board_type} vs {villain_position}. '
        f'Disadvantage score={d_score:.2f} ({d_level}). '
        f'Adjusted cbet={adj_cbet:.0%} (base={base_cbet:.0%}). '
        f'Check-raise freq={cr_freq:.0%}. '
        f'Hero hand={hero_hand_category} equity={hero_equity:.0%}. '
        f'Action={action}.'
    )

    verdict = (
        f'[RDR {d_level.upper()}|{board_type}|{hero_opening_position}] '
        f'{action.upper()} | '
        f'disadvantage={d_score:.2f} cbet={adj_cbet:.0%} cr={cr_freq:.0%}'
    )

    tips = [action_exp]

    tips.append(
        f'RANGE DISADVANTAGE SUMMARY ({d_level.upper()}): '
        f'{hero_opening_position.upper()} opening range has {d_score:.0%} disadvantage on {board_type.replace("_"," ")} board. '
        f'Recommended c-bet frequency reduced to {adj_cbet:.0%} (vs normal ~{base_cbet:.0%}). '
        f'Check-raise frequency increased to {cr_freq:.0%} to balance.'
    )

    if d_level in ('severe', 'moderate'):
        tips.append(
            f'STRATEGY SHIFT REQUIRED: On this board, villain\'s {villain_position.upper()} range '
            f'has more connected/nutted hands. '
            f'Check more frequently with your entire range; only bet strong hands and premium draws. '
            f'Do not c-bet as a default just because you were the PFR.'
        )

    if hero_hand_category in ('overcards', 'air') and d_level in ('severe', 'moderate'):
        tips.append(
            f'GIVE UP WITH AIR: {hero_hand_category} on a {board_type.replace("_"," ")} board '
            f'where villain connected better -- do not bluff. '
            f'Save bluffs for boards where you have range advantage.'
        )

    if villain_af >= 3.0:
        tips.append(
            f'AGGRESSIVE VILLAIN (AF={villain_af:.1f}): Expect villain to exploit your weak range '
            f'with increased c-bets and check-raises. '
            f'Check-raise or call-down with stronger hands; be prepared to fold marginal hands to aggression.'
        )

    return RangeDisadvantageResponse(
        hero_role=hero_role,
        hero_opening_position=hero_opening_position,
        villain_position=villain_position,
        board_type=board_type,
        street=street,
        hero_hand_category=hero_hand_category,
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        hero_stack_bb=hero_stack_bb,
        villain_vpip=villain_vpip,
        villain_af=villain_af,
        disadvantage_score=d_score,
        disadvantage_level=d_level,
        adjusted_cbet_freq=adj_cbet,
        check_raise_freq=cr_freq,
        action=action,
        action_explanation=action_exp,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rdr_one_liner(r: RangeDisadvantageResponse) -> str:
    return (
        f'[RDR {r.disadvantage_level.upper()}|{r.board_type}|{r.hero_opening_position}] '
        f'{r.action.upper()} | '
        f'd={r.disadvantage_score:.2f} cbet={r.adjusted_cbet_freq:.0%} cr={r.check_raise_freq:.0%}'
    )
