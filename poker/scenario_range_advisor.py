"""
Scenario Range Advisor (scenario_range_advisor.py)

Given a preflop scenario (hero's position, villain stats, stack depth), produces
a complete breakdown of which hand groups to 4-bet, call, or fold when facing a
3-bet. Unlike preflop_3bet_defense.py (which advises on a SINGLE hand), this
module shows the FULL RANGE picture — all major hand groups and their optimal action.

This fills the gap between per-hand advice and the holistic range view that
winning players use during study/real-time play.

Outputs 7 hand groups:
  1. Always 4-bet value:  AA-QQ, AK
  2. Situational 4-bet:   JJ, AQs (vs wide 3-bet or IP)
  3. 4-bet bluff:         A5s-A2s, K-suited blockers (when fold equity exists)
  4. IP call:             TT-88, AQo, AJs, KQs, QJs (strong enough to float)
  5. OOP call:            JJ, AQs only (very narrow)
  6. Conditional hands:   TT (call IP wide, fold OOP vs nit)
  7. Always fold:         Everything below call range

Also computes:
  - Expected 4-bet% for your range vs this specific 3-bet frequency
  - Defend% (how much of range continues)
  - MDF (minimum defense frequency to prevent exploitative folding)
  - Estimated EV per hand group

Usage:
    from poker.scenario_range_advisor import advise_scenario, ScenarioRangeAdvice
    result = advise_scenario(
        hero_pos='CO',
        villain_pos='BTN',
        villain_3bet_pct=0.08,
        villain_fold_to_4bet=0.55,
        eff_stack_bb=100.0,
        in_position=True,
    )
    for group in result.hand_groups:
        print(group.action, group.hands_description)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# All hand groups with approximate combo counts and strength
_ALL_GROUPS = [
    # (group_id, combos, strength_rank, description)
    ('AA_KK',        12, 10, 'AA-KK (premium pairs)'),
    ('QQ',            6,  9, 'QQ'),
    ('AKs',           4,  9, 'AKs'),
    ('AKo',          12,  8, 'AKo'),
    ('JJ',            6,  8, 'JJ'),
    ('TT',            6,  7, 'TT'),
    ('AQs',           4,  7, 'AQs'),
    ('AQo',          12,  6, 'AQo'),
    ('AJs',           4,  6, 'AJs'),
    ('KQs',           4,  6, 'KQs'),
    ('A5s_A2s',      16,  5, 'A5s-A2s (bluff candidates, A-blocker)'),
    ('99_88',        12,  5, '99-88'),
    ('QJs',           4,  5, 'QJs'),
    ('JTs',           4,  4, 'JTs'),
    ('KQo',          12,  4, 'KQo (marginal OOP)'),
    ('KJs',           4,  4, 'KJs'),
    ('rest',         80,  2, 'All remaining hands (fold vs 3-bet)'),
]

_GROUP_COMBOS = {g[0]: g[1] for g in _ALL_GROUPS}
_GROUP_STRENGTH = {g[0]: g[2] for g in _ALL_GROUPS}
_GROUP_DESC = {g[0]: g[3] for g in _ALL_GROUPS}


@dataclass
class HandGroupAdvice:
    group_id: str
    hands_description: str
    combos: int
    action: str             # '4bet_value', '4bet_bluff', 'call_ip', 'call_oop', 'fold'
    action_label: str
    ev_estimate: float      # approximate EV vs folding (positive = better than fold)
    notes: str              # why this action for this group


@dataclass
class ScenarioRangeAdvice:
    """Full range breakdown for a preflop 3-bet scenario."""
    # Scenario inputs
    hero_pos: str
    villain_pos: str
    villain_3bet_pct: float
    villain_fold_to_4bet: float
    eff_stack_bb: float
    in_position: bool

    # Villain classification
    villain_3bet_type: str  # 'value_only', 'balanced', 'wide_bluff'

    # Hand groups
    hand_groups: List[HandGroupAdvice]

    # Range statistics
    total_combos_open: int          # approx combos in hero's opening range
    combos_4bet_value: int
    combos_4bet_bluff: int
    combos_call: int
    combos_fold: int

    # Frequencies
    pct_4bet: float                 # fraction of range that 4-bets
    pct_call: float                 # fraction of range that calls
    pct_fold: float                 # fraction of range that folds
    mdf: float                      # minimum defense frequency
    defend_pct: float               # actual defend % (4bet + call)

    # EV overview
    range_ev_vs_fold: float         # estimated EV gain from optimal defense vs folding all

    # Guidance
    key_insight: str
    sizing_note: str
    recommendations: List[str] = field(default_factory=list)


def _villain_3bet_type(pct: float) -> str:
    if pct <= 0.05:
        return 'value_only'
    elif pct <= 0.09:
        return 'balanced'
    return 'wide_bluff'


def _mdf(threbet_size_pct: float = 3.0) -> float:
    """MDF when villain 3-bets to ~3x open."""
    # Villain bets 3x into a pot of ~4.5BB (1.5 pot)
    # MDF = 1 - fold_equity ≈ pot / (pot + 3bet)
    pot_before = 4.5  # typical pot before 3-bet
    bet = threbet_size_pct * 2.5  # 3-bet to ~7.5BB
    return pot_before / (pot_before + bet)


def _decide_action(
    group_id: str,
    in_position: bool,
    villain_3bet_pct: float,
    villain_fold_to_4bet: float,
    eff_stack_bb: float,
) -> tuple:
    """Return (action, action_label, ev_estimate, notes)."""
    v3bt = _villain_3bet_type(villain_3bet_pct)
    fold_ok = villain_fold_to_4bet >= 0.55

    if group_id == 'AA_KK':
        return ('4bet_value', '4-bet for value', 0.35,
                'Always 4-bet. Villain calling or shoving is fine — you have the nuts.')

    if group_id == 'QQ':
        return ('4bet_value', '4-bet for value', 0.20,
                'QQ always 4-bets. Only fold if villain shows 4-bet/fold tells (rare).')

    if group_id == 'AKs':
        return ('4bet_value', '4-bet for value', 0.22,
                'AKs: strong blockers + equity vs calling range. Always 4-bet.')

    if group_id == 'AKo':
        return ('4bet_value', '4-bet for value', 0.18,
                'AKo: still 4-bet value vs any 3-bet frequency.')

    if group_id == 'JJ':
        if v3bt == 'wide_bluff' or in_position:
            return ('4bet_value', '4-bet for value', 0.12,
                    f'JJ vs {villain_3bet_pct:.0%} 3-bet: 4-bet (enough bluffs in range to be profitable).')
        else:
            return ('call_ip' if in_position else 'call_oop',
                    'call (avoid GII vs value-only range)',
                    0.08,
                    f'JJ vs tight 3-bet ({villain_3bet_pct:.0%}): calling is safer than 4-bet/call off vs QQ+/AK.')

    if group_id == 'TT':
        if in_position and v3bt != 'value_only':
            return ('call_ip', 'call IP', 0.06,
                    'TT IP: calling with position; fold-to-c-bet and float options.')
        return ('fold', 'fold', -0.02,
                'TT OOP vs balanced/tight 3-bet: difficult spot with reverse implied odds.')

    if group_id == 'AQs':
        if in_position:
            return ('call_ip', 'call IP (or 4-bet vs wide)', 0.08,
                    'AQs IP: call and outplay. 4-bet if villain 3-bets >9% (adds bluffs).')
        return ('call_oop', 'call OOP (narrow range)', 0.04,
                'AQs OOP: marginal but enough equity. Narrow continue range OOP.')

    if group_id == 'AQo':
        if in_position and v3bt == 'wide_bluff':
            return ('call_ip', 'call IP vs wide', 0.05,
                    'AQo IP vs wide 3-bet: call. Too many bluffs in villain range to fold.')
        return ('fold', 'fold', -0.01,
                'AQo OOP or vs tight 3-bet: fold. Dominated by AK/KK/AA too often.')

    if group_id == 'AJs':
        if in_position:
            return ('call_ip', 'call IP', 0.04,
                    'AJs IP: good equity + position. Outflop 3-bettor\'s range sometimes.')
        return ('fold', 'fold', -0.02,
                'AJs OOP: fold. Dominated by AQ+, no position to realize equity.')

    if group_id == 'KQs':
        if in_position and v3bt == 'wide_bluff':
            return ('call_ip', 'call IP vs wide', 0.03,
                    'KQs IP vs wide 3-bet: call with good blockers + equity.')
        return ('fold', 'fold', -0.01,
                'KQs OOP or vs tight: fold. Difficult to realize equity without position.')

    if group_id == 'A5s_A2s':
        if fold_ok:
            ev = 0.08 + (villain_fold_to_4bet - 0.55) * 0.3
            return ('4bet_bluff', '4-bet bluff (A-blocker)', round(ev, 2),
                    f'A2s-A5s: ideal bluff. A-blocker + suited + villain folds {villain_fold_to_4bet:.0%} to 4-bet.')
        return ('fold', 'fold (no fold equity)', -0.03,
                f'A2s-A5s: bluff 4-bet is –EV. Villain calls {(1-villain_fold_to_4bet):.0%} of 4-bets.')

    if group_id == '99_88':
        if in_position and v3bt == 'wide_bluff':
            return ('call_ip', 'call IP vs wide', 0.02,
                    '99-88 IP vs wide 3-bet: borderline call. Set mining + equity.')
        return ('fold', 'fold', -0.03,
                '99-88 OOP or vs balanced/tight: fold. Not enough equity or implied odds.')

    if group_id == 'QJs':
        if in_position and v3bt == 'wide_bluff':
            return ('call_ip', 'call IP', 0.01,
                    'QJs IP vs wide: borderline call with connectivity + position.')
        return ('fold', 'fold', -0.02, 'QJs: fold OOP or vs balanced/tight 3-bet.')

    if group_id in ('JTs', 'KQo', 'KJs'):
        return ('fold', 'fold', -0.03,
                f'{_GROUP_DESC.get(group_id, group_id)}: fold vs 3-bet in most spots.')

    # 'rest' — everything else
    return ('fold', 'fold', -0.05,
            'All remaining hands: fold vs 3-bet.')


def advise_scenario(
    hero_pos: str = 'CO',
    villain_pos: str = 'BTN',
    villain_3bet_pct: float = 0.07,
    villain_fold_to_4bet: float = 0.55,
    eff_stack_bb: float = 100.0,
    in_position: Optional[bool] = None,
) -> ScenarioRangeAdvice:
    """
    Full range breakdown for facing a 3-bet in a specific scenario.

    Args:
        hero_pos:              Hero's position
        villain_pos:           Villain's position (3-bettor)
        villain_3bet_pct:      Villain's 3-bet frequency
        villain_fold_to_4bet:  Villain folds to 4-bet
        eff_stack_bb:          Effective stack
        in_position:           Hero acts after villain postflop (auto-detect if None)

    Returns:
        ScenarioRangeAdvice
    """
    if in_position is None:
        vp = villain_pos.upper()
        in_position = vp in ('SB', 'BB', 'UTG', 'UTG1', 'MP')

    v3bt = _villain_3bet_type(villain_3bet_pct)

    # Build hand group advice
    groups: List[HandGroupAdvice] = []
    combos_4bet_v = 0
    combos_4bet_b = 0
    combos_call   = 0
    combos_fold   = 0

    for group_id, n_combos, strength, desc in _ALL_GROUPS:
        action, label, ev, notes = _decide_action(
            group_id, in_position, villain_3bet_pct, villain_fold_to_4bet, eff_stack_bb
        )
        groups.append(HandGroupAdvice(
            group_id=group_id,
            hands_description=desc,
            combos=n_combos,
            action=action,
            action_label=label,
            ev_estimate=ev,
            notes=notes,
        ))
        if action == '4bet_value':
            combos_4bet_v += n_combos
        elif action == '4bet_bluff':
            combos_4bet_b += n_combos
        elif 'call' in action:
            combos_call += n_combos
        else:
            combos_fold += n_combos

    # Hero's total opening range (approximate by position)
    open_range_combos = {
        'UTG': 70, 'UTG1': 78, 'MP': 95, 'HJ': 115,
        'CO': 140, 'BTN': 200, 'SB': 175, 'BB': 220,
    }.get(hero_pos.upper(), 130)

    total_4bet  = combos_4bet_v + combos_4bet_b
    total_cont  = total_4bet + combos_call
    pct_4bet    = total_4bet / open_range_combos
    pct_call    = combos_call / open_range_combos
    pct_fold    = 1.0 - pct_4bet - pct_call
    mdf_val     = _mdf()
    defend_pct  = pct_4bet + pct_call

    range_ev = sum(g.ev_estimate * g.combos for g in groups if g.action != 'fold')
    range_ev /= max(open_range_combos, 1)

    # Key insight
    insights = {
        'value_only': (
            f'Villain 3-bets only {villain_3bet_pct:.0%} (value-only). '
            f'4-bet: QQ+/AK only. Fold JJ/TT/AQs OOP. Narrow call range.'
        ),
        'balanced': (
            f'Villain 3-bets {villain_3bet_pct:.0%} (balanced). '
            f'Standard defense: 4-bet QQ+/AK + bluffs (A5s-A2s if FvF4B>=55%), '
            f'call JJ/TT/AQs/AJs IP.'
        ),
        'wide_bluff': (
            f'Villain 3-bets {villain_3bet_pct:.0%} (wide/bluff-heavy). '
            f'4-bet JJ too. Call wider IP (TT/99/KQs/QJs). '
            f'Exploit: 4-bet/call lighter, call more draws IP.'
        ),
    }
    insight = insights[v3bt]

    # Sizing note
    if in_position:
        sizing = f'4-bet to ~{villain_3bet_pct * 100 * 2.2:.0f}BB (2.2x villain 3-bet). IP so keep it smaller.'
    else:
        sizing = f'4-bet to ~{villain_3bet_pct * 100 * 2.5:.0f}BB (2.5x villain 3-bet). OOP so go slightly larger.'

    # Recommendations
    recs = [insight]
    if villain_fold_to_4bet >= 0.65:
        recs.append(
            f'Villain folds {villain_fold_to_4bet:.0%} to 4-bets — bluff 4-bet frequency should be high. '
            f'Include A5s-A2s and even KQs IP.'
        )
    if defend_pct < mdf_val - 0.05:
        recs.append(
            f'Defend only {defend_pct:.0%} vs MDF of {mdf_val:.0%}. '
            f'Consider adding more calls IP or widening bluff 4-bet range.'
        )
    if not in_position:
        recs.append(
            'OOP: drastically narrow call range. Hands like TT/AJs/KQs are folds OOP '
            'vs a balanced 3-bet. Only 4-bet or fold most hands.'
        )

    return ScenarioRangeAdvice(
        hero_pos=hero_pos.upper(),
        villain_pos=villain_pos.upper(),
        villain_3bet_pct=villain_3bet_pct,
        villain_fold_to_4bet=villain_fold_to_4bet,
        eff_stack_bb=eff_stack_bb,
        in_position=in_position,
        villain_3bet_type=v3bt,
        hand_groups=groups,
        total_combos_open=open_range_combos,
        combos_4bet_value=combos_4bet_v,
        combos_4bet_bluff=combos_4bet_b,
        combos_call=combos_call,
        combos_fold=combos_fold,
        pct_4bet=round(pct_4bet, 3),
        pct_call=round(pct_call, 3),
        pct_fold=round(max(0, pct_fold), 3),
        mdf=round(mdf_val, 3),
        defend_pct=round(defend_pct, 3),
        range_ev_vs_fold=round(range_ev, 3),
        key_insight=insight,
        sizing_note=sizing,
        recommendations=recs,
    )


def scenario_one_liner(result: ScenarioRangeAdvice) -> str:
    """Single-line overlay summary."""
    ip_str = 'IP' if result.in_position else 'OOP'
    return (
        f'{result.hero_pos} vs {result.villain_3bet_pct:.0%} 3-bet [{result.villain_3bet_type}] {ip_str} | '
        f'4B {result.pct_4bet:.0%} | call {result.pct_call:.0%} | fold {result.pct_fold:.0%} | '
        f'defend={result.defend_pct:.0%} MDF={result.mdf:.0%}'
    )
