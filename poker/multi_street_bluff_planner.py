"""
Multi-Street Bluff Planner (multi_street_bluff_planner.py)

Plans bluffs across multiple streets: which street to start, how many barrels
to fire, when to give up, and how semi-bluffs differ from pure bluffs.

MULTI-STREET BLUFF THEORY:
  A multi-street bluff has multiple components:
  1. Initial bluff bet (flop or turn)
  2. Continuation (turn barrel)
  3. River completion (third barrel)

  SEMI-BLUFF vs PURE BLUFF:
  Semi-bluff: Has equity when called (draws, backdoors). Gets money in with 2 outs.
    Best semi-bluffs: flush draws (9 outs ~35%), OESD (8 outs ~32%)
    EV = fold_equity * pot + (1-fold_eq) * pot * equity
    Even with 0 fold equity, if equity > 35%, semi-bluff has positive EV
  Pure bluff: Zero equity when called. Must rely entirely on fold equity.
    Only profitable when: fold_equity > bet / (pot + bet)

  THREE-STREET COMMITMENT MATH:
  If you bet 2/3 pot on all three streets, by river:
    Pot grew: flop: 1 -> 7/3; turn: 7/3 -> 49/9; river: 49/9 -> 343/27 ~ 12.7x
  You risked: 2/3 + (2/3)(7/3) + (2/3)(49/9) = 0.67 + 1.56 + 3.63 = 5.85 pot
  Villain must fold on at least one street to make it profitable.

  GIVE-UP CONDITIONS:
  1. Turn card improved villain's range (flush/straight completes): give up unless you hit
  2. Villain check-raised flop: likely strong; stop bluffing
  3. SPR < 2 after third bet: odds too short to fold out equity
  4. Villain is passive (AF < 1.5) but hasn't folded: they have it; give up

  STREET SELECTION:
  Best bluffing street: flop (villain hasn't seen any cards; widest range)
  Turn barrel: effective when: (a) scare card hits, (b) board pairs (hits aggressor range)
  River barrel: only when equity + fold_equity justifies it; most expensive

  BLUFF SELECTION:
  Best bluff hands:
    Ace-high with backdoor draw: blockers + equity
    Flush draw missed on turn: fire as bluff (use draw for fold equity on flop)
    Gut-shot with overcards: 7 clean outs when called; semi-bluff

DISTINCT FROM:
  bluff_planner.py:         Single-street bluff analysis
  barrel.py:                Barrel decision (one street at a time)
  bluff_selection_advisor.py: Which hand to bluff with (single street)
  THIS MODULE:              MULTI-STREET plan: starting street, barrel count,
                            cumulative EV, give-up triggers, pure vs semi.

Usage:
    from poker.multi_street_bluff_planner import plan_multi_street_bluff, MultiStreetBluffPlan, msbp_one_liner

    result = plan_multi_street_bluff(
        hero_hand_category='flush_draw',
        starting_street='flop',
        pot_bb=20.0,
        stack_bb=80.0,
        board_texture='wet',
        villain_fold_to_cbet=0.45,
        villain_fold_to_turn_barrel=0.38,
        villain_fold_to_river_barrel=0.42,
        villain_af=2.0,
        hero_equity=0.34,
    )
    print(msbp_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Semi-bluff equity estimates
HAND_EQUITY = {
    'flush_draw':       0.34,
    'oesd':             0.32,
    'combo_draw':       0.50,
    'gutshot':          0.16,
    'backdoor_flush':   0.08,
    'overcards':        0.18,
    'air':              0.02,
    'missed_draw':      0.04,
    'top_pair_weak':    0.65,
    'middle_pair':      0.50,
    'bluff_catcher':    0.40,
}

# Recommended bluff bet size (fraction of pot) by street
BLUFF_SIZE_BY_STREET = {
    'flop':  0.55,
    'turn':  0.65,
    'river': 0.75,
}

# Minimum fold equity for pure bluff profitability by street
MIN_FOLD_EQUITY = {
    'flop':  0.35,
    'turn':  0.40,
    'river': 0.45,
}


def _is_semi_bluff(hand_category: str, equity: float) -> bool:
    return equity >= 0.15 and hand_category not in ('air', 'missed_draw')


def _fold_equity_ev(pot_bb: float, bet_pct: float, fold_rate: float) -> float:
    """EV gain from fold equity alone."""
    return fold_rate * pot_bb


def _equity_ev_if_called(pot_bb: float, bet_pct: float, hero_equity: float) -> float:
    """EV from equity when villain calls."""
    bet_bb = pot_bb * bet_pct
    return hero_equity * (pot_bb + 2 * bet_bb) - bet_bb


def _bluff_ev_one_street(
    pot_bb: float,
    bet_pct: float,
    fold_rate: float,
    hero_equity: float,
) -> float:
    """EV of one street bluff."""
    bet_bb = pot_bb * bet_pct
    fold_ev = fold_rate * pot_bb
    call_ev = (1 - fold_rate) * (hero_equity * (pot_bb + 2 * bet_bb) - bet_bb)
    return round(fold_ev + call_ev, 2)


def _should_fire_barrel(
    street: str,
    fold_rate: float,
    hero_equity: float,
    pot_bb: float,
) -> bool:
    bet_pct = BLUFF_SIZE_BY_STREET.get(street, 0.65)
    ev = _bluff_ev_one_street(pot_bb, bet_pct, fold_rate, hero_equity)
    return ev > 0


def _planned_barrel_count(
    hero_hand_category: str,
    hero_equity: float,
    fold_rates: dict,
    board_texture: str,
) -> int:
    """How many streets to plan to barrel."""
    is_semi = _is_semi_bluff(hero_hand_category, hero_equity)
    if hero_hand_category == 'combo_draw':
        return 3   # maximum aggression with combo draws
    if is_semi and fold_rates.get('flop', 0) >= 0.45:
        if fold_rates.get('turn', 0) >= 0.38:
            return 3 if fold_rates.get('river', 0) >= 0.40 else 2
        return 2
    if is_semi:
        return 2   # fire flop + turn; give up river unless completed
    if not is_semi and fold_rates.get('flop', 0) >= MIN_FOLD_EQUITY['flop']:
        return 1   # pure bluff: one street only
    return 0   # don't bluff


def _give_up_triggers(
    board_texture: str,
    villain_af: float,
) -> List[str]:
    triggers = []
    if board_texture == 'wet':
        triggers.append('flush/straight completes on turn or river: give up')
    if villain_af < 1.5:
        triggers.append('passive villain calls without raising: they have it; stop')
    triggers.append('villain check-raises any street: fold immediately')
    if board_texture == 'dry':
        triggers.append('villain calls flop and turn: rarely bluffing; stop river')
    return triggers


def _cumulative_ev(
    pot_bb: float,
    barrel_count: int,
    fold_rates: dict,
    hero_equity: float,
) -> float:
    """Rough EV of planned multi-street bluff."""
    total_ev = 0.0
    current_pot = pot_bb
    streets = ['flop', 'turn', 'river'][:barrel_count]
    for street in streets:
        fold = fold_rates.get(street, 0.40)
        bet_pct = BLUFF_SIZE_BY_STREET[street]
        ev = _bluff_ev_one_street(current_pot, bet_pct, fold, hero_equity)
        total_ev += ev * (1 - sum(fold_rates.get(s, 0.40) for s in streets[:streets.index(street)]) / max(1, streets.index(street)))
        current_pot = current_pot * (1 + 2 * bet_pct) * (1 - fold)
    return round(total_ev, 2)


@dataclass
class MultiStreetBluffPlan:
    # Inputs
    hero_hand_category: str
    starting_street: str
    pot_bb: float
    stack_bb: float
    board_texture: str
    villain_fold_to_cbet: float
    villain_fold_to_turn_barrel: float
    villain_fold_to_river_barrel: float
    villain_af: float
    hero_equity: float

    # Analysis
    is_semi_bluff: bool
    planned_barrel_count: int    # 0 = don't bluff; 1-3 = planned barrels
    flop_bluff_ev: float
    cumulative_ev: float
    give_up_triggers: List[str]
    bluff_type: str              # 'pure' / 'semi_bluff' / 'no_bluff'

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def plan_multi_street_bluff(
    hero_hand_category: str = 'flush_draw',
    starting_street: str = 'flop',
    pot_bb: float = 20.0,
    stack_bb: float = 80.0,
    board_texture: str = 'wet',
    villain_fold_to_cbet: float = 0.45,
    villain_fold_to_turn_barrel: float = 0.38,
    villain_fold_to_river_barrel: float = 0.42,
    villain_af: float = 2.0,
    hero_equity: float = 0.34,
) -> MultiStreetBluffPlan:
    """
    Plan a multi-street bluff including barrel count and EV.

    Args:
        hero_hand_category:           Hand category
        starting_street:              First street of bluff
        pot_bb:                       Current pot in BB
        stack_bb:                     Effective stack
        board_texture:                Board texture
        villain_fold_to_cbet:         Villain fold rate on flop
        villain_fold_to_turn_barrel:  Villain fold rate on turn
        villain_fold_to_river_barrel: Villain fold rate on river
        villain_af:                   Villain aggression factor
        hero_equity:                  Hero's equity when called

    Returns:
        MultiStreetBluffPlan
    """
    equity = HAND_EQUITY.get(hero_hand_category, hero_equity)
    is_semi = _is_semi_bluff(hero_hand_category, equity)

    fold_rates = {
        'flop':  villain_fold_to_cbet,
        'turn':  villain_fold_to_turn_barrel,
        'river': villain_fold_to_river_barrel,
    }

    barrels = _planned_barrel_count(hero_hand_category, equity, fold_rates, board_texture)
    flop_ev = _bluff_ev_one_street(pot_bb, BLUFF_SIZE_BY_STREET['flop'],
                                    villain_fold_to_cbet, equity)
    cumul_ev = _cumulative_ev(pot_bb, barrels, fold_rates, equity)
    triggers = _give_up_triggers(board_texture, villain_af)
    bluff_type = 'semi_bluff' if is_semi else ('pure' if barrels > 0 else 'no_bluff')

    if barrels == 0:
        action = 'DO_NOT_BLUFF'
    elif barrels == 1:
        action = f'BLUFF_{starting_street.upper()}_ONLY'
    elif barrels == 2:
        action = 'DOUBLE_BARREL_PLAN'
    else:
        action = 'TRIPLE_BARREL_PLAN'

    verdict = (
        f'[MSBP {hero_hand_category}|{starting_street}] '
        f'{action} barrels={barrels} '
        f'ev={cumul_ev:+.1f}BB type={bluff_type}'
    )

    reasoning = (
        f'Multi-street bluff plan: {hero_hand_category} ({bluff_type}) from {starting_street}. '
        f'Equity={equity:.0%}. '
        f'Fold rates: flop={villain_fold_to_cbet:.0%}, turn={villain_fold_to_turn_barrel:.0%}, '
        f'river={villain_fold_to_river_barrel:.0%}. '
        f'Planned barrels: {barrels}. '
        f'Flop EV: {flop_ev:+.1f}BB. Cumulative EV: {cumul_ev:+.1f}BB. '
        f'Give-up triggers: {len(triggers)} conditions.'
    )

    tips = []

    tips.append(
        f'BLUFF TYPE: {bluff_type.upper()}. '
        f'{hero_hand_category} has {equity:.0%} equity when called. '
        f'{"Semi-bluff: profitable even with some call because equity carries." if is_semi else "Pure bluff: need fold equity only -- very risky if called."} '
        f'Planned: {barrels} barrel(s).'
    )

    if barrels >= 1:
        flop_size = BLUFF_SIZE_BY_STREET['flop']
        flop_bet = pot_bb * flop_size
        tips.append(
            f'STREET PLAN: '
            f'Flop: bet {flop_size:.0%}pot ({flop_bet:.1f}BB). '
            f'{"Turn: continue if blank; give up if draw completes." if barrels >= 2 else "Turn: CHECK and give up."} '
            f'{"River: barrel if turn scare card improves your range." if barrels >= 3 else ""}'
        )

    if barrels == 0:
        tips.append(
            f'DO NOT BLUFF: Conditions not met. '
            f'Fold equity ({villain_fold_to_cbet:.0%}) too low for pure bluff '
            f'and equity ({equity:.0%}) too low for semi-bluff. '
            f'Check and realize equity instead. '
            f'Reconsider if turn or river card improves your hand.'
        )

    tips.append(
        f'GIVE-UP TRIGGERS: '
        + '; '.join(f'({i+1}) {t}' for i, t in enumerate(triggers[:3]))
    )

    if is_semi and barrels >= 2:
        tips.append(
            f'SEMI-BLUFF EXECUTION: '
            f'Fire flop and turn. On river: '
            f'If draw completes → check (showdown value). '
            f'If draw misses → barrel only if: (a) scare card hits board, (b) equity still positive. '
            f'Never fire river as pure bluff with {hero_hand_category} missed.'
        )

    return MultiStreetBluffPlan(
        hero_hand_category=hero_hand_category,
        starting_street=starting_street,
        pot_bb=pot_bb,
        stack_bb=stack_bb,
        board_texture=board_texture,
        villain_fold_to_cbet=villain_fold_to_cbet,
        villain_fold_to_turn_barrel=villain_fold_to_turn_barrel,
        villain_fold_to_river_barrel=villain_fold_to_river_barrel,
        villain_af=villain_af,
        hero_equity=equity,
        is_semi_bluff=is_semi,
        planned_barrel_count=barrels,
        flop_bluff_ev=flop_ev,
        cumulative_ev=cumul_ev,
        give_up_triggers=triggers,
        bluff_type=bluff_type,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def msbp_one_liner(r: MultiStreetBluffPlan) -> str:
    action = (
        'NO_BLUFF' if r.planned_barrel_count == 0
        else f'{r.planned_barrel_count}BARREL_{r.bluff_type.upper()}'
    )
    return (
        f'[MSBP {r.hero_hand_category}|{r.starting_street}] '
        f'{action} ev={r.cumulative_ev:+.1f}BB | eq={r.hero_equity:.0%}'
    )
