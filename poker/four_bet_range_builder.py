"""
Four-Bet Range Builder (four_bet_range_builder.py)

Builds and analyzes 4-bet ranges: 3-bet facing a 3-bet.
4-betting is a crucial weapon in modern poker that:
  1. Protects your 3-bet range (makes it balanced, not just value)
  2. Exploits overly tight folding opponents
  3. Gets max value vs KK/QQ/AK when you have AA
  4. Re-steals vs blind-defense 3-bets

FOUR-BET THEORY:
  GTO 4-bet range = VALUE hands + BLUFF hands (polarized).
  Pure value-only 4-bets are exploitable: villain can fold/call optimally.

  VALUE 4-BETS: AA (always), KK (usually), QQ (sometimes), AKs (occasionally)
  BLUFF 4-BETS: A5s, A4s, A3s, A2s (ace blockers reduce villain's AA/AK combos)
                KQs (K blocker), suited connectors with blockers

  4-BET SIZING:
    IP:   2.5x - 3x the 3-bet
    OOP:  3x - 3.5x the 3-bet (need more to deny equity OOP)
    Push/fold zones: SPR < 3 = just shove

  4-BET FREQUENCY (GTO):
    vs BTN 3bet:  ~17% of opens (roughly 4bet/call/fold breakdown)
    vs SB 3bet:   ~15%
    vs BB 3bet:   ~12% (BB 3bets are stronger; fold or flat more often)

WHEN TO 4-BET BLUFF:
  - Villain's 3-bet% is high (>12%): many bluffs in their range
  - Villain folds to 4-bet >50%: exploitable
  - Hero has ace blocker (reduces AA combos by half)
  - Hero is IP: more equity realization if called

WHEN NOT TO 4-BET:
  - Villain has low 3-bet% (<7%): very strong range; just fold/flat
  - No blocker + no equity: pure bluff 4-bet rarely good
  - Villain is a LAG who 5-bets light: 4-bet bluffs get crushed

DISTINCT FROM:
  preflop_squeeze_range.py:     3-bet after open + call (squeeze)
  preflop_equilibrium_chart.py: General preflop strategy
  THIS MODULE:                  4-bet construction; when to 4-bet bluff;
                                optimal 4-bet sizing; fold equity analysis

Usage:
    from poker.four_bet_range_builder import build_four_bet_range, FourBetDecision, fbrb_one_liner

    result = build_four_bet_range(
        hero_hand='A5s',
        hero_position='btn',
        villain_position='co',
        villain_3bet_pct=0.14,
        villain_fold_to_4bet=0.55,
        three_bet_size_bb=9.0,
        stack_bb=100.0,
        hero_history_4bet=0.02,
        pot_bb=13.5,
    )
    print(fbrb_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# 4-bet value hands (always 4-bet for value)
VALUE_4BET_HANDS = {'AA', 'KK'}

# Strong value 4-bets (situational)
STRONG_4BET_HANDS = {'QQ', 'JJ', 'AKs', 'AKo'}

# 4-bet bluff candidates (ace blockers / specific blockers)
BLUFF_4BET_HANDS = {'A5s', 'A4s', 'A3s', 'A2s', 'KQs', 'ATs', 'A9s'}

# Hands to flat call (capture value without 4-betting)
FLAT_CALL_HANDS = {'TT', '99', 'AQs', 'AQo', 'AJs', 'KQo', 'KJs', 'QJs'}


def _four_bet_category(hand: str, villain_3bet_pct: float) -> str:
    if hand in VALUE_4BET_HANDS:
        return 'value'
    elif hand in STRONG_4BET_HANDS:
        if villain_3bet_pct <= 0.08:
            return 'value'   # tight 3-bet range = can 4-bet QQ/AK for value
        else:
            return 'value_or_flat'
    elif hand in BLUFF_4BET_HANDS:
        return 'bluff'
    elif hand in FLAT_CALL_HANDS:
        return 'flat'
    else:
        return 'fold'


def _four_bet_size(
    three_bet_size_bb: float,
    hero_position: str,
    stack_bb: float,
) -> float:
    """Recommended 4-bet size in BB."""
    # Rule: ~2.5-3x the 3-bet
    multiplier = 2.5 if hero_position in ('btn', 'co') else 3.0
    size = three_bet_size_bb * multiplier
    # If SPR would be < 3 after 4-bet: just shove instead
    if stack_bb / size < 2.0:
        return round(stack_bb, 1)   # shove
    return round(min(size, stack_bb * 0.35), 1)


def _fold_equity(
    villain_3bet_pct: float,
    villain_fold_to_4bet: float,
    hero_position: str,
) -> float:
    """Estimated fold equity for the 4-bet."""
    base = villain_fold_to_4bet
    # Tight 3-bettors fold less to 4-bets (stronger range)
    if villain_3bet_pct <= 0.07:
        base -= 0.10
    elif villain_3bet_pct >= 0.15:
        base += 0.08   # wide 3-bettor folds more to 4-bets
    # IP = slightly more fold equity (positional pressure)
    if hero_position in ('btn', 'co'):
        base += 0.03
    return round(min(0.80, max(0.25, base)), 3)


def _four_bet_ev(
    dead_money_bb: float,
    fold_equity: float,
    four_bet_size: float,
    three_bet_size_bb: float,
) -> float:
    """EV of 4-betting as bluff."""
    net_risk = four_bet_size - three_bet_size_bb
    ev = fold_equity * dead_money_bb - (1 - fold_equity) * net_risk
    return round(ev, 2)


def _should_four_bet(
    cat: str,
    fold_equity: float,
    ev: float,
    villain_3bet_pct: float,
    hero_4bet_history: float,
) -> bool:
    if cat == 'value':
        return True
    if cat == 'fold':
        return False
    if cat == 'flat':
        return False   # flat call is better
    # Bluff 4-bet conditions:
    if cat == 'bluff':
        if villain_3bet_pct <= 0.06:
            return False   # too strong a range; don't bluff
        if fold_equity >= 0.50 and ev >= 0:
            return True
        if hero_4bet_history <= 0.01:
            return True    # very tight image: bluff 4-bet has extra credibility
    if cat == 'value_or_flat':
        return villain_3bet_pct <= 0.10   # value 4-bet vs tight 3-bettor
    return False


@dataclass
class FourBetDecision:
    # Inputs
    hero_hand: str
    hero_position: str
    villain_position: str
    villain_3bet_pct: float
    villain_fold_to_4bet: float
    three_bet_size_bb: float
    stack_bb: float
    hero_history_4bet: float
    pot_bb: float

    # Analysis
    hand_category: str            # 'value' / 'bluff' / 'flat' / 'fold'
    four_bet_size_bb: float
    fold_equity: float
    four_bet_ev: float
    should_four_bet: bool
    dead_money_bb: float

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def build_four_bet_range(
    hero_hand: str = 'A5s',
    hero_position: str = 'btn',
    villain_position: str = 'co',
    villain_3bet_pct: float = 0.14,
    villain_fold_to_4bet: float = 0.55,
    three_bet_size_bb: float = 9.0,
    stack_bb: float = 100.0,
    hero_history_4bet: float = 0.02,
    pot_bb: float = 13.5,
) -> FourBetDecision:
    """
    Build 4-bet range decision for current hand and situation.

    Args:
        hero_hand:               Hero's hand
        hero_position:           Hero's position
        villain_position:        3-bettor's position
        villain_3bet_pct:        Villain's 3-bet frequency
        villain_fold_to_4bet:    Villain folds to 4-bet
        three_bet_size_bb:       Size of villain's 3-bet
        stack_bb:                Effective stack
        hero_history_4bet:       Hero's 4-bet frequency in session
        pot_bb:                  Current pot before action

    Returns:
        FourBetDecision
    """
    cat = _four_bet_category(hero_hand, villain_3bet_pct)
    size = _four_bet_size(three_bet_size_bb, hero_position, stack_bb)
    dead_money = pot_bb - three_bet_size_bb
    fold_eq = _fold_equity(villain_3bet_pct, villain_fold_to_4bet, hero_position)
    ev = _four_bet_ev(dead_money, fold_eq, size, three_bet_size_bb)
    do_4bet = _should_four_bet(cat, fold_eq, ev, villain_3bet_pct, hero_history_4bet)

    action = 'FOUR_BET' if do_4bet else ('FLAT_CALL' if cat == 'flat' else 'FOLD')

    verdict = (
        f'[FBRB {hero_hand}|{hero_position}|vs_{villain_position}] '
        f'{action} {size:.1f}BB '
        f'| cat={cat} fold_eq={fold_eq:.0%} ev={ev:+.1f}BB'
    )

    reasoning = (
        f'4-bet decision: {hero_hand} at {hero_position} vs {villain_position} 3-bet. '
        f'Category={cat}. 4-bet size={size:.1f}BB. '
        f'Dead money={dead_money:.1f}BB. Fold equity={fold_eq:.0%}. EV={ev:+.1f}BB. '
        f'Villain 3bet={villain_3bet_pct:.0%} fold_to_4bet={villain_fold_to_4bet:.0%}. '
        f'Decision: {action}.'
    )

    tips = []

    tips.append(
        f'4-BET SIZING: {size:.1f}BB ({size/three_bet_size_bb:.1f}x the 3-bet of {three_bet_size_bb:.1f}BB). '
        f'Dead money in pot: {dead_money:.1f}BB. '
        f'IP size: 2.5x; OOP size: 3x. '
        f'If SPR after 4-bet < 2: consider shoving all-in instead.'
    )

    if cat == 'bluff':
        tips.append(
            f'BLUFF 4-BET: {hero_hand} has ace/king blocker. '
            f'Fold equity={fold_eq:.0%}: EV={ev:+.1f}BB. '
            f'Ace blockers reduce villain\'s AA combos from 6 to 3. '
            f'Only bluff when villain 3-bets wide ({villain_3bet_pct:.0%} >= 10%).'
        )
    elif cat == 'value':
        tips.append(
            f'VALUE 4-BET: {hero_hand} is a premium hand. '
            f'4-bet to build pot vs villain\'s KK/QQ/AK range. '
            f'Villain 3-bet={villain_3bet_pct:.0%}: their 3-bet range likely has {villain_3bet_pct * 100:.0f}% bluffs + {(1-villain_3bet_pct)*100:.0f}% value.'
        )
    elif cat == 'flat':
        tips.append(
            f'FLAT CALL: {hero_hand} is best played by calling the 3-bet. '
            f'Hand has good equity vs villain\'s range but risks being dominated when 4-bet. '
            f'Calling lets you see a flop and realize equity in position.'
        )

    if villain_fold_to_4bet >= 0.60:
        tips.append(
            f'EXPLOITABLE FOLDER (fold_to_4bet={villain_fold_to_4bet:.0%}): '
            f'Increase 4-bet bluff frequency. '
            f'Villain folds >60% to 4-bets -- profitable to 4-bet wider. '
            f'Add A2s-A5s, KQs to your 4-bet bluff range.'
        )

    if villain_3bet_pct <= 0.06:
        tips.append(
            f'TIGHT 3-BETTOR ({villain_3bet_pct:.0%}): Respect their range. '
            f'Villain 3-bets only premium hands -- avoid 4-bet bluffs. '
            f'Only 4-bet AA/KK for value. Fold or flat everything else.'
        )

    if hero_history_4bet <= 0.01:
        tips.append(
            f'TIGHT 4-BET IMAGE (history={hero_history_4bet:.0%}): '
            f'Villain will respect your 4-bets. '
            f'Consider adding one bluff 4-bet to balance your range. '
            f'Your tight image makes both value and bluff 4-bets more effective.'
        )

    return FourBetDecision(
        hero_hand=hero_hand,
        hero_position=hero_position,
        villain_position=villain_position,
        villain_3bet_pct=villain_3bet_pct,
        villain_fold_to_4bet=villain_fold_to_4bet,
        three_bet_size_bb=three_bet_size_bb,
        stack_bb=stack_bb,
        hero_history_4bet=hero_history_4bet,
        pot_bb=pot_bb,
        hand_category=cat,
        four_bet_size_bb=size,
        fold_equity=fold_eq,
        four_bet_ev=ev,
        should_four_bet=do_4bet,
        dead_money_bb=dead_money,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def fbrb_one_liner(r: FourBetDecision) -> str:
    action = 'FOUR_BET' if r.should_four_bet else ('FLAT' if r.hand_category == 'flat' else 'FOLD')
    return (
        f'[FBRB {r.hero_hand}|{r.hero_position}] '
        f'{action} {r.four_bet_size_bb:.1f}BB '
        f'| cat={r.hand_category} ev={r.four_bet_ev:+.1f}BB fold={r.fold_equity:.0%}'
    )
