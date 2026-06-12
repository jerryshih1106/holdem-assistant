"""
Implied Odds Advisor (implied_odds_advisor.py)

Many players confuse pot odds with implied odds. This module clarifies both:

POT ODDS (direct):
  Required equity = call / (pot + call)
  You need this exact equity to break even on THIS call, ignoring future betting.
  Example: Pot=100, Call=50 → req_equity = 50/150 = 33%

IMPLIED ODDS (forward):
  You will win MORE than just the current pot if you hit your draw.
  When villain has a strong hand and you hit, they will continue betting.
  Adjusted required equity = call / (pot + call + expected_future_gain)
  Example: Pot=100, Call=50, Expected future win=80 → req = 50/230 = 22%

  Future gain depends on:
  - Villain's stack depth (how much can they put in?)
  - Villain's calling tendency (do they pay off when you hit?)
  - Nuts vs non-nuts draw (do you WIN when you hit?)
  - Position (IP draws realize more value)

REVERSE IMPLIED ODDS (important!):
  When your draw completes, you might STILL LOSE to a better hand.
  Examples of bad reverse implied odds:
  - Non-nut flush draw: if A♠ comes, villain has Ax♠ = you lose when you "hit"
  - Low straight: 2345 straight is vulnerable to 6789 or 5678 straights
  - Bottom set: can become counterfeit by paired board

  Reverse implied odds INCREASE required equity:
  adj_req = req + reverse_penalty

  Reverse penalty:
  - Nut flush draw (Ax suited): 0% penalty (always wins if flush hits)
  - Non-nut flush: 8-15% penalty (risk of losing to higher flush)
  - OESD (middle of board): 5-10% penalty (risk of losing to higher straight)
  - Gutshot to low straight: 12-20% penalty

WHEN IMPLIED ODDS JUSTIFY A CALL:
  Rule of thumb:
  - Call is justified if you expect to win at least 6x the call amount when you hit
    AND villain has at least that much behind
  - "6x rule" for draws: implied_ratio >= 6 is profitable for most draws

STACK DEPTH REQUIREMENTS FOR IMPLIED ODDS:
  For draws to be worth calling:
  - FD (9 outs): need ~4x remaining stack after calling
  - OESD (8 outs): need ~5x remaining stack
  - Gutshot (4 outs): need ~10x remaining stack

Usage:
    from poker.implied_odds_advisor import advise_implied_odds
    from poker.implied_odds_advisor import ImpliedOddsAdvice, implied_odds_one_liner

    advice = advise_implied_odds(
        outs=9,
        draw_type='flush_draw',
        call_size_bb=8.0,
        pot_bb=25.0,
        villain_stack_bb=80.0,
        hero_stack_bb=90.0,
        hero_pos='IP',
        street='flop',
        villain_vpip=0.35,
        villain_af=2.0,
        is_nut_draw=True,
        n_opponents=1,
    )
    print(implied_odds_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List


# ── Reverse implied odds penalties ────────────────────────────────────────────

_REVERSE_PENALTIES = {
    'nut_flush_draw':     0.00,  # always wins when flush hits
    'flush_draw':         0.10,  # risk of non-nut flush losing to better flush
    'oesd':               0.07,  # risk of losing to higher straight
    'gutshot':            0.12,  # low straight risk
    'overcard':           0.05,  # overcard may not be best kicker
    'set_mining':         0.03,  # set can lose to flush/straight
    'pair_draw':          0.08,  # two pair/trips can still lose
    'combo_draw':         0.05,  # usually nut-heavy, but some risk
}


def _reverse_penalty(draw_type: str, is_nut_draw: bool) -> float:
    base = _REVERSE_PENALTIES.get(draw_type, 0.08)
    if is_nut_draw:
        base = max(0.0, base - 0.07)  # nut draws have less reverse implied odds risk
    return round(base, 3)


# ── Future gain estimate ──────────────────────────────────────────────────────

def _estimate_future_gain(
    villain_stack_bb: float,
    outs: int,
    hero_pos: str,
    villain_vpip: float,
    villain_af: float,
    pot_bb: float,
    street: str,
) -> float:
    """
    Estimate how much hero expects to win from future streets when draw hits.
    This is NOT the full remaining stack — villain won't stack off unless they have a hand.
    """
    max_future = min(villain_stack_bb, 200.0)

    # Base: villain will put in some fraction of their stack if hero hits
    # More draws = more equity = villain more likely to continue (paradoxically less future gain)
    hit_value_mult = {
        'flop': 0.55,    # 2 streets left = good implied odds
        'turn': 0.30,    # 1 street left = less implied odds
        'river': 0.0,    # no future streets
    }.get(street, 0.40)

    # Villain calling tendency (higher VPIP = more likely to call when hero hits)
    call_adjustment = (villain_vpip - 0.25) * 0.8  # +/- 20% around baseline
    hit_value_mult = max(0.10, hit_value_mult + call_adjustment)

    # IP hero realizes more value (can get more streets in)
    if hero_pos == 'IP':
        hit_value_mult += 0.08

    # Aggressive villain = more likely to bet into hero when hero hits (more future gain)
    if villain_af >= 2.5:
        hit_value_mult += 0.10

    future_gain = max_future * hit_value_mult
    # Cap at reasonable level
    return round(min(future_gain, pot_bb * 3.5), 2)


# ── Equity calculations ───────────────────────────────────────────────────────

def _direct_equity_required(call: float, pot: float) -> float:
    """Simple pot odds: call / (pot + call)."""
    if pot + call == 0:
        return 0.0
    return round(call / (pot + call), 4)


def _implied_equity_required(call: float, pot: float, future_gain: float) -> float:
    """call / (pot + call + future_gain): lower requirement with implied odds."""
    denom = pot + call + future_gain
    if denom == 0:
        return 0.0
    return round(call / denom, 4)


def _reverse_adjusted_equity(base_eq: float, reverse_penalty: float) -> float:
    """Add reverse implied odds penalty to required equity."""
    return round(min(base_eq + reverse_penalty, 0.95), 4)


def _current_equity(outs: int, street: str) -> float:
    """Rule of 2&4 equity estimate."""
    mult = 4 if street == 'flop' else 2
    return round(min(outs * mult / 100.0, 0.95), 3)


def _implied_ratio(call: float, future_gain: float) -> float:
    """How many times expected gain vs call size (higher = better odds)."""
    if call == 0:
        return 0.0
    return round((future_gain) / call, 1)


def _required_future_gain(call: float, pot: float, direct_req: float) -> float:
    """How much future gain is needed to make the call breakeven."""
    if direct_req >= 1.0:
        return float('inf')
    # Solve: call / (pot + call + X) = current_equity → X = call/eq - pot - call
    return 0.0  # placeholder, computed below


# ── Overall decision ──────────────────────────────────────────────────────────

def _decide(
    hero_eq: float, adj_req: float, direct_req: float,
    outs: int, street: str, implied_ratio: float,
) -> tuple:
    """Returns (action, verdict)."""
    if hero_eq >= adj_req + 0.05:
        action = 'call'
        verdict = (
            f'CALL: equity={hero_eq:.0%} comfortably exceeds '
            f'implied-adjusted requirement={adj_req:.0%}. '
            f'Implied ratio={implied_ratio:.1f}x (call justified).'
        )
    elif hero_eq >= adj_req:
        action = 'call_marginal'
        verdict = (
            f'MARGINAL CALL: equity={hero_eq:.0%} barely meets '
            f'requirement={adj_req:.0%}. '
            f'Close decision — lean call if villain is loose/passive.'
        )
    elif hero_eq >= direct_req + 0.02:
        action = 'call_if_implied'
        verdict = (
            f'CALL ONLY WITH IMPLIED ODDS: direct req={direct_req:.0%} met, '
            f'but reverse implied odds adjust to {adj_req:.0%}. '
            f'Call if villain is likely to pay off when you hit.'
        )
    else:
        action = 'fold'
        verdict = (
            f'FOLD: equity={hero_eq:.0%} < req={adj_req:.0%}. '
            f'Even with implied odds, this draw is not profitable enough. '
            f'Need {adj_req:.0%} but only have {hero_eq:.0%}.'
        )
    return (action, verdict)


@dataclass
class ImpliedOddsAdvice:
    """Implied odds analysis for a drawing hand."""
    outs: int
    draw_type: str
    call_size_bb: float
    pot_bb: float
    villain_stack_bb: float
    hero_stack_bb: float
    hero_pos: str
    street: str
    villain_vpip: float
    villain_af: float
    is_nut_draw: bool
    n_opponents: int

    # Analysis
    hero_equity: float            # rule-of-2/4 equity
    direct_required_equity: float # pot odds only
    estimated_future_gain: float  # expected future BB won when hitting
    implied_required_equity: float # with implied odds
    reverse_penalty: float         # reverse implied odds adjustment
    final_required_equity: float   # implied + reverse
    implied_ratio: float           # future_gain / call_size

    # Decision
    action: str                   # 'call', 'call_marginal', 'call_if_implied', 'fold'
    verdict: str

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_implied_odds(
    outs: int = 9,
    draw_type: str = 'flush_draw',
    call_size_bb: float = 8.0,
    pot_bb: float = 25.0,
    villain_stack_bb: float = 80.0,
    hero_stack_bb: float = 90.0,
    hero_pos: str = 'IP',
    street: str = 'flop',
    villain_vpip: float = 0.35,
    villain_af: float = 2.0,
    is_nut_draw: bool = True,
    n_opponents: int = 1,
) -> ImpliedOddsAdvice:
    """
    Calculate implied odds for a drawing hand.

    Args:
        outs:              Number of outs
        draw_type:         'flush_draw', 'oesd', 'gutshot', 'overcard', etc.
        call_size_bb:      Size of the call in BB
        pot_bb:            Current pot in BB
        villain_stack_bb:  Villain's remaining stack in BB
        hero_stack_bb:     Hero's remaining stack in BB
        hero_pos:          'IP' or 'OOP'
        street:            'flop', 'turn', 'river'
        villain_vpip:      Villain's VPIP
        villain_af:        Villain's aggression factor
        is_nut_draw:       Is this the nut version of the draw?
        n_opponents:       Number of opponents

    Returns:
        ImpliedOddsAdvice
    """
    hero_eq = _current_equity(outs, street)
    direct_req = _direct_equity_required(call_size_bb, pot_bb)
    future_gain = _estimate_future_gain(
        villain_stack_bb, outs, hero_pos, villain_vpip, villain_af, pot_bb, street,
    )

    # Multiway: implied odds worse (less likely villain has strong enough hand)
    if n_opponents > 1:
        future_gain *= 0.75

    impl_req = _implied_equity_required(call_size_bb, pot_bb, future_gain)
    rev_penalty = _reverse_penalty(draw_type, is_nut_draw)
    final_req = _reverse_adjusted_equity(impl_req, rev_penalty)
    ratio = _implied_ratio(call_size_bb, future_gain)
    action, verdict = _decide(hero_eq, final_req, direct_req, outs, street, ratio)

    reasoning = (
        f'{draw_type} with {outs} outs on {street}. '
        f'Equity={hero_eq:.0%}. '
        f'Direct req={direct_req:.0%} (pot odds). '
        f'Implied adj req={impl_req:.0%}. '
        f'Reverse penalty={rev_penalty:.0%} → final req={final_req:.0%}. '
        f'Future gain est={future_gain:.1f}BB (ratio={ratio:.1f}x). '
        f'Decision: {action}.'
    )

    # Tips
    tips = []
    if not is_nut_draw and rev_penalty >= 0.08:
        tips.append(
            f'REVERSE IMPLIED ODDS RISK ({rev_penalty:.0%} penalty): '
            f'Non-nut {draw_type} — when you hit, villain may have a BETTER draw. '
            f'Example: you have J♥9♥, board K♥5♥2♦, villain has A♥Q♥. '
            f'You both hit the flush but villain wins. '
            f'Reduce effective outs by 1-2 for non-nut draws. '
            f'Consider folding if villain range is wide (likely to have better flush).'
        )
    if street == 'turn':
        tips.append(
            f'TURN DRAW (1 card left): '
            f'Implied odds are significantly reduced — only 1 card to hit. '
            f'Rule of 2: {outs}x2%={outs*2}% equity. '
            f'Required: {final_req:.0%}. '
            f'Future gain only from RIVER action (villain must call a river bet when you hit). '
            f'Tight villains → fold. Loose villains → may still call with good implied odds.'
        )
    if villain_vpip > 0.45:
        tips.append(
            f'FISH OPPONENT (VPIP={villain_vpip:.0%}): '
            f'Excellent implied odds. Fish will call large river bets when you complete. '
            f'Future gain estimated at {future_gain:.1f}BB. '
            f'Even marginal draws are more profitable vs fish. '
            f'Use smaller calls to stay in, then extract on the river.'
        )
    if villain_stack_bb < call_size_bb * 4:
        tips.append(
            f'SHALLOW STACK (villain={villain_stack_bb:.0f}BB): '
            f'Villain does not have enough behind for good implied odds. '
            f'Future gain capped at {villain_stack_bb:.0f}BB. '
            f'Consider: pot odds alone must justify the call. '
            f'Required={direct_req:.0%}, equity={hero_eq:.0%}. '
            f'Stack-to-call ratio is only {villain_stack_bb/call_size_bb:.1f}x.'
        )
    if hero_pos == 'OOP' and action in ('call', 'call_marginal'):
        tips.append(
            f'OOP DRAW: realized equity is lower OOP (cannot set own price on later streets). '
            f'Adjust future gain down by ~15-20%. '
            f'Prefer: check-call OOP; avoid check-raise with non-nut draws OOP (risk of re-raise).'
        )
    if ratio >= 6:
        tips.append(
            f'GOOD IMPLIED ODDS (ratio={ratio:.1f}x): '
            f'Expected future gain is {ratio:.1f}x your call. '
            f'Standard rule: implied ratio >= 6 justifies most draws. '
            f'CALL is clearly correct here.'
        )
    if not tips:
        tips.append(
            f'{draw_type} ({outs} outs): {action}. '
            f'Required={final_req:.0%}, have={hero_eq:.0%}. '
            f'Future gain: {future_gain:.1f}BB ({ratio:.1f}x call). '
            f'Rev penalty: {rev_penalty:.0%}.'
        )

    return ImpliedOddsAdvice(
        outs=outs,
        draw_type=draw_type,
        call_size_bb=round(call_size_bb, 1),
        pot_bb=round(pot_bb, 1),
        villain_stack_bb=round(villain_stack_bb, 1),
        hero_stack_bb=round(hero_stack_bb, 1),
        hero_pos=hero_pos,
        street=street,
        villain_vpip=round(villain_vpip, 3),
        villain_af=round(villain_af, 2),
        is_nut_draw=is_nut_draw,
        n_opponents=n_opponents,
        hero_equity=hero_eq,
        direct_required_equity=direct_req,
        estimated_future_gain=future_gain,
        implied_required_equity=impl_req,
        reverse_penalty=rev_penalty,
        final_required_equity=final_req,
        implied_ratio=ratio,
        action=action,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def implied_odds_one_liner(r: ImpliedOddsAdvice) -> str:
    return (
        f'[IO {r.draw_type}({r.outs}outs)@{r.street}|{r.hero_pos}] '
        f'{r.action.upper()} | '
        f'eq={r.hero_equity:.0%} req={r.final_required_equity:.0%} '
        f'fut_gain={r.estimated_future_gain:.1f}BB ratio={r.implied_ratio:.1f}x | '
        f'rev_pen={r.reverse_penalty:.0%}'
    )
