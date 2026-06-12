"""
Rake-Adjusted EV Calculator (rake_ev_calculator.py)

Most EV calculations ignore rake. At micro/small stakes, rake of 5-8% of the pot
(capped at $1-5) can transform +EV plays into -EV plays.

RAKE STRUCTURES:
  NL10 (0.05/0.10): 5% rake, cap $1 = 10BB cap
  NL25 (0.10/0.25): 5% rake, cap $1 = 4BB cap
  NL50 (0.25/0.50): 5% rake, cap $2 = 4BB cap
  NL100 (0.50/1.00): 5% rake, cap $3 = 3BB cap
  NL200 (1.00/2.00): 4% rake, cap $4 = 2BB cap
  NL500 (2.50/5.00): 3% rake, cap $5 = 1BB cap
  Live $1/$2:  10% rake, cap $6 = 3BB cap
  Live $2/$5:   5% rake, cap $10 = 2BB cap

RAKE-ADJUSTED EV FORMULA:
  Gross EV = equity × (pot + 2×call) - call
  Rake = min(pot_final × rake_pct, rake_cap_bb)
  Hero's rake share = equity × rake (paid only when you win)
  Adjusted EV = Gross EV - hero_rake_share

  Alternatively: Adjusted EV = equity × (adjusted_pot) - call
  where adjusted_pot = pot_final - rake

NO-RAKE THRESHOLD:
  Many sites have a "no flop no drop" rule:
  - If hand ends preflop → no rake
  - If hand ends preflop or on flop with no bet → 0 rake

RAKEBACK IMPACT:
  If you receive 30% rakeback: effective_rake = rake × 0.70
  A 2BB/100 winner paying 5BB/100 in rake needs 30% rakeback to be +2BB/100

Usage:
    from poker.rake_ev_calculator import calc_rake_ev, RakeEVResult, rake_ev_one_liner

    result = calc_rake_ev(
        pot_bb=15.0,
        call_bb=8.0,
        hero_equity=0.58,
        rake_structure='nl100',
        hero_pos='IP',
        street='flop',
        n_opponents=1,
        rakeback_pct=0.0,
    )
    print(rake_ev_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# ── Rake structures ──────────────────────────────────────────────────────────

_RAKE_STRUCTURES = {
    # name: (rake_pct, cap_bb)
    'nl2':    (0.05, 20.0),   # NL2: 5% cap $0.40 = 20BB
    'nl5':    (0.05, 15.0),   # NL5: 5% cap $0.75 = 15BB
    'nl10':   (0.05, 10.0),   # NL10: 5% cap $1.00 = 10BB
    'nl25':   (0.05, 4.0),    # NL25: 5% cap $1.00 = 4BB
    'nl50':   (0.05, 4.0),    # NL50: 5% cap $2.00 = 4BB
    'nl100':  (0.05, 3.0),    # NL100: 5% cap $3.00 = 3BB
    'nl200':  (0.04, 2.0),    # NL200: 4% cap $4.00 = 2BB
    'nl500':  (0.03, 1.0),    # NL500: 3% cap $5.00 = 1BB
    'nl1000': (0.03, 1.0),    # NL1000: ~3% cap $10 = 1BB
    'live_1_2':  (0.10, 3.0), # Live $1/$2: 10% cap $6 = 3BB
    'live_2_5':  (0.05, 2.0), # Live $2/$5: 5% cap $10 = 2BB
    'live_5_10': (0.05, 1.5), # Live $5/$10: 5% cap $15 = 1.5BB
    'zero_rake':  (0.0, 0.0), # Solver / no rake
}


def _calc_rake(pot_final_bb: float, rake_pct: float, cap_bb: float) -> float:
    """Return actual rake taken from pot in BB."""
    if pot_final_bb <= 0 or rake_pct <= 0:
        return 0.0
    raw = pot_final_bb * rake_pct
    return round(min(raw, cap_bb), 3)


def _effective_rake_pct(pot_bb: float, rake_pct: float, cap_bb: float) -> float:
    """Effective rake percentage after cap is applied."""
    if pot_bb <= 0:
        return 0.0
    rake = _calc_rake(pot_bb, rake_pct, cap_bb)
    return round(rake / pot_bb, 4)


@dataclass
class RakeEVResult:
    """Rake-adjusted EV analysis for a poker decision."""
    # Inputs
    pot_bb: float
    call_bb: float
    hero_equity: float
    rake_structure: str
    hero_pos: str
    street: str
    n_opponents: int
    rakeback_pct: float

    # Rake calculation
    rake_pct: float
    rake_cap_bb: float
    pot_after_call_bb: float       # pot size after hero calls
    gross_rake_bb: float           # rake taken from final pot
    effective_rake_pct: float      # actual effective rake %
    rakeback_bb: float             # rakeback returned to hero
    net_rake_bb: float             # rake after rakeback
    hero_rake_share_bb: float      # hero's expected rake cost (equity × net_rake)

    # EV calculations
    gross_ev_bb: float             # EV ignoring rake
    rake_adjusted_ev_bb: float     # EV after rake
    ev_loss_to_rake_bb: float      # how much rake costs per decision

    # Break-even analysis
    break_even_equity_gross: float       # equity needed without rake
    break_even_equity_adjusted: float    # equity needed WITH rake

    # Decision
    action: str                    # 'call', 'call_marginal', 'fold', 'no_rake_call'
    verdict: str
    rake_severity: str             # 'negligible', 'minor', 'significant', 'severe'

    reasoning: str
    tips: List[str] = field(default_factory=list)


def calc_rake_ev(
    pot_bb: float = 15.0,
    call_bb: float = 8.0,
    hero_equity: float = 0.58,
    rake_structure: str = 'nl100',
    hero_pos: str = 'IP',
    street: str = 'flop',
    n_opponents: int = 1,
    rakeback_pct: float = 0.0,
) -> RakeEVResult:
    """
    Calculate rake-adjusted EV for calling or folding.

    Args:
        pot_bb:          Current pot before hero acts (BB)
        call_bb:         Cost to call (0 if hero can check freely)
        hero_equity:     Hero's equity (0-1)
        rake_structure:  One of the pre-defined structures (e.g., 'nl100')
        hero_pos:        'IP' or 'OOP'
        street:          'preflop', 'flop', 'turn', 'river'
        n_opponents:     Number of opponents in hand
        rakeback_pct:    Rakeback fraction hero receives (e.g., 0.30 for 30%)

    Returns:
        RakeEVResult
    """
    struct = _RAKE_STRUCTURES.get(rake_structure.lower(), _RAKE_STRUCTURES['nl100'])
    rake_pct, cap_bb = struct

    # Pot after hero calls
    pot_after = pot_bb + call_bb * (n_opponents + 1)  # hero + opponents putting in call_bb
    # Simplify: pot after = pot + 2×call for HU; pot + call × n_callers more accurately
    # Use: pot_after = pot + call (hero) + call (villain, assumed equal investment)
    pot_after = round(pot_bb + 2 * call_bb, 2)

    # Rake on final pot
    gross_rake = _calc_rake(pot_after, rake_pct, cap_bb)
    eff_rake_pct = _effective_rake_pct(pot_after, rake_pct, cap_bb)
    rakeback = round(gross_rake * rakeback_pct, 3)
    net_rake = round(gross_rake - rakeback, 3)

    # Hero pays rake only when they WIN the pot
    hero_rake_share = round(hero_equity * net_rake, 3)

    # Gross EV (no rake)
    if call_bb > 0:
        gross_ev = round(hero_equity * pot_after - call_bb, 3)
    else:
        gross_ev = round(hero_equity * pot_bb, 3)

    # Rake-adjusted EV
    rake_adjusted_ev = round(gross_ev - hero_rake_share, 3)
    ev_loss = round(gross_ev - rake_adjusted_ev, 3)

    # Break-even equity
    # Gross: call = equity × pot_after → eq = call / pot_after
    if pot_after > 0 and call_bb > 0:
        be_gross = round(call_bb / pot_after, 4)
        # Adjusted: call + rake_share = equity × (pot_after - net_rake)
        # call = eq × pot_after - eq × net_rake - call
        # eq × (pot_after - net_rake) = call + 0 (fold EV = 0)
        # Actually: ev=0 → eq×(pot_after - net_rake) = call
        adj_denom = pot_after - net_rake
        be_adjusted = round(call_bb / adj_denom, 4) if adj_denom > 0 else be_gross
    else:
        be_gross = 0.0
        be_adjusted = 0.0

    # Rake severity
    rake_loss_pct = ev_loss / max(abs(gross_ev), 0.01)
    if eff_rake_pct < 0.02 or net_rake < 0.1:
        severity = 'negligible'
    elif eff_rake_pct < 0.04 or net_rake < 0.5:
        severity = 'minor'
    elif eff_rake_pct < 0.06 or net_rake < 1.5:
        severity = 'significant'
    else:
        severity = 'severe'

    # Decision
    if call_bb == 0:
        action = 'no_rake_call'
        verdict = f'Free check: no call required. Rake={net_rake:.2f}BB affects future bets.'
    elif rake_adjusted_ev >= 0.5:
        action = 'call'
        verdict = (
            f'CALL: rake-adjusted EV={rake_adjusted_ev:.2f}BB (gross={gross_ev:.2f}BB). '
            f'Rake costs {ev_loss:.2f}BB ({eff_rake_pct:.1%} of pot). Still clearly profitable.'
        )
    elif rake_adjusted_ev >= 0.0:
        action = 'call_marginal'
        verdict = (
            f'MARGINAL CALL: rake-adjusted EV={rake_adjusted_ev:.2f}BB. '
            f'Gross EV={gross_ev:.2f}BB reduced by {ev_loss:.2f}BB rake. '
            f'Rake severity={severity}. Close decision.'
        )
    elif gross_ev >= 0.0:
        action = 'call_if_rakeback'
        verdict = (
            f'FOLD (or call with rakeback): gross EV={gross_ev:.2f}BB is +EV, '
            f'but rake costs {net_rake:.2f}BB → adjusted EV={rake_adjusted_ev:.2f}BB. '
            f'Requires {(rakeback_pct*100):.0f}%+ rakeback to be profitable.'
        )
    else:
        action = 'fold'
        verdict = (
            f'FOLD: both gross EV={gross_ev:.2f}BB AND rake-adjusted={rake_adjusted_ev:.2f}BB are negative. '
            f'Clear fold.'
        )

    reasoning = (
        f'{rake_structure.upper()} rake: {rake_pct:.0%} cap={cap_bb:.1f}BB. '
        f'Pot after call: {pot_after:.1f}BB. Rake: {gross_rake:.2f}BB ({eff_rake_pct:.1%}). '
        f'Rakeback: {rakeback:.2f}BB. Net rake: {net_rake:.2f}BB. '
        f'Hero rake share (eq×rake): {hero_rake_share:.2f}BB. '
        f'Gross EV: {gross_ev:.2f}BB. Adjusted EV: {rake_adjusted_ev:.2f}BB. '
        f'Break-even equity: {be_gross:.1%} (gross) / {be_adjusted:.1%} (rake-adj). '
        f'Hero equity: {hero_equity:.0%}. Decision: {action}.'
    )

    tips = []
    if severity in ('significant', 'severe'):
        tips.append(
            f'RAKE IMPACT ({severity.upper()}): '
            f'Effective rake = {eff_rake_pct:.1%} of pot ({net_rake:.2f}BB per won pot). '
            f'Break-even equity goes from {be_gross:.0%} (no rake) to {be_adjusted:.0%} (with rake). '
            f'That is +{(be_adjusted-be_gross)*100:.1f}% MORE equity needed to be profitable. '
            f'Consider: are there thinner calls you should be folding?'
        )
    if rakeback_pct == 0 and severity in ('significant', 'severe'):
        tips.append(
            f'RAKEBACK SUGGESTION: At {rake_structure.upper()}, you are paying {gross_rake:.2f}BB rake per hand. '
            f'30% rakeback would save {gross_rake*0.30:.2f}BB per hand. '
            f'At 50BB/100 hands average pot, rakeback adds 1-3BB/100 to your winrate.'
        )
    if street in ('flop', 'preflop') and gross_ev < 0.5 and gross_ev > 0:
        tips.append(
            f'THIN CALL ALERT: Gross EV={gross_ev:.2f}BB is positive but thin. '
            f'After rake ({net_rake:.2f}BB), adjusted EV={rake_adjusted_ev:.2f}BB. '
            f'At {rake_structure.upper()}, thin calls in small pots are often -EV after rake. '
            f'Prefer spots with larger pot equity advantage.'
        )
    if eff_rake_pct >= 0.08:
        tips.append(
            f'EXTREME RAKE ({eff_rake_pct:.0%} effective): This is the main challenge at {rake_structure.upper()}. '
            f'Key adjustments: play fewer but bigger pots; avoid speculative hands in small pots; '
            f'avoid thin calls and marginal bluffs; value bet relentlessly when you have equity edge.'
        )
    if be_adjusted > 0.55 and call_bb > 0:
        tips.append(
            f'HIGH BREAKEVEN ({be_adjusted:.0%} required): Even with good equity, rake raises the bar. '
            f'You need {be_adjusted:.0%} equity just to break even. '
            f'Current equity {hero_equity:.0%}: '
            f'{"above breakeven (+{:.1%})".format(hero_equity - be_adjusted) if hero_equity >= be_adjusted else "BELOW breakeven ({:.1%} short)".format(be_adjusted - hero_equity)}. '
        )
    if not tips:
        tips.append(
            f'{rake_structure.upper()} rake: {eff_rake_pct:.1%} effective. '
            f'Gross EV={gross_ev:.2f}BB → Adjusted={rake_adjusted_ev:.2f}BB (delta={ev_loss:.2f}BB). '
            f'Severity={severity}.'
        )

    return RakeEVResult(
        pot_bb=round(pot_bb, 2),
        call_bb=round(call_bb, 2),
        hero_equity=round(hero_equity, 3),
        rake_structure=rake_structure.lower(),
        hero_pos=hero_pos,
        street=street,
        n_opponents=n_opponents,
        rakeback_pct=round(rakeback_pct, 3),
        rake_pct=rake_pct,
        rake_cap_bb=cap_bb,
        pot_after_call_bb=pot_after,
        gross_rake_bb=gross_rake,
        effective_rake_pct=eff_rake_pct,
        rakeback_bb=rakeback,
        net_rake_bb=net_rake,
        hero_rake_share_bb=hero_rake_share,
        gross_ev_bb=gross_ev,
        rake_adjusted_ev_bb=rake_adjusted_ev,
        ev_loss_to_rake_bb=ev_loss,
        break_even_equity_gross=be_gross,
        break_even_equity_adjusted=be_adjusted,
        action=action,
        verdict=verdict,
        rake_severity=severity,
        reasoning=reasoning,
        tips=tips,
    )


def rake_ev_one_liner(r: RakeEVResult) -> str:
    return (
        f'[RAKE {r.rake_structure.upper()}|{r.street}] {r.action.upper()} | '
        f'gross_ev={r.gross_ev_bb:+.2f}BB adj={r.rake_adjusted_ev_bb:+.2f}BB '
        f'rake={r.net_rake_bb:.2f}BB({r.effective_rake_pct:.1%}) | '
        f'be={r.break_even_equity_adjusted:.0%} sev={r.rake_severity}'
    )
