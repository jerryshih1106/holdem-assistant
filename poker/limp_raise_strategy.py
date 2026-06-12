"""
Limp-Raise Strategy (limp_raise_strategy.py)

Analyzes when limp-raising (open-limping then re-raising) is profitable vs
standard open-raising. Limp-raising is an advanced play primarily used in:
  1. Live games where opponents open wide and you have a trapping hand
  2. Positions where open-raise stack-off is inevitable (stack-dependent)
  3. Spots with weak players who over-call limps then overbet when raised

LIMP-RAISE THEORY:
  Standard play: Open-raise to 4x (live) or 2.5x (online).
  Limp-raise: Open-limp, then 3-bet if someone raises.

  WHEN LIMP-RAISE IS +EV vs OPEN-RAISE:
  1. TRAPPING: Opponents at your table open wide when limps fold around.
     By limping with AA, you invite a raise, then re-raise for a larger pot.
     Against: players who respect raises but iso-raise limps aggressively.

  2. STACK GEOMETRY: In deep-stack live games, open-raise AA to 4x then
     4-bet means committing 25%+ stack preflop in a non-allin pot.
     Limp-raise builds a bigger pot vs opponent who folds to 3-bet.

  3. BALANCING OOP LIMP RANGE: On the button with weak players,
     mixing some limp-raises with strong hands makes your limp range
     less exploitable.

  WHEN LIMP-RAISE IS -EV vs OPEN-RAISE:
  1. Tight tables: no one opens over the limp; you see a cheap flop with AA
     but miss the pot-building opportunity.
  2. Short stacks: SPR so low that limp-raise commits too much.
  3. Online: players don't iso-raise limps often; limp = check around.
  4. Obvious pattern: if villain notices you only limp-raise with premiums.

  LIMP-RAISE SIZING:
  Facing a 3x iso-raise: raise to 12-16BB (4-5x the raise)
  Facing a 4x iso-raise: raise to 18-22BB (similar multiplier)
  Make it just large enough that caller commits ~25% stack or faces a tough decision.

  HAND SELECTION:
  Best limp-raise hands: AA, KK (want action; trapping)
  Occasional:            QQ, AKs (if table dynamic is right)
  Never:                 Small/medium pairs (prefer limp-call for implied odds)

DISTINCT FROM:
  preflop_advisor.py:    General preflop action
  open_sizing.py:        Open raise sizing
  iso_raise.py:          Isolating limpers (you are the raiser)
  THIS MODULE:           LIMP-RAISE strategy (you LIMP then RE-RAISE);
                         when it's better than open-raising; sizing;
                         hand selection; table dynamic requirements.

Usage:
    from poker.limp_raise_strategy import analyze_limp_raise, LimpRaisePlan, lrp_one_liner

    result = analyze_limp_raise(
        hero_hand='AA',
        hero_position='utg',
        table_iso_freq=0.60,
        villain_iso_size_bb=12.0,
        stack_bb=200.0,
        players_at_table=6,
        game_type='live',
        villain_fold_to_3bet=0.55,
    )
    print(lrp_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Hands where limp-raise is a valid strategy
LIMP_RAISE_HANDS = {'AA', 'KK', 'QQ', 'AKs', 'AKo'}
PREMIUM_LIMP_RAISE = {'AA', 'KK'}   # best candidates

# Table iso-frequency threshold: need at least this to limp-raise profitably
MIN_ISO_FREQ = 0.40

# Deep-stack threshold for limp-raise (stack in BB)
DEEP_STACK_THRESHOLD = 150

# Limp-raise size multiplier vs iso-raise size
LIMP_RAISE_MULTIPLIER = 4.2


def _is_limp_raise_hand(hand: str) -> bool:
    return hand in LIMP_RAISE_HANDS


def _limp_raise_size(villain_iso_size_bb: float, stack_bb: float) -> float:
    """Recommended limp-raise size in BB."""
    size = villain_iso_size_bb * LIMP_RAISE_MULTIPLIER
    max_size = stack_bb * 0.30   # don't commit more than 30% stack preflop
    return round(min(size, max_size), 1)


def _limp_raise_ev(
    dead_money: float,
    fold_equity: float,
    limp_raise_size: float,
    hero_equity_called: float = 0.80,
    pot_if_called: float = 0,
) -> float:
    """EV of limp-raise vs open-raise."""
    ev_fold = fold_equity * dead_money
    ev_call = (1 - fold_equity) * hero_equity_called * (pot_if_called + limp_raise_size)
    return round(ev_fold + ev_call - limp_raise_size, 2)


def _should_limp_raise(
    hand: str,
    table_iso_freq: float,
    stack_bb: float,
    game_type: str,
) -> bool:
    if hand not in LIMP_RAISE_HANDS:
        return False
    if table_iso_freq < MIN_ISO_FREQ:
        return False   # no one raises over your limp
    if game_type == 'online' and table_iso_freq < 0.55:
        return False   # online: limp-raise less common; need higher iso freq
    return True


def _vs_open_raise_comparison(
    hand: str,
    table_iso_freq: float,
    stack_bb: float,
    game_type: str,
) -> str:
    """Should hero open-raise or limp-raise?"""
    if not _should_limp_raise(hand, table_iso_freq, stack_bb, game_type):
        return 'open_raise'   # limp-raise conditions not met
    if hand in PREMIUM_LIMP_RAISE and table_iso_freq >= 0.60:
        return 'limp_raise'
    if stack_bb >= DEEP_STACK_THRESHOLD:
        return 'limp_raise'   # deep stacks benefit more from limp-raise
    return 'open_raise'   # standard is better in borderline cases


def _limp_raise_tell_risk(
    hand: str,
    previous_limp_raises: int,
) -> str:
    """Risk of villain exploiting predictable limp-raise pattern."""
    if previous_limp_raises >= 2 and hand in PREMIUM_LIMP_RAISE:
        return 'high_tell_risk'   # villain may recognize the pattern
    elif previous_limp_raises >= 1:
        return 'moderate_tell_risk'
    return 'low_tell_risk'


@dataclass
class LimpRaisePlan:
    # Inputs
    hero_hand: str
    hero_position: str
    table_iso_freq: float
    villain_iso_size_bb: float
    stack_bb: float
    players_at_table: int
    game_type: str
    villain_fold_to_3bet: float

    # Analysis
    is_limp_raise_hand: bool
    should_limp_raise: bool
    recommendation: str          # 'limp_raise' / 'open_raise'
    limp_raise_size_bb: float
    tell_risk: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_limp_raise(
    hero_hand: str = 'AA',
    hero_position: str = 'utg',
    table_iso_freq: float = 0.60,
    villain_iso_size_bb: float = 12.0,
    stack_bb: float = 200.0,
    players_at_table: int = 6,
    game_type: str = 'live',
    villain_fold_to_3bet: float = 0.55,
) -> LimpRaisePlan:
    """
    Analyze whether limp-raise is better than open-raise in this spot.

    Args:
        hero_hand:           Hero's hand ('AA', 'KK', etc.)
        hero_position:       Position at table
        table_iso_freq:      Frequency that someone iso-raises a limp (0.0-1.0)
        villain_iso_size_bb: Typical iso-raise size in BB
        stack_bb:            Effective stack size
        players_at_table:    Number of players
        game_type:           'live' or 'online'
        villain_fold_to_3bet: Villain fold-to-3bet rate

    Returns:
        LimpRaisePlan
    """
    eligible = _is_limp_raise_hand(hero_hand)
    should_lr = _should_limp_raise(hero_hand, table_iso_freq, stack_bb, game_type)
    rec = _vs_open_raise_comparison(hero_hand, table_iso_freq, stack_bb, game_type)
    lr_size = _limp_raise_size(villain_iso_size_bb, stack_bb)
    tell_risk = _limp_raise_tell_risk(hero_hand, 0)

    dead = 1.5 + (players_at_table - 2) * 0.1  # blinds + antes estimate
    fold_eq = villain_fold_to_3bet
    ev = _limp_raise_ev(dead, fold_eq, lr_size,
                         hero_equity_called=0.80,
                         pot_if_called=villain_iso_size_bb + dead)

    action = f'LIMP_RAISE to {lr_size:.1f}BB' if rec == 'limp_raise' else 'OPEN_RAISE'

    verdict = (
        f'[LRP {hero_hand}|{hero_position}|{game_type}] '
        f'{action} | iso_freq={table_iso_freq:.0%} stack={stack_bb:.0f}BB ev={ev:+.1f}BB'
    )

    reasoning = (
        f'Limp-raise analysis: {hero_hand} at {hero_position} in {game_type} game. '
        f'Table iso-frequency={table_iso_freq:.0%} (need >= {MIN_ISO_FREQ:.0%}). '
        f'Stack={stack_bb:.0f}BB (deep={stack_bb >= DEEP_STACK_THRESHOLD}). '
        f'Eligible hand: {eligible}. Should limp-raise: {should_lr}. '
        f'Recommendation: {rec}. LR size: {lr_size:.1f}BB ({LIMP_RAISE_MULTIPLIER}x iso={villain_iso_size_bb:.1f}BB). '
        f'EV estimate: {ev:+.1f}BB.'
    )

    tips = []

    tips.append(
        f'LIMP-RAISE CONDITIONS: '
        f'(1) Hand eligible ({hero_hand}: {"YES" if eligible else "NO"}). '
        f'(2) Table iso-freq ({table_iso_freq:.0%} >= {MIN_ISO_FREQ:.0%}: {"YES" if table_iso_freq >= MIN_ISO_FREQ else "NO"}). '
        f'(3) Deep stack ({stack_bb:.0f}BB >= {DEEP_STACK_THRESHOLD}: {"YES" if stack_bb >= DEEP_STACK_THRESHOLD else "NO"}). '
        f'Recommendation: {rec.upper()}.'
    )

    if rec == 'limp_raise':
        tips.append(
            f'LIMP-RAISE EXECUTION: '
            f'Open limp {villain_iso_size_bb/4:.1f}BB (1BB call). '
            f'Wait for iso-raise. If raised: re-raise to {lr_size:.1f}BB ({LIMP_RAISE_MULTIPLIER:.1f}x the iso). '
            f'Goal: build a pot with {hero_hand} vs villain who thinks you have a weak limp. '
            f'EV advantage: villain expects weak hand; your raise gets action vs KK/QQ/AK.'
        )
    else:
        tips.append(
            f'OPEN-RAISE IS BETTER: '
            f'{"Table iso-freq too low ("+str(int(table_iso_freq*100))+"% < "+str(int(MIN_ISO_FREQ*100))+"%): no one raises; you see flop 5-way for cheap." if table_iso_freq < MIN_ISO_FREQ else ""}'
            f'{"Stack too shallow for limp-raise geometry." if stack_bb < DEEP_STACK_THRESHOLD and table_iso_freq >= MIN_ISO_FREQ else ""}'
            f'Open-raise to {4 if game_type == "live" else 2.5}x to build pot and show aggression.'
        )

    tips.append(
        f'LIMP-RAISE SIZING: {lr_size:.1f}BB ({LIMP_RAISE_MULTIPLIER:.1f}x iso of {villain_iso_size_bb:.1f}BB). '
        f'Sizing logic: large enough to commit villain with {hero_hand.replace("A", "A")}-type hands. '
        f'If villain has QQ vs your AA: {lr_size:.1f}BB = {lr_size/stack_bb:.0%} of stack. '
        f'At this size, villain faces: call off {lr_size/stack_bb:.0%} stack preflop = often correct to shove.'
    )

    tips.append(
        f'TELL RISK ({tell_risk}): Pattern awareness critical. '
        f'If you only limp-raise with AA/KK, good villains will fold always = you just win 1BB. '
        f'Solution: occasionally limp-raise with QQ or AKs to balance. '
        f'In live games: players often don\'t pay attention; tell risk is lower.'
    )

    return LimpRaisePlan(
        hero_hand=hero_hand,
        hero_position=hero_position,
        table_iso_freq=table_iso_freq,
        villain_iso_size_bb=villain_iso_size_bb,
        stack_bb=stack_bb,
        players_at_table=players_at_table,
        game_type=game_type,
        villain_fold_to_3bet=villain_fold_to_3bet,
        is_limp_raise_hand=eligible,
        should_limp_raise=should_lr,
        recommendation=rec,
        limp_raise_size_bb=lr_size,
        tell_risk=tell_risk,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def lrp_one_liner(r: LimpRaisePlan) -> str:
    action = f'LIMP_RAISE {r.limp_raise_size_bb:.1f}BB' if r.recommendation == 'limp_raise' else 'OPEN_RAISE'
    return (
        f'[LRP {r.hero_hand}|{r.hero_position}] '
        f'{action} iso_freq={r.table_iso_freq:.0%} | '
        f'tell_risk={r.tell_risk}'
    )
