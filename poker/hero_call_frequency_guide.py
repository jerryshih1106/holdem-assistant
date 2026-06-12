"""
Hero Call Frequency Guide (hero_call_frequency_guide.py)

Determines when hero should hero-call (call despite evidence of villain strength)
based on villain bluff frequency, pot odds, and blocker effects.

THEORY:
  HERO CALL vs HERO FOLD:
  Hero call = calling a strong-looking bet with a medium holding, based on the
  read that villain is bluffing often enough to make the call profitable.

  MATHEMATICAL CONDITION:
  Call if: villain_bluff_freq > pot_odds_needed
  pot_odds_needed = bet / (pot + bet) = MDF equivalent for villain bluffs

  Example: villain bets 75% pot. pot_odds = 0.43.
  Call if villain bluffs >43% of their betting range.

  VILLAIN BLUFF FREQUENCY BY TYPE:
  Reg:              30-40% of river bets are bluffs (balanced range)
  LAG:              40-55% (bluffs very frequently)
  Nit:               5-15% (almost never bluffs)
  Fish:             20-30% (random; often more value-heavy)
  Calling_station:  10-20% (passive; rarely bets as bluff)

  BOARD TEXTURE IMPACT:
  Missed draws on river: villain bluffs with busted draws -> higher bluff freq
  Dry river:             fewer missed draws -> lower bluff freq
  Scary card landed:     villain may bluff with scare card -> moderate adjustment

  BLOCKER EFFECT:
  Holding a blocker to villain's value range increases call EV.

DISTINCT FROM:
  hero_fold_frequency_guide.py: How often to fold (fold frequency calibration)
  call_threshold.py:            When a specific hand should call
  mdf.py:                       Raw MDF calculations
  THIS MODULE:                  HERO CALL decision: when to call despite
                                evidence of strength; villain bluff freq analysis.
"""

from dataclasses import dataclass, field
from typing import List

VILLAIN_BLUFF_FREQ_RIVER: dict = {
    'fish':            0.28,
    'calling_station': 0.15,
    'nit':             0.10,
    'lag':             0.48,
    'rec':             0.32,
    'reg':             0.35,
}

BOARD_BLUFF_ADJ_HERO_CALL: dict = {
    'dry':                -0.05,
    'semi_wet':            0.00,
    'wet':                +0.05,
    'flush_draw_missed':  +0.12,
    'straight_missed':    +0.10,
    'monotone':           +0.04,
    'paired':             -0.03,
}

BLOCKER_CALL_BOOST: float = 0.06
VILLAIN_BLUFF_ADJ_STREET: dict = {
    'flop':  +0.10,
    'turn':  +0.05,
    'river':  0.00,
}

CALL_MARGIN: float = 0.03


def _mdf_call(bet_frac: float) -> float:
    return round(bet_frac / (1 + bet_frac), 3)


def _adjusted_villain_bluff_freq(
    villain_type: str,
    board_texture: str,
    street: str,
    has_blocker: bool,
) -> float:
    base = VILLAIN_BLUFF_FREQ_RIVER.get(villain_type, 0.30)
    board_adj = BOARD_BLUFF_ADJ_HERO_CALL.get(board_texture, 0.00)
    str_adj = VILLAIN_BLUFF_ADJ_STREET.get(street, 0.00)
    block_adj = BLOCKER_CALL_BOOST if has_blocker else 0.0
    freq = base + board_adj + str_adj + block_adj
    return round(min(0.80, max(0.02, freq)), 3)


def _hero_call_decision(bluff_freq: float, pot_odds_needed: float) -> str:
    margin = bluff_freq - pot_odds_needed
    if margin > 0.08:
        return 'STRONG_HERO_CALL'
    if margin > CALL_MARGIN:
        return 'HERO_CALL_MARGINAL'
    if margin > -CALL_MARGIN:
        return 'INDIFFERENT_CALL_OR_FOLD'
    return 'FOLD_VILLAIN_BLUFFS_TOO_RARELY'


@dataclass
class HeroCallFrequencyResult:
    bet_frac: float
    villain_type: str
    board_texture: str
    street: str
    has_blocker: bool

    villain_bluff_freq: float
    pot_odds_needed: float
    call_decision: str
    call_ev_approx: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_hero_call_frequency(
    bet_frac: float = 0.75,
    villain_type: str = 'reg',
    board_texture: str = 'semi_wet',
    street: str = 'river',
    has_blocker: bool = False,
) -> HeroCallFrequencyResult:
    """
    Evaluate whether hero should call despite apparent villain strength.

    Args:
        bet_frac:      Villain's bet as fraction of pot (0.5 = half pot)
        villain_type:  Villain type ('fish','nit','lag','reg', etc.)
        board_texture: Board texture ('dry','semi_wet','wet','flush_draw_missed',etc.)
        street:        Current street ('flop','turn','river')
        has_blocker:   True if hero holds a blocker to villain's value range

    Returns:
        HeroCallFrequencyResult
    """
    bluff_freq = _adjusted_villain_bluff_freq(villain_type, board_texture, street, has_blocker)
    pot_odds = _mdf_call(bet_frac)
    decision = _hero_call_decision(bluff_freq, pot_odds)
    call_ev = round((bluff_freq - pot_odds) * (1.0 + bet_frac), 2)

    verdict = (
        f'[HCF {villain_type}|{board_texture}|{street}|bet={bet_frac:.0%}] '
        f'bluff_est={bluff_freq:.0%} need={pot_odds:.0%} dec={decision}'
    )

    reasoning = (
        f'Hero call vs {villain_type} {bet_frac:.0%} pot bet on {street}: '
        f'base_bluff={VILLAIN_BLUFF_FREQ_RIVER.get(villain_type, 0.30):.0%} '
        f'board_adj={BOARD_BLUFF_ADJ_HERO_CALL.get(board_texture, 0):+.0%} '
        f'str_adj={VILLAIN_BLUFF_ADJ_STREET.get(street, 0):+.0%} '
        f'blocker_adj={BLOCKER_CALL_BOOST if has_blocker else 0:+.0%}. '
        f'Est_bluff_freq={bluff_freq:.0%} pot_odds_needed={pot_odds:.0%}. '
        f'Call_EV={call_ev:+.2f}pot-units. Decision={decision}.'
    )

    tips = []

    tips.append(
        f'Hero call vs {villain_type} ({bet_frac:.0%} pot bet): '
        f'villain bluffs est={bluff_freq:.0%}, need {pot_odds:.0%} to break even. '
        f'{"PROFITABLE CALL: villain bluffs enough" if bluff_freq > pot_odds else "UNPROFITABLE CALL: villain value-heavy"}. '
        f'Decision: {decision}.'
    )

    if decision in ('STRONG_HERO_CALL', 'HERO_CALL_MARGINAL'):
        tips.append(
            f'HERO CALL: {villain_type} bluffs {bluff_freq:.0%} here vs need {pot_odds:.0%}. '
            f'EV = {call_ev:+.2f} pot-units. '
            f'{"LAG bluffs very frequently on this runout -- call with all bluff catchers" if villain_type == "lag" else "Protect call range from exact pot odds exploitation"}. '
            f'Call with: medium pairs, bluff catchers, hands that beat bluffs.'
        )
    elif decision == 'FOLD_VILLAIN_BLUFFS_TOO_RARELY':
        tips.append(
            f'FOLD recommended: {villain_type} bluffs only {bluff_freq:.0%} vs need {pot_odds:.0%}. '
            f'{"NIT almost never bluffs -- fold everything but strongest hands" if villain_type == "nit" else "Fish/station value-bets wide but rarely pure bluffs -- fold bluff catchers"}. '
            f'Save hero calls for LAG or draw-heavy boards with missed draws.'
        )
    else:
        tips.append(
            f'BORDERLINE: bluff_freq={bluff_freq:.0%} close to pot_odds={pot_odds:.0%}. '
            f'Mix call/fold with bluff catchers based on blocker strength. '
            f'{"Blocker reduces villain value combos -- lean call" if has_blocker else "No blocker -- lean fold"}.'
        )

    if board_texture == 'flush_draw_missed':
        tips.append(
            f'FLUSH DRAW MISSED: Many villain hands are busted draws. '
            f'Villain bluff freq spikes +{BOARD_BLUFF_ADJ_HERO_CALL.get("flush_draw_missed", 0):.0%}. '
            f'Hero call with all hands that beat missed flush draw range.'
        )

    return HeroCallFrequencyResult(
        bet_frac=bet_frac,
        villain_type=villain_type,
        board_texture=board_texture,
        street=street,
        has_blocker=has_blocker,
        villain_bluff_freq=bluff_freq,
        pot_odds_needed=pot_odds,
        call_decision=decision,
        call_ev_approx=call_ev,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def hcf_one_liner(r: HeroCallFrequencyResult) -> str:
    return (
        f'[HCF {r.villain_type}|{r.board_texture}|bet={r.bet_frac:.0%}] '
        f'bluff={r.villain_bluff_freq:.0%} need={r.pot_odds_needed:.0%} {r.call_decision}'
    )
