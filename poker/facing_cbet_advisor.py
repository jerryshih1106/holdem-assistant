"""
Facing C-Bet Advisor (facing_cbet_advisor.py)

When villain fires a continuation bet, hero needs a complete response plan:
fold / call / raise, and if raising, to what size. This module synthesizes
five key factors into a single action recommendation:

  1. Hero's equity vs villain's c-betting range
  2. C-bet size (determines break-even equity and MDF)
  3. Villain's c-bet frequency (high freq → more bluffs → wider defense)
  4. Position (IP can call more hands and raise as float/semi-bluff)
  5. SPR (low SPR forces commitments earlier)

Key formulas:
  required_equity  = cbet_size / (pot + 2 * cbet_size)
  MDF              = 1 - cbet_size / (pot + cbet_size)
  villain_bluff_pct ≈ (villain_cbet_freq - gto_cbet_freq) × 0.60

Action thresholds (base):
  raise:  hero_equity >= required_equity + 0.12  AND  hand strong enough to commit
  call:   hero_equity >= required_equity
  fold:   hero_equity <  required_equity

Adjustments:
  - High villain cbet (>70%): bluffing excessively → lower call threshold by 3-5%
  - IP: can float with less (IP float freq +10%); can raise bluffs more
  - Wet board + draws: drawing hands get credit for outs (add draw equity)
  - Low SPR (<3): commit or fold — no middle ground; lower raise threshold
  - River: no draws, no float — fold or value-call/raise only

Raising:
  - Value raise: 2.2-2.8x villain's bet (standard check-raise size)
  - Semi-bluff raise: 2.5-3.0x (need fold equity + draw equity)
  - Bluff raise: 2.8-3.2x (need high fold equity from small villain bet)
  - Only raise if villain's c-bet frequency is high (>55%) OR hand is strong

Street-specific adjustments:
  Flop: can float/call wide with position and implied odds
  Turn: tighten call range (missed draws lose value)
  River: only call/raise with made hands; no implied odds

Usage:
    from poker.facing_cbet_advisor import advise_facing_cbet, FacingCBetAdvice
    from poker.facing_cbet_advisor import facing_cbet_one_liner

    result = advise_facing_cbet(
        hero_hand_class='top_pair',
        board_type='medium',
        hero_pos='OOP',
        villain_cbet_freq=0.65,
        cbet_size_pct=0.50,
        hero_equity=0.55,
        spr=4.0,
        street='flop',
    )
    print(result.action, result.raise_to_pct)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    """0 = air, 10 = nuts."""
    return {
        'air': 0, 'trash': 0, 'backdoor': 1,
        'bottom_pair': 2, 'middle_pair': 3, 'top_pair': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'draw': 4,
        'medium': 4, 'strong': 7, 'set': 9, 'nuts': 10,
        'straight': 8, 'flush': 8, 'full_house': 10,
        'premium': 8, 'speculative': 2, 'marginal': 2,
    }.get(hand_class.lower(), 4)


def _is_draw_type(hand_class: str) -> bool:
    return hand_class.lower() in ('draw', 'speculative', 'backdoor')


def _required_equity(cbet_size_pct: float) -> float:
    """Break-even equity to call."""
    return round(cbet_size_pct / (1.0 + 2.0 * cbet_size_pct), 4)


def _mdf(cbet_size_pct: float) -> float:
    """Minimum Defense Frequency."""
    return round(1.0 - cbet_size_pct / (1.0 + cbet_size_pct), 3)


def _villain_bluff_est(villain_cbet_freq: float, board_type: str, street: str) -> float:
    """Estimate villain's bluff fraction within their c-bets."""
    # GTO c-bet frequency depends on board/street
    gto_base = {
        ('flop', 'dry'): 0.55, ('flop', 'medium'): 0.48, ('flop', 'wet'): 0.40,
        ('turn', 'dry'): 0.45, ('turn', 'medium'): 0.38, ('turn', 'wet'): 0.32,
        ('river', 'dry'): 0.40, ('river', 'medium'): 0.35, ('river', 'wet'): 0.28,
    }.get((street, board_type), 0.45)

    excess = max(0.0, villain_cbet_freq - gto_base)
    bluff_of_excess = excess * 0.65   # ~65% of excess c-bets are bluffs
    base_bluff = 0.35 if board_type == 'dry' else 0.30
    return round(min(0.70, base_bluff + bluff_of_excess), 3)


def _adjusted_threshold(
    req_eq: float,
    villain_cbet_freq: float,
    hero_pos: str,
    street: str,
    spr: float,
    board_type: str,
) -> float:
    """Adjusted call threshold (lower = defend more)."""
    threshold = req_eq

    # High cbet freq → villain bluffs too much → lower threshold (call more)
    if villain_cbet_freq > 0.70:
        threshold -= 0.04
    elif villain_cbet_freq > 0.60:
        threshold -= 0.02
    elif villain_cbet_freq < 0.40:
        threshold += 0.03  # tight cbet: only strong hands → need more equity to call

    # IP: can call more (extract value with position)
    if hero_pos == 'IP':
        threshold -= 0.03

    # River: no implied odds → tighten
    if street == 'river':
        threshold += 0.03

    # Very low SPR: commit or fold (no room for floating)
    if spr < 2.0:
        threshold += 0.02

    return round(max(0.10, min(0.60, threshold)), 4)


def _raise_threshold(req_eq: float, street: str, spr: float) -> float:
    """Equity needed to raise (higher bar than call)."""
    base = req_eq + 0.12
    if street == 'river':
        base += 0.05   # river raise = full commitment
    if spr < 2.0:
        base -= 0.05   # short stack: easier to commit
    return round(max(0.30, min(0.80, base)), 4)


def _raise_sizing(
    cbet_size_pct: float,
    hand_class: str,
    hero_pos: str,
    villain_cbet_freq: float,
) -> tuple:
    """(raise_to_pct_of_bet, raise_description)"""
    rank = _hand_rank(hand_class)

    if rank >= 7:  # strong value
        mult = 2.3 if hero_pos == 'IP' else 2.6
        desc = 'value check-raise'
    elif rank >= 5:  # top pair / tptk
        mult = 2.5
        desc = 'strong check-raise'
    elif _is_draw_type(hand_class) and villain_cbet_freq >= 0.55:
        mult = 2.8
        desc = 'semi-bluff raise'
    elif villain_cbet_freq >= 0.65 and rank <= 2:
        mult = 3.0
        desc = 'bluff raise (high villain cbet freq)'
    else:
        mult = 2.5
        desc = 'check-raise'

    return (round(mult, 1), desc)


def _call_freq(
    hero_equity: float,
    call_threshold: float,
    raise_threshold: float,
    spr: float,
    street: str,
) -> tuple:
    """(call_freq, raise_freq, fold_freq) as frequencies."""
    eq_margin = hero_equity - call_threshold

    if hero_equity >= raise_threshold:
        # Strong hand: raise-heavy
        raise_f = min(0.90, 0.40 + (hero_equity - raise_threshold) * 3.0)
        call_f = 1.0 - raise_f
        fold_f = 0.0
    elif eq_margin >= 0.05:
        # Clear call range
        call_f = 0.90
        raise_f = 0.10 if spr < 4 else 0.0
        fold_f = max(0.0, 1.0 - call_f - raise_f)
    elif eq_margin >= 0.0:
        # Marginal call
        call_f = 0.70
        raise_f = 0.0
        fold_f = 0.30
    elif eq_margin >= -0.05:
        # Slightly below threshold: mixed fold/call
        call_f = 0.30
        raise_f = 0.0
        fold_f = 0.70
    else:
        # Clear fold
        call_f = 0.0
        raise_f = 0.0
        fold_f = 1.0

    return (round(call_f, 2), round(raise_f, 2), round(fold_f, 2))


def _primary_action(call_f: float, raise_f: float, fold_f: float) -> str:
    if raise_f >= 0.50:
        return 'raise'
    if call_f >= 0.50:
        return 'call'
    return 'fold'


@dataclass
class FacingCBetAdvice:
    """Advice for responding to villain's continuation bet."""
    hero_hand_class: str
    board_type: str
    hero_pos: str
    villain_cbet_freq: float
    cbet_size_pct: float
    hero_equity: float
    spr: float
    street: str

    # Decision
    action: str            # 'fold', 'call', 'raise'
    call_freq: float       # frequency to call (0-1)
    raise_freq: float      # frequency to raise
    fold_freq: float       # frequency to fold

    # Raise details
    raise_to_pct: float    # raise to this multiple of villain's bet
    raise_description: str

    # Math
    required_equity: float
    adjusted_threshold: float  # threshold after adjustments
    mdf: float
    villain_bluff_pct: float

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_facing_cbet(
    hero_hand_class: str = 'top_pair',
    board_type: str = 'medium',
    hero_pos: str = 'OOP',
    villain_cbet_freq: float = 0.55,
    cbet_size_pct: float = 0.50,
    hero_equity: float = 0.55,
    spr: float = 4.0,
    street: str = 'flop',
) -> FacingCBetAdvice:
    """
    Advise hero's response to villain's c-bet.

    Args:
        hero_hand_class:  Hero's hand: 'top_pair','two_pair','draw','air','set', etc.
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' or 'OOP'
        villain_cbet_freq: Villain's overall c-bet frequency (0-1)
        cbet_size_pct:    C-bet size as fraction of pot (e.g., 0.5 = half pot)
        hero_equity:      Hero's equity vs villain's overall range (0-1)
        spr:              Stack-to-pot ratio
        street:           'flop', 'turn', 'river'

    Returns:
        FacingCBetAdvice
    """
    req_eq = _required_equity(cbet_size_pct)
    mdf = _mdf(cbet_size_pct)
    bluff_est = _villain_bluff_est(villain_cbet_freq, board_type, street)
    adj_threshold = _adjusted_threshold(req_eq, villain_cbet_freq, hero_pos, street, spr, board_type)
    raise_thr = _raise_threshold(req_eq, street, spr)
    raise_mult, raise_desc = _raise_sizing(cbet_size_pct, hero_hand_class, hero_pos, villain_cbet_freq)
    call_f, raise_f, fold_f = _call_freq(hero_equity, adj_threshold, raise_thr, spr, street)
    action = _primary_action(call_f, raise_f, fold_f)

    # Build reasoning
    margin = round(hero_equity - adj_threshold, 3)
    if action == 'raise':
        reason = (
            f'RAISE: Hero equity {hero_equity:.0%} >> adj_threshold {adj_threshold:.0%} '
            f'(req={req_eq:.0%}). Strong hand — raise to {raise_mult:.1f}x villain bet. '
            f'Villain bluff est={bluff_est:.0%} of cbets.'
        )
    elif action == 'call':
        reason = (
            f'CALL: Hero equity {hero_equity:.0%} >= adj_threshold {adj_threshold:.0%} '
            f'(margin={margin:+.0%}). MDF={mdf:.0%}. '
            f'Villain cbet_freq={villain_cbet_freq:.0%} → est bluffs={bluff_est:.0%}.'
        )
    else:
        reason = (
            f'FOLD: Hero equity {hero_equity:.0%} < adj_threshold {adj_threshold:.0%} '
            f'(deficit={margin:.0%}). Required eq={req_eq:.0%} for {cbet_size_pct:.0%}pot bet. '
            f'No profitable call or raise available.'
        )

    # Tips
    tips = []
    if villain_cbet_freq > 0.70:
        tips.append(
            f'Villain cbets {villain_cbet_freq:.0%} — far above GTO. '
            f'They are bluffing too much. Widen your defending range. '
            f'Call with any two cards that have reasonable equity (~{adj_threshold:.0%}+).'
        )
    if hero_pos == 'IP' and action == 'call' and street == 'flop':
        tips.append(
            'IP call: plan your turn action now. If villain bets turn again, '
            'you need top pair+ or a strong draw to continue profitably. '
            'If villain checks, consider betting any made hand for value.'
        )
    if _is_draw_type(hero_hand_class) and street == 'flop' and hero_equity >= 0.35:
        tips.append(
            f'Draw: consider semi-bluff raising vs a high-frequency c-bettor. '
            f'Raise gives fold equity + draw equity. '
            f'If called, you still win when draw completes ({hero_equity:.0%} equity).'
        )
    if spr < 2.5 and action == 'call':
        tips.append(
            f'Low SPR ({spr:.1f}): calling commits ~{1/spr:.0%} of effective stack. '
            f'Be prepared to call off the rest of the stack on the turn. '
            f'If not comfortable stacking off, fold now or raise.'
        )
    if street == 'river' and action == 'fold':
        tips.append(
            'River fold: no more streets to improve. '
            'If pot odds require more equity than you have, fold is correct. '
            'Exception: if villain has a high AF/bluff history, look for bluff-catches '
            'with hands that block villain\'s value range.'
        )

    # Guarantee at least one tip
    if not tips:
        if action == 'raise':
            tips.append(
                f'Check-raise to {raise_mult:.1f}x villain bet ({raise_desc}). '
                f'Your equity ({hero_equity:.0%}) significantly exceeds threshold ({adj_threshold:.0%}). '
                f'Build the pot on this street — do not slow-play.'
            )
        elif action == 'call':
            tips.append(
                f'Call: equity {hero_equity:.0%} above threshold {adj_threshold:.0%}. '
                f'MDF requires defending {mdf:.0%} of hands. '
                f'Plan for next street before calling: have a clear turn/river game plan.'
            )
        else:
            tips.append(
                f'Fold: equity {hero_equity:.0%} below threshold {adj_threshold:.0%}. '
                f'Required equity for {cbet_size_pct:.0%}pot bet: {req_eq:.0%}. '
                f'Villain cbet={villain_cbet_freq:.0%}, est bluffs={bluff_est:.0%} of cbets.'
            )

    return FacingCBetAdvice(
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        hero_pos=hero_pos,
        villain_cbet_freq=round(villain_cbet_freq, 3),
        cbet_size_pct=round(cbet_size_pct, 3),
        hero_equity=round(hero_equity, 3),
        spr=round(spr, 2),
        street=street,
        action=action,
        call_freq=call_f,
        raise_freq=raise_f,
        fold_freq=fold_f,
        raise_to_pct=raise_mult,
        raise_description=raise_desc,
        required_equity=req_eq,
        adjusted_threshold=adj_threshold,
        mdf=mdf,
        villain_bluff_pct=bluff_est,
        reasoning=reason,
        tips=tips,
    )


def facing_cbet_one_liner(result: FacingCBetAdvice) -> str:
    return (
        f'[FCB {result.hero_hand_class}@{result.street}|{result.hero_pos}] '
        f'{result.action.upper()} | '
        f'eq={result.hero_equity:.0%} need={result.adjusted_threshold:.0%} | '
        f'MDF={result.mdf:.0%} vbluff={result.villain_bluff_pct:.0%} | '
        f'cbet={result.villain_cbet_freq:.0%}'
    )
