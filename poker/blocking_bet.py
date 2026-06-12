"""
Blocking Bet Advisor (blocking_bet.py)

A blocking bet (or "blocker bet") is a small defensive bet made OOP on the
river with a medium-strength hand. The goal is NOT to build a large pot for
value — it's to control the price you pay to see showdown.

Why blocking bets work:
  - Villain may be planning a large bluff or value bet (75-100% pot)
  - By betting first (20-33% pot), hero:
      1. Denies villain the option to bet large
      2. Gets called by worse hands (thin value)
      3. Makes villain fold some of their bluffing range
      4. Often wins a small pot instead of facing a large shove

When to block-bet (OOP):
  - River, out-of-position
  - Hero has SDV (40-60% equity): beats bluffs, loses to value
  - Villain has high aggression factor (high AF) — likely to bet large
  - Pot is large enough that facing a villain bet would be uncomfortable
  - Board is wet/scary (completing draws) that villain could represent

When NOT to block-bet:
  - Hero has strong value (>65% equity) → bet large for value instead
  - Hero has no showdown value (<35%) → check-fold is better
  - Villain is passive (rarely bets) → just check-call
  - In position (IP) → check back naturally controls pot
  - Small pot (< 5BB) → not worth the sizing complications

Key EV calculation:
  - EV(block) = size × P(fold) + equity × (pot + size) × P(call) - size × P(call) + …
  - EV(check) = equity × pot × (1 - villain_bet_prob) + [check-call EV] × villain_bet_prob
  - Blocking saves EV when villain would bet big and hero has mediocre equity vs that bet

Optimal block-bet sizing:
  - Usually 20-33% pot
  - Enough to deny free showdown, small enough that villain can't raise profitably
  - On paired boards: 25% (villain's raise range narrower)
  - Wet boards: 30% (need to charge drawing hands)

Usage:
    from poker.blocking_bet import advise_blocking_bet, BlockingBetAdvice
    result = advise_blocking_bet(
        hero_equity=0.52,
        hero_pos='OOP',
        pot_bb=30.0,
        eff_stack_bb=70.0,
        villain_af=2.5,
        villain_wtsd=0.30,
        villain_bet_freq=0.55,
        board_type='medium',
    )
    print(result.action, result.block_size_bb)
"""

from dataclasses import dataclass, field
from typing import List


def _block_size_pct(board_type: str, villain_af: float) -> float:
    """Block bet as fraction of pot."""
    base = 0.27
    if board_type in ('wet', 'connected'):
        base += 0.05  # slightly bigger on scary boards
    elif board_type in ('dry', 'paired'):
        base -= 0.04  # smaller on static boards
    if villain_af >= 2.5:
        base += 0.03  # bigger vs aggressive players to not look weak
    return round(min(0.38, max(0.18, base)), 2)


def _villain_fold_to_block(villain_af: float, villain_wtsd: float) -> float:
    """How often villain folds to a small block bet."""
    base = 0.35
    af_adj = -(villain_af - 2.0) * 0.08  # aggressive: calls/raises more
    wtsd_adj = -(villain_wtsd - 0.30) * 0.40  # high WTSD: folds less
    return round(max(0.10, min(0.65, base + af_adj + wtsd_adj)), 3)


def _villain_bet_size_if_checks(villain_af: float, pot_bb: float) -> float:
    """Villain's expected bet size if hero checks."""
    if villain_af >= 3.0:
        pct = 0.85  # aggressive: bets large
    elif villain_af >= 2.0:
        pct = 0.65
    elif villain_af >= 1.0:
        pct = 0.50
    else:
        pct = 0.33  # passive: bets small or checks
    return round(pot_bb * pct, 1)


def _ev_block(
    size_bb: float,
    fold_pct: float,
    hero_equity: float,
    pot_bb: float,
) -> float:
    """EV of blocking bet."""
    ev_fold = fold_pct * pot_bb
    ev_call = (1 - fold_pct) * (hero_equity * (pot_bb + 2 * size_bb) - size_bb)
    return round(ev_fold + ev_call, 2)


def _ev_check(
    hero_equity: float,
    pot_bb: float,
    villain_bet_prob: float,
    villain_bet_bb: float,
    villain_bluff_pct: float,
) -> float:
    """EV of checking (hero check-calls or check-folds based on equity)."""
    # If villain checks back: hero wins at showdown proportionally
    ev_no_bet = hero_equity * pot_bb
    # If villain bets: hero calls when getting decent odds
    call_threshold = villain_bet_bb / (pot_bb + 2 * villain_bet_bb)
    if hero_equity >= call_threshold:
        ev_villain_bets = hero_equity * (pot_bb + 2 * villain_bet_bb) - villain_bet_bb
    else:
        ev_villain_bets = 0.0  # fold
    return round(
        (1 - villain_bet_prob) * ev_no_bet + villain_bet_prob * ev_villain_bets,
        2,
    )


@dataclass
class BlockingBetAdvice:
    """River blocking bet analysis."""
    hero_equity: float
    hero_pos: str
    pot_bb: float
    eff_stack_bb: float
    board_type: str

    # Decision
    action: str           # 'block_bet', 'check_call', 'value_bet', 'check_fold'
    block_size_bb: float
    block_size_pct: float

    # Villain model
    villain_fold_to_block: float
    villain_expected_bet_bb: float  # what villain bets if hero checks
    villain_bet_freq: float

    # EV comparison
    ev_block_bb: float
    ev_check_bb: float
    ev_saved_bb: float    # EV(block) - EV(check)

    # Context
    reasoning: str
    strategic_tips: List[str] = field(default_factory=list)


def advise_blocking_bet(
    hero_equity: float = 0.52,
    hero_pos: str = 'OOP',
    pot_bb: float = 30.0,
    eff_stack_bb: float = 70.0,
    villain_af: float = 2.0,
    villain_wtsd: float = 0.30,
    villain_bet_freq: float = 0.50,
    board_type: str = 'medium',
    villain_bluff_pct: float = 0.35,
) -> BlockingBetAdvice:
    """
    Advise on river blocking bet.

    Args:
        hero_equity:       Hero's showdown equity (0-1)
        hero_pos:          'OOP' or 'IP'
        pot_bb:            Current pot size
        eff_stack_bb:      Remaining effective stack
        villain_af:        Villain's aggression factor
        villain_wtsd:      Villain's went-to-showdown frequency
        villain_bet_freq:  How often villain bets river when checked to
        board_type:        'dry', 'medium', 'wet', 'paired', 'connected'
        villain_bluff_pct: Villain's estimated river bluff frequency

    Returns:
        BlockingBetAdvice
    """
    size_pct = _block_size_pct(board_type, villain_af)
    block_bb = round(pot_bb * size_pct, 1)

    fold_to_block = _villain_fold_to_block(villain_af, villain_wtsd)
    expected_villain_bet = _villain_bet_size_if_checks(villain_af, pot_bb)

    ev_blk = _ev_block(block_bb, fold_to_block, hero_equity, pot_bb)
    ev_chk = _ev_check(hero_equity, pot_bb, villain_bet_freq,
                        expected_villain_bet, villain_bluff_pct)
    ev_saved = round(ev_blk - ev_chk, 2)

    is_ip = hero_pos == 'IP'
    has_strong_value = hero_equity >= 0.65
    has_no_sdv = hero_equity < 0.35
    villain_is_passive = villain_af < 1.0 and villain_bet_freq < 0.30

    # Decision logic
    if is_ip:
        action = 'check_call' if hero_equity >= 0.45 else 'check_fold'
        reason = (
            f'In position: check back naturally controls pot. '
            f'No need to block bet from IP — just check back.'
        )
    elif has_strong_value:
        action = 'value_bet'
        reason = (
            f'High equity ({hero_equity:.0%}): bet for VALUE, not to block. '
            f'Use 65-75% pot sizing to extract maximum from worse hands.'
        )
    elif has_no_sdv:
        action = 'check_fold'
        reason = (
            f'Low equity ({hero_equity:.0%}): no showdown value. '
            f'Blocking with a hand that loses to villain\'s entire calling range '
            f'is a mistake. Check and fold to a bet.'
        )
    elif villain_is_passive:
        action = 'check_call'
        reason = (
            f'Passive villain (AF={villain_af:.1f}, bet_freq={villain_bet_freq:.0%}): '
            f'rarely bets river. No need to block — just check-call. '
            f'Blocking wastes chips vs someone who won\'t bet anyway.'
        )
    elif ev_blk >= ev_chk:
        action = 'block_bet'
        reason = (
            f'OOP block bet: {size_pct:.0%}pot = {block_bb:.1f}BB. '
            f'Villain expected to bet {expected_villain_bet:.1f}BB if checked to. '
            f'EV(block) = {ev_blk:.1f}BB vs EV(check) = {ev_chk:.1f}BB. '
            f'Saves {ev_saved:.1f}BB by setting the price.'
        )
    else:
        action = 'check_call'
        reason = (
            f'Check-call: EV(check) = {ev_chk:.1f}BB > EV(block) = {ev_blk:.1f}BB. '
            f'Villain\'s expected bet ({expected_villain_bet:.1f}BB) is small enough '
            f'that calling is better than blocking.'
        )

    tips = []
    if action == 'block_bet':
        tips.append(
            f'Size: {block_bb:.1f}BB ({size_pct:.0%}pot). '
            f'Villain folds {fold_to_block:.0%} → hero wins pot without showdown. '
            f'When called, hero has {hero_equity:.0%} equity.'
        )
        tips.append(
            f'If villain RAISES your block bet → fold. '
            f'Villain\'s raising range crushes your medium-strength holding.'
        )
    if villain_af >= 2.5:
        tips.append(
            f'Aggressive villain (AF={villain_af:.1f}): blocking is especially valuable. '
            f'Without block, expect {expected_villain_bet:.1f}BB bet — a much larger price.'
        )
    if board_type in ('wet', 'connected'):
        tips.append(
            'Wet board: hero\'s medium hand may be ahead of villain\'s missed draws. '
            'Blocking charges them to see if you\'re bluffing.'
        )

    return BlockingBetAdvice(
        hero_equity=round(hero_equity, 3),
        hero_pos=hero_pos,
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        board_type=board_type,
        action=action,
        block_size_bb=block_bb if action == 'block_bet' else 0.0,
        block_size_pct=size_pct if action == 'block_bet' else 0.0,
        villain_fold_to_block=fold_to_block,
        villain_expected_bet_bb=expected_villain_bet,
        villain_bet_freq=villain_bet_freq,
        ev_block_bb=ev_blk,
        ev_check_bb=ev_chk,
        ev_saved_bb=ev_saved,
        reasoning=reason,
        strategic_tips=tips,
    )


def blocking_bet_one_liner(result: BlockingBetAdvice) -> str:
    ev_str = f'+{result.ev_saved_bb:.1f}' if result.ev_saved_bb >= 0 else f'{result.ev_saved_bb:.1f}'
    return (
        f'[BLKB {result.hero_pos}] {result.action.upper()} | '
        f'size={result.block_size_bb:.0f}BB ({result.block_size_pct:.0%}pot) | '
        f'vfold={result.villain_fold_to_block:.0%} | '
        f'EV_saved={ev_str}BB'
    )
