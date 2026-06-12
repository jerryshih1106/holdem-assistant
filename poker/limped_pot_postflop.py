"""
Limped Pot Postflop Advisor (limped_pot_postflop.py)

A limped pot occurs when all players call the big blind preflop (no one raises).
This creates fundamentally different postflop dynamics compared to raised pots:

KEY DIFFERENCES from raised pots:
  1. No range advantage: No one is the "aggressor" with a defined preflop range.
     All players can have any hand from 22 to AA (since premiums might slow-play).
     This makes betting for protection/fold-equity LESS effective.

  2. Ranges are capped AND uncapped: Limp-callers can have strong hands (traps)
     AND weak hands (recreational players with any two cards).
     You can't assume limpers are weak just because they didn't raise.

  3. Value sizing is smaller: Because ranges overlap heavily, betting large
     forces out exactly the hands you WANT to get value from (worse hands that
     call small bets). In limped pots: 25-40% pot is standard for value.

  4. Bluffing is less effective: Multiple wide-range opponents = someone
     likely has a piece of the board. Need stronger reasons to bluff.

  5. Board texture matters more for hand reading: On low boards in limped pots,
     everyone is connected. On high boards, Aces/Kings are live for everyone.

  6. Position value increases: IP player has massive advantage in limped pots
     because they act last with unclear initiative.

Decision framework:
  Hero in BB (checked option):
    Good hand (top pair+): Bet 25-40% pot for value (fish call; tight players fold to big bets)
    Draw: Check-call or small bet depending on position
    Air: Check and fold to bets; bluffing into multiple limpers = -EV

  Hero as BTN/CO limper:
    Strong: Bet OOP small, or raise limpers' bets as 2-3x
    Marginal: Check back and control pot
    Draw: Semi-bluff small or check

  Multiway considerations:
    Each additional opponent reduces optimal bet frequency
    Value hands need larger "winning" share to justify betting
    3+ opponents: only bet hands that are likely best AND benefit from protection

Bet sizing guide for limped pots:
  Dry board: 25-35% pot (villain has weak made hands that call small)
  Medium board: 30-40% pot
  Wet board: 40-55% pot (charge draws; protect value hands)
  Sets/two pair on any: 40-60% pot (build pot; don't slow-play in multiway)

Usage:
    from poker.limped_pot_postflop import advise_limped_pot
    from poker.limped_pot_postflop import LimpedPotAdvice, limped_pot_one_liner

    result = advise_limped_pot(
        hero_hand_class='top_pair',
        board_type='medium',
        hero_pos='IP',
        hero_equity=0.65,
        n_opponents=2,
        street='flop',
        pot_bb=8.0,
        hero_stack_bb=100.0,
        villain_vpip=0.45,
        has_draws_on_board=True,
    )
    print(result.action, result.recommended_bet_pct)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'trash': 0, 'bottom_pair': 2, 'marginal': 2,
        'middle_pair': 3, 'draw': 3, 'speculative': 2,
        'top_pair': 4, 'medium': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'strong': 7,
        'set': 9, 'straight': 8, 'flush': 8, 'premium': 9,
        'full_house': 10, 'quads': 10, 'nuts': 10,
    }.get(hand_class.lower(), 4)


def _base_bet_pct(
    board_type: str,
    hand_rank: int,
    has_draws: bool,
    n_opponents: int,
) -> float:
    """
    Base bet size for limped pot. Smaller than raised pot sizing throughout.
    """
    # Start with board-type base
    if board_type == 'wet' or has_draws:
        base = 0.45
    elif board_type == 'medium':
        base = 0.35
    else:
        base = 0.28  # dry: very small for value

    # Strong hands: slightly larger (build pot)
    if hand_rank >= 7:
        base += 0.08
    elif hand_rank >= 5:
        base += 0.03

    # More opponents: keep bet small (more callers, need more callers to fold)
    if n_opponents >= 3:
        base -= 0.05
    elif n_opponents >= 2:
        base -= 0.02

    return round(min(0.65, max(0.22, base)), 2)


def _bet_frequency(
    hand_rank: int,
    n_opponents: int,
    hero_pos: str,
    hero_equity: float,
    board_type: str,
) -> float:
    """
    How often to bet (0-1). Limped pots require lower bet frequency
    than raised pots due to range overlap and multiway dynamics.
    """
    # Strong hands: always bet
    if hand_rank >= 7:
        freq = 0.90
    elif hand_rank >= 5:
        freq = 0.75   # TPTK/overpair: bet often
    elif hand_rank == 4:
        freq = 0.60   # Top pair: bet most of the time
    elif hand_rank == 3:
        freq = 0.35   # Middle pair: mixed (pot control)
    else:
        freq = 0.10   # Weak hands: rarely bet

    # Position bonus: IP bets more
    if hero_pos == 'IP':
        freq += 0.08
    elif hero_pos == 'OOP':
        freq -= 0.10

    # More opponents: bet less often
    if n_opponents >= 3:
        freq -= 0.15
    elif n_opponents >= 2:
        freq -= 0.08

    # High equity: bet more
    if hero_equity >= 0.70:
        freq += 0.08
    elif hero_equity < 0.50:
        freq -= 0.10

    # Dry board: even value hands can check (pot control)
    if board_type == 'dry' and hand_rank <= 4:
        freq -= 0.10

    return round(min(0.95, max(0.05, freq)), 2)


def _action(
    bet_freq: float,
    hand_rank: int,
    hero_equity: float,
    n_opponents: int,
    street: str,
) -> str:
    """Primary action recommendation."""
    # River: no implied odds; pure showdown value
    if street == 'river':
        if hand_rank >= 5 and hero_equity >= 0.55:
            return 'bet'
        if hero_equity >= 0.40:
            return 'check_call'
        return 'check_fold'

    if bet_freq >= 0.55:
        return 'bet'
    if bet_freq >= 0.30:
        return 'mixed'  # bet some, check some
    if hand_rank >= 3 and hero_equity >= 0.38:
        return 'check_call'
    return 'check_fold'


def _raise_response_vs_limper_bet(
    hand_rank: int,
    n_opponents: int,
    hero_equity: float,
) -> str:
    """When a limper bets into us, how do we respond?"""
    if hand_rank >= 7:
        return 'raise_large'   # Set+: raise for value + isolation
    if hand_rank >= 5 and n_opponents <= 2:
        return 'call_or_raise'  # TPTK: call or raise depending on sizing
    if hero_equity >= 0.45:
        return 'call'
    return 'fold'


@dataclass
class LimpedPotAdvice:
    """Postflop advice for limped pots."""
    hero_hand_class: str
    board_type: str
    hero_pos: str
    hero_equity: float
    n_opponents: int
    street: str
    pot_bb: float
    hero_stack_bb: float
    villain_vpip: float
    has_draws_on_board: bool

    # Decision
    action: str              # 'bet', 'mixed', 'check_call', 'check_fold'
    recommended_bet_pct: float
    recommended_bet_bb: float
    bet_frequency: float     # how often to take this action (0-1)

    # vs incoming bet (if a limper bets first)
    vs_limper_bet: str       # 'raise_large', 'call_or_raise', 'call', 'fold'

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_limped_pot(
    hero_hand_class: str = 'top_pair',
    board_type: str = 'medium',
    hero_pos: str = 'IP',
    hero_equity: float = 0.65,
    n_opponents: int = 2,
    street: str = 'flop',
    pot_bb: float = 8.0,
    hero_stack_bb: float = 100.0,
    villain_vpip: float = 0.45,
    has_draws_on_board: bool = True,
) -> LimpedPotAdvice:
    """
    Advise postflop strategy in a limped pot.

    Args:
        hero_hand_class:  Hero's hand strength
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' or 'OOP'
        hero_equity:      Hero's equity vs opponents' collective range
        n_opponents:      Number of opponents in the pot
        street:           'flop', 'turn', 'river'
        pot_bb:           Current pot size in BB
        hero_stack_bb:    Hero's remaining stack in BB
        villain_vpip:     Villain(s) average VPIP
        has_draws_on_board: True if board has flush or straight draws

    Returns:
        LimpedPotAdvice
    """
    rank = _hand_rank(hero_hand_class)
    bet_pct = _base_bet_pct(board_type, rank, has_draws_on_board, n_opponents)
    freq = _bet_frequency(rank, n_opponents, hero_pos, hero_equity, board_type)
    action = _action(freq, rank, hero_equity, n_opponents, street)
    vs_bet = _raise_response_vs_limper_bet(rank, n_opponents, hero_equity)

    if action == 'bet':
        reason = (
            f'BET {bet_pct:.0%} pot ({pot_bb * bet_pct:.1f}BB): '
            f'{hero_hand_class} (rank={rank}) in {n_opponents}-way limped pot. '
            f'Bet freq={freq:.0%}. Smaller sizing than raised pot is optimal here.'
        )
    elif action == 'mixed':
        reason = (
            f'MIXED: bet {bet_pct:.0%} pot {freq:.0%} of time. '
            f'{hero_hand_class} is marginal for limped pot — '
            f'check more OOP or vs many opponents.'
        )
    elif action == 'check_call':
        reason = (
            f'CHECK-CALL: {hero_hand_class} has equity ({hero_equity:.0%}) '
            f'but limped pot dynamics suggest checking (not betting into {n_opponents} wide ranges). '
            f'Call if a limper bets.'
        )
    else:
        reason = (
            f'CHECK-FOLD: {hero_hand_class} lacks equity ({hero_equity:.0%}) to '
            f'profitably continue in {n_opponents}-way limped pot.'
        )

    # Tips
    tips = []
    tips.append(
        f'Limped pot sizing: use {bet_pct:.0%} pot (NOT the standard 50-75% from raised pots). '
        f'Fish call small bets and fold large bets — '
        f'small sizing extracts more value from recreational players.'
    )
    if n_opponents >= 3:
        tips.append(
            f'{n_opponents}-way pot: bet only top pair+ ({bet_pct:.0%} pot). '
            f'Bluffing into {n_opponents} wide ranges is -EV. '
            f'Someone always has a piece. Check-fold air and marginal hands.'
        )
    if rank >= 9:
        tips.append(
            f'Nutted hand (rank={rank}) in limped pot: '
            f'do NOT slow-play (opponents have wide ranges that connect with boards). '
            f'Bet {bet_pct:.0%} pot on all streets — let them call with top pair and pairs.'
        )
    if board_type == 'dry' and rank <= 4:
        tips.append(
            'Dry board + top pair in limped pot: can check for pot control. '
            'Everyone checked preflop → narrow range for villain (no preflop aggressor). '
            'Value bet small or check and call small bets from opponents.'
        )
    if villain_vpip > 0.50:
        tips.append(
            f'Fish table (VPIP={villain_vpip:.0%}): maximize value with small, frequent bets. '
            f'Recommended {bet_pct:.0%} pot every street. They will call with any pair. '
            f'Never bluff — they call down with bottom pair.'
        )
    if has_draws_on_board and rank >= 6:
        tips.append(
            f'Draws present + strong hand: bet {bet_pct:.0%} pot to charge draws. '
            f'In limped pots, opponents have draw-heavy ranges. '
            f'Protect your two pair/set by betting; free cards are costly.'
        )
    if not tips:
        tips.append(
            f'{action.upper()}: {hero_hand_class} on {board_type} board. '
            f'Bet {bet_pct:.0%} pot, freq={freq:.0%}. '
            f'Limped pot: smaller sizing, lower bluff frequency than raised pots.'
        )

    return LimpedPotAdvice(
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        hero_pos=hero_pos,
        hero_equity=round(hero_equity, 3),
        n_opponents=n_opponents,
        street=street,
        pot_bb=round(pot_bb, 1),
        hero_stack_bb=round(hero_stack_bb, 1),
        villain_vpip=round(villain_vpip, 3),
        has_draws_on_board=has_draws_on_board,
        action=action,
        recommended_bet_pct=bet_pct,
        recommended_bet_bb=round(pot_bb * bet_pct, 1),
        bet_frequency=freq,
        vs_limper_bet=vs_bet,
        reasoning=reason,
        tips=tips,
    )


def limped_pot_one_liner(result: LimpedPotAdvice) -> str:
    return (
        f'[LP {result.hero_hand_class}@{result.street}|{result.n_opponents}way] '
        f'{result.action.upper()} | '
        f'bet={result.recommended_bet_pct:.0%}pot({result.recommended_bet_bb:.1f}BB) '
        f'freq={result.bet_frequency:.0%} | '
        f'vs_bet={result.vs_limper_bet}'
    )
