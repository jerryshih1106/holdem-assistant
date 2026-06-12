"""
IP Check-Back Range Advisor (check_back_ip.py)

When hero is in position on the flop or turn and has the option to check back
instead of betting, building a well-balanced check-back range is critical:

  Why check back at all (even with strong hands)?
    - If hero always bets strong hands and always checks weak hands, villain
      knows that hero's checking range is capped and weak → villain auto-bets
      every time hero checks → hero loses value on every check.
    - A balanced check-back range includes SOME strong hands (traps) so villain
      cannot freely bet into hero after a check.

  Four categories of hands to check back:
    1. MUST CHECK (pure pot control):
       - Medium strength one-pair hands (TPWK, middle pair, bottom pair) on wet
         boards where drawing cards are dangerous. Checking controls pot, keeps
         SPR manageable, and denies villain easy bluff opportunities.

    2. TRAP CHECK (balance + implied odds):
       - A portion of strong hands — sets, overpairs, flopped two-pair — to
         keep the checking range strong. Trap frequency scales with board
         wetness: check more on wet boards to protect against bad turn cards.

    3. DRAW CHECKS (balance + deception):
       - Some draws check back instead of semi-bluffing to keep the checking
         range credible. Specifically: backdoor draws, weak flush draws that
         prefer to see a free card, and combo draws on boards where a bet would
         commit too many chips.

    4. BLUFF CATCHER CHECKS (value on later streets):
       - Hands like second/third pair that prefer to get to showdown cheaply.
         These call if villain bets but not worth building a pot with.

  Frequencies by board type:
    Dry board   (e.g. K72r): trap set/TP ~10%; check 60% of one-pair
    Medium      (e.g. T87ss): trap set/2P ~20%; semi-draws check ~25%
    Wet/dynamic (e.g. J98ss): trap set/2P ~30%; draws check ~40%

Usage:
    from poker.check_back_ip import advise_check_back, CheckBackAdvice
    result = advise_check_back(
        hero_hand_class='top_pair',
        hero_equity=0.68,
        board_type='medium',
        street='flop',
        pot_bb=12.0,
        eff_stack_bb=95.0,
        villain_cbet_freq=0.65,
        villain_check_raise_freq=0.15,
    )
    print(result.recommended_action, result.check_back_freq)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Board texture parameters: (trap_freq_base, draw_check_freq, pot_control_freq)
_BOARD_PARAMS = {
    'dry':       (0.10, 0.10, 0.55),
    'semi_dry':  (0.12, 0.15, 0.50),
    'medium':    (0.20, 0.25, 0.45),
    'semi_wet':  (0.25, 0.30, 0.40),
    'wet':       (0.30, 0.40, 0.35),
    'monotone':  (0.35, 0.15, 0.40),
    'paired':    (0.08, 0.05, 0.60),
}


def _board_params(board_type: str) -> tuple:
    return _BOARD_PARAMS.get(board_type.lower(), _BOARD_PARAMS['medium'])


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'draw': 1, 'backdoor_draw': 1, 'bottom_pair': 2,
        'middle_pair': 3, 'top_pair_weak': 4, 'top_pair': 5, 'tptk': 6,
        'top_pair_strong': 6, 'overpair': 6, 'two_pair': 7, 'set': 8,
        'straight': 9, 'flush': 10, 'full_house': 11, 'quads': 12,
    }.get(hand_class.lower(), 5)


def _spr(pot_bb: float, eff_stack_bb: float) -> float:
    return eff_stack_bb / pot_bb if pot_bb > 0 else 99.0


def _check_back_category(
    hand_class: str,
    hero_equity: float,
    board_type: str,
    street: str,
    spr: float,
    villain_cbet_freq: float,
    villain_check_raise_freq: float,
) -> tuple:
    """
    Categorize the hand and return:
    (category, recommended_action, check_back_freq, reasoning)

    category: 'must_check', 'trap_check', 'draw_check', 'bluff_catcher', 'should_bet'
    recommended_action: 'check' or 'bet'
    check_back_freq: frequency to check this hand class (0.0 - 1.0)
    """
    rank = _hand_rank(hand_class)
    trap_base, draw_check, pot_ctrl = _board_params(board_type)

    # SPR adjustment: high SPR → check more (pot control matters more)
    spr_adj = min(0.15, max(-0.10, (spr - 8.0) * 0.015))

    # Villain aggression adjustment
    # If villain bets when checked to, checking (trapping) becomes more valuable
    aggression_adj = max(0.0, (villain_cbet_freq - 0.50) * 0.20)
    # But if villain check-raises a lot, reduce check-raises from strong hands
    xr_adj = max(0.0, villain_check_raise_freq * 0.10)

    is_wet = board_type.lower() in ('wet', 'semi_wet', 'monotone')
    is_turn = street.lower() == 'turn'

    # -- AIR / COMPLETE BLUFFS (rank 0)
    if rank == 0:
        # Never bet air as a pure bluff on turn with high villain aggression
        if is_turn and hero_equity < 0.15:
            return ('must_check', 'check', 1.0,
                    'Air on turn: no equity. Pot control. Check-fold if villain bets.')
        freq = 0.80
        return ('must_check', 'check', freq,
                f'Air ({hero_equity:.0%} equity): check back to preserve stack. '
                f'Bet rarely as delayed bluff on dry boards only.')

    # -- DRAWS (rank 1)
    if rank == 1:
        # Sometimes check back draws to balance checking range
        base_check = draw_check + spr_adj
        # Strong draws (equity >= 0.45) bet more
        if hero_equity >= 0.45:
            check_freq = max(0.15, base_check - 0.15)
            action = 'bet' if check_freq < 0.50 else 'check'
        # Weak/backdoor draws
        else:
            check_freq = min(0.90, base_check + 0.20)
            action = 'check' if check_freq >= 0.50 else 'bet'
        return ('draw_check', action, round(check_freq, 2),
                f'Draw (eq={hero_equity:.0%}): check back {check_freq:.0%} of the time to '
                f'balance range. Bet the rest as semi-bluff.')

    # -- BOTTOM PAIR / MIDDLE PAIR (ranks 2-3): pot control or bluff catcher
    if rank <= 3:
        check_freq = min(0.95, pot_ctrl + spr_adj + 0.10)
        action = 'check' if check_freq >= 0.60 else 'bet'
        cat = 'must_check' if check_freq >= 0.80 else 'bluff_catcher'
        return (cat, action, round(check_freq, 2),
                f'{hand_class} (eq={hero_equity:.0%}): check back {check_freq:.0%}. '
                f'Thin value on a {board_type} board. Call if villain bets small.')

    # -- TOP PAIR WEAK (rank 4)
    if rank == 4:
        check_freq = pot_ctrl + spr_adj
        if is_wet:
            check_freq += 0.10
        action = 'check' if check_freq >= 0.55 else 'bet'
        return ('must_check' if check_freq >= 0.65 else 'pot_control',
                action, round(check_freq, 2),
                f'Top pair weak: check back {check_freq:.0%} on {board_type} board. '
                f'Prefer one-and-done sizing if betting. Give up to significant aggression.')

    # -- TOP PAIR / TPTK / OVERPAIR (ranks 5-6)
    if rank <= 6:
        # Mostly bet, but trap some on wet boards / vs aggressive villains
        trap_freq = trap_base + aggression_adj + spr_adj * 0.5
        if is_wet:
            trap_freq += 0.05
        trap_freq = round(min(0.45, max(0.05, trap_freq)), 2)
        bet_freq = 1.0 - trap_freq
        action = 'bet' if bet_freq >= 0.60 else 'check'
        return ('trap_check', action, trap_freq,
                f'{hand_class} (eq={hero_equity:.0%}): bet {bet_freq:.0%}, '
                f'trap check {trap_freq:.0%} to balance range. '
                f'Trap more vs aggressive ({villain_cbet_freq:.0%} cbet) villain.')

    # -- TWO PAIR (rank 7)
    if rank == 7:
        trap_freq = min(0.35, trap_base + aggression_adj + 0.05)
        if is_wet:
            trap_freq += 0.08
        trap_freq = round(trap_freq, 2)
        action = 'bet'  # mostly bet two pair for value
        return ('trap_check', action, trap_freq,
                f'Two pair: mostly bet for value. Trap {trap_freq:.0%} '
                f'especially on {board_type} boards (scare cards can slow action).')

    # -- SET+ (ranks 8+): mostly bet, trap ~25-30% vs aggressive villains
    trap_freq = min(0.50, trap_base + aggression_adj + xr_adj + 0.10)
    if is_wet and rank == 8:
        trap_freq += 0.05  # sets on wet boards trap more (want to continue)
    trap_freq = round(trap_freq, 2)
    action = 'bet' if aggression_adj < 0.10 else 'check'
    cat = 'trap_check'
    return (cat, action, trap_freq,
            f'{hand_class}: trap {trap_freq:.0%} with villain cbet={villain_cbet_freq:.0%}. '
            f'Check-raise if villain bets into you. Vary between fast-play and slowplay.')


def _build_recommendations(
    hand_class: str,
    category: str,
    action: str,
    check_freq: float,
    board_type: str,
    spr: float,
    villain_cbet_freq: float,
    street: str,
) -> List[str]:
    rank = _hand_rank(hand_class)
    recs = []

    if category == 'trap_check' and action == 'check':
        recs.append(
            f'After checking back, call {villain_cbet_freq:.0%} villain bets on next street. '
            f'Consider check-raise if villain has high cbet tendency ({villain_cbet_freq:.0%}).'
        )
        recs.append(
            f'Checking with {hand_class} protects your check-back range. '
            f'Villain cannot over-bet freely when you might have sets or overpairs.'
        )

    if category == 'must_check' and rank <= 3:
        recs.append(
            f'With {hand_class} on {board_type} board: check-call 1 street max vs small bets. '
            f'Fold to 2 barrels unless odds are compelling.'
        )

    if category == 'draw_check':
        recs.append(
            f'Checking back draw balances your checking range. '
            f'If you ONLY check back air and ONLY bet draws, villain folds to all draw-hitting bets.'
        )
        if street == 'flop':
            recs.append(
                f'Flop check-back with draw: see free turn card. '
                f'Bet turn aggressively when draw completes or you pick up equity.'
            )

    if spr <= 4 and rank >= 5:
        recs.append(
            f'Low SPR ({spr:.1f}): bet/commit. Checking is less appropriate when SPR is low — '
            f'the pot is already large relative to remaining stack.'
        )

    if not recs:
        recs.append(
            f'Check back frequency {check_freq:.0%}. '
            f'Balance betting and checking to avoid being exploited.'
        )

    return recs


@dataclass
class CheckBackAdvice:
    """IP check-back range advice for a given hand and board situation."""
    # Input context
    hero_hand_class: str
    hero_equity: float
    board_type: str
    street: str
    spr: float
    pot_bb: float
    eff_stack_bb: float

    # Classification
    category: str           # 'must_check', 'trap_check', 'draw_check', 'bluff_catcher', 'should_bet'
    recommended_action: str # 'check' or 'bet'
    check_back_freq: float  # 0.0-1.0 — how often to check this hand class
    bet_freq: float         # 1.0 - check_back_freq

    # Sizing (when betting)
    recommended_bet_pct: float  # fraction of pot
    recommended_bet_bb: float

    # Strategy notes
    category_reasoning: str
    recommendations: List[str] = field(default_factory=list)

    # Range balance summary
    range_summary: str = ''
    one_liner: str = ''


def advise_check_back(
    hero_hand_class: str,
    hero_equity: float,
    board_type: str = 'medium',
    street: str = 'flop',
    pot_bb: float = 10.0,
    eff_stack_bb: float = 100.0,
    villain_cbet_freq: float = 0.60,
    villain_check_raise_freq: float = 0.12,
) -> CheckBackAdvice:
    """
    Advise on whether to check back or bet when IP on flop/turn.

    Args:
        hero_hand_class:        Hand classification
        hero_equity:            Current equity vs villain's range
        board_type:             'dry', 'semi_dry', 'medium', 'semi_wet', 'wet', 'monotone', 'paired'
        street:                 'flop' or 'turn'
        pot_bb:                 Current pot in BB
        eff_stack_bb:           Effective stack remaining
        villain_cbet_freq:      How often villain bets when checked to (0-1)
        villain_check_raise_freq: How often villain check-raises (0-1)

    Returns:
        CheckBackAdvice with recommended action and frequency
    """
    spr = _spr(pot_bb, eff_stack_bb)

    category, action, check_freq, reasoning = _check_back_category(
        hero_hand_class, hero_equity, board_type, street,
        spr, villain_cbet_freq, villain_check_raise_freq,
    )

    bet_freq = round(1.0 - check_freq, 2)

    # Recommended bet size when betting (smaller for traps, larger for strong hands)
    rank = _hand_rank(hero_hand_class)
    if rank >= 8:        # set+
        bet_pct = 0.75
    elif rank >= 6:      # overpair/tptk
        bet_pct = 0.60
    elif rank >= 4:      # top pair
        bet_pct = 0.50
    elif rank == 1:      # draw
        bet_pct = 0.55
    else:                # bluff/pair
        bet_pct = 0.40

    # Board adjustment
    if board_type in ('wet', 'semi_wet'):
        bet_pct = min(0.90, bet_pct + 0.10)

    bet_bb = round(pot_bb * bet_pct, 1)

    recs = _build_recommendations(
        hero_hand_class, category, action, check_freq,
        board_type, spr, villain_cbet_freq, street,
    )

    # Range balance summary
    trap_base, draw_check_base, pot_ctrl_base = _board_params(board_type)
    range_summary = (
        f'On {board_type} {street}: '
        f'check back ~{pot_ctrl_base:.0%} of one-pair hands (pot control), '
        f'trap ~{trap_base:.0%} of sets/strong hands, '
        f'check back ~{draw_check_base:.0%} of draws to balance range.'
    )

    one_liner = (
        f'[CB {hero_hand_class}] {action.upper()} ({check_freq:.0%} chk) | '
        f'{category} | '
        f'bet={bet_pct:.0%}pot={bet_bb:.0f}BB | '
        f'SPR={spr:.1f}'
    )

    return CheckBackAdvice(
        hero_hand_class=hero_hand_class,
        hero_equity=round(hero_equity, 3),
        board_type=board_type,
        street=street,
        spr=round(spr, 2),
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        category=category,
        recommended_action=action,
        check_back_freq=check_freq,
        bet_freq=bet_freq,
        recommended_bet_pct=round(bet_pct, 2),
        recommended_bet_bb=bet_bb,
        category_reasoning=reasoning,
        recommendations=recs,
        range_summary=range_summary,
        one_liner=one_liner,
    )


def check_back_range_summary(
    board_type: str = 'medium',
    street: str = 'flop',
    villain_cbet_freq: float = 0.60,
) -> dict:
    """
    Return a summary of check-back frequencies for all major hand classes
    on a given board type. Useful for range visualization in the overlay.

    Returns: dict {hand_class: {'action': str, 'freq': float, 'category': str}}
    """
    result = {}
    hand_classes = [
        ('air', 0.10), ('draw', 0.40), ('backdoor_draw', 0.20),
        ('bottom_pair', 0.30), ('middle_pair', 0.42),
        ('top_pair_weak', 0.55), ('top_pair', 0.65), ('tptk', 0.72),
        ('overpair', 0.75), ('two_pair', 0.78), ('set', 0.85),
    ]
    for hand_class, equity in hand_classes:
        r = advise_check_back(
            hero_hand_class=hand_class,
            hero_equity=equity,
            board_type=board_type,
            street=street,
            pot_bb=10.0,
            eff_stack_bb=100.0,
            villain_cbet_freq=villain_cbet_freq,
        )
        result[hand_class] = {
            'action': r.recommended_action,
            'check_freq': r.check_back_freq,
            'bet_freq': r.bet_freq,
            'category': r.category,
        }
    return result


def check_back_one_liner(result: CheckBackAdvice) -> str:
    return result.one_liner
