"""
Session Game Plan Advisor (session_game_plan.py)

Pre-session strategic planning is one of the most underrated poker skills.
Most players sit down and react; winning players arrive with a plan.

Key decisions before sitting down:
  1. Table selection: is this game worth playing?
  2. Stack size: full buy-in or short stack strategy?
  3. Primary strategy: are you exploiting fish, playing GTO, or defending?
  4. Quit criteria: profit target AND stop loss AND time limit
  5. Mental game: are you in the right state to play?

Table type adjustments:
  fish_heavy (>2 players VPIP>50%):
    - Value-heavy strategy: widen value range, reduce bluffs
    - Target fish seats (act after them if possible)
    - Open wider IP vs fish; tighten OOP vs unknowns
    - Priority: thin value betting, not fancy plays

  aggressive_regular:
    - 3-bet/4-bet wars — have a plan for common 3-bet spots
    - Tighten opening range to avoid being squeezed constantly
    - Exploit aggro tells: re-raise frequency, cbet patterns
    - Priority: well-timed counter-aggression, not just calling

  nit_table (mostly VPIP<25%):
    - Steal more — nits defend too tight
    - Bluff more (they fold too much)
    - Value bet only top 20% of range against nits
    - Priority: positional theft, not large pots

  loose_passive (lots of limpers, low PFR%):
    - ISO-raise liberally vs limpers
    - Value bet very thin (they call too much)
    - Never pure bluff — they never fold
    - Priority: huge value extraction, stop bluffing

  short_handed (<5 players):
    - Widen ranges significantly
    - C-bet more (fewer opponents)
    - 3-bet more aggressively
    - Priority: aggression and position

  tournament_late / mtt_bubble:
    - ICM pressure changes push/fold dynamics
    - Avoid marginal spots vs large stacks
    - Attack short stacks below you
    - Priority: survival + controlled accumulation

Fatigue model:
  - Focus peaks at 1-2 hours into session
  - Mild decline after 3-4 hours (common GTO mistakes)
  - Significant decline after 6+ hours (tilt risk, basic errors)
  - Never play >8 hours without a break

Usage:
    from poker.session_game_plan import build_session_plan, SessionGamePlan, plan_one_liner
    plan = build_session_plan(
        table_type='fish_heavy',
        stack_bb=100.0,
        hours_available=4.0,
        bankroll_bb=2000.0,
        personal_strength='postflop',
    )
    print(plan.primary_focus)
    print(plan_one_liner(plan))
"""

from dataclasses import dataclass, field
from typing import List


def _validate_table_type(t: str) -> str:
    valid = {
        'fish_heavy', 'aggressive_regular', 'nit_table',
        'loose_passive', 'short_handed', 'mtt_bubble', 'standard',
    }
    return t if t in valid else 'standard'


def _primary_focus(table_type: str, personal_strength: str) -> str:
    """Main strategic focus for the session."""
    focus_map = {
        'fish_heavy': 'exploit_value',
        'aggressive_regular': 'counter_aggression',
        'nit_table': 'positional_theft',
        'loose_passive': 'pure_value_extraction',
        'short_handed': 'aggressive_positional',
        'mtt_bubble': 'icm_aware_survival',
        'standard': 'balanced_gto',
    }
    return focus_map.get(table_type, 'balanced_gto')


def _open_range_adj(table_type: str, personal_strength: str) -> float:
    """Fractional adjustment to standard opening ranges. +0.10 = widen by 10%."""
    adj_map = {
        'fish_heavy': +0.05,        # slight widening (value extraction more important)
        'aggressive_regular': -0.08, # tighten (avoid getting squeezed)
        'nit_table': +0.12,         # steal aggressively
        'loose_passive': +0.03,     # slight widen (they call, don't 3-bet)
        'short_handed': +0.15,      # 4-handed: widen a lot
        'mtt_bubble': -0.05,        # tighten (ICM)
        'standard': 0.0,
    }
    return adj_map.get(table_type, 0.0)


def _cbet_freq_adj(table_type: str) -> float:
    """Fractional adjustment to c-bet frequency."""
    adj_map = {
        'fish_heavy': +0.05,         # fish fold to cbets → cbet more
        'aggressive_regular': -0.10, # regs defend well → be selective
        'nit_table': +0.15,          # nits fold too much
        'loose_passive': -0.05,      # calling stations call cbets → cbet only value
        'short_handed': +0.10,       # fewer opponents → c-bet more
        'mtt_bubble': 0.0,
        'standard': 0.0,
    }
    return adj_map.get(table_type, 0.0)


def _bluff_freq_adj(table_type: str) -> float:
    """Fractional adjustment to bluff frequency."""
    adj_map = {
        'fish_heavy': -0.20,         # never bluff fish
        'aggressive_regular': 0.0,   # balanced
        'nit_table': +0.15,          # nits fold to any pressure
        'loose_passive': -0.30,      # calling stations never fold
        'short_handed': +0.05,       # slightly more bluffs (fewer opponents)
        'mtt_bubble': -0.05,         # survival > bluffing
        'standard': 0.0,
    }
    return adj_map.get(table_type, 0.0)


def _profit_target(stack_bb: float, table_type: str, hours: float) -> float:
    """Suggested profit target for the session (in BB)."""
    # Base: 5-10 BB/hour is a strong live win rate
    hourly_target = {
        'fish_heavy': 12.0,
        'loose_passive': 10.0,
        'nit_table': 4.0,
        'aggressive_regular': 5.0,
        'short_handed': 6.0,
        'mtt_bubble': stack_bb * 0.30,  # stack-based for MTT
        'standard': 6.0,
    }.get(table_type, 6.0)
    return round(min(stack_bb * 2.5, hourly_target * hours), 0)


def _stop_loss(stack_bb: float, table_type: str) -> float:
    """Session stop loss in BB."""
    # Standard: 1.5-2.5 buy-ins
    factor = {
        'fish_heavy': 2.0,       # game is good, can lose more before quitting
        'aggressive_regular': 1.5,
        'nit_table': 1.5,
        'loose_passive': 2.0,
        'short_handed': 1.5,
        'mtt_bubble': stack_bb,  # ICM: lose stack = bust
        'standard': 1.5,
    }.get(table_type, 1.5)
    return round(stack_bb * factor, 0)


def _optimal_hours(hours_available: float, table_type: str) -> float:
    """Recommended session length."""
    # Fatigue model: diminishing returns after ~3 hours, significant after 5
    if table_type == 'fish_heavy':
        optimal = min(hours_available, 5.0)  # play longer in good games
    elif table_type == 'aggressive_regular':
        optimal = min(hours_available, 3.0)  # mental game drains faster vs regs
    elif table_type == 'mtt_bubble':
        optimal = hours_available  # play until done
    else:
        optimal = min(hours_available, 4.0)
    return optimal


def _fatigue_risk(hours_available: float) -> str:
    if hours_available <= 2:
        return 'low'
    if hours_available <= 4:
        return 'medium'
    return 'high'


def _key_adjustments(table_type: str, personal_strength: str) -> List[str]:
    """3-5 concrete adjustments for this session."""
    adjustments = {
        'fish_heavy': [
            'Value bet thinner than normal — call stations pay off with worse hands.',
            'Never pure bluff with air against fish. Bluff only with equity (semi-bluffs).',
            'Iso-raise every limper when in position. Extract value preflop.',
            'Size up value bets vs calling stations (75-100% pot on wet boards).',
            'Skip elaborate multi-street bluffs — fish do not fold to 3-barrels.',
        ],
        'aggressive_regular': [
            'Tighten preflop opening range to avoid 3-bet pressure.',
            'Have a 4-bet plan for hands you plan to open (AA/KK/QQ = jam or 4-bet call).',
            'Defend BB correctly — do not over-fold vs positional 3-bets.',
            'Counter-4-bet light vs known 3-bet bluffers (ATs, KQs as call/jam).',
            'Slow-play occasionally with sets to trap aggressive c-betters.',
        ],
        'nit_table': [
            'Open BTN/CO liberally — nits fold blinds too often.',
            'Double-barrel nearly every board vs nits (they fold to turn pressure).',
            'Do not over-value top pair vs nit — when they raise, they have it.',
            'Use smaller c-bets (40% pot) — nits fold to any bet, save money.',
            'Thin value bet only vs specific nits who cannot fold overpairs.',
        ],
        'loose_passive': [
            'Never bluff. Calling stations fold less than 40% to any bet.',
            'Value bet very thin — middle pair is often best on showdown.',
            'ISO-raise every limper with top 30-40% of hands.',
            'Build big pots with strong hands — callers give maximum value.',
            'Accept multi-way pots — set mine aggressively for implied odds.',
        ],
        'short_handed': [
            'Widen opening range: at 4-handed, UTG is like CO at 9-max.',
            '3-bet much more aggressively — fewer players = less fold equity needed.',
            'C-bet almost every flop (80%+ frequency) — single opponent defends less.',
            'Be prepared for aggressive back-and-forth — regs adjust fast.',
            'Position matters even more short-handed — never limp from SB.',
        ],
        'mtt_bubble': [
            'Attack short stacks below you when in position — they cannot call.',
            'Avoid marginal spots vs chip leaders (they can eliminate you).',
            'Tighten 3-bet range — avoid building large pots out of position.',
            'Steal relentlessly vs medium stacks who fear busting near the money.',
            'Jam stack below 15BB — push/fold only, no open-raise-fold.',
        ],
        'standard': [
            'Play balanced GTO in unclear spots to avoid being exploited.',
            'Adjust after 30-50 hands based on how each villain is playing.',
            'Track each player\'s VPIP/PFR/cbet frequency mentally.',
            'Look for deviation opportunities when you have solid HUD reads.',
            'Take breaks every 90 minutes to maintain focus.',
        ],
    }
    base = adjustments.get(table_type, adjustments['standard'])

    # Add personal strength note
    if personal_strength == 'preflop':
        base.append('Leverage preflop skill — look for 3-bet/4-bet spots and steal situations.')
    elif personal_strength == 'postflop':
        base.append('Leverage postflop skill — call more preflop to get into postflop situations.')
    elif personal_strength == 'bluffing':
        base.append('Leverage bluffing skill — pick high-fold-equity spots, not calling stations.')
    elif personal_strength == 'value_betting':
        base.append('Leverage value-bet skill — get stacks in thin; do not miss value on any street.')

    return base[:6]


def _target_villain_type(table_type: str) -> str:
    targets = {
        'fish_heavy': 'fish/calling_station (VPIP>50%, low PFR)',
        'aggressive_regular': 'wide_3bettor (3bet>8%) — flat their 3-bets, 4-bet jam premiums',
        'nit_table': 'nit (VPIP<20%) — steal their blinds relentlessly',
        'loose_passive': 'loose_passive (VPIP>45%, PFR<12%) — value-town them',
        'short_handed': 'position_stealer — counter their steals from BTN/CO',
        'mtt_bubble': 'medium_stack near bubble — steal their chips while they survive',
        'standard': 'loosest player at table — build pots vs them IP',
    }
    return targets.get(table_type, 'loosest player')


@dataclass
class SessionGamePlan:
    """Pre-session strategic game plan."""
    table_type: str
    stack_bb: float
    hours_available: float
    bankroll_bb: float
    personal_strength: str

    # Core strategy
    primary_focus: str
    target_villain_type: str

    # Range adjustments (fractional, +/- from standard)
    open_range_adj: float     # +0.10 = widen by 10%
    cbet_freq_adj: float
    bluff_freq_adj: float

    # Session management
    profit_target_bb: float
    stop_loss_bb: float
    optimal_hours: float
    fatigue_risk: str        # 'low', 'medium', 'high'

    # Game plan
    key_adjustments: List[str]
    pre_session_checklist: List[str]

    reasoning: str


def build_session_plan(
    table_type: str = 'standard',
    stack_bb: float = 100.0,
    hours_available: float = 4.0,
    bankroll_bb: float = 2000.0,
    personal_strength: str = 'balanced',
) -> SessionGamePlan:
    """
    Build a pre-session game plan based on table type and personal factors.

    Args:
        table_type:       Table type: 'fish_heavy','aggressive_regular','nit_table',
                          'loose_passive','short_handed','mtt_bubble','standard'
        stack_bb:         Starting stack in big blinds
        hours_available:  How long you plan to play
        bankroll_bb:      Total bankroll in big blinds
        personal_strength: 'preflop','postflop','bluffing','value_betting','balanced'

    Returns:
        SessionGamePlan
    """
    table_type = _validate_table_type(table_type)
    focus = _primary_focus(table_type, personal_strength)
    open_adj = _open_range_adj(table_type, personal_strength)
    cbet_adj = _cbet_freq_adj(table_type)
    bluff_adj = _bluff_freq_adj(table_type)
    profit_t = _profit_target(stack_bb, table_type, hours_available)
    stop_l = _stop_loss(stack_bb, table_type)
    opt_hours = _optimal_hours(hours_available, table_type)
    fatigue = _fatigue_risk(hours_available)
    adjustments = _key_adjustments(table_type, personal_strength)
    target = _target_villain_type(table_type)

    # Checklist
    checklist = [
        'Confirm starting stack is at table max buy-in.',
        'Check bankroll: this session is {:.0f}% of bankroll.'.format(stack_bb / bankroll_bb * 100),
        f'Profit target: +{profit_t:.0f}BB. Stop loss: -{stop_l:.0f}BB.',
        f'Optimal play time: {opt_hours:.0f}h. Take a break every 90 minutes.',
    ]
    if fatigue == 'high':
        checklist.append('Warning: >4h session planned. High fatigue risk. Set a phone alarm.')
    if bluff_adj < -0.15:
        checklist.append('This table: do NOT bluff. Mark bluff spots as check-fold.')
    if table_type == 'mtt_bubble':
        checklist.append('Know your exact stack/blind ratio before each hand.')

    # Bankroll check
    br_risk = stack_bb / bankroll_bb
    if br_risk > 0.10:
        checklist.append(
            f'CAUTION: stack is {br_risk:.0%} of bankroll. '
            f'Standard: play at stakes where buy-in <= 5% of BR.'
        )

    reasoning = (
        f'{table_type.replace("_", " ").title()} table: {focus.replace("_", " ")}. '
        f'Key lever: {adjustments[0].split(".")[0]}. '
        f'Target: {target}. '
        f'Session length: {opt_hours:.0f}h, profit target: +{profit_t:.0f}BB, '
        f'stop loss: -{stop_l:.0f}BB.'
    )

    return SessionGamePlan(
        table_type=table_type,
        stack_bb=round(stack_bb, 1),
        hours_available=hours_available,
        bankroll_bb=round(bankroll_bb, 1),
        personal_strength=personal_strength,
        primary_focus=focus,
        target_villain_type=target,
        open_range_adj=open_adj,
        cbet_freq_adj=cbet_adj,
        bluff_freq_adj=bluff_adj,
        profit_target_bb=profit_t,
        stop_loss_bb=stop_l,
        optimal_hours=opt_hours,
        fatigue_risk=fatigue,
        key_adjustments=adjustments,
        pre_session_checklist=checklist,
        reasoning=reasoning,
    )


def plan_one_liner(plan: SessionGamePlan) -> str:
    sign = '+' if plan.open_range_adj >= 0 else ''
    return (
        f'[SGP {plan.table_type}] '
        f'{plan.primary_focus.upper()} | '
        f'open={sign}{plan.open_range_adj:+.0%} cbet={plan.cbet_freq_adj:+.0%} '
        f'bluff={plan.bluff_freq_adj:+.0%} | '
        f'target={plan.profit_target_bb:.0f}BB stop={plan.stop_loss_bb:.0f}BB | '
        f'{plan.optimal_hours:.0f}h'
    )
