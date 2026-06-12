"""
Tournament Reshove Advisor (reshove_advisor.py)

When a short stack pushes all-in, should the next player re-jam (reshove)
over them? This is different from:
  - push/fold.py: YOU are the first to push
  - jam_caller.py: You call a jam (no reshove option -- no players behind)
  - icm_advisor.py: General ICM bubble strategy

RESHOVE THEORY:
  RESHOVE = You push all-in over a shorter stack's jam, with players still behind.

  WHY RESHOVE (vs just calling):
  1. Force out the players behind who have not acted yet
  2. Isolate HU vs the original jammer (instead of multiway)
  3. Maximize your fold equity against the players behind
  4. Protect your equity in HU pot vs adding more opponents

  WHY NOT RESHOVE:
  1. Players behind may have strong hands -- reshove runs into AA
  2. ICM: Busting out is more expensive than chip-EV suggests
  3. If you have a medium stack, ICM pressure is high
  4. If players behind are tight/nit, reshove isolates you vs two ranges

  RESHOVE EV FORMULA:
  EV(reshove) = P_fold_all_behind × (P_beat_jammer × pot_won - P_lose × jammer_stack)
              + P_call_behind × EV(3-way_pot)

  KEY INPUTS:
  - Hero stack size vs jammer stack size vs big blind
  - M-ratio of hero and jammer
  - Players behind and their tendencies
  - Hand strength vs jammer's pushing range
  - Bubble distance (ICM pressure)

  RESHOVE HAND REQUIREMENTS:
  vs fish/loose jammer: any top 30% hand
  vs tight jammer:      top 15-20% (jammer's range is strong)
  With players behind:  tighten by 5-10% per tight player behind

  STACK SIZE EFFECTS:
  - Hero is big stack: reshove wider (fold equity from behind players is high)
  - Hero is medium:    reshove medium range (don't endanger tournament life)
  - Hero is short:     may be better to call and play HU vs just reshove

  ICM RESHOVE PREMIUM:
  - At bubble: add 15-25% equity premium requirement (risking tournament life)
  - Final table: add 10-20% premium per payout jump

DISTINCT FROM:
  pushfold.py:            Hero is first to push (no prior shover)
  jam_caller.py:          Calling a jam with no players behind
  preflop_nash_call_advisor.py: Nash equilibrium call (no reshove)
  THIS MODULE:            RESHOVE SPECIFIC; isolate jammer; account for
                          players-behind; ICM reshove premium; HU equity calculation.
"""

from dataclasses import dataclass, field
from typing import List


JAMMER_RANGE_PCT: dict = {
    'fish':             0.55,
    'rec':              0.40,
    'nit':              0.20,
    'lag':              0.60,
    'reg':              0.30,
    'any':              0.45,
}

PLAYER_BEHIND_CALL_PCTS: dict = {
    'fish':   0.35,
    'rec':    0.22,
    'nit':    0.12,
    'lag':    0.28,
    'reg':    0.18,
}

RESHOVE_BASE_RANGE: dict = {
    'big_stack':    0.35,
    'medium_stack': 0.22,
    'short_stack':  0.15,
}

ICM_BUBBLE_PREMIUM: dict = {
    0: 0.26,   # on the bubble = maximum ICM pressure
    1: 0.20,
    2: 0.14,
    3: 0.08,
    5: 0.00,   # 5+ spots from bubble = no ICM adjustment
}


def _stack_category(hero_bb: float, avg_bb: float) -> str:
    ratio = hero_bb / max(avg_bb, 1.0)
    if ratio >= 1.5:
        return 'big_stack'
    elif ratio >= 0.7:
        return 'medium_stack'
    return 'short_stack'


def _jammer_range(jammer_type: str, jammer_bb: float) -> float:
    base = JAMMER_RANGE_PCT.get(jammer_type, 0.40)
    if jammer_bb <= 8:
        return min(0.75, base + 0.20)
    elif jammer_bb <= 12:
        return min(0.60, base + 0.10)
    return base


def _icm_premium(spots_from_bubble: int) -> float:
    """spots_from_bubble=0 = on bubble (max pressure); higher = farther from bubble."""
    keys = sorted(ICM_BUBBLE_PREMIUM.keys())
    for k in reversed(keys):
        if spots_from_bubble >= k:
            return ICM_BUBBLE_PREMIUM[k]
    return 0.0


def _combined_call_pct(players_behind_types: List[str]) -> float:
    no_call = 1.0
    for pt in players_behind_types:
        no_call *= (1.0 - PLAYER_BEHIND_CALL_PCTS.get(pt, 0.20))
    return round(1.0 - no_call, 3)


def _reshove_threshold(
    stack_cat: str,
    jammer_type: str,
    players_behind_types: List[str],
    spots_from_bubble: int,
) -> float:
    base = RESHOVE_BASE_RANGE.get(stack_cat, 0.22)
    icm = _icm_premium(spots_from_bubble)
    behind_pressure = 0.04 * len([t for t in players_behind_types
                                   if t in ('nit', 'reg')])
    return round(min(0.70, base + icm + behind_pressure), 3)


def _reshove_ev(
    pot_bb: float,
    hero_stack_bb: float,
    jammer_stack_bb: float,
    hero_equity_vs_jammer: float,
    combined_call_pct: float,
) -> float:
    fold_equity_pot = pot_bb + jammer_stack_bb
    fold_ev = (1.0 - combined_call_pct) * (
        hero_equity_vs_jammer * (fold_equity_pot + jammer_stack_bb) - jammer_stack_bb
    )
    call_ev = combined_call_pct * (
        hero_equity_vs_jammer * (pot_bb + 2.0 * hero_stack_bb) - hero_stack_bb
    )
    return round(fold_ev + call_ev, 2)


def _reshove_action(
    hero_hand_pct: float,
    threshold: float,
    jammer_bb: float,
    hero_bb: float,
) -> str:
    if hero_hand_pct >= threshold + 0.10:
        return 'RESHOVE'
    if hero_hand_pct >= threshold:
        return 'RESHOVE_BORDERLINE'
    if hero_hand_pct >= threshold - 0.10:
        return 'CALL_HU'
    return 'FOLD'


@dataclass
class ReshoveResult:
    hero_hand_pct: float
    jammer_type: str
    jammer_bb: float
    stack_category: str

    jammer_range_pct: float
    reshove_threshold: float
    icm_premium: float
    combined_call_pct: float
    reshove_ev: float

    recommended_action: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_reshove(
    hero_hand_pct: float = 0.35,
    hero_bb: float = 40.0,
    avg_bb: float = 30.0,
    jammer_type: str = 'rec',
    jammer_bb: float = 12.0,
    players_behind_types: List[str] = None,
    spots_from_bubble: int = 3,
    pot_bb: float = 1.5,
) -> ReshoveResult:
    """
    Analyze whether to reshove all-in over a short stack's jam.

    Args:
        hero_hand_pct:          Hero's hand percentile (0-1; 1=best)
        hero_bb:                Hero's stack in BB
        avg_bb:                 Average stack in BB (for stack category)
        jammer_type:            Short-stack jammer type ('fish','rec','nit','lag','reg')
        jammer_bb:              Jammer's stack in BB
        players_behind_types:   List of player types still to act ['nit','rec'...]
        spots_from_bubble:      How many spots from the money (0 = on bubble)
        pot_bb:                 Current pot in BB (antes+blinds)

    Returns:
        ReshoveResult
    """
    if players_behind_types is None:
        players_behind_types = []

    stack_cat = _stack_category(hero_bb, avg_bb)
    jammer_rng = _jammer_range(jammer_type, jammer_bb)
    icm_prem = _icm_premium(spots_from_bubble)
    call_pct = _combined_call_pct(players_behind_types)
    threshold = _reshove_threshold(
        stack_cat, jammer_type, players_behind_types, spots_from_bubble)

    hero_eq = hero_hand_pct * (1.0 / jammer_rng) if jammer_rng > 0 else 0.50
    hero_eq = max(0.10, min(0.90, hero_eq))

    ev = _reshove_ev(pot_bb, hero_bb, jammer_bb, hero_eq, call_pct)
    action = _reshove_action(hero_hand_pct, threshold, jammer_bb, hero_bb)

    verdict = (
        f'[RSH hand={hero_hand_pct:.0%}|{jammer_type}({jammer_bb:.0f}BB)|'
        f'{stack_cat}] '
        f'{action} threshold={threshold:.0%} icm_prem={icm_prem:.0%} '
        f'EV={ev:+.1f}BB call_risk={call_pct:.0%}'
    )

    reasoning = (
        f'Reshove analysis: hero={hero_bb:.0f}BB ({stack_cat}) vs '
        f'{jammer_type} jammer ({jammer_bb:.0f}BB). '
        f'Jammer range={jammer_rng:.0%}; hero equity={hero_eq:.0%}. '
        f'ICM premium={icm_prem:.0%}; call risk behind={call_pct:.0%}. '
        f'Reshove threshold={threshold:.0%} vs hero hand={hero_hand_pct:.0%}. '
        f'Action: {action}. EV={ev:+.1f}BB.'
    )

    tips = []

    tips.append(
        f'RESHOVE DECISION: Hand={hero_hand_pct:.0%} vs threshold={threshold:.0%} '
        f'({stack_cat}, {spots_from_bubble} spots from bubble). '
        f'{"RESHOVE -- hand above threshold." if hero_hand_pct >= threshold else "FOLD or CALL -- below reshove threshold."}'
    )

    tips.append(
        f'JAMMER RANGE: {jammer_type} jammer ({jammer_bb:.0f}BB) pushes ~{jammer_rng:.0%} of hands. '
        f'Your hero equity vs their range = {hero_eq:.0%}. '
        f'{"Tight jammer -- need strong hand to reshove." if jammer_rng < 0.30 else "Wide jammer -- can reshove wider range."}'
    )

    if icm_prem > 0:
        tips.append(
            f'ICM PRESSURE: {spots_from_bubble} spots from bubble adds {icm_prem:.0%} equity premium. '
            f'Need {icm_prem:.0%} MORE equity than chip-EV suggests. '
            f'{"Near bubble -- tighten reshove range significantly." if icm_prem >= 0.20 else "Moderate ICM pressure -- tighten slightly."}'
        )
    else:
        tips.append(
            f'ICM PRESSURE: No bubble pressure (in money or far from bubble). '
            f'Reshove based on chip-EV alone. '
            f'Be more aggressive -- no payout cliff to protect.'
        )

    if call_pct >= 0.20:
        tips.append(
            f'PLAYERS BEHIND: {len(players_behind_types)} player(s) behind with '
            f'{call_pct:.0%} combined call probability. '
            f'High call risk -- tighten reshove range or avoid with marginal hands.'
        )
    elif players_behind_types:
        tips.append(
            f'PLAYERS BEHIND: {len(players_behind_types)} player(s) behind with only {call_pct:.0%} call risk. '
            f'Low interference -- reshove with standard range. '
            f'Fold equity from behind players is high.'
        )

    return ReshoveResult(
        hero_hand_pct=hero_hand_pct,
        jammer_type=jammer_type,
        jammer_bb=jammer_bb,
        stack_category=stack_cat,
        jammer_range_pct=jammer_rng,
        reshove_threshold=threshold,
        icm_premium=icm_prem,
        combined_call_pct=call_pct,
        reshove_ev=ev,
        recommended_action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def reshove_one_liner(r: ReshoveResult) -> str:
    return (
        f'[RSH {r.hero_hand_pct:.0%}|{r.jammer_type}({r.jammer_bb:.0f}BB)] '
        f'{r.recommended_action} threshold={r.reshove_threshold:.0%} '
        f'icm={r.icm_premium:.0%} EV={r.reshove_ev:+.1f}BB'
    )
