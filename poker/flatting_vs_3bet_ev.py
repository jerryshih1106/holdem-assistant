"""
Flatting vs 3-Bet EV Comparator (flatting_vs_3bet_ev.py)

Answers the question every competent preflop player faces dozens of times
per session: "Should I flat this open or 3-bet?"

Both lines can be +EV. This module computes approximate EV for each
and explains when each is preferred. The key factors are:
  1. Fold equity (how often villain folds to 3-bet)
  2. Position (IP flatting >> OOP flatting)
  3. Hand playability in 3-bet pot vs SRP
  4. Domination risk (AQo vs UTG open)
  5. Stack depth and implied odds

CORE EV MODEL:
  EV(3-bet) = p_fold × dead_money_pot
             + p_call × postflop_ev_3bet_pot(equity, position)
             + p_4bet × ev_vs_4bet(hand_strength)

  EV(flat)  = equity_in_srp × srp_pot_won
             - call_cost
             + position_bonus(is_ip)
             + implied_odds_bonus(nut_potential, stack_depth)
             - domination_penalty(risk_of_dominated)

NOTE: EV values are approximate guide values in BB, not full game-tree
solutions. They capture the material differences between the lines and
help players calibrate toward GTO while exploiting villain tendencies.

IMPORTANT DISTINCTION FROM OTHER MODULES:
  preflop_advisor.py:   general preflop action advice
  bb_defense_optimizer.py: BB defense specifically
  cold_4bet_advisor.py: when to 4-bet facing a 3-bet
  THIS MODULE:          precise flat vs 3-bet comparison for any position

Usage:
    from poker.flatting_vs_3bet_ev import compare_flat_3bet, Flat3BetResult, f3b_one_liner

    result = compare_flat_3bet(
        hero_hand_rank_pct=0.87,   # AQs
        hero_is_ip=True,
        villain_open_bb=2.5,
        villain_open_pct=0.44,     # BTN open
        villain_fold_to_3b=0.55,
        villain_4bet_pct=0.08,
        effective_stack_bb=100.0,
        nut_potential=0.65,        # AQs has decent nut potential
        domination_risk=0.30,      # AQs vs BTN: moderate dom. risk
    )
    print(f3b_one_liner(result))
"""

import math
from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# EV estimation helpers
# --------------------------------------------------------------------------

# 3-bet sizing: IP = 3x, OOP = 3.5x
def _threeb_size(open_bb: float, is_ip: bool) -> float:
    mult = 3.0 if is_ip else 3.5
    return round(open_bb * mult, 1)


# Dead money in pot before hero 3-bets: open_bb + SB (0.5) + BB (1.0) = open_bb + 1.5
def _pot_before_3bet(open_bb: float) -> float:
    return open_bb + 1.5


# Hero equity in 3-bet pot based on hand rank pct vs villain's calling range
# Villain's 3-bet-call range is stronger than typical: they're not folding with nothing
def _equity_in_3bet_pot(hero_rank_pct: float, villain_fold_to_3b: float) -> float:
    """
    When villain calls the 3-bet, their range is strong (usually QQ-/AK range that
    decided to call rather than fold or 4-bet). Adjust hero equity downward vs this
    tighter continuing range.
    """
    # Villain's calling range is strong: filter of all their hands minus folders
    # More folds = remaining callers have wider distribution (some speculators)
    # Less folds = remaining callers are very strong
    caller_range_tightness = 1.0 - villain_fold_to_3b   # fraction that calls+4bets

    # Base equity model: rank pct maps roughly to equity
    base_eq = 0.30 + hero_rank_pct * 0.40

    # Against a tighter calling range (fewer folds), hero equity is lower
    caller_adj = (caller_range_tightness - 0.45) * -0.10
    adj_eq = base_eq + caller_adj

    # Hand-class specific overrides for accuracy
    if hero_rank_pct >= 0.98:    # AA
        adj_eq = 0.78 + villain_fold_to_3b * 0.04
    elif hero_rank_pct >= 0.96:   # KK
        adj_eq = 0.70 + villain_fold_to_3b * 0.03
    elif hero_rank_pct >= 0.93:   # QQ
        adj_eq = 0.62 + villain_fold_to_3b * 0.03
    elif hero_rank_pct >= 0.90:   # JJ
        adj_eq = 0.55 + villain_fold_to_3b * 0.02
    elif hero_rank_pct >= 0.87:   # AQs
        adj_eq = 0.50 + villain_fold_to_3b * 0.02
    elif hero_rank_pct >= 0.83:   # TT/AJs
        adj_eq = 0.48 + villain_fold_to_3b * 0.02
    elif hero_rank_pct >= 0.77:   # KQs/AQo
        adj_eq = 0.44 + villain_fold_to_3b * 0.02
    elif hero_rank_pct >= 0.65:   # 99/KJs
        adj_eq = 0.40 + villain_fold_to_3b * 0.02

    return round(min(0.82, max(0.22, adj_eq)), 3)


def _ev_3bet(
    hero_rank_pct: float,
    hero_is_ip: bool,
    open_bb: float,
    fold_to_3b: float,
    fourbet_pct: float,
    effective_stack_bb: float,
) -> float:
    """Approximate EV of 3-betting in BB."""
    threeb_sz = _threeb_size(open_bb, hero_is_ip)
    pot_before = _pot_before_3bet(open_bb)

    p_fold = fold_to_3b
    p_4bet = fourbet_pct
    p_call = max(0.0, 1.0 - p_fold - p_4bet)

    # Fold component: win the pot minus hero's 3-bet investment
    # Hero puts in threeb_sz, wins pot_before + hero_3bet = pot_before
    # Net = pot_before - threeb_sz (we win the pot, but our 3-bet is in it)
    # Actually: hero invests threeb_sz, pot becomes pot_before + threeb_sz
    # If villain folds, hero wins pot_before (what was there before hero's 3-bet)
    ev_fold_comp = p_fold * pot_before

    # Call component: hero plays 3-bet pot
    pot_3bet = pot_before + threeb_sz + open_bb  # approximate pot in play
    eq = _equity_in_3bet_pot(hero_rank_pct, fold_to_3b)

    # Postflop EV in 3-bet pot = equity * pot - (1-equity) * remaining_stack_at_risk
    # Simplified: EV = (eq - 0.50) * pot_3bet (net relative to breaking even)
    pos_adj = 1.00 if hero_is_ip else 0.75   # OOP plays much worse
    ev_call_comp = p_call * (eq - 0.50) * pot_3bet * pos_adj

    # 4-bet component: hero loses most of 3-bet unless very strong (calls/5-bets)
    if hero_rank_pct >= 0.96:  # KK+: can call 4-bet
        # Jam equity vs 4-bet range (villain usually has QQ+ / AK): rough 55-75% for KK+
        jam_eq = 0.70 + (hero_rank_pct - 0.96) * 3.0  # AA=0.76, KK=0.70
        jam_pot = effective_stack_bb * 2
        ev_4bet_comp = p_4bet * (jam_eq * jam_pot - effective_stack_bb)
    elif hero_rank_pct >= 0.90:  # QQ/JJ: tough spot vs 4-bet, often fold
        ev_4bet_comp = p_4bet * (-threeb_sz * 0.90)   # mostly lose 3-bet
    else:
        # Bluff 3-bet or light value: fold to 4-bet, lose ~85% of 3-bet
        ev_4bet_comp = p_4bet * (-threeb_sz * 0.85)

    # Total EV from hero's perspective (net change from putting in 3-bet)
    ev = ev_fold_comp + ev_call_comp + ev_4bet_comp - threeb_sz * (1 - p_fold)
    return round(ev, 2)


def _ev_flat(
    hero_rank_pct: float,
    hero_is_ip: bool,
    open_bb: float,
    villain_open_pct: float,
    effective_stack_bb: float,
    nut_potential: float,
    domination_risk: float,
    villain_fold_to_3b: float,
) -> float:
    """Approximate EV of flatting the open in BB."""
    call_cost = open_bb - 1.0   # if hero is BB (has 1BB invested); simplify to open_bb for all positions
    srp_pot = open_bb + 1.5     # pot in single-raised pot

    # Hero equity in SRP vs villain's full open range
    base_eq = 0.35 + hero_rank_pct * 0.30  # ranges from 0.35 to 0.65

    # Domination risk: being dominated reduces realized equity
    dom_penalty = domination_risk * 0.08   # max -8% equity if high domination risk

    # Narrow villain range: strong hand vs UTG (tight) → less equity
    # Wide villain range: flatting vs BTN (loose) → more equity due to blockers/dominated villains
    range_adj = (villain_open_pct - 0.28) * 0.05  # adjust for range width

    adj_eq = base_eq + range_adj - dom_penalty

    # Base EV of flatting: equity in pot minus call cost
    # EV = adj_eq * pot_won - (1-adj_eq) * call_cost
    # Expected pot won when winning ~ 2x call_cost (continuation, raised pots)
    avg_pot_won = srp_pot * 1.4   # average pot size through all streets when hero wins

    ev_base = adj_eq * avg_pot_won - call_cost

    # Position bonus: IP flatting is worth significantly more
    if hero_is_ip:
        position_bonus = open_bb * 0.35   # +35% of open in positional EV
    else:
        position_bonus = -open_bb * 0.20  # -20% of open when OOP

    # Implied odds bonus: speculative hands (SC, small pairs) gain from deep stacks
    eff_stacks_ratio = effective_stack_bb / 100.0
    implied_odds_bonus = nut_potential * 0.40 * eff_stacks_ratio

    # For premium hands, flatting loses EV vs building pot with 3-bet
    # This is the "slow play cost" — captured by comparison with 3-bet EV

    ev = ev_base + position_bonus + implied_odds_bonus
    return round(ev, 2)


def _build_3bet_range_note(
    hero_rank_pct: float,
    hero_is_ip: bool,
    fold_to_3b: float,
    domination_risk: float,
) -> str:
    if hero_rank_pct >= 0.95:
        return '3-bet for value (premium hand — build pot + charge draws)'
    elif hero_rank_pct >= 0.87:
        if fold_to_3b >= 0.55:
            return '3-bet for value/semibluff — villain folds enough to make it profitable'
        else:
            return '3-bet or flat — premium enough to extract value but villain calls often'
    elif hero_rank_pct >= 0.55 and fold_to_3b >= 0.58:
        if not hero_is_ip:
            return '3-bet bluff OOP — avoid playing OOP in single-raised pot with marginal hand'
        else:
            return 'Flat preferred IP — better implied odds + position than 3-bet'
    elif domination_risk >= 0.50:
        return 'Caution: high domination risk — 3-bet only vs wide openers (CO/BTN)'
    else:
        return 'Flat to maintain range advantage and use position'


@dataclass
class Flat3BetResult:
    # Inputs
    hero_hand_rank_pct: float
    hero_is_ip: bool
    villain_open_bb: float
    villain_open_pct: float
    villain_fold_to_3b: float
    villain_4bet_pct: float
    effective_stack_bb: float
    nut_potential: float
    domination_risk: float

    # 3-bet analysis
    threeb_size_bb: float
    ev_3bet: float
    eq_in_3bet_pot: float
    threeb_fold_equity_bb: float    # p_fold × dead_money

    # Flat analysis
    call_cost_bb: float
    ev_flat: float
    eq_in_srp: float

    # Comparison
    ev_difference: float        # ev_3bet - ev_flat (positive = 3-bet better)
    recommendation: str         # '3bet_value' / '3bet_bluff' / 'flat' / 'fold' / '3bet_or_flat'
    action_reason: str          # brief reason
    confidence: str             # 'high' / 'medium' / 'low'

    # Guidance
    threeb_range_note: str
    fold_equity_threshold: float    # minimum fold% needed to make 3-bet profitable
    breakeven_fold_pct: float       # fold% at which 3-bet EV = flat EV

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def compare_flat_3bet(
    hero_hand_rank_pct: float = 0.87,
    hero_is_ip: bool = True,
    villain_open_bb: float = 2.5,
    villain_open_pct: float = 0.44,
    villain_fold_to_3b: float = 0.55,
    villain_4bet_pct: float = 0.08,
    effective_stack_bb: float = 100.0,
    nut_potential: float = 0.50,
    domination_risk: float = 0.25,
) -> Flat3BetResult:
    """
    Compare EV of flatting vs 3-betting a preflop open.

    Args:
        hero_hand_rank_pct:  Hero hand percentile (0=worst, 1=best)
                             AA=0.99, KK=0.98, QQ=0.96, JJ=0.93, TT=0.89
                             AKs=0.97, AKo=0.92, AQs=0.87, AQo=0.74, KQs=0.77
                             99=0.83, 88=0.79, 77=0.70, 76s=0.55, 65s=0.52
        hero_is_ip:          True if hero acts after villain postflop
        villain_open_bb:     Villain's open raise size
        villain_open_pct:    Villain's VPIP/open freq from that position
        villain_fold_to_3b:  How often villain folds to 3-bets (0.0-1.0)
        villain_4bet_pct:    How often villain 4-bets (0.0-1.0)
        effective_stack_bb:  Effective stacks before any action
        nut_potential:       Hand's nut potential (1.0=AA/wheel/nut draws, 0=AJo)
                             76s=0.70, AKs=0.65, 99=0.45, KJo=0.25
        domination_risk:     Risk of being dominated by villain's range (0.0-1.0)
                             AQo vs UTG = 0.65, 76s vs BTN = 0.10

    Returns:
        Flat3BetResult
    """
    pos_label = 'IP' if hero_is_ip else 'OOP'

    threeb_sz = _threeb_size(villain_open_bb, hero_is_ip)
    pot_before = _pot_before_3bet(villain_open_bb)
    call_cost = villain_open_bb - 1.0

    # EV calculations
    ev_3b = _ev_3bet(
        hero_rank_pct=hero_hand_rank_pct,
        hero_is_ip=hero_is_ip,
        open_bb=villain_open_bb,
        fold_to_3b=villain_fold_to_3b,
        fourbet_pct=villain_4bet_pct,
        effective_stack_bb=effective_stack_bb,
    )
    ev_fl = _ev_flat(
        hero_rank_pct=hero_hand_rank_pct,
        hero_is_ip=hero_is_ip,
        open_bb=villain_open_bb,
        villain_open_pct=villain_open_pct,
        effective_stack_bb=effective_stack_bb,
        nut_potential=nut_potential,
        domination_risk=domination_risk,
        villain_fold_to_3b=villain_fold_to_3b,
    )

    ev_diff = round(ev_3b - ev_fl, 2)

    eq_3bet = _equity_in_3bet_pot(hero_hand_rank_pct, villain_fold_to_3b)
    eq_srp = round(0.35 + hero_hand_rank_pct * 0.28 + (villain_open_pct - 0.28) * 0.05
                   - domination_risk * 0.08, 3)
    eq_srp = round(min(0.75, max(0.25, eq_srp)), 3)

    fold_equity_won = round(villain_fold_to_3b * pot_before, 2)

    # Breakeven fold% — at what fold rate does 3-bet EV equal flat EV?
    # Approximation: be_fold = (ev_flat + threeb_sz - postflop_gain) / pot_before
    postflop_3b_gain = ev_3b - villain_fold_to_3b * pot_before
    be_fold_num = ev_fl + threeb_sz - postflop_3b_gain
    be_fold_denom = pot_before
    be_fold = round(min(0.90, max(0.20, be_fold_num / be_fold_denom)), 3) if be_fold_denom > 0 else 0.5

    # Minimum fold% for 3-bet bluff to be profitable vs fold (ignoring postflop equity)
    fold_thresh = round(threeb_sz / (threeb_sz + pot_before), 3)

    # Recommendation logic
    if hero_hand_rank_pct >= 0.95:
        rec = '3bet_value'
        reason = f'Premium hand (rank={hero_hand_rank_pct:.0%}): always 3-bet to build pot and charge draws'
        conf = 'high'
    elif hero_hand_rank_pct >= 0.87 and ev_diff > 0.50:
        rec = '3bet_value'
        reason = f'Strong hand with {ev_diff:+.2f}BB EV advantage for 3-betting'
        conf = 'high' if ev_diff > 1.5 else 'medium'
    elif hero_hand_rank_pct >= 0.87 and -0.50 <= ev_diff <= 0.50:
        rec = '3bet_or_flat'
        reason = f'Similar EV lines ({ev_diff:+.2f}BB diff). 3-bet for balance; flat for deception'
        conf = 'low'
    elif hero_hand_rank_pct >= 0.87:
        rec = 'flat'
        reason = f'Strong hand but flat EV superior by {-ev_diff:.2f}BB (IP position advantage)'
        conf = 'medium'
    elif not hero_is_ip and villain_fold_to_3b >= 0.55 and hero_hand_rank_pct >= 0.55:
        rec = '3bet_bluff'
        reason = f'OOP: avoid SRP, 3-bet fold equity={fold_equity_won:.2f}BB. Villain folds {villain_fold_to_3b:.0%}'
        conf = 'medium'
    elif hero_is_ip and ev_fl > ev_3b and nut_potential >= 0.50:
        rec = 'flat'
        reason = f'IP flat: implied odds ({nut_potential:.0%} nut pot.) + position > fold equity gain'
        conf = 'medium'
    elif ev_fl > 0 and ev_fl >= ev_3b:
        rec = 'flat'
        reason = f'Flat EV ({ev_fl:+.2f}BB) > 3-bet EV ({ev_3b:+.2f}BB)'
        conf = 'medium'
    elif ev_3b > 0:
        rec = '3bet_value' if hero_hand_rank_pct >= 0.80 else '3bet_bluff'
        reason = f'3-bet EV ({ev_3b:+.2f}BB) > flat EV ({ev_fl:+.2f}BB)'
        conf = 'medium'
    elif ev_fl <= 0 and ev_3b <= 0:
        rec = 'fold'
        reason = 'Both lines are -EV. Fold unless hand is in defend/balance range'
        conf = 'medium'
    else:
        rec = 'flat'
        reason = f'Marginal: flat preferred ({ev_fl:+.2f}BB vs 3b {ev_3b:+.2f}BB)'
        conf = 'low'

    range_note = _build_3bet_range_note(
        hero_hand_rank_pct, hero_is_ip, villain_fold_to_3b, domination_risk
    )

    reasoning = (
        f'Hero ({hero_hand_rank_pct:.0%} hand) {pos_label} vs {villain_open_bb:.1f}BB open '
        f'({villain_open_pct:.0%} range). '
        f'Villain fold={villain_fold_to_3b:.0%} 4bet={villain_4bet_pct:.0%}. '
        f'EV(3-bet)={ev_3b:+.2f}BB vs EV(flat)={ev_fl:+.2f}BB (diff={ev_diff:+.2f}BB). '
        f'Recommendation: {rec}. Confidence: {conf}.'
    )

    verdict = (
        f'[F3B {pos_label}|{hero_hand_rank_pct:.0%} hand] {rec.upper()} ({conf}) | '
        f'3b_ev={ev_3b:+.2f}BB flat_ev={ev_fl:+.2f}BB diff={ev_diff:+.2f}BB | '
        f'fold_eq={fold_equity_won:.2f}BB'
    )

    tips = []

    # Main recommendation tip
    if rec in ('3bet_value', '3bet_bluff'):
        tips.append(
            f'{"3-BET VALUE" if rec=="3bet_value" else "3-BET BLUFF"}: '
            f'3-bet to {threeb_sz:.1f}BB. '
            f'EV advantage = {ev_diff:+.2f}BB over flatting. '
            f'Fold equity = {fold_equity_won:.2f}BB ({villain_fold_to_3b:.0%} fold). '
            f'{range_note}.'
        )
    elif rec == 'flat':
        tips.append(
            f'FLAT: Call {villain_open_bb:.1f}BB. '
            f'EV advantage = {-ev_diff:+.2f}BB over 3-betting. '
            f'Pot odds: {call_cost:.1f}BB to win ~{pot_before:.1f}BB pot. '
            f'{range_note}.'
        )
    elif rec == '3bet_or_flat':
        tips.append(
            f'MIXED STRATEGY: EV difference is only {abs(ev_diff):.2f}BB. '
            f'3-bet ~{round(villain_fold_to_3b*60):.0f}% for balance, flat rest. '
            f'{range_note}.'
        )
    else:  # fold
        tips.append(
            f'FOLD: Both lines are -EV ({ev_3b:+.2f}BB vs {ev_fl:+.2f}BB). '
            f'Hand is too weak vs this range. '
            f'Include in range only if needed for balance.'
        )

    # OOP warning
    if not hero_is_ip and rec == 'flat':
        tips.append(
            f'OOP CAUTION: Flatting {villain_open_bb:.1f}BB OOP is tricky. '
            f'You will often be at a positional disadvantage postflop. '
            f'Consider 3-betting or folding instead of flatting OOP with marginal hands.'
        )

    # Domination risk warning
    if domination_risk >= 0.45 and hero_hand_rank_pct < 0.90:
        tips.append(
            f'DOMINATION RISK ({domination_risk:.0%}): '
            f'Villain open range ({villain_open_pct:.0%}) contains many hands that dominate yours. '
            f'(e.g., AQo vs UTG might face AK/AJ/AQ more often = bad equity realization). '
            f'Tighten up or 3-bet to fold villain out rather than calling.'
        )

    # Stack depth + implied odds
    if effective_stack_bb >= 100 and nut_potential >= 0.60 and hero_is_ip:
        tips.append(
            f'DEEP STACK BONUS: {effective_stack_bb:.0f}BB deep with nut potential={nut_potential:.0%}. '
            f'Flatting IP gives strong implied odds. '
            f'Aim for implied pot of {effective_stack_bb * 0.3:.0f}BB+ when you hit.'
        )

    # Fold equity threshold info
    tips.append(
        f'3-BET BREAKEVEN: Villain needs to fold {fold_thresh:.0%}+ for pure fold equity to cover 3-bet. '
        f'Actual fold rate={villain_fold_to_3b:.0%}. '
        f'{"Fold equity covers 3-bet cost." if villain_fold_to_3b >= fold_thresh else "Relying on postflop equity — need good hand."}'
    )

    return Flat3BetResult(
        hero_hand_rank_pct=round(hero_hand_rank_pct, 3),
        hero_is_ip=hero_is_ip,
        villain_open_bb=round(villain_open_bb, 1),
        villain_open_pct=round(villain_open_pct, 3),
        villain_fold_to_3b=round(villain_fold_to_3b, 3),
        villain_4bet_pct=round(villain_4bet_pct, 3),
        effective_stack_bb=round(effective_stack_bb, 1),
        nut_potential=round(nut_potential, 3),
        domination_risk=round(domination_risk, 3),
        threeb_size_bb=threeb_sz,
        ev_3bet=ev_3b,
        eq_in_3bet_pot=eq_3bet,
        threeb_fold_equity_bb=fold_equity_won,
        call_cost_bb=round(call_cost, 1),
        ev_flat=ev_fl,
        eq_in_srp=eq_srp,
        ev_difference=ev_diff,
        recommendation=rec,
        action_reason=reason,
        confidence=conf,
        threeb_range_note=range_note,
        fold_equity_threshold=fold_thresh,
        breakeven_fold_pct=be_fold,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def f3b_one_liner(r: Flat3BetResult) -> str:
    pos = 'IP' if r.hero_is_ip else 'OOP'
    return (
        f'[F3B {pos}|{r.hero_hand_rank_pct:.0%} hand] {r.recommendation.upper()} ({r.confidence}) | '
        f'3b_ev={r.ev_3bet:+.2f}BB flat_ev={r.ev_flat:+.2f}BB diff={r.ev_difference:+.2f}BB | '
        f'fold_eq={r.threeb_fold_equity_bb:.2f}BB'
    )
