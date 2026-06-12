"""
Turn Barrel Advisor (turn_barrel_advisor.py)

After hero c-bets the flop and villain calls, analyzes whether to fire
a second barrel on the turn. Accounts for:
  - Turn card quality for hero's range vs villain's perceived calling range
  - Villain's response tendencies on the turn
  - Board run-out: scare cards, draw completions, blanks
  - SPR and equity required to justify a turn barrel

Usage:
    from poker.turn_barrel_advisor import analyze_turn_barrel, TurnBarrelResult
    result = analyze_turn_barrel(
        hero_equity=0.62,
        pot_bb=18.0,
        eff_stack_bb=80.0,
        villain_fold_to_barrel=0.45,
        turn_card_rank='A',
        board_had_draw=True,
        draw_completed=False,
        hero_pos='BTN',
        in_position=True,
    )
    print(result.action, result.barrel_size_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


_RANK_ORDER = '23456789TJQKA'


def _rank_index(rank: str) -> int:
    """Return 0-12 rank index. Unknown = 6 (mid)."""
    r = rank.strip().upper()
    return _RANK_ORDER.index(r) if r in _RANK_ORDER else 6


def _classify_turn_card(
    turn_card_rank: str,
    board_had_draw: bool,
    draw_completed: bool,
    hero_range_advantage: float,
) -> str:
    """
    Return 'blank', 'scare_good', 'scare_bad', 'draw_complete'.

    scare_good : card that improves hero's perceived range more than villain's
    scare_bad  : overcard / draw completion that helps villain's perceived range
    blank      : irrelevant card that doesn't change relative strengths
    draw_complete: draw completes — villain may have hit; hero's bluffs are hurt
    """
    if draw_completed:
        return 'draw_complete'

    ridx = _rank_index(turn_card_rank)

    # Ace on turn when hero is PFR: generally good (hero has more aces)
    if ridx == 12:
        return 'scare_good' if hero_range_advantage > 0.0 else 'scare_bad'

    # King: also generally favors preflop aggressor
    if ridx == 11:
        return 'scare_good'

    # Low blanks (2-7): almost always blank
    if ridx <= 5:
        return 'blank'

    # Mid cards: depends on draw board
    if board_had_draw and ridx in (6, 7, 8, 9):
        return 'scare_bad'

    return 'blank'


@dataclass
class TurnBarrelResult:
    """Full turn-barrel analysis."""
    # Context
    hero_equity: float
    pot_bb: float
    eff_stack_bb: float
    spr: float
    in_position: bool

    # Turn card assessment
    turn_card_rank: str
    turn_card_quality: str      # 'blank', 'scare_good', 'scare_bad', 'draw_complete'
    turn_card_is_good: bool     # good for hero's range

    # Barrel sizing
    barrel_size_bb: float
    barrel_size_pct: float      # fraction of pot

    # EV
    ev_barrel: float
    ev_check: float

    # Decision
    action: str                 # 'barrel', 'check-call', 'check-fold'
    barrel_type: str            # 'value', 'semi-bluff', 'bluff', 'give-up'

    # Villain info
    villain_fold_to_barrel: float
    board_had_draw: bool
    draw_completed: bool

    # Reasoning
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_turn_barrel(
    hero_equity: float,
    pot_bb: float,
    eff_stack_bb: float,
    villain_fold_to_barrel: float = 0.45,
    turn_card_rank: str = '7',
    board_had_draw: bool = False,
    draw_completed: bool = False,
    hero_pos: str = 'BTN',
    in_position: bool = True,
    hero_range_advantage: float = 0.15,
    villain_af: float = 1.5,
    has_draw: bool = False,
    flop_cbet_size_pct: float = 0.50,
) -> TurnBarrelResult:
    """
    Analyze whether to fire a second barrel on the turn after villain calls
    hero's flop c-bet.

    Args:
        hero_equity:            Hero's equity vs villain's perceived turn range (0-1)
        pot_bb:                 Pot on the turn (after flop action)
        eff_stack_bb:           Effective stack remaining
        villain_fold_to_barrel: Villain's frequency of folding to turn barrels (0-1)
        turn_card_rank:         Rank of the turn card ('A','K','Q','J','T','9',...,'2')
        board_had_draw:         True if flop had a flush/straight draw present
        draw_completed:         True if turn completes a major draw
        hero_pos:               Hero's position ('UTG','HJ','CO','BTN','SB','BB')
        in_position:            Hero acts after villain on the turn
        hero_range_advantage:   How much hero's range benefits from this run-out (−1 to +1)
        villain_af:             Villain aggression factor (passive=1, aggro=3+)
        has_draw:               True if hero personally has a draw (flush/straight)
        flop_cbet_size_pct:     What fraction of pot hero bet on flop (for sizing context)

    Returns:
        TurnBarrelResult
    """
    spr = eff_stack_bb / pot_bb if pot_bb > 0 else 99.0

    # ── Turn card quality ────────────────────────────────────────────────────
    card_quality = _classify_turn_card(
        turn_card_rank, board_had_draw, draw_completed, hero_range_advantage
    )
    card_is_good = card_quality in ('scare_good', 'blank')

    # ── Barrel type classification ────────────────────────────────────────────
    value_threshold = 0.58
    # Semi-bluff: has equity + fold equity
    semi_threshold = 0.35

    if hero_equity >= value_threshold:
        barrel_type = 'value'
    elif hero_equity >= semi_threshold and (has_draw or villain_fold_to_barrel > 0.45):
        barrel_type = 'semi-bluff'
    elif hero_equity < semi_threshold and villain_fold_to_barrel > 0.55 and card_is_good:
        barrel_type = 'bluff'
    else:
        barrel_type = 'give-up'

    # Scare-bad turn: reduce willingness to barrel air/semi
    if card_quality == 'draw_complete':
        if barrel_type in ('bluff', 'semi-bluff') and not has_draw:
            barrel_type = 'give-up'
    elif card_quality == 'scare_bad':
        if barrel_type == 'bluff':
            barrel_type = 'give-up'

    # Good scare card: we can bluff more profitably
    if card_quality == 'scare_good' and barrel_type == 'give-up':
        if villain_fold_to_barrel > 0.50:
            barrel_type = 'bluff'

    # ── Barrel sizing ─────────────────────────────────────────────────────────
    # Turn barrels: typically 60-75% pot
    # Value: larger; bluff: can go smaller (more fold equity per $)
    if barrel_type == 'value':
        size_pct = 0.70 + (hero_equity - value_threshold) * 0.5
    elif barrel_type == 'semi-bluff':
        size_pct = 0.60 + (0.1 if has_draw else 0)
    elif barrel_type == 'bluff':
        size_pct = 0.55 + (0.1 if card_quality == 'scare_good' else 0)
    else:
        size_pct = 0.60    # default (unused; won't barrel give-up)

    size_pct = min(1.00, max(0.40, size_pct))
    barrel_size = pot_bb * size_pct
    barrel_size = min(barrel_size, eff_stack_bb * 0.75)   # don't over-commit

    # ── EV calculations ───────────────────────────────────────────────────────
    total_pot_if_call = pot_bb + barrel_size

    ev_if_fold = pot_bb   # hero wins pot
    ev_if_call = hero_equity * total_pot_if_call - (1 - hero_equity) * barrel_size

    ev_barrel = (villain_fold_to_barrel * ev_if_fold
                 + (1 - villain_fold_to_barrel) * ev_if_call)

    # EV of checking: passive but retains equity
    # IP check: hero often gets showdown or fires river; OOP check gives free card
    check_realisation = 0.85 if in_position else 0.65
    ev_check = hero_equity * pot_bb * check_realisation

    # ── Action decision ──────────────────────────────────────────────────────
    if barrel_type == 'give-up':
        action = 'check-fold' if hero_equity < 0.25 else 'check-call'
    elif ev_barrel > ev_check:
        action = 'barrel'
    elif barrel_type == 'value':
        action = 'barrel'    # always barrel value even if EV close
    else:
        action = 'check-call' if hero_equity >= 0.35 else 'check-fold'

    # Passive villain: donk bets with strong hands — be more cautious if villain_af < 1.0
    if villain_af < 1.0 and action == 'barrel' and barrel_type == 'bluff':
        action = 'check-fold'

    # ── Tips ──────────────────────────────────────────────────────────────────
    tips = []
    if card_quality == 'scare_good':
        tips.append(
            f'{turn_card_rank} on the turn is a great scare card for the PFR. '
            f'Villain\'s flat-call range is capped — barrel aggressively.'
        )
    if card_quality == 'draw_complete':
        tips.append(
            'Draw completed. If villain check-raises, give up unless you have nut draw. '
            'Value hands should still bet; bluffs should check-fold.'
        )
    if board_had_draw and not draw_completed and barrel_type == 'semi-bluff':
        tips.append(
            'Draw still live on turn — barrel to charge villain and protect equity.'
        )
    if spr < 3 and hero_equity > 0.55:
        tips.append(
            f'SPR={spr:.1f}: consider shoving turn to deny equity and commit stacks with {hero_equity:.0%} equity.'
        )
    if not in_position and barrel_type == 'bluff':
        tips.append(
            'OOP bluff barrel: risky. Villain can float or raise. '
            'Reduce bluff frequency unless villain is very fold-prone.'
        )
    if villain_fold_to_barrel > 0.60:
        tips.append(
            f'Villain folds to turn barrels {villain_fold_to_barrel:.0%} — profitable spot to fire wide.'
        )
    if not tips:
        tips.append(
            f'Turn barrel: {barrel_type}. Use {size_pct:.0%} pot sizing. '
            f'EV(barrel)={ev_barrel:+.2f} vs EV(check)={ev_check:+.2f}.'
        )

    reasoning = (
        f'Turn [{turn_card_rank}] ({card_quality}). '
        f'equity={hero_equity:.0%} fold_eq={villain_fold_to_barrel:.0%}. '
        f'Barrel {barrel_size:.1f}BB ({size_pct:.0%} pot) — type: {barrel_type}. '
        f'EV(barrel)={ev_barrel:+.2f} vs EV(check)={ev_check:+.2f}. '
        f'Action: {action.upper()}.'
    )

    return TurnBarrelResult(
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        eff_stack_bb=eff_stack_bb,
        spr=round(spr, 2),
        in_position=in_position,
        turn_card_rank=turn_card_rank,
        turn_card_quality=card_quality,
        turn_card_is_good=card_is_good,
        barrel_size_bb=round(barrel_size, 1),
        barrel_size_pct=round(size_pct, 2),
        ev_barrel=round(ev_barrel, 2),
        ev_check=round(ev_check, 2),
        action=action,
        barrel_type=barrel_type,
        villain_fold_to_barrel=villain_fold_to_barrel,
        board_had_draw=board_had_draw,
        draw_completed=draw_completed,
        reasoning=reasoning,
        tips=tips,
    )


def turn_barrel_one_liner(result: TurnBarrelResult) -> str:
    """Single-line overlay summary."""
    return (
        f'Turn [{result.turn_card_rank}] {result.turn_card_quality}: '
        f'{result.action.upper()} [{result.barrel_type}] {result.barrel_size_bb:.1f}BB | '
        f'EV={result.ev_barrel:+.2f} vs check={result.ev_check:+.2f}'
    )
