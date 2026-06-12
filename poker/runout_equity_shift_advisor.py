"""
Runout Equity Shift Advisor (runout_equity_shift_advisor.py)

Analyzes how much a new card (turn or river) SHIFTS EQUITY between ranges,
recommending whether to barrel or slow down based on who benefits.

THEORY:
  EQUITY SHIFT = how much the new card benefits hero's range vs villain's.

  POSITIVE SHIFT (hero gains):
  - Overcard hero's raising range contains more of
  - Board pairs a high card (PFR has more top pair / two pair)
  - Action card that improves PFR range (A on low board)
  - River blank that maintains PFR's range advantage

  NEGATIVE SHIFT (villain gains):
  - Flush draw completes (callers have more flush draws)
  - Straight completes (callers have more straight draws)
  - Low card pairs (BB/SB calling range has more low pairs)
  - Scare card for hero's made hands

  BARREL FREQUENCY:
  Large positive shift  -> barrel 75-85%
  Slight positive       -> barrel 55-65%
  Neutral               -> barrel ~50%
  Negative shift        -> barrel 30-45%
  Large negative shift  -> barrel 15-25%

DISTINCT FROM:
  turn_runout_analysis.py:   General turn card classification
  board_pairing_advantage.py: Specific board pairing analysis
  turn_texture_change.py:    Texture change on the turn
  THIS MODULE:               EQUITY SHIFT MAGNITUDE; barrel frequency adjustment;
                             PFR vs caller range benefit; card-by-card shift table.
"""

from dataclasses import dataclass, field
from typing import List


# (pfr_shift, caller_shift) for each card type
# positive = that player's range benefits from this card
CARD_SHIFT: dict = {
    'blank':                  ( 0.02, -0.02),
    'overcard_for_pfr':       ( 0.10, -0.10),
    'overcard_for_caller':    (-0.08,  0.08),
    'flush_draw_completes':   (-0.06,  0.06),
    'straight_completes':     (-0.10,  0.10),
    'board_pairs_high':       ( 0.08, -0.08),
    'board_pairs_low':        (-0.08,  0.08),
    'second_flush_draw':      (-0.04,  0.04),
    'action_card':            ( 0.06, -0.06),
    'scare_card_for_pfr':     (-0.07,  0.07),
    'rainbow_completes':      ( 0.01, -0.01),
    'backdoor_flush_blocker': ( 0.03, -0.03),
}

BARREL_FREQUENCY: dict = {
    'large_hero_gain':       0.80,
    'moderate_hero_gain':    0.62,
    'neutral':               0.50,
    'moderate_villain_gain': 0.36,
    'large_villain_gain':    0.20,
}

TEXTURE_BARREL_MOD: dict = {
    'dry':       0.05,
    'semi_wet':  0.00,
    'wet':      -0.05,
    'monotone': -0.10,
}


def _equity_shift(card_type: str, hero_is_pfr: bool) -> float:
    pair = CARD_SHIFT.get(card_type, (0.0, 0.0))
    return pair[0] if hero_is_pfr else pair[1]


def _shift_category(shift: float) -> str:
    if shift >= 0.08:
        return 'large_hero_gain'
    elif shift >= 0.04:
        return 'moderate_hero_gain'
    elif shift >= -0.03:
        return 'neutral'
    elif shift >= -0.08:
        return 'moderate_villain_gain'
    else:
        return 'large_villain_gain'


def _barrel_frequency(shift_cat: str, flop_texture: str, position: str) -> float:
    base = BARREL_FREQUENCY.get(shift_cat, 0.50)
    mod = TEXTURE_BARREL_MOD.get(flop_texture, 0.0)
    pos_mod = 0.05 if position == 'ip' else -0.05
    return round(min(0.90, max(0.10, base + mod + pos_mod)), 2)


def _barrel_sizing(shift_cat: str, street: str) -> float:
    base = 0.60 if street == 'turn' else 0.65
    if shift_cat == 'large_hero_gain':
        return round(min(0.90, base + 0.15), 2)
    elif shift_cat == 'moderate_hero_gain':
        return round(base + 0.05, 2)
    elif shift_cat in ('moderate_villain_gain', 'large_villain_gain'):
        return round(max(0.40, base - 0.15), 2)
    return base


def _action_recommendation(
    shift_cat: str,
    barrel_freq: float,
    hero_is_pfr: bool,
    hand_strength: str,
) -> str:
    if shift_cat == 'large_hero_gain':
        return 'BARREL_STRONG'
    elif shift_cat == 'moderate_hero_gain':
        if hand_strength in ('strong_value', 'nuts', 'top_pair'):
            return 'BARREL_VALUE'
        return 'BARREL_SELECTIVE'
    elif shift_cat == 'neutral':
        if hand_strength in ('air', 'missed_draw'):
            return 'CHECK_OR_GIVE_UP'
        return 'BARREL_NORMAL'
    elif shift_cat == 'moderate_villain_gain':
        if hand_strength in ('nuts', 'strong_value'):
            return 'BET_PROTECTED_VALUE'
        return 'CHECK_CONTROL'
    else:
        return 'CHECK_FOLD_BLUFFS'


@dataclass
class RunoutEquityShiftResult:
    card_type: str
    hero_is_pfr: bool
    street: str
    position: str
    flop_texture: str
    hand_strength: str

    equity_shift: float
    shift_category: str
    barrel_frequency: float
    barrel_size_frac: float

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_runout_equity_shift(
    card_type: str = 'blank',
    hero_is_pfr: bool = True,
    street: str = 'turn',
    position: str = 'ip',
    flop_texture: str = 'semi_wet',
    hand_strength: str = 'top_pair',
    pot_bb: float = 20.0,
) -> RunoutEquityShiftResult:
    """
    Analyze equity shift from a new card and recommend barrel frequency.

    Args:
        card_type:      New card type ('blank','overcard_for_pfr','overcard_for_caller',
                        'flush_draw_completes','straight_completes','board_pairs_high',
                        'board_pairs_low','action_card','scare_card_for_pfr')
        hero_is_pfr:    True if hero was preflop raiser
        street:         Current street ('turn' or 'river')
        position:       Hero position ('ip' or 'oop')
        flop_texture:   Flop texture ('dry','semi_wet','wet','monotone')
        hand_strength:  Hero hand strength
        pot_bb:         Pot in BB before barrel

    Returns:
        RunoutEquityShiftResult
    """
    shift = _equity_shift(card_type, hero_is_pfr)
    shift_cat = _shift_category(shift)
    barrel_freq = _barrel_frequency(shift_cat, flop_texture, position)
    barrel_size = _barrel_sizing(shift_cat, street)
    barrel_bb = round(pot_bb * barrel_size, 1)
    action = _action_recommendation(shift_cat, barrel_freq, hero_is_pfr, hand_strength)

    role = 'PFR' if hero_is_pfr else 'CALL'
    sign = '+' if shift >= 0 else ''

    verdict = (
        f'[RES {card_type}|{role}|{street}] '
        f'shift={sign}{shift:+.2f} [{shift_cat}] '
        f'barrel={barrel_freq:.0%} size={barrel_size:.0%}pot={barrel_bb:.1f}BB '
        f'{action}'
    )

    reasoning = (
        f'Runout equity shift: {card_type} on {street}. '
        f'Hero is {role} {position.upper()} on {flop_texture} flop. '
        f'Equity shift: {sign}{shift:+.2f} ({shift_cat}). '
        f'Barrel frequency: {barrel_freq:.0%} at {barrel_size:.0%} pot = {barrel_bb:.1f}BB. '
        f'Action: {action}.'
    )

    tips = []

    tips.append(
        f'BARREL STRATEGY: {action}. '
        f'Frequency={barrel_freq:.0%} at {barrel_size:.0%}pot={barrel_bb:.1f}BB. '
        f'{"Range advantage maintained -- continue aggression." if shift >= 0 else "Villain range improved -- protect equity."}'
    )

    tips.append(
        f'EQUITY SHIFT: {sign}{shift:+.2f} ({shift_cat}). '
        f'{"Hero gains range advantage -- barrel more." if shift >= 0.04 else "Villain gains range advantage -- slow down." if shift <= -0.04 else "Neutral runout -- barrel at normal frequency."} '
        f'Recommended barrel frequency: {barrel_freq:.0%}.'
    )

    if shift_cat == 'large_hero_gain':
        tips.append(
            f'STRONG BARREL SPOT: {card_type} improves hero range significantly. '
            f'Barrel {barrel_freq:.0%} with size {barrel_size:.0%} pot. '
            f'Villain cannot defend enough -- bet value AND bluffs aggressively.'
        )
    elif shift_cat == 'large_villain_gain':
        tips.append(
            f'EQUITY DANGER: {card_type} improved villain range significantly. '
            f'Reduce barrel to {barrel_freq:.0%}. '
            f'Only barrel strong value for protection; check most bluffs.'
        )
    elif shift_cat == 'moderate_hero_gain':
        tips.append(
            f'GOOD BARREL SPOT: {card_type} slightly improves hero range. '
            f'Barrel {barrel_freq:.0%} -- focus on value and strong semi-bluffs.'
        )

    if card_type == 'flush_draw_completes':
        tips.append(
            f'FLUSH CARD: Callers have more flush draws than raisers. '
            f'{"As PFR, check more on this runout; villain range improved." if hero_is_pfr else "As caller, flush card boosts your range -- consider leading."}'
        )
    elif card_type == 'straight_completes':
        tips.append(
            f'STRAIGHT CARD: Callers have more straight draw combos. '
            f'{"As PFR, do not triple-barrel without the nuts." if hero_is_pfr else "As caller, this card improves your range; check-raise or lead more."}'
        )
    elif card_type in ('board_pairs_high', 'overcard_for_pfr', 'action_card'):
        tips.append(
            f'PFR GAINS: {card_type} improves PFR range significantly. '
            f'{"Barrel aggressively; villain range weakened." if hero_is_pfr else "Proceed cautiously; PFR range now stronger."}'
        )
    elif card_type in ('board_pairs_low', 'overcard_for_caller'):
        tips.append(
            f'CALLER GAINS: {card_type} benefits caller range. '
            f'{"As PFR, check more; avoid bluffing into improved villain range." if hero_is_pfr else "As caller, lead or check-raise more aggressively."}'
        )

    return RunoutEquityShiftResult(
        card_type=card_type,
        hero_is_pfr=hero_is_pfr,
        street=street,
        position=position,
        flop_texture=flop_texture,
        hand_strength=hand_strength,
        equity_shift=shift,
        shift_category=shift_cat,
        barrel_frequency=barrel_freq,
        barrel_size_frac=barrel_size,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def res_one_liner(r: RunoutEquityShiftResult) -> str:
    sign = '+' if r.equity_shift >= 0 else ''
    return (
        f'[RES {r.card_type}|{"PFR" if r.hero_is_pfr else "CALL"}|{r.street}] '
        f'shift={sign}{r.equity_shift:+.2f} barrel={r.barrel_frequency:.0%} '
        f'{r.recommended_action}'
    )
