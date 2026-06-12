"""
Value-to-Bluff Ratio Advisor (value_bluff_ratio_advisor.py)

Maintains the correct value:bluff ratio per betting spot to prevent
exploitation. A balanced poker strategy requires specific value:bluff
ratios that make villain indifferent to calling or folding.

KEY THEORY:
  For any bet size, the correct bluff ratio (alpha) satisfies:
    alpha = bet / (pot + bet)    [villain's break-even fold probability]
  This means: villain must fold at least alpha% for bluff to break even.
  For GTO, hero bluffs exactly enough that villain is indifferent.

  Example at 50% pot bet:
    alpha = 0.50 / (1 + 0.50) = 0.33
    For every 2 value hands, hero has 1 bluff (2:1 ratio)

VALUE:BLUFF RATIOS BY STREET AND SIZE:
  Flop (more equity; include semi-bluffs):
    33% pot: ratio 3:2 (bluffs = 40% of range)
    50% pot: ratio 2:1 (bluffs = 33%)
    75% pot: ratio 5:2 (bluffs = 29%)
  Turn (less equity realization):
    33% pot: 3:2
    50% pot: 2:1
    75% pot: 3:1
  River (no future streets; pure bluffs):
    33% pot: 2:1
    50% pot: 2:1
    75% pot: 3:1
    pot:     4:1

HERO'S ACTUAL RATIO ASSESSMENT:
  Over-bluffing: more bluffs than GTO → villain profits by calling more
  Under-bluffing: fewer bluffs than GTO → villain profits by folding more
  Balanced: near GTO → villain has no exploitable response

DISTINCT FROM:
  multistreet_bluff_calibrator.py: Calibrates bluff FREQUENCY per street
  river_range_builder.py:         Builds range composition for river
  THIS MODULE:                    Advises on VALUE:BLUFF ratio specifically;
                                  given hero's hand breakdown, calculates
                                  if ratio is balanced and how to fix it

Usage:
    from poker.value_bluff_ratio_advisor import advise_vb_ratio, VBRatioAdvice, vbr_one_liner

    result = advise_vb_ratio(
        street='river',
        bet_size_pct=0.75,
        hero_value_combos=12,
        hero_bluff_combos=6,
        pot_bb=30.0,
        board_texture='dry',
        villain_wtsd=0.30,
    )
    print(vbr_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


def _alpha(bet_size_pct: float) -> float:
    """Villain's break-even fold probability = GTO bluff frequency."""
    return round(bet_size_pct / (1 + bet_size_pct), 3)


def _gto_bluff_pct(bet_size_pct: float, street: str) -> float:
    """
    GTO bluff percentage of the total betting range.
    River: pure alpha.
    Flop/Turn: include semi-bluffs (more bluffs allowed).
    """
    alpha = _alpha(bet_size_pct)
    if street == 'river':
        return round(alpha, 3)
    elif street == 'turn':
        return round(min(0.50, alpha * 1.15), 3)   # semi-bluffs add ~15%
    else:  # flop
        return round(min(0.55, alpha * 1.30), 3)   # equity bonus for semi-bluffs


def _gto_value_pct(bluff_pct: float) -> float:
    return round(1.0 - bluff_pct, 3)


def _ratio_status(hero_bluff_pct: float, gto_bluff_pct: float) -> str:
    dev = hero_bluff_pct - gto_bluff_pct
    abs_dev = abs(dev)
    if abs_dev <= 0.05:
        return 'balanced'
    elif dev > 0.05:
        return 'over_bluffing'
    else:
        return 'under_bluffing'


def _ev_loss_from_imbalance(
    hero_bluff_pct: float,
    gto_bluff_pct: float,
    pot_bb: float,
    bet_size_pct: float,
    villain_wtsd: float,
) -> float:
    """
    Rough EV loss per 100 combos from having wrong bluff ratio.
    When over-bluffing: villain calls more → lose bet with bluffs.
    When under-bluffing: villain folds more → miss value with value hands.
    """
    dev = hero_bluff_pct - gto_bluff_pct
    bet_bb = bet_size_pct * pot_bb
    if dev > 0:
        # Over-bluffing: villain exploits by calling more
        extra_bluffs = dev
        villain_call_increase = min(0.20, dev)   # villain adjusts call rate
        ev_loss = extra_bluffs * villain_call_increase * bet_bb * 100
    else:
        # Under-bluffing: villain exploits by folding more
        missed_bluffs = abs(dev)
        villain_fold_increase = min(0.20, missed_bluffs)
        ev_loss = missed_bluffs * villain_fold_increase * pot_bb * 0.60 * 100
    return round(ev_loss, 1)


def _fix_bluff_count(
    total_value: int,
    gto_bluff_pct: float,
) -> int:
    """Target bluff count to achieve GTO ratio given value combo count."""
    if gto_bluff_pct >= 0.99:
        return total_value * 10
    gto_value_pct = 1 - gto_bluff_pct
    target_bluffs = round(total_value * gto_bluff_pct / gto_value_pct)
    return max(0, target_bluffs)


@dataclass
class VBRatioAdvice:
    # Inputs
    street: str
    bet_size_pct: float
    hero_value_combos: int
    hero_bluff_combos: int
    pot_bb: float
    board_texture: str
    villain_wtsd: float

    # Analysis
    total_combos: int
    hero_bluff_pct: float         # actual bluff % in hero's betting range
    gto_bluff_pct: float          # target GTO bluff %
    hero_value_pct: float
    gto_value_pct: float

    alpha: float                  # villain's break-even fold %
    ratio_status: str             # 'balanced' / 'over_bluffing' / 'under_bluffing'
    deviation: float              # actual - GTO bluff %
    ev_loss_per_100: float        # EV loss per 100 combos from imbalance

    # Fix
    target_bluff_combos: int      # correct number of bluffs
    bluffs_to_add_or_remove: int  # how many to add (+) or remove (-)

    verdict: str
    tips: List[str] = field(default_factory=list)


def advise_vb_ratio(
    street: str = 'river',
    bet_size_pct: float = 0.75,
    hero_value_combos: int = 12,
    hero_bluff_combos: int = 6,
    pot_bb: float = 30.0,
    board_texture: str = 'dry',
    villain_wtsd: float = 0.30,
) -> VBRatioAdvice:
    """
    Advise on value:bluff ratio balance for a given betting spot.

    Args:
        street:             'flop' / 'turn' / 'river'
        bet_size_pct:       Bet size as fraction of pot (0.33, 0.50, 0.75, 1.00)
        hero_value_combos:  Estimated number of value combo hands hero bets
        hero_bluff_combos:  Estimated number of bluff combo hands hero bets
        pot_bb:             Current pot in BBs
        board_texture:      'dry' / 'semi_wet' / 'wet' / 'paired' / 'monotone'
        villain_wtsd:       Villain's WTSD stat

    Returns:
        VBRatioAdvice
    """
    total = hero_value_combos + hero_bluff_combos
    hero_bluff_pct = round(hero_bluff_combos / max(total, 1), 3)
    hero_value_pct = round(1 - hero_bluff_pct, 3)

    gto_bluff = _gto_bluff_pct(bet_size_pct, street)
    gto_value = _gto_value_pct(gto_bluff)
    alpha = _alpha(bet_size_pct)

    status = _ratio_status(hero_bluff_pct, gto_bluff)
    deviation = round(hero_bluff_pct - gto_bluff, 3)
    ev_loss = _ev_loss_from_imbalance(hero_bluff_pct, gto_bluff, pot_bb, bet_size_pct, villain_wtsd)
    target_bluffs = _fix_bluff_count(hero_value_combos, gto_bluff)
    adj = target_bluffs - hero_bluff_combos

    verdict = (
        f'[VBR {street.upper()}|{bet_size_pct:.0%}pot|{status}] '
        f'bluff={hero_bluff_pct:.0%} (GTO={gto_bluff:.0%}) dev={deviation:+.0%} | '
        f'ev_loss={ev_loss:.1f}BB/100 | fix={adj:+d} bluffs'
    )

    tips = []
    ratio_str = f'{hero_value_combos}:{hero_bluff_combos}'
    gto_ratio = f'{hero_value_combos}:{target_bluffs}'
    tips.append(
        f'CURRENT RATIO: {ratio_str} (bluff={hero_bluff_pct:.0%}). '
        f'GTO for {bet_size_pct:.0%} pot bet on {street}: {gto_ratio} (bluff={gto_bluff:.0%}). '
        f'Deviation={deviation:+.0%}. Status={status}.'
    )

    if status == 'over_bluffing':
        tips.append(
            f'OVER-BLUFFING by {deviation:.0%}: Remove {abs(adj)} bluff combos from range. '
            f'Villain profits by calling every time. '
            f'Keep only strongest bluffs (best blockers, highest equity). '
            f'Target ratio: {gto_ratio}.'
        )
    elif status == 'under_bluffing':
        tips.append(
            f'UNDER-BLUFFING by {abs(deviation):.0%}: Add {abs(adj)} bluff combos. '
            f'Villain profits by folding every time -- you miss EV. '
            f'Add bluffs from: missed draws, backdoor misses, hands with blockers. '
            f'Target ratio: {gto_ratio}.'
        )
    else:
        tips.append(
            f'BALANCED RATIO: Your {ratio_str} ratio is near GTO ({gto_ratio}). '
            f'Villain cannot profitably deviate. EV loss is minimal.'
        )

    tips.append(
        f'ALPHA REMINDER: At {bet_size_pct:.0%} pot bet, villain needs to fold {alpha:.0%} '
        f'for your bluffs to break even. GTO bluff% = {gto_bluff:.0%}. '
        f'If villain folds less → remove bluffs. If villain folds more → add bluffs.'
    )

    if villain_wtsd >= 0.38:
        tips.append(
            f'CALLING STATION (WTSD={villain_wtsd:.0%}): This villain calls too often. '
            f'REDUCE bluffs well below GTO. Exploitative adjustment: '
            f'target {max(0, target_bluffs - 3)} bluffs (not GTO {target_bluffs}).'
        )
    elif villain_wtsd <= 0.22:
        tips.append(
            f'FOLDER (WTSD={villain_wtsd:.0%}): This villain folds too often. '
            f'INCREASE bluffs above GTO. Exploitative adjustment: '
            f'add {adj + 2} bluffs (more than GTO).'
        )

    if board_texture == 'wet' and street in ('flop', 'turn'):
        tips.append(
            f'WET BOARD: More semi-bluffs are available (flush draws, straight draws). '
            f'GTO allows more bluffs on wet boards ({gto_bluff:.0%} vs dry board ~{gto_bluff*0.85:.0%}). '
            f'Use draws as bluffs to reach target {gto_ratio} ratio.'
        )

    return VBRatioAdvice(
        street=street,
        bet_size_pct=bet_size_pct,
        hero_value_combos=hero_value_combos,
        hero_bluff_combos=hero_bluff_combos,
        pot_bb=pot_bb,
        board_texture=board_texture,
        villain_wtsd=villain_wtsd,
        total_combos=total,
        hero_bluff_pct=hero_bluff_pct,
        gto_bluff_pct=gto_bluff,
        hero_value_pct=hero_value_pct,
        gto_value_pct=gto_value,
        alpha=alpha,
        ratio_status=status,
        deviation=deviation,
        ev_loss_per_100=ev_loss,
        target_bluff_combos=target_bluffs,
        bluffs_to_add_or_remove=adj,
        verdict=verdict,
        tips=tips,
    )


def vbr_one_liner(r: VBRatioAdvice) -> str:
    return (
        f'[VBR {r.street.upper()}|{r.bet_size_pct:.0%}pot|{r.ratio_status}] '
        f'{r.hero_value_combos}:{r.hero_bluff_combos} (GTO={r.gto_bluff_pct:.0%}) '
        f'dev={r.deviation:+.0%} fix={r.bluffs_to_add_or_remove:+d}'
    )
