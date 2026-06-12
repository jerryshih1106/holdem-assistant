"""
3-Bet Pot Caller Strategy (caller_3bet_pot.py)

When you CALL a 3-bet (instead of 4-betting), the postflop dynamics shift
fundamentally from a single-raised pot:

  1. SPR is much lower (~2-5), so commitment thresholds are much lower
  2. Your range is CAPPED — your nutted hands (AA/KK usually) would have 4-bet
  3. Villain's c-bet range is WIDE and polarized vs your capped range
  4. Position matters more: IP caller can float aggressively; OOP caller is very
     constrained and should often check-fold marginal hands

Key adjustments vs normal pots:
  IP caller:
    - Float c-bets more with position advantage (35-45% of range)
    - Raise draws and strong pairs (not just nuts — range is capped anyway)
    - Check-raise strong holdings more (villain can't assume you have nuts)
  OOP caller (e.g., BB calling CO 3-bet):
    - Fold much more to c-bets (60-70%)
    - Lead donk/probe less (villain's range crushes most boards)
    - Check-raise only premium draws + top two pair+

Usage:
    from poker.caller_3bet_pot import analyze_caller_3bet, CallerAdvice
    result = analyze_caller_3bet(
        hero_equity=0.55,
        hero_hand_class='top_pair',
        in_position=True,
        villain_cbet_freq=0.70,
        villain_cbet_size_pct=0.50,
        pot_bb=18.0,
        eff_stack_bb=82.0,
        board_type='semi_wet',
        street='flop',
    )
    print(result.action, result.reasoning)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Hand rank in 3-bet pot context (capped range means we're rarely nuts)
_HAND_RANK = {
    'air': 0,
    'backdoor': 1,
    'draw': 2,
    'bottom_pair': 3,
    'middle_pair': 4,
    'top_pair_weak': 5,
    'top_pair': 6,
    'top_pair_strong': 7,
    'two_pair': 8,
    'set': 9,
    'straight': 10,
    'flush': 11,
    'full_house': 12,
}

_HAND_CLASS_MAP = {
    # normalize common inputs
    'air': 'air',
    'nothing': 'air',
    'draw': 'draw',
    'flush_draw': 'draw',
    'straight_draw': 'draw',
    'oesd': 'draw',
    'gutshot': 'draw',
    'bottom_pair': 'bottom_pair',
    'pair': 'top_pair_weak',
    'middle_pair': 'middle_pair',
    'second_pair': 'middle_pair',
    'top_pair_weak': 'top_pair_weak',
    'top_pair': 'top_pair',
    'tptk': 'top_pair_strong',
    'top_pair_strong': 'top_pair_strong',
    'two_pair': 'two_pair',
    'set': 'set',
    'straight': 'straight',
    'flush': 'flush',
    'full_house': 'full_house',
    'quads': 'full_house',
}


def _normalize_hand(hand_class: str) -> str:
    return _HAND_CLASS_MAP.get(hand_class.lower(), 'top_pair')


def _spr(pot_bb: float, eff_stack_bb: float) -> float:
    return eff_stack_bb / pot_bb if pot_bb > 0 else 99.0


def _cbet_alpha(cbet_size_pct: float) -> float:
    """Minimum equity needed to continue vs c-bet."""
    c = cbet_size_pct * 1.0  # relative to pot = 1.0
    return c / (1 + c)


def _ip_float_freq(villain_cbet_freq: float, board_type: str, spr: float) -> float:
    """Optimal IP float frequency vs c-bet."""
    base = 0.40
    # Villain c-bets too much → float more
    if villain_cbet_freq > 0.70:
        base += 0.08
    elif villain_cbet_freq < 0.45:
        base -= 0.08
    # Wet boards: more draws to float with
    board_adj = {'wet': 0.05, 'semi_wet': 0.02, 'dry': -0.05,
                 'monotone': -0.03, 'paired': -0.02}.get(board_type, 0.0)
    # Low SPR: less room to maneuver
    spr_adj = 0.0 if spr > 3 else -0.08
    return max(0.10, min(0.65, base + board_adj + spr_adj))


def _oop_continue_freq(villain_cbet_freq: float, board_type: float, spr: float) -> float:
    """OOP caller continue frequency vs c-bet (how much of range continues)."""
    base = 0.35
    if villain_cbet_freq > 0.70:
        base -= 0.05  # exploitatively bet more often to fold out weak hands
    board_adj = {'wet': 0.05, 'semi_wet': 0.02, 'dry': -0.08,
                 'monotone': -0.05, 'paired': -0.03}.get(board_type, 0.0)
    spr_adj = 0.05 if spr < 3 else 0.0  # lower SPR → wider range to continue
    return max(0.15, min(0.60, base + board_adj + spr_adj))


def _checkraise_freq(hand_rank: int, in_position: bool, board_type: str) -> float:
    """How often to check-raise this hand class in 3-bet pot."""
    if in_position:
        # IP: prefer calling and using position advantage
        if hand_rank >= 9:  # set+
            return 0.50
        elif hand_rank >= 8:  # two pair
            return 0.30
        elif hand_rank >= 6:  # top pair
            return 0.15
        elif hand_rank == 2:  # draw
            base = 0.35 if board_type == 'wet' else 0.20
            return base
        return 0.0
    else:
        # OOP: check-raise or fold (no position to float)
        if hand_rank >= 9:  # set+
            return 0.80
        elif hand_rank >= 8:  # two pair
            return 0.55
        elif hand_rank >= 7:  # tptk
            return 0.35
        elif hand_rank == 2:  # draw
            return 0.45 if board_type in ('wet', 'semi_wet') else 0.25
        return 0.0


def _ev_call_cbet(hero_equity: float, pot_bb: float, cbet_bb: float) -> float:
    total_pot = pot_bb + 2 * cbet_bb
    return hero_equity * total_pot - cbet_bb


def _ev_fold(pot_bb: float) -> float:
    return 0.0  # gives up pot


def _ev_raise(hero_equity: float, pot_bb: float, cbet_bb: float,
              raise_bb: float, villain_fold_to_raise: float) -> float:
    fold_ev = pot_bb + cbet_bb  # win what's in pot
    call_pot = pot_bb + cbet_bb + raise_bb + raise_bb
    call_ev = hero_equity * call_pot - raise_bb
    return villain_fold_to_raise * fold_ev + (1 - villain_fold_to_raise) * call_ev


@dataclass
class CallerAdvice:
    """Strategy advice for caller in 3-bet pot."""
    # Inputs
    hero_equity: float
    hero_hand_class: str
    in_position: bool
    pot_bb: float
    eff_stack_bb: float
    spr: float

    # C-bet context
    villain_cbet_freq: float
    cbet_alpha: float          # min equity to continue vs c-bet
    ip_float_freq: float       # caller's IP float range %
    oop_continue_freq: float   # OOP continue range %

    # Action
    action: str                # 'call', 'raise', 'fold', 'check', 'lead'
    action_label: str
    check_raise_freq: float    # how often to check-raise this hand here

    # EV
    ev_call: float
    ev_fold: float
    ev_raise: Optional[float]

    # Range context
    range_is_capped: bool      # caller's range is capped (no nuts)
    should_protect_range: bool # check-raise some hands to balance range
    hero_hand_rank: int        # numeric hand rank

    # Guidance
    reasoning: str
    key_adjustments: List[str] = field(default_factory=list)
    tips: List[str] = field(default_factory=list)


def analyze_caller_3bet(
    hero_equity: float,
    hero_hand_class: str = 'top_pair',
    in_position: bool = True,
    villain_cbet_freq: float = 0.65,
    villain_cbet_size_pct: float = 0.50,
    villain_fold_to_raise: float = 0.45,
    pot_bb: float = 18.0,
    eff_stack_bb: float = 82.0,
    board_type: str = 'semi_wet',
    street: str = 'flop',
    n_opponents: int = 1,
) -> CallerAdvice:
    """
    Strategy for hero as the caller in a 3-bet pot.

    Args:
        hero_equity:          Hero's equity vs villain's c-bet range
        hero_hand_class:      Hand classification (top_pair, draw, set, etc.)
        in_position:          Hero acts after villain postflop
        villain_cbet_freq:    How often villain c-bets in 3-bet pots
        villain_cbet_size_pct: Villain's c-bet size as fraction of pot
        villain_fold_to_raise: Villain folds to hero's raise in 3-bet pot
        pot_bb:               Current pot size in BB
        eff_stack_bb:         Effective stack remaining in BB
        board_type:           'dry', 'wet', 'semi_wet', 'monotone', 'paired'
        street:               'flop', 'turn', 'river'
        n_opponents:          Number of opponents (1 = heads-up)

    Returns:
        CallerAdvice
    """
    hand_cls = _normalize_hand(hero_hand_class)
    hand_rank = _HAND_RANK.get(hand_cls, 6)

    spr = _spr(pot_bb, eff_stack_bb)
    alpha = _cbet_alpha(villain_cbet_size_pct)
    cbet_bb = pot_bb * villain_cbet_size_pct
    raise_bb = cbet_bb * 2.8  # standard 2.8x raise in 3-bet pot

    ip_float = _ip_float_freq(villain_cbet_freq, board_type, spr)
    oop_cont = _oop_continue_freq(villain_cbet_freq, board_type, spr)
    cr_freq = _checkraise_freq(hand_rank, in_position, board_type)

    ev_call = _ev_call_cbet(hero_equity, pot_bb, cbet_bb)
    ev_fold = _ev_fold(pot_bb)
    ev_raise_val = _ev_raise(hero_equity, pot_bb, cbet_bb, raise_bb, villain_fold_to_raise)

    # Action decision
    if hand_rank >= 9:  # set or better
        if spr <= 2.5 or not in_position:
            action = 'raise'
            action_label = 'check-raise (set or better — build pot)'
        else:
            action = 'call' if in_position else 'raise'
            action_label = 'call IP (use position) / check-raise OOP'
    elif hand_rank >= 8:  # two pair
        action = 'raise' if (cr_freq >= 0.40) else 'call'
        action_label = 'raise/check-raise two pair' if action == 'raise' else 'call two pair'
    elif hand_rank >= 6:  # top pair
        if hero_equity >= alpha + 0.10:
            action = 'call'
            action_label = 'call top pair — have equity to continue'
        elif hero_equity < alpha:
            action = 'fold'
            action_label = 'fold — insufficient equity vs c-bet size'
        else:
            action = 'call' if in_position else 'fold'
            action_label = 'call IP marginal / fold OOP'
    elif hand_rank == 2:  # draw
        if hero_equity >= alpha:
            action = 'call' if in_position else ('raise' if cr_freq >= 0.40 else 'call')
            action_label = 'call draw IP / check-raise semi-bluff OOP'
        else:
            action = 'fold'
            action_label = 'fold — draw odds not justified'
    elif hand_rank <= 4:  # weak pair or air
        if in_position and villain_cbet_freq > 0.70:
            action = 'call'  # float
            action_label = 'float IP — villain c-bets too wide'
        else:
            action = 'fold'
            action_label = 'fold weak hand OOP or vs balanced c-bettor'
    else:
        action = 'call' if hero_equity >= alpha else 'fold'
        action_label = 'call' if action == 'call' else 'fold'

    # Range cap + protection
    is_capped = hand_rank <= 10  # caller has no 4-bet hands (AA/KK) in range
    should_protect = hand_rank >= 7 and cr_freq > 0.25

    # Key adjustments
    adjustments = []
    if in_position:
        adjustments.append(
            f'IP caller: use position to float {ip_float:.0%} of your range. '
            f'Do not fold too often — villain c-bets wide.'
        )
    else:
        adjustments.append(
            f'OOP caller: continue only top {oop_cont:.0%} of range. '
            f'Check-raise your strong hands to avoid being forced out.'
        )
    if is_capped:
        adjustments.append(
            'Range is CAPPED (no 4-bet hands). Villain knows this — '
            'check-raise some two pairs/sets to deny free information.'
        )
    if villain_cbet_freq > 0.75:
        adjustments.append(
            f'Villain c-bets {villain_cbet_freq:.0%} — very wide. '
            f'Float more IP; check-raise more OOP to punish.'
        )
    if spr < 3.0:
        adjustments.append(
            f'Low SPR={spr:.1f}: hands with equity are near-committed. '
            f'Raise/call-off top pair+ and draws; fold marginal hands.'
        )

    # Tips
    tips = []
    if street == 'flop' and hand_rank >= 8:
        tips.append(
            f'Strong hand in 3-bet pot on flop: consider check-raising instead of '
            f'calling. SPR={spr:.1f} means minimal post-flop maneuverability — build the pot now.'
        )
    if not in_position and action == 'call':
        tips.append(
            'Calling OOP in 3-bet pot: plan what to do vs a turn bet BEFORE calling. '
            'Only continue on turn if you improved or villain shows weakness (checks).'
        )
    if hand_rank == 2 and in_position:
        tips.append(
            f'Draw IP in 3-bet pot: prefer calling to semi-bluff raising. '
            f'SPR={spr:.1f} means a raise may price you out if villain re-raises.'
        )
    if ev_raise_val is not None and ev_raise_val > ev_call + 2.0:
        tips.append(
            f'EV(raise)={ev_raise_val:+.1f} > EV(call)={ev_call:+.1f}: '
            f'raising is significantly better — do not just call.'
        )

    reasoning = (
        f'3-bet pot caller ({street}, {"IP" if in_position else "OOP"}). '
        f'SPR={spr:.1f}. Hand={hand_cls} (rank={hand_rank}). '
        f'Hero eq={hero_equity:.0%}, alpha={alpha:.0%}. '
        f'C-bet freq={villain_cbet_freq:.0%} size={villain_cbet_size_pct:.0%}pot. '
        f'CR freq for this hand={cr_freq:.0%}. '
        f'Action: {action_label}.'
    )

    return CallerAdvice(
        hero_equity=hero_equity,
        hero_hand_class=hand_cls,
        in_position=in_position,
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        spr=round(spr, 2),
        villain_cbet_freq=villain_cbet_freq,
        cbet_alpha=round(alpha, 3),
        ip_float_freq=round(ip_float, 2),
        oop_continue_freq=round(oop_cont, 2),
        action=action,
        action_label=action_label,
        check_raise_freq=round(cr_freq, 2),
        ev_call=round(ev_call, 2),
        ev_fold=round(ev_fold, 2),
        ev_raise=round(ev_raise_val, 2) if ev_raise_val is not None else None,
        range_is_capped=is_capped,
        should_protect_range=should_protect,
        hero_hand_rank=hand_rank,
        reasoning=reasoning,
        key_adjustments=adjustments,
        tips=tips,
    )


def caller_one_liner(result: CallerAdvice) -> str:
    """Single-line overlay summary."""
    ip_str = 'IP' if result.in_position else 'OOP'
    ev_str = f'EV(call)={result.ev_call:+.1f}'
    return (
        f'3B-pot caller {ip_str} SPR={result.spr:.1f} | '
        f'{result.action.upper()} [{result.hero_hand_class}] | '
        f'{ev_str} | CR={result.check_raise_freq:.0%}'
    )
