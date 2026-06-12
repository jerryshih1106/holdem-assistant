"""
EV Sensitivity Analyzer (ev_sensitivity_analyzer.py)

For any poker decision, determines WHICH uncertain input matters most.
When you are uncertain about multiple factors (equity, fold equity, pot size),
this module shows how the EV changes as each factor varies -- revealing
which estimate you most need to get right.

CORE INSIGHT:
  A decision is "robust" if EV remains positive even when your estimates
  are off by 10-20%. A decision is "fragile" if small errors flip it.

EV FORMULA (bet/raise):
  EV = fold_eq * pot + (1 - fold_eq) * (equity * pot_after - call_size)
  where pot_after = pot + 2 * bet_size

SENSITIVITIES (partial derivatives):
  dEV/d(equity)   = (1 - fold_eq) * pot_after       [equity matters more in called pots]
  dEV/d(fold_eq)  = pot - (1 - equity) * pot_after  [fold eq matters more in thin spots]
  dEV/d(pot)      = fold_eq + (1 - fold_eq) * equity [always positive]

KEY METRIC: Which input, if off by 5%, flips the EV sign?
  If equity is the key: use hand reading / blockers to get accurate estimate
  If fold_eq is key: use villain stats / board read for fold tendency

Usage:
    from poker.ev_sensitivity_analyzer import analyze_ev_sensitivity, EVSensitivityResult, evs_one_liner

    result = analyze_ev_sensitivity(
        pot_bb=20.0,
        bet_bb=15.0,
        hero_equity=0.35,
        fold_equity=0.40,
        call_bb=15.0,
    )
    print(evs_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# --------------------------------------------------------------------------
# EV calculation
# --------------------------------------------------------------------------

def _bet_ev(pot: float, bet: float, equity: float, fold_eq: float) -> float:
    """EV of a bet: fold_eq * pot + (1-fold_eq) * (equity * pot_after - bet)."""
    pot_after = pot + 2 * bet
    return round(fold_eq * pot + (1 - fold_eq) * (equity * pot_after - bet), 4)


def _call_ev(pot: float, call: float, equity: float) -> float:
    """EV of a call: equity * (pot + call) - call."""
    return round(equity * (pot + call) - call, 4)


# --------------------------------------------------------------------------
# Sensitivity analysis
# --------------------------------------------------------------------------

def _sensitivity_bet(
    pot: float, bet: float, equity: float, fold_eq: float,
    delta: float = 0.05,
) -> Dict[str, float]:
    """
    Partial sensitivity: how much does EV change per unit change in each input?
    Uses finite differences.
    """
    base = _bet_ev(pot, bet, equity, fold_eq)

    # dEV per 1% change in equity
    ev_hi = _bet_ev(pot, bet, min(1.0, equity + delta), fold_eq)
    ev_lo = _bet_ev(pot, bet, max(0.0, equity - delta), fold_eq)
    d_equity = (ev_hi - ev_lo) / (2 * delta)

    # dEV per 1% change in fold_equity
    fe_hi = _bet_ev(pot, bet, equity, min(1.0, fold_eq + delta))
    fe_lo = _bet_ev(pot, bet, equity, max(0.0, fold_eq - delta))
    d_fold_eq = (fe_hi - fe_lo) / (2 * delta)

    # dEV per 1BB change in pot
    pot_hi = _bet_ev(pot + delta * 10, bet, equity, fold_eq)
    pot_lo = _bet_ev(max(0.0, pot - delta * 10), bet, equity, fold_eq)
    d_pot = (pot_hi - pot_lo) / (2 * delta * 10)

    return {
        'base_ev': round(base, 3),
        'd_equity': round(d_equity, 3),     # BB per 1% equity improvement
        'd_fold_eq': round(d_fold_eq, 3),   # BB per 1% fold equity improvement
        'd_pot': round(d_pot, 3),            # BB per 1BB more pot
    }


def _sensitivity_call(
    pot: float, call: float, equity: float,
    delta: float = 0.05,
) -> Dict[str, float]:
    base = _call_ev(pot, call, equity)
    ev_hi = _call_ev(pot, call, min(1.0, equity + delta))
    ev_lo = _call_ev(pot, call, max(0.0, equity - delta))
    d_equity = (ev_hi - ev_lo) / (2 * delta)
    pot_hi = _call_ev(pot + delta * 10, call, equity)
    pot_lo = _call_ev(max(0.0, pot - delta * 10), call, equity)
    d_pot = (pot_hi - pot_lo) / (2 * delta * 10)
    return {
        'base_ev': round(base, 3),
        'd_equity': round(d_equity, 3),
        'd_fold_eq': 0.0,     # calls have no fold equity component
        'd_pot': round(d_pot, 3),
    }


def _breakeven_equity_bet(pot: float, bet: float, fold_eq: float) -> float:
    """Equity where EV(bet) = 0: fold_eq*pot + (1-fold_eq)*(eq*pot_after - bet) = 0"""
    pot_after = pot + 2 * bet
    denom = (1 - fold_eq) * pot_after
    if denom <= 0:
        return 0.0
    be = (bet * (1 - fold_eq) - fold_eq * pot) / denom
    return round(max(0.0, min(1.0, be)), 4)


def _breakeven_fold_eq_bet(pot: float, bet: float, equity: float) -> float:
    """Fold equity where EV(bet) = 0."""
    pot_after = pot + 2 * bet
    ev_if_called = equity * pot_after - bet
    if ev_if_called >= 0:
        return 0.0   # profitable even if never folds
    # fold_eq * pot + (1-fold_eq) * ev_if_called = 0
    # fold_eq * (pot - ev_if_called) = -ev_if_called
    denom = pot - ev_if_called
    if denom <= 0:
        return 1.0
    return round(max(0.0, min(1.0, -ev_if_called / denom)), 4)


def _breakeven_equity_call(pot: float, call: float) -> float:
    """Equity where EV(call) = 0: eq*(pot+call) = call -> eq = call/(pot+call)."""
    total = pot + call
    if total <= 0:
        return 0.5
    return round(call / total, 4)


# --------------------------------------------------------------------------
# Dataclass
# --------------------------------------------------------------------------

@dataclass
class EVSensitivityResult:
    # Inputs
    action: str             # 'bet', 'call', 'raise'
    pot_bb: float
    bet_bb: float           # bet size (0 for calls)
    call_bb: float          # call size (= bet_bb for calls)
    hero_equity: float
    fold_equity: float

    # Base EV
    base_ev: float
    decision: str           # 'bet/raise', 'call', 'check/fold'

    # Sensitivities (BB gained per 1% improvement in each factor)
    sensitivity_equity: float
    sensitivity_fold_eq: float
    sensitivity_pot: float

    # Breakeven thresholds
    breakeven_equity: float     # min equity needed
    breakeven_fold_eq: float    # min fold equity needed (bet/raise only)

    # Key finding
    most_important_factor: str  # 'equity', 'fold_equity', 'pot'
    robustness: str             # 'robust', 'marginal', 'fragile'
    equity_margin: float        # hero_equity - breakeven_equity
    fold_eq_margin: float       # fold_equity - breakeven_fold_eq

    # Scenario analysis (EV at different equity estimates)
    ev_equity_low: float    # EV if equity is 5% lower
    ev_equity_high: float   # EV if equity is 5% higher
    ev_fold_eq_low: float   # EV if fold equity is 5% lower
    ev_fold_eq_high: float  # EV if fold equity is 5% higher

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Main function
# --------------------------------------------------------------------------

def analyze_ev_sensitivity(
    pot_bb: float = 20.0,
    bet_bb: float = 15.0,
    hero_equity: float = 0.35,
    fold_equity: float = 0.40,
    call_bb: float = 0.0,
    action: str = 'bet',
) -> EVSensitivityResult:
    """
    Analyze which uncertain factor most affects the EV of a decision.

    Args:
        pot_bb:       Current pot in BB
        bet_bb:       Hero's bet/raise size (0 if hero is calling)
        hero_equity:  Hero's equity vs calling range (0-1)
        fold_equity:  Probability villain folds to hero's bet (0-1)
        call_bb:      If hero is calling, the bet size to call (overrides bet_bb)
        action:       'bet', 'raise', or 'call'

    Returns:
        EVSensitivityResult
    """
    is_call = action == 'call'

    if is_call:
        bet_bb_used = 0.0
        call_used = call_bb if call_bb > 0 else bet_bb
        sens = _sensitivity_call(pot_bb, call_used, hero_equity)
        base_ev = sens['base_ev']
        be_eq = _breakeven_equity_call(pot_bb, call_used)
        be_fe = 0.0
        ev_eq_lo = _call_ev(pot_bb, call_used, max(0.0, hero_equity - 0.05))
        ev_eq_hi = _call_ev(pot_bb, call_used, min(1.0, hero_equity + 0.05))
        ev_fe_lo = base_ev    # fold eq irrelevant for calls
        ev_fe_hi = base_ev
    else:
        bet_bb_used = bet_bb
        call_used = bet_bb
        sens = _sensitivity_bet(pot_bb, bet_bb, hero_equity, fold_equity)
        base_ev = sens['base_ev']
        be_eq = _breakeven_equity_bet(pot_bb, bet_bb, fold_equity)
        be_fe = _breakeven_fold_eq_bet(pot_bb, bet_bb, hero_equity)
        ev_eq_lo = _bet_ev(pot_bb, bet_bb, max(0.0, hero_equity - 0.05), fold_equity)
        ev_eq_hi = _bet_ev(pot_bb, bet_bb, min(1.0, hero_equity + 0.05), fold_equity)
        ev_fe_lo = _bet_ev(pot_bb, bet_bb, hero_equity, max(0.0, fold_equity - 0.05))
        ev_fe_hi = _bet_ev(pot_bb, bet_bb, hero_equity, min(1.0, fold_equity + 0.05))

    d_eq = abs(sens['d_equity'])
    d_fe = abs(sens['d_fold_eq'])
    d_pot = abs(sens['d_pot'])

    if d_eq >= d_fe and d_eq >= d_pot:
        most_important = 'equity'
    elif d_fe >= d_eq and d_fe >= d_pot:
        most_important = 'fold_equity'
    else:
        most_important = 'pot'

    eq_margin = round(hero_equity - be_eq, 4)
    fe_margin = round(fold_equity - be_fe, 4) if not is_call else 1.0

    # Robustness: how comfortable is the margin?
    key_margin = eq_margin if most_important == 'equity' else fe_margin
    if key_margin > 0.10:
        robustness = 'robust'
    elif key_margin > 0.03:
        robustness = 'marginal'
    else:
        robustness = 'fragile'

    decision = 'bet/raise' if base_ev > 0 else ('check/fold' if not is_call else 'fold')
    if is_call and base_ev > 0:
        decision = 'call'
    elif is_call:
        decision = 'fold'

    reasoning = (
        f'{action.upper()} {bet_bb_used:.1f}BB into {pot_bb:.1f}BB pot. '
        f'equity={hero_equity:.0%} fold_eq={fold_equity:.0%}. '
        f'Base EV: {base_ev:+.2f}BB. '
        f'Sensitivity: equity={sens["d_equity"]:+.2f}BB/1% | fold_eq={sens["d_fold_eq"]:+.2f}BB/1%. '
        f'Most important: {most_important}. '
        f'Robustness: {robustness} (key margin={key_margin:.1%}).'
    )

    verdict = (
        f'{action.upper()} EV={base_ev:+.2f}BB ({robustness}). '
        f'Most sensitive to {most_important}. '
        f'Be-equity={be_eq:.0%} (margin={eq_margin:+.1%}). '
        f'Decision: {decision.upper()}.'
    )

    tips = []

    if most_important == 'equity':
        tips.append(
            f'EQUITY IS KEY: A 5% equity error changes EV by ~{d_eq*5:.2f}BB. '
            f'Use blockers, board texture, and range analysis to nail the equity estimate. '
            f'Current margin: {eq_margin:.1%} above breakeven ({be_eq:.0%}).'
        )
    elif most_important == 'fold_equity':
        tips.append(
            f'FOLD EQUITY IS KEY: A 5% fold-equity error changes EV by ~{d_fe*5:.2f}BB. '
            f'Use villain WTSD, recent action, and board texture to estimate fold frequency. '
            f'Current margin: {fe_margin:.1%} above breakeven ({be_fe:.0%}).'
        )

    if robustness == 'fragile':
        tips.append(
            f'FRAGILE DECISION: Key margin is only {key_margin:.1%}. '
            f'A small estimation error could flip the EV. '
            f'Consider the default/conservative play unless you have strong reads.'
        )
    elif robustness == 'robust':
        tips.append(
            f'ROBUST DECISION: Key margin is {key_margin:.1%}. '
            f'This decision is correct even if estimates are somewhat off. '
            f'Proceed with confidence.'
        )

    if not is_call:
        tips.append(
            f'EV scenarios: eq-5%={ev_eq_lo:+.2f}BB | base={base_ev:+.2f}BB | eq+5%={ev_eq_hi:+.2f}BB | '
            f'fe-5%={ev_fe_lo:+.2f}BB | fe+5%={ev_fe_hi:+.2f}BB.'
        )

    return EVSensitivityResult(
        action=action,
        pot_bb=round(pot_bb, 2),
        bet_bb=round(bet_bb_used, 2),
        call_bb=round(call_used, 2),
        hero_equity=round(hero_equity, 4),
        fold_equity=round(fold_equity, 4),
        base_ev=round(base_ev, 3),
        decision=decision,
        sensitivity_equity=round(sens['d_equity'], 3),
        sensitivity_fold_eq=round(sens['d_fold_eq'], 3),
        sensitivity_pot=round(sens['d_pot'], 3),
        breakeven_equity=round(be_eq, 4),
        breakeven_fold_eq=round(be_fe, 4),
        most_important_factor=most_important,
        robustness=robustness,
        equity_margin=round(eq_margin, 4),
        fold_eq_margin=round(fe_margin, 4),
        ev_equity_low=round(ev_eq_lo, 3),
        ev_equity_high=round(ev_eq_hi, 3),
        ev_fold_eq_low=round(ev_fe_lo, 3),
        ev_fold_eq_high=round(ev_fe_hi, 3),
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def evs_one_liner(r: EVSensitivityResult) -> str:
    return (
        f'[EVS {r.action.upper()}|{r.pot_bb:.0f}BB pot] '
        f'{r.decision.upper()} ev={r.base_ev:+.2f}BB | '
        f'key_factor={r.most_important_factor} margin={r.equity_margin:+.1%} | '
        f'robustness={r.robustness}'
    )
