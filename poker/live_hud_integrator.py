"""
Live HUD Integrator (live_hud_integrator.py)

Combines ALL available villain stats into a unified HUD profile
and returns a single, prioritized action recommendation.

PURPOSE:
  In a live session, hero receives data from multiple sources:
  - VPIP / PFR (long-term stats from HUD or notes)
  - AF (aggression factor)
  - 3-bet frequency
  - Recent session patterns (fold streak, bet streak, etc.)
  - Recent betting lines (double barrel, check-check, etc.)

  This module integrates all of these into a single villain profile
  and returns the most important tactical insight for the current spot.

INTEGRATION LOGIC:
  Priority order (what overrides what):
  1. Showdown data (just showed big hand / bluff): immediately adjust
  2. Session-level patterns (last 10-30 hands): primary tactical guide
  3. Long-term HUD stats (VPIP/AF): secondary baseline
  4. Street-level weakness signals: fine-tuning
  When sources conflict, use the most recent/specific data.

VILLAIN ARCHETYPE:
  Combining VPIP + PFR + AF -> villain type:
  - VPIP>40, AF<1.5: Calling station (never bluff; bet thin value)
  - VPIP<20, AF<1.5: Nit (fold all draws vs 3-streets; they have it)
  - VPIP>35, AF>3:   Maniac (call wider; value bet bigger; trap)
  - VPIP 25-35, AF 2-3: Loose-passive (value bet; bluff sparingly)
  - VPIP<25, AF 2-3: Reg (GTO-ish; mixed strategies; study notes)
  - VPIP 25-35, PFR>15, AF>2: LAG (widen calling range; 3-bet bluffs ok)
  - VPIP<20, PFR>12: TAG (respect 3-bets; fold marginal vs big bet)

DISTINCT FROM:
  session_exploit_tracker.py:   Session patterns only
  bayesian_villain_model.py:    Bayesian range update
  villain_weakness_detector.py: Real-time weakness signals
  THIS MODULE:                  Full integration of ALL data sources
                                into a unified villain profile + single
                                recommended tactical adjustment.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


# Villain archetypes
ARCHETYPES: Dict[str, str] = {
    'calling_station':  'VPIP>40 AF<1.5: Never bluff. Bet thin value every street.',
    'nit':              'VPIP<20 AF<1.5: They have it when they bet. Fold to 3 streets.',
    'maniac':           'VPIP>35 AF>3: Call wider. Trap with big hands. Value bet big.',
    'loose_passive':    'VPIP>35 PFR<12: Bet value; bluff sparingly. They call too much.',
    'reg':              'VPIP 22-32 AF 2-2.8: GTO-ish. Use mixed strategies. Study patterns.',
    'lag':              'VPIP>28 PFR>15 AF>2: 3-bet bluffs OK. Call down lighter.',
    'tag':              'VPIP<22 PFR>12: Respect 3-bets. Fold marginal vs big bet.',
}

# Tactical adjustments per archetype
ARCHETYPE_ADJUSTMENTS: Dict[str, dict] = {
    'calling_station': {'bluff_freq': -0.40, 'value_size': +0.20, 'call_threshold': -0.05},
    'nit':             {'bluff_freq': +0.10, 'value_size': -0.10, 'call_threshold': +0.10},
    'maniac':          {'bluff_freq': -0.20, 'value_size': +0.30, 'call_threshold': -0.10},
    'loose_passive':   {'bluff_freq': -0.20, 'value_size': +0.15, 'call_threshold': -0.05},
    'reg':             {'bluff_freq': 0.00, 'value_size': 0.00, 'call_threshold': 0.00},
    'lag':             {'bluff_freq': -0.10, 'value_size': +0.10, 'call_threshold': -0.05},
    'tag':             {'bluff_freq': +0.10, 'value_size': 0.00, 'call_threshold': +0.08},
}


def _classify_archetype(
    vpip: float,
    pfr: float,
    af: float,
) -> str:
    if vpip >= 0.40 and af < 1.5:
        return 'calling_station'
    if vpip < 0.20 and af < 1.5:
        return 'nit'
    if vpip >= 0.35 and af > 3.0:
        return 'maniac'
    if vpip >= 0.28 and pfr >= 0.15 and af > 2.0:
        return 'lag'
    if vpip < 0.22 and pfr >= 0.12:
        return 'tag'
    if vpip >= 0.35:
        return 'loose_passive'
    return 'reg'


def _session_override(session_pattern: str, archetype_adjs: dict) -> dict:
    """Override archetype adjustments with session-specific patterns."""
    adjs = dict(archetype_adjs)
    if session_pattern == 'fold_streak':
        adjs['bluff_freq'] = min(0.35, adjs['bluff_freq'] + 0.25)
    elif session_pattern == 'call_streak':
        adjs['bluff_freq'] = max(-0.50, adjs['bluff_freq'] - 0.30)
        adjs['value_size'] = min(0.35, adjs['value_size'] + 0.15)
    elif session_pattern == 'bet_streak':
        adjs['call_threshold'] = max(-0.15, adjs['call_threshold'] - 0.08)
    elif session_pattern in ('big_value_showdown',):
        adjs['bluff_freq'] = max(-0.50, adjs['bluff_freq'] - 0.15)
        adjs['value_size'] = max(-0.15, adjs['value_size'] - 0.05)
    elif session_pattern == 'bluff_showdown':
        adjs['call_threshold'] = max(-0.20, adjs['call_threshold'] - 0.12)
    return adjs


def _compute_effective_adj(
    base_adj: dict,
    weakness_signals: list,
) -> dict:
    """Fine-tune with weakness signals."""
    adjs = dict(base_adj)
    if 'tiny_bet_sizing' in weakness_signals or 'check_check_multiway' in weakness_signals:
        adjs['bluff_freq'] = min(0.40, adjs['bluff_freq'] + 0.15)
    if 'bet_fold_history' in weakness_signals:
        adjs['bluff_freq'] = min(0.45, adjs['bluff_freq'] + 0.20)
    return adjs


def _top_insight(
    archetype: str,
    session_pattern: str,
    effective_adj: dict,
    board_texture: str,
    hand_category: str,
) -> str:
    """Single most important tactical insight for the current spot."""
    insights = []

    # Session pattern is highest priority
    if session_pattern == 'fold_streak':
        insights.append(f'FOLD STREAK: Exploit with bluffs (+{effective_adj["bluff_freq"]:+.0%} bluff freq).')
    elif session_pattern == 'call_streak':
        insights.append(f'CALL STREAK: Value bet big; never bluff ({effective_adj["bluff_freq"]:+.0%} bluff adj).')
    elif session_pattern == 'bet_streak':
        insights.append(f'BET STREAK: Trap; call wider (call_threshold {effective_adj["call_threshold"]:+.0%}).')

    # Archetype
    if archetype == 'calling_station':
        insights.append(f'CALLING STATION: Value bet every street. Size up ({effective_adj["value_size"]:+.0%} value adj).')
    elif archetype == 'maniac':
        insights.append(f'MANIAC: Trap big hands. Call lighter (+{-effective_adj["call_threshold"]:.0%} call adj).')
    elif archetype == 'nit':
        insights.append(f'NIT: Fold to 3 streets. Bluff only on scare cards (+{effective_adj["bluff_freq"]:.0%} adj).')

    # Board/hand-specific
    if board_texture == 'dry' and effective_adj['bluff_freq'] > 0.10:
        insights.append(f'DRY BOARD + bluff adj: semi-bluff or pure bluff +EV.')

    return insights[0] if insights else f'STANDARD PLAY ({archetype}): follow GTO adjustments.'


@dataclass
class HUDProfile:
    vpip: float
    pfr: float
    af: float
    three_bet_freq: float
    archetype: str
    archetype_description: str

    session_pattern: str
    weakness_signals: list

    effective_bluff_adj: float
    effective_value_adj: float
    effective_call_threshold_adj: float

    top_insight: str
    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def build_hud_profile(
    vpip: float = 0.28,
    pfr: float = 0.20,
    af: float = 2.0,
    three_bet_freq: float = 0.08,
    session_pattern: str = 'no_pattern',
    weakness_signals: Optional[list] = None,
    board_texture: str = 'dry',
    hand_category: str = 'top_pair',
    hero_position: str = 'ip',
) -> HUDProfile:
    """
    Build a unified HUD villain profile from all available data.

    Args:
        vpip:              Villain VPIP (0-1)
        pfr:               Villain PFR (0-1)
        af:                Villain aggression factor
        three_bet_freq:    Villain 3-bet frequency (0-1)
        session_pattern:   Current session pattern from session_exploit_tracker
        weakness_signals:  List of in-hand weakness signals
        board_texture:     Board texture
        hand_category:     Hero's current hand category
        hero_position:     'ip' / 'oop'

    Returns:
        HUDProfile
    """
    if weakness_signals is None:
        weakness_signals = []

    archetype = _classify_archetype(vpip, pfr, af)
    archetype_desc = ARCHETYPES.get(archetype, 'Unknown')
    base_adjs = ARCHETYPE_ADJUSTMENTS.get(archetype, {'bluff_freq': 0.0, 'value_size': 0.0, 'call_threshold': 0.0})

    session_adjs = _session_override(session_pattern, base_adjs)
    effective_adjs = _compute_effective_adj(session_adjs, weakness_signals)

    insight = _top_insight(archetype, session_pattern, effective_adjs, board_texture, hand_category)

    verdict = (
        f'[HUD {archetype}|{session_pattern}] '
        f'VPIP={vpip:.0%} PFR={pfr:.0%} AF={af:.1f} | '
        f'{insight[:60]}'
    )

    reasoning = (
        f'Villain: VPIP={vpip:.0%} PFR={pfr:.0%} AF={af:.1f} 3bet={three_bet_freq:.0%}. '
        f'Archetype: {archetype}. '
        f'Session pattern: {session_pattern}. '
        f'Weakness signals: {weakness_signals}. '
        f'Adjustments: bluff={effective_adjs["bluff_freq"]:+.0%}, '
        f'value={effective_adjs["value_size"]:+.0%}, '
        f'call={effective_adjs["call_threshold"]:+.0%}.'
    )

    tips = []

    tips.append(
        f'VILLAIN ARCHETYPE: {archetype}. '
        f'{archetype_desc} '
        f'(VPIP={vpip:.0%} PFR={pfr:.0%} AF={af:.1f}).'
    )

    tips.append(
        f'ADJUSTMENTS: bluff_freq {effective_adjs["bluff_freq"]:+.0%}, '
        f'value_size {effective_adjs["value_size"]:+.0%}, '
        f'call_threshold {effective_adjs["call_threshold"]:+.0%}. '
        f'Session override: {session_pattern}.'
    )

    tips.append(
        f'TOP INSIGHT: {insight}'
    )

    if three_bet_freq >= 0.15:
        tips.append(
            f'HIGH 3-BET ({three_bet_freq:.0%}): Open smaller; add 4-bet bluff range. '
            f'Do not cold-call without plan vs re-4-bet.'
        )
    elif three_bet_freq <= 0.04:
        tips.append(
            f'LOW 3-BET ({three_bet_freq:.0%}): Open wider; villain rarely defends. '
            f'Steal from LP and BTN. Respect their 3-bet when it comes.'
        )

    return HUDProfile(
        vpip=vpip,
        pfr=pfr,
        af=af,
        three_bet_freq=three_bet_freq,
        archetype=archetype,
        archetype_description=archetype_desc,
        session_pattern=session_pattern,
        weakness_signals=weakness_signals,
        effective_bluff_adj=effective_adjs['bluff_freq'],
        effective_value_adj=effective_adjs['value_size'],
        effective_call_threshold_adj=effective_adjs['call_threshold'],
        top_insight=insight,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def hud_one_liner(r: HUDProfile) -> str:
    return (
        f'[HUD {r.archetype}] '
        f'VPIP={r.vpip:.0%} AF={r.af:.1f} | '
        f'bluff_adj={r.effective_bluff_adj:+.0%} '
        f'value_adj={r.effective_value_adj:+.0%}'
    )
