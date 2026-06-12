"""
River Value Bet Sizing Guide (river_value_bet_sizing_guide.py)

Calibrates river value bet sizing based on hand strength, villain calling
frequency, and board texture to extract maximum EV from value hands.

THEORY:
  RIVER VALUE BET OPTIMIZATION:
  Goal: maximize EV = (call_freq * bet) - (fold_freq * 0)
  Simplified: larger bets are better IF villain call_freq stays profitable.

  VILLAIN CALL FREQUENCY ON RIVER:
  Fish/calling_station: calls 70-85% of river bets (call almost any size)
  Reg: calls ~52-62% (near MDF; calibrated)
  Nit: calls ~30-45% (folds wide on river)
  LAG: calls ~55-68% (calls wide but not infinitely)

  OPTIMAL VALUE SIZE FORMULA:
  EV(bet) = call_freq * bet - (1 - call_freq) * 0
  Since EV = call_freq * bet: larger bets = more EV IF villain keeps calling.
  So vs fish: go as large as possible (85-100% pot or more)
  vs nit: smaller (40-55%); nit only calls with top-of-range

  HAND STRENGTH ADJUSTMENTS:
  Nuts: max size (guaranteed winner)
  Strong value: 75-90% pot
  Thin value: 45-65% pot (risk of being called by better hand)
  Very thin: 30-40% pot (want calls from worse hands only)

  BOARD TEXTURE (RIVER):
  Dry river: polarize large (villain range capped; bet big or don't bet)
  Wet river: medium size (villain has more calling hands)
  Paired river: can bet large (villain unlikely to have boat unless specific)

DISTINCT FROM:
  river_value.py:               When river value bet is good
  value_bet_threshold_calculator.py: EV threshold for value bets
  thin_value_vs_calling_station.py:  Thin value specific to calling stations
  THIS MODULE:                  HOW MUCH to size river value bets; villain
                                calling frequency analysis; hand strength mapping.
"""

from dataclasses import dataclass, field
from typing import List

VILLAIN_RIVER_CALL_FREQ: dict = {
    'fish':            0.78,
    'calling_station': 0.85,
    'nit':             0.38,
    'lag':             0.60,
    'rec':             0.58,
    'reg':             0.55,
}

HAND_STRENGTH_VALUE_SIZE: dict = {
    'nuts':         0.95,
    'strong_value': 0.80,
    'two_pair':     0.70,
    'top_pair_gk':  0.65,
    'top_pair_wk':  0.50,
    'middle_pair':  0.38,
    'overpair':     0.75,
    'flush':        0.85,
    'straight':     0.82,
}

BOARD_RIVER_VALUE_MODIFIER: dict = {
    'dry':      +0.10,
    'semi_wet':  0.00,
    'wet':      -0.08,
    'monotone': -0.05,
    'paired':   +0.05,
}

POSITION_RIVER_VALUE_MODIFIER: dict = {
    'ip':  +0.03,
    'oop': -0.04,
}

MIN_VALUE_SIZE: float = 0.28
MAX_VALUE_SIZE: float = 1.20


def _optimal_value_pct(
    hand_strength: str,
    villain_type: str,
    board_texture: str,
    position: str,
) -> float:
    hand_base = HAND_STRENGTH_VALUE_SIZE.get(hand_strength, 0.60)
    call_freq = VILLAIN_RIVER_CALL_FREQ.get(villain_type, 0.55)
    call_boost = (call_freq - 0.55) * 0.80
    board_adj = BOARD_RIVER_VALUE_MODIFIER.get(board_texture, 0.0)
    pos_adj = POSITION_RIVER_VALUE_MODIFIER.get(position, 0.0)
    raw = hand_base + call_boost + board_adj + pos_adj
    return round(min(MAX_VALUE_SIZE, max(MIN_VALUE_SIZE, raw)), 3)


def _value_bet_ev(call_freq: float, pot_bb: float, bet_pct: float) -> float:
    bet_bb = pot_bb * bet_pct
    return round(call_freq * bet_bb, 2)


def _value_size_category(pct: float) -> str:
    if pct >= 0.90:
        return 'OVERBET_VALUE'
    if pct >= 0.70:
        return 'LARGE_VALUE_BET'
    if pct >= 0.50:
        return 'MEDIUM_VALUE_BET'
    if pct >= 0.35:
        return 'SMALL_VALUE_BET'
    return 'THIN_VALUE_BET'


@dataclass
class RiverValueBetSizingResult:
    hand_strength: str
    villain_type: str
    board_texture: str
    position: str
    pot_bb: float

    villain_call_freq: float
    optimal_value_pct: float
    optimal_value_bb: float
    expected_ev_bb: float
    size_category: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_river_value_bet_sizing(
    hand_strength: str = 'top_pair_gk',
    villain_type: str = 'reg',
    board_texture: str = 'semi_wet',
    position: str = 'ip',
    pot_bb: float = 20.0,
) -> RiverValueBetSizingResult:
    """
    Calibrate river value bet size.

    Args:
        hand_strength: Hand strength category ('nuts','strong_value','two_pair',
                       'top_pair_gk','top_pair_wk','middle_pair','overpair','flush','straight')
        villain_type:  Villain type ('fish','nit','lag','reg','calling_station')
        board_texture: River board texture ('dry','semi_wet','wet','monotone','paired')
        position:      Hero position ('ip' or 'oop')
        pot_bb:        Pot size in BB before river bet

    Returns:
        RiverValueBetSizingResult
    """
    call_freq = VILLAIN_RIVER_CALL_FREQ.get(villain_type, 0.55)
    opt_pct = _optimal_value_pct(hand_strength, villain_type, board_texture, position)
    opt_bb = round(pot_bb * opt_pct, 1)
    ev = _value_bet_ev(call_freq, pot_bb, opt_pct)
    cat = _value_size_category(opt_pct)

    verdict = (
        f'[RVS {hand_strength}|{villain_type}|{board_texture}] '
        f'size={opt_pct:.0%}pot={opt_bb:.1f}BB EV={ev:.1f}BB {cat}'
    )

    reasoning = (
        f'River value sizing: {hand_strength} vs {villain_type} ({board_texture}). '
        f'hand_base={HAND_STRENGTH_VALUE_SIZE.get(hand_strength, 0.60):.0%} '
        f'call_freq={call_freq:.0%}(boost={((call_freq-0.55)*0.80):+.0%}) '
        f'board_adj={BOARD_RIVER_VALUE_MODIFIER.get(board_texture, 0):+.0%} '
        f'pos_adj={POSITION_RIVER_VALUE_MODIFIER.get(position, 0):+.0%}. '
        f'Optimal={opt_pct:.0%}pot={opt_bb:.1f}BB. EV={ev:.1f}BB.'
    )

    tips = []

    tips.append(
        f'River value bet: {hand_strength} vs {villain_type}: {opt_pct:.0%} pot = {opt_bb:.1f}BB. '
        f'Villain calls ~{call_freq:.0%} of river bets. EV={ev:.1f}BB. '
        f'{cat}.'
    )

    if villain_type in ('fish', 'calling_station'):
        tips.append(
            f'vs {villain_type.upper()}: MAX VALUE SIZE. '
            f'{villain_type} calls {call_freq:.0%} of bets -- go {opt_pct:.0%} pot. '
            f'Never go smaller than {opt_pct:.0%} with {hand_strength} vs {villain_type}. '
            f'These players call with second pair, any pair, any draw -- extract everything.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'vs NIT: Smaller value bet {opt_pct:.0%} pot. '
            f'Nit calls only {call_freq:.0%}; large bets get folded. '
            f'Medium value bet extracts more total EV than large bet vs nit. '
            f'Nit range when calling: top pair+, draws; {hand_strength} is profitable.'
        )
    else:
        tips.append(
            f'vs {villain_type}: {opt_pct:.0%} pot balanced value bet. '
            f'Villain calls {call_freq:.0%}: {cat} achieves max EV. '
            f'{"Dry board: polarize -- larger works" if board_texture == "dry" else "Wet board: size down slightly -- villain has more calling hands"}.'
        )

    return RiverValueBetSizingResult(
        hand_strength=hand_strength,
        villain_type=villain_type,
        board_texture=board_texture,
        position=position,
        pot_bb=pot_bb,
        villain_call_freq=call_freq,
        optimal_value_pct=opt_pct,
        optimal_value_bb=opt_bb,
        expected_ev_bb=ev,
        size_category=cat,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rvs_one_liner(r: RiverValueBetSizingResult) -> str:
    return (
        f'[RVS {r.hand_strength}|{r.villain_type}] '
        f'{r.optimal_value_pct:.0%}pot={r.optimal_value_bb:.1f}BB EV={r.expected_ev_bb:.1f}BB'
    )
