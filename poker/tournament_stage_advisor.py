"""
Tournament Stage Advisor (tournament_stage_advisor.py)

Tournament play requires fundamentally different strategy at each stage.
Two critical axes: M-ratio (stack urgency) and tournament phase (context).

M-RATIO (Harrington's M):
  M = stack / (BB + SB + antes_per_orbit)
  Green  (M > 20): No pressure. Play full strategy.
  Yellow (M 10-20): Slight urgency. Reshove spots arise.
  Orange (M  6-10): Danger zone. Push/fold becoming primary.
  Red    (M  1-5 ): Push/fold only. Find best spot now.
  Dead   (M  < 1 ): Shove any hand. Last resort mode.

TOURNAMENT PHASES:
  Early     (>75% players remaining): Chip accumulation phase.
  Middle    (25-75% remaining):       Balance accumulate/survive.
  Bubble    (<10% from ITM):          ICM pressure maximized.
  In Money  (ITM, not FT):           Ladder up payouts.
  Final Table:                        Complex ICM, pay jumps.

Usage:
    from poker.tournament_stage_advisor import advise_tournament_stage, TournamentStageAdvice, tourney_one_liner

    advice = advise_tournament_stage(
        stack_bb=30.0,
        big_blind=1.0,
        small_blind=0.5,
        ante_bb=0.1,
        n_players_table=9,
        total_players_started=1000,
        players_remaining=120,
        in_money=False,
        final_table=False,
        avg_stack_bb=50.0,
    )
    print(tourney_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List, Tuple


# --------------------------------------------------------------------------
# M-ratio helpers
# --------------------------------------------------------------------------

def _calc_m_ratio(stack_bb: float, bb: float, sb: float, ante_bb: float, n_players: int) -> float:
    """M = stack / cost of one orbit."""
    orbit_cost = bb + sb + ante_bb * n_players
    if orbit_cost <= 0:
        return 999.0
    return round(stack_bb / orbit_cost, 2)


def _m_zone(m: float) -> str:
    if m > 20:  return 'green'
    if m > 10:  return 'yellow'
    if m > 6:   return 'orange'
    if m > 1:   return 'red'
    return 'dead'


def _phase(pct_remaining: float, in_money: bool, final_table: bool,
           pct_from_money: float) -> str:
    if final_table:
        return 'final_table'
    if in_money:
        return 'in_money'
    if pct_from_money <= 0.10:
        return 'bubble'
    if pct_remaining > 0.75:
        return 'early'
    if pct_remaining > 0.25:
        return 'middle'
    return 'bubble'


# --------------------------------------------------------------------------
# Recommendation tables
# --------------------------------------------------------------------------

_VPIP_TARGET = {
    'green':  '24-30%',
    'yellow': '20-25%',
    'orange': '15-20%',
    'red':    '10-15%',
    'dead':   '100%',
}

_OPEN_SIZE = {
    'green':  '2.5x BB',
    'yellow': '2.2x BB',
    'orange': 'Open-shove or 2.0x (any open near-commits)',
    'red':    'Shove only (no minraise)',
    'dead':   'Shove all-in immediately',
}

_RESHOVE_RANGE = {
    'green':  '3bet/fold top 6%, 3bet/jam top 3%',
    'yellow': '3bet-jam top 8-12% vs late pos opens',
    'orange': '3bet-jam top 15-20% (cannot 3bet/fold at this depth)',
    'red':    'Any Ax, 44+, suited broadways vs open',
    'dead':   'Shove 100% of hands — do not fold blinds',
}

_CALLOFF_RANGE = {
    'green':  'Top 15% (Ax, TT+, premium broadways)',
    'yellow': 'Top 20-25% (88+, ATo+, KQs+)',
    'orange': 'Top 30-35% (66+, A8o+, KJs+)',
    'red':    'Any 38%+ equity vs shover range',
    'dead':   'Any 2 cards -- need the chips desperately',
}

# Strategy [zone][phase] -> (mode, description)
_STRATEGY = {
    ('green', 'early'):       ('accumulate', 'Full strategy. Speculate, setmine, float. Build the biggest stack now.'),
    ('green', 'middle'):      ('accumulate', 'Continue accumulating. Avoid big coin flips without an edge.'),
    ('green', 'bubble'):      ('bully',      'BIG STACK BULLY: Attack medium stacks brutally. ICM freezes them.'),
    ('green', 'in_money'):    ('bully',      'Keep applying max pressure. Collect from ICM-squeezed medium stacks.'),
    ('green', 'final_table'): ('selective',  'Chip leader at FT: pick off shorts carefully. Avoid flips vs other bigs.'),

    ('yellow', 'early'):      ('accumulate', 'Stack manageable. Accumulate but avoid unnecessary marginal spots.'),
    ('yellow', 'middle'):     ('balanced',   'Balance accumulation and survival. Reshove spots are high value now.'),
    ('yellow', 'bubble'):     ('tight',      'TIGHT on bubble: yellow zone means fold equity matters. Avoid marginal spots.'),
    ('yellow', 'in_money'):   ('reshove',    'Look for reshove spots. Open 2.0-2.2x to preserve chips per orbit.'),
    ('yellow', 'final_table'):('reshove',    'Medium stack FT: reshove well-chosen spots. Avoid calling off without premium.'),

    ('orange', 'early'):      ('reshove',    'Danger zone early -- unusual. Double up immediately via reshove.'),
    ('orange', 'middle'):     ('push_fold',  'PUSH/FOLD: Open-jam or fold. Stack too short for post-flop play.'),
    ('orange', 'bubble'):     ('jam_now',    'ORANGE ON BUBBLE: Cannot blind out much longer. Best spot -- jam.'),
    ('orange', 'in_money'):   ('jam_now',    'ITM short: push/fold immediately. Do not ladder into oblivion.'),
    ('orange', 'final_table'):('jam_now',    'FT short: jam wide. Pay jumps give you ICM leverage vs bigs.'),

    ('red', 'early'):         ('push_fold',  'M<6 early: unusual. Shove any +EV spot in late position immediately.'),
    ('red', 'middle'):        ('push_fold',  'PUSH/FOLD ONLY: Shove any decent hand (Ax, any pair, suited broadways).'),
    ('red', 'bubble'):        ('shove_wide', 'Short bubble: shove wide -- ICM helps you, medium stacks cannot call.'),
    ('red', 'in_money'):      ('shove_wide', 'ITM short: shove any +EV hand. Ladder off gets you nothing.'),
    ('red', 'final_table'):   ('shove_wide', 'FT short: shove wide targeting pay jumps. Do not fold into irrelevance.'),

    ('dead', 'early'):        ('desperate',  'M<1: Shove every single hand. Cannot fold ever. Last resort.'),
    ('dead', 'middle'):       ('desperate',  'DESPERATE: Shove immediately. Fold equity near zero -- go now.'),
    ('dead', 'bubble'):       ('desperate',  'Desperate shove: even with air, every orbit that passes is lost equity.'),
    ('dead', 'in_money'):     ('desperate',  'Shove every hand. Any chip gain is progress. Do not fold.'),
    ('dead', 'final_table'):  ('desperate',  'FT dead: shove every spot. Any double-up is worth taking.'),
}


# --------------------------------------------------------------------------
# Dataclass
# --------------------------------------------------------------------------

@dataclass
class TournamentStageAdvice:
    # Inputs
    stack_bb: float
    big_blind: float
    small_blind: float
    ante_bb: float
    n_players_table: int
    total_players_started: int
    players_remaining: int
    in_money: bool
    final_table: bool
    avg_stack_bb: float

    # Calculated
    m_ratio: float
    m_zone: str             # 'green', 'yellow', 'orange', 'red', 'dead'
    pct_remaining: float    # fraction of field left
    phase: str              # 'early', 'middle', 'bubble', 'in_money', 'final_table'
    stack_vs_avg: float     # hero_stack / avg_stack

    # Recommendations
    strategy_mode: str      # 'accumulate', 'bully', 'reshove', 'push_fold', etc.
    strategy_advice: str
    vpip_target: str
    open_raise_size: str
    reshove_range: str
    calloff_range: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Main function
# --------------------------------------------------------------------------

def advise_tournament_stage(
    stack_bb: float = 50.0,
    big_blind: float = 1.0,
    small_blind: float = 0.5,
    ante_bb: float = 0.0,
    n_players_table: int = 9,
    total_players_started: int = 1000,
    players_remaining: int = 500,
    in_money: bool = False,
    final_table: bool = False,
    avg_stack_bb: float = 50.0,
    itm_spots: int = 100,
) -> TournamentStageAdvice:
    """
    Advise tournament strategy based on stack depth (M-ratio) and phase.

    Args:
        stack_bb:              Hero's stack in big blinds
        big_blind:             BB denomination (usually 1.0 normalized)
        small_blind:           SB (usually 0.5)
        ante_bb:               Ante per player in BB (0 if no ante)
        n_players_table:       Players at this table (affects orbit cost)
        total_players_started: Starting field size
        players_remaining:     How many players still in
        in_money:              True if hero is already ITM
        final_table:           True if at the final table
        avg_stack_bb:          Current average stack in BB
        itm_spots:             Number of paid spots in the tournament

    Returns:
        TournamentStageAdvice
    """
    m = _calc_m_ratio(stack_bb, big_blind, small_blind, ante_bb, n_players_table)
    zone = _m_zone(m)

    pct_remaining = round(players_remaining / max(total_players_started, 1), 4)
    # pct_from_money: how close to bubble as fraction of total field
    pct_from_money = round(
        (players_remaining - itm_spots) / max(total_players_started, 1), 4
    )
    phase = _phase(pct_remaining, in_money, final_table, pct_from_money)

    mode, advice = _STRATEGY.get(
        (zone, phase),
        ('balanced', 'Standard tournament strategy for this zone and phase.')
    )

    stack_vs_avg = round(stack_bb / max(avg_stack_bb, 1.0), 2)

    vpip = _VPIP_TARGET[zone]
    open_sz = _OPEN_SIZE[zone]
    reshove = _RESHOVE_RANGE[zone]
    calloff = _CALLOFF_RANGE[zone]

    reasoning = (
        f'Stack: {stack_bb:.1f}BB | M={m:.1f} ({zone} zone) | '
        f'Phase: {phase} ({pct_remaining:.0%} field remains) | '
        f'Stack vs avg: {stack_vs_avg:.2f}x | Mode: {mode}'
    )

    verdict = (
        f'[{zone.upper()}|M={m:.1f}|{phase.upper().replace("_"," ")}] '
        f'{mode.upper()}: {advice}'
    )

    # --- Tips ---
    tips = []

    # Antes effect
    if ante_bb > 0.0:
        orbit_base = big_blind + small_blind
        orbit_total = orbit_base + ante_bb * n_players_table
        ante_pct = (orbit_total - orbit_base) / orbit_total * 100
        tips.append(
            f'ANTES: {ante_pct:.0f}% extra orbit cost. Steal/open ranges widen significantly. '
            f'More dead money = more profitable aggression. Add antes to M calculation.'
        )

    # Stack vs avg
    if stack_vs_avg < 0.5:
        tips.append(
            f'SHORT STACK ({stack_vs_avg:.2f}x avg): You are well below average. '
            f'Do NOT play passive. Double up is the immediate goal. '
            f'Shove wide from LP when first to act. Look for reshove vs opens.'
        )
    elif stack_vs_avg > 2.0:
        tips.append(
            f'CHIP LEADER ({stack_vs_avg:.2f}x avg): Exploit your chip advantage. '
            f'Attack medium stacks who cannot call without busting or major stack loss. '
            f'Avoid unnecessary flips vs other chip leaders.'
        )

    # Urgency reminder
    if zone in ('orange', 'red', 'dead'):
        orbit_cost = big_blind + small_blind + ante_bb * n_players_table
        orbits_left = round(stack_bb / max(orbit_cost, 0.01), 1)
        tips.append(
            f'URGENCY: At M={m:.1f} you have ~{orbits_left:.0f} orbits before busting. '
            f'Do not wait. Find your best spot in the next {max(1, int(orbits_left // 2))} hands.'
        )

    # Phase tips
    if phase == 'bubble':
        tips.append(
            f'BUBBLE DYNAMICS: Big stacks attack medium stacks (ICM freezes them). '
            f'Short stacks shove wide (ICM helps — medium stacks fold big hands). '
            f'Medium stacks tighten most (max ICM pain if they bust).'
        )
    if phase == 'final_table':
        tips.append(
            f'FINAL TABLE: Check the pay jump to next spot vs stack risk. '
            f'Target players whose bust helps you the most. '
            f'Avoid all-in flips unless clearly +EV or desperate.'
        )
    if phase == 'in_money' and zone in ('green', 'yellow'):
        tips.append(
            f'ITM CHIP LEADER: Keep attacking. Survival mentality costs BB/100. '
            f'Each pay jump is worth chasing by accumulating chips aggressively now.'
        )

    if not tips:
        tips.append(
            f'M={m:.1f} ({zone}): VPIP target {vpip}. Open: {open_sz}. {advice}'
        )

    return TournamentStageAdvice(
        stack_bb=round(stack_bb, 2),
        big_blind=round(big_blind, 3),
        small_blind=round(small_blind, 3),
        ante_bb=round(ante_bb, 3),
        n_players_table=n_players_table,
        total_players_started=total_players_started,
        players_remaining=players_remaining,
        in_money=in_money,
        final_table=final_table,
        avg_stack_bb=round(avg_stack_bb, 2),
        m_ratio=m,
        m_zone=zone,
        pct_remaining=pct_remaining,
        phase=phase,
        stack_vs_avg=stack_vs_avg,
        strategy_mode=mode,
        strategy_advice=advice,
        vpip_target=vpip,
        open_raise_size=open_sz,
        reshove_range=reshove,
        calloff_range=calloff,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tourney_one_liner(r: TournamentStageAdvice) -> str:
    adv_short = r.strategy_advice[:50] + '...' if len(r.strategy_advice) > 50 else r.strategy_advice
    return (
        f'[MTT {r.m_zone.upper()}|M={r.m_ratio:.1f}|{r.phase}] '
        f'{r.strategy_mode.upper()} | '
        f'stack={r.stack_vs_avg:.2f}x_avg vpip={r.vpip_target} | '
        f'{adv_short}'
    )
