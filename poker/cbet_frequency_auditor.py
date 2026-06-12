"""
C-Bet Frequency Auditor (cbet_frequency_auditor.py)

Audits hero's continuation betting frequency across different positions,
streets, and board types vs GTO baselines. Quantifies the BB/100 EV loss
from each deviation.

Most players have two primary c-bet leaks:
  1. Over-cbetting OOP on wet boards (gives opponents good price with draws)
  2. Under-cbetting dry boards IP (leaving money on table vs weak hands)

GTO BASELINE C-BET FREQUENCIES:
  IP   dry:   72%     OOP  dry:   56%
  IP   medium: 62%    OOP  medium: 48%
  IP   wet:   50%     OOP  wet:   35%
  IP   paired: 78%    OOP  paired: 60%
  IP   3bet:  58%     OOP  3bet:  44%
  Multiway (each extra opp): -12% from IP baseline

EV LOSS FROM DEVIATIONS:
  +10% over-cbet OOP wet: ~0.8 BB/100 (villain floats more profitably)
  -15% under-cbet IP dry: ~1.2 BB/100 (missed fold equity)
  +20% over-cbet all positions: ~2.0 BB/100 (predictable, float-exploitable)

DISTINCT FROM OTHER MODULES:
  gto_deviation.py:       Detects general statistical deviations from GTO
  range_protect_advisor.py: Advises on range protection per hand
  THIS MODULE:            Complete c-bet frequency AUDIT across all situations,
                          BB/100 quantification, and improvement priority list

Usage:
    from poker.cbet_frequency_auditor import audit_cbet_frequencies, CbetAuditResult, cba_one_liner

    result = audit_cbet_frequencies(
        cbet_ip_dry=0.78,
        cbet_ip_wet=0.68,
        cbet_oop_dry=0.72,
        cbet_oop_wet=0.55,
        cbet_3bet_ip=0.62,
        cbet_3bet_oop=0.50,
        cbet_multiway=0.35,
        sample_hands=5000,
    )
    print(cba_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List, Dict


# --------------------------------------------------------------------------
# GTO baselines
# --------------------------------------------------------------------------

GTO_CBET = {
    'ip_dry':       0.72,
    'ip_medium':    0.62,
    'ip_wet':       0.50,
    'ip_paired':    0.78,
    'ip_3bet':      0.58,
    'oop_dry':      0.56,
    'oop_medium':   0.48,
    'oop_wet':      0.35,
    'oop_paired':   0.60,
    'oop_3bet':     0.44,
    'multiway':     0.30,
}

# BB/100 EV loss per 10% absolute deviation in each spot
# Larger loss for spots with more dead money or opponent fold equity impact
EV_LOSS_PER_10PCT = {
    'ip_dry':     0.8,    # moderate: leaving fold equity on table
    'ip_medium':  0.6,
    'ip_wet':     0.7,    # significant: over-betting into good draw prices
    'ip_paired':  0.5,
    'ip_3bet':    0.9,    # high: SPR is low, cbet frequencies matter a lot
    'oop_dry':    0.7,
    'oop_medium': 0.5,
    'oop_wet':    0.9,    # highest: OOP overbetting wet = very exploitable
    'oop_paired': 0.6,
    'oop_3bet':   0.8,
    'multiway':   1.0,    # cbetting multiway loses money when too frequent
}

SPOT_LABELS = {
    'ip_dry':     'IP Dry Flop',
    'ip_medium':  'IP Medium Flop',
    'ip_wet':     'IP Wet Flop',
    'ip_paired':  'IP Paired Flop',
    'ip_3bet':    'IP 3-Bet Pot',
    'oop_dry':    'OOP Dry Flop',
    'oop_medium': 'OOP Medium Flop',
    'oop_wet':    'OOP Wet Flop',
    'oop_paired': 'OOP Paired Flop',
    'oop_3bet':   'OOP 3-Bet Pot',
    'multiway':   'Multiway Pot',
}


def _ev_loss(deviation_pct: float, ev_loss_per_10: float) -> float:
    """BB/100 EV loss from deviation."""
    return round(abs(deviation_pct) / 0.10 * ev_loss_per_10, 2)


def _reliability(hands: int) -> str:
    if hands < 500:
        return 'very_low'
    elif hands < 2000:
        return 'low'
    elif hands < 8000:
        return 'medium'
    else:
        return 'high'


@dataclass
class CbetSpotResult:
    spot: str
    label: str
    hero_freq: float
    gto_freq: float
    deviation: float    # hero - gto
    direction: str      # 'over_cbetting' / 'under_cbetting' / 'on_target'
    ev_loss_bb100: float
    severity: str       # 'critical' / 'major' / 'minor' / 'ok'
    fix_advice: str


@dataclass
class CbetAuditResult:
    # Input frequencies
    cbet_ip_dry: float
    cbet_ip_wet: float
    cbet_oop_dry: float
    cbet_oop_wet: float
    cbet_3bet_ip: float
    cbet_3bet_oop: float
    cbet_multiway: float
    sample_hands: int

    # Per-spot analysis
    spots: List[CbetSpotResult]

    # Summary
    total_ev_loss_bb100: float
    top_leak: str           # most costly spot
    top_leak_ev: float
    reliability: str        # reliability of the audit

    # Overall assessment
    overall_direction: str  # 'over_cbetting' / 'under_cbetting' / 'inconsistent' / 'balanced'
    over_cbet_spots: int
    under_cbet_spots: int
    on_target_spots: int

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def audit_cbet_frequencies(
    cbet_ip_dry: float = 0.72,
    cbet_ip_medium: float = 0.62,
    cbet_ip_wet: float = 0.58,
    cbet_ip_paired: float = 0.78,
    cbet_oop_dry: float = 0.56,
    cbet_oop_medium: float = 0.48,
    cbet_oop_wet: float = 0.45,
    cbet_oop_paired: float = 0.60,
    cbet_3bet_ip: float = 0.58,
    cbet_3bet_oop: float = 0.44,
    cbet_multiway: float = 0.30,
    sample_hands: int = 5000,
) -> CbetAuditResult:
    """
    Audit hero's c-bet frequencies across all major spots.

    Args:
        cbet_ip_dry:     Hero's cbet% IP vs dry boards (0.0-1.0)
        cbet_ip_medium:  Hero's cbet% IP vs medium texture
        cbet_ip_wet:     Hero's cbet% IP vs wet boards
        cbet_ip_paired:  Hero's cbet% IP vs paired boards
        cbet_oop_dry:    Hero's cbet% OOP vs dry boards
        cbet_oop_medium: Hero's cbet% OOP vs medium texture
        cbet_oop_wet:    Hero's cbet% OOP vs wet boards
        cbet_oop_paired: Hero's cbet% OOP vs paired boards
        cbet_3bet_ip:    Hero's cbet% in 3-bet pot IP
        cbet_3bet_oop:   Hero's cbet% in 3-bet pot OOP
        cbet_multiway:   Hero's cbet% in multiway pots
        sample_hands:    Number of hands in sample (for reliability)

    Returns:
        CbetAuditResult
    """
    hero_freqs = {
        'ip_dry':     cbet_ip_dry,
        'ip_medium':  cbet_ip_medium,
        'ip_wet':     cbet_ip_wet,
        'ip_paired':  cbet_ip_paired,
        'ip_3bet':    cbet_3bet_ip,
        'oop_dry':    cbet_oop_dry,
        'oop_medium': cbet_oop_medium,
        'oop_wet':    cbet_oop_wet,
        'oop_paired': cbet_oop_paired,
        'oop_3bet':   cbet_3bet_oop,
        'multiway':   cbet_multiway,
    }

    spots = []
    total_ev_loss = 0.0
    n_over = n_under = n_ok = 0
    top_spot = ''
    top_ev = 0.0

    for key, hero_freq in hero_freqs.items():
        gto_freq = GTO_CBET[key]
        deviation = round(hero_freq - gto_freq, 3)
        abs_dev = abs(deviation)

        if abs_dev <= 0.05:
            direction = 'on_target'
            severity = 'ok'
            n_ok += 1
        elif deviation > 0:
            direction = 'over_cbetting'
            n_over += 1
            severity = 'critical' if abs_dev >= 0.20 else 'major' if abs_dev >= 0.12 else 'minor'
        else:
            direction = 'under_cbetting'
            n_under += 1
            severity = 'critical' if abs_dev >= 0.20 else 'major' if abs_dev >= 0.12 else 'minor'

        ev_loss = _ev_loss(deviation, EV_LOSS_PER_10PCT[key]) if abs_dev > 0.05 else 0.0
        total_ev_loss += ev_loss

        if ev_loss > top_ev:
            top_ev = ev_loss
            top_spot = SPOT_LABELS[key]

        # Fix advice
        if direction == 'on_target':
            fix = f'{SPOT_LABELS[key]}: On target ({hero_freq:.0%} vs GTO {gto_freq:.0%})'
        elif direction == 'over_cbetting':
            fix = (
                f'{SPOT_LABELS[key]}: REDUCE cbet from {hero_freq:.0%} to ~{gto_freq:.0%} '
                f'(currently {deviation:+.0%}). '
                f'{"Check back more bluffs; bet only value+protection." if "wet" in key else "Mix in more checks with medium hands."}'
            )
        else:
            fix = (
                f'{SPOT_LABELS[key]}: INCREASE cbet from {hero_freq:.0%} to ~{gto_freq:.0%} '
                f'(currently {deviation:+.0%}). '
                f'{"Bet more IP on dry boards — fold equity is high." if "ip_dry" in key else "Bet more to protect equity and deny free cards."}'
            )

        spots.append(CbetSpotResult(
            spot=key, label=SPOT_LABELS[key],
            hero_freq=hero_freq, gto_freq=gto_freq, deviation=deviation,
            direction=direction, ev_loss_bb100=ev_loss, severity=severity, fix_advice=fix,
        ))

    # Sort by EV loss descending (most important leaks first)
    spots.sort(key=lambda s: s.ev_loss_bb100, reverse=True)

    if n_over > n_under + 2:
        overall = 'over_cbetting'
    elif n_under > n_over + 2:
        overall = 'under_cbetting'
    elif n_over > 0 and n_under > 0:
        overall = 'inconsistent'
    else:
        overall = 'balanced'

    reliability = _reliability(sample_hands)

    reasoning = (
        f'C-bet audit across {len(spots)} spots. '
        f'Total EV loss={total_ev_loss:.2f}BB/100. '
        f'Top leak: {top_spot} ({top_ev:.2f}BB/100). '
        f'Over-betting={n_over} spots, under={n_under}, ok={n_ok}. '
        f'Overall: {overall}. Sample={sample_hands} hands ({reliability} reliability).'
    )

    verdict = (
        f'[CBA {overall.upper()}|{reliability}] EV_loss={total_ev_loss:.2f}BB/100 | '
        f'top_leak={top_spot[:20]} ({top_ev:.2f}BB) | '
        f'over={n_over} under={n_under} ok={n_ok}'
    )

    tips = []

    # Priority fix list (top 3 leaks)
    priority_spots = [s for s in spots if s.ev_loss_bb100 > 0][:3]
    if priority_spots:
        tips.append(
            f'TOP {len(priority_spots)} LEAKS (fix these first):\n'
            + '\n'.join(f'  {i+1}. {s.fix_advice} (-{s.ev_loss_bb100:.2f}BB/100)'
                       for i, s in enumerate(priority_spots))
        )

    if overall == 'over_cbetting':
        tips.append(
            f'OVER-CBETTING PATTERN: You cbet too often in {n_over} spots. '
            f'Fix: check back more bluffs (keep range balanced). '
            f'Opponents will start floating more profitably and your range becomes transparent.'
        )
    elif overall == 'under_cbetting':
        tips.append(
            f'UNDER-CBETTING PATTERN: You check too often in {n_under} spots. '
            f'Fix: bet more frequently on boards where you have range advantage. '
            f'Leaving fold equity on the table against weak hands.'
        )

    if reliability in ('very_low', 'low'):
        tips.append(
            f'LOW SAMPLE WARNING ({sample_hands} hands): Results unreliable. '
            f'Need 5000+ hands per spot for meaningful cbet frequency data. '
            f'Track via HUD; revisit this audit after more sessions.'
        )

    if total_ev_loss >= 3.0:
        tips.append(
            f'HIGH EV LOSS: Fixing all cbet leaks could recover {total_ev_loss:.1f}BB/100. '
            f'Focus on the top 2-3 spots first for maximum impact.'
        )

    return CbetAuditResult(
        cbet_ip_dry=cbet_ip_dry,
        cbet_ip_wet=cbet_ip_wet,
        cbet_oop_dry=cbet_oop_dry,
        cbet_oop_wet=cbet_oop_wet,
        cbet_3bet_ip=cbet_3bet_ip,
        cbet_3bet_oop=cbet_3bet_oop,
        cbet_multiway=cbet_multiway,
        sample_hands=sample_hands,
        spots=spots,
        total_ev_loss_bb100=round(total_ev_loss, 2),
        top_leak=top_spot,
        top_leak_ev=round(top_ev, 2),
        reliability=reliability,
        overall_direction=overall,
        over_cbet_spots=n_over,
        under_cbet_spots=n_under,
        on_target_spots=n_ok,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def cba_one_liner(r: CbetAuditResult) -> str:
    return (
        f'[CBA {r.overall_direction.upper()}|{r.reliability}] '
        f'loss={r.total_ev_loss_bb100:.2f}BB/100 | '
        f'top={r.top_leak[:18]} ({r.top_leak_ev:.2f}BB) | '
        f'over={r.over_cbet_spots} under={r.under_cbet_spots} ok={r.on_target_spots}'
    )
