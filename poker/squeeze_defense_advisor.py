"""
Squeeze Defense Advisor (squeeze_defense_advisor.py)

When villain squeezes (3-bets after one or more callers), the dead money from
the callers changes the math significantly compared to facing a normal 3-bet.

Key insight: dead money improves your pot odds to call.
  Normal 3-bet defense: pot = open + 3bet; call cost = 3bet - open
  Squeeze defense: pot = open + callers × open + squeeze; call cost = squeeze - open
  Dead money makes the call more attractive.

Example:
  Open 3BB, two callers (3BB each), villain squeezes to 18BB:
  - Normal 3-bet math: pot before hero = 3+18=21BB, call=15BB, req_eq = 15/(21+15) = 41.7%
  - Squeeze math: pot before hero = 3+3+3+18=27BB (dead=6BB), call=15BB, req_eq = 15/(27+15) = 35.7%
  Dead money reduced required equity by 6%!

When to call the squeeze:
  - Call if hero_equity >= required_equity (with dead money)
  - More callers = more dead money = wider call range
  - Position matters: IP call is +EV with implied odds; OOP call needs more equity

When to 4-bet:
  - 4-bet for value: hand strong enough to build large pot (premiums, AK)
  - 4-bet as bluff: need villain to fold to 4-bets enough to be profitable
    EV(4-bet bluff) = villain_fold_4bet × (pot_before) - (1-fold_4bet) × 4bet_size
  - 4-bet more vs wide squeeze ranges (villain squeezing 12%+ = bluffing too often)

4-bet sizing:
  - As original raiser: 4-bet to ~2.5-3.0x the squeeze
  - The squeeze is already large (3.5-5x open), so 4-bets are relatively small multiplier

Fold thresholds:
  - Fold if hero_equity < required_equity AND 4-bet is not profitable
  - Original raiser: defend wider (already invested, dead money helps)
  - Caller who was about to call: fold most of range (will be OOP; committed to stacking off)

Usage:
    from poker.squeeze_defense_advisor import advise_squeeze_defense, SqueezeDefenseAdvice
    from poker.squeeze_defense_advisor import squeeze_defense_one_liner

    result = advise_squeeze_defense(
        hero_role='original_raiser',
        hero_pos='CO',
        open_size_bb=2.5,
        n_callers=2,
        squeeze_size_bb=14.0,
        hero_hand_class='strong',
        hero_equity=0.60,
        villain_squeeze_pct=0.08,
        villain_fold_to_4b=0.55,
        eff_stack_bb=100.0,
    )
    print(result.action, result.required_equity)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    return {
        'premium': 10, 'strong': 8, 'medium_pair': 6, 'medium': 5,
        'speculative': 3, 'marginal': 2, 'trash': 0, 'air': 0,
        'draw': 3, 'tptk': 5, 'top_pair': 4, 'overpair': 7,
        'two_pair': 6, 'set': 9, 'bluff_candidate': 2,
    }.get(hand_class.lower(), 4)


def _dead_money(n_callers: int, open_size_bb: float) -> float:
    """Dead money contributed by callers before villain's squeeze."""
    return round(n_callers * open_size_bb, 1)


def _pot_before_hero(
    open_size_bb: float,
    n_callers: int,
    squeeze_size_bb: float,
) -> float:
    """Pot size including hero's initial investment + dead money + squeeze."""
    return round(open_size_bb + n_callers * open_size_bb + squeeze_size_bb, 1)


def _call_cost(
    hero_role: str,
    open_size_bb: float,
    squeeze_size_bb: float,
) -> float:
    """Additional chips hero must invest to call."""
    if hero_role == 'original_raiser':
        # Hero already put in open_size_bb
        return round(squeeze_size_bb - open_size_bb, 1)
    elif hero_role == 'caller':
        # Hero already put in open_size_bb (called the open)
        return round(squeeze_size_bb - open_size_bb, 1)
    else:
        # Hero hasn't invested anything yet (other position)
        return round(squeeze_size_bb, 1)


def _required_equity(pot_before: float, call_cost: float) -> float:
    """Break-even equity to call. req_eq = call / (pot_after_call)."""
    total_after_call = pot_before + call_cost
    if total_after_call <= 0:
        return 0.5
    return round(call_cost / total_after_call, 4)


def _normal_3bet_req_eq(open_size_bb: float, threeb_size_bb: float) -> float:
    """Required equity for a normal 3-bet (no dead money)."""
    pot = open_size_bb + threeb_size_bb
    cost = threeb_size_bb - open_size_bb
    return round(cost / (pot + cost), 4)


def _fourbet_size(squeeze_size_bb: float, eff_stack_bb: float) -> float:
    """Recommended 4-bet size as raiser."""
    # 4-bet to ~2.5x squeeze, capped at ~40% of effective stack
    raw = squeeze_size_bb * 2.5
    return round(min(raw, eff_stack_bb * 0.40), 1)


def _fourbet_bluff_ev(
    pot_before: float,
    fourbet_size: float,
    villain_fold_to_4b: float,
    hero_equity_if_called: float,
) -> float:
    """EV of 4-bet bluff."""
    ev_fold = villain_fold_to_4b * pot_before
    ev_call = (1 - villain_fold_to_4b) * (
        hero_equity_if_called * (pot_before + 2 * fourbet_size) - fourbet_size
    )
    return round(ev_fold + ev_call, 2)


def _action(
    hero_equity: float,
    req_eq: float,
    hand_rank: int,
    villain_squeeze_pct: float,
    villain_fold_to_4b: float,
    pot_before: float,
    fourbet_size: float,
    eff_stack_bb: float,
) -> tuple:
    """(action, reasoning)"""
    # Premium hands: 4-bet for value
    if hand_rank >= 8:
        return (
            'fourbet_value',
            f'Premium hand (rank={hand_rank}): 4-bet to {fourbet_size:.1f}BB for value. '
            f'Want to build pot vs villain squeezing range.'
        )

    # Strong hands on verge of commitment: call or 4-bet depending on SPR
    if hand_rank >= 6:
        spr_after_call = (eff_stack_bb - (fourbet_size / 2)) / pot_before if pot_before > 0 else 3
        if spr_after_call < 2.5:
            # SPR is low enough after 4-bet that we should jam/call
            return (
                'fourbet_value',
                f'Strong hand (rank={hand_rank}): 4-bet commits stack — SPR post-4b is low.'
            )
        return (
            'call',
            f'Strong hand (rank={hand_rank}): call and play postflop. '
            f'Equity {hero_equity:.0%} >= required {req_eq:.0%}.'
        )

    # Wide squeeze range: villain is bluffing too often → 4-bet bluff or wide call
    bluff_ev = _fourbet_bluff_ev(pot_before, fourbet_size, villain_fold_to_4b, hero_equity)
    if villain_squeeze_pct >= 0.10 and villain_fold_to_4b >= 0.55 and hand_rank >= 3:
        if bluff_ev > 0:
            return (
                'fourbet_bluff',
                f'Wide villain squeeze ({villain_squeeze_pct:.0%}) + high fold-to-4b ({villain_fold_to_4b:.0%}): '
                f'4-bet bluff EV = +{bluff_ev:.1f}BB.'
            )

    # Sufficient equity to call
    if hero_equity >= req_eq:
        return (
            'call',
            f'Hero equity {hero_equity:.0%} >= required {req_eq:.0%} '
            f'(dead money improved odds). Call and play postflop.'
        )

    # Below threshold: fold
    return (
        'fold',
        f'Hero equity {hero_equity:.0%} < required {req_eq:.0%}. '
        f'Fold despite dead money. Hand not strong enough vs villain squeeze range.'
    )


@dataclass
class SqueezeDefenseAdvice:
    """Advice for defending against a squeeze (3-bet with dead money)."""
    hero_role: str              # 'original_raiser', 'caller', 'other'
    hero_pos: str
    open_size_bb: float
    n_callers: int
    squeeze_size_bb: float
    eff_stack_bb: float

    # Dead money math
    dead_money_bb: float
    pot_before_hero: float      # pot before hero acts
    call_cost_bb: float
    required_equity: float      # to call (with dead money)
    normal_3bet_req_eq: float   # comparison: what it'd be without dead money

    # Hero's situation
    hero_hand_class: str
    hero_equity: float
    villain_squeeze_pct: float
    villain_fold_to_4b: float

    # Decision
    action: str                 # 'call', 'fourbet_value', 'fourbet_bluff', 'fold'
    fourbet_size_bb: float
    fourbet_bluff_ev: float    # EV of 4-bet bluff if applicable
    equity_saved_by_dead_money: float  # how much lower req_eq is vs no dead money

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_squeeze_defense(
    hero_role: str = 'original_raiser',
    hero_pos: str = 'CO',
    open_size_bb: float = 2.5,
    n_callers: int = 1,
    squeeze_size_bb: float = 12.0,
    hero_hand_class: str = 'medium',
    hero_equity: float = 0.45,
    villain_squeeze_pct: float = 0.08,
    villain_fold_to_4b: float = 0.55,
    eff_stack_bb: float = 100.0,
) -> SqueezeDefenseAdvice:
    """
    Advise hero facing a squeeze with dead money.

    Args:
        hero_role:          'original_raiser', 'caller', or 'other'
        hero_pos:           Hero's table position
        open_size_bb:       Original open-raise size in BB
        n_callers:          Number of players who called before villain squeezed
        squeeze_size_bb:    Villain's squeeze size in BB
        hero_hand_class:    Hero's hand strength class
        hero_equity:        Hero's equity vs villain's squeezing range
        villain_squeeze_pct: Villain's 3-bet/squeeze frequency (0-1)
        villain_fold_to_4b: Fraction of time villain folds to 4-bet
        eff_stack_bb:       Effective stack in BB

    Returns:
        SqueezeDefenseAdvice
    """
    rank = _hand_rank(hero_hand_class)
    dead = _dead_money(n_callers, open_size_bb)
    pot_before = _pot_before_hero(open_size_bb, n_callers, squeeze_size_bb)
    call_cost = _call_cost(hero_role, open_size_bb, squeeze_size_bb)
    req_eq = _required_equity(pot_before, call_cost)
    normal_req = _normal_3bet_req_eq(open_size_bb, squeeze_size_bb)
    eq_saved = round(normal_req - req_eq, 4)
    f4b_size = _fourbet_size(squeeze_size_bb, eff_stack_bb)
    f4b_ev = _fourbet_bluff_ev(pot_before, f4b_size, villain_fold_to_4b, hero_equity)

    action, reasoning = _action(
        hero_equity, req_eq, rank, villain_squeeze_pct,
        villain_fold_to_4b, pot_before, f4b_size, eff_stack_bb
    )

    # Tips
    tips = []
    tips.append(
        f'Dead money from {n_callers} caller(s): {dead:.1f}BB. '
        f'Required equity reduced: {normal_req:.0%} (no dead money) → {req_eq:.0%} ({eq_saved:.0%} improvement). '
        f'Call is more attractive than vs a normal 3-bet.'
    )
    if villain_squeeze_pct >= 0.10:
        tips.append(
            f'Villain squeezes {villain_squeeze_pct:.0%} — wide range likely includes many bluffs. '
            f'Defend wider: call with hands you might fold vs 8% squeeze. '
            f'4-bet bluff viable if villain folds {villain_fold_to_4b:.0%} to 4-bets.'
        )
    if hero_role == 'caller':
        tips.append(
            'As a caller (not original raiser): you will be OOP vs the squeezer. '
            'Need extra equity to compensate for positional disadvantage. '
            'Call only with hands that play well in 3-bet pot OOP (sets, straights, big pairs).'
        )
    if action == 'fourbet_value':
        tips.append(
            f'4-bet to {f4b_size:.1f}BB ({f4b_size/open_size_bb:.1f}x open). '
            f'If villain 5-bets jam, you are calling off — confirm hand is strong enough.'
        )
    if n_callers >= 2:
        tips.append(
            f'{n_callers} callers = significant dead money ({dead:.1f}BB). '
            f'Even marginal hands become profitable calls. '
            f'Speculative hands (suited connectors, small pairs) gain implied odds value.'
        )

    return SqueezeDefenseAdvice(
        hero_role=hero_role,
        hero_pos=hero_pos,
        open_size_bb=round(open_size_bb, 1),
        n_callers=n_callers,
        squeeze_size_bb=round(squeeze_size_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        dead_money_bb=dead,
        pot_before_hero=pot_before,
        call_cost_bb=round(call_cost, 1),
        required_equity=req_eq,
        normal_3bet_req_eq=normal_req,
        hero_hand_class=hero_hand_class,
        hero_equity=round(hero_equity, 3),
        villain_squeeze_pct=round(villain_squeeze_pct, 3),
        villain_fold_to_4b=round(villain_fold_to_4b, 3),
        action=action,
        fourbet_size_bb=f4b_size,
        fourbet_bluff_ev=f4b_ev,
        equity_saved_by_dead_money=eq_saved,
        reasoning=reasoning,
        tips=tips,
    )


def squeeze_defense_one_liner(result: SqueezeDefenseAdvice) -> str:
    return (
        f'[SQD {result.hero_role[:4]}@{result.hero_pos}|{result.n_callers}caller] '
        f'{result.action.upper()} | '
        f'req={result.required_equity:.0%}(no_dm={result.normal_3bet_req_eq:.0%}) | '
        f'dead={result.dead_money_bb:.1f}BB | '
        f'saved={result.equity_saved_by_dead_money:.0%}'
    )
