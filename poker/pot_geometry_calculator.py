"""
Pot Geometry Calculator (pot_geometry_calculator.py)

Computes GEOMETRIC POT SIZING for multi-street commitment planning.
The goal: size bets across streets so that the river jam uses exactly
the remaining stack, maximizing pressure while keeping consistent sizing.

THEORY:
  GEOMETRIC SIZING ensures the bet-to-pot ratio stays consistent across
  streets, building to a river jam with no wasted/awkward remaining stack.

  THREE-STREET GEOMETRIC SIZE:
  Given pot P and effective stack S, find x (bet as fraction of pot) such
  that after three bets of x*pot, the stack is fully committed:

  After flop:   pot = P*(1+2x),  stack remaining = S - x*P
  After turn:   pot = P*(1+2x)^2, stack remaining = S - x*P - x*P*(1+2x)
  After river:  jam remaining stack = S - x*P*(1+2x+1) = ... (simplified)

  SIMPLIFIED FORMULA:
  For each street starting from pot P and effective stack S:
    geometric_size_frac = 1 - (P / (P + S))^(1/n_streets)
    where n_streets = number of streets remaining

  This ensures the pot grows by the same factor each street.

  WORKED EXAMPLE:
  Pot = 20BB, Stack = 80BB (SPR = 4)
  3 streets remaining:
    factor = (20/(20+80))^(1/3) = (0.20)^(0.333) = 0.585
    bet_frac = 1 - 0.585 = 0.415 (each street ~41% of pot)
    Flop bet: 0.415*20 = 8.3BB  (pot grows to 20+2*8.3=36.6)
    Turn bet: 0.415*36.6 = 15.2BB (pot grows to 36.6+30.4=67)
    River bet: remaining stack ~80-8.3-15.2=56.5BB (jams ~56.5)

  POT ODDS AT EACH STREET:
  The villain gets the same pot odds at each decision point when you
  use geometric sizing. This is maximally exploitative because villain
  cannot "wait" for a better price on a later street.

  ADJUSTMENTS:
  - Want to commit by turn (2 streets): recalculate for n=2
  - Want to keep small and jam river: use small flop/turn then overbet river
  - Against short stacks: reduce to n=1 or n=2 based on SPR

DISTINCT FROM:
  bet_sizing_ev.py:         EV of different bet sizes
  street_planning.py:       Multi-street action planning
  THIS MODULE:              GEOMETRIC SIZES specifically; consistent factor;
                            stack commitment math; SPR at each decision point.
"""

from dataclasses import dataclass, field
from typing import List


def _geometric_factor(pot: float, stack: float, n_streets: int) -> float:
    """Multiplier for pot at each street to commit stack over n streets."""
    if n_streets <= 0 or stack <= 0 or pot <= 0:
        return 1.0
    return round((pot / (pot + stack)) ** (1.0 / n_streets), 4)


def _geometric_bet_frac(pot: float, stack: float, n_streets: int) -> float:
    factor = _geometric_factor(pot, stack, n_streets)
    return round(1.0 - factor, 4)


def _spr(stack: float, pot: float) -> float:
    return round(stack / pot, 2) if pot > 0 else 99.0


def _plan_streets(pot_bb: float, stack_bb: float, n_streets: int) -> list:
    """Return list of (bet_frac, bet_bb, pot_after) for each street."""
    plan = []
    current_pot = pot_bb
    current_stack = stack_bb
    for i in range(n_streets):
        remaining_streets = n_streets - i
        if current_stack <= 0:
            plan.append((0.0, 0.0, current_pot))
            continue
        if remaining_streets == 1:
            bet_bb = min(current_stack, current_stack)  # jam all-in
            bet_frac = round(bet_bb / current_pot, 3)
        else:
            bet_frac = _geometric_bet_frac(current_pot, current_stack, remaining_streets)
            bet_bb = round(current_pot * bet_frac, 1)
            bet_bb = min(bet_bb, current_stack)

        pot_after = round(current_pot + 2 * bet_bb, 1)
        plan.append((round(bet_frac, 3), bet_bb, pot_after))
        current_stack -= bet_bb
        current_pot = pot_after
    return plan


@dataclass
class PotGeometryResult:
    pot_bb: float
    effective_stack_bb: float
    spr: float
    n_streets: int

    geometric_factor: float
    flop_bet_frac: float
    flop_bet_bb: float
    turn_bet_frac: float
    turn_bet_bb: float
    river_bet_frac: float
    river_bet_bb: float

    street_plan: list  # [(bet_frac, bet_bb, pot_after), ...]

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def calculate_pot_geometry(
    pot_bb: float = 20.0,
    effective_stack_bb: float = 80.0,
    n_streets: int = 3,
    street: str = 'flop',
) -> PotGeometryResult:
    """
    Calculate geometric bet sizes for committing stack over n streets.

    Args:
        pot_bb:             Current pot in BB
        effective_stack_bb: Effective stack (smaller of hero/villain) in BB
        n_streets:          Number of streets remaining (1, 2, or 3)
        street:             Current street ('flop', 'turn', 'river')

    Returns:
        PotGeometryResult with optimal geometric sizes for each street
    """
    spr = _spr(effective_stack_bb, pot_bb)
    factor = _geometric_factor(pot_bb, effective_stack_bb, n_streets)
    plan = _plan_streets(pot_bb, effective_stack_bb, n_streets)

    def _get_plan(idx, key_idx):
        if idx < len(plan):
            return plan[idx][key_idx]
        return 0.0

    flop_frac  = _get_plan(0, 0)
    flop_bb    = _get_plan(0, 1)
    turn_frac  = _get_plan(1, 0)
    turn_bb    = _get_plan(1, 1)
    river_frac = _get_plan(2, 0)
    river_bb   = _get_plan(2, 1)

    streets_label = {1: 'river-jam', 2: 'turn+river', 3: 'flop+turn+river'}
    plan_type = streets_label.get(n_streets, f'{n_streets}-street')

    verdict = (
        f'[PGC pot={pot_bb:.0f}BB stack={effective_stack_bb:.0f}BB SPR={spr:.1f}] '
        f'{plan_type}: factor={factor:.3f} '
        f'Flop:{flop_frac:.0%} Turn:{turn_frac:.0%} River:jam'
    )

    reasoning = (
        f'Pot geometry: pot={pot_bb:.0f}BB, effective_stack={effective_stack_bb:.0f}BB. '
        f'SPR={spr:.1f}. {n_streets} streets to commit. '
        f'Geometric factor={factor:.3f}. '
        f'Consistent {1-factor:.0%}pot bets per street.'
    )

    tips = []

    tips.append(
        f'GEOMETRIC PLAN ({n_streets} streets): '
        + ', '.join(f'Street{i+1}: {p[0]:.0%}pot={p[1]:.1f}BB' for i, p in enumerate(plan))
        + f'. Stack committed after {n_streets} bets.'
    )

    if spr <= 2.0:
        tips.append(
            f'LOW SPR ({spr:.1f}): Jam or near-jam is correct on {street}. '
            f'No need for multi-street planning; commit immediately.'
        )
    elif spr <= 5.0:
        tips.append(
            f'MEDIUM SPR ({spr:.1f}): 2-street commitment is clean. '
            f'Bet {flop_frac:.0%}pot flop ({flop_bb:.1f}BB), '
            f'jam turn with {turn_bb:.1f}BB remaining stack.'
        )
    else:
        tips.append(
            f'HIGH SPR ({spr:.1f}): 3-street plan needed. '
            f'Bet {flop_frac:.0%}pot on each street. '
            f'Villain gets same pot odds every street -- cannot "wait" for a better price.'
        )

    if flop_frac > 0:
        tips.append(
            f'FLOP BET: {flop_frac:.0%}pot = {flop_bb:.1f}BB. '
            f'After call: pot = {_get_plan(0, 2):.1f}BB, '
            f'remaining stack ~{effective_stack_bb - flop_bb:.1f}BB.'
        )

    if n_streets >= 2 and turn_frac > 0:
        tips.append(
            f'TURN BET: {turn_frac:.0%}pot = {turn_bb:.1f}BB. '
            f'After call: pot = {_get_plan(1, 2):.1f}BB, '
            f'commit river with ~{effective_stack_bb - flop_bb - turn_bb:.1f}BB jam.'
        )

    return PotGeometryResult(
        pot_bb=pot_bb,
        effective_stack_bb=effective_stack_bb,
        spr=spr,
        n_streets=n_streets,
        geometric_factor=factor,
        flop_bet_frac=flop_frac,
        flop_bet_bb=flop_bb,
        turn_bet_frac=turn_frac,
        turn_bet_bb=turn_bb,
        river_bet_frac=river_frac,
        river_bet_bb=river_bb,
        street_plan=plan,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pgc_one_liner(r: PotGeometryResult) -> str:
    return (
        f'[PGC SPR={r.spr:.1f} {r.n_streets}streets] '
        f'factor={r.geometric_factor:.3f} '
        f'F:{r.flop_bet_frac:.0%}pot={r.flop_bet_bb:.1f}BB '
        f'T:{r.turn_bet_frac:.0%}pot={r.turn_bet_bb:.1f}BB '
        f'R:jam'
    )
