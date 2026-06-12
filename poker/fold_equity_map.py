"""
Fold Equity Map (fold_equity_map.py)

Fold equity is the probability that all opponents fold when hero bets or raises.
It is a core component of bluff EV:

  EV(bluff) = fold_equity × pot - (1 - fold_equity) × bet

For a bet to be profitable without equity:
  fold_equity > bet / (pot + bet)   [= alpha]

This module provides:
1. Fold equity estimates for different bet sizes vs villain archetypes
2. The minimum fold equity needed for a bluff to be profitable
3. Adjustments for street, position, board texture
4. A complete fold equity map: {bet_size: fold_equity} for each villain type

VILLAIN ARCHETYPES:
  fish:             VPIP>40%, rarely folds — fold equity very low
  calling_station:  WTSD>45% — calls down with any pair
  nit:              VPIP<18%, folds to pressure — fold equity high
  tight_reg:        Solid TAG, folds mediocre hands
  balanced_reg:     GTO-ish, defends at MDF
  lag:              Loose-aggressive, calls AND raises — dangerous
  maniac:           Never folds, often re-raises

BASELINE FOLD FREQUENCIES (river):
  Bet 25%pot: 20-28% for balanced reg
  Bet 50%pot: 28-35%
  Bet 75%pot: 35-42%
  Bet 100%pot: 40-48%
  Bet 150%pot: 47-55%

ADJUSTMENTS:
  - Fish: -15% fold vs any size (they call wide)
  - Nit: +15% fold (they give up)
  - Flop (vs river): -10% fold (more draws/pairs stay in)
  - Turn: -5% fold vs river baseline
  - OOP villain: -3% fold (calling is cheaper for them in terms of pot odds)
  - High board (A/K high): villain calls wider (perceived top pair)
  - Low board (6-4-2): villain folds more (less connected to range)

Usage:
    from poker.fold_equity_map import calc_fold_equity_map
    from poker.fold_equity_map import FoldEquityMap, fold_equity_one_liner

    result = calc_fold_equity_map(
        villain_type='balanced_reg',
        street='turn',
        hero_pos='IP',
        board_type='medium',
        villain_vpip=0.28,
        villain_wtsd=0.32,
        villain_af=2.0,
        n_opponents=1,
    )
    print(fold_equity_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List


# ── Base fold frequencies by bet size (PSB = pot-sized bet = 100%) ───────────

_BASE_FOLD_FREQ_RIVER = {
    0.25: 0.24,   # 1/4 pot → 24% fold
    0.33: 0.27,
    0.50: 0.32,
    0.67: 0.37,
    0.75: 0.40,
    1.00: 0.45,
    1.33: 0.50,
    1.50: 0.52,
    2.00: 0.57,
}

# Street adjustment relative to river
_STREET_ADJ = {
    'flop':   -0.10,   # more hands to come, villain continues wider
    'turn':   -0.05,
    'river':  +0.00,
}

# Villain type adjustments
_VILLAIN_TYPE_ADJ = {
    'fish':             -0.18,
    'calling_station':  -0.15,
    'loose_passive':    -0.10,
    'balanced_reg':     +0.00,
    'tight_reg':        +0.08,
    'nit':              +0.15,
    'lag':              -0.08,   # raises instead of folding → less fold equity
    'maniac':           -0.20,
}

# Board type adjustments
_BOARD_ADJ = {
    'dry':      +0.05,    # low connected boards fold more (hero range hits)
    'medium':   +0.00,
    'wet':      -0.05,    # draws stay, fold equity drops
    'monotone': -0.08,    # flush possible, villain defends draws
    'paired':   -0.02,
}

# Hero position adjustment
_POS_ADJ = {
    'IP':  +0.03,   # IP bets carry more credibility
    'OOP': -0.03,
}


def _estimate_fold_freq(
    bet_pct: float,
    villain_type: str,
    street: str,
    hero_pos: str,
    board_type: str,
    villain_vpip: float,
    villain_wtsd: float,
) -> float:
    """Estimate fold frequency for a specific bet size."""
    # Interpolate between known bet sizes
    sorted_sizes = sorted(_BASE_FOLD_FREQ_RIVER.keys())
    if bet_pct <= sorted_sizes[0]:
        base = _BASE_FOLD_FREQ_RIVER[sorted_sizes[0]]
    elif bet_pct >= sorted_sizes[-1]:
        base = _BASE_FOLD_FREQ_RIVER[sorted_sizes[-1]]
    else:
        # Linear interpolation
        for i in range(len(sorted_sizes) - 1):
            lo, hi = sorted_sizes[i], sorted_sizes[i + 1]
            if lo <= bet_pct <= hi:
                t = (bet_pct - lo) / (hi - lo)
                base = _BASE_FOLD_FREQ_RIVER[lo] + t * (_BASE_FOLD_FREQ_RIVER[hi] - _BASE_FOLD_FREQ_RIVER[lo])
                break
        else:
            base = 0.35

    # Apply adjustments
    adj = 0.0
    adj += _STREET_ADJ.get(street, 0.0)
    adj += _VILLAIN_TYPE_ADJ.get(villain_type, 0.0)
    adj += _BOARD_ADJ.get(board_type, 0.0)
    adj += _POS_ADJ.get(hero_pos, 0.0)

    # VPIP adjustment: higher VPIP = less folding
    vpip_adj = -(villain_vpip - 0.28) * 0.40  # each 10% above 28% = -4%
    adj += vpip_adj

    # WTSD adjustment: high WTSD = less folding
    wtsd_adj = -(villain_wtsd - 0.32) * 0.30  # each 10% above 32% = -3%
    adj += wtsd_adj

    fold_freq = base + adj
    return round(max(0.05, min(0.85, fold_freq)), 3)


def _alpha(bet_pct: float) -> float:
    """Minimum fold equity needed to profit without equity (alpha)."""
    return round(bet_pct / (1 + 2 * bet_pct), 3)


def _bluff_ev(fold_freq: float, bet_pct: float, hero_equity: float = 0.0) -> float:
    """
    EV of bluff in units of pot:
    EV = fold × 1.0 + (1-fold) × [equity × (1 + 2*bet) - bet]
    """
    called_ev = hero_equity * (1.0 + 2 * bet_pct) - bet_pct
    ev = fold_freq * 1.0 + (1 - fold_freq) * called_ev
    return round(ev, 3)


def _break_even_fold(bet_pct: float, hero_equity: float) -> float:
    """Minimum fold frequency to break even given hero equity."""
    # EV = 0 → fold × 1.0 + (1-fold) × called_ev = 0
    called_ev = hero_equity * (1.0 + 2 * bet_pct) - bet_pct
    if called_ev >= 0:
        return 0.0  # profitable even when called
    # fold + (1-fold) × called_ev = 0
    # fold × (1 - called_ev) = -called_ev
    denom = 1.0 - called_ev
    if denom <= 0:
        return 1.0
    return round(max(0.0, -called_ev / denom), 3)


@dataclass
class FoldEquityMap:
    """Fold equity analysis for different bet sizes vs a specific villain."""
    villain_type: str
    street: str
    hero_pos: str
    board_type: str
    villain_vpip: float
    villain_wtsd: float
    villain_af: float
    n_opponents: int

    # Maps: bet_size_pct → fold_equity
    fold_equity_by_size: Dict[float, float]     # {0.33: 0.28, 0.50: 0.33, ...}
    alpha_by_size: Dict[float, float]            # minimum fold needed (no equity)
    bluff_ev_by_size: Dict[float, float]         # EV in pot units (0 equity bluff)
    profitable_sizes: List[float]                # sizes where bluff is profitable

    # Key metrics
    optimal_bluff_size: float                    # best size for pure bluff
    break_even_fold_by_size: Dict[float, float]  # at 0 equity

    # Summary
    verdict: str
    bluff_feasibility: str                       # 'excellent', 'good', 'marginal', 'poor'
    reasoning: str
    tips: List[str] = field(default_factory=list)


def calc_fold_equity_map(
    villain_type: str = 'balanced_reg',
    street: str = 'turn',
    hero_pos: str = 'IP',
    board_type: str = 'medium',
    villain_vpip: float = 0.28,
    villain_wtsd: float = 0.32,
    villain_af: float = 2.0,
    n_opponents: int = 1,
    hero_equity: float = 0.0,
) -> FoldEquityMap:
    """
    Calculate fold equity map across bet sizes for a specific villain.

    Args:
        villain_type:  'fish', 'calling_station', 'nit', 'tight_reg',
                       'balanced_reg', 'lag', 'maniac', 'loose_passive'
        street:        'flop', 'turn', 'river'
        hero_pos:      'IP' or 'OOP'
        board_type:    'dry', 'medium', 'wet', 'monotone', 'paired'
        villain_vpip:  Villain's VPIP
        villain_wtsd:  Villain's WTSD
        villain_af:    Villain's aggression factor
        n_opponents:   Number of opponents (multiway reduces fold equity)
        hero_equity:   Hero's actual equity when called (for EV calc)

    Returns:
        FoldEquityMap
    """
    bet_sizes = [0.25, 0.33, 0.50, 0.67, 0.75, 1.00, 1.33, 1.50, 2.00]

    fold_eq_map: Dict[float, float] = {}
    alpha_map: Dict[float, float] = {}
    bluff_ev_map: Dict[float, float] = {}
    be_fold_map: Dict[float, float] = {}

    for bs in bet_sizes:
        fe = _estimate_fold_freq(bs, villain_type, street, hero_pos, board_type, villain_vpip, villain_wtsd)
        # Multiway: fold equity decreases (all opponents must fold)
        if n_opponents > 1:
            fe = fe ** n_opponents  # independent fold probabilities
        fold_eq_map[bs] = fe
        alpha_map[bs] = _alpha(bs)
        bluff_ev_map[bs] = _bluff_ev(fe, bs, hero_equity)
        be_fold_map[bs] = _break_even_fold(bs, hero_equity)

    # Profitable sizes: where bluff EV >= 0
    profitable = [bs for bs in bet_sizes if bluff_ev_map[bs] >= 0]

    # Optimal bluff size: highest EV among profitable sizes
    if profitable:
        optimal = max(profitable, key=lambda bs: bluff_ev_map[bs])
    else:
        # Find closest to profitable
        optimal = min(bet_sizes, key=lambda bs: abs(bluff_ev_map[bs]))

    # Bluff feasibility
    max_ev = max(bluff_ev_map.values())
    if max_ev >= 0.15:
        feasibility = 'excellent'
    elif max_ev >= 0.05:
        feasibility = 'good'
    elif max_ev >= 0.0:
        feasibility = 'marginal'
    else:
        feasibility = 'poor'

    verdict = (
        f'{villain_type.replace("_", " ").title()} on {street} ({board_type} board, {hero_pos}): '
        f'Bluff feasibility={feasibility}. '
        f'Best bluff size={optimal:.0%}pot (fold_eq={fold_eq_map[optimal]:.0%}, EV={bluff_ev_map[optimal]:+.3f}pot). '
        f'Profitable bluff sizes: {[f"{b:.0%}" for b in profitable] if profitable else "none"}.'
    )

    reasoning = (
        f'Villain: {villain_type} (VPIP={villain_vpip:.0%}, WTSD={villain_wtsd:.0%}, AF={villain_af:.1f}). '
        f'Street={street}, pos={hero_pos}, board={board_type}, n_opp={n_opponents}. '
        f'Fold equity range: {min(fold_eq_map.values()):.0%} (25%pot) to '
        f'{max(fold_eq_map.values()):.0%} (200%pot). '
        f'Alpha at 50%pot={alpha_map[0.50]:.0%}. '
        f'Max bluff EV at {optimal:.0%}pot={bluff_ev_map[optimal]:+.3f}pot. '
        f'Feasibility: {feasibility}.'
    )

    tips = []
    if villain_type in ('fish', 'calling_station', 'maniac'):
        tips.append(
            f'CALLING VILLAIN ({villain_type}): '
            f'Do NOT bluff this villain — fold equity is too low. '
            f'Even at 200%pot, fold eq is only {fold_eq_map[2.00]:.0%} (need >{_alpha(2.00):.0%}). '
            f'Redirect to VALUE BETTING: extract more from their calling tendency instead.'
        )
    if villain_type in ('nit', 'tight_reg') and feasibility in ('excellent', 'good'):
        tips.append(
            f'NIT/TIGHT VILLAIN: Excellent bluff opportunity. '
            f'Use {optimal:.0%}pot ({fold_eq_map[optimal]:.0%} fold eq). '
            f'Nits over-fold to pressure — target spots where they lack strong hands. '
            f'Flop dry boards where their range misses.'
        )
    if n_opponents > 1:
        tips.append(
            f'MULTIWAY POT ({n_opponents} opponents): Fold equity drops dramatically. '
            f'50%pot: each player folds {_estimate_fold_freq(0.50, villain_type, street, hero_pos, board_type, villain_vpip, villain_wtsd):.0%} → '
            f'combined fold eq {fold_eq_map[0.50]:.0%}. '
            f'Avoid bluffing multiway unless you have semi-bluff equity.'
        )
    if street == 'flop' and feasibility in ('excellent', 'good'):
        tips.append(
            f'FLOP BLUFF: Has fold equity but remember you have 2 streets to go. '
            f'Optimal: use {optimal:.0%}pot for balanced range. '
            f'Avoid over-bluffing flop — villain may call to see turn then fold.'
        )
    if not tips:
        tips.append(
            f'{villain_type.replace("_", " ").title()} fold equity: '
            f'25%pot={fold_eq_map[0.25]:.0%}, 50%pot={fold_eq_map[0.50]:.0%}, '
            f'100%pot={fold_eq_map[1.00]:.0%}, 200%pot={fold_eq_map[2.00]:.0%}. '
            f'Best bluff size: {optimal:.0%}pot (EV={bluff_ev_map[optimal]:+.3f}pot).'
        )

    return FoldEquityMap(
        villain_type=villain_type,
        street=street,
        hero_pos=hero_pos,
        board_type=board_type,
        villain_vpip=round(villain_vpip, 3),
        villain_wtsd=round(villain_wtsd, 3),
        villain_af=round(villain_af, 1),
        n_opponents=n_opponents,
        fold_equity_by_size=fold_eq_map,
        alpha_by_size=alpha_map,
        bluff_ev_by_size=bluff_ev_map,
        profitable_sizes=profitable,
        optimal_bluff_size=optimal,
        break_even_fold_by_size=be_fold_map,
        verdict=verdict,
        bluff_feasibility=feasibility,
        reasoning=reasoning,
        tips=tips,
    )


def fold_equity_one_liner(r: FoldEquityMap) -> str:
    fe_50 = r.fold_equity_by_size.get(0.50, 0.0)
    fe_100 = r.fold_equity_by_size.get(1.00, 0.0)
    return (
        f'[FE {r.villain_type}|{r.street}|{r.hero_pos}] {r.bluff_feasibility.upper()} | '
        f'50%pot_fe={fe_50:.0%} 100%pot_fe={fe_100:.0%} '
        f'best={r.optimal_bluff_size:.0%}pot(ev={r.bluff_ev_by_size.get(r.optimal_bluff_size, 0):+.3f}) | '
        f'profitable={len(r.profitable_sizes)}/9 sizes'
    )
