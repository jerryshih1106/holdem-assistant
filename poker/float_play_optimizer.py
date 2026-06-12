"""
Float Play Optimizer (float_play_optimizer.py)

Analyzes the FLOAT PLAY: calling a flop c-bet in position with a weak hand,
then taking the pot away on the turn when villain checks back.

THEORY:
  FLOAT = call a c-bet in position with weak hand (limited equity) as a
  DELAYED BLUFF. The plan is to bet the turn if villain shows weakness
  by checking the turn.

  FLOAT EV FORMULA:
    EV(float) = P(villain_checks_turn) * P(villain_folds_turn_bet) * pot_gain
              + P(villain_checks_turn) * P(villain_calls_turn_bet) * EV_if_called
              + P(villain_bets_turn)   * EV_if_villain_bets_turn
              - flop_call_cost

  Simplified:
    EV(float) = P(vill_check_turn) * [villain_fold_turn * (pot + vill_cbet)
                                       - villain_call_turn * hero_turn_bet]
              + P(vill_bet_turn)   * (-flop_call_cost)  [hero folds to 2nd barrel]
              - flop_call_cost

  WHEN FLOATING IS PROFITABLE:
  1. Villain has HIGH single-barrel c-bet frequency but LOW double-barrel:
     - C-bet 70%+ of flops, but gives up 50%+ of turns when called = great float spot
  2. Hero is IN POSITION (sees villain's turn action first after checking)
  3. Board has many scare cards on turn (A, flush complete, straight complete):
     - Villain will give up when scare card comes
  4. Hero's hand has some showdown value or backdoor equity
  5. Villain is a "fish" or "rec" type: bets wide on flop, gives up easily

  WHEN NOT TO FLOAT:
  1. Villain has high double-barrel frequency (double-barrels 60%+ of turns)
  2. Out of position (can't see villain's check first)
  3. Villain's range crushes the board (A-high board with UTG villain)
  4. Hero has absolutely no equity (no backdoor, no overcards)

  IDEAL FLOAT SPOT:
  - Villain: rec/fish, c-bet 65%+, double-barrel < 40%
  - Hero: IP, some backdoor equity or overcard
  - Board: dry flop that often blanks on turn (low connected boards)
  - Pot is manageable (not already too large)

  FLOAT TURN BET SIZE:
  - 55-70% pot: standard; represents made hand
  - Large enough to deny calling; villain's weak range cannot call profitably

DISTINCT FROM:
  probe_bet.py:    Turn probe bet (OOP after flop checks through)
  fold_equity.py:  General fold equity calculation
  bluff_advisor.py: General bluffing advisor
  THIS MODULE:     FLOAT PLAY as in-position delayed bluff; villain check-through
                   frequencies; double-barrel analysis; scare card equity.
"""

from dataclasses import dataclass, field
from typing import List


# Double-barrel tendencies by villain type
DOUBLE_BARREL_PCT: dict = {
    'fish':           0.28,
    'rec':            0.32,
    'calling_station': 0.20,
    'tight':          0.48,
    'nit':            0.55,
    'reg':            0.52,
    'lag':            0.68,
    'tag':            0.55,
    'unknown':        0.40,
}

# C-bet give-up (turn check) rate when called on flop
TURN_GIVE_UP_PCT: dict = {
    'fish':           0.60,
    'rec':            0.55,
    'calling_station': 0.25,
    'tight':          0.42,
    'nit':            0.38,
    'reg':            0.45,
    'lag':            0.30,
    'tag':            0.40,
    'unknown':        0.48,
}

# Turn fold% when facing float bet
TURN_FOLD_VS_FLOAT: dict = {
    'fish':           0.62,
    'rec':            0.58,
    'calling_station': 0.25,
    'tight':          0.52,
    'nit':            0.48,
    'reg':            0.48,
    'lag':            0.42,
    'tag':            0.50,
    'unknown':        0.50,
}


def _float_ev(
    flop_cbet_bb: float,
    pot_after_cbet: float,
    turn_give_up_pct: float,
    turn_fold_pct: float,
    hero_turn_bet_bb: float,
    hero_equity_if_called: float,
    villain_double_barrel_pct: float,
) -> float:
    # Hero calls flop, pays flop_cbet_bb
    # Case 1: villain checks turn (give-up)
    pot_after_call = pot_after_cbet + flop_cbet_bb
    turn_ev = (
        turn_fold_pct * pot_after_call          # villain folds to hero's turn bet
        + (1 - turn_fold_pct) * (hero_equity_if_called * (pot_after_call + hero_turn_bet_bb) - hero_turn_bet_bb)
    )
    check_turn_ev = turn_give_up_pct * turn_ev

    # Case 2: villain double-barrels turn -> hero folds (loses flop call)
    double_barrel_ev = villain_double_barrel_pct * 0.0  # hero folds; already paid flop call

    total_ev = check_turn_ev + double_barrel_ev - flop_cbet_bb
    return round(total_ev, 2)


def _float_profitability(
    villain_type: str,
    flop_cbet_pct: float,
    hero_equity: float,
    position: str,
) -> float:
    score = 0.0
    score += (1.0 - DOUBLE_BARREL_PCT.get(villain_type, 0.40)) * 3.0
    score += TURN_GIVE_UP_PCT.get(villain_type, 0.48) * 3.0
    score += hero_equity * 2.0
    if position == 'ip':
        score += 1.5
    if flop_cbet_pct >= 0.65:
        score += 0.5  # wide c-bet = more bluffs to take away
    return round(min(10.0, max(0.0, score)), 1)


@dataclass
class FloatResult:
    villain_type: str
    flop_cbet_pct: float
    villain_double_barrel_pct: float
    turn_give_up_pct: float
    turn_fold_pct: float

    flop_call_bb: float
    hero_turn_bet_bb: float
    float_ev_bb: float
    profitability_score: float

    recommendation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def optimize_float(
    villain_type: str = 'rec',
    flop_cbet_pct: float = 0.65,
    flop_cbet_bb: float = 8.0,
    pot_before_cbet: float = 12.0,
    position: str = 'ip',
    hero_hand: str = 'overcards',
    hero_equity: float = 0.15,
    hero_turn_bet_frac: float = 0.60,
) -> FloatResult:
    """
    Optimize the float play decision.

    Args:
        villain_type:       Villain player type
        flop_cbet_pct:      Villain's flop c-bet frequency
        flop_cbet_bb:       Villain's actual c-bet size in BB
        pot_before_cbet:    Pot size before villain's c-bet
        position:           Hero's position ('ip' always for float)
        hero_hand:          Hero's hand category
        hero_equity:        Hero's raw equity at showdown
        hero_turn_bet_frac: Hero's planned turn bet as fraction of pot

    Returns:
        FloatResult
    """
    dbl = DOUBLE_BARREL_PCT.get(villain_type, 0.40)
    give_up = TURN_GIVE_UP_PCT.get(villain_type, 0.48)
    fold_vs_float = TURN_FOLD_VS_FLOAT.get(villain_type, 0.50)

    pot_after_cbet = pot_before_cbet + flop_cbet_bb   # villain's bet added
    pot_after_call = pot_after_cbet + flop_cbet_bb    # hero's call added
    turn_bet_bb = round(pot_after_call * hero_turn_bet_frac, 1)

    ev = _float_ev(
        flop_cbet_bb, pot_after_cbet, give_up, fold_vs_float,
        turn_bet_bb, hero_equity, dbl,
    )
    score = _float_profitability(villain_type, flop_cbet_pct, hero_equity, position)

    if position != 'ip':
        rec = 'FLOAT_REQUIRES_IP'
    elif score >= 7.0 and ev > 0:
        rec = 'FLOAT'
    elif score >= 5.0 and ev > 0:
        rec = 'FLOAT_MARGINAL'
    elif ev > 0:
        rec = 'FLOAT_THIN'
    else:
        rec = 'FOLD_OR_CALL_ONLY_WITH_EQUITY'

    verdict = (
        f'[FLT {hero_hand}|{villain_type}|{position}] '
        f'{rec} | score={score:.0f}/10 EV={ev:+.1f}BB | '
        f'give_up={give_up:.0%} dbl_barrel={dbl:.0%}'
    )

    reasoning = (
        f'Float play: {position.upper()} vs {villain_type} ({flop_cbet_pct:.0%} c-bet). '
        f'Hero has {hero_hand} (equity={hero_equity:.0%}). '
        f'Villain double-barrel: {dbl:.0%}. Turn give-up: {give_up:.0%}. '
        f'Float EV={ev:+.1f}BB. Profitability score: {score:.0f}/10. '
        f'Recommendation: {rec}.'
    )

    tips = []

    tips.append(
        f'FLOAT ANALYSIS: Villain double-barrel={dbl:.0%}, give-up={give_up:.0%}. '
        f'Turn bet={turn_bet_bb:.0f}BB ({hero_turn_bet_frac:.0%}pot). '
        f'Float EV={ev:+.1f}BB. Score={score:.0f}/10.'
    )

    if dbl <= 0.35:
        tips.append(
            f'LOW DOUBLE-BARREL ({dbl:.0%}): Villain gives up turn often. '
            f'Float is EFFECTIVE here. '
            f'Call flop, bet turn when villain checks (expected {give_up:.0%} of the time).'
        )
    elif dbl >= 0.60:
        tips.append(
            f'HIGH DOUBLE-BARREL ({dbl:.0%}): Villain fires 2 bullets often. '
            f'Float is RISKY. Need real equity to continue vs. 2nd barrel. '
            f'Consider fold or only float with strong backdoor equity.'
        )

    if position == 'ip':
        tips.append(
            f'IP FLOAT ADVANTAGE: You see villain\'s action before deciding. '
            f'When villain checks turn ({give_up:.0%} chance), bet {turn_bet_bb:.0f}BB '
            f'({hero_turn_bet_frac:.0%}pot) to represent strong made hand.'
        )
    else:
        tips.append(
            f'OOP FLOAT: Floating out-of-position is almost always incorrect. '
            f'You must act first on the turn without information. '
            f'Only proceed if you have real equity (draws, pairs).'
        )

    if hero_equity >= 0.20:
        tips.append(
            f'BACKDOOR EQUITY ({hero_equity:.0%}): Float has value + equity component. '
            f'Even if villain double-barrels, you have {hero_equity:.0%} equity to continue.'
        )

    if flop_cbet_pct >= 0.70:
        tips.append(
            f'WIDE C-BET VILLAIN ({flop_cbet_pct:.0%}): Many c-bets are weak/air. '
            f'Floating counters over-c-betting. '
            f'Villain cannot have value every time they c-bet {flop_cbet_pct:.0%}+ of flops.'
        )

    return FloatResult(
        villain_type=villain_type,
        flop_cbet_pct=flop_cbet_pct,
        villain_double_barrel_pct=dbl,
        turn_give_up_pct=give_up,
        turn_fold_pct=fold_vs_float,
        flop_call_bb=flop_cbet_bb,
        hero_turn_bet_bb=turn_bet_bb,
        float_ev_bb=ev,
        profitability_score=score,
        recommendation=rec,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def flt_one_liner(r: FloatResult) -> str:
    return (
        f'[FLT {r.villain_type}] {r.recommendation} '
        f'score={r.profitability_score:.0f}/10 EV={r.float_ev_bb:+.1f}BB '
        f'dbl={r.villain_double_barrel_pct:.0%}'
    )
