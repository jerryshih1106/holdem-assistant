"""
Facing Check-Raise Response (facing_check_raise_response.py)

Analyzes how to respond when villain check-raises your bet.
A check-raise is a very strong signal in poker and requires careful response:
  1. FOLD: Most hands; respect the signal
  2. CALL: Strong draws, nut draws; realize equity
  3. RERAISE (4-bet): Premium value; trapped/polar range

CHECK-RAISE RESPONSE THEORY:
  When villain check-raises, they are representing a STRONG range.
  The distribution is heavily weighted toward:
  - Sets (slowplayed on the flop; check-raise to build pot)
  - Two-pair (check-raise to define hand and build pot)
  - Flush draws (semi-bluff check-raise; especially by aggressive villains)
  - Straight draws (combo draws with check-raise)

  CHECK-RAISE FREQUENCIES by villain type:
  Passive (AF < 1.5): Almost always strong (sets, two-pair)
  Balanced (AF 1.5-3): Mix of strong value and semi-bluffs
  Aggressive (AF > 3): Wider range including bluffs

  RESPONSE DECISION TREE:
  1. Strong value (sets, overpairs): RERAISE for value or call and let them barrel
  2. Top pair: FOLD (usually; check-raise > top pair)
  3. Strong draw (9 outs+): CALL or RERAISE as semi-bluff
  4. Weak draw (< 6 outs): FOLD (odds too poor)
  5. Air: FOLD immediately

  SIZING RESPONSE:
  If calling check-raise: usually commit to calling turn and river
  If reraising: raise to 2.5-3x the check-raise size
  If folding: fold all marginal top pairs and weaker

  EQUITY NEEDED TO CALL CHECK-RAISE:
  Standard: need ~33% equity vs villain's check-raise range to call
  (based on pot odds after check-raise)
  - Flush draw: 35% equity → can call
  - OESD: 32% equity → borderline call
  - Top pair: 40% equity → may call vs balanced villain

DISTINCT FROM:
  check_raise.py:         Hero check-raising (offensive)
  checkraise_advisor.py:  When to check-raise
  facing_aggression.py:   General facing aggression
  THIS MODULE:            RESPONDING to check-raise against you;
                          fold vs call vs reraise thresholds;
                          villain type adjustments.

Usage:
    from poker.facing_check_raise_response import respond_to_check_raise, CheckRaiseResponse, fcrr_one_liner

    result = respond_to_check_raise(
        hero_hand_category='top_pair',
        villain_check_raise_size_bb=18.0,
        pot_before_hero_bet=15.0,
        hero_bet_bb=9.0,
        villain_af=1.8,
        street='flop',
        board_texture='wet',
        hero_equity=0.55,
        hero_position='ip',
    )
    print(fcrr_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Equity thresholds for responding to check-raise
FOLD_EQUITY_THRESHOLD = 0.33   # below this: fold
CALL_EQUITY_THRESHOLD = 0.33   # above this: can call
RERAISE_EQUITY_THRESHOLD = 0.65  # above this: consider reraise

# Hand ranking for check-raise response
HAND_RANK = {
    'nuts': 13, 'near_nuts': 12, 'full_house': 11,
    'flush': 10, 'straight': 9, 'set': 8,
    'two_pair': 7, 'overpair': 6, 'strong_top_pair': 5,
    'top_pair': 4, 'combo_draw': 4, 'flush_draw': 3,
    'oesd': 3, 'middle_pair': 2, 'gutshot': 2,
    'bottom_pair': 1, 'air': 0,
}

# Minimum hand rank to call a check-raise (by villain type)
CALL_FLOOR_BY_VILLAIN = {
    'passive':   5,   # need strong_top_pair or better vs passive check-raise
    'balanced':  3,   # flush draw and above ok to call
    'aggressive': 2,  # oesd+ ok to call; even some gutshots
}

# Reraise hands (relative nuts)
RERAISE_HANDS = {'nuts', 'near_nuts', 'set', 'full_house', 'flush', 'straight'}


def _villain_type(villain_af: float) -> str:
    if villain_af < 1.5:
        return 'passive'
    elif villain_af < 3.0:
        return 'balanced'
    else:
        return 'aggressive'


def _pot_odds(pot_total: float, call_amount: float) -> float:
    """Pot odds as a fraction required equity."""
    return call_amount / (pot_total + call_amount)


def _implied_pot_odds(
    pot_total: float,
    call_amount: float,
    remaining_stack: float,
) -> float:
    """Pot odds with implied odds from future streets."""
    total_winnable = pot_total + call_amount + remaining_stack * 0.5
    return call_amount / total_winnable


def _check_raise_response(
    hand_category: str,
    villain_af: float,
    hero_equity: float,
    pot_odds_required: float,
) -> str:
    vtype = _villain_type(villain_af)
    call_floor = CALL_FLOOR_BY_VILLAIN[vtype]
    hand_rank = HAND_RANK.get(hand_category, 0)

    if hand_category in RERAISE_HANDS and hero_equity >= RERAISE_EQUITY_THRESHOLD:
        return 'reraise'

    if hand_rank >= call_floor and hero_equity >= pot_odds_required:
        return 'call'

    return 'fold'


def _reraise_size(check_raise_size_bb: float) -> float:
    return round(check_raise_size_bb * 2.8, 1)


def _equity_vs_check_raise_range(
    hand_category: str,
    villain_af: float,
) -> float:
    """Rough equity estimate vs villain's check-raise range."""
    vtype = _villain_type(villain_af)
    base_equity = {
        'nuts': 0.95, 'near_nuts': 0.90, 'set': 0.75, 'two_pair': 0.62,
        'overpair': 0.50, 'strong_top_pair': 0.45, 'top_pair': 0.40,
        'flush_draw': 0.35, 'combo_draw': 0.50, 'oesd': 0.32,
        'middle_pair': 0.25, 'gutshot': 0.22, 'air': 0.05,
    }.get(hand_category, 0.30)

    if vtype == 'aggressive':
        base_equity += 0.08   # wider bluff range = hero does better
    elif vtype == 'passive':
        base_equity -= 0.08   # value heavy = hero does worse

    return round(min(0.95, max(0.05, base_equity)), 2)


@dataclass
class CheckRaiseResponse:
    # Inputs
    hero_hand_category: str
    villain_check_raise_size_bb: float
    pot_before_hero_bet: float
    hero_bet_bb: float
    villain_af: float
    street: str
    board_texture: str
    hero_equity: float
    hero_position: str

    # Analysis
    villain_type: str
    pot_odds_required: float
    equity_vs_cr_range: float
    response: str             # 'fold' / 'call' / 'reraise'
    reraise_size_bb: float
    call_amount_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def respond_to_check_raise(
    hero_hand_category: str = 'top_pair',
    villain_check_raise_size_bb: float = 18.0,
    pot_before_hero_bet: float = 15.0,
    hero_bet_bb: float = 9.0,
    villain_af: float = 1.8,
    street: str = 'flop',
    board_texture: str = 'wet',
    hero_equity: float = 0.55,
    hero_position: str = 'ip',
) -> CheckRaiseResponse:
    """
    Determine optimal response to a check-raise.

    Args:
        hero_hand_category:         Hero's hand strength
        villain_check_raise_size_bb: Size of villain's check-raise in BB
        pot_before_hero_bet:         Pot size before hero bet (BB)
        hero_bet_bb:                 Hero's bet that got check-raised
        villain_af:                  Villain's aggression factor
        street:                      'flop' / 'turn' / 'river'
        board_texture:               Board texture
        hero_equity:                 Hero's current equity
        hero_position:               'ip' / 'oop'

    Returns:
        CheckRaiseResponse
    """
    vtype = _villain_type(villain_af)
    pot_total = pot_before_hero_bet + hero_bet_bb + villain_check_raise_size_bb
    call_amount = villain_check_raise_size_bb - hero_bet_bb
    pot_odds_req = _pot_odds(pot_total, call_amount)
    eq_vs_cr = _equity_vs_check_raise_range(hero_hand_category, villain_af)
    response = _check_raise_response(hero_hand_category, villain_af, eq_vs_cr, pot_odds_req)
    rr_size = _reraise_size(villain_check_raise_size_bb)

    action_str = {
        'fold': f'FOLD (eq={eq_vs_cr:.0%} < {pot_odds_req:.0%} required)',
        'call': f'CALL {call_amount:.1f}BB',
        'reraise': f'RERAISE to {rr_size:.1f}BB',
    }.get(response, 'FOLD')

    verdict = (
        f'[FCRR {hero_hand_category}|{street}|{vtype}] '
        f'{action_str} | '
        f'pot_odds={pot_odds_req:.0%} eq={eq_vs_cr:.0%}'
    )

    reasoning = (
        f'Check-raise response: {hero_hand_category} on {board_texture} {street}. '
        f'Villain CR size={villain_check_raise_size_bb:.1f}BB (AF={villain_af:.1f} = {vtype}). '
        f'Call amount={call_amount:.1f}BB. Pot={pot_total:.1f}BB. '
        f'Pot odds required={pot_odds_req:.0%}. '
        f'Equity vs CR range={eq_vs_cr:.0%}. '
        f'Response: {response}.'
    )

    tips = []

    tips.append(
        f'CHECK-RAISE SIGNAL: Villain {vtype} (AF={villain_af:.1f}) check-raises. '
        f'{"Passive check-raise = almost always STRONG. Respect it." if vtype == "passive" else ""}'
        f'{"Balanced check-raise = strong value + semi-bluffs. Standard response." if vtype == "balanced" else ""}'
        f'{"Aggressive check-raise = wide range including many bluffs. Call wider." if vtype == "aggressive" else ""}'
        f' Call floor: {CALL_FLOOR_BY_VILLAIN[vtype]}/13 hand rank.'
    )

    tips.append(
        f'POT ODDS: Need {pot_odds_req:.0%} equity to call. '
        f'Your estimated equity vs CR range: {eq_vs_cr:.0%}. '
        f'{"SUFFICIENT: call or reraise." if eq_vs_cr >= pot_odds_req else "INSUFFICIENT: fold."}'
    )

    if response == 'fold':
        tips.append(
            f'FOLD {hero_hand_category}: Check-raise range beats your hand. '
            f'{"Passive villain: check-raise is sets/two-pair. Your " + hero_hand_category + " is beaten." if vtype == "passive" else ""}'
            f'{"You need " + f"{pot_odds_req:.0%}" + " equity but only have " + f"{eq_vs_cr:.0%}" + "."}'
        )
    elif response == 'call':
        tips.append(
            f'CALL PLAN: Call {call_amount:.1f}BB. Pot odds = {pot_odds_req:.0%}, equity = {eq_vs_cr:.0%}. '
            f'Plan: call and re-evaluate on {"turn" if street == "flop" else "river"}. '
            f'Give up if equity falls; continue if you improve or scare card hits.'
        )
    elif response == 'reraise':
        tips.append(
            f'RERAISE to {rr_size:.1f}BB ({villain_check_raise_size_bb:.1f}BB x 2.8). '
            f'Build pot with {hero_hand_category}. '
            f'Villain must commit a large fraction of stack. '
            f'If villain folds: win the pot. If they call: high equity on all runouts.'
        )

    return CheckRaiseResponse(
        hero_hand_category=hero_hand_category,
        villain_check_raise_size_bb=villain_check_raise_size_bb,
        pot_before_hero_bet=pot_before_hero_bet,
        hero_bet_bb=hero_bet_bb,
        villain_af=villain_af,
        street=street,
        board_texture=board_texture,
        hero_equity=hero_equity,
        hero_position=hero_position,
        villain_type=vtype,
        pot_odds_required=pot_odds_req,
        equity_vs_cr_range=eq_vs_cr,
        response=response,
        reraise_size_bb=rr_size,
        call_amount_bb=call_amount,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def fcrr_one_liner(r: CheckRaiseResponse) -> str:
    return (
        f'[FCRR {r.hero_hand_category}|{r.street}|{r.villain_type}] '
        f'{r.response.upper()} eq={r.equity_vs_cr_range:.0%} min={r.pot_odds_required:.0%} | '
        f'call_amt={r.call_amount_bb:.1f}BB'
    )
