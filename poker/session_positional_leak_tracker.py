"""
Session Positional Leak Tracker (session_positional_leak_tracker.py)

Tracks hero's EV (winrate) broken down by position over a session and
identifies which positions are leaking money. Many players have strong
stats in BTN/CO but hemorrhage chips in EP or SB.

POSITIONS: EP, MP, CO, BTN, SB, BB

KEY METRICS PER POSITION:
  VPIP:      Voluntary put $ in pot — should be tightest in EP, widest in BTN
  PFR:       Pre-flop raise % — should scale with position
  Win rate:  BB/100 at this position — positive expected in BTN/CO; SB often negative
  WTSD:      Went to showdown — high is passive (calling too much)
  W$SD:      Won $ at showdown — low means calling too wide (going to SD and losing)

GTO VPIP/PFR TARGETS (6-max):
  EP:  VPIP 14-18%, PFR 10-14%
  MP:  VPIP 18-22%, PFR 13-17%
  CO:  VPIP 22-28%, PFR 16-22%
  BTN: VPIP 38-48%, PFR 26-35%
  SB:  VPIP 40-55%, PFR 28-40%   (many limps → high VPIP; wide 3-bet)
  BB:  VPIP 65-75% (defense), PFR 10-20%

EXPECTED WIN RATE (6-max, 200NL player):
  EP:  -3 to +1 BB/100   (cost of being out of position)
  MP:  -1 to +3 BB/100
  CO:  +1 to +5 BB/100
  BTN: +5 to +15 BB/100  (most profitable seat)
  SB:  -5 to -1 BB/100   (out of position for all post-flop)
  BB:  -3 to +1 BB/100   (defending blind)

LEAK DETECTION:
  Negative BB/100 when GTO says positive → leak
  Large VPIP-PFR spread → calling too often (not 3-betting enough)
  Low W$SD → calling down too wide

DISTINCT FROM OTHER MODULES:
  positional_awareness.py:  Per-hand positional advice
  hud_overlay.py:           Live stat display
  THIS MODULE:              End-of-session leak ANALYSIS across positions;
                            detects systematic leaks; gives fix priority list

Usage:
    from poker.session_positional_leak_tracker import track_positional_leaks, PositionalLeakReport, plt_one_liner

    result = track_positional_leaks(
        ep_stats=dict(hands=80, bb_won=-2.1, vpip=0.18, pfr=0.12, wtsd=0.28, wsd=0.49),
        mp_stats=dict(hands=70, bb_won=1.5, vpip=0.22, pfr=0.16, wtsd=0.30, wsd=0.51),
        co_stats=dict(hands=65, bb_won=3.2, vpip=0.35, pfr=0.20, wtsd=0.29, wsd=0.50),
        btn_stats=dict(hands=90, bb_won=8.5, vpip=0.50, pfr=0.38, wtsd=0.27, wsd=0.52),
        sb_stats=dict(hands=55, bb_won=-8.0, vpip=0.62, pfr=0.22, wtsd=0.38, wsd=0.44),
        bb_stats=dict(hands=85, bb_won=-1.5, vpip=0.70, pfr=0.14, wtsd=0.32, wsd=0.50),
    )
    print(plt_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# --------------------------------------------------------------------------
# GTO baselines (6-max)
# --------------------------------------------------------------------------

GTO_VPIP = {'EP': 0.16, 'MP': 0.20, 'CO': 0.25, 'BTN': 0.43, 'SB': 0.47, 'BB': 0.70}
GTO_PFR  = {'EP': 0.12, 'MP': 0.15, 'CO': 0.19, 'BTN': 0.31, 'SB': 0.34, 'BB': 0.15}
EXPECTED_WIN_RATE = {'EP': -1.0, 'MP': 1.0, 'CO': 3.0, 'BTN': 8.0, 'SB': -3.0, 'BB': -1.5}

# Minimum hands for reliable stats
MIN_HANDS = 50


def _leak_score(position: str, bb_won: float, vpip: float, pfr: float, wtsd: float, wsd: float) -> float:
    """
    Score for how much a position is leaking (higher = worse).
    Returns 0 if no significant leak detected.
    """
    score = 0.0
    gto_win = EXPECTED_WIN_RATE.get(position, 0.0)
    gto_vp = GTO_VPIP.get(position, 0.20)
    gto_pf = GTO_PFR.get(position, 0.15)

    # Win rate below expected
    win_shortfall = gto_win - bb_won
    if win_shortfall > 0:
        score += min(10.0, win_shortfall * 0.5)

    # VPIP deviation
    vpip_dev = abs(vpip - gto_vp)
    if vpip_dev >= 0.05:
        score += vpip_dev * 5.0

    # VPIP-PFR spread (calling gap): too wide = limping/calling too often
    calling_gap = vpip - pfr
    gto_gap = gto_vp - gto_pf
    excess_gap = calling_gap - gto_gap
    if excess_gap >= 0.08:
        score += excess_gap * 8.0

    # W$SD (low = losing at showdown = calling too wide)
    if wsd < 0.46:
        score += (0.46 - wsd) * 20.0

    return round(score, 2)


def _position_assessment(position: str, hands: int, bb_won: float, vpip: float,
                          pfr: float, wtsd: float, wsd: float) -> dict:
    gto_win = EXPECTED_WIN_RATE.get(position, 0.0)
    gto_vp = GTO_VPIP.get(position, 0.20)
    gto_pf = GTO_PFR.get(position, 0.15)

    leaks = []
    if hands < MIN_HANDS:
        return {
            'position': position, 'hands': hands, 'bb_won': bb_won,
            'vpip': vpip, 'pfr': pfr, 'wtsd': wtsd, 'wsd': wsd,
            'leaks': ['Insufficient sample size'], 'leak_score': 0.0,
            'reliable': False,
        }

    # Win rate leak
    if bb_won < gto_win - 3.0:
        leaks.append(
            f'Win rate {bb_won:.1f}BB/100 well below expected {gto_win:.0f}BB/100 '
            f'(gap={bb_won-gto_win:.1f}BB/100)'
        )

    # Over-VPIP leak
    if vpip > gto_vp + 0.07:
        leaks.append(
            f'VPIP too wide: {vpip:.0%} vs GTO {gto_vp:.0%}. '
            f'Fold more marginal hands pre-flop in {position}.'
        )
    elif vpip < gto_vp - 0.07:
        leaks.append(
            f'VPIP too tight: {vpip:.0%} vs GTO {gto_vp:.0%}. '
            f'Open/call more hands in {position} (leaving EV on table).'
        )

    # Calling gap (VPIP - PFR too large → not 3-betting enough)
    calling_gap = vpip - pfr
    gto_gap = gto_vp - gto_pf
    if calling_gap - gto_gap >= 0.10:
        leaks.append(
            f'Calling gap too large: VPIP-PFR={calling_gap:.0%} vs GTO {gto_gap:.0%}. '
            f'3-bet more hands instead of just calling opens from {position}.'
        )

    # W$SD low → calling down too wide
    if wsd < 0.47:
        leaks.append(
            f'W$SD={wsd:.0%} (below 47%): Going to showdown and losing too often. '
            f'Fold more on the turn/river when villain shows strength. '
            f'Bluff catch less without good blockers.'
        )
    elif wsd > 0.58:
        leaks.append(
            f'W$SD={wsd:.0%} (above 58%): Winning at showdown but possibly folding too much earlier. '
            f'Add more bluff-catches; you may be too tight before showdown.'
        )

    # WTSD high → calling stations
    if wtsd > 0.38 and position in ('EP', 'MP', 'CO'):
        leaks.append(
            f'WTSD={wtsd:.0%} in {position}: Going to showdown too often OOP. '
            f'Fold more on rivers when OOP and facing bets.'
        )

    score = _leak_score(position, bb_won, vpip, pfr, wtsd, wsd)
    return {
        'position': position, 'hands': hands, 'bb_won': bb_won,
        'vpip': vpip, 'pfr': pfr, 'wtsd': wtsd, 'wsd': wsd,
        'leaks': leaks, 'leak_score': score, 'reliable': True,
    }


@dataclass
class PositionalLeakReport:
    # Per-position stats
    position_data: Dict[str, dict]   # position → assessment dict

    # Ranked leaks (most costly first)
    leak_ranking: List[str]          # positions ranked by leak_score
    top_leak_position: str
    top_leak_score: float

    # Overall
    total_bb_won: float
    avg_win_rate_bb100: float
    total_hands: int

    # Summary
    weakest_position: str
    strongest_position: str
    over_vpip_positions: List[str]  # positions where hero is too loose
    under_pfr_positions: List[str]  # positions where hero isn't raising enough

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def track_positional_leaks(
    ep_stats: Optional[dict] = None,
    mp_stats: Optional[dict] = None,
    co_stats: Optional[dict] = None,
    btn_stats: Optional[dict] = None,
    sb_stats: Optional[dict] = None,
    bb_stats: Optional[dict] = None,
) -> PositionalLeakReport:
    """
    Analyze hero's stats by position and identify leaks.

    Each stats dict should have keys:
        hands, bb_won (BB/100), vpip (0-1), pfr (0-1), wtsd (0-1), wsd (0-1)

    Returns:
        PositionalLeakReport
    """
    defaults = {'hands': 0, 'bb_won': 0.0, 'vpip': 0.20, 'pfr': 0.12, 'wtsd': 0.30, 'wsd': 0.50}

    raw = {
        'EP': ep_stats or defaults.copy(),
        'MP': mp_stats or defaults.copy(),
        'CO': co_stats or defaults.copy(),
        'BTN': btn_stats or defaults.copy(),
        'SB': sb_stats or defaults.copy(),
        'BB': bb_stats or defaults.copy(),
    }

    position_data = {}
    for pos, stats in raw.items():
        d = {**defaults, **stats}
        position_data[pos] = _position_assessment(
            pos, d['hands'], d['bb_won'], d['vpip'], d['pfr'], d['wtsd'], d['wsd']
        )

    # Rank by leak score (highest = most leaky)
    ranked = sorted(
        [p for p in position_data if position_data[p].get('reliable')],
        key=lambda p: -position_data[p]['leak_score']
    )
    top_leak = ranked[0] if ranked else 'EP'
    top_score = position_data[top_leak]['leak_score']

    # Overall stats
    total_hands = sum(d['hands'] for d in position_data.values())
    total_bb = sum(d['bb_won'] * d['hands'] / 100 for d in position_data.values() if d['hands'] > 0)
    avg_wr = round(total_bb / max(total_hands, 1) * 100, 2)

    # Strongest position
    scored = [(p, d['bb_won']) for p, d in position_data.items() if d['hands'] >= MIN_HANDS]
    strongest = max(scored, key=lambda x: x[1])[0] if scored else 'BTN'
    weakest = min(scored, key=lambda x: x[1])[0] if scored else 'SB'

    over_vpip = [
        p for p in position_data
        if position_data[p]['hands'] >= MIN_HANDS
        and position_data[p]['vpip'] > GTO_VPIP.get(p, 0.25) + 0.07
    ]
    under_pfr = [
        p for p in position_data
        if position_data[p]['hands'] >= MIN_HANDS
        and position_data[p]['pfr'] < GTO_PFR.get(p, 0.15) - 0.05
    ]

    reasoning = (
        f'Positional analysis: {total_hands} total hands across 6 positions. '
        f'Avg win rate={avg_wr:.1f}BB/100. '
        f'Top leak: {top_leak} (score={top_score:.1f}). '
        f'Strongest: {strongest}; Weakest: {weakest}. '
        f'Over-VPIP: {over_vpip or "none"}. Under-PFR: {under_pfr or "none"}.'
    )

    verdict = (
        f'[PLT leak={top_leak}|score={top_score:.1f}] '
        f'wr={avg_wr:.1f}BB/100 ({total_hands}h) | '
        f'best={strongest} worst={weakest}'
    )

    tips = []
    # Top 3 leak positions
    for pos in ranked[:3]:
        d = position_data[pos]
        if d['leaks']:
            tips.append(f'[{pos}] ' + '; '.join(d['leaks'][:2]))

    if over_vpip:
        tips.append(
            f'OVER-PLAYING POSITIONS: {", ".join(over_vpip)}. '
            f'Tighten pre-flop ranges — you are paying too many bad odds to see flops.'
        )
    if under_pfr:
        tips.append(
            f'UNDER-RAISING: {", ".join(under_pfr)} — raise more pre-flop to gain initiative. '
            f'3-bet instead of flat-calling opens; pick up more pre-flop fold equity.'
        )

    btn_data = position_data.get('BTN', {})
    if btn_data.get('hands', 0) >= MIN_HANDS and btn_data.get('bb_won', 0) < 4.0:
        tips.append(
            f'BTN WIN RATE LOW ({btn_data["bb_won"]:.1f}BB/100): '
            f'BTN should be your most profitable seat (+5 to +15 BB/100). '
            f'Steal more (40%+ open), defend aggressively, apply IP pressure post-flop.'
        )

    sb_data = position_data.get('SB', {})
    if sb_data.get('hands', 0) >= MIN_HANDS and sb_data.get('bb_won', 0) < -8.0:
        tips.append(
            f'SB IS BLEEDING CHIPS ({sb_data["bb_won"]:.1f}BB/100): '
            f'SB is always OOP post-flop. '
            f'Increase 3-bet frequency to force fold equity pre-flop. '
            f'Limp/call less; 3-bet/fold or complete vs weak BTN opens.'
        )

    return PositionalLeakReport(
        position_data=position_data,
        leak_ranking=ranked,
        top_leak_position=top_leak,
        top_leak_score=top_score,
        total_bb_won=round(total_bb, 2),
        avg_win_rate_bb100=avg_wr,
        total_hands=total_hands,
        weakest_position=weakest,
        strongest_position=strongest,
        over_vpip_positions=over_vpip,
        under_pfr_positions=under_pfr,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def plt_one_liner(r: PositionalLeakReport) -> str:
    return (
        f'[PLT leak={r.top_leak_position}|score={r.top_leak_score:.1f}] '
        f'wr={r.avg_win_rate_bb100:.1f}BB/100 ({r.total_hands}h) | '
        f'best={r.strongest_position} worst={r.weakest_position}'
    )
