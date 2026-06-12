"""
Game Selection Advisor (game_selection.py)

Table selection is the highest-leverage skill in poker — choosing
to sit with weak players instead of strong ones can add 5-10 BB/100
to your win rate. This module scores available tables and seats to
recommend where to sit.

Scoring factors:
  - Average villain VPIP (higher = fishier table)
  - Average villain PFR (lower relative to VPIP = more passive/fishy)
  - Number of high-VPIP players (fish count)
  - Average AF (low = passive/exploitable)
  - Stack depth distribution (big stacks = more post-flop value)
  - Seat quality (relative to the big fish)
  - Rake structure impact

Usage:
    from poker.game_selection import evaluate_table, rank_tables, TableScore
    tables = [
        {'table_id': 'T1', 'players': [
            {'vpip': 0.45, 'pfr': 0.10, 'af': 1.2, 'stack_bb': 120},
            {'vpip': 0.28, 'pfr': 0.22, 'af': 2.5, 'stack_bb': 100},
            ...
        ]},
    ]
    scores = rank_tables(tables)
    print(scores[0].table_id, scores[0].recommendation)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class PlayerProfile:
    """Snapshot of one player's stats for game selection."""
    vpip: float = 0.25
    pfr: float = 0.18
    af: float = 2.0
    stack_bb: float = 100.0
    hands_observed: int = 30
    seat: int = 0


@dataclass
class TableScore:
    """Full game selection analysis for one table."""
    table_id: str
    num_players: int

    # Aggregate stats
    avg_vpip: float
    avg_pfr: float
    avg_af: float
    avg_stack_bb: float
    fish_count: int          # players with VPIP > 35%
    reg_count: int           # VPIP 22-32%, PFR/VPIP >= 0.6

    # Opportunity scores (0-10)
    fish_score: float        # how many big fish are present
    passivity_score: float   # how passive/exploitable the table is
    stack_score: float       # stack depth for implied odds
    overall_score: float     # weighted combination (10 = best)

    # Win rate potential
    estimated_ev_bb100: float  # rough expected win rate vs field

    # Best seat
    best_seat: int           # seat number (0-indexed) to sit at vs fish
    best_seat_reason: str

    # Verdict
    grade: str               # 'A', 'B', 'C', 'D', 'F'
    recommendation: str      # 'join', 'wait', 'avoid'
    reasoning: str
    tips: List[str] = field(default_factory=list)


def _classify_player(p: PlayerProfile) -> str:
    """Classify a player as fish/reg/nit/aggro."""
    vpip, pfr, af = p.vpip, p.pfr, p.af
    pfr_ratio = pfr / vpip if vpip > 0 else 0

    if vpip > 0.40:
        return 'fish'
    if vpip > 0.32 and pfr_ratio < 0.45:
        return 'loose_passive'
    if vpip < 0.18 and pfr < 0.14:
        return 'nit'
    if pfr_ratio > 0.80 and af > 3.0:
        return 'lag'
    if vpip < 0.28 and pfr_ratio > 0.65:
        return 'reg'
    return 'unknown'


def _fish_score(players: List[PlayerProfile]) -> float:
    """Score 0-10 based on fish quality and count."""
    score = 0.0
    for p in players:
        ptype = _classify_player(p)
        if ptype == 'fish':
            # More VPIP = more exploitable
            score += 2.5 + (p.vpip - 0.40) * 5.0
        elif ptype == 'loose_passive':
            score += 1.5
        elif ptype == 'nit':
            score += 0.2   # nits are boring but not harmful
        elif ptype == 'lag':
            score -= 0.5   # LAGs are dangerous
        elif ptype == 'reg':
            score -= 0.3   # regs reduce EV
    return max(0.0, min(10.0, score))


def _passivity_score(players: List[PlayerProfile]) -> float:
    """Score 0-10: high passive villain = more exploitable."""
    if not players:
        return 5.0
    avg_af = sum(p.af for p in players) / len(players)
    avg_pfr_ratio = sum(p.pfr / p.vpip if p.vpip > 0 else 0.7 for p in players) / len(players)
    # AF < 1.5 = very passive; AF > 3.5 = very aggressive
    af_score = max(0, (3.0 - avg_af) * 2.0)   # higher when passive
    pfr_score = max(0, (0.60 - avg_pfr_ratio) * 8.0)
    return min(10.0, af_score + pfr_score)


def _stack_score(players: List[PlayerProfile]) -> float:
    """Score 0-10 based on average stack depth (more = better implied odds)."""
    if not players:
        return 5.0
    avg_stack = sum(p.stack_bb for p in players) / len(players)
    # 100BB = 5; 150BB = 7; 200BB+ = 9; 50BB = 3
    return min(10.0, max(1.0, avg_stack / 20.0))


def _best_seat_vs_fish(players: List[PlayerProfile]) -> tuple:
    """
    Find the best seat to sit at vs the biggest fish.
    Ideal: sit LEFT of the biggest fish (act after them postflop).
    Returns (seat_index, reason).
    """
    if not players:
        return 0, 'No data — choose any seat'

    # Find the biggest fish by VPIP
    fish_list = [(i, p) for i, p in enumerate(players)
                 if _classify_player(p) in ('fish', 'loose_passive')]

    if not fish_list:
        return 0, 'No clear fish — any seat is fine'

    # Sort by VPIP descending
    fish_list.sort(key=lambda x: x[1].vpip, reverse=True)
    biggest_fish_seat = fish_list[0][0]

    n = len(players) + 1  # one extra for hero
    # Best seat = one seat to the LEFT of the fish (seat after in position order)
    best_seat = (biggest_fish_seat + 1) % n
    reason = (
        f'Seat {best_seat} is left of the biggest fish (seat {biggest_fish_seat}, '
        f'VPIP={fish_list[0][1].vpip:.0%}) — you\'ll act after them postflop.'
    )
    return best_seat, reason


def evaluate_table(
    table_id: str,
    players: List[PlayerProfile],
    rake_pct: float = 0.05,
    rake_cap_bb: float = 2.0,
) -> TableScore:
    """
    Score a single table for game selection.

    Args:
        table_id:     Identifier for the table
        players:      List of PlayerProfile for current occupants
        rake_pct:     Site rake percentage
        rake_cap_bb:  Rake cap in BBs

    Returns:
        TableScore
    """
    n = len(players)
    if n == 0:
        return TableScore(
            table_id=table_id, num_players=0,
            avg_vpip=0.25, avg_pfr=0.18, avg_af=2.0, avg_stack_bb=100.0,
            fish_count=0, reg_count=0,
            fish_score=0.0, passivity_score=5.0, stack_score=5.0, overall_score=5.0,
            estimated_ev_bb100=0.0,
            best_seat=0, best_seat_reason='No players',
            grade='C', recommendation='wait',
            reasoning='No players at table', tips=['Wait for players to join']
        )

    avg_vpip = sum(p.vpip for p in players) / n
    avg_pfr = sum(p.pfr for p in players) / n
    avg_af = sum(p.af for p in players) / n
    avg_stack = sum(p.stack_bb for p in players) / n

    fish_count = sum(1 for p in players if _classify_player(p) in ('fish', 'loose_passive'))
    reg_count = sum(1 for p in players if _classify_player(p) == 'reg')

    # Score components
    fs = _fish_score(players)
    ps = _passivity_score(players)
    ss = _stack_score(players)

    # Weighted overall score
    overall = 0.50 * fs + 0.30 * ps + 0.20 * ss

    # Rake adjustment: high rake reduces EV
    rake_penalty = (rake_pct - 0.04) * 20.0   # 5% rake = -2 pt vs 4%
    overall = max(0.0, overall - rake_penalty)

    # Estimated win rate vs this field
    # Base: VPIP of field predicts exploitability
    # Each 1% above 25% VPIP avg ≈ +0.5 BB/100 for a competent reg
    base_edge = (avg_vpip - 0.25) * 50   # +2.5 BB/100 per 5% above average
    passivity_bonus = (2.5 - avg_af) * 2.0 if avg_af < 2.5 else 0.0
    rake_drag = rake_pct * 50             # 5% rake ≈ -2.5 BB/100 drag
    estimated_ev = base_edge + passivity_bonus - rake_drag

    # Best seat
    best_seat, seat_reason = _best_seat_vs_fish(players)

    # Grade
    if overall >= 7.5:
        grade = 'A'
        recommendation = 'join'
    elif overall >= 5.5:
        grade = 'B'
        recommendation = 'join'
    elif overall >= 4.0:
        grade = 'C'
        recommendation = 'wait'
    elif overall >= 2.5:
        grade = 'D'
        recommendation = 'wait'
    else:
        grade = 'F'
        recommendation = 'avoid'

    # Tips
    tips = []
    if fish_count >= 2:
        tips.append(
            f'{fish_count} fish detected (VPIP>35%). '
            f'Prioritize value betting; reduce bluff frequency.'
        )
    if reg_count >= 3:
        tips.append(
            f'{reg_count} regulars at this table. '
            f'Win rate will be lower — consider a different table.'
        )
    if avg_af < 1.5:
        tips.append(
            'Very passive table (avg AF<1.5). '
            'Bet for value relentlessly; bluffs are less effective.'
        )
    if avg_af > 3.5:
        tips.append(
            'Aggressive table (avg AF>3.5). '
            'Play more GTO; avoid light calls.'
        )
    if avg_stack < 60:
        tips.append(
            f'Short-stack table (avg {avg_stack:.0f}BB). '
            f'Implied odds are reduced; prefer tight value ranges.'
        )
    if rake_pct > 0.05:
        tips.append(
            f'High rake ({rake_pct:.0%}): tighten marginally profitable calls. '
            f'Win rate must be >2 BB/100 higher to compensate vs lower-rake site.'
        )
    if not tips:
        tips.append(
            f'Avg VPIP={avg_vpip:.0%} AF={avg_af:.1f}. '
            f'Standard table — play your default GTO-adjusted strategy.'
        )

    reasoning = (
        f'Table {table_id}: {n} players, VPIP={avg_vpip:.0%} PFR={avg_pfr:.0%} '
        f'AF={avg_af:.1f} stack={avg_stack:.0f}BB. '
        f'Fish={fish_count} regs={reg_count}. '
        f'Score: fish={fs:.1f} passive={ps:.1f} stack={ss:.1f} '
        f'overall={overall:.1f}/10. '
        f'Est EV={estimated_ev:+.1f}BB/100. '
        f'Grade: {grade}. {recommendation.upper()}.'
    )

    return TableScore(
        table_id=table_id,
        num_players=n,
        avg_vpip=round(avg_vpip, 3),
        avg_pfr=round(avg_pfr, 3),
        avg_af=round(avg_af, 2),
        avg_stack_bb=round(avg_stack, 1),
        fish_count=fish_count,
        reg_count=reg_count,
        fish_score=round(fs, 2),
        passivity_score=round(ps, 2),
        stack_score=round(ss, 2),
        overall_score=round(overall, 2),
        estimated_ev_bb100=round(estimated_ev, 1),
        best_seat=best_seat,
        best_seat_reason=seat_reason,
        grade=grade,
        recommendation=recommendation,
        reasoning=reasoning,
        tips=tips,
    )


def rank_tables(
    tables: List[Dict],
    rake_pct: float = 0.05,
    rake_cap_bb: float = 2.0,
) -> List[TableScore]:
    """
    Rank multiple tables for game selection.

    Args:
        tables:  List of dicts with 'table_id' and 'players' (list of dicts).
                 Each player dict: {'vpip', 'pfr', 'af', 'stack_bb', 'seat'}
        rake_pct:     Site rake percentage
        rake_cap_bb:  Rake cap in BBs

    Returns:
        List[TableScore] sorted by overall_score descending (best first)
    """
    scores = []
    for t in tables:
        tid = t.get('table_id', 'unknown')
        raw_players = t.get('players', [])
        profiles = []
        for p in raw_players:
            profiles.append(PlayerProfile(
                vpip=p.get('vpip', 0.25),
                pfr=p.get('pfr', 0.18),
                af=p.get('af', 2.0),
                stack_bb=p.get('stack_bb', 100.0),
                hands_observed=p.get('hands_observed', 30),
                seat=p.get('seat', 0),
            ))
        score = evaluate_table(tid, profiles, rake_pct, rake_cap_bb)
        scores.append(score)

    scores.sort(key=lambda x: x.overall_score, reverse=True)
    return scores


def selection_one_liner(score: TableScore) -> str:
    """Single-line overlay summary for a table."""
    return (
        f'Table {score.table_id} [{score.grade}]: '
        f'fish={score.fish_count} VPIP={score.avg_vpip:.0%} '
        f'score={score.overall_score:.1f}/10 '
        f'EV={score.estimated_ev_bb100:+.1f}BB/100 '
        f'→ {score.recommendation.upper()}'
    )
