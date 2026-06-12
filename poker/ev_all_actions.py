"""
All-Actions EV Comparator (ev_all_actions.py)

Shows the EV of every available action side-by-side in one snapshot:
  FOLD, CHECK/CALL, small bet, medium bet, large bet, all-in

This is the complete decision dashboard: hero can see at a glance which
action has the highest EV and by how much, rather than reasoning through
each option separately.

Key formulas:
  EV(fold)   = 0  (net neutral — hero gets no more chips from pot)
  EV(check)  = equity × pot  (no additional investment)
  EV(call)   = equity × (pot + 2*call) - call  (pot grows by call on each side)
  EV(bet X)  = f(X) × pot + (1-f(X)) × (equity × (pot+2X) - X)
               where f(X) = estimated fold frequency at size X

Fold frequency model:
  f(X) = base_fold × multiplier(X/pot)
  base_fold depends on villain VPIP/AF
  multiplier curves: 0.33pot → 0.7x, 0.5pot → 1.0x, 0.75pot → 1.3x, 1.0x pot → 1.6x, 1.5x → 2.0x

Note: EV is relative to folding (EV=0 is the fold baseline).
Positive EV = action wins more than folding.
Negative EV = action loses money relative to folding (fold is correct).

Usage:
    from poker.ev_all_actions import compare_all_actions, AllActionsEV
    result = compare_all_actions(
        hero_equity=0.65,
        pot_bb=20.0,
        call_bb=0.0,       # 0 if no bet to call (hero acts first)
        eff_stack_bb=80.0,
        villain_vpip=0.30,
        villain_af=2.0,
        villain_wtsd=0.32,
        street='turn',
    )
    print(result.best_action, result.best_ev_bb)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ─── Fold frequency model ────────────────────────────────────────────────────

_FOLD_MULT = {
    0.25: 0.55,
    0.33: 0.75,
    0.50: 1.00,
    0.60: 1.15,
    0.75: 1.30,
    1.00: 1.55,
    1.25: 1.75,
    1.50: 1.95,
    2.00: 2.20,
}


def _interpolate_fold_mult(bet_pct: float) -> float:
    keys = sorted(_FOLD_MULT.keys())
    if bet_pct <= keys[0]:
        return _FOLD_MULT[keys[0]]
    if bet_pct >= keys[-1]:
        return _FOLD_MULT[keys[-1]]
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= bet_pct <= hi:
            t = (bet_pct - lo) / (hi - lo)
            return _FOLD_MULT[lo] + t * (_FOLD_MULT[hi] - _FOLD_MULT[lo])
    return 1.0


def _base_fold_freq(villain_vpip: float, villain_af: float, villain_wtsd: float) -> float:
    """Base fold frequency vs a 50% pot bet."""
    # Tighter villains fold more; higher WTSD villains fold less
    base = 0.50
    vpip_adj  = (villain_vpip - 0.30) * -0.50   # loose → lower fold
    af_adj    = (villain_af - 2.0) * -0.05       # aggressive → slightly lower fold (call+raise)
    wtsd_adj  = (villain_wtsd - 0.30) * -0.40   # high WTSD → much lower fold
    return round(max(0.10, min(0.85, base + vpip_adj + af_adj + wtsd_adj)), 3)


def _fold_freq(bet_pct: float, base_fold: float) -> float:
    return min(0.95, base_fold * _interpolate_fold_mult(bet_pct))


# ─── EV calculations ─────────────────────────────────────────────────────────

def _ev_fold() -> float:
    return 0.0


def _ev_check(hero_equity: float, pot_bb: float) -> float:
    """EV of checking (no additional investment)."""
    return round(hero_equity * pot_bb, 3)


def _ev_call(hero_equity: float, pot_bb: float, call_bb: float) -> float:
    """EV of calling villain's bet."""
    if call_bb <= 0:
        return _ev_check(hero_equity, pot_bb)
    total_pot = pot_bb + 2 * call_bb
    return round(hero_equity * total_pot - call_bb, 3)


def _ev_bet(hero_equity: float, pot_bb: float, bet_bb: float,
            base_fold: float) -> float:
    """EV of betting bet_bb into pot_bb."""
    bet_pct = bet_bb / pot_bb if pot_bb > 0 else 0.5
    fold_f = _fold_freq(bet_pct, base_fold)
    pot_after_call = pot_bb + 2 * bet_bb
    ev = fold_f * pot_bb + (1 - fold_f) * (hero_equity * pot_after_call - bet_bb)
    return round(ev, 3)


def _ev_allin(hero_equity: float, pot_bb: float, eff_stack_bb: float,
              base_fold: float) -> float:
    bet_bb = eff_stack_bb
    bet_pct = bet_bb / pot_bb if pot_bb > 0 else 1.0
    fold_f = min(0.80, _fold_freq(bet_pct, base_fold))
    total_pot = pot_bb + 2 * bet_bb
    ev = fold_f * pot_bb + (1 - fold_f) * (hero_equity * total_pot - bet_bb)
    return round(ev, 3)


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ActionEV:
    action: str
    bet_pct: float   # 0 for fold/check/call
    bet_bb: float
    fold_freq: float
    ev_bb: float
    label: str


@dataclass
class AllActionsEV:
    """Complete EV comparison for all available actions."""
    hero_equity: float
    pot_bb: float
    call_bb: float
    eff_stack_bb: float
    street: str

    # All action EVs ranked best to worst
    actions: List[ActionEV]
    best_action: str
    best_ev_bb: float

    # Comparative
    ev_check_or_call: float
    ev_best_bet: float
    best_bet_pct: float

    # Villain model
    base_fold_freq: float
    villain_model_note: str

    # Summary
    summary: str


def compare_all_actions(
    hero_equity: float,
    pot_bb: float,
    call_bb: float = 0.0,
    eff_stack_bb: float = 100.0,
    villain_vpip: float = 0.30,
    villain_af: float = 2.0,
    villain_wtsd: float = 0.32,
    street: str = 'flop',
    include_allin: bool = True,
) -> AllActionsEV:
    """
    Compare EV of all available actions in one call.

    Args:
        hero_equity:  Hero's equity vs villain's current range (0-1)
        pot_bb:       Pot size in BB
        call_bb:      Amount to call (0 if hero acts first)
        eff_stack_bb: Effective stack remaining
        villain_vpip: Villain VPIP (0-1)
        villain_af:   Villain aggression factor
        villain_wtsd: Villain went-to-showdown rate
        street:       'flop', 'turn', 'river'
        include_allin: Whether to include all-in in comparison

    Returns:
        AllActionsEV with all actions ranked by EV
    """
    base_fold = _base_fold_freq(villain_vpip, villain_af, villain_wtsd)

    # Determine if hero is facing a bet (call available) or acting first (bet available)
    facing_bet = call_bb > 0.0

    actions_list = []

    # 1. FOLD
    actions_list.append(ActionEV(
        action='fold', bet_pct=0.0, bet_bb=0.0,
        fold_freq=1.0, ev_bb=_ev_fold(),
        label='FOLD  (baseline = 0)',
    ))

    if facing_bet:
        # 2. CALL
        ev_c = _ev_call(hero_equity, pot_bb, call_bb)
        actions_list.append(ActionEV(
            action='call', bet_pct=call_bb / pot_bb if pot_bb > 0 else 0,
            bet_bb=call_bb, fold_freq=0.0, ev_bb=ev_c,
            label=f'CALL  {call_bb:.0f}BB',
        ))

        # 3. RAISE sizes
        raise_sizes = [2.2 * call_bb, 3.0 * call_bb, 4.0 * call_bb]
        for raise_bb in raise_sizes:
            if raise_bb <= eff_stack_bb:
                pct = raise_bb / pot_bb if pot_bb > 0 else 0.5
                ev = _ev_bet(hero_equity, pot_bb, raise_bb, base_fold)
                actions_list.append(ActionEV(
                    action=f'raise_{raise_bb:.0f}bb',
                    bet_pct=round(pct, 2), bet_bb=round(raise_bb, 1),
                    fold_freq=round(_fold_freq(pct, base_fold), 3),
                    ev_bb=ev,
                    label=f'RAISE {raise_bb:.0f}BB ({pct:.0%}pot)',
                ))
    else:
        # 2. CHECK
        ev_check = _ev_check(hero_equity, pot_bb)
        actions_list.append(ActionEV(
            action='check', bet_pct=0.0, bet_bb=0.0,
            fold_freq=0.0, ev_bb=ev_check,
            label=f'CHECK (show: +{ev_check:.2f}BB)',
        ))

        # 3. BET sizes: 25%, 33%, 50%, 75%, 100% pot
        bet_pcts = [0.25, 0.33, 0.50, 0.75, 1.00]
        for pct in bet_pcts:
            bet_bb = round(pot_bb * pct, 1)
            if bet_bb > eff_stack_bb:
                break
            fold_f = _fold_freq(pct, base_fold)
            ev = _ev_bet(hero_equity, pot_bb, bet_bb, base_fold)
            actions_list.append(ActionEV(
                action=f'bet_{pct:.0%}pot',
                bet_pct=pct, bet_bb=bet_bb,
                fold_freq=round(fold_f, 3),
                ev_bb=ev,
                label=f'BET   {bet_bb:.1f}BB ({pct:.0%}pot)',
            ))

    # 4. ALL-IN
    if include_allin and eff_stack_bb > 0:
        ev_ai = _ev_allin(hero_equity, pot_bb, eff_stack_bb, base_fold)
        actions_list.append(ActionEV(
            action='allin', bet_pct=eff_stack_bb / pot_bb if pot_bb > 0 else 9.9,
            bet_bb=round(eff_stack_bb, 1), fold_freq=0.0,
            ev_bb=ev_ai,
            label=f'ALLIN {eff_stack_bb:.0f}BB',
        ))

    # Sort best → worst
    actions_list.sort(key=lambda a: a.ev_bb, reverse=True)

    best = actions_list[0]

    # Find best non-allin bet for comparison
    bets = [a for a in actions_list if a.action.startswith('bet_')]
    best_bet = max(bets, key=lambda a: a.ev_bb) if bets else None
    ev_best_bet = best_bet.ev_bb if best_bet else 0.0
    best_bet_pct = best_bet.bet_pct if best_bet else 0.0

    # Check/call EV
    cc = next((a for a in actions_list if a.action in ('check', 'call')), None)
    ev_cc = cc.ev_bb if cc else 0.0

    villain_note = (
        f'Villain model: VPIP={villain_vpip:.0%} AF={villain_af:.1f} WTSD={villain_wtsd:.0%}. '
        f'Base fold to 50%pot bet: {base_fold:.0%}.'
    )

    # Summary line
    margin = best.ev_bb - (actions_list[1].ev_bb if len(actions_list) > 1 else 0)
    summary = (
        f'Best: {best.label.strip()} (EV=+{best.ev_bb:.2f}BB). '
        f'Margin over 2nd: {margin:.2f}BB. '
        f'{"Clear winner." if margin > 1.5 else "Close decision — board and range read matters."}'
    )

    return AllActionsEV(
        hero_equity=round(hero_equity, 3),
        pot_bb=round(pot_bb, 1),
        call_bb=round(call_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        street=street,
        actions=actions_list,
        best_action=best.action,
        best_ev_bb=best.ev_bb,
        ev_check_or_call=ev_cc,
        ev_best_bet=ev_best_bet,
        best_bet_pct=best_bet_pct,
        base_fold_freq=base_fold,
        villain_model_note=villain_note,
        summary=summary,
    )


def all_actions_table(result: AllActionsEV) -> str:
    """Format all actions as a readable table."""
    lines = [f'EV Comparison ({result.street}, pot={result.pot_bb:.0f}BB, eq={result.hero_equity:.0%}):']
    for a in result.actions:
        marker = ' <<' if a.action == result.best_action else '   '
        lines.append(f'  {a.label:<30} EV={a.ev_bb:+6.2f}BB{marker}')
    lines.append(f'  {result.summary}')
    return '\n'.join(lines)


def ev_one_liner(result: AllActionsEV) -> str:
    return (
        f'[EV] best={result.best_action}(+{result.best_ev_bb:.1f}BB) | '
        f'bet={result.ev_best_bet:.1f} chk/call={result.ev_check_or_call:.1f} fold=0 | '
        f'eq={result.hero_equity:.0%}'
    )
