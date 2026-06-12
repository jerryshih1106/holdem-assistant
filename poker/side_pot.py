"""
Side Pot Calculator (side_pot.py)

In live poker, when multiple players go all-in with different stack sizes,
the pot splits into a main pot and one or more side pots. Each pot is only
contested by players who contributed to it.

Rules:
  1. Main pot = smallest all-in bet * number of players who put in money
  2. First side pot = (2nd smallest - smallest) * (N-1 remaining players)
  3. Continue until all contributions are allocated

Why this matters for decision-making:
  - A short-stack going all-in for 20BB does NOT give a deep player pot
    odds on a side pot — that side pot is only between the two deep players
  - Hero may be correct to call a short-stack AI even with a weak hand
    because they're also building the side pot vs the medium stack
  - Hero can sometimes be correct to FOLD even getting 3:1 odds on the
    main pot if the side pot is large and hero's equity vs deep stack is poor

Example (6-max, 100BB stacks):
  Player A: all-in 15BB (short stack)
  Player B: all-in 45BB (medium stack)
  Player C (hero): full stack, deciding to call 45BB

  Main pot = 15 * 3 = 45BB (A, B, C eligible)
  Side pot = (45-15) * 2 = 60BB (B, C eligible only)
  Hero's call = 45BB to win up to 105BB (main+side) ... but A can only
  win 45BB regardless of what cards hero holds

Usage:
    from poker.side_pot import calculate_side_pots, SidePotResult
    result = calculate_side_pots(
        players=[
            {'name': 'short', 'invested_bb': 15.0, 'is_allin': True, 'has_cards': True},
            {'name': 'medium', 'invested_bb': 45.0, 'is_allin': True, 'has_cards': True},
            {'name': 'hero', 'invested_bb': 45.0, 'is_allin': False, 'has_cards': True},
        ],
        hero_name='hero',
        hero_equity_main=0.45,
        hero_equity_side=0.60,
    )
    print(result.hero_ev_bb, result.call_advice)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class PotSlice:
    """A single pot (main or side)."""
    label: str              # 'main', 'side_1', 'side_2', ...
    amount_bb: float
    eligible_players: List[str]  # player names eligible to win this pot


@dataclass
class SidePotResult:
    """Full side pot breakdown + hero decision."""
    # Input summary
    n_players: int
    total_pot_bb: float

    # Pot structure
    pots: List[PotSlice]
    main_pot_bb: float
    side_pot_total_bb: float

    # Hero analysis
    hero_name: str
    hero_max_win_bb: float       # max hero can win (pots hero is eligible for)
    hero_invested_bb: float
    hero_ev_bb: float            # expected value given equities
    hero_pot_odds: float         # pot_odds for hero's call decision
    call_is_correct: bool

    # Notes
    call_advice: str
    pot_structure_note: str
    strategic_tips: List[str] = field(default_factory=list)


def _build_pots(players: List[Dict]) -> List[PotSlice]:
    """
    Build the list of pots (main + side pots) from player investments.
    players: sorted list of {'name', 'invested_bb', 'has_cards'}
             — only players who actually put money in.
    """
    # Work only with players who have cards (eligible to win)
    eligible = [p for p in players if p.get('has_cards', True)]
    # Sort by invested_bb ascending
    eligible_sorted = sorted(eligible, key=lambda p: p['invested_bb'])

    pots = []
    prev_level = 0.0
    pot_idx = 0

    for i, p in enumerate(eligible_sorted):
        level = p['invested_bb']
        if level <= prev_level:
            continue
        increment = level - prev_level
        # Only players who invested at least the current level contributed here
        contributors = [ep for ep in eligible_sorted if ep['invested_bb'] >= level]
        actual_amount = increment * len(contributors)
        label = 'main' if pot_idx == 0 else f'side_{pot_idx}'
        pots.append(PotSlice(
            label=label,
            amount_bb=round(actual_amount, 2),
            eligible_players=[ep['name'] for ep in contributors],
        ))
        prev_level = level
        pot_idx += 1

    return pots


def calculate_side_pots(
    players: List[Dict],
    hero_name: str = 'hero',
    hero_equity_main: float = 0.40,
    hero_equity_side: float = 0.50,
) -> SidePotResult:
    """
    Calculate side pot structure and hero EV.

    Args:
        players:           List of dicts with keys:
                           - name (str)
                           - invested_bb (float): chips already in pot
                           - is_allin (bool): True if all-in
                           - has_cards (bool): True if still in hand
        hero_name:         Hero's name in the players list
        hero_equity_main:  Hero's equity vs ALL players in main pot
        hero_equity_side:  Hero's equity in side pot(s) vs non-AI players

    Returns:
        SidePotResult
    """
    active = [p for p in players if p.get('has_cards', True)]
    total_invested = sum(p['invested_bb'] for p in active)
    hero = next((p for p in active if p['name'] == hero_name), None)
    hero_invested = hero['invested_bb'] if hero else 0.0

    # Build pot structure
    pots = _build_pots(active)
    main_pot_bb = pots[0].amount_bb if pots else 0.0
    side_pot_total = sum(p.amount_bb for p in pots[1:]) if len(pots) > 1 else 0.0
    hero_max_win = sum(
        p.amount_bb for p in pots if hero_name in p.eligible_players
    )

    # EV calculation
    # Main pot EV for hero
    ev_main = hero_equity_main * main_pot_bb if hero_name in (pots[0].eligible_players if pots else []) else 0.0
    # Side pot EV
    ev_side = hero_equity_side * side_pot_total if side_pot_total > 0 else 0.0
    hero_ev = round(ev_main + ev_side - hero_invested, 2)

    # Pot odds for hero (what hero needs to call more)
    # If hero hasn't called yet, pot_odds = hero_max_win / hero_invested
    pot_odds = round(hero_max_win / hero_invested, 2) if hero_invested > 0 else 0.0
    breakeven_equity_main = round(hero_invested / (total_invested + hero_invested), 3)
    call_correct = hero_ev >= 0

    # Build advice
    n_side = len(pots) - 1
    pot_note = (
        f'Main pot: {main_pot_bb:.1f}BB ({len(pots[0].eligible_players) if pots else 0} eligible). '
        + (f'{n_side} side pot(s): {side_pot_total:.1f}BB total.' if n_side > 0
           else 'No side pots.')
    )

    if hero_ev >= 2.0:
        call_advice = (
            f'CLEAR CALL: EV = +{hero_ev:.1f}BB. '
            f'Hero equity in main ({hero_equity_main:.0%}) and side ({hero_equity_side:.0%}) '
            f'exceeds cost.'
        )
    elif hero_ev >= 0:
        call_advice = (
            f'MARGINAL CALL: EV = +{hero_ev:.1f}BB. '
            f'Just barely profitable. Consider live reads.'
        )
    else:
        call_advice = (
            f'FOLD: EV = {hero_ev:.1f}BB. '
            f'Hero needs {breakeven_equity_main:.0%} equity to break even on main pot alone.'
        )

    tips = [
        f'Short-stacked players can only win main pot ({main_pot_bb:.1f}BB) — '
        f'not the side pot ({side_pot_total:.1f}BB).',
    ]
    if side_pot_total > main_pot_bb:
        tips.append(
            f'Side pot ({side_pot_total:.1f}BB) is larger than main pot. '
            f'Focus equity analysis on side pot vs the non-allin player.'
        )
    if hero_equity_side > hero_equity_main + 0.10:
        tips.append(
            f'Hero has better equity vs the side pot opponent ({hero_equity_side:.0%}) '
            f'than the main pot field ({hero_equity_main:.0%}). '
            f'This makes the call more attractive.'
        )

    return SidePotResult(
        n_players=len(active),
        total_pot_bb=round(total_invested, 2),
        pots=pots,
        main_pot_bb=round(main_pot_bb, 2),
        side_pot_total_bb=round(side_pot_total, 2),
        hero_name=hero_name,
        hero_max_win_bb=round(hero_max_win, 2),
        hero_invested_bb=round(hero_invested, 2),
        hero_ev_bb=hero_ev,
        hero_pot_odds=pot_odds,
        call_is_correct=call_correct,
        call_advice=call_advice,
        pot_structure_note=pot_note,
        strategic_tips=tips,
    )


def side_pot_one_liner(result: SidePotResult) -> str:
    pots_str = f'main={result.main_pot_bb:.0f}BB'
    if result.side_pot_total_bb > 0:
        pots_str += f' side={result.side_pot_total_bb:.0f}BB'
    ev_str = f'+{result.hero_ev_bb:.1f}' if result.hero_ev_bb >= 0 else f'{result.hero_ev_bb:.1f}'
    action = 'CALL' if result.call_is_correct else 'FOLD'
    return (
        f'[SP {result.n_players}way] {action} | {pots_str} | '
        f'EV={ev_str}BB | odds={result.hero_pot_odds:.1f}x'
    )
