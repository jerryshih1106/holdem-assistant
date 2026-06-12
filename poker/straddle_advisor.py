"""
Straddle Advisor (straddle_advisor.py)

Covers strategy adjustments when there is a straddle (an additional blind
posted by UTG, BTN, or another position before cards are dealt).

How a straddle changes the game:
  1. POSITION SHIFT: The straddler acts LAST preflop (same as BB does normally).
     Example: UTG straddle → UTG now acts last preflop (most powerful position).
     BTN straddle → BTN acts last preflop (same as normal BTN, but...
     ...everyone else loses one position of advantage).

  2. EFFECTIVE BIG BLIND doubles (or more with double-straddle):
     - Standard: SB=0.5BB, BB=1BB → UTG straddle=2BB, so pot starts at 3.5BB
     - All raises must be at minimum 2x the straddle (like normal raise rules)
     - Opening from CO: instead of 2.5BB, now raise to 5-6BB (2x straddle + adjustments)

  3. RANGE ADJUSTMENTS:
     - Because pot is bigger, pot-equity requirements change
     - Calling ranges tighten (bigger price to enter)
     - 3-bet ranges need adjustment (bigger 3-bets required)
     - Squeeze opportunities increase (more dead money)

  4. SPR on flop decreases:
     - Standard open (2.5BB) → flop SPR ~15 at 100BB
     - With straddle and open (5BB) → flop SPR ~8-10
     - Commitment thresholds reached sooner

  5. Straddler's positional advantage preflop:
     - If UTG straddles and everyone folds to them, they can squeeze any range
     - Straddler acts last → can 3-bet or call with any hand they want

Typical adjustments:
  - Opening sizes: multiply by 2 (straddle is 2BB, standard opens vs 2BB straddle)
  - 3-bet sizes: add 1 straddle to standard 3-bet calculation
  - Call/fold thresholds: tighter calls (bigger price), looser folds
  - Squeeze: more profitable (extra dead money from straddle)
  - Straddler defense: straddler gets to close action like BB; wide defense range

Usage:
    from poker.straddle_advisor import advise_straddle, StraddleAdvice
    result = advise_straddle(
        hero_pos='CO',
        straddle_pos='UTG',
        straddle_bb=2.0,
        hero_stack_bb=100.0,
        n_players=6,
        villain_vpip=0.28,
    )
    print(result.recommended_open_bb, result.positional_notes)
"""

from dataclasses import dataclass, field
from typing import List, Optional


_POSITION_ORDER = ['SB', 'BB', 'UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN']


def _position_after_straddle(hero_pos: str, straddle_pos: str) -> str:
    """Return hero's effective position given the straddle."""
    # Straddler acts last preflop → everyone before them gains a "position"
    # effectively. Straddle is like a third blind.
    try:
        hero_idx = _POSITION_ORDER.index(hero_pos)
        strad_idx = _POSITION_ORDER.index(straddle_pos)
    except ValueError:
        return hero_pos

    if strade_idx := strad_idx:
        if hero_idx > strad_idx:
            return 'early'   # hero acts before straddler = early position
        elif hero_idx < strad_idx:
            return 'late'    # hero acts after straddler in a normal sense but pre-straddle
        else:
            return 'straddler'

    return hero_pos


def _effective_bb(straddle_bb: float) -> float:
    """The effective 'big blind' when a straddle is live."""
    return straddle_bb


def _recommended_open_size(
    hero_pos: str,
    straddle_bb: float,
    n_players_behind: int,
    villain_vpip: float,
) -> float:
    """Recommended open-raise size with straddle."""
    # Base: 2.2-2.5x the straddle (same ratio as standard open vs 1BB)
    if villain_vpip >= 0.40:
        base_mult = 2.8  # loose game → raise bigger to build pot
    elif villain_vpip >= 0.30:
        base_mult = 2.5
    else:
        base_mult = 2.2

    # Add 0.5 straddle per player behind (more dead money to take)
    players_adj = min(0.5 * straddle_bb, n_players_behind * 0.15 * straddle_bb)

    raw = straddle_bb * base_mult + players_adj

    # Cap: don't open to more than 5x the straddle
    return round(min(raw, straddle_bb * 5.0), 1)


def _threeBet_size(
    open_size_bb: float,
    straddle_bb: float,
    in_position: bool,
    callers_before: int,
) -> float:
    """3-bet size with straddle."""
    # Standard 3-bet is 3x IP, 3.5x OOP vs normal opens
    # With straddle, there's extra dead money → larger 3-bet
    mult = 2.8 if in_position else 3.3
    base = open_size_bb * mult + callers_before * straddle_bb
    return round(base, 1)


def _spr_on_flop(open_size_bb: float, hero_stack_bb: float) -> float:
    """Approximate SPR on flop when hero opens and gets one caller."""
    pot_on_flop = open_size_bb * 2 + 1.5  # open + call + blinds/straddle
    remaining = hero_stack_bb - open_size_bb
    return round(remaining / pot_on_flop, 2) if pot_on_flop > 0 else 0.0


def _straddler_defense_range(straddle_bb: float, villain_open_bb: float) -> dict:
    """When straddler faces an open raise, their defense ranges."""
    # Pot odds to call: call / (pot + call) = open / (straddle + blinds + open)
    pot_before = straddle_bb + 1.5  # straddle + SB + BB
    call_amt = villain_open_bb - straddle_bb
    pot_odds = call_amt / (pot_before + villain_open_bb)

    # Straddler acts LAST preflop → very favorable → defend wide
    # MDF: pot / (pot + raise) = pot_before / (pot_before + call_amt)
    mdf = pot_before / (pot_before + call_amt)

    return {
        'pot_odds': round(pot_odds, 3),
        'mdf': round(mdf, 3),
        'call_range_pct': round(max(0.25, mdf * 0.85), 3),
        'threbet_pct': round(0.08 + max(0.0, (pot_odds - 0.35) * 0.10), 3),
        'note': (
            f'Straddler acts last: defend with {max(0.25, mdf * 0.85):.0%} of hands. '
            f'MDF={mdf:.0%}. 3-bet {round(0.08 + max(0.0, (pot_odds - 0.35) * 0.10), 3):.0%}.'
        ),
    }


def _squeeze_opportunity(n_callers: int, open_size_bb: float,
                         straddle_bb: float, hero_stack_bb: float) -> dict:
    """Squeeze EV estimate with straddle adding dead money."""
    dead_money = straddle_bb + 1.5 + n_callers * open_size_bb  # blinds + straddle + callers
    squeeze_size = open_size_bb * 3.5 + n_callers * straddle_bb
    fold_equity = max(0.30, 0.55 - n_callers * 0.05)

    # Rough EV: p_fold * dead_money - p_call * squeeze
    ev = fold_equity * dead_money - (1 - fold_equity) * squeeze_size * 0.40
    return {
        'dead_money_bb': round(dead_money, 1),
        'recommended_squeeze_bb': round(squeeze_size, 1),
        'fold_equity_estimate': round(fold_equity, 2),
        'ev_estimate_bb': round(ev, 2),
        'should_squeeze_more': ev > 0.5,
    }


@dataclass
class StraddleAdvice:
    """Strategy adjustments when there is a straddle."""
    hero_pos: str
    straddle_pos: str
    straddle_bb: float
    hero_stack_bb: float
    n_players: int

    # Sizing adjustments
    recommended_open_bb: float
    threeBet_ip_bb: float
    threeBet_oop_bb: float
    effective_big_blind: float   # straddle acts as new BB

    # SPR changes
    spr_on_flop_if_opens: float  # SPR on flop after hero opens and gets 1 call
    spr_vs_standard: float       # SPR at standard 2.5BB open for comparison

    # Positional notes
    straddler_last_preflop: bool
    positional_notes: str

    # Defense (if hero IS the straddler)
    straddler_defense: Optional[dict] = None

    # Squeeze opportunity
    squeeze_analysis: Optional[dict] = None

    # Strategic adjustments
    tighten_calling_range: bool = True
    calling_range_adj_pct: float = 0.0   # how much to tighten vs standard
    strategic_notes: List[str] = field(default_factory=list)


def advise_straddle(
    hero_pos: str,
    straddle_pos: str = 'UTG',
    straddle_bb: float = 2.0,
    hero_stack_bb: float = 100.0,
    n_players: int = 6,
    villain_vpip: float = 0.28,
    n_callers: int = 0,
    hero_is_straddler: bool = False,
) -> StraddleAdvice:
    """
    Strategy adjustments for a straddled game.

    Args:
        hero_pos:            Hero's position
        straddle_pos:        Position of the straddler ('UTG', 'BTN', etc.)
        straddle_bb:         Straddle size in BB (usually 2.0)
        hero_stack_bb:       Hero's stack
        n_players:           Active players at table
        villain_vpip:        Average villain VPIP (affects sizing)
        n_callers:           Number of callers before hero (for squeeze)
        hero_is_straddler:   True if hero posted the straddle

    Returns:
        StraddleAdvice
    """
    n_behind = max(0, n_players - _POSITION_ORDER.index(hero_pos) - 1) \
        if hero_pos in _POSITION_ORDER else 2

    open_size = _recommended_open_size(hero_pos, straddle_bb, n_behind, villain_vpip)
    three_ip  = _threeBet_size(open_size, straddle_bb, True, 0)
    three_oop = _threeBet_size(open_size, straddle_bb, False, 0)
    spr_now   = _spr_on_flop(open_size, hero_stack_bb)
    spr_std   = _spr_on_flop(2.5, hero_stack_bb)

    straddler_acts_last = (straddle_pos == 'UTG')  # UTG straddle = UTG acts last preflop

    # Calling range tightening: bigger price → need stronger hands
    call_adj = -round(max(0.0, (straddle_bb - 1.0) * 0.06), 3)

    defense = None
    if hero_is_straddler:
        defense = _straddler_defense_range(straddle_bb, open_size)

    squeeze = None
    if n_callers > 0:
        squeeze = _squeeze_opportunity(n_callers, open_size, straddle_bb, hero_stack_bb)

    notes = [
        f'Straddle={straddle_bb:.0f}BB: effective BB doubled. '
        f'Open to {open_size:.0f}BB (vs normal ~2.5BB). '
        f'All bet sizes scale with straddle.',
        f'SPR on flop after open+call: {spr_now:.1f} vs standard {spr_std:.1f}. '
        f'Lower SPR means commitment threshold is reached faster.',
        f'Tighten calling range by ~{abs(call_adj)*100:.0f}%. '
        f'Bigger pot entry cost requires stronger hands to call profitably.',
    ]
    if straddler_acts_last:
        notes.append(
            f'UTG straddle: straddler acts LAST preflop. '
            f'If everyone folds to UTG, they can squeeze very wide with position advantage.'
        )
    if n_callers >= 2:
        notes.append(
            f'Dead money from {n_callers} callers + straddle = highly profitable squeeze spots.'
        )

    pos_note = (
        f'Hero ({hero_pos}) vs {straddle_pos} straddle. '
        f'{"Straddler acts last preflop." if straddler_acts_last else "Normal position order."} '
        f'Open size: {open_size:.1f}BB. 3-bet IP: {three_ip:.1f}BB / OOP: {three_oop:.1f}BB.'
    )

    return StraddleAdvice(
        hero_pos=hero_pos,
        straddle_pos=straddle_pos,
        straddle_bb=straddle_bb,
        hero_stack_bb=hero_stack_bb,
        n_players=n_players,
        recommended_open_bb=open_size,
        threeBet_ip_bb=three_ip,
        threeBet_oop_bb=three_oop,
        effective_big_blind=straddle_bb,
        spr_on_flop_if_opens=spr_now,
        spr_vs_standard=spr_std,
        straddler_last_preflop=straddler_acts_last,
        positional_notes=pos_note,
        straddler_defense=defense,
        squeeze_analysis=squeeze,
        tighten_calling_range=True,
        calling_range_adj_pct=call_adj,
        strategic_notes=notes,
    )


def straddle_one_liner(result: StraddleAdvice) -> str:
    return (
        f'[STRDL {result.straddle_bb:.0f}BB] '
        f'open={result.recommended_open_bb:.0f}BB | '
        f'3b-IP={result.threeBet_ip_bb:.0f}BB OOP={result.threeBet_oop_bb:.0f}BB | '
        f'SPR={result.spr_on_flop_if_opens:.1f}'
    )
