"""
Turn Check-Raise Advisor (turn_check_raise.py)

The turn check-raise (C/R) is the most powerful OOP weapon:
  - Used for value with strong made hands (two pair+, set)
  - Used as semi-bluff with strong draws (OESD, combo draw, flush draw)
  - Timing: hero checks OOP → villain bets → hero raises
  - SPR after C/R is very low (0.5-1.5) → nearly always committed

Why turn C/R is different from flop C/R:
  - Flop C/R: SPR still relatively high (5-8), draws have 2 streets left
  - Turn C/R: SPR becomes 0.5-2.0 after C/R; commitment is almost certain
  - Turn C/R range is NARROWER than flop C/R: fewer bluffs, more value
  - Draws that C/R on turn have only 1 card to come → must be very strong

Frequency benchmark:
  - Overall turn C/R frequency (OOP vs turn bet): 8-12%
  - Value C/R: two pair+ (SPR<3 after C/R) + overpair vs wet turn
  - Semi-bluff C/R: combo draw (15 outs), OESD (8 outs) on board without many completed draws
  - Fold: most one-pair hands, backdoor draws, gutshots

Sizing:
  - Standard: 2.5-3.5x villain's turn bet
  - Dry boards: 2.5x (villain has less calling equity)
  - Wet boards: 3.0-3.5x (need to protect vs draws)

Key principle: after C/R, hero is committed at SPR <= 1.5.
Do not C/R-fold. Only C/R if willing to call a 4-bet jam.

Usage:
    from poker.turn_check_raise import advise_turn_cr, TurnCRAdvice
    result = advise_turn_cr(
        hero_hand_class='two_pair',
        hero_equity=0.68,
        villain_bet_pct=0.60,
        pot_bb=18.0,
        eff_stack_bb=82.0,
        board_type='semi_wet',
        villain_af=2.2,
        villain_cbet_freq=0.65,
    )
    print(result.action, result.cr_size_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'draw': 1, 'backdoor_draw': 1, 'gutshot': 1,
        'bottom_pair': 2, 'middle_pair': 3,
        'top_pair_weak': 4, 'top_pair': 5, 'tptk': 6,
        'top_pair_strong': 6, 'overpair': 6, 'two_pair': 7, 'set': 8,
        'straight': 9, 'flush': 10, 'full_house': 11,
    }.get(hand_class.lower(), 5)


def _spr(pot_bb: float, eff_stack_bb: float) -> float:
    return eff_stack_bb / pot_bb if pot_bb > 0 else 99.0


def _cr_size_bb(villain_bet_bb: float, pot_bb: float, board_type: str,
                hero_equity: float) -> float:
    """
    Compute the check-raise size in BB.
    Standard: villain_bet * 2.5 to 3.5x.
    """
    # Base multiplier
    if board_type.lower() in ('wet', 'semi_wet', 'monotone'):
        mult = 3.2  # bigger raise to protect equity, deny draws
    elif board_type.lower() == 'paired':
        mult = 2.8
    else:
        mult = 2.6  # dry board: smaller raise OK

    # Strong equity → can go larger (more value, can call off more)
    if hero_equity >= 0.80:
        mult += 0.20

    raw = villain_bet_bb * mult
    # Never more than putting in ~75% of remaining stack
    return round(raw, 1)


def _spr_after_cr(pot_bb: float, cr_size_bb: float, villain_bet_bb: float,
                  eff_stack_bb: float) -> float:
    """SPR after hero check-raises."""
    hero_invested = cr_size_bb
    pot_after = pot_bb + villain_bet_bb + cr_size_bb
    remaining_stack = eff_stack_bb - hero_invested
    return remaining_stack / pot_after if pot_after > 0 else 0.0


def _action_and_freq(
    hand_class: str,
    hero_equity: float,
    villain_bet_pct: float,
    spr: float,
    spr_after: float,
    board_type: str,
    villain_af: float,
    villain_cbet_freq: float,
) -> tuple:
    """Return (action, cr_frequency, check_call_freq, check_fold_freq, reasoning)."""
    rank = _hand_rank(hand_class)
    is_wet = board_type.lower() in ('wet', 'semi_wet', 'monotone')

    # Very strong made hands → value C/R
    if rank >= 8:  # set+
        freq_cr = 0.75 if is_wet else 0.60  # trap more on dry boards
        freq_call = 1.0 - freq_cr
        return ('check_raise', freq_cr, freq_call, 0.0,
                f'Set+ value C/R: raise {freq_cr:.0%} of time. '
                f'SPR after C/R={spr_after:.2f} → committed. '
                f'Mix C/R with some check-calls to balance.')

    if rank == 7:  # two pair
        # Two pair on wet boards: almost always C/R (protect + value)
        freq_cr = 0.85 if is_wet else 0.65
        freq_call = 0.10
        freq_fold = 0.05
        return ('check_raise', freq_cr, freq_call, freq_fold,
                f'Two pair: C/R {freq_cr:.0%} — protect against draws, build pot. '
                f'Turn two pair is strong enough to commit (SPR after={spr_after:.2f}).')

    # Strong draws → semi-bluff C/R
    if rank == 1 and hero_equity >= 0.38:
        # Combo draw / OESD: strong enough to C/R
        freq_cr = 0.55 if hero_equity >= 0.48 else 0.35
        freq_call = 0.30
        freq_fold = max(0.0, 1.0 - freq_cr - freq_call)
        return ('check_raise', freq_cr, freq_call, freq_fold,
                f'Strong draw semi-bluff C/R {freq_cr:.0%}: '
                f'equity={hero_equity:.0%} + fold equity vs villain cbet={villain_cbet_freq:.0%}. '
                f'Balanced with check-calls.')

    # Weak draws / gutshot → check-call or fold
    if rank == 1 and hero_equity < 0.38:
        # Gutshot / backdoor: rarely profitable to C/R on turn
        freq_call = 0.35 if hero_equity >= 0.25 else 0.0
        freq_fold = 1.0 - freq_call
        return ('check_call' if freq_call > 0 else 'check_fold',
                0.0, freq_call, freq_fold,
                f'Weak draw (eq={hero_equity:.0%}): '
                f'{"check-call" if freq_call > 0 else "check-fold"} — '
                f'not enough equity to C/R on turn with 1 card left.')

    # TPTK / overpair (rank 6)
    if rank == 6:
        # TPTK vs aggressive villain on wet board: sometimes C/R
        if is_wet and villain_af >= 2.5:
            freq_cr = 0.30  # protection C/R
            freq_call = 0.55
            freq_fold = 0.15
            return ('check_call', freq_cr, freq_call, freq_fold,
                    f'TPTK on wet board vs aggro villain: C/R {freq_cr:.0%} for protection. '
                    f'Usually check-call {freq_call:.0%}. '
                    f'SPR after C/R={spr_after:.2f}.')
        # Standard: check-call TPTK on turn
        freq_call = max(0.40, 1.0 - villain_bet_pct * 0.4)
        freq_fold = 1.0 - freq_call
        return ('check_call', 0.0, freq_call, freq_fold,
                f'TPTK: check-call {freq_call:.0%} — not strong enough to C/R '
                f'as only hand in range; will lose to value raises.')

    # Top pair or weaker → mostly check-call/fold
    if rank >= 4:
        # Top pair: pot odds determine if we call
        alpha = villain_bet_pct / (1 + villain_bet_pct)
        if hero_equity >= alpha + 0.05:
            return ('check_call', 0.0, 0.70, 0.30,
                    f'Top pair: check-call with sufficient equity ({hero_equity:.0%} > alpha={alpha:.0%}). '
                    f'Do not C/R — range too thin to commit. Give up to large aggression.')
        else:
            return ('check_fold', 0.0, 0.20, 0.80,
                    f'Weak top pair: check-fold — equity={hero_equity:.0%} < alpha={alpha:.0%}. '
                    f'Not worth calling off stack with dominated top pair.')

    # Middle pair or weaker
    alpha = villain_bet_pct / (1 + villain_bet_pct)
    if hero_equity >= alpha - 0.05 and villain_af < 1.5:
        return ('check_call', 0.0, 0.30, 0.70,
                f'Middle pair vs passive villain: thin check-call. '
                f'Fold to large raises.')
    return ('check_fold', 0.0, 0.0, 1.0,
            f'Weak hand ({hand_class}): check-fold. '
            f'Not worth investing more chips.')


@dataclass
class TurnCRAdvice:
    """Turn check-raise decision and frequencies."""
    hero_hand_class: str
    hero_equity: float
    board_type: str
    villain_bet_pct: float
    villain_bet_bb: float
    pot_bb: float
    eff_stack_bb: float

    # SPR context
    spr: float
    spr_after_cr: float

    # Decision
    recommended_action: str   # 'check_raise', 'check_call', 'check_fold'
    cr_frequency: float       # how often to check-raise this hand class
    call_frequency: float
    fold_frequency: float

    # Sizing (when C/Ring)
    cr_size_bb: float
    cr_size_pct_of_pot: float

    # Commitment
    committed_after_cr: bool  # True if SPR after C/R <= 1.5

    # Reasoning
    action_reasoning: str
    key_concepts: List[str] = field(default_factory=list)


def advise_turn_cr(
    hero_hand_class: str,
    hero_equity: float,
    villain_bet_pct: float,
    pot_bb: float,
    eff_stack_bb: float,
    board_type: str = 'medium',
    villain_af: float = 2.0,
    villain_cbet_freq: float = 0.60,
) -> TurnCRAdvice:
    """
    Advise on turn check-raise strategy.

    Args:
        hero_hand_class:  Hand classification
        hero_equity:      Equity vs villain's turn betting range
        villain_bet_pct:  Villain's bet size as fraction of pot (e.g., 0.75)
        pot_bb:           Pot size before villain's bet
        eff_stack_bb:     Effective stack (before villain's bet)
        board_type:       'dry', 'semi_wet', 'wet', 'monotone', 'paired'
        villain_af:       Villain's aggression factor
        villain_cbet_freq: How often villain bets this street

    Returns:
        TurnCRAdvice
    """
    spr = _spr(pot_bb, eff_stack_bb)
    villain_bet_bb = round(pot_bb * villain_bet_pct, 1)
    cr_bb = _cr_size_bb(villain_bet_bb, pot_bb, board_type, hero_equity)
    spr_a = _spr_after_cr(pot_bb, cr_bb, villain_bet_bb, eff_stack_bb)
    committed = spr_a <= 1.5

    action, cr_freq, call_freq, fold_freq, reasoning = _action_and_freq(
        hero_hand_class, hero_equity, villain_bet_pct,
        spr, spr_a, board_type, villain_af, villain_cbet_freq,
    )

    # Clamp frequencies
    total = cr_freq + call_freq + fold_freq
    if total > 0:
        cr_freq   = round(cr_freq / total, 2)
        call_freq = round(call_freq / total, 2)
        fold_freq = round(1.0 - cr_freq - call_freq, 2)

    concepts = [
        f'Turn C/R SPR: currently {spr:.1f} → after C/R: {spr_a:.2f}. '
        f'{"COMMITTED — cannot check-raise and fold to 4-bet." if committed else "Not yet committed after C/R."}',
        f'Only C/R if willing to call off remaining {eff_stack_bb - cr_bb:.0f}BB on all-in. '
        f'Turn C/R-fold is a major leak.',
        f'Target C/R range: two pair+, combo draw (15 outs), OESD (8 outs). '
        f'TPTK and gutshot are usually check-call or fold.',
    ]
    if villain_cbet_freq >= 0.65:
        concepts.append(
            f'Villain fires turns {villain_cbet_freq:.0%}: C/R semi-bluffs more profitable '
            f'because villain continues wider and your fold equity is high.'
        )

    return TurnCRAdvice(
        hero_hand_class=hero_hand_class,
        hero_equity=round(hero_equity, 3),
        board_type=board_type,
        villain_bet_pct=villain_bet_pct,
        villain_bet_bb=villain_bet_bb,
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        spr=round(spr, 2),
        spr_after_cr=round(spr_a, 2),
        recommended_action=action,
        cr_frequency=cr_freq,
        call_frequency=call_freq,
        fold_frequency=fold_freq,
        cr_size_bb=cr_bb,
        cr_size_pct_of_pot=round(cr_bb / pot_bb, 2) if pot_bb > 0 else 0.0,
        committed_after_cr=committed,
        action_reasoning=reasoning,
        key_concepts=concepts,
    )


def turn_cr_one_liner(result: TurnCRAdvice) -> str:
    return (
        f'[TCR {result.hero_hand_class}] {result.recommended_action.upper()} | '
        f'C/R {result.cr_frequency:.0%} to {result.cr_size_bb:.0f}BB | '
        f'SPR-after={result.spr_after_cr:.2f} | '
        f'{"COMMIT" if result.committed_after_cr else "not-commit"}'
    )
