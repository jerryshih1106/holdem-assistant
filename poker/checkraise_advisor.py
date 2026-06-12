"""
Check-Raise Advisor (checkraise_advisor.py)

Analyzes when and how to check-raise on each street.
Check-raising is one of the highest-EV plays when used correctly:
  - Value check-raises extract maximum value and build the pot
  - Bluff check-raises deny equity to draws and take down pots immediately
  - Frequency must be balanced to stay unexploitable

Usage:
    from poker.checkraise_advisor import analyze_checkraise, CheckRaiseResult
    result = analyze_checkraise(
        hole_cards=['Ah', 'Ac'],
        community=['As', '7h', '2d'],
        pot_bb=10.0,
        villain_bet_bb=6.0,
        hero_equity=0.88,
        board_wetness=0.20,
        villain_cbet_freq=0.70,
        villain_fold_to_cr=0.55,
    )
    print(result.action, result.cr_size_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CheckRaiseResult:
    """Full check-raise analysis."""
    # Input context
    pot_bb: float
    villain_bet_bb: float
    hero_equity: float
    board_wetness: float

    # CR sizing
    cr_size_bb: float          # recommended CR size
    min_cr_bb: float
    max_cr_bb: float

    # Fold equity
    villain_fold_to_cr: float  # estimated fold% to CR
    total_fold_equity: float   # fold_pct after villain folds to CR

    # EV components
    ev_checkraise: float       # EV of check-raising
    ev_checkcall: float        # EV of calling villain's bet
    ev_checkfold: float        # always 0

    # Classification
    action: str                # 'check-raise', 'check-call', 'check-fold'
    cr_type: str               # 'value', 'bluff', 'semi-bluff', 'none'
    is_value_cr: bool
    is_bluff_cr: bool

    # Frequency guidance
    recommended_cr_freq: float    # 0-1, how often to CR this hand type
    value_cr_threshold: float     # min equity for value CR
    bluff_cr_threshold: float     # max equity for bluff CR (must have fold equity)

    # Reasoning
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_checkraise(
    hole_cards: List[str],
    community: List[str],
    pot_bb: float,
    villain_bet_bb: float,
    hero_equity: float,
    board_wetness: float = 0.50,
    villain_cbet_freq: float = 0.60,
    villain_fold_to_cr: float = 0.50,
    hero_pos: str = 'BB',
    street: str = 'flop',
    eff_stack_bb: float = 100.0,
    has_draw: bool = False,
) -> CheckRaiseResult:
    """
    Analyze whether to check-raise, check-call, or check-fold.

    Args:
        hole_cards:         Hero's hole cards
        community:          Community cards
        pot_bb:             Pot before villain's bet
        villain_bet_bb:     Size of villain's bet
        hero_equity:        Hero's equity (0-1) from Monte Carlo
        board_wetness:      Board wetness from board_texture (0=dry, 1=wet)
        villain_cbet_freq:  How often villain c-bets this street (0-1)
        villain_fold_to_cr: How often villain folds to check-raise (0-1)
        hero_pos:           Hero's position (typically 'BB' or 'SB' for CR)
        street:             'flop', 'turn', 'river'
        eff_stack_bb:       Effective stack
        has_draw:           True if hero has a draw (flush/straight)

    Returns:
        CheckRaiseResult
    """
    total_pot = pot_bb + villain_bet_bb    # pot after villain bets

    # ── CR sizing ─────────────────────────────────────────────────────────
    # Standard: 2.5x-3.5x the bet, adjusted for street and wetness
    if street == 'flop':
        multiplier = 3.0 + board_wetness * 0.5   # wetter → bigger
    elif street == 'turn':
        multiplier = 2.8 + board_wetness * 0.3
    else:  # river
        multiplier = 2.5

    cr_size = multiplier * villain_bet_bb
    cr_size = max(cr_size, villain_bet_bb * 2.2)    # at least 2.2x
    cr_size = min(cr_size, eff_stack_bb * 0.5, total_pot * 2.5)  # cap

    min_cr = villain_bet_bb * 2.2
    max_cr = min(eff_stack_bb, total_pot * 3.0)

    # ── Fold equity ────────────────────────────────────────────────────────
    # If villain calls CR, they have ~30-40% of strong hands
    # total_fold_equity = % of time villain folds to the CR
    total_fold_eq = villain_fold_to_cr

    # ── Value CR threshold ─────────────────────────────────────────────────
    # On dry boards, CR for value with top ~25% of range
    # On wet boards, value CR with top ~20% (protect)
    value_cr_threshold = 0.65 + (1 - board_wetness) * 0.10
    # On river, tighten (polarise): only top hands; must be > flop threshold
    if street == 'river':
        value_cr_threshold = max(0.78, value_cr_threshold)

    # ── Bluff CR threshold ─────────────────────────────────────────────────
    # Bluff CR when: fold equity is high AND equity is low enough to not be value
    # Must have some equity (draw) or be at bottom of value range
    bluff_cr_threshold = 0.35
    if has_draw:
        bluff_cr_threshold = 0.45   # draws have more equity to semi-bluff

    # ── CR type classification ─────────────────────────────────────────────
    is_value_cr = hero_equity >= value_cr_threshold
    is_bluff_cr = (
        hero_equity < bluff_cr_threshold
        and villain_fold_to_cr >= 0.45
        and villain_cbet_freq >= 0.55     # they bet a lot → can bluff them
    )
    is_semi_bluff = (
        has_draw
        and bluff_cr_threshold <= hero_equity < value_cr_threshold
        and villain_fold_to_cr >= 0.40
    )

    if is_value_cr:
        cr_type = 'value'
    elif is_semi_bluff:
        cr_type = 'semi-bluff'
    elif is_bluff_cr:
        cr_type = 'bluff'
    else:
        cr_type = 'none'

    # ── EV calculation ─────────────────────────────────────────────────────
    # EV(CR) = fold_eq * total_pot + (1-fold_eq) * (equity * (total_pot + cr_size) - (1-eq)*cr_size)
    pot_if_fold = total_pot
    pot_if_call = total_pot + cr_size
    ev_if_villain_folds = pot_if_fold
    ev_if_villain_calls = hero_equity * pot_if_call - (1 - hero_equity) * cr_size

    ev_checkraise = (total_fold_eq * ev_if_villain_folds
                     + (1 - total_fold_eq) * ev_if_villain_calls)

    # EV(check-call) = equity * (total_pot) - (1-equity) * villain_bet
    ev_checkcall = hero_equity * total_pot - (1 - hero_equity) * villain_bet_bb

    ev_checkfold = 0.0

    # ── Recommended CR frequency ───────────────────────────────────────────
    if is_value_cr:
        freq = 0.90 if street != 'river' else 1.0   # always CR river value
    elif is_semi_bluff:
        freq = 0.55 + villain_fold_to_cr * 0.30
    elif is_bluff_cr:
        freq = 0.25 + villain_fold_to_cr * 0.30
    else:
        freq = 0.0

    freq = min(1.0, freq)

    # ── Action decision ───────────────────────────────────────────────────
    if (is_value_cr or is_semi_bluff or is_bluff_cr) and ev_checkraise > ev_checkcall:
        action = 'check-raise'
    elif ev_checkcall > 0:
        action = 'check-call'
    else:
        action = 'check-fold'

    # ── Tips ──────────────────────────────────────────────────────────────
    tips = []
    if is_value_cr and board_wetness > 0.6:
        tips.append(f'Wet board ({board_wetness:.0%}): CR for value + protection — '
                    f'do not let draws see free cards.')
    if villain_cbet_freq > 0.70 and villain_fold_to_cr > 0.55:
        tips.append(f'Villain c-bets {villain_cbet_freq:.0%} and folds {villain_fold_to_cr:.0%} '
                    f'to CR — expand bluff CR range.')
    if is_semi_bluff and has_draw:
        tips.append('Semi-bluff CR: if called you still have equity to win on later streets.')
    if street == 'river' and is_bluff_cr:
        tips.append('River bluff CR is highest risk — only use with nut blocker and large CR size.')
    if ev_checkraise < ev_checkcall and not (is_value_cr or is_semi_bluff):
        tips.append('Check-calling is more EV than CR here — no fold equity advantage.')
    if not tips:
        tips.append('Standard line — use GTO frequencies.')

    # ── Reasoning ─────────────────────────────────────────────────────────
    reasoning = (
        f'equity={hero_equity:.0%} vs villain bet {villain_bet_bb:.1f}BB '
        f'into {pot_bb:.1f}BB on {street} (wetness={board_wetness:.2f}). '
        f'CR {cr_size:.1f}BB — type: {cr_type}. '
        f'fold_eq={total_fold_eq:.0%} | '
        f'EV(CR)={ev_checkraise:.2f} vs EV(call)={ev_checkcall:.2f}. '
        f'Action: {action.upper()}.'
    )

    return CheckRaiseResult(
        pot_bb=pot_bb,
        villain_bet_bb=villain_bet_bb,
        hero_equity=hero_equity,
        board_wetness=board_wetness,
        cr_size_bb=round(cr_size, 1),
        min_cr_bb=round(min_cr, 1),
        max_cr_bb=round(max_cr, 1),
        villain_fold_to_cr=villain_fold_to_cr,
        total_fold_equity=total_fold_eq,
        ev_checkraise=round(ev_checkraise, 2),
        ev_checkcall=round(ev_checkcall, 2),
        ev_checkfold=0.0,
        action=action,
        cr_type=cr_type,
        is_value_cr=is_value_cr,
        is_bluff_cr=is_bluff_cr,
        recommended_cr_freq=round(freq, 2),
        value_cr_threshold=value_cr_threshold,
        bluff_cr_threshold=bluff_cr_threshold,
        reasoning=reasoning,
        tips=tips,
    )


def cr_one_liner(result: CheckRaiseResult) -> str:
    """Single-line overlay summary."""
    return (f'CR: {result.action.upper()} {result.cr_size_bb:.1f}BB '
            f'[{result.cr_type}] | '
            f'EV(CR)={result.ev_checkraise:+.1f} vs EV(call)={result.ev_checkcall:+.1f}')
