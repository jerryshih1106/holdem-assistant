"""
Leak Detector (leak_detector.py)

Analyzes a player's aggregate statistics to identify the top leaks
costing them the most BB/100.  Each leak is quantified with an estimated
BB/100 cost and a corrective action.

Key stats analyzed:
  VPIP          : voluntary put money in pot (ideal 20-27% 6-max, 14-20% FR)
  PFR           : preflop raise frequency (ideal: PFR/VPIP >= 0.70)
  AF            : postflop aggression factor (ideal 2.0-3.5)
  WTSD          : went-to-showdown (ideal 25-33%)
  W$SD          : won money at showdown (ideal >= 50%)
  fold_to_3bet  : ideal 55-65%
  fold_to_cbet  : ideal 40-55%
  three_bet_pct : 3-bet frequency (ideal 5-9% 6-max)
  river_bet_pct : river bet frequency (should be 35-50%)
  cbet_freq     : continuation bet frequency (ideal 50-70%)

Usage:
    from poker.leak_detector import detect_leaks, LeakReport
    report = detect_leaks(
        vpip=0.28, pfr=0.18, af=1.8, wtsd=0.35, wsd=0.48,
        fold_to_3bet=0.72, fold_to_cbet=0.55,
        three_bet_pct=0.03, river_bet_pct=0.30, cbet_freq=0.65,
    )
    for leak in report.top_leaks:
        print(leak.name, f'{leak.estimated_bb100_cost:+.1f} BB/100')
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Leak:
    """A single identified stat leak."""
    name: str                       # short identifier
    stat_name: str                  # which stat triggered this
    observed_value: float           # player's actual value
    ideal_range: str                # what a winning player shows
    estimated_bb100_cost: float     # negative = costing BB/100
    severity: str                   # 'minor', 'moderate', 'major', 'critical'
    description: str
    corrective_action: str


@dataclass
class LeakReport:
    """Full leak analysis for a player."""
    # Raw stats
    vpip: float
    pfr: float
    af: float
    wtsd: float
    wsd: float
    fold_to_3bet: float
    fold_to_cbet: float
    three_bet_pct: float
    river_bet_pct: float
    cbet_freq: float

    # Derived
    top_leaks: List[Leak] = field(default_factory=list)
    total_estimated_bb100_cost: float = 0.0
    player_type_estimate: str = 'unknown'

    # Narrative
    summary: str = ''
    priority_fix: str = ''


def _severity(cost: float) -> str:
    cost = abs(cost)
    if cost >= 5.0:
        return 'critical'
    elif cost >= 3.0:
        return 'major'
    elif cost >= 1.5:
        return 'moderate'
    return 'minor'


def _player_type(vpip: float, pfr: float, af: float, wtsd: float) -> str:
    if vpip > 0.40:
        return 'fish' if pfr < 0.12 else 'loose_aggro'
    if vpip < 0.15:
        return 'nit'
    if vpip > 0.28 and pfr > 0.22 and af > 2.5:
        return 'lag'
    if vpip < 0.24 and pfr > 0.18:
        return 'tag'
    if wtsd > 0.40:
        return 'calling_station'
    return 'reg'


def _check_vpip(vpip: float, leaks: list) -> None:
    # 6-max ideal 20-27%; >30% or <17% are leaks
    if vpip > 0.32:
        excess = vpip - 0.27
        cost = -(excess * 25)   # approx -25 BB/100 per 10% excess VPIP
        leaks.append(Leak(
            name='vpip_too_high',
            stat_name='VPIP',
            observed_value=vpip,
            ideal_range='20-27%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'VPIP={vpip:.0%} is too loose. Playing marginal hands OOP bleeds equity.',
            corrective_action='Tighten from EP/MP: fold suited connectors below 76s, offsuit broadways below KJ, weak aces below A9o.',
        ))
    elif vpip < 0.16:
        cost = -((0.18 - vpip) * 15)
        leaks.append(Leak(
            name='vpip_too_tight',
            stat_name='VPIP',
            observed_value=vpip,
            ideal_range='20-27%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'VPIP={vpip:.0%} is too tight. Leaving significant win-rate on the table.',
            corrective_action='Open more from BTN/CO: add suited connectors (65s+), suited aces (A2s-A5s), KQo, QJo.',
        ))


def _check_pfr_vpip_gap(vpip: float, pfr: float, leaks: list) -> None:
    if vpip < 0.01:
        return
    ratio = pfr / vpip
    if ratio < 0.60:
        cost = -((0.68 - ratio) * 20)
        leaks.append(Leak(
            name='pfr_vpip_gap',
            stat_name='PFR/VPIP ratio',
            observed_value=ratio,
            ideal_range='0.70-0.85',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=(
                f'PFR/VPIP ratio={ratio:.2f} — calling too often instead of raising. '
                f'Cold-callers give up initiative and face c-bets OOP.'
            ),
            corrective_action='Replace flat-calls with 3-bets for hands in your range (AQ, JJ, KQs). Fold the rest instead of limping/calling.',
        ))


def _check_3bet(three_bet_pct: float, leaks: list) -> None:
    if three_bet_pct < 0.04:
        cost = -((0.05 - three_bet_pct) * 30)
        leaks.append(Leak(
            name='3bet_too_low',
            stat_name='3-bet%',
            observed_value=three_bet_pct,
            ideal_range='5-9%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'3-bet%={three_bet_pct:.1%} is too low. Opponents steal freely and face no pressure.',
            corrective_action='Add light 3-bets from BTN/CO vs late-position steals with A2s-A5s, K5s-K9s, 76s, 87s. Size 3x IP, 3.5x OOP.',
        ))
    elif three_bet_pct > 0.12:
        cost = -((three_bet_pct - 0.09) * 15)
        leaks.append(Leak(
            name='3bet_too_high',
            stat_name='3-bet%',
            observed_value=three_bet_pct,
            ideal_range='5-9%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'3-bet%={three_bet_pct:.1%} is too high. Opponents will start 4-betting your light 3-bets.',
            corrective_action='Remove weakest bluff 3-bets (offsuit connectors, weak suited gappers). Tighten to hands with good blockers (A-high, K-high suited).',
        ))


def _check_fold_to_3bet(fold_to_3bet: float, leaks: list) -> None:
    if fold_to_3bet > 0.68:
        cost = -((fold_to_3bet - 0.62) * 12)
        leaks.append(Leak(
            name='folds_too_much_to_3bet',
            stat_name='fold_to_3bet',
            observed_value=fold_to_3bet,
            ideal_range='55-65%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'Fold-to-3bet={fold_to_3bet:.0%} is too high. Opponents will 3-bet you relentlessly.',
            corrective_action='Defend more with KQs, QJs, ATs, JJ-TT by calling or 4-betting. Never fold QQ+/AK to a 3-bet.',
        ))
    elif fold_to_3bet < 0.48:
        cost = -((0.55 - fold_to_3bet) * 10)
        leaks.append(Leak(
            name='defends_too_much_vs_3bet',
            stat_name='fold_to_3bet',
            observed_value=fold_to_3bet,
            ideal_range='55-65%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'Fold-to-3bet={fold_to_3bet:.0%} is too low. Calling OOP with marginal hands bleeds chips.',
            corrective_action='Fold more OOP vs 3-bets: KJo, QJo, ATo, KTs when facing nit 3-bets OOP.',
        ))


def _check_fold_to_cbet(fold_to_cbet: float, leaks: list) -> None:
    if fold_to_cbet > 0.57:
        cost = -((fold_to_cbet - 0.52) * 10)
        leaks.append(Leak(
            name='folds_too_much_to_cbet',
            stat_name='fold_to_cbet',
            observed_value=fold_to_cbet,
            ideal_range='40-55%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'Fold-to-cbet={fold_to_cbet:.0%} makes you an easy c-bet target. Opponents cbet wide.',
            corrective_action='Defend with weak pairs + backdoor draws. Float IP with any pair, any draw. Raise draws OOP when board gives equity.',
        ))
    elif fold_to_cbet < 0.36:
        cost = -((0.42 - fold_to_cbet) * 8)
        leaks.append(Leak(
            name='calls_too_many_cbets',
            stat_name='fold_to_cbet',
            observed_value=fold_to_cbet,
            ideal_range='40-55%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'Fold-to-cbet={fold_to_cbet:.0%} is too low — calling without equity or plan.',
            corrective_action='Fold more hands with no equity and no draw. Gutshots alone OOP on dry boards are near 0-EV calls.',
        ))


def _check_af(af: float, leaks: list) -> None:
    if af < 1.5:
        cost = -((1.8 - af) * 5)
        leaks.append(Leak(
            name='postflop_passive',
            stat_name='AF',
            observed_value=af,
            ideal_range='2.0-3.5',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'AF={af:.1f} — passive postflop. Value is extracted through bets, not check-calls.',
            corrective_action='Bet your strong hands on the flop instead of check-calling. Use check-raises on boards where you have equity. C-bet 50-65% on dry boards.',
        ))
    elif af > 4.5:
        cost = -((af - 3.5) * 3)
        leaks.append(Leak(
            name='postflop_overaggressive',
            stat_name='AF',
            observed_value=af,
            ideal_range='2.0-3.5',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'AF={af:.1f} — over-aggressive; bluffing into calling stations or in wrong spots.',
            corrective_action='Check back medium hands more on the flop. Reduce multi-barrel bluffs vs high-WTSD opponents.',
        ))


def _check_wtsd(wtsd: float, leaks: list) -> None:
    if wtsd > 0.38:
        cost = -((wtsd - 0.33) * 18)
        leaks.append(Leak(
            name='wtsd_too_high',
            stat_name='WTSD',
            observed_value=wtsd,
            ideal_range='25-33%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'WTSD={wtsd:.0%} — calling down too often. Opponents value-bet you relentlessly.',
            corrective_action='Fold more to river bets. When villain turns a passive line aggressive on river, give them credit. Let go of second pair on rivers.',
        ))
    elif wtsd < 0.22:
        cost = -((0.25 - wtsd) * 12)
        leaks.append(Leak(
            name='wtsd_too_low',
            stat_name='WTSD',
            observed_value=wtsd,
            ideal_range='25-33%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'WTSD={wtsd:.0%} — folding too much on later streets. Opponents bluff you off good hands.',
            corrective_action='Call down more with one-pair hands vs aggressive opponents. Use pot-odds; if you need >33% equity, have it.',
        ))


def _check_wsd(wsd: float, leaks: list) -> None:
    if wsd < 0.47:
        cost = -((0.50 - wsd) * 20)
        leaks.append(Leak(
            name='wsd_too_low',
            stat_name='W$SD',
            observed_value=wsd,
            ideal_range='50-57%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'W$SD={wsd:.0%} — reaching showdown with losing hands too often.',
            corrective_action='Fold more dominated hands preflop (KJo vs UTG, A9o vs 3-bet). At showdown, you should mostly have top pair+ or draws that got there.',
        ))


def _check_river_bet(river_bet_pct: float, leaks: list) -> None:
    if river_bet_pct < 0.30:
        cost = -((0.35 - river_bet_pct) * 8)
        leaks.append(Leak(
            name='river_bet_freq_low',
            stat_name='river_bet%',
            observed_value=river_bet_pct,
            ideal_range='35-50%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'River bet%={river_bet_pct:.0%} — checking too many value hands on the river.',
            corrective_action='Bet strong hands on the river for thin value. Against weak opponents, bet top two pair+ always. Merge your range river sizing (50-66% pot for value).',
        ))


def _check_cbet(cbet_freq: float, leaks: list) -> None:
    if cbet_freq > 0.78:
        cost = -((cbet_freq - 0.70) * 6)
        leaks.append(Leak(
            name='cbet_too_frequent',
            stat_name='cbet%',
            observed_value=cbet_freq,
            ideal_range='50-70%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'Cbet={cbet_freq:.0%} — betting too often on unfavorable boards. Easy to exploit with floats/raises.',
            corrective_action='Check back on wet boards without equity (e.g., J-9-8 with overcards). Balance range with check-calls on boards where you\'re out of range.',
        ))
    elif cbet_freq < 0.45:
        cost = -((0.52 - cbet_freq) * 5)
        leaks.append(Leak(
            name='cbet_too_infrequent',
            stat_name='cbet%',
            observed_value=cbet_freq,
            ideal_range='50-70%',
            estimated_bb100_cost=round(cost, 1),
            severity=_severity(cost),
            description=f'Cbet={cbet_freq:.0%} — not exploiting preflop range advantage. Giving free cards.',
            corrective_action='C-bet more on dry boards (A-x-x, K-x-x) where your preflop range connects better. Use 33-40% pot sizing for efficiency.',
        ))


def detect_leaks(
    vpip: float,
    pfr: float,
    af: float,
    wtsd: float,
    wsd: float,
    fold_to_3bet: float,
    fold_to_cbet: float,
    three_bet_pct: float,
    river_bet_pct: float,
    cbet_freq: float = 0.60,
    sample_hands: int = 0,
) -> LeakReport:
    """
    Identify top poker leaks from aggregate statistics.

    Args:
        vpip:           Voluntarily put $ in pot (0-1)
        pfr:            Preflop raise % (0-1)
        af:             Postflop aggression factor (bets+raises / calls)
        wtsd:           Went to showdown % (0-1)
        wsd:            Won $ at showdown % (0-1)
        fold_to_3bet:   Fold to 3-bet % (0-1)
        fold_to_cbet:   Fold to c-bet % (0-1)
        three_bet_pct:  3-bet frequency (0-1)
        river_bet_pct:  River bet frequency (0-1)
        cbet_freq:      Continuation bet frequency (0-1)
        sample_hands:   Hand sample size (0 = unknown)

    Returns:
        LeakReport with top_leaks sorted by BB/100 cost
    """
    leaks: List[Leak] = []

    _check_vpip(vpip, leaks)
    _check_pfr_vpip_gap(vpip, pfr, leaks)
    _check_3bet(three_bet_pct, leaks)
    _check_fold_to_3bet(fold_to_3bet, leaks)
    _check_fold_to_cbet(fold_to_cbet, leaks)
    _check_af(af, leaks)
    _check_wtsd(wtsd, leaks)
    _check_wsd(wsd, leaks)
    _check_river_bet(river_bet_pct, leaks)
    _check_cbet(cbet_freq, leaks)

    # Sort by cost (most expensive first)
    leaks.sort(key=lambda l: l.estimated_bb100_cost)

    total_cost = sum(l.estimated_bb100_cost for l in leaks)
    player_type = _player_type(vpip, pfr, af, wtsd)

    # Summary
    top3 = leaks[:3]
    if top3:
        top3_names = ', '.join(l.name for l in top3)
        summary = (
            f'Player type: {player_type}. '
            f'Found {len(leaks)} leak(s) costing est. {total_cost:+.1f} BB/100. '
            f'Top issues: {top3_names}.'
        )
        priority_fix = top3[0].corrective_action if top3 else 'No critical leaks detected.'
    else:
        summary = f'Player type: {player_type}. No significant stat leaks detected — focus on game selection and table dynamics.'
        priority_fix = 'Maintain current stat profile; look for exploitative adjustments vs specific player types.'

    if sample_hands > 0 and sample_hands < 10000:
        summary += f' Note: only {sample_hands:,} hands — stats may not be stable yet (need 20k+ for reliable reads).'

    return LeakReport(
        vpip=vpip,
        pfr=pfr,
        af=af,
        wtsd=wtsd,
        wsd=wsd,
        fold_to_3bet=fold_to_3bet,
        fold_to_cbet=fold_to_cbet,
        three_bet_pct=three_bet_pct,
        river_bet_pct=river_bet_pct,
        cbet_freq=cbet_freq,
        top_leaks=leaks,
        total_estimated_bb100_cost=round(total_cost, 1),
        player_type_estimate=player_type,
        summary=summary,
        priority_fix=priority_fix,
    )


def leak_one_liner(report: LeakReport) -> str:
    """Single-line overlay summary."""
    top = report.top_leaks[0] if report.top_leaks else None
    if top:
        return (
            f'[{report.player_type_estimate}] '
            f'{len(report.top_leaks)} leaks / {report.total_estimated_bb100_cost:+.1f} BB/100 | '
            f'#1: {top.name} ({top.estimated_bb100_cost:+.1f}) | Fix: {top.corrective_action[:40]}'
        )
    return f'[{report.player_type_estimate}] No leaks detected'
