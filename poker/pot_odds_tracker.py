"""
Pot Odds Tracker (pot_odds_tracker.py)

A real-time pot odds reference tool. Given the current pot size, shows
for every common villain bet size (20% to 300% pot) exactly:

  - How much villain bets
  - The total pot after the bet
  - How much hero must call
  - The pot odds ratio (X:1)
  - The required equity to break even (call_amount / total_pot_after_call)
  - Whether a specific hero equity makes the call profitable

This is essential for live poker where:
  - Villain makes unusual bet sizes (e.g., 37% pot, 1.5x pot)
  - Hero needs to quickly calculate break-even equity
  - Hero wants to know the MDF (Minimum Defense Frequency)
  - Multiple bet size scenarios to prepare for

Key formula:
  Required equity = call_amount / (pot + call_amount)
  = bet_bb / (pot_bb + 2 * bet_bb)     [when you call, pot doubles]
  Actually: call / (pot_after_villain_bet + call)
          = bet / (pot_before + bet + bet)  [pot + 2*bet if both put in bet]
  Correct: pot_after_call = pot_before + villain_bet + hero_call
         = pot + bet + bet = pot + 2*bet
  So: required_eq = bet / (pot + 2*bet)
  And: MDF = 1 - bet/(pot+bet) = pot/(pot+bet)

Usage:
    from poker.pot_odds_tracker import build_pot_odds_table, PotOddsTable
    table = build_pot_odds_table(pot_bb=40.0, hero_equity=0.55)
    print(table.summary_text)

    # Or quick lookup for a specific villain bet
    entry = lookup_odds(pot_bb=40.0, villain_bet_bb=30.0)
    print(entry.required_equity, entry.is_profitable)
"""

from dataclasses import dataclass, field
from typing import List, Optional


_STANDARD_BET_PCTS = [0.20, 0.25, 0.33, 0.40, 0.50, 0.60, 0.66, 0.75,
                       1.00, 1.25, 1.50, 2.00, 2.50, 3.00]


@dataclass
class PotOddsEntry:
    """Pot odds for a single villain bet size."""
    bet_pct: float         # villain bet as fraction of pot
    bet_bb: float          # villain bet in BB
    total_pot_after_bb: float   # pot after villain bets (before hero calls)
    to_call_bb: float      # what hero must call
    pot_if_call_bb: float  # pot if hero calls (total)
    pot_odds_ratio: float  # X:1 (pot:call)
    required_equity: float # break-even equity to call
    mdf: float             # Minimum Defense Frequency (1 - alpha)
    is_profitable: bool    # True if hero_equity >= required_equity
    label: str             # e.g. "33%pot", "PSB", "2x overbet"


@dataclass
class PotOddsTable:
    """Complete pot odds reference for a given pot size."""
    pot_bb: float
    hero_equity: float
    entries: List[PotOddsEntry]

    # Summary
    profitable_calls: List[str]   # labels where call is profitable
    marginal_calls: List[str]     # within 3% of break-even
    clear_folds: List[str]        # hero equity is well below required
    summary_text: str = ''


def _label(bet_pct: float) -> str:
    if abs(bet_pct - 0.33) < 0.02:
        return '33%pot'
    if abs(bet_pct - 0.50) < 0.02:
        return 'half-pot'
    if abs(bet_pct - 0.66) < 0.02:
        return '2/3pot'
    if abs(bet_pct - 0.75) < 0.02:
        return '3/4pot'
    if abs(bet_pct - 1.00) < 0.02:
        return 'PSB(1x)'
    if bet_pct >= 1.40:
        return f'{bet_pct:.0%}OB'
    return f'{bet_pct:.0%}pot'


def _make_entry(pot_bb: float, bet_pct: float, hero_equity: float) -> PotOddsEntry:
    bet_bb = round(pot_bb * bet_pct, 2)
    pot_after = round(pot_bb + bet_bb, 2)
    pot_if_call = round(pot_bb + 2 * bet_bb, 2)
    req_eq = round(bet_bb / pot_if_call, 4) if pot_if_call > 0 else 0
    mdf = round(1.0 - bet_bb / (pot_bb + bet_bb), 4)
    odds_ratio = round(pot_after / bet_bb, 2) if bet_bb > 0 else 99.0
    is_profitable = hero_equity >= req_eq
    return PotOddsEntry(
        bet_pct=bet_pct,
        bet_bb=bet_bb,
        total_pot_after_bb=pot_after,
        to_call_bb=bet_bb,
        pot_if_call_bb=pot_if_call,
        pot_odds_ratio=odds_ratio,
        required_equity=req_eq,
        mdf=mdf,
        is_profitable=is_profitable,
        label=_label(bet_pct),
    )


def build_pot_odds_table(
    pot_bb: float = 40.0,
    hero_equity: float = 0.50,
    custom_bet_pcts: Optional[List[float]] = None,
) -> PotOddsTable:
    """
    Build a complete pot odds reference table.

    Args:
        pot_bb:            Current pot size before villain bet
        hero_equity:       Hero's equity (0-1) for profitability check
        custom_bet_pcts:   Override default bet sizes (as fractions of pot)

    Returns:
        PotOddsTable with entries for each bet size
    """
    bet_pcts = custom_bet_pcts or _STANDARD_BET_PCTS
    entries = [_make_entry(pot_bb, pct, hero_equity) for pct in bet_pcts]

    profitable = [e.label for e in entries if e.is_profitable]
    marginal = [e.label for e in entries
                if not e.is_profitable and e.required_equity - hero_equity <= 0.03]
    folds = [e.label for e in entries if e.required_equity - hero_equity > 0.03]

    # Build summary text (ASCII-safe for cp950)
    lines = [
        f'Pot: {pot_bb:.1f}BB | Hero equity: {hero_equity:.0%}',
        f'{"Bet":>12} {"Bet BB":>8} {"To Call":>8} {"Req Eq":>8} {"MDF":>7} {"Call?":>7}',
        '-' * 55,
    ]
    for e in entries:
        call_str = 'CALL' if e.is_profitable else ('~' if abs(e.required_equity - hero_equity) <= 0.03 else 'FOLD')
        lines.append(
            f'{e.label:>12} {e.bet_bb:>8.1f} {e.to_call_bb:>8.1f} '
            f'{e.required_equity:>8.1%} {e.mdf:>7.0%} {call_str:>7}'
        )
    summary = '\n'.join(lines)

    return PotOddsTable(
        pot_bb=round(pot_bb, 2),
        hero_equity=round(hero_equity, 4),
        entries=entries,
        profitable_calls=profitable,
        marginal_calls=marginal,
        clear_folds=folds,
        summary_text=summary,
    )


def lookup_odds(
    pot_bb: float,
    villain_bet_bb: float,
    hero_equity: float = 0.50,
) -> PotOddsEntry:
    """
    Quick lookup for a specific villain bet amount.

    Args:
        pot_bb:          Pot before villain bet
        villain_bet_bb:  Villain's actual bet amount
        hero_equity:     Hero's equity for profitability check

    Returns:
        PotOddsEntry with all pot odds info
    """
    bet_pct = villain_bet_bb / pot_bb if pot_bb > 0 else 1.0
    return _make_entry(pot_bb, bet_pct, hero_equity)


def pot_odds_one_liner(pot_bb: float, villain_bet_bb: float,
                       hero_equity: float) -> str:
    e = lookup_odds(pot_bb, villain_bet_bb, hero_equity)
    action = 'CALL' if e.is_profitable else 'FOLD'
    return (
        f'[PO] {e.bet_bb:.1f}BB into {pot_bb:.1f}BB | '
        f'need {e.required_equity:.0%} have {hero_equity:.0%} | '
        f'MDF={e.mdf:.0%} | {action}'
    )
