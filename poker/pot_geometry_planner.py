"""
Pot Geometry Planner (pot_geometry_planner.py)

Calculates optimal multi-street bet sizes to get stacks committed by a target street.
"Pot geometry" is the art of sizing each street's bet so that the pot grows naturally
into the remaining stack by the river, enabling clean value extraction.

POT GEOMETRY THEORY:
  Goal: commit stacks on the street that maximizes EV for your hand strength.
  Strong hands (sets, flushes): commit by turn or river
  Vulnerable hands (overpairs): commit by flop or turn to deny equity
  Speculative hands (draws): don't commit until completing

  SPR COMMITMENT GUIDE:
    SPR < 2:   Commit now (flop or preflop jam). Any strong hand is auto-commit.
    SPR 2-4:   Commit by flop/turn. Bet 55-65% flop -> 75-90% turn.
    SPR 4-8:   Commit by turn/river. Bet 33-45% flop -> 55-70% turn -> shove river.
    SPR 8-15:  Commit by river only. Bet 25-33% flop -> 40-55% turn -> 75-100% river.
    SPR > 15:  Deep stack play. Small bets early; big bets on strong runouts.

  BACKWARD INDUCTION:
    Work backwards from the desired final state (stacks in on street X):
    Target final pot = 2 * effective_stack
    Turn pot needed if jamming river: stack_after_turn_bet / remaining_stack_ratio
    Flop bet needed to reach turn target pot

  HAND-SPECIFIC COMMITMENT URGENCY:
    sets/two_pair:    medium urgency (can wait; improved by blanks)
    overpair:         high urgency (vulnerable; commit on flop vs draws)
    top_pair:         low-medium urgency (equity denial not critical)
    flush_draw:       don't commit until river (equity not realized)
    nuts/near_nuts:   any street (extract max value; can slowplay)

DISTINCT FROM:
  spr_planner.py:        SPR analysis and hand commitment thresholds
  spr_commitment.py:     Whether to commit stacks (yes/no decision)
  street_plan_builder.py: Multi-street line (bet/check/raise choices)
  THIS MODULE:           HOW MUCH to bet on each street to precisely
                         achieve a desired stack commitment point.
                         Backward induction from final pot target.

Usage:
    from poker.pot_geometry_planner import plan_pot_geometry, PotGeometryPlan, pgp_one_liner

    result = plan_pot_geometry(
        hero_hand_category='set',
        pot_bb=20.0,
        stack_bb=80.0,
        street='flop',
        board_texture='semi_wet',
        target_commitment_street='turn',
    )
    print(pgp_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List


# Minimum equity needed to commit stacks by hand category
COMMIT_EQUITY = {
    'nuts':           0.85,
    'near_nuts':      0.80,
    'full_house':     0.82,
    'flush':          0.75,
    'set':            0.70,
    'two_pair':       0.62,
    'overpair':       0.58,
    'top_pair':       0.50,
    'middle_pair':    0.40,
    'bottom_pair':    0.35,
    'flush_draw':     0.45,
    'oesd':           0.40,
    'gutshot':        0.30,
    'air':            0.05,
}

# Recommended commitment street by SPR
SPR_COMMIT_STREET = {
    (0.0, 2.0):   'flop',
    (2.0, 4.0):   'turn',
    (4.0, 8.0):   'turn',
    (8.0, 12.0):  'river',
    (12.0, 999.): 'river',
}

# Urgency to commit stacks by hand
COMMIT_URGENCY = {
    'nuts': 'low',         # slowplay potential; don't need to rush
    'near_nuts': 'low',
    'full_house': 'low',
    'flush': 'medium',
    'set': 'medium',
    'two_pair': 'medium_high',
    'overpair': 'high',    # vulnerable to overcards and draws
    'top_pair': 'medium',
    'middle_pair': 'low',
    'flush_draw': 'never', # don't commit with draws
    'oesd': 'never',
    'gutshot': 'never',
    'air': 'never',
}


def _recommended_commit_street(spr: float, hand_category: str) -> str:
    urgency = COMMIT_URGENCY.get(hand_category, 'medium')
    if urgency == 'never':
        return 'never'
    for (lo, hi), street in SPR_COMMIT_STREET.items():
        if lo <= spr < hi:
            # High urgency (overpair) commits one street earlier
            if urgency == 'high' and street == 'turn':
                return 'flop'
            if urgency == 'high' and street == 'river':
                return 'turn'
            # Low urgency can wait one street later
            if urgency == 'low' and street == 'flop':
                return 'turn'
            return street
    return 'river'


def _flop_bet_pct(target_street: str, spr: float) -> float:
    """Flop bet size as fraction of pot to set up target commitment street."""
    if target_street == 'flop':
        return 0.70   # big bet now to commit
    elif target_street == 'turn':
        if spr <= 3:
            return 0.60
        elif spr <= 5:
            return 0.50
        else:
            return 0.40
    else:   # river
        return 0.30   # small; need two more streets


def _turn_bet_pct(target_street: str, spr: float) -> float:
    """Turn bet size as fraction of pot."""
    if target_street == 'flop':
        return 0.0    # already committed on flop
    elif target_street == 'turn':
        if spr <= 3:
            return 0.80
        else:
            return 0.65
    else:   # river
        if spr <= 8:
            return 0.55
        else:
            return 0.45


def _river_bet_pct(target_street: str, spr: float, remaining_stack: float, pot: float) -> float:
    """River bet size as fraction of pot. May be a jam."""
    if target_street in ('flop', 'turn'):
        return 0.0   # stack committed already
    # River: bet remaining stack if it fits, else use geometric sizing
    if remaining_stack <= pot:
        return min(remaining_stack / pot, 1.0)
    return 0.75


def _run_pot_geometry(
    pot_bb: float,
    stack_bb: float,
    flop_pct: float,
    turn_pct: float,
    river_pct: float,
) -> Dict[str, float]:
    """Simulate pot growth through streets with given bet percentages."""
    result = {}
    pot = pot_bb
    stack = stack_bb

    # Flop
    flop_bet = min(pot * flop_pct, stack)
    pot_after_flop = pot + flop_bet * 2   # villain calls
    stack_after_flop = stack - flop_bet
    result['flop_bet'] = round(flop_bet, 1)
    result['pot_after_flop'] = round(pot_after_flop, 1)
    result['stack_after_flop'] = round(stack_after_flop, 1)

    # Turn
    turn_bet = min(pot_after_flop * turn_pct, stack_after_flop)
    pot_after_turn = pot_after_flop + turn_bet * 2
    stack_after_turn = stack_after_flop - turn_bet
    result['turn_bet'] = round(turn_bet, 1)
    result['pot_after_turn'] = round(pot_after_turn, 1)
    result['stack_after_turn'] = round(stack_after_turn, 1)

    # River
    river_bet = min(pot_after_turn * river_pct, stack_after_turn)
    pot_after_river = pot_after_turn + river_bet * 2
    stack_at_end = stack_after_turn - river_bet
    result['river_bet'] = round(river_bet, 1)
    result['pot_after_river'] = round(pot_after_river, 1)
    result['stack_at_end'] = round(stack_at_end, 1)
    result['total_invested'] = round(flop_bet + turn_bet + river_bet, 1)
    result['stack_committed_pct'] = round(
        (flop_bet + turn_bet + river_bet) / stack_bb, 3
    ) if stack_bb > 0 else 0.0
    return result


def _commit_label(committed_pct: float, target_street: str) -> str:
    if committed_pct >= 0.95:
        return 'ALL_IN'
    elif committed_pct >= 0.75:
        return 'NEAR_COMMITTED'
    elif committed_pct >= 0.50:
        return f'HALF_STACK_BY_{target_street.upper()}'
    else:
        return 'SHALLOW_BET'


@dataclass
class PotGeometryPlan:
    # Inputs
    hero_hand_category: str
    pot_bb: float
    stack_bb: float
    street: str
    board_texture: str
    target_commitment_street: str

    # Derived
    spr: float
    recommended_commit_street: str
    commit_urgency: str
    min_commit_equity: float

    # Sizing plan
    flop_bet_pct: float
    turn_bet_pct: float
    river_bet_pct: float

    # Running pots
    pot_geo: Dict[str, float]
    commit_label: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def plan_pot_geometry(
    hero_hand_category: str = 'set',
    pot_bb: float = 20.0,
    stack_bb: float = 80.0,
    street: str = 'flop',
    board_texture: str = 'semi_wet',
    target_commitment_street: str = 'turn',
) -> PotGeometryPlan:
    """
    Plan optimal bet sizes at each street to commit stacks by target street.

    Args:
        hero_hand_category:       Hero's current hand strength
        pot_bb:                   Current pot size in big blinds
        stack_bb:                 Effective stack (smaller of two)
        street:                   Current street: 'flop' / 'turn' / 'river'
        board_texture:            'wet' / 'semi_wet' / 'dry' / 'monotone'
        target_commitment_street: Street to aim for stack commitment

    Returns:
        PotGeometryPlan
    """
    spr = round(stack_bb / pot_bb, 2) if pot_bb > 0 else 0.0

    urgency = COMMIT_URGENCY.get(hero_hand_category, 'medium')
    rec_street = _recommended_commit_street(spr, hero_hand_category)
    min_equity = COMMIT_EQUITY.get(hero_hand_category, 0.50)

    # Derive bet percentages
    flop_pct = _flop_bet_pct(target_commitment_street, spr)
    turn_pct = _turn_bet_pct(target_commitment_street, spr)

    # Texture adjustment: wet boards = smaller bets (protection not as efficient)
    if board_texture in ('wet', 'monotone'):
        flop_pct = max(0.25, flop_pct - 0.08)
        turn_pct = max(0.25, turn_pct - 0.05)
    elif board_texture == 'dry':
        flop_pct = min(0.80, flop_pct + 0.08)
        turn_pct = min(0.90, turn_pct + 0.05)

    # Run preliminary geo to get pot/stack at river
    prelim = _run_pot_geometry(pot_bb, stack_bb, flop_pct, turn_pct, 0.0)
    river_pct = _river_bet_pct(
        target_commitment_street, spr,
        prelim['stack_after_turn'], prelim['pot_after_turn']
    )

    geo = _run_pot_geometry(pot_bb, stack_bb, flop_pct, turn_pct, river_pct)
    label = _commit_label(geo['stack_committed_pct'], target_commitment_street)

    verdict = (
        f'[PGP {hero_hand_category}|{street}] COMMIT_{target_commitment_street.upper()} '
        f'spr={spr:.1f} | '
        f'flop={flop_pct:.0%} turn={turn_pct:.0%} river={river_pct:.0%} '
        f'pot_final={geo["pot_after_river"]:.0f}BB'
    )

    reasoning = (
        f'Pot geometry plan for {hero_hand_category} on {board_texture} {street}. '
        f'SPR={spr:.1f}. Urgency={urgency}. '
        f'Recommended commit street: {rec_street} (user target: {target_commitment_street}). '
        f'Bet sequence: flop={flop_pct:.0%}, turn={turn_pct:.0%}, river={river_pct:.0%}. '
        f'Stack invested: {geo["stack_committed_pct"]:.0%} of starting stack={stack_bb}BB. '
        f'Final pot={geo["pot_after_river"]:.1f}BB.'
    )

    tips = []

    tips.append(
        f'BET SEQUENCE: flop {geo["flop_bet"]:.1f}BB ({flop_pct:.0%}pot) -> '
        f'turn {geo["turn_bet"]:.1f}BB ({turn_pct:.0%}pot) -> '
        f'river {geo["river_bet"]:.1f}BB ({river_pct:.0%}pot). '
        f'Final pot: {geo["pot_after_river"]:.1f}BB. '
        f'Stack invested: {geo["total_invested"]:.1f}BB ({geo["stack_committed_pct"]:.0%}).'
    )

    tips.append(
        f'SPR COMMITMENT GUIDE (spr={spr:.1f}): '
        f'SPR<2 = commit now/flop; '
        f'SPR 2-4 = commit by turn; '
        f'SPR 4-8 = commit by turn/river; '
        f'SPR>8 = river only. '
        f'Your hand ({hero_hand_category}) urgency is {urgency}: '
        f'recommended commit street = {rec_street}.'
    )

    tips.append(
        f'MIN EQUITY TO COMMIT: {min_equity:.0%} for {hero_hand_category}. '
        f'Committing requires at least {min_equity:.0%} equity vs villain calling range. '
        f'If equity is below this, reduce commitment or check back.'
    )

    if urgency == 'high':
        tips.append(
            f'HIGH URGENCY HAND: {hero_hand_category} is vulnerable to overcards/draws. '
            f'Commit one street earlier than SPR suggests. '
            f'Giving free cards costs more than overbet protection.'
        )
    elif urgency == 'low':
        tips.append(
            f'LOW URGENCY HAND: {hero_hand_category} benefits from slowplay potential. '
            f'Consider mixing in check-back on the flop to balance range. '
            f'Most value comes from trapping with checks then betting turn/river.'
        )

    if board_texture in ('wet', 'monotone'):
        tips.append(
            f'WET BOARD ({board_texture}): Villain has more draws; your equity advantage shrinks. '
            f'Adjust: smaller flop bets to induce calls (not big bets that fold out draws). '
            f'Raise sizes on wet boards should still deny equity but not build pot too fast.'
        )

    return PotGeometryPlan(
        hero_hand_category=hero_hand_category,
        pot_bb=pot_bb,
        stack_bb=stack_bb,
        street=street,
        board_texture=board_texture,
        target_commitment_street=target_commitment_street,
        spr=spr,
        recommended_commit_street=rec_street,
        commit_urgency=urgency,
        min_commit_equity=min_equity,
        flop_bet_pct=flop_pct,
        turn_bet_pct=turn_pct,
        river_bet_pct=river_pct,
        pot_geo=geo,
        commit_label=label,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def pgp_one_liner(r: PotGeometryPlan) -> str:
    return (
        f'[PGP {r.hero_hand_category}|{r.street}] '
        f'COMMIT_{r.target_commitment_street.upper()} spr={r.spr:.1f} | '
        f'flop={r.flop_bet_pct:.0%} turn={r.turn_bet_pct:.0%} river={r.river_bet_pct:.0%} '
        f'pot={r.pot_geo["pot_after_river"]:.0f}BB'
    )
