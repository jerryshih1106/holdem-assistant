"""
Population Reads by Stakes (population_reads.py)

When you first sit at a table with 0 hands on any villain, all advisors
need calibrated default stats. Population averages at each stake level are
well-documented: micro-stakes players are looser and more passive; higher
stakes players are tighter, more aggressive, and harder to exploit.

This module provides:
  1. Stake-specific average stats (VPIP, PFR, AF, 3-bet, fold-to-cbet, etc.)
  2. Exploit adjustments derived from those defaults
  3. Transition hints: what to watch for to update the default

Stake populations (6-max cash, approximate):
  NL2:   VPIP~37%, PFR~14%, AF~1.2, 3bet~4.5%, FCbet~57%
  NL5:   VPIP~33%, PFR~16%, AF~1.4, 3bet~5%,   FCbet~55%
  NL10:  VPIP~29%, PFR~18%, AF~1.7, 3bet~5.5%, FCbet~53%
  NL25:  VPIP~26%, PFR~19%, AF~2.0, 3bet~6%,   FCbet~51%
  NL50:  VPIP~24%, PFR~20%, AF~2.2, 3bet~6.5%, FCbet~49%
  NL100: VPIP~23%, PFR~20%, AF~2.4, 3bet~7%,   FCbet~48%
  NL200: VPIP~22%, PFR~20%, AF~2.5, 3bet~7.5%, FCbet~47%
  NL500: VPIP~21%, PFR~19%, AF~2.6, 3bet~8%,   FCbet~46%

Usage:
    from poker.population_reads import get_population_stats, PopulationStats
    stats = get_population_stats(10)   # NL10
    print(stats.vpip, stats.fold_to_cbet)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PopulationStats:
    """Average opponent profile at a given stake level."""
    stake_nl: int          # e.g. 2, 5, 10, 25, 50, 100, 200, 500
    stake_label: str       # e.g. 'NL10'
    player_pool: str       # 'rec_dominant', 'mixed', 'reg_dominant'

    # Core HUD stats
    vpip: float            # voluntary put money in pot (fraction)
    pfr: float             # pre-flop raise (fraction)
    af: float              # aggression factor
    three_bet: float       # 3-bet frequency (fraction)
    fold_to_3bet: float    # fold to 3-bet frequency
    cbet_freq: float       # c-bet frequency
    fold_to_cbet: float    # fold to c-bet frequency
    wtsd: float            # went-to-showdown frequency

    # Derived stats
    pfr_to_vpip: float     # PFR/VPIP ratio (higher = more aggressive/positional)
    limp_freq: float       # VPIP - PFR ≈ limping frequency

    # Exploit strategy adjustments (vs GTO baseline)
    cbet_adj: float        # +/- adjust to cbet frequency (vs GTO 50%)
    threebet_adj: float    # +/- adjust to 3-bet frequency
    valuebet_size_mult: float   # multiply value bet size by this
    bluff_freq_mult: float      # multiply bluff frequency by this

    # Signature tells
    primary_leak: str      # biggest exploitable tendency
    secondary_leak: str
    watch_for: List[str] = field(default_factory=list)  # tells to update read


# ── Population data table ─────────────────────────────────────────────────────
# Each entry: (stake_nl, vpip, pfr, af, 3bet, fold_to_3bet, cbet, fcbet, wtsd)
_STAKE_DATA = [
    (2,   0.370, 0.140, 1.20, 0.045, 0.62, 0.52, 0.570, 0.31),
    (5,   0.330, 0.160, 1.40, 0.050, 0.60, 0.53, 0.550, 0.30),
    (10,  0.290, 0.180, 1.70, 0.055, 0.58, 0.55, 0.530, 0.29),
    (25,  0.260, 0.190, 2.00, 0.060, 0.56, 0.57, 0.510, 0.28),
    (50,  0.240, 0.200, 2.20, 0.065, 0.54, 0.58, 0.490, 0.27),
    (100, 0.230, 0.200, 2.40, 0.070, 0.52, 0.59, 0.480, 0.26),
    (200, 0.220, 0.200, 2.50, 0.075, 0.51, 0.60, 0.470, 0.26),
    (500, 0.210, 0.190, 2.60, 0.080, 0.50, 0.60, 0.460, 0.25),
]


def _closest_stake(stake_nl: int) -> tuple:
    """Find the data row for the closest stake level."""
    best = min(_STAKE_DATA, key=lambda row: abs(row[0] - stake_nl))
    return best


def get_population_stats(stake_nl: int) -> PopulationStats:
    """
    Return population-average stats for a given NL stake level.

    Args:
        stake_nl: Buy-in level in USD (2, 5, 10, 25, 50, 100, 200, 500)

    Returns:
        PopulationStats calibrated to that stake level
    """
    row = _closest_stake(stake_nl)
    nl, vpip, pfr, af, threbet, fold_3bet, cbet, fcbet, wtsd = row

    pfr_ratio = pfr / vpip if vpip > 0 else 0.5
    limp = vpip - pfr

    # Player pool classification
    if nl <= 10:
        pool = 'rec_dominant'
    elif nl <= 50:
        pool = 'mixed'
    else:
        pool = 'reg_dominant'

    # Exploit adjustments vs GTO baseline
    # High fcbet → we can cbet more often
    cbet_adj = (fcbet - 0.50) * 1.2    # +12% cbet per 10% above 50% fold
    # High fold_to_3bet → 3-bet more
    threebet_adj = (fold_3bet - 0.55) * 0.8
    # High vpip / passive → size up for value
    value_mult = 1.0 + (vpip - 0.25) * 0.8 + (1.5 - af) * 0.10
    value_mult = max(0.8, min(1.6, value_mult))
    # Passive (low af) → fewer bluffs are needed
    bluff_mult = max(0.4, min(1.2, 0.7 + (af - 1.5) * 0.2))

    # Primary leak
    if vpip > 0.32 and af < 1.5:
        primary = 'loose-passive: calls too much, rarely raises'
        secondary = 'high VPIP: enters too many pots OOP'
    elif vpip > 0.28 and fold_3bet > 0.58:
        primary = 'folds too much to 3-bets'
        secondary = 'wide VPIP + low aggression = exploitable'
    elif fcbet > 0.55:
        primary = 'folds too often to c-bets'
        secondary = 'can be probed relentlessly on dry boards'
    else:
        primary = 'balanced: fewer dominant leaks — play closer to GTO'
        secondary = 'watch for bet sizing tells and showdown hands'

    watch_for = [
        'First limp or open-limp → raise VPIP, likely rec',
        'No 3-bet in 30 hands → pfr_ratio likely < 0.50, fold to 3bet',
        f'Fold to cbet default {fcbet:.0%} — probe all turns after they check',
        'First showdown hand: adjust tight/loose read immediately',
    ]

    return PopulationStats(
        stake_nl=nl,
        stake_label=f'NL{nl}',
        player_pool=pool,
        vpip=round(vpip, 3),
        pfr=round(pfr, 3),
        af=round(af, 2),
        three_bet=round(threbet, 3),
        fold_to_3bet=round(fold_3bet, 3),
        cbet_freq=round(cbet, 3),
        fold_to_cbet=round(fcbet, 3),
        wtsd=round(wtsd, 3),
        pfr_to_vpip=round(pfr_ratio, 3),
        limp_freq=round(limp, 3),
        cbet_adj=round(cbet_adj, 3),
        threebet_adj=round(threebet_adj, 3),
        valuebet_size_mult=round(value_mult, 3),
        bluff_freq_mult=round(bluff_mult, 3),
        primary_leak=primary,
        secondary_leak=secondary,
        watch_for=watch_for,
    )


def default_villain_stats(stake_nl: int, position: str = '') -> dict:
    """
    Return a dict of default villain stats suitable for passing directly
    to other advisors (villain_vpip, villain_pfr, villain_af, etc.).

    Args:
        stake_nl:  Stake level in NL
        position:  Optional position filter ('BTN', 'UTG', etc.) — adjusts
                   VPIP/PFR slightly for positional play

    Returns:
        dict with keys: vpip, pfr, af, fcbet, three_bet, fold_to_3bet, wtsd
    """
    stats = get_population_stats(stake_nl)

    # Positional adjustments: BTN plays wider; UTG tighter
    pos_adj = {
        'UTG': -0.04, 'HJ': -0.02, 'CO': 0.0,
        'BTN': +0.04, 'SB': +0.02, 'BB': +0.06,
    }.get(position.upper() if position else '', 0.0)

    vpip_adj = max(0.10, min(0.60, stats.vpip + pos_adj))
    pfr_adj  = max(0.08, min(0.50, stats.pfr + pos_adj * 0.7))

    return {
        'vpip': round(vpip_adj, 3),
        'pfr':  round(pfr_adj, 3),
        'af':   stats.af,
        'fcbet': stats.fold_to_cbet,
        'three_bet': stats.three_bet,
        'fold_to_3bet': stats.fold_to_3bet,
        'wtsd': stats.wtsd,
        'cbet_freq': stats.cbet_freq,
        'source': f'population_default_{stats.stake_label}',
    }


def population_exploit_summary(stake_nl: int) -> str:
    """One-paragraph exploit plan for unknown villain at this stake."""
    s = get_population_stats(stake_nl)
    return (
        f'NL{stake_nl} default ({s.player_pool}): '
        f'VPIP={s.vpip:.0%} PFR={s.pfr:.0%} AF={s.af:.1f} FCbet={s.fold_to_cbet:.0%}. '
        f'Leak: {s.primary_leak}. '
        f'Cbet {s.cbet_adj:+.0%} vs GTO; '
        f'size value bets {s.valuebet_size_mult:.1f}x; '
        f'bluff {s.bluff_freq_mult:.1f}x. '
        f'3-bet {s.threebet_adj:+.0%}.'
    )
