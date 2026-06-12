"""
Check-Call Line Guide (check_call_line_guide.py)

Guides players on executing the check-call line correctly: when to check-call
(passively call bets without raising), how many streets to check-call, and
when to transition to a different line (raise, fold, or lead).

THEORY:
  CHECK-CALL LINE DEFINITION:
  Check-call = passively calling without leading or raising. Common with:
  1. Medium-strength hands (top pair weak kicker, middle pair with good kicker)
  2. Strong hands building a trap (slowplay)
  3. Bluff-catchers (weak hands calling villain's river bluff)
  4. Draws (paying to complete; equity play)

  WHEN TO CHECK-CALL vs ALTERNATIVES:
  - CHECK-CALL: Medium equity; don't want to face a raise; pot control
  - CHECK-RAISE: Strong hand + draw heavy board + aggressive villain
  - LEAD BET: OOP with value; prevent villain from check-back; probe turn
  - FOLD: Below minimum defense frequency; weak hand vs strong range

  HOW MANY STREETS TO CHECK-CALL:
  - 1 street: Draws or bluff-catchers (commit to fold on next street if miss)
  - 2 streets: Medium-strength hands vs reasonable villain ranges
  - 3 streets: Strong hands trying to trap (set, two pair, strong draws)

  CHECK-CALL vs VILLAIN TYPE:
  - vs Fish: Check-call less (fish check-back too often; better to lead for value)
  - vs LAG: Check-call medium hands (LAG bets wide; your check-call range is
    strong by definition; don't raise into LAG's barreling range)
  - vs Nit: Check-call sparingly (nit bets only with value; check-fold more)

  TRANSITION TRIGGERS:
  When to STOP check-calling and transition:
  - After missing a draw: switch to check-fold
  - After hitting a strong draw: switch to lead or check-raise
  - After multi-street check-call: villain's range narrows to value; reassess
  - If pot gets too large relative to stack: commit or fold

  CHECK-CALL FREQUENCY CALIBRATION:
  MDF = pot/(pot+bet) = minimum frequency to check-call (prevent bet being profitable)
  If villain bets 60% pot: MDF = 62.5%; hero must check-call 62.5% of their range

DISTINCT FROM:
  calldown_advisor.py:        Multi-street calldown planning
  call_threshold.py:          When to call vs fold threshold
  check_call_frequency_guide.py: May exist, but this is LINE-specific
  THIS MODULE:                LINE GUIDANCE; n_streets to check-call; transition
                              triggers; MDF calibration; villain-type adjustments.
"""

from dataclasses import dataclass, field
from typing import List


BASE_CHECK_CALL_STREETS: dict = {
    'nuts':           3,
    'strong_value':   3,
    'two_pair':       3,
    'top_pair_gk':    2,
    'top_pair_wk':    2,
    'overpair':       3,
    'middle_pair':    1,
    'bottom_pair':    0,
    'flush_draw':     1,
    'oesd':           1,
    'combo_draw':     2,
    'bluff_catcher':  1,
    'air':            0,
}

VILLAIN_TYPE_STREETS_ADJUST: dict = {
    'fish':   -1,
    'rec':     0,
    'nit':    -1,
    'lag':    +1,
    'reg':     0,
}

VILLAIN_BET_FRAC: dict = {
    'fish':   0.55,
    'rec':    0.60,
    'nit':    0.65,
    'lag':    0.75,
    'reg':    0.60,
}

HAND_SDV: dict = {
    'nuts':           0.95,
    'strong_value':   0.80,
    'two_pair':       0.78,
    'top_pair_gk':    0.65,
    'top_pair_wk':    0.53,
    'overpair':       0.70,
    'middle_pair':    0.44,
    'bottom_pair':    0.28,
    'flush_draw':     0.15,
    'oesd':           0.12,
    'combo_draw':     0.22,
    'bluff_catcher':  0.30,
    'air':            0.05,
}


def _mdf(bet_frac: float) -> float:
    return round(1.0 / (1.0 + bet_frac), 3)


def _streets_to_call(hand_category: str, villain_type: str, spr: float) -> int:
    base = BASE_CHECK_CALL_STREETS.get(hand_category, 1)
    adj  = VILLAIN_TYPE_STREETS_ADJUST.get(villain_type, 0)
    n = max(0, min(3, base + adj))
    if spr < 2.0 and n > 0:
        n = 1
    return n


def _transition_trigger(
    hand_category: str,
    street: str,
    villain_type: str,
    n_streets_called: int,
) -> str:
    sdv = HAND_SDV.get(hand_category, 0.30)
    if hand_category in ('flush_draw', 'oesd') and street == 'river':
        return 'SWITCH_TO_CHECK_FOLD_MISS'
    if n_streets_called >= 2 and sdv < 0.50:
        return 'REASSESS_RANGE_NARROWED'
    if villain_type == 'nit' and n_streets_called >= 1 and sdv < 0.60:
        return 'SWITCH_TO_CHECK_FOLD_NIT'
    if hand_category in ('nuts', 'strong_value') and n_streets_called >= 2:
        return 'CONSIDER_LEAD_OR_RAISE'
    return 'CONTINUE_CHECK_CALL'


@dataclass
class CheckCallLineResult:
    hand_category: str
    villain_type: str
    street: str
    spr: float

    streets_to_call: int
    mdf: float
    sdv: float
    transition_trigger: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_check_call_line(
    hand_category: str = 'top_pair_gk',
    villain_type: str = 'reg',
    street: str = 'flop',
    spr: float = 5.0,
    pot_bb: float = 20.0,
    n_streets_called: int = 0,
    villain_bet_frac: float = None,
) -> CheckCallLineResult:
    """
    Guide the check-call line: how many streets and when to transition.

    Args:
        hand_category:    Hand strength category
        villain_type:     Villain type ('fish','rec','nit','lag','reg')
        street:           Current street ('flop','turn','river')
        spr:              Stack-to-pot ratio
        pot_bb:           Current pot in BB
        n_streets_called: How many streets have already been check-called
        villain_bet_frac: Villain's bet size as fraction of pot

    Returns:
        CheckCallLineResult
    """
    if villain_bet_frac is None:
        villain_bet_frac = VILLAIN_BET_FRAC.get(villain_type, 0.60)

    streets = _streets_to_call(hand_category, villain_type, spr)
    mdf_val = _mdf(villain_bet_frac)
    sdv     = HAND_SDV.get(hand_category, 0.30)
    trigger = _transition_trigger(hand_category, street, villain_type, n_streets_called)

    verdict = (
        f'[CCL {hand_category}|{villain_type}|{street}] '
        f'streets={streets} MDF={mdf_val:.0%} sdv={sdv:.0%} '
        f'trigger={trigger}'
    )

    reasoning = (
        f'Check-call line: {hand_category} vs {villain_type} on {street}. '
        f'SPR={spr:.1f}; already called {n_streets_called} streets. '
        f'Streets to call={streets}; MDF={mdf_val:.0%}; SDV={sdv:.0%}. '
        f'Transition trigger: {trigger}.'
    )

    tips = []

    tips.append(
        f'CHECK-CALL LINE: {hand_category} on {street} -- call {streets} street(s). '
        f'SDV={sdv:.0%}. '
        f'{"Slowplay -- hands good enough to trap." if sdv >= 0.75 else "Standard check-call -- pot control with medium hand." if sdv >= 0.50 else "Bluff-catch -- calling to catch villain bluffs."}'
    )

    tips.append(
        f'MDF: {mdf_val:.0%} (villain bets {villain_bet_frac:.0%}pot). '
        f'Must check-call at least {mdf_val:.0%} of range to prevent profitable bluffs. '
        f'This hand ({hand_category}, SDV={sdv:.0%}) {"is in the call range." if sdv >= 1-mdf_val else "may be in the fold range -- review."}'
    )

    if trigger != 'CONTINUE_CHECK_CALL':
        tips.append(
            f'TRANSITION: {trigger}. '
            f'{"Miss on river -- check-fold; no SDV." if "MISS" in trigger else "Villain range narrows after 2+ streets -- reassess equity." if "NARROW" in trigger else "Nit always has value -- check-fold marginal hands." if "NIT" in trigger else "Strong hand after 2 streets -- consider leading or raising."}'
        )

    if villain_type == 'lag':
        tips.append(
            f'VS LAG: Add {VILLAIN_TYPE_STREETS_ADJUST["lag"]} extra street to check-call ({streets} total). '
            f'LAG barrels wide; your check-call with medium hands is strong by definition. '
            f'Do not raise into LAG unless you have clear value.'
        )
    elif villain_type == 'nit':
        tips.append(
            f'VS NIT: Reduce streets by {abs(VILLAIN_TYPE_STREETS_ADJUST["nit"])} ({streets} total). '
            f'Nit only bets value; check-call only strong enough hands. '
            f'Check-fold more marginal hands; nit range is very narrow.'
        )

    return CheckCallLineResult(
        hand_category=hand_category,
        villain_type=villain_type,
        street=street,
        spr=spr,
        streets_to_call=streets,
        mdf=mdf_val,
        sdv=sdv,
        transition_trigger=trigger,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def ccl_one_liner(r: CheckCallLineResult) -> str:
    return (
        f'[CCL {r.hand_category}|{r.villain_type}|{r.street}] '
        f'streets={r.streets_to_call} MDF={r.mdf:.0%} sdv={r.sdv:.0%}'
    )
