"""
Stack Depth Preflop Advisor (stack_depth_preflop.py)

Effective stack depth dramatically changes optimal preflop strategy.
Many live players fail to adjust their ranges based on stack depth,
playing 200BB strategies with 40BB stacks and vice versa.

Stack depth regimes:
  15-25BB (ultra-short):
    - Push/fold only: no open-raise-fold, no flat calling
    - Shove or fold preflop, nothing else
    - Range determined by position + stack-specific ICM/EV tables
    - See pushfold.py for specific hand cutoffs

  25-40BB (short):
    - Open-raise but only to 2.0-2.2BB (commit-or-fold sizing)
    - 3-bet = jam (too short to 3-bet and fold)
    - No flat calling 3-bets (SPR too low for speculative hands)
    - Tighten opening range vs earlier positions

  40-60BB (medium-short):
    - Open to 2.2-2.5BB
    - Can 3-bet non-all-in but large (9-11BB) = pot-committed
    - Limited flat calling (only vs in-position opens with premium)
    - Suited connectors and small pairs: mostly fold (poor implied odds)

  60-100BB (standard):
    - Standard GTO opening ranges by position
    - Open to 2.5-3.0BB
    - Balanced 3-bet ranges (value + bluffs)
    - Call raises with speculative hands in position

  100-150BB (deep):
    - Widen calling ranges (more implied odds)
    - Small pairs and suited connectors become more valuable
    - Open to 2.5BB (position plays a larger role)
    - 3-bet range can be wider (more room to maneuver post-flop)

  150BB+ (very deep):
    - Maximum implied odds for suited connectors/small pairs
    - Limping becomes reasonable with strong implied-odds hands
    - Stack-to-pot ratio allows multi-street trap setups
    - Top pair decreases in relative value (need two pair+ to commit)

Usage:
    from poker.stack_depth_preflop import advise_stack_preflop, StackDepthAdvice
    result = advise_stack_preflop(
        eff_stack_bb=45.0,
        hero_pos='CO',
        hero_hand_class='medium',
        n_players=6,
        villain_3bet_pct=0.07,
    )
    print(result.action, result.open_size_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _hand_rank(hand_class: str) -> int:
    return {
        'premium': 10, 'strong': 8, 'medium_pair': 6, 'medium': 5,
        'speculative': 3, 'marginal': 2, 'trash': 0,
        'air': 0, 'draw': 2, 'bottom_pair': 2, 'middle_pair': 4,
        'top_pair': 5, 'tptk': 6, 'overpair': 8, 'two_pair': 7, 'set': 9,
    }.get(hand_class.lower(), 4)


def _stack_regime(eff_stack_bb: float) -> str:
    if eff_stack_bb < 25:
        return 'ultra_short'
    if eff_stack_bb < 40:
        return 'short'
    if eff_stack_bb < 60:
        return 'medium_short'
    if eff_stack_bb <= 100:
        return 'standard'
    if eff_stack_bb < 150:
        return 'deep'
    return 'very_deep'


def _open_size(regime: str, hero_pos: str) -> float:
    """Recommended open size in BB."""
    base = {
        'ultra_short': 0.0,    # shove only
        'short': 2.1,
        'medium_short': 2.3,
        'standard': 2.5,
        'deep': 2.5,
        'very_deep': 2.5,
    }.get(regime, 2.5)
    # BTN/CO can go slightly smaller (steal sizing)
    if hero_pos in ('BTN', 'SB') and regime in ('standard', 'deep', 'very_deep'):
        base -= 0.2
    return round(max(0.0, base), 1)


def _open_range_pct(regime: str, hero_pos: str) -> float:
    """Recommended open range as fraction of all hands (0-1)."""
    pos_base = {
        'UTG': 0.13, 'UTG1': 0.16, 'HJ': 0.20, 'CO': 0.27, 'BTN': 0.42, 'SB': 0.45
    }.get(hero_pos, 0.25)
    multiplier = {
        'ultra_short': 0.70,  # push range slightly tighter (ICM considerations)
        'short': 0.80,        # tighter — can't fold after opening
        'medium_short': 0.90,
        'standard': 1.00,
        'deep': 1.10,         # wider with implied odds
        'very_deep': 1.20,
    }.get(regime, 1.00)
    return round(min(0.65, pos_base * multiplier), 3)


def _threeBet_type(regime: str) -> str:
    if regime in ('ultra_short', 'short'):
        return 'jam'
    if regime == 'medium_short':
        return 'linear_large'  # large 3-bet, mostly committed
    if regime == 'standard':
        return 'polarized'
    return 'polarized_wide'


def _call_open_ok(regime: str, hand_rank: int, hero_pos: str) -> bool:
    """Should hero flat call an open raise?"""
    if regime == 'ultra_short':
        return False  # never flat, only jam or fold
    if regime == 'short':
        return hand_rank >= 8 and hero_pos in ('BTN', 'CO')  # only premiums, only IP
    if regime == 'medium_short':
        return hand_rank >= 6  # medium pairs+, only vs IP opens
    return hand_rank >= 3  # standard: medium and up


def _speculative_ok(regime: str) -> bool:
    """Are small pairs / suited connectors worth playing?"""
    return regime in ('deep', 'very_deep')


def _action(regime: str, hand_rank: int, hero_pos: str,
            villain_3bet_pct: float) -> tuple:
    """(action, reasoning)"""
    if regime == 'ultra_short':
        if hand_rank >= 5:
            return ('shove', f'Ultra-short ({regime}): push/fold only. Shove {hero_pos}.')
        return ('fold', f'Ultra-short ({regime}): push/fold only. Hand not strong enough to shove.')

    open_pct = _open_range_pct(regime, hero_pos)
    # Is this hand good enough to open?
    # Rough mapping: rank >= threshold to be in open range
    threshold_rank = max(0, 5 - int(open_pct * 15))
    in_open_range = hand_rank >= threshold_rank

    if not in_open_range:
        return ('fold', f'Hand rank {hand_rank} below open threshold for {regime} stack ({hero_pos}).')

    # Facing a 3-bet scenario?
    if villain_3bet_pct >= 0.10 and regime in ('short', 'medium_short'):
        if hand_rank >= 7:
            return ('open_jam', f'Short stack + aggressive villain: open-jam premiums to avoid 3-bet commitment.')
        return ('open_fold', f'Short stack vs aggro villain: open-raise but fold to 3-bet with non-premium.')

    return ('open_raise', f'Open-raise from {hero_pos}. Stack regime: {regime}.')


@dataclass
class StackDepthAdvice:
    """Preflop strategy adjusted for effective stack depth."""
    eff_stack_bb: float
    stack_regime: str
    hero_pos: str
    hero_hand_class: str
    n_players: int

    # Action
    action: str           # 'open_raise', 'shove', 'fold', 'call', 'open_jam', 'open_fold'
    open_size_bb: float
    threeBet_type: str    # 'jam', 'linear_large', 'polarized', 'polarized_wide'

    # Range context
    open_range_pct: float
    call_open_ok: bool
    speculative_hands_ok: bool  # small pairs, suited connectors

    # Stack-specific notes
    commit_threshold_bb: float  # bet this much = pot-committed
    implied_odds_factor: float  # multiplier for implied odds value

    # Notes
    action_reasoning: str
    stack_tips: List[str] = field(default_factory=list)


def advise_stack_preflop(
    eff_stack_bb: float = 100.0,
    hero_pos: str = 'CO',
    hero_hand_class: str = 'medium',
    n_players: int = 6,
    villain_3bet_pct: float = 0.07,
) -> StackDepthAdvice:
    """
    Advise preflop strategy based on effective stack depth.

    Args:
        eff_stack_bb:      Effective stack in big blinds
        hero_pos:          Hero's position ('UTG','HJ','CO','BTN','SB','BB')
        hero_hand_class:   Hero's hand classification
        n_players:         Number of players at table
        villain_3bet_pct:  Most aggressive villain's 3-bet frequency

    Returns:
        StackDepthAdvice
    """
    rank = _hand_rank(hero_hand_class)
    regime = _stack_regime(eff_stack_bb)
    open_bb = _open_size(regime, hero_pos)
    open_pct = _open_range_pct(regime, hero_pos)
    threeb_type = _threeBet_type(regime)
    call_ok = _call_open_ok(regime, rank, hero_pos)
    spec_ok = _speculative_ok(regime)
    action, reasoning = _action(regime, rank, hero_pos, villain_3bet_pct)

    # Commit threshold: how much investment makes hero pot-committed
    commit_bb = round(eff_stack_bb * 0.33, 1)

    # Implied odds factor: deeper = more valuable speculative hands
    implied_factor = min(3.0, eff_stack_bb / 100.0)

    # Tips
    tips = []
    if regime == 'ultra_short':
        tips.append(
            f'{eff_stack_bb:.0f}BB (ultra-short): Push-fold chart only. '
            f'Opening and folding to 3-bets wastes ~1BB each time. '
            f'Shove ranges: UTG=AA-TT/AK/AQ, BTN=AA-55/AK-AJ/KQ.'
        )
    elif regime == 'short':
        tips.append(
            f'{eff_stack_bb:.0f}BB (short): Open to {open_bb:.1f}BB. '
            f'3-bet = shove (no room to 3-bet/fold). '
            f'Do NOT flat speculative hands — SPR will be too low post-flop.'
        )
    elif regime == 'medium_short':
        tips.append(
            f'{eff_stack_bb:.0f}BB (medium-short): 3-bet to ~11BB commits ~25% of stack. '
            f'Treat large 3-bets as semi-committed. '
            f'Suited connectors need 15:1 implied odds — not available here.'
        )
    elif regime == 'standard':
        tips.append(
            f'{eff_stack_bb:.0f}BB (standard): GTO ranges apply. '
            f'Balanced 3-bet range (premium value + suited Ace bluffs). '
            f'Flat speculative hands in position only.'
        )
    elif regime == 'deep':
        tips.append(
            f'{eff_stack_bb:.0f}BB (deep): Widen flat calling range. '
            f'Small pairs, suited connectors need ~10:1 implied odds — achievable. '
            f'Set mining: call up to 5% of stack to set-mine.'
        )
    else:  # very_deep
        tips.append(
            f'{eff_stack_bb:.0f}BB (very deep): Maximum implied odds. '
            f'Top pair decreases in value — commit only with two pair+. '
            f'Slow-play sets: bigger implied odds from deeper stacks.'
        )
    if villain_3bet_pct >= 0.10:
        tips.append(
            f'Aggressive villain (3bet={villain_3bet_pct:.0%}): '
            f'Open tighter or open-jam premiums to deny fold equity. '
            f'At {regime} depth, being re-raised is costly.'
        )
    if not spec_ok and rank == 3:
        tips.append(
            f'Speculative hands (suited connectors, small pairs) require deep stacks. '
            f'At {eff_stack_bb:.0f}BB, pot odds and SPR do not support implied-odds plays.'
        )

    return StackDepthAdvice(
        eff_stack_bb=round(eff_stack_bb, 1),
        stack_regime=regime,
        hero_pos=hero_pos,
        hero_hand_class=hero_hand_class,
        n_players=n_players,
        action=action,
        open_size_bb=open_bb,
        threeBet_type=threeb_type,
        open_range_pct=open_pct,
        call_open_ok=call_ok,
        speculative_hands_ok=spec_ok,
        commit_threshold_bb=commit_bb,
        implied_odds_factor=round(implied_factor, 2),
        action_reasoning=reasoning,
        stack_tips=tips,
    )


def stack_depth_one_liner(result: StackDepthAdvice) -> str:
    return (
        f'[SD {result.eff_stack_bb:.0f}BB|{result.stack_regime}] '
        f'{result.action.upper()} | '
        f'open={result.open_size_bb:.1f}BB range={result.open_range_pct:.0%} | '
        f'3b={result.threeBet_type} | '
        f'spec={"OK" if result.speculative_hands_ok else "NO"}'
    )
