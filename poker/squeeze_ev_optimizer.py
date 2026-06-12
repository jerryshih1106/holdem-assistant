"""
Squeeze EV Optimizer (squeeze_ev_optimizer.py)

Precise EV calculator for preflop squeeze plays. A squeeze occurs when:
  hero 3-bets after an open + one or more callers.

The key advantage: dead money from callers dramatically increases
fold equity value, often making squeezes profitable with any two cards
when villain fold rates are high enough.

KEY FORMULAS:
  dead_money = sum(callers * open_bb) + posted_blinds
  pot_before_squeeze = dead_money + open_bb + hero_invested_bb

  p_all_fold = prod(fold_prob_i for each opponent)
    - opener fold probability: f(stack, position, open_pct, fold_to_3b)
    - each caller fold probability: f(caller_type, stack, call_vs_squeeze)

  EV = p_all_fold * pot_before
     + p_call * postflop_ev_squeeze_pot(equity, position)
     + p_4bet * ev_vs_4bet(hand_rank)

  breakeven_fold = squeeze_size / (squeeze_size + pot_before)

OPTIMAL SQUEEZE SIZE:
  IP:  open * 3.0x (tight) to 3.5x (loose callers)
  OOP: open * 3.5x to 4.2x (need bigger vs callers in position)
  Add 1BB per additional caller past 1

IMPORTANT DISTINCTION FROM squeeze.py / squeeze_advisor.py:
  squeeze.py:         should_squeeze YES/NO + basic sizing
  THIS MODULE:        precise dead money math + per-villain fold model +
                      optimal size curve + BB/100 impact + EV breakdown

Usage:
    from poker.squeeze_ev_optimizer import optimize_squeeze, SqueezeEVResult, sqz_one_liner

    result = optimize_squeeze(
        hero_position='BTN',
        hero_hand_rank_pct=0.72,       # KQs level
        opener_position='UTG',
        opener_open_bb=2.5,
        opener_fold_to_3b=0.55,
        n_callers=2,
        caller_avg_fold_to_squeeze=0.62,
        effective_stack_bb=100.0,
        is_ip=True,
    )
    print(sqz_one_liner(result))
"""

import math
from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# Opponent fold probability models
# --------------------------------------------------------------------------

# Opener fold-to-3bet by position (GTO baseline)
_OPENER_FOLD_TO_3B_GTO = {
    'UTG':  0.55,
    'UTG1': 0.52,
    'MP':   0.50,
    'HJ':   0.48,
    'CO':   0.45,
    'BTN':  0.43,
    'SB':   0.40,
}

# Caller fold-to-squeeze baseline (callers have wider ranges, fold more to squeeze)
_CALLER_FOLD_TO_SQUEEZE_BASE = 0.72   # callers typically fold ~70-75% to squeeze

def _opener_fold_prob(
    position: str,
    fold_to_3b: float,
    stack_bb: float,
) -> float:
    """Opener's probability of folding to the squeeze."""
    gto = _OPENER_FOLD_TO_3B_GTO.get(position.upper(), 0.50)
    # Actual fold rate vs GTO
    base = fold_to_3b if fold_to_3b > 0 else gto
    # Short stack: less likely to fold (pot committed)
    if stack_bb <= 20:
        stack_adj = -0.10
    elif stack_bb <= 35:
        stack_adj = -0.05
    else:
        stack_adj = 0.0
    return round(min(0.90, max(0.15, base + stack_adj)), 3)


def _caller_fold_prob(
    avg_fold_to_squeeze: float,
    n_callers: int,
    caller_vpip: float = 0.30,
) -> float:
    """
    Each caller's individual fold probability to the squeeze.
    Callers have wide ranges (limped/called) → fold more to squeeze.
    """
    base = avg_fold_to_squeeze if avg_fold_to_squeeze > 0 else _CALLER_FOLD_TO_SQUEEZE_BASE
    # More callers → each individual folds slightly less (herding effect)
    herd_adj = -(n_callers - 1) * 0.04
    # Loose callers (high VPIP): somewhat stickier
    vpip_adj = -(caller_vpip - 0.30) * 0.20
    return round(min(0.88, max(0.30, base + herd_adj + vpip_adj)), 3)


def _p_all_fold(
    opener_fold: float,
    caller_fold_each: float,
    n_callers: int,
) -> float:
    """Probability ALL opponents fold to the squeeze."""
    p = opener_fold
    for _ in range(n_callers):
        p *= caller_fold_each
    return round(p, 4)


def _dead_money(
    opener_open_bb: float,
    n_callers: int,
    hero_position: str,
) -> float:
    """Dead money in pot before hero squeezes."""
    # Blinds: 0.5 + 1.0 = 1.5 always in
    blinds = 1.5
    # Opener's raise
    opener_contrib = opener_open_bb
    # Each caller contributes same amount
    caller_contrib = n_callers * opener_open_bb
    # Hero's prior investment (if in blinds, already put in 0.5 or 1.0)
    if hero_position.upper() == 'BB':
        hero_prior = 1.0
    elif hero_position.upper() == 'SB':
        hero_prior = 0.5
    else:
        hero_prior = 0.0

    pot = blinds + opener_contrib + caller_contrib
    return round(pot - hero_prior, 2)


def _squeeze_size(
    opener_open_bb: float,
    n_callers: int,
    is_ip: bool,
    hero_position: str,
) -> float:
    """Recommended squeeze sizing in BB."""
    base = opener_open_bb * (3.0 if is_ip else 3.8)
    # Add 1BB per caller beyond 1
    extra = max(0, n_callers - 1) * 1.0
    # SB squeeze is bigger (more OOP)
    if hero_position.upper() == 'SB':
        extra += 1.0
    return round(base + extra, 1)


def _equity_in_squeezed_pot(
    hero_rank_pct: float,
    n_callers: int,
    opener_fold_prob: float,
) -> float:
    """
    Hero's approximate equity in the squeeze pot if called.
    When called, villain typically has tight continuing range.
    """
    # Base: rank pct maps to equity vs continuing range
    base_eq = 0.30 + hero_rank_pct * 0.38

    # Multiple callers → someone has a hand → lower equity
    multiway_adj = -(n_callers - 1) * 0.03

    # Tight opener (high fold) → when they DON'T fold they have very strong hand
    if opener_fold_prob >= 0.60:
        tight_adj = -0.03  # when called, villain has premium hand
    else:
        tight_adj = 0.02   # loose opener calls with wider range = better equity for hero

    # Strong hand overrides
    if hero_rank_pct >= 0.98:    # AA
        base_eq = 0.76
    elif hero_rank_pct >= 0.96:   # KK
        base_eq = 0.70
    elif hero_rank_pct >= 0.93:   # QQ
        base_eq = 0.62
    elif hero_rank_pct >= 0.90:   # JJ
        base_eq = 0.56
    elif hero_rank_pct >= 0.87:   # AQs
        base_eq = 0.52

    adj = base_eq + multiway_adj + tight_adj
    return round(min(0.85, max(0.25, adj)), 3)


def _postflop_ev_squeezed(
    hero_equity: float,
    squeeze_bb: float,
    opener_open_bb: float,
    dead_money: float,
    is_ip: bool,
) -> float:
    """EV when villain calls the squeeze and hero plays a squeeze pot."""
    # Squeeze pot size (dead money + squeeze + caller's call)
    squeeze_pot = dead_money + squeeze_bb * 2  # approximate
    # Postflop edge: eq * pot - invested
    pos_mult = 1.05 if is_ip else 0.80
    ev = (hero_equity - 0.50) * squeeze_pot * pos_mult
    return round(ev, 2)


def _ev_vs_4bet(
    hero_rank_pct: float,
    squeeze_bb: float,
    effective_stack_bb: float,
) -> float:
    """EV when villain 4-bets hero's squeeze."""
    if hero_rank_pct >= 0.97:  # AA/KK: jam/call 4-bet
        jam_eq = 0.80 - (1.0 - hero_rank_pct) * 5
        jam_pot = effective_stack_bb * 2
        return round(jam_eq * jam_pot - effective_stack_bb, 2)
    elif hero_rank_pct >= 0.93:  # QQ/JJ: tough spot, often fold
        return round(-squeeze_bb * 0.90, 2)
    else:
        return round(-squeeze_bb * 0.85, 2)


def _ev_squeeze(
    p_all_fold: float,
    p_one_calls: float,
    p_4bet: float,
    dead_money: float,
    squeeze_bb: float,
    postflop_ev: float,
    ev_4bet: float,
) -> float:
    """Total EV of squeezing."""
    ev_fold_comp = p_all_fold * dead_money
    ev_call_comp = p_one_calls * postflop_ev
    ev_4bet_comp = p_4bet * ev_4bet
    # Net: hero invests squeeze_bb, but gets dead_money_won back if fold
    # (already accounted in fold component — dead_money is the pot hero wins)
    total = ev_fold_comp + ev_call_comp + ev_4bet_comp - squeeze_bb * (1 - p_all_fold)
    return round(total, 2)


def _breakeven_fold_pct(
    squeeze_bb: float,
    dead_money: float,
) -> float:
    """Fold % needed for pure fold-equity to cover squeeze investment."""
    return round(squeeze_bb / (squeeze_bb + dead_money), 3)


@dataclass
class SqueezeEVResult:
    # Inputs
    hero_position: str
    hero_hand_rank_pct: float
    opener_position: str
    opener_open_bb: float
    opener_fold_to_3b: float
    n_callers: int
    caller_avg_fold_to_squeeze: float
    effective_stack_bb: float
    is_ip: bool

    # Dead money and sizing
    dead_money_bb: float
    squeeze_size_bb: float
    pot_before_squeeze_bb: float   # dead money + anything hero invested before

    # Fold probabilities
    opener_fold_pct: float
    caller_fold_pct_each: float
    p_all_fold: float              # probability ALL opponents fold

    # EV breakdown
    ev_fold_component: float       # p_fold * dead_money
    ev_call_component: float       # p_call * postflop_ev
    ev_4bet_component: float       # p_4bet * ev_vs_4bet
    ev_total: float                # total squeeze EV
    ev_per_100_bb100: float        # EV per 100 squeeze attempts in BB/100

    # Benchmarks
    ev_fold_only: float            # EV if we only count fold equity (no postflop)
    breakeven_fold_pct: float      # minimum all-fold% to cover squeeze cost
    fold_surplus: float            # p_all_fold - breakeven_fold_pct

    # Hero equity
    hero_equity_if_called: float

    # Decision
    squeeze_recommended: bool
    decision: str           # 'squeeze_value' / 'squeeze_bluff' / 'squeeze_marginal' / 'fold' / 'call'
    confidence: str
    squeeze_type: str       # 'strong_value' / 'light_value' / 'semibluff' / 'pure_bluff'

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def optimize_squeeze(
    hero_position: str = 'BTN',
    hero_hand_rank_pct: float = 0.72,
    opener_position: str = 'UTG',
    opener_open_bb: float = 2.5,
    opener_fold_to_3b: float = 0.55,
    n_callers: int = 2,
    caller_avg_fold_to_squeeze: float = 0.65,
    effective_stack_bb: float = 100.0,
    is_ip: bool = True,
    villain_4bet_pct: float = 0.08,
    caller_vpip: float = 0.30,
) -> SqueezeEVResult:
    """
    Calculate precise EV of a preflop squeeze.

    Args:
        hero_position:              Hero's position (BTN/CO/SB/BB etc.)
        hero_hand_rank_pct:         Hand strength (0-1; AA=0.99, 72o=0.01)
        opener_position:            Original raiser's position
        opener_open_bb:             Open raise size in BB
        opener_fold_to_3b:          Opener's fold-to-3-bet stat
        n_callers:                  Number of cold callers between opener and hero
        caller_avg_fold_to_squeeze: Average caller fold-to-squeeze frequency
        effective_stack_bb:         Effective stack in BB
        is_ip:                      True if hero is in position on villain(s)
        villain_4bet_pct:           Estimated 4-bet frequency from opener
        caller_vpip:                Average caller VPIP

    Returns:
        SqueezeEVResult
    """
    hero_pos = hero_position.upper()
    open_pos = opener_position.upper()

    # Fold probabilities
    opener_fold = _opener_fold_prob(open_pos, opener_fold_to_3b, effective_stack_bb)
    each_caller_fold = _caller_fold_prob(caller_avg_fold_to_squeeze, n_callers, caller_vpip)
    p_fold = _p_all_fold(opener_fold, each_caller_fold, n_callers)

    # Pot / sizing
    dm = _dead_money(opener_open_bb, n_callers, hero_pos)
    sqz_sz = _squeeze_size(opener_open_bb, n_callers, is_ip, hero_pos)

    # Equity if called
    eq_called = _equity_in_squeezed_pot(hero_hand_rank_pct, n_callers, opener_fold)

    # Probabilities: fold / call / 4-bet
    p_4b = villain_4bet_pct * (1 - p_fold)   # 4-bet is conditional on not folding
    p_call = max(0.0, 1.0 - p_fold - p_4b)

    # EV components
    ev_fold_comp = round(p_fold * dm, 2)
    ev_call_comp_val = _postflop_ev_squeezed(eq_called, sqz_sz, opener_open_bb, dm, is_ip)
    ev_call_comp = round(p_call * ev_call_comp_val, 2)
    ev_4b_comp_val = _ev_vs_4bet(hero_hand_rank_pct, sqz_sz, effective_stack_bb)
    ev_4b_comp = round(p_4b * ev_4b_comp_val, 2)

    ev_total = _ev_squeeze(p_fold, p_call, p_4b, dm, sqz_sz, ev_call_comp_val, ev_4b_comp_val)

    # BB/100 impact: assume hero squeezes this spot ~5% of hands
    ev_bb100 = round(ev_total * 5.0, 2)  # approximate: 5 squeezes per 100 hands in this spot

    # Fold-only EV
    ev_fold_only = round(p_fold * dm - sqz_sz * (1 - p_fold), 2)
    be_fold = _breakeven_fold_pct(sqz_sz, dm)
    fold_surplus = round(p_fold - be_fold, 3)

    # Decision
    if hero_hand_rank_pct >= 0.95:
        sq_type = 'strong_value'
    elif hero_hand_rank_pct >= 0.85:
        sq_type = 'light_value'
    elif hero_hand_rank_pct >= 0.55:
        sq_type = 'semibluff'
    else:
        sq_type = 'pure_bluff'

    if ev_total > 2.0:
        decision = 'squeeze_value' if sq_type in ('strong_value', 'light_value') else 'squeeze_bluff'
        conf = 'high'
    elif ev_total > 0.50:
        decision = 'squeeze_value' if sq_type in ('strong_value', 'light_value') else 'squeeze_bluff'
        conf = 'medium'
    elif ev_total > -0.50:
        decision = 'squeeze_marginal'
        conf = 'low'
    elif ev_fold_only > 0 and sq_type == 'pure_bluff':
        decision = 'fold'
        conf = 'medium'
    else:
        decision = 'fold' if sq_type == 'pure_bluff' else 'call'
        conf = 'medium'

    sq_recommended = decision in ('squeeze_value', 'squeeze_bluff')

    reasoning = (
        f'Squeeze from {hero_pos} vs {open_pos}({opener_open_bb:.1f}BB)+{n_callers}caller(s). '
        f'Dead money={dm:.1f}BB squeeze_size={sqz_sz:.1f}BB. '
        f'P(all_fold)={p_fold:.0%} (opener={opener_fold:.0%} each_caller={each_caller_fold:.0%}). '
        f'EV={ev_total:+.2f}BB (fold={ev_fold_comp:+.2f} call={ev_call_comp:+.2f} 4b={ev_4b_comp:+.2f}). '
        f'Breakeven fold={be_fold:.0%}. Type: {sq_type}. Decision: {decision}.'
    )

    verdict = (
        f'[SQZ {hero_pos}|{n_callers}callers|{sq_type}] {decision.upper()} ({conf}) | '
        f'ev={ev_total:+.2f}BB dm={dm:.1f}BB sz={sqz_sz:.1f}BB | '
        f'p_fold={p_fold:.0%} be={be_fold:.0%}'
    )

    tips = []

    # Dead money tip
    tips.append(
        f'DEAD MONEY ADVANTAGE: {dm:.1f}BB in pot before squeeze. '
        f'P(all fold)={p_fold:.0%}: opener folds {opener_fold:.0%}, each caller folds {each_caller_fold:.0%}. '
        f'Pure fold EV={ev_fold_only:+.2f}BB. Need {be_fold:.0%} fold rate to break even on squeeze investment.'
    )

    # EV breakdown
    tips.append(
        f'EV BREAKDOWN: fold={ev_fold_comp:+.2f}BB call={ev_call_comp:+.2f}BB 4bet={ev_4b_comp:+.2f}BB. '
        f'Total={ev_total:+.2f}BB. Fold surplus={fold_surplus:+.0%} over breakeven.'
    )

    # Number of callers impact
    if n_callers >= 2:
        tips.append(
            f'{n_callers} CALLERS = MORE DEAD MONEY: '
            f'{n_callers} cold callers add {n_callers * opener_open_bb:.1f}BB dead money. '
            f'More callers = larger squeeze size needed but higher fold equity value. '
            f'Squeeze size adjusted to {sqz_sz:.1f}BB (+{n_callers-1:.0f}BB per extra caller).'
        )

    # Hand type guidance
    if sq_type == 'pure_bluff':
        tips.append(
            f'BLUFF SQUEEZE: Hand strength ({hero_hand_rank_pct:.0%}) relies on fold equity. '
            f'Fold EV={ev_fold_only:+.2f}BB. '
            f'{"Profitable: fold rate high enough." if ev_fold_only > 0 else "Unprofitable: insufficient fold rate - prefer fold or call."}'
        )
    elif sq_type == 'strong_value':
        tips.append(
            f'VALUE SQUEEZE: Strong hand ({hero_hand_rank_pct:.0%}) profits from both fold equity AND equity. '
            f'Can squeeze larger (up to {sqz_sz * 1.2:.0f}BB) vs fish/calling stations. '
            f'Equity when called: {eq_called:.0%}.'
        )

    if not sq_recommended and eq_called >= 0.45:
        tips.append(
            f'ALTERNATIVE - CALL: {hero_pos} EV(squeeze)={ev_total:+.2f}BB. '
            f'Consider calling instead: implied odds from callers in pot, '
            f'avoid 4-bet risk, play postflop with position advantage.'
        )

    return SqueezeEVResult(
        hero_position=hero_pos,
        hero_hand_rank_pct=round(hero_hand_rank_pct, 3),
        opener_position=open_pos,
        opener_open_bb=round(opener_open_bb, 1),
        opener_fold_to_3b=round(opener_fold_to_3b, 3),
        n_callers=n_callers,
        caller_avg_fold_to_squeeze=round(caller_avg_fold_to_squeeze, 3),
        effective_stack_bb=round(effective_stack_bb, 1),
        is_ip=is_ip,
        dead_money_bb=dm,
        squeeze_size_bb=sqz_sz,
        pot_before_squeeze_bb=dm,
        opener_fold_pct=opener_fold,
        caller_fold_pct_each=each_caller_fold,
        p_all_fold=p_fold,
        ev_fold_component=ev_fold_comp,
        ev_call_component=ev_call_comp,
        ev_4bet_component=ev_4b_comp,
        ev_total=ev_total,
        ev_per_100_bb100=ev_bb100,
        ev_fold_only=ev_fold_only,
        breakeven_fold_pct=be_fold,
        fold_surplus=fold_surplus,
        hero_equity_if_called=eq_called,
        squeeze_recommended=sq_recommended,
        decision=decision,
        confidence=conf,
        squeeze_type=sq_type,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sqz_one_liner(r: SqueezeEVResult) -> str:
    return (
        f'[SQZ {r.hero_position}|{r.n_callers}callers|{r.squeeze_type}] '
        f'{r.decision.upper()} ({r.confidence}) | '
        f'ev={r.ev_total:+.2f}BB dm={r.dead_money_bb:.1f}BB sz={r.squeeze_size_bb:.1f}BB | '
        f'p_fold={r.p_all_fold:.0%} be={r.breakeven_fold_pct:.0%}'
    )
