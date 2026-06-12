"""
Thin Value vs Calling Station (thin_value_vs_calling_station.py)

Against calling stations (players who call too wide), extract maximum EV by:
1. Betting more streets with thin value hands
2. Sizing up on all streets (they call regardless of size)
3. Reducing bluffs (bluffs are -EV vs players who don't fold)
4. Identifying which marginal hands become value bets vs their calling range

THEORY:
  CALLING STATION PROFILE:
  - Calling range: any pair, any draw, any backdoor, any gut-shot, etc.
  - Average calling hand strength: medium (one pair, weak two-pair)
  - They rarely fold to any bet size on any street
  - Fold frequency: ~20-30% vs half-pot; ~35-40% vs full-pot

  THIN VALUE vs CALLING STATION:
  - Hands that BEAT their calling range -> value bet all streets
  - Hands that LOSE to their calling range -> check or fold
  - THIN VALUE = hands that beat >50% of their calling range

  VALUE BET SIZING:
  - Size UP vs calling station: they call full pot same as 1/2 pot
  - Optimal: 60-80% pot (enough to extract; not so big they fold their draws)
  - On river: can overbet with nut hands (they call anything)

  BLUFF FREQUENCY vs CALLING STATION:
  - Reduce bluffs to near ZERO (they call too much; bluffs are -EV)
  - Only bluff when you have very strong blockers + villain is OOP with specific weakness

  STREET EXTENSION:
  - Standard value: 2-street (flop + turn or turn + river)
  - vs calling station: extend to 3-street value more often
  - Hands like top pair decent kicker -> thin 3-street value

  EV CALCULATION:
  ev_per_street = (hero_equity - villain_call_pct * call_range_equity_against_hero)
                  * bet_size * streets

DISTINCT FROM:
  calling_station_exploiter.py:  General calling station exploit
  villain_exploitability_scorer.py: Villain scoring
  value_bet_threshold_calculator.py: General value bet threshold
  THIS MODULE:                   THIN VALUE specific; street-extension decisions;
                                 sizing optimization; bluff reduction; EV per street.
"""

from dataclasses import dataclass, field
from typing import List


CALLING_STATION_FOLD: dict = {
    0.25: 0.15,
    0.50: 0.22,
    0.75: 0.32,
    1.00: 0.38,
    1.50: 0.45,
}

THIN_VALUE_THRESHOLD: dict = {
    'calling_station': 0.52,  # beats 52% of their range
    'rec':             0.55,
    'fish':            0.53,
    'nit':             0.60,
    'lag':             0.58,
}

STREET_VALUE_HANDS: dict = {
    'nuts':             3,
    'strong_value':     3,
    'top_pair_gk':      3,
    'top_pair_wk':      2,
    'overpair':         3,
    'two_pair':         3,
    'middle_pair':      1,
    'bottom_pair':      0,
    'air':              0,
}

OPTIMAL_SIZING_VS_STATION: dict = {
    'flop':  0.65,
    'turn':  0.70,
    'river': 0.80,
}


def _villain_fold_vs_station(bet_frac: float) -> float:
    sizes = sorted(CALLING_STATION_FOLD.keys())
    closest = min(sizes, key=lambda s: abs(s - bet_frac))
    return CALLING_STATION_FOLD[closest]


def _thin_value_threshold(villain_type: str) -> float:
    return THIN_VALUE_THRESHOLD.get(villain_type, 0.54)


def _recommended_streets(hand_strength: str, villain_type: str) -> int:
    base = STREET_VALUE_HANDS.get(hand_strength, 1)
    if villain_type in ('calling_station', 'fish', 'rec'):
        return min(3, base + 1)
    return base


def _ev_per_street(
    pot_bb: float,
    bet_frac: float,
    hero_equity: float,
    villain_fold: float,
) -> float:
    bet_bb = pot_bb * bet_frac
    fold_ev = villain_fold * pot_bb
    call_ev = (1.0 - villain_fold) * (hero_equity * (pot_bb + 2.0 * bet_bb) - bet_bb)
    return round(fold_ev + call_ev, 2)


def _sizing_recommendation(villain_type: str, street: str, hand_strength: str) -> float:
    base = OPTIMAL_SIZING_VS_STATION.get(street, 0.70)
    if villain_type in ('calling_station',):
        base = min(0.90, base + 0.10)  # push even larger vs stations
    if hand_strength in ('middle_pair', 'bottom_pair'):
        base = max(0.40, base - 0.20)  # smaller with thin value
    return round(base, 2)


def _bluff_recommendation(villain_type: str) -> str:
    if villain_type in ('calling_station', 'fish'):
        return 'NO_BLUFFS'
    elif villain_type == 'rec':
        return 'MINIMAL_BLUFFS'
    return 'STANDARD_BLUFFS'


@dataclass
class ThinValueStationResult:
    villain_type: str
    hand_strength: str
    street: str

    hero_equity: float
    thin_value_threshold: float
    is_thin_value: bool

    recommended_streets: int
    optimal_sizing_frac: float
    ev_per_street_bb: float
    bluff_recommendation: str

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_thin_value_vs_station(
    villain_type: str = 'calling_station',
    hand_strength: str = 'top_pair_wk',
    street: str = 'flop',
    pot_bb: float = 20.0,
    hero_equity: float = 0.60,
) -> ThinValueStationResult:
    """
    Analyze thin value betting strategy vs calling stations.

    Args:
        villain_type:   Villain profile ('calling_station','fish','rec','nit','lag')
        hand_strength:  Hero hand ('nuts','strong_value','top_pair_gk','top_pair_wk',
                        'overpair','two_pair','middle_pair','air')
        street:         Current street ('flop','turn','river')
        pot_bb:         Pot size in BB
        hero_equity:    Hero's equity vs villain's calling range

    Returns:
        ThinValueStationResult
    """
    threshold = _thin_value_threshold(villain_type)
    is_thin = hero_equity >= threshold
    streets = _recommended_streets(hand_strength, villain_type)
    size = _sizing_recommendation(villain_type, street, hand_strength)
    fold_pct = _villain_fold_vs_station(size)
    ev = _ev_per_street(pot_bb, size, hero_equity, fold_pct)
    bluff_rec = _bluff_recommendation(villain_type)

    if not is_thin and hand_strength in ('air', 'bottom_pair'):
        action = 'CHECK_GIVE_UP'
    elif not is_thin:
        action = 'CHECK_SHOWDOWN'
    elif streets >= 3 and is_thin:
        action = 'VALUE_BET_3_STREETS'
    elif streets >= 2:
        action = 'VALUE_BET_2_STREETS'
    else:
        action = 'VALUE_BET_1_STREET'

    verdict = (
        f'[TVS {hand_strength}|{villain_type}|{street}] '
        f'{action} size={size:.0%}pot EV={ev:+.1f}BB/street '
        f'{streets}-streets thin_val={is_thin}'
    )

    reasoning = (
        f'Thin value vs {villain_type}: {hand_strength} on {street}. '
        f'Hero equity={hero_equity:.0%} vs threshold={threshold:.0%}. '
        f'Is thin value: {is_thin}. '
        f'Recommended {streets} streets at {size:.0%}pot. '
        f'EV/street={ev:+.1f}BB. Bluffs: {bluff_rec}.'
    )

    tips = []

    tips.append(
        f'THIN VALUE THRESHOLD: {hero_equity:.0%} equity vs {threshold:.0%} threshold for {villain_type}. '
        f'{"THIN VALUE -- bet all {0} streets.".format(streets) if is_thin else "NOT thin value -- check; hero equity insufficient."}'
    )

    tips.append(
        f'SIZING vs {villain_type.upper()}: {size:.0%} pot ({round(pot_bb*size,1):.1f}BB). '
        f'Villain folds only {fold_pct:.0%} -- most calling. '
        f'{"Size up; they call regardless." if villain_type == "calling_station" else "Standard sizing applies."}'
    )

    tips.append(f'BLUFF POLICY: {bluff_rec}. '
        f'{"Eliminate bluffs -- station calls too much; bluffs are -EV." if bluff_rec == "NO_BLUFFS" else "Minimal bluffs only with strong blockers." if bluff_rec == "MINIMAL_BLUFFS" else "Standard bluff frequency."}'
    )

    if is_thin and streets == 3:
        tips.append(
            f'3-STREET VALUE: {hand_strength} qualifies for 3 streets vs {villain_type}. '
            f'Bet flop, turn, and river for value. '
            f'Total EV gain ~{ev*3:+.1f}BB vs checking all streets.'
        )

    return ThinValueStationResult(
        villain_type=villain_type,
        hand_strength=hand_strength,
        street=street,
        hero_equity=hero_equity,
        thin_value_threshold=threshold,
        is_thin_value=is_thin,
        recommended_streets=streets,
        optimal_sizing_frac=size,
        ev_per_street_bb=ev,
        bluff_recommendation=bluff_rec,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tvs_one_liner(r: ThinValueStationResult) -> str:
    return (
        f'[TVS {r.hand_strength}|{r.villain_type}] '
        f'{r.recommended_action} {r.optimal_sizing_frac:.0%}pot '
        f'EV={r.ev_per_street_bb:+.1f}BB/street {r.recommended_streets}-streets'
    )
