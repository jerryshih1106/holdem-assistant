"""
Rake Advisor (rake_advisor.py)

Real-money poker tables charge rake on every pot. At micro/small stakes,
rake is typically 3-5% of the pot up to a cap. Ignoring rake converts
many marginally profitable calls into losing plays.

Key adjustments:
  - Effective pot odds: your call buys fewer "real dollars" due to rake
  - EV reduction: every showdown pot is raked
  - Breakeven equity rises with higher rake
  - Marginal bluffs become less profitable (raked when villain folds)

Common rake structures:
  - Micro stakes (NL2-NL10): 5% up to $0.50-$1.00 cap
  - Small stakes (NL25-NL50): 4.5% up to $2-$3 cap
  - Mid stakes (NL100+): 3-4% up to $3-$5 cap
  - Zoom/Fast fold: 5% same cap, but fewer hands per hour
  - Live casino: flat $4-$7 per hand regardless of pot size

Usage:
    from poker.rake_advisor import analyze_rake, RakeAnalysis
    result = analyze_rake(
        pot_bb=20.0,
        call_bb=8.0,
        hero_equity=0.38,
        rake_pct=0.05,
        rake_cap_bb=2.0,
        bb_size_usd=0.02,  # NL2: BB=$0.02
    )
    print(result.action, result.adjusted_equity_needed)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RakeAnalysis:
    """Full rake impact analysis for a pot."""
    # Inputs
    pot_bb: float
    call_bb: float
    hero_equity: float
    rake_pct: float
    rake_cap_bb: float

    # Rake on the pot
    rake_bb: float              # actual rake charged (capped)
    rake_pct_effective: float   # actual rake % after cap

    # Adjusted pot & EV
    pot_after_rake_bb: float           # pot hero wins if they win showdown
    adjusted_pot_odds: float           # call_bb / (pot_after_rake - call_bb)
    breakeven_equity_raw: float        # without rake
    breakeven_equity_raked: float      # with rake — higher than raw

    # EV components
    ev_call_no_rake: float
    ev_call_with_rake: float
    ev_difference: float               # cost of rake on this call

    # Decision
    action: str                        # 'call', 'fold' (with rake considered)
    action_no_rake: str                # what you'd do without rake
    rake_changes_action: bool          # True if rake flips the decision

    # Annualized rake cost
    rake_per_100_hands_bb: float       # estimate BB/100 lost to rake

    reasoning: str
    tips: List[str] = field(default_factory=list)


def _compute_rake(pot_bb: float, rake_pct: float, rake_cap_bb: float) -> float:
    """Rake taken from this pot size (capped)."""
    return min(pot_bb * rake_pct, rake_cap_bb)


def analyze_rake(
    pot_bb: float,
    call_bb: float,
    hero_equity: float,
    rake_pct: float = 0.05,
    rake_cap_bb: float = 2.0,
    bb_size_usd: float = 0.02,
    hands_per_hour: int = 80,
    pots_per_hour: float = 20.0,
) -> RakeAnalysis:
    """
    Analyze the impact of rake on a call decision.

    Args:
        pot_bb:           Pot size before hero's call (in BBs)
        call_bb:          Amount hero must call (BBs)
        hero_equity:      Hero's equity (0-1) from Monte Carlo
        rake_pct:         Site rake percentage (e.g. 0.05 = 5%)
        rake_cap_bb:      Maximum rake in BBs per hand
        bb_size_usd:      Size of 1 BB in USD (for stake context)
        hands_per_hour:   Hands played per hour (for BB/100 estimate)
        pots_per_hour:    Average pots per hour hero is involved in

    Returns:
        RakeAnalysis
    """
    total_pot_if_call = pot_bb + call_bb

    # Rake is charged on the final pot (including call)
    rake_charged = _compute_rake(total_pot_if_call, rake_pct, rake_cap_bb)
    effective_rake_pct = rake_charged / total_pot_if_call if total_pot_if_call > 0 else 0

    pot_after_rake = total_pot_if_call - rake_charged

    # ── EV calculations ────────────────────────────────────────────────────────
    # Correct EV formula:
    #   If hero wins: takes pot_after_rake (net gain = pot_after_rake - call_bb)
    #   If hero loses: loses call_bb
    #   EV = equity*(pot_after_rake - call_bb) - (1-equity)*call_bb
    #      = equity*pot_after_rake - call_bb
    # Without rake: pot_after_rake = total_pot → EV = equity*total_pot - call_bb
    ev_no_rake = hero_equity * total_pot_if_call - call_bb
    breakeven_no_rake = call_bb / total_pot_if_call

    # With rake: hero wins only the raked pot
    ev_with_rake = hero_equity * pot_after_rake - call_bb
    # Breakeven: equity * pot_after_rake = call_bb → equity = call_bb / pot_after_rake
    # Raked breakeven is always higher because pot_after_rake < total_pot
    breakeven_raked = call_bb / pot_after_rake if pot_after_rake > 0 else 1.0

    # Adjusted pot odds = call relative to the raked pot hero can win
    adjusted_pot_odds = call_bb / pot_after_rake if pot_after_rake > 0 else 1.0

    ev_diff = ev_with_rake - ev_no_rake   # negative: rake costs EV

    # ── Decisions ─────────────────────────────────────────────────────────────
    action_no_rake = 'call' if hero_equity >= breakeven_no_rake else 'fold'
    action_with_rake = 'call' if hero_equity >= breakeven_raked else 'fold'
    rake_changes = (action_no_rake != action_with_rake)

    # ── BB/100 rake estimate ───────────────────────────────────────────────────
    # Per 100 hands, estimate avg rake paid in pots hero is involved in
    # avg_pot ≈ 10 BB (rough); rake ≈ min(10*rake_pct, cap)
    avg_pot_estimate = 10.0
    avg_rake_per_pot = _compute_rake(avg_pot_estimate, rake_pct, rake_cap_bb)
    # Hero is involved in ~pots_per_hour of pots; scale to 100 hands
    pots_per_100 = pots_per_hour * (100 / max(hands_per_hour, 1))
    rake_per_100 = avg_rake_per_pot * pots_per_100 * 0.5  # hero wins ~50% of pots

    # ── Tips ──────────────────────────────────────────────────────────────────
    tips = []
    if rake_changes:
        tips.append(
            f'RAKE FLIPS DECISION: Without rake, equity {hero_equity:.0%} '
            f'> breakeven {breakeven_no_rake:.0%} → call. '
            f'With rake, need {breakeven_raked:.0%} → fold. '
            f'This call is -EV after rake.'
        )
    if effective_rake_pct > 0.04:
        tips.append(
            f'Effective rake is {effective_rake_pct:.1%} — very high. '
            f'Tighten calling ranges and avoid marginal spots. '
            f'Add {breakeven_raked - breakeven_no_rake:.1%} to your equity requirement.'
        )
    if rake_cap_bb / total_pot_if_call < rake_pct and total_pot_if_call > 0:
        tips.append(
            f'Rake cap applies: paying {rake_cap_bb:.1f}BB cap on {total_pot_if_call:.0f}BB pot '
            f'({rake_cap_bb/total_pot_if_call:.1%} effective). '
            f'Large pots benefit more from the cap.'
        )
    if call_bb / total_pot_if_call < 0.25 and rake_changes:
        tips.append(
            'Small bet into large pot: pot odds look good but rake on small bets '
            'is proportionally larger. Recalculate with rake cap.'
        )
    if bb_size_usd > 0:
        rake_usd_per_100 = rake_per_100 * bb_size_usd
        tips.append(
            f'Estimated rake cost: {rake_per_100:.1f}BB/100 '
            f'(~${rake_usd_per_100:.2f}/100 at ${bb_size_usd:.2f} BB). '
            f'This is your table tax — factor it into win-rate goals.'
        )
    if not tips:
        tips.append(
            f'Rake impact: {ev_diff:+.2f}BB on this call. '
            f'Breakeven rises from {breakeven_no_rake:.0%} to {breakeven_raked:.0%}.'
        )

    reasoning = (
        f'Pot={pot_bb:.1f}BB call={call_bb:.1f}BB rake={rake_pct:.0%} cap={rake_cap_bb:.1f}BB. '
        f'Rake charged: {rake_charged:.2f}BB ({effective_rake_pct:.1%}). '
        f'Pot after rake: {pot_after_rake:.1f}BB. '
        f'Equity needed: {breakeven_no_rake:.0%} raw → {breakeven_raked:.0%} raked. '
        f'Hero equity={hero_equity:.0%}. '
        f'EV(call) raw={ev_no_rake:+.2f} raked={ev_with_rake:+.2f}. '
        f'Action: {action_with_rake.upper()}{" (rake flips!)" if rake_changes else ""}.'
    )

    return RakeAnalysis(
        pot_bb=pot_bb,
        call_bb=call_bb,
        hero_equity=hero_equity,
        rake_pct=rake_pct,
        rake_cap_bb=rake_cap_bb,
        rake_bb=round(rake_charged, 3),
        rake_pct_effective=round(effective_rake_pct, 4),
        pot_after_rake_bb=round(pot_after_rake, 2),
        adjusted_pot_odds=round(adjusted_pot_odds, 4),
        breakeven_equity_raw=round(breakeven_no_rake, 4),
        breakeven_equity_raked=round(breakeven_raked, 4),
        ev_call_no_rake=round(ev_no_rake, 3),
        ev_call_with_rake=round(ev_with_rake, 3),
        ev_difference=round(ev_diff, 3),
        action=action_with_rake,
        action_no_rake=action_no_rake,
        rake_changes_action=rake_changes,
        rake_per_100_hands_bb=round(rake_per_100, 2),
        reasoning=reasoning,
        tips=tips,
    )


def rake_one_liner(result: RakeAnalysis) -> str:
    """Single-line overlay summary."""
    flip = ' [RAKE FLIPS!]' if result.rake_changes_action else ''
    return (
        f'Rake {result.rake_pct:.0%} cap={result.rake_cap_bb:.1f}BB: '
        f'need {result.breakeven_equity_raked:.0%} eq (raw={result.breakeven_equity_raw:.0%}) '
        f'EV={result.ev_call_with_rake:+.2f}BB{flip}'
    )


def compare_rake_structures(
    pot_bb: float,
    call_bb: float,
    hero_equity: float,
    structures: list,
) -> list:
    """
    Compare multiple rake structures side by side.

    Args:
        pot_bb:       Pot before call
        call_bb:      Hero's call size
        hero_equity:  Hero's equity
        structures:   List of (name, rake_pct, rake_cap_bb) tuples

    Returns:
        List of (name, RakeAnalysis) sorted by ev_call_with_rake descending
    """
    results = []
    for name, rake_pct, rake_cap_bb in structures:
        r = analyze_rake(pot_bb, call_bb, hero_equity, rake_pct, rake_cap_bb)
        results.append((name, r))
    results.sort(key=lambda x: x[1].ev_call_with_rake, reverse=True)
    return results
