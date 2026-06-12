"""
OOP Float Advisor (oop_float_advisor.py)

Advises Out-of-Position (OOP) players on floating (calling a bet OOP with
a plan to bet into villain on a later street when they check).

KEY INSIGHT: IP floating is well-covered (float_bet.py), but OOP floating
is different and often misunderstood. OOP float requires:
  1. Villain checks back turn/river at high frequency (passive)
  2. Hero has enough equity or outs to improve
  3. Hero's hand can credibly represent a range on future streets
  4. Pot size and stack depth justify the investment

OOP FLOAT TYPES:
  float_to_probe:   Call flop bet; probe turn when villain checks (check-check)
  float_to_river:   Call flop+turn bets; bet river when checked to
  float_and_raise:  Call; check-raise when villain fires again
  semi_float:       Call with draw; realized equity + fold equity on later streets

VILLAIN BEHAVIOR REQUIRED:
  For OOP float to profit, villain must check frequently after being called.
  Key stats: villain's "bet-flop-check-turn" frequency and cbet-turn% after cbet-flop.
  Passive villains (low AF) check back turns frequently → OOP float is profitable.

EQUITY THRESHOLD:
  OOP float needs HIGHER equity than IP float because:
  - Hero acts first on all future streets (no bluff-catching position)
  - Hero must either improve or rely on villain's passivity
  - If villain keeps betting, OOP player has no free card option

DISTINCT FROM:
  float_bet.py:       IP float strategy (acts after villain checks)
  turn_probe_bet_advisor.py: Check-check flop → probe turn
  THIS MODULE:        OOP-specific float calling + future street plan;
                      focuses on "hero calls villain's bet OOP" scenario

Usage:
    from poker.oop_float_advisor import advise_oop_float, OOPFloatAdvice, ofa_one_liner

    result = advise_oop_float(
        hero_hand_category='middle_pair',
        board_texture='semi_wet',
        street='flop',
        cbet_size_pct=0.50,
        villain_af=1.5,
        villain_wtsd=0.30,
        villain_cbet_turn_pct=0.45,
        hero_equity=0.35,
        pot_bb=10.0,
        hero_stack_bb=90.0,
    )
    print(ofa_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Minimum equity required for OOP float (higher than IP float)
MIN_EQUITY_OOP_FLOAT = 0.25   # vs 0.18 for IP float


def _villain_check_back_freq(villain_af: float, villain_cbet_turn_pct: float) -> float:
    """
    Estimate how often villain checks back the turn after flop cbet is called.
    Higher check-back = more profitable OOP float.
    """
    # High cbet-turn% → villain barrels → OOP float needs more equity
    check_back = round(max(0.10, min(0.85, 1.0 - villain_cbet_turn_pct)), 3)
    # Low AF means villain is passive → check back more
    if villain_af <= 1.2:
        check_back = min(0.85, check_back + 0.10)
    elif villain_af >= 3.0:
        check_back = max(0.10, check_back - 0.12)
    return round(check_back, 3)


def _float_type(
    hero_hand_category: str,
    hero_equity: float,
    board_texture: str,
    villain_check_back: float,
) -> str:
    """Classify the float type."""
    if hero_hand_category in ('flush_draw', 'straight_draw', 'draw', 'combo_draw'):
        return 'semi_float'   # equity + fold equity
    elif hero_equity >= 0.40 and villain_check_back >= 0.50:
        return 'float_to_probe'  # decent equity + villain checks often
    elif hero_hand_category in ('middle_pair', 'top_pair', 'weak_top_pair'):
        if villain_check_back >= 0.45:
            return 'float_to_probe'
        else:
            return 'float_and_raise'  # passive float is marginally profitable
    elif hero_equity >= 0.30 and board_texture == 'dry':
        return 'float_to_probe'  # dry board: villain checks back often
    else:
        return 'float_to_river'  # deep float hoping to improve


def _float_ev(
    hero_equity: float,
    pot_bb: float,
    call_cost: float,
    villain_check_back: float,
    probe_success_rate: float,
    float_type: str,
) -> float:
    """
    Simplified EV of OOP float vs folding.
    EV = P(villain checks) × (probe succeeds → win pot) + P(improve) × equity
       - call_cost
    """
    if float_type == 'semi_float':
        # Equity realization + fold equity when probe succeeds
        ev_improve = hero_equity * (pot_bb + 2 * call_cost)   # when improve
        ev_probe = villain_check_back * probe_success_rate * pot_bb   # bluff win
        ev_give_up = villain_check_back * (1 - probe_success_rate) * 0   # give up
        ev = ev_improve * (1 - villain_check_back) + ev_probe - call_cost
    else:
        # Value float: win pot when villain folds to probe; showdown EV otherwise
        ev_probe_win = villain_check_back * probe_success_rate * pot_bb
        ev_sd = hero_equity * (pot_bb + 2 * call_cost) * (1 - villain_check_back)
        ev = ev_probe_win + ev_sd * 0.5 - call_cost  # 0.5 discount for imperfect play

    return round(ev, 2)


def _should_float(
    hero_equity: float,
    float_ev: float,
    float_type: str,
    villain_af: float,
    villain_check_back: float,
    street: str,
) -> bool:
    """Decision to float or fold."""
    if hero_equity < MIN_EQUITY_OOP_FLOAT and float_type not in ('semi_float',):
        return False
    if float_ev <= -1.0:
        return False
    if villain_af >= 3.5:
        return False   # very aggressive; OOP float is too costly
    if villain_check_back < 0.25:
        return False   # villain keeps barreling; float needs check-backs
    if street == 'river':
        return False   # no future streets; OOP float on river = calling
    return float_ev >= -0.5 and (hero_equity >= 0.25 or float_type == 'semi_float')


def _probe_success_rate(
    hero_hand_category: str,
    board_texture: str,
    villain_wtsd: float,
    villain_af: float,
) -> float:
    """Estimated fold rate when hero probes after villain checks back."""
    base = 0.50  # base fold rate to OOP probe
    # Strong hands → villain calls more with good hands vs OOP probe
    if hero_hand_category in ('top_pair', 'overpair', 'two_pair', 'set'):
        base = 0.35   # villain calls with any pair; probe is for value
    elif hero_hand_category in ('flush_draw', 'straight_draw', 'draw', 'combo_draw'):
        base = 0.55   # semi-bluff probe; villain folds marginals
    elif hero_hand_category in ('air', 'missed_draw', 'weak_pair'):
        base = 0.60   # bluff probe; villain has nothing; folds often

    # Passive villains fold to probes more (they check back with weak hands)
    if villain_af <= 1.2:
        base += 0.08
    elif villain_af >= 3.0:
        base -= 0.10  # aggressive villains defend probes more

    # WTSD: high WTSD = villains go to showdown = don't fold probes
    if villain_wtsd >= 0.37:
        base -= 0.10
    elif villain_wtsd <= 0.22:
        base += 0.07

    # Wet boards: villain likely has draws/pairs; calls more
    if board_texture == 'wet':
        base -= 0.08
    elif board_texture == 'dry':
        base += 0.05

    return round(max(0.15, min(0.80, base)), 3)


@dataclass
class OOPFloatAdvice:
    # Inputs
    hero_hand_category: str
    board_texture: str
    street: str
    cbet_size_pct: float
    villain_af: float
    villain_wtsd: float
    villain_cbet_turn_pct: float
    hero_equity: float
    pot_bb: float
    hero_stack_bb: float

    # Analysis
    villain_check_back_freq: float  # P(villain checks back turn after flop cbet called)
    float_type: str                 # 'semi_float' / 'float_to_probe' / 'float_to_river' / 'float_and_raise'
    probe_success_rate: float       # P(villain folds to probe when hero bets turn)
    call_cost_bb: float             # cost to call cbet
    float_ev: float                 # EV of floating vs folding (net)

    # Decision
    action: str                     # 'float' / 'fold' / 'call_showdown'
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_oop_float(
    hero_hand_category: str = 'middle_pair',
    board_texture: str = 'semi_wet',
    street: str = 'flop',
    cbet_size_pct: float = 0.50,
    villain_af: float = 1.5,
    villain_wtsd: float = 0.30,
    villain_cbet_turn_pct: float = 0.45,
    hero_equity: float = 0.35,
    pot_bb: float = 10.0,
    hero_stack_bb: float = 90.0,
) -> OOPFloatAdvice:
    """
    Advise OOP player on whether to float villain's bet with a plan to
    bet into them on future streets when they check.

    Args:
        hero_hand_category: Hand type (top_pair/middle_pair/draw/flush_draw/
                            straight_draw/air/combo_draw/weak_pair/etc.)
        board_texture:      'dry' / 'semi_wet' / 'wet' / 'paired' / 'monotone'
        street:             'flop' / 'turn' (river = calling, not floating)
        cbet_size_pct:      Villain's cbet size as fraction of pot
        villain_af:         Aggression factor
        villain_wtsd:       WTSD stat
        villain_cbet_turn_pct: How often villain fires turn after flop cbet is called
        hero_equity:        Hero's equity (from MC or hand strength)
        pot_bb:             Current pot size
        hero_stack_bb:      Effective stack

    Returns:
        OOPFloatAdvice
    """
    call_cost = round(cbet_size_pct * pot_bb, 1)
    check_back = _villain_check_back_freq(villain_af, villain_cbet_turn_pct)
    probe_success = _probe_success_rate(hero_hand_category, board_texture, villain_wtsd, villain_af)
    f_type = _float_type(hero_hand_category, hero_equity, board_texture, check_back)
    ev = _float_ev(hero_equity, pot_bb, call_cost, check_back, probe_success, f_type)
    should_float = _should_float(hero_equity, ev, f_type, villain_af, check_back, street)

    if should_float:
        action = 'float'
        action_exp = (
            f'FLOAT ({f_type.replace("_", " ")}): Call {call_cost:.1f}BB OOP. '
            f'Villain checks {check_back:.0%} → probe/bet turn. '
            f'Float EV={ev:+.1f}BB. Equity={hero_equity:.0%}, probe success={probe_success:.0%}.'
        )
    elif hero_equity >= 0.45:
        action = 'call_showdown'
        action_exp = (
            f'CALL FOR SHOWDOWN: Call {call_cost:.1f}BB with equity={hero_equity:.0%}. '
            f'Not an optimal float (villain AF={villain_af:.1f} is too aggressive) '
            f'but hand has enough equity to call for showdown value.'
        )
    else:
        action = 'fold'
        action_exp = (
            f'FOLD: Float not profitable. EV={ev:+.1f}BB. '
            f'Villain check-back={check_back:.0%} too low or equity={hero_equity:.0%} insufficient.'
        )

    reasoning = (
        f'OOP float analysis: {hero_hand_category} on {board_texture} {street}. '
        f'Villain cbet {cbet_size_pct:.0%} pot. '
        f'Call cost={call_cost:.1f}BB. '
        f'Villain check-back={check_back:.0%} (cbet_turn={villain_cbet_turn_pct:.0%}, AF={villain_af:.1f}). '
        f'Float type={f_type}. Probe success={probe_success:.0%}. '
        f'Float EV={ev:+.1f}BB. Decision={action}.'
    )

    verdict = (
        f'[OFA {hero_hand_category.upper()}|{board_texture}|{f_type}] '
        f'{action.upper()} | '
        f'ev={ev:+.1f}BB chk_back={check_back:.0%} probe={probe_success:.0%} | '
        f'call={call_cost:.1f}BB'
    )

    tips = [action_exp]

    if action == 'float':
        tips.append(
            f'OOP FLOAT PLAN: Call {call_cost:.1f}BB. '
            f'If villain checks turn ({check_back:.0%} frequency): fire {probe_success:.0%} fold eq. '
            f'If villain bets turn ({1-check_back:.0%} frequency): '
            f'evaluate equity ({hero_equity:.0%}) vs pot odds to continue.'
        )

    if f_type == 'semi_float':
        tips.append(
            f'SEMI-FLOAT WITH DRAW: You have equity + fold equity. '
            f'Call with {hero_hand_category} and plan to bet when draws complete or when '
            f'villain shows weakness. This is the strongest type of OOP float.'
        )

    if villain_af >= 2.8:
        tips.append(
            f'HIGH AF WARNING (AF={villain_af:.1f}): Villain continues barreling frequently. '
            f'OOP float is high risk -- villain fires again and you are OOP. '
            f'Only float with hands that can withstand a second bet or strong draws.'
        )

    if villain_cbet_turn_pct <= 0.35:
        tips.append(
            f'PASSIVE VILLAIN: Cbet turn only {villain_cbet_turn_pct:.0%}. '
            f'They check back turns frequently ({check_back:.0%}) -- '
            f'ideal for OOP float. Probe aggressively when they check to you.'
        )

    return OOPFloatAdvice(
        hero_hand_category=hero_hand_category,
        board_texture=board_texture,
        street=street,
        cbet_size_pct=cbet_size_pct,
        villain_af=villain_af,
        villain_wtsd=villain_wtsd,
        villain_cbet_turn_pct=villain_cbet_turn_pct,
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        hero_stack_bb=hero_stack_bb,
        villain_check_back_freq=check_back,
        float_type=f_type,
        probe_success_rate=probe_success,
        call_cost_bb=call_cost,
        float_ev=ev,
        action=action,
        action_explanation=action_exp,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ofa_one_liner(r: OOPFloatAdvice) -> str:
    return (
        f'[OFA {r.hero_hand_category.upper()}|{r.board_texture}|{r.float_type}] '
        f'{r.action.upper()} | '
        f'ev={r.float_ev:+.1f}BB chk_back={r.villain_check_back_freq:.0%} | '
        f'probe={r.probe_success_rate:.0%} call={r.call_cost_bb:.1f}BB'
    )
