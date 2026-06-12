"""
Postflop Draw Advisor (draw_advisor.py)

Analyzes drawing hands on the flop/turn: flush draws, straight draws, gutshots.
Determines whether pot odds + implied odds justify calling, and whether
a semi-bluff raise is more profitable than calling.

Usage:
    from poker.draw_advisor import analyze_draw, DrawAdvice
    result = analyze_draw(
        outs=9,              # flush draw
        pot_bb=15.0,
        villain_bet_bb=10.0,
        streets_remaining=2, # flop: still turn + river
        eff_stack_bb=80.0,
        villain_stack_bb=80.0,
        villain_tendency='avg',
    )
    print(result.action, result.ev_call)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Out counts for common draws ───────────────────────────────────────────────
DRAW_OUTS: dict = {
    'flush':          9,
    'oesd':           8,
    'combo_fd_oesd': 15,
    'combo_fd_gs':   12,
    'gutshot':        4,
    'fd_overcards':  12,   # FD + two overcards
    'two_pair_fh':    4,
    'set_fh':         7,
    'overcards':      6,
    'backdoor_fd':    2,   # one street to hit backdoor flush draw
}


def _hit_prob(outs: int, streets: int) -> float:
    """Probability of hitting at least one out in N streets (precise)."""
    unseen = 45   # 52 - 2 hero - 5 board
    if streets == 1:
        return outs / unseen
    elif streets == 2:
        p_miss = ((unseen - outs) / unseen) * ((unseen - 1 - outs) / (unseen - 1))
        return 1 - p_miss
    return min(1.0, outs * 0.022 * streets)


# How much villain pays off when draw completes — fraction of remaining stack
_PAYOFF_FRACTION: dict = {
    'payoff': 0.65,    # calling stations always pay
    'sticky': 0.50,    # calls decent bets
    'avg':    0.40,
    'tight':  0.25,
    'nitty':  0.15,
}

# Concealment discount: obvious draws get paid off less
_CONCEAL: dict = {
    'flush':          0.75,   # very obvious on paired/flush board
    'oesd':           0.88,
    'combo_fd_oesd':  0.70,
    'combo_fd_gs':    0.80,
    'gutshot':        1.00,   # concealed
    'fd_overcards':   0.75,
    'two_pair_fh':    0.95,
    'set_fh':         1.00,
    'overcards':      0.90,
    'backdoor_fd':    1.00,
}


@dataclass
class DrawAdvice:
    """Postflop draw analysis result."""
    draw_type: str
    outs: int
    streets_remaining: int

    # Probabilities
    hit_prob: float
    miss_prob: float

    # Pot odds
    pot_odds: float           # equity needed to break even on raw pot odds
    has_raw_pot_odds: bool    # True if hit_prob >= pot_odds

    # Implied odds
    required_implied_bb: float    # need to win this more when hitting
    realistic_implied_bb: float   # villain likely to pay this much
    implied_sufficient: bool

    # EV
    ev_call: float            # EV of calling (including implied)
    ev_raise: float           # EV of semi-bluff raise
    ev_fold: float            # always 0

    # Decision
    action: str               # 'raise', 'call', 'fold'
    raise_ok: bool
    call_ok: bool

    villain_tendency: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_draw(
    outs: int,
    pot_bb: float,
    villain_bet_bb: float,
    streets_remaining: int = 1,
    eff_stack_bb: float = 100.0,
    villain_stack_bb: float = 100.0,
    villain_tendency: str = 'avg',
    draw_type: str = 'flush',
    in_position: bool = True,
    villain_fold_to_raise: float = 0.50,
) -> DrawAdvice:
    """
    Analyze a drawing hand situation on the flop or turn.

    Args:
        outs:                  Number of clean outs
        pot_bb:                Pot size before villain's bet
        villain_bet_bb:        Villain's bet size
        streets_remaining:     1 (turn decision) or 2 (flop with turn+river left)
        eff_stack_bb:          Hero's effective stack
        villain_stack_bb:      Villain's remaining stack
        villain_tendency:      'payoff', 'sticky', 'avg', 'tight', 'nitty'
        draw_type:             Key from DRAW_OUTS (used for concealment discount)
        in_position:           Hero acts after villain postflop
        villain_fold_to_raise: Villain's fold frequency when facing a raise (0-1)

    Returns:
        DrawAdvice
    """
    total_pot = pot_bb + villain_bet_bb
    hit_prob = _hit_prob(outs, streets_remaining)
    miss_prob = 1 - hit_prob
    pot_odds = villain_bet_bb / (pot_bb + villain_bet_bb)

    has_raw_pot_odds = hit_prob >= pot_odds

    # ── Required implied winnings ──────────────────────────────────────────
    # Breakeven: hit_prob * (pot_bb + impl) = miss_prob * call
    # → impl = (miss_prob * call - hit_prob * pot) / hit_prob
    if has_raw_pot_odds:
        required_implied = 0.0
    elif hit_prob > 0:
        required_implied = max(0.0,
            (miss_prob * villain_bet_bb - hit_prob * pot_bb) / hit_prob)
    else:
        required_implied = float('inf')

    # ── Realistic implied winnings ─────────────────────────────────────────
    payoff_frac = _PAYOFF_FRACTION.get(villain_tendency, 0.40)
    conceal = _CONCEAL.get(draw_type, 0.85)
    remaining_stack = min(villain_stack_bb, eff_stack_bb) - villain_bet_bb
    realistic_implied = remaining_stack * payoff_frac * conceal

    implied_sufficient = realistic_implied >= required_implied or has_raw_pot_odds

    # ── EV of calling ─────────────────────────────────────────────────────
    ev_call = (hit_prob * (pot_bb + realistic_implied)
               - miss_prob * villain_bet_bb)

    # ── EV of semi-bluff raising ──────────────────────────────────────────
    # Semi-bluff raise: charge villain to see next card AND have equity
    raise_size = 2.5 * villain_bet_bb
    raise_size = min(raise_size, eff_stack_bb * 0.40)

    # EV when villain folds: win the pot
    ev_raise_fold = total_pot

    # EV when villain calls: hero has outs + raise size already in
    pot_after_raise = total_pot + raise_size
    ev_raise_call = hit_prob * pot_after_raise - miss_prob * raise_size

    ev_raise = (villain_fold_to_raise * ev_raise_fold
                + (1 - villain_fold_to_raise) * ev_raise_call)

    # ── Decision ──────────────────────────────────────────────────────────
    call_ok = ev_call > 0 and implied_sufficient
    raise_ok = ev_raise > ev_call and outs >= 6 and streets_remaining >= 1

    if raise_ok and villain_fold_to_raise >= 0.40:
        action = 'raise'
    elif call_ok or has_raw_pot_odds:
        action = 'call'
    else:
        action = 'fold'

    # ── Tips ──────────────────────────────────────────────────────────────
    tips = []
    if streets_remaining == 2 and outs >= 9:
        tips.append(f'{outs} outs + 2 streets = {hit_prob:.0%} equity — '
                    f'semi-bluff raise often better than calling.')
    if not has_raw_pot_odds and not implied_sufficient:
        tips.append(f'Need {required_implied:.1f}BB implied but only '
                    f'{realistic_implied:.1f}BB realistic — fold unless read changes.')
    if draw_type == 'flush' and streets_remaining == 1:
        tips.append('Turn FD: one card to hit. If pot odds not met, fold unless '
                    'villain is a payoff station.')
    if villain_tendency in ('tight', 'nitty') and not has_raw_pot_odds:
        tips.append(f'{villain_tendency} villain pays off less — '
                    f'reduce implied odds estimate further.')
    if in_position and not raise_ok:
        tips.append('In position: consider floating (calling) and barrel the turn '
                    'if villain checks.')
    if not tips:
        tips.append(f'Outs={outs} hit_prob={hit_prob:.0%} pot_odds={pot_odds:.0%}. '
                    f'Standard draw decision.')

    reasoning = (
        f'{draw_type} ({outs} outs): {hit_prob:.0%} hit chance, '
        f'{streets_remaining} street(s) left. '
        f'Call {villain_bet_bb:.1f}BB into {pot_bb:.1f}BB (pot_odds={pot_odds:.0%}). '
        f'Need {required_implied:.1f}BB implied; realistic={realistic_implied:.1f}BB '
        f'({villain_tendency}). '
        f'EV(call)={ev_call:+.2f} EV(raise)={ev_raise:+.2f}. '
        f'Action: {action.upper()}.'
    )

    return DrawAdvice(
        draw_type=draw_type,
        outs=outs,
        streets_remaining=streets_remaining,
        hit_prob=round(hit_prob, 3),
        miss_prob=round(miss_prob, 3),
        pot_odds=round(pot_odds, 3),
        has_raw_pot_odds=has_raw_pot_odds,
        required_implied_bb=round(required_implied, 2),
        realistic_implied_bb=round(realistic_implied, 2),
        implied_sufficient=implied_sufficient,
        ev_call=round(ev_call, 2),
        ev_raise=round(ev_raise, 2),
        ev_fold=0.0,
        action=action,
        raise_ok=raise_ok,
        call_ok=call_ok,
        villain_tendency=villain_tendency,
        reasoning=reasoning,
        tips=tips,
    )


def draw_one_liner(result: DrawAdvice) -> str:
    """Single-line overlay summary."""
    return (f'{result.draw_type} {result.outs}outs {result.hit_prob:.0%}: '
            f'{result.action.upper()} | '
            f'EV={result.ev_call:+.2f}BB req={result.required_implied_bb:.1f} '
            f'real={result.realistic_implied_bb:.1f}BB')
