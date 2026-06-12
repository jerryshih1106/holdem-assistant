"""
Value Betting Threshold Advisor (value_threshold.py)

The most common leak at microstakes/small stakes: betting too thin vs calling
stations (letting them fold) OR not betting thin enough vs fish (missing value).

This module computes the minimum hand strength required to value bet profitably
against a specific villain profile, then gives the exact sizing recommendation.

Key insight:
  EV(value_bet) = fold_freq * pot + call_freq * (equity * (pot + bet) - bet)
  Value bet is profitable when EV(bet) > EV(check) = equity * pot

  breakeven_equity = bet / (pot + bet)  when villain folds frequently
  breakeven_equity = 0.50              when villain calls everything

Villain type thresholds:
  Fish (VPIP>40, AF<1.5):
    - Calls too wide → value bet very thin (top pair any kicker, 2nd pair TPWK equiv)
    - Never bluff → wasted money
    - Optimal size: 55-75% pot (not too big — fish might fold)

  Calling station (VPIP>35, AF<1.0, WtSD>45%):
    - Calls rivers very wide → thin value on all three streets
    - size slightly smaller to maximize call-range width

  Nit (VPIP<15, AF>1.5, Fold3B>75%):
    - Folds too much → bluff more, value bet only strong hands
    - When they call/raise: give them credit

  TAg-reg (VPIP 20-28, PFR 18-25):
    - Standard balanced play
    - Bet 2/3 pot with top pair+

  LAG (VPIP>28, PFR>25, AF>2.5):
    - Don't bluff → they never fold
    - Do not call them down light without strong hand

Usage:
    from poker.value_threshold import analyze_value_threshold, ValueThresholdResult
    result = analyze_value_threshold(
        hero_equity=0.62,
        hand_class='top_pair',
        villain_vpip=0.42,
        villain_pfr=0.08,
        villain_af=0.9,
        villain_wtsd=0.48,
        pot_bb=15.0,
        bet_bb=8.0,
        street='river',
    )
    print(result.action, result.value_bet_recommended)
"""

from dataclasses import dataclass, field
from typing import List, Optional


_HAND_STRENGTH_RANK = {
    'quads': 10, 'full_house': 9, 'flush': 8, 'straight': 7,
    'set': 6, 'two_pair': 5, 'top_pair': 4, 'second_pair': 3,
    'bottom_pair': 2, 'high_card': 1, 'air': 0,
}


def _villain_type(vpip: float, pfr: float, af: float, wtsd: float) -> str:
    """Classify villain into strategic archetype."""
    if vpip >= 0.40 and pfr <= 0.12:
        if wtsd >= 0.45 or af <= 1.0:
            return 'calling_station'
        return 'fish'
    if vpip <= 0.16 and pfr <= 0.13:
        return 'nit'
    if vpip >= 0.28 and pfr >= 0.24 and af >= 2.5:
        return 'lag'
    if vpip >= 0.28 and pfr >= 0.22:
        return 'loose_aggro'
    if vpip <= 0.24 and pfr >= 0.18 and af >= 2.0:
        return 'tag_reg'
    if vpip <= 0.30 and pfr >= 0.15:
        return 'reg'
    return 'unknown'


def _value_threshold_for_type(villain_type: str, street: str) -> tuple:
    """
    Return (min_hand_rank, min_equity, description) for profitable value betting.
    """
    if villain_type == 'calling_station':
        return 2, 0.48, 'Call station: value bet any pair+ (2nd pair qualifies on flop/turn)'
    elif villain_type == 'fish':
        return 3, 0.50, 'Fish: value bet bottom pair+ on flop, 2nd pair+ on turn/river'
    elif villain_type == 'nit':
        if street == 'river':
            return 5, 0.72, 'Nit: river value needs two-pair+ (they fold too much)'
        return 4, 0.60, 'Nit: flop/turn top pair+ needed (they fold weak hands)'
    elif villain_type in ('lag', 'loose_aggro'):
        return 4, 0.55, 'LAG: top pair+ value bet; they will raise or call with wide range'
    elif villain_type == 'tag_reg':
        if street == 'river':
            return 5, 0.65, 'Reg: river value needs solid two-pair or better'
        return 4, 0.55, 'Reg: top pair+ on flop/turn; use polarized sizing'
    elif villain_type == 'reg':
        return 4, 0.55, 'Reg: standard value betting thresholds'
    else:
        return 4, 0.55, 'Unknown villain type: use default thresholds'


def _optimal_size(villain_type: str, hero_equity: float, street: str, pot_bb: float) -> float:
    """
    Compute optimal bet size in BBs for value betting.
    Larger vs fish/stations; smaller vs tight players.
    """
    base_pct = {
        'calling_station': 0.60,
        'fish':            0.65,
        'nit':             0.50,
        'lag':             0.55,
        'loose_aggro':     0.55,
        'tag_reg':         0.60,
        'reg':             0.60,
        'unknown':         0.55,
    }.get(villain_type, 0.55)

    # River: bet bigger (getting full value on final street)
    if street == 'river':
        base_pct += 0.10
    elif street == 'turn':
        base_pct += 0.05

    # High equity = can size up; low equity = size down to keep villain in
    equity_adj = (hero_equity - 0.55) * 0.20
    base_pct = max(0.30, min(1.00, base_pct + equity_adj))

    return round(pot_bb * base_pct, 1)


def _ev_bet(
    hero_equity: float,
    pot_bb: float,
    bet_bb: float,
    villain_fold_freq: float,
) -> float:
    total_pot = pot_bb + bet_bb * 2   # hero bets, villain calls
    ev_fold = pot_bb
    ev_call = hero_equity * total_pot - bet_bb
    return villain_fold_freq * ev_fold + (1 - villain_fold_freq) * ev_call


def _ev_check(hero_equity: float, pot_bb: float, in_position: bool) -> float:
    realise = 0.87 if in_position else 0.73
    return hero_equity * pot_bb * realise


def _fold_freq_estimate(villain_type: str, street: str) -> float:
    """Estimate villain's fold frequency to a value bet."""
    base = {
        'calling_station': 0.10, 'fish': 0.20, 'nit': 0.55,
        'lag': 0.30, 'loose_aggro': 0.30, 'tag_reg': 0.42,
        'reg': 0.42, 'unknown': 0.40,
    }.get(villain_type, 0.40)
    if street == 'river':
        base = max(0.05, base - 0.05)  # less folding on river (pot committed)
    return base


@dataclass
class ValueThresholdResult:
    """Villian-type adjusted value betting analysis."""
    # Classification
    villain_type: str
    villain_type_label: str

    # Hero hand
    hand_class: str
    hand_rank: int              # 0=air, 10=quads
    hero_equity: float

    # Thresholds
    min_hand_rank: int          # minimum rank for profitable value bet
    min_equity_threshold: float # minimum equity needed
    threshold_description: str

    # Current decision
    value_bet_recommended: bool
    reason: str

    # Sizing
    optimal_bet_pct: float
    optimal_bet_bb: float
    fold_equity_estimate: float

    # EV
    ev_bet: float
    ev_check: float
    ev_advantage: float         # ev_bet - ev_check

    # Exploitation
    exploitation_tips: List[str] = field(default_factory=list)
    one_liner: str = ''


def analyze_value_threshold(
    hero_equity: float,
    hand_class: str,
    villain_vpip: float,
    villain_pfr: float,
    villain_af: float = 1.5,
    villain_wtsd: float = 0.35,
    pot_bb: float = 10.0,
    bet_bb: Optional[float] = None,
    street: str = 'river',
    in_position: bool = True,
) -> ValueThresholdResult:
    """
    Determine optimal value betting strategy vs a specific villain profile.

    Args:
        hero_equity:    Hero's equity vs villain's calling range
        hand_class:     Hero's hand class ('top_pair', 'two_pair', 'set', etc.)
        villain_vpip:   Villain's VPIP (0-1)
        villain_pfr:    Villain's PFR (0-1)
        villain_af:     Villain's aggression factor
        villain_wtsd:   Villain's went-to-showdown frequency (0-1)
        pot_bb:         Current pot in BBs
        bet_bb:         Proposed bet size (None = compute optimal)
        street:         'flop', 'turn', 'river'
        in_position:    True if hero acts last

    Returns:
        ValueThresholdResult
    """
    vtype = _villain_type(villain_vpip, villain_pfr, villain_af, villain_wtsd)

    vtype_labels = {
        'calling_station': 'Calling Station', 'fish': 'Fish',
        'nit': 'Nit', 'lag': 'LAG', 'loose_aggro': 'Loose-Aggro',
        'tag_reg': 'TAG-Reg', 'reg': 'Reg', 'unknown': 'Unknown',
    }
    label = vtype_labels.get(vtype, 'Unknown')

    min_rank, min_equity, thresh_desc = _value_threshold_for_type(vtype, street)
    hand_rank = _HAND_STRENGTH_RANK.get(hand_class.lower(), 4)

    # Optimal sizing
    opt_bet = _optimal_size(vtype, hero_equity, street, pot_bb)
    if bet_bb is None:
        bet_bb = opt_bet

    fold_freq = _fold_freq_estimate(vtype, street)

    ev_bet = _ev_bet(hero_equity, pot_bb, bet_bb, fold_freq)
    ev_chk = _ev_check(hero_equity, pot_bb, in_position)
    ev_adv = ev_bet - ev_chk

    # Value bet is recommended when:
    # 1. Hand is above threshold rank, AND
    # 2. Equity exceeds minimum threshold, AND
    # 3. EV(bet) > EV(check)
    meets_rank = hand_rank >= min_rank
    meets_equity = hero_equity >= min_equity
    ev_positive = ev_bet > ev_chk

    value_bet_ok = meets_rank and meets_equity and ev_positive

    if value_bet_ok:
        reason = (
            f'{hand_class} vs {label}: all criteria met. '
            f'EV(bet)={ev_bet:+.1f} > EV(check)={ev_chk:+.1f}.'
        )
    elif not meets_rank:
        reason = (
            f'{hand_class} (rank {hand_rank}) is below minimum rank {min_rank} vs {label}. '
            f'Check or use as bluff-catcher.'
        )
    elif not meets_equity:
        reason = (
            f'Equity {hero_equity:.0%} below {min_equity:.0%} threshold vs {label}. '
            f'Don\'t value bet.'
        )
    else:
        reason = (
            f'EV(bet)={ev_bet:+.1f} <= EV(check)={ev_chk:+.1f}. '
            f'Checking is more profitable.'
        )

    # Exploitation tips
    tips = []
    if vtype == 'calling_station':
        tips.append(
            'Calling station: never bluff. Value bet all pairs. '
            f'Use {opt_bet/pot_bb:.0%} pot sizing — do NOT overbet (they might fold).'
        )
        tips.append('3-street value bet: bet flop, turn, river with any top pair or better.')
    elif vtype == 'fish':
        tips.append(
            f'Fish (VPIP {villain_vpip:.0%}): value bet wide. '
            f'Size {opt_bet/pot_bb:.0%} pot to maximize calls without folding them out.'
        )
        tips.append(
            'Do NOT bluff fish — they call too wide. '
            'Wait for hands and extract maximum value.'
        )
    elif vtype == 'nit':
        tips.append(
            f'Nit (VPIP {villain_vpip:.0%}): fold often to their bets (they have it). '
            f'Steal more preflop. Value bet tighter — only strong made hands.'
        )
        tips.append('When nit calls your value bet, reassess on later streets.')
    elif vtype in ('lag', 'loose_aggro'):
        tips.append(
            f'LAG (VPIP {villain_vpip:.0%} / PFR {villain_pfr:.0%}): '
            f'don\'t fold easily. Call down wider vs LAG bluffs. '
            f'Value bet strong hands; they\'ll pay off or turn their bluffs into calls.'
        )
    elif vtype in ('tag_reg', 'reg'):
        tips.append(
            f'Reg: balanced play. Value bet {opt_bet/pot_bb:.0%} pot with '
            f'top pair+ on {street}. Mix check-raises with strong hands for range balance.'
        )

    if not tips:
        tips.append(f'vs {label}: use {opt_bet:.1f}BB ({opt_bet/pot_bb:.0%} pot) when value betting.')

    opt_pct = round(opt_bet / pot_bb, 2)
    one_liner = (
        f'{label} | min={_HAND_STRENGTH_RANK.get(hand_class, "?")} '
        f'vbet={value_bet_ok} | '
        f'size={opt_bet:.1f}BB({opt_pct:.0%}) | '
        f'EV+{ev_adv:+.1f}'
    )

    return ValueThresholdResult(
        villain_type=vtype,
        villain_type_label=label,
        hand_class=hand_class,
        hand_rank=hand_rank,
        hero_equity=round(hero_equity, 2),
        min_hand_rank=min_rank,
        min_equity_threshold=round(min_equity, 2),
        threshold_description=thresh_desc,
        value_bet_recommended=value_bet_ok,
        reason=reason,
        optimal_bet_pct=opt_pct,
        optimal_bet_bb=opt_bet,
        fold_equity_estimate=round(fold_freq, 2),
        ev_bet=round(ev_bet, 2),
        ev_check=round(ev_chk, 2),
        ev_advantage=round(ev_adv, 2),
        exploitation_tips=tips,
        one_liner=one_liner,
    )


def value_threshold_one_liner(result: ValueThresholdResult) -> str:
    """Single-line overlay summary."""
    action = 'BET' if result.value_bet_recommended else 'CHECK'
    return (
        f'vs {result.villain_type_label}: {action} {result.optimal_bet_bb:.1f}BB '
        f'({result.optimal_bet_pct:.0%}p) | EV+{result.ev_advantage:+.1f}'
    )
