"""
OOP Turn Advisor (oop_turn_advisor.py)

When hero is out of position (OOP) and first to act on the turn, the decision
to bet vs check is one of the most common and costly mistakes in live poker.

Unlike in-position play (covered by turn_barrel_decision.py, delayed_cbet.py),
OOP turn decisions carry additional risk: checking can give a free card and
give up the initiative, while betting into an in-position opponent who can
raise is dangerous with medium-strength hands.

Flop sequences that lead to OOP turn decisions:
  1. Hero bet flop (as PFR or donk), got called by IP villain → "double barrel" spot
  2. Hero checked flop, villain bet, hero called → "probe" or "check-back" spot
  3. Hero checked flop, villain checked, both checked through → "lead turn" spot
  4. Hero bet flop, villain raised, hero called → "OOP vs aggressive" spot

Key principles:
  Sequence 1 (hero bet, got called):
    - Continue betting with: range advantage on this board + hands that want protection
    - Check-fold with: pure air that missed
    - Check-raise with: nuts/near-nuts (trap aggressive IP villain)
    - Board: blank → continue; scare card → check-fold bluffs, bet value

  Sequence 2 (villain bet, hero called):
    - Check-call with: hands with equity (draws, top pair)
    - Probe bet with: semi-strong hands + villain is passive on turn
    - Check-fold with: hands that can't call a second barrel
    - IP villain checked flop, bet turn → give credit

  Sequence 3 (both checked flop):
    - Lead turn with: draws that need protection, nutted hands (balancing)
    - Check-call/check-raise: vs aggressive IP player who might bet
    - Lead frequently: checked-through flop = no range advantage signal

  Sequence 4 (hero bet, villain raised, hero called):
    - Almost always check: hero showed strength but villain showed more
    - Check-call with: sets, top two pair (strong hands that called raise)
    - Check-fold with: medium pairs (can't call another barrel)

Turn card effects on OOP betting:
  Blank turn: continue with original plan
  Hero hits draw: bet or check-raise
  Scare card (overcards, draw completes): check and reassess
  Board pairs: slow down with medium pairs (villain might have trips)

Usage:
    from poker.oop_turn_advisor import advise_oop_turn, OopTurnAdvice, oop_turn_one_liner
    result = advise_oop_turn(
        flop_sequence='hero_bet_called',
        hero_hand_class='top_pair',
        turn_card_type='blank',
        hero_equity=0.60,
        spr=3.5,
        villain_af=2.0,
        villain_cbet_pct=0.55,
        board_type='medium',
        hero_has_draw=False,
        pot_bb=20.0,
    )
    print(result.action, result.bet_size_pct)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'trash': 0, 'bottom_pair': 2, 'draw': 3, 'marginal': 2,
        'middle_pair': 3, 'top_pair': 4, 'tptk': 5, 'medium': 4,
        'overpair': 6, 'two_pair': 6, 'set': 9, 'strong': 7,
        'straight': 8, 'flush': 8, 'premium': 8, 'speculative': 3,
    }.get(hand_class.lower(), 4)


def _is_draw(hand_class: str) -> bool:
    return hand_class.lower() in ('draw', 'speculative')


def _is_strong(hand_class: str) -> bool:
    return _hand_rank(hand_class) >= 7


def _is_value(hand_class: str) -> bool:
    return _hand_rank(hand_class) >= 4


def _turn_card_modifier(turn_card_type: str, hero_has_draw: bool, hand_rank: int) -> float:
    """
    Multiplier on base bet frequency based on turn card.
    Returns 1.0 for no change, <1 to reduce betting, >1 to increase.
    """
    if turn_card_type == 'blank':
        return 1.0
    if turn_card_type == 'hero_hits':
        return 1.30   # hit our draw → bet more
    if turn_card_type == 'scare':
        if hand_rank >= 7:
            return 1.10   # strong hand: bet for protection on scare card
        return 0.40   # medium/weak: reduce betting significantly
    if turn_card_type == 'draw_completes':
        if hand_rank >= 7:
            return 0.70   # draw completed, reduce bluffing, still value bet
        return 0.25   # medium hands: mostly check, draw completed
    if turn_card_type == 'board_pairs':
        if hand_rank >= 9:   # set/full house
            return 1.20
        if hand_rank >= 6:   # two pair might be counterfeited
            return 0.60
        return 0.50   # medium: check mostly
    return 1.0


def _seq1_advice(
    hand_rank: int, turn_mod: float, villain_af: float, spr: float,
) -> tuple:
    """hero_bet_called: turn after hero's flop cbet was called."""
    if hand_rank >= 7 and villain_af >= 2.0:
        action = 'check_raise'
        freq = 0.65
        reason = f'Strong hand ({hand_rank}) vs aggressive villain (AF={villain_af:.1f}): check-raise trap.'
    elif hand_rank >= 5:
        freq = max(0.20, min(0.85, 0.60 * turn_mod))
        action = 'bet' if freq >= 0.50 else 'check_call'
        reason = f'Value hand: {"double barrel" if action == "bet" else "check-call"} turn.'
    elif hand_rank >= 3 and turn_mod >= 1.0:
        freq = max(0.20, min(0.60, 0.40 * turn_mod))
        action = 'bet' if freq >= 0.45 else 'check_fold'
        reason = f'Semi-bluff: {"second barrel" if action == "bet" else "give up"} with turn {turn_mod:.1f}x.'
    else:
        freq = max(0.05, 0.25 * turn_mod)
        action = 'check_fold'
        reason = f'Weak hand: check and fold to villain bet on most turns.'
    return action, round(freq, 2), reason


def _seq2_advice(
    hand_rank: int, turn_mod: float, villain_af: float, hero_equity: float,
) -> tuple:
    """villain_bet_hero_called: hero check-called flop."""
    # Hero showed weakness by check-calling, villain showed strength
    if hand_rank >= 7:
        freq = 0.50 * turn_mod
        action = 'bet' if freq >= 0.40 else 'check_call'
        reason = f'Strong hand after check-call: {"lead probe" if action == "bet" else "check-call"}.'
    elif hand_rank >= 4 and hero_equity >= 0.45:
        # Consider probe bet if villain is passive
        if villain_af < 1.5:
            freq = 0.45 * turn_mod
            action = 'bet' if freq >= 0.40 else 'check_call'
            reason = f'Probe bet vs passive villain (AF={villain_af:.1f}): they may check back without a strong hand.'
        else:
            action = 'check_call'
            freq = 0.75
            reason = f'Top pair vs aggressive villain: check-call, do not lead into strength.'
    elif hero_equity >= 0.35:
        action = 'check_call'
        freq = 0.60
        reason = f'Marginal equity ({hero_equity:.0%}): check-call if villain bets reasonable size.'
    else:
        action = 'check_fold'
        freq = 0.85
        reason = f'Low equity ({hero_equity:.0%}) after check-calling flop: give up on turn.'
    return action, round(freq, 2), reason


def _seq3_advice(
    hand_rank: int, turn_mod: float, hero_has_draw: bool, hero_equity: float,
) -> tuple:
    """both_checked: both hero and villain checked flop."""
    # No one showed strength on flop; OOP hero can lead turn as probe
    if hand_rank >= 7:
        action = 'bet'
        freq = 0.75 * turn_mod
        reason = f'Strong hand: lead turn after both checked flop. Build pot now.'
    elif hand_rank >= 4 or hero_has_draw:
        action = 'bet'
        freq = max(0.35, min(0.70, 0.55 * turn_mod))
        reason = f'Value/draw: lead turn probe. Neither player showed strength on flop.'
    elif hero_equity >= 0.35:
        action = 'check_call'
        freq = 0.65
        reason = f'Marginal hand: check and call a bet from IP villain on turn.'
    else:
        action = 'check_fold'
        freq = 0.80
        reason = f'Weak hand: check and fold to any turn bet from villain.'
    return action, round(max(0.05, min(0.95, freq)), 2), reason


def _seq4_advice(hand_rank: int) -> tuple:
    """hero_bet_villain_raised_hero_called: hero bet, villain raised, hero called."""
    # Villain showed significant strength by raising; OOP hero is now wide-ranged with caution
    if hand_rank >= 9:  # set+
        action = 'check_raise'
        freq = 0.70
        reason = f'Nutted hand (rank={hand_rank}): check to induce villain barrel, then raise.'
    elif hand_rank >= 6:  # two_pair, overpair
        action = 'check_call'
        freq = 0.80
        reason = f'Strong but not nuts: check-call. Villain raised flop → strong range.'
    elif hand_rank >= 4:  # top pair
        action = 'check_call'
        freq = 0.55
        reason = f'Top pair: check-call but be prepared to fold to large bets. Villain showed strength.'
    else:
        action = 'check_fold'
        freq = 0.90
        reason = f'Weak hand: check and fold. Cannot call second barrel vs villain who raised flop.'
    return action, round(freq, 2), reason


def _bet_size_pct(
    action: str,
    hand_rank: int,
    board_type: str,
    spr: float,
    flop_sequence: str,
) -> float:
    """Recommended bet size as fraction of pot."""
    if action not in ('bet',):
        return 0.0
    # Base by hand rank
    if hand_rank >= 7:
        base = 0.65  # value: larger
    elif hand_rank >= 4:
        base = 0.55  # top pair: medium
    else:
        base = 0.50  # bluff/probe: medium-small

    # Wet boards: larger (protect, charge draws)
    if board_type == 'wet':
        base += 0.10
    elif board_type == 'dry':
        base -= 0.05

    # Low SPR: smaller (don't overbet thin)
    if spr < 2.5:
        base -= 0.10

    # Probe after check-through: smaller (information bet)
    if flop_sequence == 'both_checked':
        base -= 0.05

    return round(min(0.85, max(0.30, base)), 2)


@dataclass
class OopTurnAdvice:
    """Advice for OOP player first to act on the turn."""
    flop_sequence: str      # 'hero_bet_called', 'villain_bet_hero_called', 'both_checked', 'hero_bet_villain_raised_hero_called'
    hero_hand_class: str
    turn_card_type: str     # 'blank', 'hero_hits', 'scare', 'draw_completes', 'board_pairs'
    hero_equity: float
    spr: float
    villain_af: float
    board_type: str
    hero_has_draw: bool
    pot_bb: float

    # Decision
    action: str             # 'bet', 'check_call', 'check_fold', 'check_raise'
    action_frequency: float # frequency to take this action
    bet_size_pct: float     # if action == 'bet'
    bet_size_bb: float      # actual BB amount

    # Card effect
    turn_card_modifier: float

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_oop_turn(
    flop_sequence: str = 'hero_bet_called',
    hero_hand_class: str = 'top_pair',
    turn_card_type: str = 'blank',
    hero_equity: float = 0.60,
    spr: float = 3.5,
    villain_af: float = 2.0,
    villain_cbet_pct: float = 0.55,
    board_type: str = 'medium',
    hero_has_draw: bool = False,
    pot_bb: float = 20.0,
) -> OopTurnAdvice:
    """
    Advise OOP hero's turn action (first to act).

    Args:
        flop_sequence:    What happened on the flop:
                          'hero_bet_called'                      — hero bet, villain called
                          'villain_bet_hero_called'              — villain bet, hero called
                          'both_checked'                         — both checked through
                          'hero_bet_villain_raised_hero_called'  — hero bet, villain raised, hero called
        hero_hand_class:  Hero's hand strength
        turn_card_type:   Type of turn card: 'blank','hero_hits','scare','draw_completes','board_pairs'
        hero_equity:      Current equity
        spr:              Stack-to-pot ratio
        villain_af:       Villain's aggression factor
        villain_cbet_pct: Villain's c-bet frequency
        board_type:       'dry', 'medium', 'wet'
        hero_has_draw:    True if hero has a draw component
        pot_bb:           Pot size in BB

    Returns:
        OopTurnAdvice
    """
    rank = _hand_rank(hero_hand_class)
    turn_mod = _turn_card_modifier(turn_card_type, hero_has_draw, rank)

    # Dispatch by flop sequence
    if flop_sequence == 'hero_bet_called':
        action, freq, reason = _seq1_advice(rank, turn_mod, villain_af, spr)
    elif flop_sequence == 'villain_bet_hero_called':
        action, freq, reason = _seq2_advice(rank, turn_mod, villain_af, hero_equity)
    elif flop_sequence == 'both_checked':
        action, freq, reason = _seq3_advice(rank, turn_mod, hero_has_draw, hero_equity)
    elif flop_sequence == 'hero_bet_villain_raised_hero_called':
        action, freq, reason = _seq4_advice(rank)
    else:
        action, freq, reason = 'check_call', 0.60, f'Unknown sequence: default to check-call.'

    bet_pct = _bet_size_pct(action, rank, board_type, spr, flop_sequence)
    bet_bb = round(pot_bb * bet_pct, 1) if action == 'bet' else 0.0

    # Tips
    tips = []
    if turn_card_type == 'scare' and action in ('bet', 'check_call'):
        tips.append(
            'Scare card turn: villain may also have slowplayed a strong hand. '
            'Bet only with hands that can comfortably call a raise. '
            'Check marginal hands; do not bet-fold mediocre holdings.'
        )
    if flop_sequence == 'villain_bet_hero_called' and villain_af < 1.5:
        tips.append(
            f'Passive villain (AF={villain_af:.1f}): they checked turn means weakness. '
            f'Probe bet is productive — they rarely raise without strong hands. '
            f'Size: {bet_pct:.0%} pot to get calls from weak pairs and draws.'
        )
    if flop_sequence == 'hero_bet_villain_raised_hero_called':
        tips.append(
            'You called villain\'s flop raise: villain showed significant strength. '
            'Your range is capped at medium-strength hands (you\'d have 4-bet premium). '
            'Check and let villain take the lead — your main goal is to get to showdown cheaply.'
        )
    if flop_sequence == 'both_checked' and rank >= 4:
        tips.append(
            'Both checked flop: neither player\'s range is defined. '
            'OOP lead is strong here — you have same range advantage as PFR. '
            f'Size: {bet_pct:.0%} pot (standard probe size to deny equity cheaply).'
        )
    if spr < 2.5 and action == 'bet':
        tips.append(
            f'Low SPR ({spr:.1f}): betting means near-commitment. '
            'Be prepared to call off vs a raise. Only bet if comfortable stacking off.'
        )
    if not tips:
        tips.append(
            f'{flop_sequence.replace("_", " ").title()}: '
            f'{action.replace("_", " ")} {freq:.0%} of the time. '
            f'Turn card ({turn_card_type}) {"helps" if turn_mod >= 1.0 else "hurts"} betting frequency.'
        )

    return OopTurnAdvice(
        flop_sequence=flop_sequence,
        hero_hand_class=hero_hand_class,
        turn_card_type=turn_card_type,
        hero_equity=round(hero_equity, 3),
        spr=round(spr, 2),
        villain_af=round(villain_af, 2),
        board_type=board_type,
        hero_has_draw=hero_has_draw,
        pot_bb=round(pot_bb, 1),
        action=action,
        action_frequency=freq,
        bet_size_pct=bet_pct,
        bet_size_bb=bet_bb,
        turn_card_modifier=round(turn_mod, 2),
        reasoning=reason,
        tips=tips,
    )


def oop_turn_one_liner(result: OopTurnAdvice) -> str:
    seq_short = result.flop_sequence[:8]
    size_str = f'{result.bet_size_pct:.0%}pot' if result.action == 'bet' else 'no_bet'
    return (
        f'[OOP-T {seq_short}|{result.turn_card_type[:5]}] '
        f'{result.action.upper()} {result.action_frequency:.0%} | '
        f'{size_str} | '
        f'eq={result.hero_equity:.0%} SPR={result.spr:.1f} AF={result.villain_af:.1f}'
    )
