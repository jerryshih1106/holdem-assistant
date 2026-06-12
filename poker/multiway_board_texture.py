"""
Multiway Board Texture Advisor (multiway_board_texture.py)

In multiway pots (3+ players), board texture has dramatically different
strategic implications vs heads-up:

Key differences from heads-up:
  1. Fold equity is much lower — need ALL other players to fold, not just one
  2. Value hands need protection more urgently (more players = more draws)
  3. Bluffing frequency drops to near-zero vs 2+ callers
  4. Bet sizing should DECREASE (smaller size targets multiple callers)
  5. Range advantage matters less — at least one player hits every board

C-bet frequency by board and n_players:
  - Dry boards (A72r): HU=75%, 3-way=40%, 4-way=15%
  - Medium boards (JT5 two-tone): HU=55%, 3-way=25%, 4-way=8%
  - Wet boards (987 two-tone): HU=35%, 3-way=10%, 4-way=0%
  - Monotone (all same suit): HU=30%, 3-way=5%, 4-way=0%

Protection needs in multiway:
  - Top pair + draw: MUST bet to deny equity to multiple draws
  - Two pair: bet medium sizing to build pot and protect
  - Flush draw only: often better to check (can't fold everyone)
  - Sets: can check once (range too strong, price villain for turn)

Bet sizing in multiway:
  - Smaller than HU (33% instead of 50-66% pot)
  - Bigger than HU when protecting (charge multiple draws)
  - Never large (1.0x pot+) unless multi-player pot AND nutted hand

Usage:
    from poker.multiway_board_texture import analyze_multiway_texture, MultiwayTexture
    result = analyze_multiway_texture(
        n_players=3,
        board_type='medium',
        hero_hand_class='top_pair',
        hero_equity=0.55,
        hero_pos='IP',
        n_draw_threats=2,
    )
    print(result.should_cbet, result.cbet_size_pct)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'trash': 0,
        'draw': 1, 'speculative': 1, 'backdoor': 1,
        'bottom_pair': 2, 'marginal': 2,
        'middle_pair': 3,
        'top_pair': 4, 'tptk': 5,
        'overpair': 6,
        'two_pair': 7,
        'set': 8, 'flush': 8, 'straight': 8,
        'premium': 9, 'flush_draw_strong': 3,
    }.get(hand_class.lower(), 4)


# Base c-bet frequency: (board_type, n_players) → gto_freq
_CBET_FREQ = {
    'dry':      {2: 0.75, 3: 0.40, 4: 0.15, 5: 0.05},
    'medium':   {2: 0.55, 3: 0.25, 4: 0.08, 5: 0.02},
    'wet':      {2: 0.35, 3: 0.10, 4: 0.02, 5: 0.00},
    'paired':   {2: 0.60, 3: 0.35, 4: 0.12, 5: 0.04},
    'monotone': {2: 0.30, 3: 0.05, 4: 0.00, 5: 0.00},
    'connected':{2: 0.40, 3: 0.15, 4: 0.05, 5: 0.00},
}


def _base_cbet_freq(board_type: str, n_players: int) -> float:
    n = min(5, max(2, n_players))
    tbl = _CBET_FREQ.get(board_type, _CBET_FREQ['medium'])
    return tbl.get(n, tbl.get(min(tbl), 0.0))


def _cbet_size_pct(board_type: str, n_players: int, hero_needs_protection: bool) -> float:
    """Optimal c-bet size as fraction of pot for multiway situations."""
    # Base: smaller in multiway (targeting multiple callers)
    if n_players == 2:
        base = 0.55
    elif n_players == 3:
        base = 0.40
    else:
        base = 0.33

    # Protection needs demand larger sizing
    if hero_needs_protection:
        base += 0.15

    # Wet/connected: size up (charge draws)
    if board_type in ('wet', 'connected'):
        base += 0.10
    elif board_type == 'dry':
        base -= 0.07

    return round(min(0.85, max(0.25, base)), 2)


def _needs_protection(hand_rank: int, board_type: str,
                      n_draw_threats: int, n_players: int) -> bool:
    """Does hero need to charge the draws in a multiway pot?"""
    if n_players < 3:
        return False
    # Two pair or better with draws on board: must protect
    if hand_rank >= 7 and n_draw_threats >= 1:
        return True
    # Top pair or overpair on wet/connected boards with multiple opponents
    if hand_rank >= 4 and board_type in ('wet', 'connected') and n_draw_threats >= 2:
        return True
    return False


def _can_bluff(board_type: str, n_players: int, hero_equity: float) -> bool:
    """Is a pure bluff viable in this multiway situation?"""
    if n_players >= 4:
        return False  # Too many players, fold equity near zero
    if n_players == 3:
        # Only on dry boards with very high fold equity
        return board_type == 'dry' and hero_equity < 0.15
    return hero_equity < 0.20  # HU bluff threshold


def _fold_equity_estimate(n_players: int, board_type: str) -> float:
    """P(all other players fold to a standard c-bet)."""
    per_player = {
        'dry': 0.60, 'medium': 0.45, 'wet': 0.30,
        'paired': 0.55, 'monotone': 0.25, 'connected': 0.35,
    }.get(board_type, 0.40)
    # P(all fold) = per_player ^ (n_players - 1)
    return round(per_player ** (n_players - 1), 3)


def _multiway_adjustments(n_players: int, board_type: str,
                          hand_rank: int) -> List[str]:
    """Key strategic adjustments for multiway play."""
    adj = []
    if n_players >= 3:
        adj.append(
            f'{n_players}-way pot: reduce bluffing frequency sharply. '
            f'Need all {n_players-1} opponents to fold — fold equity ~'
            f'{_fold_equity_estimate(n_players, board_type):.0%}.'
        )
    if board_type in ('wet', 'connected') and n_players >= 3:
        adj.append(
            'Wet board multiway: your value hands are MORE vulnerable. '
            'At least one player likely has a draw. Size up to protect.'
        )
    if board_type == 'dry' and n_players == 3:
        adj.append(
            'Dry board 3-way: c-bet frequency drops from 75% to 40%. '
            'Range becomes more polarized (strong value + air, no medium hands).'
        )
    if hand_rank >= 8:  # set or better
        adj.append(
            'Monster hand multiway: consider CHECK to induce bets. '
            'Multiple players = more chance someone will bet or call a second barrel.'
        )
    if hand_rank in (4, 5, 6):  # top pair / overpair
        adj.append(
            'One pair multiway: your hand has LESS relative strength. '
            'At least one player is statistically ahead or drawing strongly.'
        )
    return adj


@dataclass
class MultiwayTexture:
    """Multiway board texture analysis."""
    n_players: int
    board_type: str
    hero_hand_class: str
    hero_equity: float
    hero_pos: str

    # C-bet analysis
    should_cbet: bool
    cbet_freq: float
    cbet_size_pct: float
    fold_equity: float           # P(all fold to c-bet)

    # Protection
    needs_protection: bool
    protection_size_pct: float

    # Bluffing
    can_bluff: bool
    bluff_freq: float            # recommended bluff frequency (usually 0 in multiway)

    # Range dynamics
    value_hands_needed: str      # what hand class to bet for value
    check_trap_option: bool      # is check-trapping viable?

    # Notes
    adjustments: List[str] = field(default_factory=list)
    reasoning: str = ''


def analyze_multiway_texture(
    n_players: int = 3,
    board_type: str = 'medium',
    hero_hand_class: str = 'top_pair',
    hero_equity: float = 0.55,
    hero_pos: str = 'IP',
    n_draw_threats: int = 1,
    hero_was_pfr: bool = True,
) -> MultiwayTexture:
    """
    Analyze board texture adjustments for multiway pots.

    Args:
        n_players:         Total players in pot (including hero)
        board_type:        'dry', 'medium', 'wet', 'paired', 'monotone', 'connected'
        hero_hand_class:   Hero's hand classification
        hero_equity:       Hero's equity vs the field
        hero_pos:          'IP' or 'OOP'
        n_draw_threats:    Number of obvious draw possibilities on board
        hero_was_pfr:      Hero was the preflop raiser

    Returns:
        MultiwayTexture
    """
    rank = _hand_rank(hero_hand_class)
    base_freq = _base_cbet_freq(board_type, n_players)
    protect = _needs_protection(rank, board_type, n_draw_threats, n_players)
    fold_eq = _fold_equity_estimate(n_players, board_type)
    bluff_ok = _can_bluff(board_type, n_players, hero_equity)

    # IP gets small boost
    ip_adj = 0.05 if hero_pos == 'IP' else -0.05
    if not hero_was_pfr:
        base_freq *= 0.60  # non-PFR cbets less often

    cbet_freq = round(min(1.0, base_freq + ip_adj), 3)

    # Decision
    if rank == 0 and not bluff_ok:
        should_cbet = False
        cbet_freq = 0.0
    elif rank >= 7 and n_players >= 3:
        # Strong hands: mix between bet and check-trap
        should_cbet = True
        cbet_freq = round(cbet_freq * 0.75, 3)  # check some for trapping
    else:
        should_cbet = cbet_freq >= 0.15

    size_pct = _cbet_size_pct(board_type, n_players, protect)
    prot_size = _cbet_size_pct(board_type, n_players, True) if protect else size_pct

    # Value hand minimum for betting
    if n_players >= 4:
        value_min = 'two_pair+'
    elif n_players == 3:
        value_min = 'top_pair_good_kicker+'
    else:
        value_min = 'any_value'

    check_trap = rank >= 8 and n_players >= 3  # monsters benefit from trapping

    bluff_freq = 0.0
    if bluff_ok:
        # Pure bluffs: only on dry boards with good blockers
        bluff_freq = min(0.15, fold_eq * 0.20)

    adjustments = _multiway_adjustments(n_players, board_type, rank)

    reasoning = (
        f'{n_players}-way pot, {board_type} board. '
        f'C-bet freq: {cbet_freq:.0%} ({size_pct:.0%}pot). '
        f'Fold equity: {fold_eq:.0%}. '
    )
    if protect:
        reasoning += f'Protection needed — size up to {prot_size:.0%}pot. '
    if not should_cbet and rank > 0:
        reasoning += 'Check and re-evaluate based on action.'
    elif not should_cbet:
        reasoning += 'Check and give up (bluffing not viable).'

    return MultiwayTexture(
        n_players=n_players,
        board_type=board_type,
        hero_hand_class=hero_hand_class,
        hero_equity=round(hero_equity, 3),
        hero_pos=hero_pos,
        should_cbet=should_cbet,
        cbet_freq=cbet_freq,
        cbet_size_pct=size_pct,
        fold_equity=fold_eq,
        needs_protection=protect,
        protection_size_pct=prot_size,
        can_bluff=bluff_ok,
        bluff_freq=bluff_freq,
        value_hands_needed=value_min,
        check_trap_option=check_trap,
        adjustments=adjustments,
        reasoning=reasoning,
    )


def multiway_texture_one_liner(result: MultiwayTexture) -> str:
    action = 'CBET' if result.should_cbet else 'CHECK'
    return (
        f'[MW {result.n_players}way {result.board_type}] {action} '
        f'{result.cbet_freq:.0%} | size={result.cbet_size_pct:.0%}pot | '
        f'fold_eq={result.fold_equity:.0%} | '
        f'{"PROTECT" if result.needs_protection else "no_prot"}'
    )
