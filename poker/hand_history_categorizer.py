"""
Hand History Categorizer (hand_history_categorizer.py)

Tracks how hero plays each hand category across sessions to identify
leaks and opportunities. Answers: "Do I overfold top pair? Do I bluff
too much with air? How profitable am I with flush draws?"

THEORY:
  Even without a HUD, tracking your own patterns reveals exploitable leaks:
  - Top pair: are you folding too often to aggression?
  - Sets: are you slow-playing too much (missing value)?
  - Draws: are you chasing too many unprofitable draws?
  - Air: are you bluffing into calling stations at the wrong frequency?
  - Nut hands: are you maximizing value?

  By categorizing outcomes (win/loss/fold), hero can identify:
  1. Under-valued hands (folding when should call)
  2. Over-played hands (calling/raising when should fold)
  3. EV leaks from specific hand categories
  4. Bankroll volatility by hand type

TRACKING MODEL:
  For each hand_category, we track:
  - Times played (saw flop with this category)
  - Times won (at showdown or villain folded)
  - Times folded (hero folded even though might have won)
  - Times lost (hero called/raised and lost)
  - Net BB won/lost

  DERIVED STATISTICS:
  - Win rate (wins / played)
  - BB/100 by hand type (profit per 100 hands with this category)
  - Fold rate (folds / played)
  - Mistake indicator: if fold_rate > expected_fold_rate for hand type

EXPECTED FOLD RATES (approximate):
  Nuts/sets: fold_rate < 5%  (should almost never fold strong hands)
  Two pair: fold_rate < 15%  (fold only to large multiway raises)
  Top pair: fold_rate 20-30% (fold to 3-street pressure occasionally)
  Middle pair: fold_rate 35-50% (fold to significant aggression)
  Draws: fold_rate 15-25%  (continue with right odds)
  Air: fold_rate 60-75%    (most air should be folded unless bluffing)

LEAK DETECTION:
  A hand category is a "leak" if:
  1. Fold rate significantly above expected -> hero over-folding
  2. Win rate significantly below average -> hero over-playing weak hands
  3. Negative BB/100 for a hand that should be +EV (sets, top pair)
  4. Loss rate > 50% for draws -> chasing without right odds

DISTINCT FROM:
  session_exploit_tracker.py:  Tracks VILLAIN patterns session-level
  bayesian_villain_model.py:   Villain range tracking
  THIS MODULE:                 Tracks HERO's own play patterns by hand
                               category; leak detection; win-rate analysis
                               for self-improvement.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Expected fold rates per hand category
EXPECTED_FOLD_RATE: Dict[str, float] = {
    'nuts':       0.02,
    'full_house': 0.03,
    'flush':      0.05,
    'straight':   0.06,
    'set':        0.04,
    'two_pair':   0.12,
    'overpair':   0.15,
    'top_pair':   0.25,
    'top_pair_wk': 0.35,
    'middle_pair': 0.42,
    'low_pair':   0.52,
    'flush_draw': 0.20,
    'combo_draw': 0.15,
    'oesd':       0.22,
    'gutshot':    0.35,
    'air':        0.68,
}

# Expected win rates at showdown (equity-based)
EXPECTED_WIN_RATE: Dict[str, float] = {
    'nuts':       0.97,
    'full_house': 0.94,
    'flush':      0.86,
    'straight':   0.82,
    'set':        0.87,
    'two_pair':   0.73,
    'overpair':   0.68,
    'top_pair':   0.62,
    'top_pair_wk': 0.54,
    'middle_pair': 0.47,
    'low_pair':   0.40,
    'flush_draw': 0.38,  # before hit/miss
    'combo_draw': 0.52,
    'oesd':       0.35,
    'gutshot':    0.28,
    'air':        0.15,
}


def _detect_leak(
    hand_category: str,
    times_played: int,
    times_won: int,
    times_folded: int,
    bb_net: float,
) -> str:
    if times_played < 5:
        return 'insufficient_sample'
    win_rate = times_won / max(1, times_played - times_folded)
    fold_rate = times_folded / max(1, times_played)
    expected_fold = EXPECTED_FOLD_RATE.get(hand_category, 0.30)
    expected_win = EXPECTED_WIN_RATE.get(hand_category, 0.50)
    bb_per_hand = bb_net / max(1, times_played)

    # Over-folding
    if fold_rate > expected_fold * 1.5:
        return 'over_folding'
    # Under-folding (calling too much)
    if fold_rate < expected_fold * 0.5 and win_rate < expected_win * 0.8:
        return 'over_calling'
    # Losing money with strong hands
    if hand_category in ('set', 'flush', 'two_pair', 'straight') and bb_per_hand < -2.0:
        return 'not_extracting_value'
    # Winning rate too low (playing badly)
    if win_rate < expected_win * 0.70:
        return 'poor_win_rate'
    return 'no_leak'


def _bb_per_100(bb_net: float, times_played: int) -> float:
    if times_played == 0:
        return 0.0
    return round((bb_net / times_played) * 100, 1)


@dataclass
class HandCategoryStats:
    hand_category: str
    times_played: int
    times_won: int
    times_lost: int
    times_folded: int
    bb_net: float

    win_rate: float
    fold_rate: float
    bb_per_100_hands: float
    leak_type: str

    expected_fold_rate: float
    expected_win_rate: float


@dataclass
class HandHistoryReport:
    hand_stats: Dict[str, HandCategoryStats]
    total_hands: int
    total_bb_net: float
    worst_leak: str
    worst_leak_category: str
    best_category: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def _build_stats(
    hand_category: str,
    times_played: int,
    times_won: int,
    times_lost: int,
    times_folded: int,
    bb_net: float,
) -> HandCategoryStats:
    win_rate = round(times_won / max(1, times_played - times_folded), 3)
    fold_rate = round(times_folded / max(1, times_played), 3)
    bb100 = _bb_per_100(bb_net, times_played)
    leak = _detect_leak(hand_category, times_played, times_won, times_folded, bb_net)
    return HandCategoryStats(
        hand_category=hand_category,
        times_played=times_played,
        times_won=times_won,
        times_lost=times_lost,
        times_folded=times_folded,
        bb_net=bb_net,
        win_rate=win_rate,
        fold_rate=fold_rate,
        bb_per_100_hands=bb100,
        leak_type=leak,
        expected_fold_rate=EXPECTED_FOLD_RATE.get(hand_category, 0.30),
        expected_win_rate=EXPECTED_WIN_RATE.get(hand_category, 0.50),
    )


def analyze_hand_history(
    hand_data: Optional[Dict[str, dict]] = None,
) -> HandHistoryReport:
    """
    Analyze hero's hand history across categories.

    Args:
        hand_data:  Dict mapping hand_category -> dict with keys:
                    {played, won, lost, folded, bb_net}
                    If None, uses sample data for demonstration.

    Returns:
        HandHistoryReport
    """
    if hand_data is None:
        hand_data = {
            'top_pair':    {'played': 50, 'won': 28, 'lost': 8, 'folded': 14, 'bb_net': 45.0},
            'middle_pair': {'played': 35, 'won': 14, 'lost': 10, 'folded': 11, 'bb_net': -8.0},
            'flush_draw':  {'played': 25, 'won': 10, 'lost': 7, 'folded': 8, 'bb_net': 12.0},
            'set':         {'played': 12, 'won': 11, 'lost': 1, 'folded': 0, 'bb_net': 85.0},
            'air':         {'played': 30, 'won': 8, 'lost': 5, 'folded': 17, 'bb_net': -15.0},
        }

    stats: Dict[str, HandCategoryStats] = {}
    for cat, d in hand_data.items():
        stats[cat] = _build_stats(
            cat,
            d.get('played', 0),
            d.get('won', 0),
            d.get('lost', 0),
            d.get('folded', 0),
            d.get('bb_net', 0.0),
        )

    total_hands = sum(s.times_played for s in stats.values())
    total_bb = sum(s.bb_net for s in stats.values())

    # Find worst leak
    leaked = [(cat, s) for cat, s in stats.items() if s.leak_type not in ('no_leak', 'insufficient_sample')]
    if leaked:
        worst_cat, worst_stat = min(leaked, key=lambda x: x[1].bb_per_100_hands)
        worst_leak = worst_stat.leak_type
    else:
        worst_cat = 'none'
        worst_leak = 'no_leak'

    # Find best category by bb/100
    if stats:
        best_cat = max(stats.keys(), key=lambda c: stats[c].bb_per_100_hands)
    else:
        best_cat = 'none'

    verdict = (
        f'[HHC {total_hands} hands] '
        f'net={total_bb:+.1f}BB | '
        f'worst_leak={worst_leak}({worst_cat}) | '
        f'best={best_cat}'
    )

    reasoning = (
        f'Hand history analysis: {total_hands} total hands tracked. '
        f'Net: {total_bb:+.1f}BB. '
        f'Categories tracked: {list(stats.keys())}. '
        f'Worst leak: {worst_leak} in {worst_cat}. '
        f'Best category: {best_cat} ({stats[best_cat].bb_per_100_hands:+.0f}BB/100).'
        if stats else 'No data.'
    )

    tips = []

    for cat, s in stats.items():
        if s.leak_type == 'over_folding':
            tips.append(
                f'LEAK OVER_FOLD [{cat}]: fold_rate={s.fold_rate:.0%} vs expected {s.expected_fold_rate:.0%}. '
                f'You are folding {cat} too often. '
                f'Call more aggressively; villain may be bluffing.'
            )
        elif s.leak_type == 'over_calling':
            tips.append(
                f'LEAK OVER_CALL [{cat}]: win_rate={s.win_rate:.0%} vs expected {s.expected_win_rate:.0%}. '
                f'You are calling too much with {cat}. '
                f'Tighten up; fold earlier to large bets.'
            )
        elif s.leak_type == 'not_extracting_value':
            tips.append(
                f'LEAK VALUE [{cat}]: strong hand losing money (bb/100={s.bb_per_100_hands:+.0f}). '
                f'Played {s.times_played} times, won {s.times_won}. '
                f'Bet larger/faster with {cat}; stop slow-playing.'
            )
        elif s.leak_type == 'poor_win_rate':
            tips.append(
                f'LEAK WIN_RATE [{cat}]: win_rate={s.win_rate:.0%} vs expected {s.expected_win_rate:.0%}. '
                f'Consistently losing with {cat}. '
                f'Review when/how you enter pots with this hand.'
            )

    if not tips and stats:
        tips.append(
            f'NO MAJOR LEAKS: All tracked categories within expected ranges. '
            f'Best category: {best_cat} at {stats[best_cat].bb_per_100_hands:+.0f}BB/100. '
            f'Continue tracking to accumulate more data.'
        )

    tips.append(
        f'OVERALL: {total_hands} hands tracked. '
        f'Net: {total_bb:+.1f}BB ({_bb_per_100(total_bb, total_hands):+.0f}BB/100 overall). '
        f'Focus improvement on: {worst_cat} ({worst_leak}).'
    )

    return HandHistoryReport(
        hand_stats=stats,
        total_hands=total_hands,
        total_bb_net=total_bb,
        worst_leak=worst_leak,
        worst_leak_category=worst_cat,
        best_category=best_cat,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def hhc_one_liner(r: HandHistoryReport) -> str:
    return (
        f'[HHC {r.total_hands}h] '
        f'net={r.total_bb_net:+.1f}BB | '
        f'leak={r.worst_leak}@{r.worst_leak_category} | '
        f'best={r.best_category}'
    )
