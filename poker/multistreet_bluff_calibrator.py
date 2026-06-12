"""
Multistreet Bluff Calibrator (multistreet_bluff_calibrator.py)

Calibrates a player's bluffing frequency across flop, turn, and river to
ensure the betting range is balanced (villain indifferent to calling/folding).

KEY CONCEPT: GTO bluff frequencies
  If you bet pot, villain needs 33% equity to call.
  Therefore your value:bluff ratio should be 2:1 (66% value, 33% bluffs).
  Betting 75% pot: villain needs 37.5% to call → 62.5% value, 37.5% bluff OK.
  Betting 50% pot: villain needs 25% to call → 75% value, 25% bluff.

MULTISTREET CONSIDERATIONS:
  Flop bluffs need equity (draws) to continue profitably on turn.
  Turn bluffs should be semi-bluffs or give up (pure air has no equity).
  River: pure bluff territory (no more equity). Must have enough bluffs to stay balanced.

BLUFF FREQUENCY BY STREET (as % of total betting range):
  Flop:  35-45% bluffs is standard (many have equity: draws)
  Turn:  25-35% bluffs (fewer pure bluffs; equity draws shrink)
  River: 20-30% bluffs (pure bluffs only; must be balanced)

GTO BLUFF-TO-VALUE RATIOS:
  river 33% pot: ~40% bluffs
  river 50% pot: 33% bluffs
  river 75% pot: 29% bluffs
  river 100% pot: 25% bluffs
  river 150% pot: 20% bluffs

DISTINCT FROM OTHER MODULES:
  range_protect_advisor.py:   Per-hand balancing on current street
  bluff_frequency.py:         Single-spot bluff decision
  THIS MODULE:                Calibrates bluff % across ALL THREE streets;
                              detects over/under-bluffing patterns; gives
                              specific correction guidance per street.

Usage:
    from poker.multistreet_bluff_calibrator import calibrate_bluffs, BluffCalibration, mbc_one_liner

    result = calibrate_bluffs(
        flop_bluff_pct=0.42,
        turn_bluff_pct=0.38,
        river_bluff_pct=0.18,
        avg_flop_bet_size_pct=0.65,
        avg_turn_bet_size_pct=0.75,
        avg_river_bet_size_pct=0.80,
        sample_hands=3000,
    )
    print(mbc_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# GTO bluff frequency lookup
# --------------------------------------------------------------------------

def _gto_bluff_freq(bet_size_pct: float) -> float:
    """
    GTO river bluff frequency for a given bet size (fraction of pot).
    Alpha = bet / (bet + pot). Bluff freq = alpha (villain must be indifferent).
    """
    alpha = bet_size_pct / (1 + bet_size_pct)
    return round(alpha, 3)


def _gto_flop_bluff_freq(bet_size_pct: float) -> float:
    """
    GTO flop bluff frequency. Higher than river because bluffs have equity.
    Effectively: river_alpha * 1.3 (equity bonus for semi-bluffs).
    """
    base = _gto_bluff_freq(bet_size_pct)
    return round(min(0.55, base * 1.30), 3)


def _gto_turn_bluff_freq(bet_size_pct: float) -> float:
    """GTO turn bluff frequency. Between flop and river."""
    base = _gto_bluff_freq(bet_size_pct)
    return round(min(0.45, base * 1.15), 3)


def _street_assessment(hero_pct: float, gto_pct: float) -> tuple:
    deviation = round(hero_pct - gto_pct, 3)
    abs_dev = abs(deviation)
    if abs_dev <= 0.04:
        status = 'balanced'
        severity = 'ok'
    elif deviation > 0:
        status = 'over_bluffing'
        severity = 'critical' if abs_dev >= 0.15 else 'major' if abs_dev >= 0.08 else 'minor'
    else:
        status = 'under_bluffing'
        severity = 'critical' if abs_dev >= 0.15 else 'major' if abs_dev >= 0.08 else 'minor'
    return deviation, status, severity


def _ev_loss_per_10pct(street: str, bet_size_pct: float) -> float:
    """Estimated BB/100 lost per 10% absolute deviation."""
    base = {'flop': 0.55, 'turn': 0.70, 'river': 0.85}.get(street, 0.65)
    size_mult = min(1.5, max(0.7, 0.7 + bet_size_pct * 0.5))
    return round(base * size_mult, 2)


def _fix_advice(street: str, hero_pct: float, gto_pct: float, bet_size_pct: float, status: str) -> str:
    if status == 'balanced':
        return f'{street.capitalize()}: On target ({hero_pct:.0%} vs GTO {gto_pct:.0%}). Keep bluff frequency stable.'
    elif status == 'over_bluffing':
        delta = hero_pct - gto_pct
        return (
            f'{street.capitalize()}: OVER-BLUFFING by {delta:.0%} ({hero_pct:.0%} vs GTO {gto_pct:.0%} @ {bet_size_pct:.0%} pot). '
            f'{"Fold more air; only bet draws with nut blockers." if street == "flop" else "Give up more turn draws that missed." if street == "turn" else "Remove weakest bluffs; keep nut blockers only on river."}'
        )
    else:
        delta = gto_pct - hero_pct
        return (
            f'{street.capitalize()}: UNDER-BLUFFING by {delta:.0%} ({hero_pct:.0%} vs GTO {gto_pct:.0%} @ {bet_size_pct:.0%} pot). '
            f'{"Add more semi-bluffs (draws) to your flop cbet range." if street == "flop" else "Bluff more with gutshots/backdoors on turn." if street == "turn" else "Add more river bluffs with nut blockers (AXs, etc.)."}'
        )


def _consistency_assessment(flop_status: str, turn_status: str, river_status: str) -> str:
    statuses = [flop_status, turn_status, river_status]
    n_over = sum(1 for s in statuses if s == 'over_bluffing')
    n_under = sum(1 for s in statuses if s == 'under_bluffing')
    if n_over >= 2:
        return 'over_bluffing'
    elif n_under >= 2:
        return 'under_bluffing'
    elif n_over >= 1 and n_under >= 1:
        return 'inconsistent'
    return 'balanced'


@dataclass
class BluffCalibration:
    # Inputs
    flop_bluff_pct: float
    turn_bluff_pct: float
    river_bluff_pct: float
    avg_flop_bet_size_pct: float
    avg_turn_bet_size_pct: float
    avg_river_bet_size_pct: float
    sample_hands: int

    # GTO targets
    gto_flop: float
    gto_turn: float
    gto_river: float

    # Per-street deviations
    flop_deviation: float
    turn_deviation: float
    river_deviation: float
    flop_status: str    # 'balanced' / 'over_bluffing' / 'under_bluffing'
    turn_status: str
    river_status: str
    flop_severity: str  # 'ok' / 'minor' / 'major' / 'critical'
    turn_severity: str
    river_severity: str

    # EV impact
    flop_ev_loss: float   # BB/100 lost from deviation
    turn_ev_loss: float
    river_ev_loss: float
    total_ev_loss: float

    # Overall
    overall_pattern: str  # 'over_bluffing' / 'under_bluffing' / 'inconsistent' / 'balanced'

    # Fixes
    flop_fix: str
    turn_fix: str
    river_fix: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def calibrate_bluffs(
    flop_bluff_pct: float = 0.38,
    turn_bluff_pct: float = 0.30,
    river_bluff_pct: float = 0.22,
    avg_flop_bet_size_pct: float = 0.65,
    avg_turn_bet_size_pct: float = 0.75,
    avg_river_bet_size_pct: float = 0.80,
    sample_hands: int = 3000,
) -> BluffCalibration:
    """
    Calibrate bluff frequencies across all three streets.

    Args:
        flop_bluff_pct:          Hero's bluff % of total flop bets (0.0-1.0)
        turn_bluff_pct:          Hero's bluff % of total turn bets
        river_bluff_pct:         Hero's bluff % of total river bets
        avg_flop_bet_size_pct:   Average flop bet as fraction of pot
        avg_turn_bet_size_pct:   Average turn bet as fraction of pot
        avg_river_bet_size_pct:  Average river bet as fraction of pot
        sample_hands:            Hands in sample

    Returns:
        BluffCalibration
    """
    gto_f = _gto_flop_bluff_freq(avg_flop_bet_size_pct)
    gto_t = _gto_turn_bluff_freq(avg_turn_bet_size_pct)
    gto_r = _gto_bluff_freq(avg_river_bet_size_pct)

    fd, fs, fsev = _street_assessment(flop_bluff_pct, gto_f)
    td, ts, tsev = _street_assessment(turn_bluff_pct, gto_t)
    rd, rs, rsev = _street_assessment(river_bluff_pct, gto_r)

    ev_f = _ev_loss_per_10pct('flop', avg_flop_bet_size_pct) * abs(fd) / 0.10 if abs(fd) > 0.04 else 0.0
    ev_t = _ev_loss_per_10pct('turn', avg_turn_bet_size_pct) * abs(td) / 0.10 if abs(td) > 0.04 else 0.0
    ev_r = _ev_loss_per_10pct('river', avg_river_bet_size_pct) * abs(rd) / 0.10 if abs(rd) > 0.04 else 0.0
    total_ev = round(ev_f + ev_t + ev_r, 2)

    overall = _consistency_assessment(fs, ts, rs)
    ff = _fix_advice('flop', flop_bluff_pct, gto_f, avg_flop_bet_size_pct, fs)
    tf = _fix_advice('turn', turn_bluff_pct, gto_t, avg_turn_bet_size_pct, ts)
    rf = _fix_advice('river', river_bluff_pct, gto_r, avg_river_bet_size_pct, rs)

    reasoning = (
        f'Multistreet bluff calibration: flop={flop_bluff_pct:.0%}(gto={gto_f:.0%},{fs}), '
        f'turn={turn_bluff_pct:.0%}(gto={gto_t:.0%},{ts}), '
        f'river={river_bluff_pct:.0%}(gto={gto_r:.0%},{rs}). '
        f'Total EV loss={total_ev:.2f}BB/100. Pattern={overall}.'
    )

    verdict = (
        f'[MBC {overall.upper()}] loss={total_ev:.2f}BB/100 | '
        f'f={flop_bluff_pct:.0%}(gto={gto_f:.0%},{fsev}) '
        f't={turn_bluff_pct:.0%}(gto={gto_t:.0%},{tsev}) '
        f'r={river_bluff_pct:.0%}(gto={gto_r:.0%},{rsev})'
    )

    tips = []
    tips.append(ff)
    tips.append(tf)
    tips.append(rf)

    if overall == 'over_bluffing':
        tips.append(
            f'OVER-BLUFFING PATTERN: Villains will profit by calling you down. '
            f'Apply the "alpha filter": only bluff when you have a nut blocker or '
            f'the board texture heavily favors your perceived range.'
        )
    elif overall == 'under_bluffing':
        tips.append(
            f'UNDER-BLUFFING PATTERN: Villains will profitably over-fold vs your bets. '
            f'You are leaving money on the table. '
            f'Add well-chosen bluffs with nut blockers: AX on flush-possible boards, '
            f'missed draws on rivers where your range has polarized naturally.'
        )
    elif overall == 'inconsistent':
        tips.append(
            f'INCONSISTENT PATTERN: Bluff too much on some streets, too little on others. '
            f'Fix: plan bluff routes from flop → this hand will bluff all 3 streets if draws miss, '
            f'or give up on flop and reduce downstream frequency accordingly.'
        )

    tips.append(
        f'GTO SUMMARY: At your bet sizes ({avg_flop_bet_size_pct:.0%}/{avg_turn_bet_size_pct:.0%}/{avg_river_bet_size_pct:.0%} pot), '
        f'target bluff rates: flop={gto_f:.0%}, turn={gto_t:.0%}, river={gto_r:.0%}. '
        f'River bluff formula: bet/(pot+bet). Use nut blockers to select specific bluffs.'
    )

    return BluffCalibration(
        flop_bluff_pct=round(flop_bluff_pct, 3),
        turn_bluff_pct=round(turn_bluff_pct, 3),
        river_bluff_pct=round(river_bluff_pct, 3),
        avg_flop_bet_size_pct=avg_flop_bet_size_pct,
        avg_turn_bet_size_pct=avg_turn_bet_size_pct,
        avg_river_bet_size_pct=avg_river_bet_size_pct,
        sample_hands=sample_hands,
        gto_flop=gto_f,
        gto_turn=gto_t,
        gto_river=gto_r,
        flop_deviation=fd,
        turn_deviation=td,
        river_deviation=rd,
        flop_status=fs,
        turn_status=ts,
        river_status=rs,
        flop_severity=fsev,
        turn_severity=tsev,
        river_severity=rsev,
        flop_ev_loss=round(ev_f, 2),
        turn_ev_loss=round(ev_t, 2),
        river_ev_loss=round(ev_r, 2),
        total_ev_loss=total_ev,
        overall_pattern=overall,
        flop_fix=ff,
        turn_fix=tf,
        river_fix=rf,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def mbc_one_liner(r: BluffCalibration) -> str:
    return (
        f'[MBC {r.overall_pattern.upper()}] loss={r.total_ev_loss:.2f}BB/100 | '
        f'flop={r.flop_bluff_pct:.0%}(gto={r.gto_flop:.0%}) '
        f'turn={r.turn_bluff_pct:.0%}(gto={r.gto_turn:.0%}) '
        f'river={r.river_bluff_pct:.0%}(gto={r.gto_river:.0%})'
    )
