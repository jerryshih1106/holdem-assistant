"""
Dynamic C-bet Size Optimizer (dynamic_cbet_size_optimizer.py)

Computes the OPTIMAL c-bet SIZE (not just frequency) based on:
1. Board texture and range advantage
2. Villain's VPIP/FCBet tendencies
3. Stack depth and SPR
4. Street (flop/turn/river)
5. Hand category (protection vs value)

THEORY:
  C-bet sizing is not fixed. The optimal size depends on:

  1. RANGE-BASED SIZING:
     - Strong range advantage: small bet (30-40% pot) -- polarize; villain
       cannot defend enough to stop EV
     - Weak range advantage: standard (50-65% pot) or no bet
     - Nut advantage: large (70-85%+) -- maximize value

  2. HAND-BASED SIZING:
     - Draws (protection): larger bets charge more per out
     - Made value: standard or thin value sizing
     - Bluffs: sizing depends on fold equity needed

  3. VILLAIN ADJUSTMENT:
     - High FCBet (>65%): bet ANY size; villain folds too much
     - Low FCBet (<35%): bet larger for value; small bets get called wide
     - Calling station: bigger bets extract more value per combo called

  4. SPR GEOMETRY:
     - Low SPR (<4): commit now with large bets; protect SPR math
     - Medium SPR (4-8): standard sizing to build for river
     - High SPR (8+): small bets maintain multiple streets of action

  OPTIMAL SIZE FORMULA:
  size = base_size × range_adj × villain_adj × spr_adj × street_adj
  where:
    base_size = 0.55 (standard IP flop cbet)
    range_adj = f(range advantage score)
    villain_adj = f(FCBet, VPIP)
    spr_adj = f(SPR)
    street_adj = f(street)

DISTINCT FROM:
  range_cbet.py:     C-bet frequency + basic sizing
  bet_sizing_ev.py:  EV comparison across sizes
  adaptive_sizing.py: Villain-type-specific sizing
  THIS MODULE:       DYNAMIC optimal size for THIS specific cbet spot;
                     ALL factors combined; geometric pot building.
"""

from dataclasses import dataclass, field
from typing import List


# Base c-bet sizes by position and street
BASE_CBET_SIZE: dict = {
    ('ip',  'flop'):  0.55,
    ('ip',  'turn'):  0.65,
    ('ip',  'river'): 0.70,
    ('oop', 'flop'):  0.60,
    ('oop', 'turn'):  0.70,
    ('oop', 'river'): 0.75,
}

# Range advantage adjustment (score 0-10)
def _range_adj(range_score: float) -> float:
    if range_score >= 8.0:
        return 0.75  # dominant advantage: small bet works
    elif range_score >= 6.0:
        return 0.90
    elif range_score >= 4.0:
        return 1.00  # balanced: standard size
    elif range_score >= 2.0:
        return 1.15  # slight disadvantage: bet bigger for fold equity
    else:
        return 1.30  # disadvantage: large or no bet


def _villain_adj(villain_fcbet: float, villain_vpip: float) -> float:
    if villain_fcbet >= 0.65:
        return 0.80   # folds too much; small bet fine
    elif villain_fcbet <= 0.30:
        return 1.25   # never folds; bet bigger for value
    elif villain_vpip >= 0.45:
        return 1.15   # loose passive; value bet bigger
    elif villain_vpip <= 0.18:
        return 0.90   # tight; no need for large bets
    return 1.00


def _spr_adj(spr: float) -> float:
    if spr <= 2.0:
        return 1.40   # near all-in; commit now
    elif spr <= 4.0:
        return 1.15
    elif spr <= 8.0:
        return 1.00   # standard
    elif spr <= 15.0:
        return 0.85   # deep; small bets maintain multiple streets
    else:
        return 0.75   # very deep; pot control


def _street_adj(street: str) -> float:
    return {'flop': 1.00, 'turn': 1.05, 'river': 1.10}.get(street, 1.00)


def _hand_size_adj(hand_category: str) -> float:
    if hand_category in ('nuts', 'full_house', 'flush', 'straight', 'set'):
        return 1.10   # strong value; maximize
    elif hand_category in ('combo_draw', 'oesd'):
        return 1.15   # protection draw; charge more
    elif hand_category in ('air', 'gutshot'):
        return 0.85   # bluff; smaller but still profitable
    elif hand_category in ('top_pair', 'overpair', 'two_pair'):
        return 1.00   # standard
    return 1.00


def _optimal_size(
    position: str,
    street: str,
    range_score: float,
    villain_fcbet: float,
    villain_vpip: float,
    spr: float,
    hand_category: str,
) -> float:
    base = BASE_CBET_SIZE.get((position, street), 0.60)
    size = (base
            * _range_adj(range_score)
            * _villain_adj(villain_fcbet, villain_vpip)
            * _spr_adj(spr)
            * _street_adj(street)
            * _hand_size_adj(hand_category))
    return round(min(1.50, max(0.25, size)), 2)


@dataclass
class DynamicCbetSizeResult:
    position: str
    street: str
    hand_category: str
    range_score: float
    villain_fcbet: float
    villain_vpip: float
    spr: float
    pot_bb: float

    optimal_size_frac: float
    optimal_bet_bb: float
    size_category: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def optimize_cbet_size(
    position: str = 'ip',
    street: str = 'flop',
    hand_category: str = 'top_pair',
    range_score: float = 5.0,
    villain_fcbet: float = 0.50,
    villain_vpip: float = 0.28,
    spr: float = 6.0,
    pot_bb: float = 15.0,
) -> DynamicCbetSizeResult:
    """
    Compute optimal c-bet size for this specific spot.

    Args:
        position:       'ip' / 'oop'
        street:         'flop' / 'turn' / 'river'
        hand_category:  Hero's hand category
        range_score:    Range advantage score (0-10, higher = hero advantage)
        villain_fcbet:  Villain's fold-to-cbet %
        villain_vpip:   Villain's VPIP
        spr:            Stack-to-pot ratio
        pot_bb:         Current pot in BB

    Returns:
        DynamicCbetSizeResult
    """
    size = _optimal_size(position, street, range_score, villain_fcbet, villain_vpip, spr, hand_category)
    bet_bb = round(pot_bb * size, 1)

    if size <= 0.35:
        size_cat = 'small'
    elif size <= 0.55:
        size_cat = 'standard'
    elif size <= 0.80:
        size_cat = 'large'
    else:
        size_cat = 'overbet'

    verdict = (
        f'[DCS {hand_category}|{position}|{street}] '
        f'CBET {size:.0%}pot = {bet_bb:.1f}BB ({size_cat}) | '
        f'range={range_score:.0f}/10 FCBet={villain_fcbet:.0%}'
    )

    reasoning = (
        f'Optimal cbet size: {position.upper()} {street} with {hand_category}. '
        f'Range advantage: {range_score:.0f}/10. '
        f'Villain: VPIP={villain_vpip:.0%} FCBet={villain_fcbet:.0%}. '
        f'SPR={spr:.1f}. '
        f'Optimal size: {size:.0%}pot = {bet_bb:.1f}BB ({size_cat}).'
    )

    tips = []

    tips.append(
        f'OPTIMAL SIZE: {size:.0%}pot = {bet_bb:.1f}BB on {street}. '
        f'Range adj={_range_adj(range_score):.2f}x, '
        f'villain adj={_villain_adj(villain_fcbet, villain_vpip):.2f}x, '
        f'SPR adj={_spr_adj(spr):.2f}x, '
        f'hand adj={_hand_size_adj(hand_category):.2f}x.'
    )

    if range_score >= 8:
        tips.append(
            f'STRONG RANGE ADVANTAGE (score={range_score:.0f}): Use SMALL bet. '
            f'Villain cannot defend wide enough; {size:.0%}pot extracts max EV. '
            f'Large bets let villain over-fold.'
        )
    elif range_score <= 3:
        tips.append(
            f'WEAK RANGE ADVANTAGE (score={range_score:.0f}): Use LARGE bet or check. '
            f'Need fold equity to compensate for weak range. '
            f'{size:.0%}pot maximizes fold equity.'
        )

    if villain_fcbet >= 0.65:
        tips.append(
            f'HIGH FCBet ({villain_fcbet:.0%}): Villain folds too much. '
            f'Any size works; use {size:.0%}pot for efficiency. '
            f'Increase bluff frequency in this spot.'
        )
    elif villain_fcbet <= 0.30:
        tips.append(
            f'LOW FCBet ({villain_fcbet:.0%}): Villain calls wide. '
            f'Bet bigger ({size:.0%}pot) for more value per call. '
            f'Reduce bluff frequency; only value-bet and strong semi-bluffs.'
        )

    if spr <= 3.0:
        tips.append(
            f'LOW SPR ({spr:.1f}): Commit with {size:.0%}pot bet. '
            f'After call, SPR ~{round((spr*pot_bb - bet_bb)/(pot_bb + 2*bet_bb), 1)}. '
            f'May need to go all-in on turn/river.'
        )

    return DynamicCbetSizeResult(
        position=position,
        street=street,
        hand_category=hand_category,
        range_score=range_score,
        villain_fcbet=villain_fcbet,
        villain_vpip=villain_vpip,
        spr=spr,
        pot_bb=pot_bb,
        optimal_size_frac=size,
        optimal_bet_bb=bet_bb,
        size_category=size_cat,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def dcs_one_liner(r: DynamicCbetSizeResult) -> str:
    return (
        f'[DCS {r.hand_category}|{r.position}|{r.street}] '
        f'{r.optimal_size_frac:.0%}pot={r.optimal_bet_bb:.1f}BB ({r.size_category})'
    )
