"""
Range Protection Advisor (range_protect_advisor.py)

CORE PROBLEM: Players who always bet the same hands in the same spots
are EXPLOITABLE. A solver-aware villain will:
  - Check-raise hero's c-bets more if hero bets too frequently
  - Call down with wider hands knowing hero's range is capped (too thin)
  - Bluff raise knowing hero will fold most of their "always-check" hands

RANGE PROTECTION = Adding strong hands to your CHECKING RANGE
                  AND adding bluffs to your BETTING RANGE

When hero should protect their checking range:
  - Hero has been betting strong hands too frequently in a spot
  - Hero's checking range becomes weak/capped (villain can attack)
  - Solution: Trap some strong hands; check-raise villain's attack

When hero should protect their betting range:
  - Hero bets too few bluffs → villain can over-fold and profit
  - Solution: Add some low-SDV hands to betting range as bluffs

EXPLOITATION DETECTION:
  If hero's actual frequency > GTO frequency + THRESHOLD:
    → Hero is OVER-BETTING this hand category
    → Move some hands from BETTING to CHECKING range

  If hero's actual frequency < GTO frequency - THRESHOLD:
    → Hero is UNDER-BETTING this hand category
    → Move some hands from CHECKING to BETTING range

EV IMPACT of exploitation (approximate):
  Being exploited in c-bet spot (hero over-bets by 20%):
    Villain gains roughly 0.15-0.25 BB/100 per 20% deviation × frequency of spot

  With 60% spots being c-bet situations and 20% over-betting:
    Loss ≈ 0.18 BB/100 (significant over a long session)

PROTECTION STRATEGIES by hand class:
  Strong hands (overpair, two pair, set):
    If betting 100% → move 20-30% to checking (check-raise/trap)
    Benefit: Protects checking range; villain can't freely bluff

  Medium hands (top pair, TPTK):
    If betting 100% → move 15-20% to checking (pot control)
    Benefit: Balance + prevents villain from correctly folding marginal hands

  Weak hands / air:
    If betting 0% → add some as bluffs (GTO requires bluffing frequency)
    If betting >50% → reduce (you're burning money on low-FE spots)

Usage:
    from poker.range_protect_advisor import advise_range_protection
    from poker.range_protect_advisor import RangeProtectAdvice, range_protect_one_liner

    result = advise_range_protection(
        hero_cbet_freq=0.85,
        hero_hand_class='top_pair',
        hero_pos='IP',
        board_type='medium',
        street='flop',
        villain_cr_freq=0.15,
        villain_fold_to_cbet=0.48,
        pot_bb=15.0,
        spr=6.0,
    )
    print(result.action, result.protection_needed)
"""

from dataclasses import dataclass, field
from typing import List


# GTO reference frequencies (hero's optimal betting frequency by hand class + board)
_GTO_CBET_FREQ = {
    # (hand_cat, board_type) → (ip_freq, oop_freq)
    ('premium',     'dry'):    (0.92, 0.82),
    ('premium',     'medium'): (0.88, 0.78),
    ('premium',     'wet'):    (0.80, 0.68),
    ('overpair',    'dry'):    (0.85, 0.75),
    ('overpair',    'medium'): (0.80, 0.70),
    ('overpair',    'wet'):    (0.72, 0.60),
    ('top_pair',    'dry'):    (0.75, 0.65),
    ('top_pair',    'medium'): (0.65, 0.55),
    ('top_pair',    'wet'):    (0.55, 0.42),
    ('middle_pair', 'dry'):    (0.40, 0.28),
    ('middle_pair', 'medium'): (0.30, 0.20),
    ('middle_pair', 'wet'):    (0.22, 0.15),
    ('draw',        'dry'):    (0.55, 0.40),
    ('draw',        'medium'): (0.50, 0.38),
    ('draw',        'wet'):    (0.45, 0.35),
    ('air',         'dry'):    (0.35, 0.22),
    ('air',         'medium'): (0.28, 0.18),
    ('air',         'wet'):    (0.20, 0.12),
}

# Exploitation threshold: deviation beyond this signals exploitable pattern
_EXPLOIT_THRESHOLD = 0.15  # 15% deviation from GTO = exploitable


def _hand_cat(hand_class: str) -> str:
    return {
        'air': 'air', 'trash': 'air', 'bottom_pair': 'air', 'marginal': 'air',
        'middle_pair': 'middle_pair', 'draw': 'draw', 'speculative': 'draw',
        'top_pair': 'top_pair', 'medium': 'top_pair', 'tptk': 'top_pair',
        'overpair': 'overpair', 'two_pair': 'overpair', 'strong': 'overpair',
        'set': 'premium', 'straight': 'premium', 'flush': 'premium',
        'premium': 'premium', 'full_house': 'premium', 'nuts': 'premium',
    }.get(hand_class.lower(), 'top_pair')


def _gto_freq(hand_cat: str, board_type: str, hero_pos: str) -> float:
    key = (hand_cat, board_type)
    if key in _GTO_CBET_FREQ:
        ip_freq, oop_freq = _GTO_CBET_FREQ[key]
        return ip_freq if hero_pos == 'IP' else oop_freq
    # Fallback
    if hand_cat == 'premium': return 0.85
    if hand_cat == 'overpair': return 0.78
    if hand_cat == 'top_pair': return 0.62
    if hand_cat == 'middle_pair': return 0.28
    if hand_cat == 'draw': return 0.45
    return 0.25


def _deviation(actual: float, gto: float) -> float:
    """Deviation from GTO: positive = over-betting, negative = under-betting."""
    return round(actual - gto, 3)


def _exploitation_severity(dev: float) -> str:
    """How severely exploited is hero?"""
    abs_dev = abs(dev)
    if abs_dev >= 0.30:
        return 'severe'
    if abs_dev >= 0.20:
        return 'significant'
    if abs_dev >= _EXPLOIT_THRESHOLD:
        return 'moderate'
    return 'none'


def _villain_cr_adjustment(villain_cr_freq: float, gto_cr: float = 0.10) -> str:
    """Is villain over-exploiting hero by check-raising more?"""
    if villain_cr_freq >= gto_cr + 0.10:
        return 'over_attack'   # villain has noticed hero over-bets; attacking
    if villain_cr_freq >= gto_cr:
        return 'normal'
    return 'passive'


def _protection_adjustments(
    deviation: float,
    hand_cat: str,
    villain_cr_status: str,
    hero_pos: str,
) -> tuple:
    """
    Returns (action, pct_to_move, protection_strategy).
    pct_to_move: percentage of hands in this category to move
    """
    dev = deviation

    if dev > _EXPLOIT_THRESHOLD:
        # Over-betting: move some strong hands to checking
        if hand_cat in ('premium', 'overpair'):
            pct = min(0.40, dev * 1.2)
            strategy = (
                f'Move {pct:.0%} of {hand_cat} hands from betting to CHECKING. '
                f'Check-raise or check-call when villain bets. '
                f'This adds nutted hands to your checking range — villain cannot bluff you freely.'
            )
            return ('reduce_betting', pct, strategy)

        if hand_cat == 'top_pair':
            pct = min(0.25, dev * 1.0)
            strategy = (
                f'Move {pct:.0%} of {hand_cat} to CHECKING (pot control). '
                f'Your checking range gains more showdown value; '
                f'villain cannot over-bluff when you check.'
            )
            return ('reduce_betting', pct, strategy)

        if hand_cat in ('middle_pair', 'draw', 'air'):
            pct = min(0.60, dev * 1.5)
            strategy = (
                f'Reduce bluff frequency by {pct:.0%}. '
                f'You are bluffing too often in this spot. '
                f'Focus bluffs on hands with blockers or equity.'
            )
            return ('reduce_bluffing', pct, strategy)

    if dev < -_EXPLOIT_THRESHOLD:
        # Under-betting: add more hands to betting range
        abs_dev = abs(dev)
        if hand_cat in ('premium', 'overpair', 'top_pair'):
            pct = min(0.30, abs_dev * 1.0)
            strategy = (
                f'Add {pct:.0%} more {hand_cat} hands to BETTING. '
                f'You are giving up too much value. '
                f'Villain is getting free looks at your weak checking range.'
            )
            return ('increase_betting', pct, strategy)

        if hand_cat in ('draw', 'air'):
            pct = min(0.25, abs_dev * 0.8)
            strategy = (
                f'Add {pct:.0%} more semi-bluffs to your betting range. '
                f'You are not bluffing enough — villain can over-fold and profit.'
            )
            return ('increase_bluffing', pct, strategy)

    # No significant deviation
    if villain_cr_status == 'over_attack' and hand_cat in ('premium', 'overpair'):
        # Villain is attacking hero's checking range
        return (
            'trap_vs_attack',
            0.15,
            f'Villain is over-check-raising ({villain_cr_status}). '
            f'Keep strong hands in checking range to trap. '
            f'Check-raise villain when they attack: they will over-fire into your traps.'
        )

    return ('no_change', 0.0, 'Current frequency is GTO-optimal. No adjustment needed.')


def _ev_impact(deviation: float, pot_bb: float, hand_cat: str) -> float:
    """Approximate EV loss per hand from this exploitation (in BB)."""
    if abs(deviation) < _EXPLOIT_THRESHOLD:
        return 0.0
    # Rough estimate: each 10% over/under-bet deviates EV by 0.3-0.8x BB
    severity_mult = {'air': 0.4, 'draw': 0.5, 'middle_pair': 0.6, 'top_pair': 0.8, 'overpair': 1.0, 'premium': 0.5}.get(hand_cat, 0.6)
    ev_loss = abs(deviation) * pot_bb * 0.08 * severity_mult
    return round(ev_loss, 2)


@dataclass
class RangeProtectAdvice:
    """Advice on protecting hero's betting/checking range from exploitation."""
    hero_cbet_freq: float
    hero_hand_class: str
    hero_pos: str
    board_type: str
    street: str
    villain_cr_freq: float
    villain_fold_to_cbet: float
    pot_bb: float
    spr: float

    # Analysis
    hand_category: str
    gto_target_freq: float
    deviation: float              # actual - gto (positive=over, negative=under)
    exploitation_severity: str    # 'none', 'moderate', 'significant', 'severe'
    villain_cr_status: str        # 'passive', 'normal', 'over_attack'
    protection_needed: bool

    # Recommendation
    action: str                   # 'reduce_betting', 'reduce_bluffing', 'increase_betting', 'increase_bluffing', 'trap_vs_attack', 'no_change'
    pct_to_adjust: float          # fraction of this hand class to move
    protection_strategy: str      # specific adjustment description
    ev_loss_per_hand: float       # approximate EV loss from current exploitation

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_range_protection(
    hero_cbet_freq: float = 0.85,
    hero_hand_class: str = 'top_pair',
    hero_pos: str = 'IP',
    board_type: str = 'medium',
    street: str = 'flop',
    villain_cr_freq: float = 0.15,
    villain_fold_to_cbet: float = 0.48,
    pot_bb: float = 15.0,
    spr: float = 6.0,
) -> RangeProtectAdvice:
    """
    Detect and advise on range protection needs.

    Args:
        hero_cbet_freq:       Hero's actual betting frequency (0-1) in this spot
        hero_hand_class:      Hero's hand strength
        hero_pos:             'IP' or 'OOP'
        board_type:           'dry', 'medium', 'wet'
        street:               'flop', 'turn', 'river'
        villain_cr_freq:      Villain's observed check-raise frequency
        villain_fold_to_cbet: Villain's fold-to-cbet rate
        pot_bb:               Current pot size in BB
        spr:                  Stack-to-pot ratio

    Returns:
        RangeProtectAdvice
    """
    cat = _hand_cat(hero_hand_class)
    gto = _gto_freq(cat, board_type, hero_pos)
    dev = _deviation(hero_cbet_freq, gto)
    severity = _exploitation_severity(dev)
    cr_status = _villain_cr_adjustment(villain_cr_freq)
    protection_needed = severity != 'none' or cr_status == 'over_attack'
    action, pct, strategy = _protection_adjustments(dev, cat, cr_status, hero_pos)
    ev_loss = _ev_impact(dev, pot_bb, cat)

    direction = 'over-betting' if dev > 0 else 'under-betting'
    reasoning = (
        f'Current {hero_hand_class} c-bet freq={hero_cbet_freq:.0%} '
        f'vs GTO={gto:.0%} ({direction} by {abs(dev):.0%}). '
        f'Severity={severity}. '
        f'Villain CR freq={villain_cr_freq:.0%} [{cr_status}]. '
        f'Recommended: {action} by {pct:.0%}. '
        f'EV loss from current pattern: ~{ev_loss:.1f}BB/hand.'
    )

    # Tips
    tips = []
    if severity in ('significant', 'severe') and dev > 0:
        tips.append(
            f'OVER-BETTING ALERT ({severity}): You bet {hero_hand_class} '
            f'{hero_cbet_freq:.0%} but GTO is {gto:.0%} '
            f'(+{dev:.0%} over). '
            f'Villain KNOWS you always bet here — they can profitably call wider '
            f'or check-raise to isolate your value hands. '
            f'Move {pct:.0%} of {hero_hand_class} to checking range this session.'
        )
    if severity in ('significant', 'severe') and dev < 0:
        tips.append(
            f'UNDER-BETTING ALERT ({severity}): You bet {hero_hand_class} '
            f'only {hero_cbet_freq:.0%} but GTO is {gto:.0%} '
            f'({abs(dev):.0%} under). '
            f'Villain can over-fold (they know you rarely bet) and bluff you on future streets. '
            f'Add more {hero_hand_class} to your betting range.'
        )
    if cr_status == 'over_attack':
        tips.append(
            f'VILLAIN ATTACKING: Villain is check-raising {villain_cr_freq:.0%} '
            f'(above GTO baseline of ~10%). '
            f'They have noticed your over-betting and are exploiting it. '
            f'RESPONSE: Keep strong hands in checking range (trap). '
            f'When villain CR, check-raise over their raise or call down confidently.'
        )
    if villain_fold_to_cbet < 0.40:
        tips.append(
            f'LOW FOLD-TO-CBET ({villain_fold_to_cbet:.0%}): Villain is calling your c-bets wide. '
            f'Reduce bluff frequency — they are making your bluffs -EV. '
            f'Increase value bet frequency and sizing. '
            f'Consider checking back draws (implied odds better than semi-bluff EV).'
        )
    if villain_fold_to_cbet > 0.65:
        tips.append(
            f'HIGH FOLD-TO-CBET ({villain_fold_to_cbet:.0%}): Villain is folding too much. '
            f'You can profitably c-bet wider than GTO here. '
            f'Add more bluffs to your betting range against this player.'
        )
    if cat == 'premium' and action == 'reduce_betting':
        tips.append(
            f'TRAPPING GUIDE: Move {pct:.0%} of sets/straights/flushes to CHECK. '
            f'When you check, villain will often bluff into you. '
            f'Plan: check-raise their bet (not just call) to extract max value. '
            f'Checking range with nuts = unexpected and extremely high EV.'
        )
    if not tips:
        tips.append(
            f'Range is GTO-balanced ({hero_hand_class}: {hero_cbet_freq:.0%} vs GTO {gto:.0%}). '
            f'Maintain current frequency. No protection adjustment needed. '
            f'Monitor if villain starts adjusting (watch for increased CR frequency).'
        )

    return RangeProtectAdvice(
        hero_cbet_freq=round(hero_cbet_freq, 3),
        hero_hand_class=hero_hand_class,
        hero_pos=hero_pos,
        board_type=board_type,
        street=street,
        villain_cr_freq=round(villain_cr_freq, 3),
        villain_fold_to_cbet=round(villain_fold_to_cbet, 3),
        pot_bb=round(pot_bb, 1),
        spr=round(spr, 2),
        hand_category=cat,
        gto_target_freq=round(gto, 3),
        deviation=dev,
        exploitation_severity=severity,
        villain_cr_status=cr_status,
        protection_needed=protection_needed,
        action=action,
        pct_to_adjust=round(pct, 2),
        protection_strategy=strategy,
        ev_loss_per_hand=ev_loss,
        reasoning=reasoning,
        tips=tips,
    )


def range_protect_one_liner(result: RangeProtectAdvice) -> str:
    return (
        f'[RP {result.hero_hand_class}@{result.street}|{result.hero_pos}] '
        f'{result.action.upper()} | '
        f'actual={result.hero_cbet_freq:.0%} gto={result.gto_target_freq:.0%} '
        f'dev={result.deviation:+.0%} | '
        f'sev={result.exploitation_severity} ev_loss={result.ev_loss_per_hand:.1f}BB'
    )
