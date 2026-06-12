"""
Satellite Strategy Optimizer (satellite_strategy_optimizer.py)

Satellites award the SAME prize to everyone who finishes in a paid spot
(typically a tournament ticket). This creates a uniquely flat prize pool
that demands a completely different strategy from regular MTT play.

KEY INSIGHT:
  In a satellite, chip EV and $ EV diverge dramatically near the bubble.
  A chip-leading player has NO incentive to accumulate more chips beyond
  "enough to survive." Busting anyone gets you closer to your goal.

SATELLITE DYNAMICS:
  - All that matters is finishing IN the paid spots, not how many chips
  - With 3 seats and 4 players left: any bust is equally valuable
  - With 5 seats and 6 players left: extreme survival mode
  - The shortest stack is often NOT worth calling -- let them bust vs others

CRITICAL STRATEGY DIFFERENCES vs REGULAR MTT:
  1. NEVER call off stack with <65% equity near bubble (even with chips to spare)
  2. Chip leader should FOLD, not accumulate -- no point risking bust
  3. Short stacks should shove VERY wide (desperation = fold equity opportunity)
  4. Medium stacks avoid confrontation with other medium stacks near bubble
  5. "Lock up" mode: when you have enough to survive, sit and wait

Usage:
    from poker.satellite_strategy_optimizer import optimize_satellite_strategy, SatelliteAdvice, sat_one_liner

    advice = optimize_satellite_strategy(
        hero_stack_bb=40.0,
        avg_stack_bb=30.0,
        seats_awarded=3,
        players_remaining=5,
        min_stack_bb=8.0,
        max_stack_bb=60.0,
    )
    print(sat_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _survival_probability(stack: float, avg: float, n_players: int, seats: int) -> float:
    """
    Rough survival probability by folding (baseline).
    If hero is ahead of average: high survival chance.
    If below average: lower.
    """
    if n_players <= seats:
        return 1.0
    if n_players == seats + 1:
        # One bust away from cashing
        rank_est = max(1, min(n_players, int((avg / max(stack, 0.01)) * (n_players / 2))))
        if stack >= avg:
            return 0.90
        else:
            # Below average: lower but can still survive
            return max(0.30, stack / (avg * n_players / seats))
    else:
        # Multi-bust situations
        excess = n_players - seats
        if stack >= avg * 1.5:
            return 0.95
        elif stack >= avg:
            return 0.75
        elif stack >= avg * 0.5:
            return 0.50
        else:
            return 0.25


def _min_equity_to_call_off(survival_prob: float, pot_odds_equity: float) -> float:
    """
    In satellites, calling off requires MUCH higher equity than pot odds suggest.
    If you have 70% survival probability folding, you need >70% equity to call.
    """
    return max(survival_prob, pot_odds_equity)


def _strategy_mode(
    stack: float, avg: float, n_players: int, seats: int
) -> str:
    """Determine satellite strategy mode."""
    if n_players <= seats:
        return 'locked_in'
    bubble_proximity = (n_players - seats) / max(n_players, 1)

    if stack >= avg * 2.0 and bubble_proximity <= 0.25:
        return 'lock_up'     # chip leader near bubble: just survive
    if stack >= avg * 1.3:
        return 'accumulate'  # comfortable: modest accumulation
    if stack >= avg * 0.7:
        return 'survive'     # average: play tight
    if stack >= avg * 0.3:
        return 'shove_wide'  # short: shove or fold
    return 'desperate'       # very short: shove anything


_MODE_DESC = {
    'locked_in':   'Congrats -- you are already in the money! No pressure.',
    'lock_up':     'LOCK UP: You have enough to survive. Fold almost everything. Let others bust.',
    'accumulate':  'Comfortable stack. Modest accumulation. Avoid unnecessary all-in confrontations.',
    'survive':     'SURVIVAL MODE: Avoid coin flips. Fold marginal spots. One double-up puts you in comfort.',
    'shove_wide':  'SHOVE/FOLD: Push 30-45% of hands. You need chips NOW. Medium stacks will fold.',
    'desperate':   'DESPERATE: Shove any two cards. Do NOT fold your stack away.',
}

_VPIP_TARGET = {
    'locked_in':   '30%+ (play freely)',
    'lock_up':     '5-10% (near-rock)',
    'accumulate':  '18-22% (TAG)',
    'survive':     '12-18% (tight TAG)',
    'shove_wide':  '35-45% (shove/fold)',
    'desperate':   '100% (push every hand)',
}

_CALL_EQUITY_THRESHOLD = {
    'locked_in':   0.40,   # already in: standard pot odds
    'lock_up':     0.75,   # barely call without huge equity
    'accumulate':  0.65,
    'survive':     0.68,
    'shove_wide':  0.55,   # shove/fold: you call shoves wider when desperate
    'desperate':   0.45,   # desperate: call any hand with decent equity
}


# --------------------------------------------------------------------------
# Dataclass
# --------------------------------------------------------------------------

@dataclass
class SatelliteAdvice:
    # Inputs
    hero_stack_bb: float
    avg_stack_bb: float
    seats_awarded: int
    players_remaining: int
    min_stack_bb: float
    max_stack_bb: float

    # Analysis
    players_need_to_bust: int   # how many need to bust before cashing
    stack_vs_avg: float         # hero_stack / avg_stack
    survival_prob_fold: float   # estimated survival if folding into bubble
    strategy_mode: str
    strategy_desc: str

    # Thresholds
    min_equity_to_call_off: float   # do NOT call off stack below this
    vpip_target: str
    pot_odds_standard: float        # standard pot odds if called

    # Status
    on_bubble: bool
    is_chip_leader: bool
    is_short_stack: bool

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Main function
# --------------------------------------------------------------------------

def optimize_satellite_strategy(
    hero_stack_bb: float = 40.0,
    avg_stack_bb: float = 30.0,
    seats_awarded: int = 3,
    players_remaining: int = 5,
    min_stack_bb: float = 8.0,
    max_stack_bb: float = 60.0,
    pot_bb: float = 0.0,
    call_bb: float = 0.0,
) -> SatelliteAdvice:
    """
    Optimize satellite tournament strategy based on chip positions.

    Args:
        hero_stack_bb:     Hero's current stack in BB
        avg_stack_bb:      Average stack in BB
        seats_awarded:     Number of seats/tickets being awarded
        players_remaining: Players still in the tournament
        min_stack_bb:      Shortest stack at the table in BB
        max_stack_bb:      Largest stack at the table in BB
        pot_bb:            Current pot (for specific hand EV calculation)
        call_bb:           Current call size (0 if not facing a decision)

    Returns:
        SatelliteAdvice
    """
    to_bust = max(0, players_remaining - seats_awarded)
    stack_vs_avg = round(hero_stack_bb / max(avg_stack_bb, 1.0), 3)
    on_bubble = 1 <= to_bust <= 3
    is_chip_leader = hero_stack_bb >= max_stack_bb * 0.9
    is_short = hero_stack_bb <= min_stack_bb * 1.5

    mode = _strategy_mode(hero_stack_bb, avg_stack_bb, players_remaining, seats_awarded)
    mode_desc = _MODE_DESC[mode]

    surv_prob = _survival_probability(hero_stack_bb, avg_stack_bb, players_remaining, seats_awarded)

    pot_odds_eq = call_bb / (pot_bb + call_bb) if (pot_bb + call_bb) > 0 else 0.50
    min_eq = _min_equity_to_call_off(surv_prob, pot_odds_eq)
    vpip = _VPIP_TARGET[mode]
    call_threshold = _CALL_EQUITY_THRESHOLD[mode]

    reasoning = (
        f'Satellite: {to_bust} player(s) need to bust. '
        f'Hero stack={hero_stack_bb:.0f}BB ({stack_vs_avg:.2f}x avg={avg_stack_bb:.0f}BB). '
        f'Mode: {mode}. Survival prob (fold): {surv_prob:.0%}. '
        f'Min equity to call off: {call_threshold:.0%}.'
    )

    verdict = (
        f'SATELLITE [{mode.upper()}]: {mode_desc} '
        f'VPIP target: {vpip}. '
        f'Min equity to call off stack: {call_threshold:.0%}. '
        f'Players left: {players_remaining}, seats: {seats_awarded}, need {to_bust} to bust.'
    )

    tips = []

    # Satellite-specific tip #1
    tips.append(
        f'SATELLITE RULE: Finishing chips do NOT matter -- only finishing position. '
        f'Avoid ANY risk of bust when survival probability ({surv_prob:.0%}) is high. '
        f'Fold 70% equity hands near bubble if survival is better.'
    )

    if mode == 'lock_up':
        tips.append(
            f'CHIP LEADER LOCK UP: You have {hero_stack_bb:.0f}BB vs avg {avg_stack_bb:.0f}BB. '
            f'Sit on your stack. Do NOT open unless first-in with huge fold equity. '
            f'Every hand you fold, the short stacks burn chips on each other.'
        )
    elif mode == 'shove_wide':
        tips.append(
            f'SHOVE WIDE: Short stack needs action. Shove first-in from CO/BTN/SB. '
            f'Medium stacks CANNOT call you without risking their tournament life. '
            f'Use ICM pressure: they fold hands they would normally call with.'
        )
    elif mode == 'survive':
        tips.append(
            f'SURVIVAL: Average stack is dangerous -- you need to maintain. '
            f'Only play premium hands: 88+, AJs+, AQo+. '
            f'Let short stacks and chip leaders battle each other.'
        )

    if on_bubble and to_bust == 1:
        tips.append(
            f'ONE FROM CASH: Only {to_bust} player(s) need to bust. '
            f'The shortest stack ({min_stack_bb:.0f}BB) is your target. '
            f'Never call the short stack if it risks your own tournament life. '
            f'Let the short stack bust into someone else.'
        )

    if not on_bubble and to_bust > 3:
        tips.append(
            f'EARLY SATELLITE: {to_bust} players need to bust. Not yet panic time. '
            f'But avoid unnecessary gambles -- one bad spot can undo 2 hours of work.'
        )

    return SatelliteAdvice(
        hero_stack_bb=round(hero_stack_bb, 1),
        avg_stack_bb=round(avg_stack_bb, 1),
        seats_awarded=seats_awarded,
        players_remaining=players_remaining,
        min_stack_bb=round(min_stack_bb, 1),
        max_stack_bb=round(max_stack_bb, 1),
        players_need_to_bust=to_bust,
        stack_vs_avg=stack_vs_avg,
        survival_prob_fold=round(surv_prob, 3),
        strategy_mode=mode,
        strategy_desc=mode_desc,
        min_equity_to_call_off=round(call_threshold, 3),
        vpip_target=vpip,
        pot_odds_standard=round(pot_odds_eq, 4),
        on_bubble=on_bubble,
        is_chip_leader=is_chip_leader,
        is_short_stack=is_short,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sat_one_liner(r: SatelliteAdvice) -> str:
    return (
        f'[SAT {r.strategy_mode.upper()}|{r.players_remaining}left/{r.seats_awarded}seats] '
        f'stack={r.stack_vs_avg:.2f}x_avg surv={r.survival_prob_fold:.0%} | '
        f'min_eq_calloff={r.min_equity_to_call_off:.0%} vpip={r.vpip_target.split("(")[0].strip()}'
    )
