"""
Villain Tendency Report (villain_tendency_report.py)

Synthesizes HUD statistics into a prioritized, actionable report of
specific line adjustments against a particular villain. Unlike `exploit.py`
which gives a general exploit profile, this module produces per-street
concrete instruction: "check-raise flop more", "never bluff-catch river",
"iso-raise pre when in position".

Key difference from existing modules:
  - exploit.py: general multipliers (value_size_mult, bluff_mult, etc.)
  - exploit_adapter.py: 3-5 generic adjustments
  - villain_tendency_report.py: per-street instructions with specific
    frequencies, sizing suggestions, and rationale per leak

Covered HUD leaks:
  1. VPIP > 50%: call wide → extract value, never bluff
  2. PFR/VPIP ratio < 0.3: limp-heavy → iso-raise, expect weakness post
  3. WTSD > 40%: showdown donkey → thin value bet every street, no bluffs
  4. WTSD < 20%: folds too much → bluff every street with range
  5. FCBet > 70%: folds to cbets → always bet flop regardless of hand
  6. CBet > 80%: over-cbets → raise more, float more
  7. CBet < 30%: under-cbets → steal turn aggressively when checked to
  8. 3Bet% < 3%: never 3-bets → steal wider, open all marginal hands
  9. 3Bet% > 12%: 3-bets too wide → 4-bet lighter, flat more premiums
  10. Fold to 3Bet% > 70%: folds to 3-bets → 3-bet polarized range wide
  11. AF > 3.5: hyper-aggressive → check-raise more, call down lighter
  12. AF < 0.5: very passive → thin-value bet every street, no bluffs

Usage:
    from poker.villain_tendency_report import generate_tendency_report, VillainReport
    result = generate_tendency_report(
        vpip=0.55, pfr=0.12, threeb_pct=0.03,
        fold_to_3b=0.72, cbet_pct=0.82, fold_to_cbet=0.65,
        af=0.8, wtsd=0.42, hands=80,
    )
    for line in result.priority_adjustments:
        print(line)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TendencyLeak:
    """A single detected tendency with actionable adjustments."""
    stat_name: str      # e.g. 'VPIP', 'FCBet'
    stat_value: float
    severity: str       # 'critical', 'major', 'minor'
    adjustment: str     # what hero should do
    ev_impact: str      # qualitative EV impact
    street: str         # 'preflop', 'flop', 'turn', 'river', 'all'


@dataclass
class VillainReport:
    """Complete villain tendency report."""
    hands: int
    confidence: str     # 'high', 'medium', 'low'

    # Player type
    player_type: str
    player_type_note: str

    # Detected leaks sorted by priority
    leaks: List[TendencyLeak]

    # Top 5 priority adjustments (plain text)
    priority_adjustments: List[str]

    # Per-street summary
    preflop_strategy: str
    flop_strategy: str
    turn_strategy: str
    river_strategy: str

    one_liner: str = ''


def _confidence(hands: int) -> str:
    if hands >= 100:
        return 'high'
    if hands >= 40:
        return 'medium'
    return 'low'


def _player_type(vpip: float, pfr: float, af: float, wtsd: float) -> tuple:
    aggr = pfr / vpip if vpip > 0 else 0
    if vpip < 0.20 and pfr / max(vpip, 0.01) > 0.70:
        return ('nit', 'Very tight, mostly premium hands. Respect their raises.')
    if vpip > 0.45 and af < 1.0:
        return ('calling_station', 'Loose passive. Never bluff; value bet every street.')
    if vpip > 0.45 and af >= 2.0:
        return ('loose_aggressive', 'LAG. Let them bluff; check-raise strong hands.')
    if vpip < 0.25 and af >= 2.0:
        return ('tag', 'Tight-aggressive. Respect 3-bets; fight for pots in position.')
    if vpip > 0.30 and pfr < 0.10:
        return ('fish', 'Loose passive fish. Isolate preflop; extract value post.')
    if vpip > 0.35 and af >= 3.0:
        return ('maniac', 'Maniac. Trap with strong hands; call down lighter.')
    return ('reg', 'Regular player. Standard exploits apply.')


def _detect_leaks(
    vpip: float, pfr: float, threeb_pct: float,
    fold_to_3b: float, cbet_pct: float, fold_to_cbet: float,
    af: float, wtsd: float,
) -> List[TendencyLeak]:
    leaks: List[TendencyLeak] = []

    # --- PREFLOP ---
    if vpip > 0.50:
        leaks.append(TendencyLeak(
            'VPIP', vpip, 'critical',
            f'Isolate pre with any decent hand (ATo+, 66+). '
            f'Never bluff post-flop — value bet every pair.',
            'very_high', 'preflop',
        ))
    pfr_ratio = pfr / vpip if vpip > 0 else 0
    if pfr_ratio < 0.30 and vpip > 0.30:
        leaks.append(TendencyLeak(
            'PFR/VPIP', pfr_ratio, 'major',
            f'Limp-heavy player (PFR/VPIP={pfr_ratio:.0%}). '
            f'ISO-raise 3-4x with any hand in your range. '
            f'Post-flop range is weak — bet for value aggressively.',
            'high', 'preflop',
        ))
    if threeb_pct < 0.03 and vpip > 0.20:
        leaks.append(TendencyLeak(
            '3bet%', threeb_pct, 'major',
            f'Almost never 3-bets ({threeb_pct:.0%}). '
            f'Open wider in their blind spots. '
            f'Their flat-calling range is often capped (no AA/KK).',
            'high', 'preflop',
        ))
    if threeb_pct > 0.12:
        leaks.append(TendencyLeak(
            '3bet%', threeb_pct, 'major',
            f'3-bets very wide ({threeb_pct:.0%}). '
            f'4-bet-value with QQ+, AK. Flat JJ/TT/AQs in position. '
            f'Stop open-folding — they are bluffing frequently.',
            'high', 'preflop',
        ))
    if fold_to_3b > 0.70:
        leaks.append(TendencyLeak(
            'Fold3B', fold_to_3b, 'critical',
            f'Folds to 3-bets {fold_to_3b:.0%} of the time. '
            f'3-bet any two cards in position. '
            f'Widen 3-bet range to all suited Ax, any Broadway.',
            'very_high', 'preflop',
        ))
    if fold_to_3b < 0.35:
        leaks.append(TendencyLeak(
            'Fold3B', fold_to_3b, 'minor',
            f'Calls 3-bets too wide ({1-fold_to_3b:.0%} call). '
            f'3-bet for value only (strong hands). '
            f'They will pay off your value range post-flop.',
            'medium', 'preflop',
        ))

    # --- FLOP ---
    if fold_to_cbet > 0.65:
        leaks.append(TendencyLeak(
            'FCBet', fold_to_cbet, 'critical',
            f'Folds to c-bets {fold_to_cbet:.0%}. '
            f'C-bet every flop regardless of hand. '
            f'Use 33-40% pot sizing — do not need to bet large.',
            'very_high', 'flop',
        ))
    if cbet_pct > 0.75:
        leaks.append(TendencyLeak(
            'CBet%', cbet_pct, 'major',
            f'C-bets too often ({cbet_pct:.0%}). '
            f'Check-raise strong hands and draws. '
            f'Float with good hands — their flop range is wide/weak.',
            'high', 'flop',
        ))
    if cbet_pct < 0.30:
        leaks.append(TendencyLeak(
            'CBet%', cbet_pct, 'minor',
            f'Rarely c-bets ({cbet_pct:.0%}). '
            f'Bet turn/probe when they check twice. '
            f'Their check range is often balanced (has strong hands).',
            'medium', 'flop',
        ))

    # --- ALL STREETS ---
    if wtsd > 0.40:
        leaks.append(TendencyLeak(
            'WTSD', wtsd, 'critical',
            f'Goes to showdown {wtsd:.0%} — calling station. '
            f'Thin value bet every street with any pair+. '
            f'Zero bluffs. Bet 70-80% pot for max value.',
            'very_high', 'all',
        ))
    if wtsd < 0.20:
        leaks.append(TendencyLeak(
            'WTSD', wtsd, 'major',
            f'Only goes to showdown {wtsd:.0%} — over-folds. '
            f'Triple barrel with all semi-bluffs. '
            f'River bluff with any reasonable blockers.',
            'high', 'all',
        ))
    if af > 3.5:
        leaks.append(TendencyLeak(
            'AF', af, 'major',
            f'Aggression factor {af:.1f} — hyper-aggressive. '
            f'Check-raise strong hands to build pot. '
            f'Call down lighter (they bluff too often).',
            'high', 'all',
        ))
    if af < 0.5:
        leaks.append(TendencyLeak(
            'AF', af, 'major',
            f'Aggression factor {af:.1f} — extremely passive. '
            f'Bet every street for value — they will not raise. '
            f'Never bluff (they call everything, never fold).',
            'high', 'all',
        ))

    # Sort by severity
    order = {'critical': 0, 'major': 1, 'minor': 2}
    leaks.sort(key=lambda x: order.get(x.severity, 3))
    return leaks


def _per_street(leaks: List[TendencyLeak], vpip: float, pfr: float,
                af: float, wtsd: float, fold_to_cbet: float,
                cbet_pct: float, fold_to_3b: float) -> tuple:
    """Summarize strategy by street."""
    pre = []
    if fold_to_3b > 0.65:
        pre.append(f'3-bet wide (fold_to_3b={fold_to_3b:.0%})')
    if vpip > 0.45:
        pre.append(f'ISO-raise limpers (VPIP={vpip:.0%})')
    if not pre:
        pre.append('Standard preflop — adjust by position')

    flop = []
    if fold_to_cbet > 0.65:
        flop.append(f'Cbet always (FCBet={fold_to_cbet:.0%}), 33-40%pot')
    if cbet_pct > 0.75:
        flop.append('Check-raise strong hands vs frequent cbets')
    if not flop:
        flop.append('Standard flop play')

    turn = []
    if wtsd < 0.25:
        turn.append('Barrel turn wide — they fold too often')
    if af < 0.5:
        turn.append('Bet turn thin — they never raise')
    if not turn:
        turn.append('Standard turn play')

    river = []
    if wtsd > 0.40:
        river.append('Never bluff river — value bet thin (any pair)')
    elif wtsd < 0.20:
        river.append('River bluff with blockers — they over-fold')
    if af > 3.5:
        river.append('Call down river — they over-bluff')
    if not river:
        river.append('Standard river play')

    return (
        ' | '.join(pre),
        ' | '.join(flop),
        ' | '.join(turn),
        ' | '.join(river),
    )


def generate_tendency_report(
    vpip: float = 0.30,
    pfr: float = 0.10,
    threeb_pct: float = 0.05,
    fold_to_3b: float = 0.55,
    cbet_pct: float = 0.55,
    fold_to_cbet: float = 0.45,
    af: float = 1.5,
    wtsd: float = 0.30,
    hands: int = 60,
) -> VillainReport:
    """
    Generate a comprehensive villain tendency report.

    Args:
        vpip:          Voluntarily put money in pot (0-1)
        pfr:           Preflop raise frequency (0-1)
        threeb_pct:    3-bet percentage (0-1)
        fold_to_3b:    Fold to 3-bet frequency (0-1)
        cbet_pct:      C-bet frequency (0-1)
        fold_to_cbet:  Fold to c-bet frequency (0-1)
        af:            Aggression factor
        wtsd:          Went to showdown (0-1)
        hands:         Sample size

    Returns:
        VillainReport
    """
    conf = _confidence(hands)
    ptype, pnote = _player_type(vpip, pfr, af, wtsd)
    leaks = _detect_leaks(vpip, pfr, threeb_pct, fold_to_3b,
                          cbet_pct, fold_to_cbet, af, wtsd)
    pre_s, flop_s, turn_s, river_s = _per_street(
        leaks, vpip, pfr, af, wtsd, fold_to_cbet, cbet_pct, fold_to_3b
    )

    priority = [f'[{l.stat_name}={l.stat_value:.0%}|{l.severity}] {l.adjustment}'
                for l in leaks[:5]]
    if not priority:
        priority = ['No major leaks detected — play balanced GTO strategy.']

    one_liner = (
        f'[VTR {ptype}] {len(leaks)} leaks | '
        f'top={leaks[0].stat_name if leaks else "none"} | '
        f'VPIP={vpip:.0%} AF={af:.1f} WTSD={wtsd:.0%}'
    )

    return VillainReport(
        hands=hands,
        confidence=conf,
        player_type=ptype,
        player_type_note=pnote,
        leaks=leaks,
        priority_adjustments=priority,
        preflop_strategy=pre_s,
        flop_strategy=flop_s,
        turn_strategy=turn_s,
        river_strategy=river_s,
        one_liner=one_liner,
    )


def villain_report_one_liner(result: VillainReport) -> str:
    return result.one_liner
