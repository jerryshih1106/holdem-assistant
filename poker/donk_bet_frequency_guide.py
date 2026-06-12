"""
Donk Bet Frequency Guide (donk_bet_frequency_guide.py)

Quantifies optimal donk bet frequency by street, board texture, and villain type.
A donk bet is when the OOP player (usually BB) leads into the preflop aggressor
before they can cbet (flop) or after they showed weakness (turn/river).

THEORY:
  DONK BET DEFINITION:
  Flop donk: OOP player leads BEFORE IP player cbets (unconventional but valid)
  Turn donk: OOP player leads AFTER flop went check-check (IP showed weakness)
  River donk: OOP player leads AFTER turn went check-check (IP very weak)

  FLOP DONK FREQUENCIES (BB vs BTN cbet spot):
  Very low in balanced GTO play; mostly exploitative vs specific villains.
  Dry board:       8%  (IP has large range advantage; OOP leads weak hand combos)
  Semi-wet board: 12%  (OOP connects enough to lead range; balance with value)
  Wet/connected:  15%  (OOP connects frequently; lead to protect equity, deny free cards)
  Monotone:       10%  (careful; IP may hold flush draw/blocker advantage)
  Paired board:   10%  (OOP leads with trips/FH slowly; thin leads on pair boards)

  TURN DONK FREQUENCIES (after flop check-check):
  IP showed weakness by checking flop. OOP can now lead wide range.
  Brick turn:         30% (OOP leads medium hands; IP very weak)
  Low connecting:     33% (some draws help OOP range)
  Scare card (A/K):  40% (OOP benefits most; polarized donk range)
  Flush complete:     35% (OOP leads flushes + missed equity)
  Paired:             25% (OOP trips benefit; but be careful of IP boat)

  RIVER DONK FREQUENCIES (after turn check-check):
  Both players showed weakness. OOP leads with value, missed draws, blockers.
  Blank river:        40%
  Draw complete:      45% (lead as value; missed draw bluffs at high freq)
  Scare card:         50% (OOP benefits; polarized lead with strong hands + air)

  VILLAIN ADJUSTMENTS (IP villain type):
  vs nit:            +8%  (nit rarely bets without strong hand; donk exploits passive)
  vs lag:           -10%  (lag raises donks aggressively; donk bluffs lose EV)
  vs fish:           -5%  (fish calls everything; donk bluffs unprofitable)
  vs reg:             0%
  vs calling_station:-8%  (calling station never folds; only donk value hands)

  SIZING:
  Flop donk:  40-52% pot (small-medium; don't over-commit with weak donks)
  Turn donk:  50-65% pot (standard; protect equity or extract value)
  River donk: 55-75% pot (larger; polarized range; value gets called/bluffs need fold)

DISTINCT FROM:
  donk_bet.py:              Core donk bet logic and spot identification
  donk_bet_advisor.py:      Situation-specific donk advice
  donk_bet_range_builder.py:Which hands to include in donk range
  THIS MODULE:              Frequency tables; street calibration; optimal donk %
                            by board texture and villain type; sizing targets.
"""

from dataclasses import dataclass, field
from typing import List

FLOP_DONK_FREQ_BY_TEXTURE: dict = {
    'dry':       0.08,
    'semi_wet':  0.12,
    'wet':       0.15,
    'monotone':  0.10,
    'paired':    0.10,
}

TURN_DONK_FREQ_BY_TURN_CARD: dict = {
    'brick':          0.30,
    'low_connecting': 0.33,
    'ace_king':       0.40,
    'flush_complete': 0.35,
    'paired':         0.25,
}

RIVER_DONK_FREQ_BY_RUNOUT: dict = {
    'blank':          0.40,
    'draw_complete':  0.45,
    'scare_card':     0.50,
}

VILLAIN_DONK_MODIFIER: dict = {
    'nit':             +0.08,
    'fish':            -0.05,
    'lag':             -0.10,
    'reg':              0.00,
    'calling_station': -0.08,
}

DONK_SIZE_BY_STREET: dict = {
    'flop':  0.46,
    'turn':  0.58,
    'river': 0.65,
}

BOARD_DONK_SIZE_MODIFIER: dict = {
    'dry':      -0.06,
    'semi_wet':  0.00,
    'wet':      +0.08,
    'monotone': +0.04,
    'paired':   -0.03,
}

STREET_OPTIONS = {'flop', 'turn', 'river'}


def _base_donk_freq(street: str, board_texture: str) -> float:
    if street == 'flop':
        return FLOP_DONK_FREQ_BY_TEXTURE.get(board_texture, 0.10)
    elif street == 'turn':
        return TURN_DONK_FREQ_BY_TURN_CARD.get(board_texture, 0.30)
    else:
        return RIVER_DONK_FREQ_BY_RUNOUT.get(board_texture, 0.40)


def _optimal_donk_freq(street: str, board_texture: str, villain_type: str) -> float:
    base = _base_donk_freq(street, board_texture)
    villain_adj = VILLAIN_DONK_MODIFIER.get(villain_type, 0.0)
    return round(max(0.0, min(0.65, base + villain_adj)), 4)


def _donk_size_pct(street: str, board_texture: str) -> float:
    base = DONK_SIZE_BY_STREET.get(street, 0.55)
    adj = BOARD_DONK_SIZE_MODIFIER.get(board_texture, 0.0)
    return round(min(0.85, max(0.30, base + adj)), 3)


def _donk_size_bb(pot_bb: float, street: str, board_texture: str) -> float:
    return round(pot_bb * _donk_size_pct(street, board_texture), 1)


def _donk_decision(freq: float) -> str:
    if freq >= 0.40:
        return 'HIGH_FREQ_DONK'
    if freq >= 0.25:
        return 'MODERATE_DONK'
    if freq >= 0.12:
        return 'SELECTIVE_DONK'
    if freq >= 0.05:
        return 'RARE_EXPLOITATIVE_DONK'
    return 'AVOID_DONK'


@dataclass
class DonkBetFrequencyResult:
    street: str
    board_texture: str
    villain_type: str
    pot_bb: float

    base_donk_freq: float
    optimal_donk_freq: float
    donk_size_pct: float
    donk_size_bb: float
    donk_decision: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_donk_bet_frequency(
    street: str = 'turn',
    board_texture: str = 'brick',
    villain_type: str = 'reg',
    pot_bb: float = 8.0,
) -> DonkBetFrequencyResult:
    """
    Calculate optimal donk bet frequency by street and board texture.

    Args:
        street:        'flop', 'turn', or 'river'
        board_texture: Flop: 'dry','semi_wet','wet','monotone','paired'
                       Turn: 'brick','low_connecting','ace_king','flush_complete','paired'
                       River: 'blank','draw_complete','scare_card'
        villain_type:  IP villain type ('nit','fish','lag','reg','calling_station')
        pot_bb:        Pot size in BB before donk

    Returns:
        DonkBetFrequencyResult
    """
    base = _base_donk_freq(street, board_texture)
    freq = _optimal_donk_freq(street, board_texture, villain_type)
    size_pct = _donk_size_pct(street, board_texture)
    size_bb = _donk_size_bb(pot_bb, street, board_texture)
    decision = _donk_decision(freq)

    verdict = (
        f'[DONK {street}|{board_texture}|{villain_type}] '
        f'freq={freq:.0%} size={size_pct:.0%}pot={size_bb:.1f}BB dec={decision}'
    )

    reasoning = (
        f'Donk bet on {street} ({board_texture}): '
        f'base_freq={base:.0%} '
        f'villain_adj={VILLAIN_DONK_MODIFIER.get(villain_type, 0):+.0%} '
        f'final_freq={freq:.0%}. '
        f'Sizing: {size_pct:.0%}pot={size_bb:.1f}BB. '
        f'Decision={decision}. '
        f'{"Flop donk is exploitative vs specific villain types" if street == "flop" else "Turn donk exploits IP weakness shown by flop check-through" if street == "turn" else "River donk: both showed weakness; lead polarized range"}.'
    )

    tips = []

    tips.append(
        f'{street.upper()} DONK: {freq:.0%} frequency ({decision}). '
        f'Size to {size_pct:.0%} pot ({size_bb:.1f}BB). '
        f'{"Rarely donk flop in balanced play; reserve for exploitative spots vs specific villains" if street == "flop" else "Turn donk exploits IP passive flop check; lead top pair+, draws, and some air blockers" if street == "turn" else "River donk: IP very weak; lead value + missed-draw bluffs at high frequency"}.'
    )

    if villain_type == 'nit':
        tips.append(
            f'vs NIT IP: increase donk to {freq:.0%}. '
            f'Nit rarely bets without strong hand; your donk denies free showdown. '
            f'Nit folds to donk bets frequently -- bluffs gain extra EV. '
            f'Size {size_pct:.0%} pot; nit will call/raise only with clear value.'
        )
    elif villain_type == 'lag':
        tips.append(
            f'vs LAG IP: reduce donk to {freq:.0%}. '
            f'LAG raises donk bets aggressively; your donk turns into a check-raise situation. '
            f'Only donk strong value hands vs LAG (top two pair+, sets, straights). '
            f'Check-call or check-raise is often better than donking vs LAG on {street}.'
        )
    elif villain_type in ('fish', 'calling_station'):
        tips.append(
            f'vs {villain_type.upper()} IP: donk {freq:.0%} (reduced). '
            f'{villain_type} calls your donk bets too wide -- bluff donks lose EV. '
            f'Only donk strong value hands that benefit from calling-station behavior. '
            f'Check and let them bet with worse hands, then call down or raise.'
        )
    else:
        tips.append(
            f'vs {villain_type} IP: standard donk {freq:.0%} on {street}. '
            f'Balance donk range: '
            f'{"value hands (top pair+) + strong draws (FD, OESD) + select bluffs with blockers" if street == "flop" else "strong made hands + draws + some air with backdoor equity" if street == "turn" else "value (straights, flushes, two pair+) + missed draw bluffs + blocker bets"}. '
            f'Size {size_pct:.0%} pot ({size_bb:.1f}BB).'
        )

    return DonkBetFrequencyResult(
        street=street,
        board_texture=board_texture,
        villain_type=villain_type,
        pot_bb=pot_bb,
        base_donk_freq=base,
        optimal_donk_freq=freq,
        donk_size_pct=size_pct,
        donk_size_bb=size_bb,
        donk_decision=decision,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def dbf_one_liner(r: DonkBetFrequencyResult) -> str:
    return (
        f'[DONK {r.street}|{r.board_texture}] '
        f'freq={r.optimal_donk_freq:.0%} size={r.donk_size_pct:.0%}pot {r.donk_decision}'
    )
