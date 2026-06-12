"""
Game Selection Advisor (game_selection_advisor.py)

"The best poker players in the world spend 40% of their time finding good games."
Game selection is worth more than any in-game adjustment.
A 5BB/100 winner at a soft table can become a -3BB/100 loser at a reg table.

TABLE SCORING (0-100):
  Fish presence:     25+ pts per fish at table (VPIP>40% players)
  Stack depth:       Deeper stacks = better implied odds for skilled players
  Player count:      6-max or HU tables have less rake per hand than 9-max
  Table aggression:  Moderate aggression is ideal; very high = dangerous reg table
  Reg density:       Fewer regs = better
  Ante / straddle:   Antes increase pot size and implied odds (often good)

SEAT SELECTION:
  - Sit LEFT of fish/loose passive (act after them, extract maximum value)
  - Sit RIGHT of aggressive 3-bettors (avoid being squeezed)
  - Avoid sitting left of an aggressive player unless you have strong reads

WIN RATE ESTIMATE:
  Based on table composition, estimate expected BB/100
  Fish table: +8 to +15 BB/100
  Balanced table: +2 to +5 BB/100
  Reg-heavy table: -3 to +1 BB/100
  All-reg table: -5 to -2 BB/100 (unless you are among the best regs)

TABLE TYPES:
  fish_heavy:     3+ fish at 6-max table. Maximum value extraction.
  soft_average:   1-2 fish at 6-max. Normal win rate.
  balanced:       Mix of fish and regs. Moderate win rate.
  reg_heavy:      Mostly tight-aggressive regulars. Hard game.
  all_reg:        Pure reg table. Avoid unless you have specific edge.
  short_handed:   4 or fewer players. HU skill required.
  nit_table:      Extremely tight table. Steal profits, hard to get paid.

Usage:
    from poker.game_selection_advisor import advise_game_selection
    from poker.game_selection_advisor import GameSelectionAdvice, game_selection_one_liner

    advice = advise_game_selection(
        player_vpips=[0.48, 0.32, 0.26, 0.55, 0.18, 0.22],
        player_stacks_bb=[120.0, 100.0, 85.0, 200.0, 60.0, 40.0],
        hero_seat=0,
        table_size=6,
        avg_pot_bb=15.0,
        rake_structure='nl100',
        hero_winrate_baseline_bb100=3.0,
    )
    print(game_selection_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List, Dict


# ── Table classification thresholds ─────────────────────────────────────────

_FISH_VPIP_THRESHOLD = 0.40    # VPIP >= 40% = fish
_NIT_VPIP_THRESHOLD  = 0.18    # VPIP <= 18% = nit (likely grinder/reg)
_REG_VPIP_THRESHOLD  = 0.25    # VPIP <= 25% = likely reg


def _classify_player(vpip: float) -> str:
    if vpip >= _FISH_VPIP_THRESHOLD:
        return 'fish'
    if vpip >= 0.30:
        return 'loose_passive'
    if vpip >= 0.26:
        return 'tag'
    if vpip >= _NIT_VPIP_THRESHOLD:
        return 'reg'
    return 'nit'


def _fish_count(vpips: List[float]) -> int:
    return sum(1 for v in vpips if v >= _FISH_VPIP_THRESHOLD)


def _reg_count(vpips: List[float]) -> int:
    return sum(1 for v in vpips if v <= _REG_VPIP_THRESHOLD)


def _avg_vpip(vpips: List[float]) -> float:
    return round(sum(vpips) / len(vpips), 3) if vpips else 0.30


def _table_type(fish_n: int, reg_n: int, total_n: int) -> str:
    if total_n <= 2:
        return 'short_handed'
    if fish_n >= 3:
        return 'fish_heavy'
    if fish_n == 2:
        return 'soft_average'
    if fish_n == 1:
        return 'balanced'
    if reg_n >= total_n - 1:
        return 'all_reg'
    # All nit table
    avg = sum(1 for _ in range(total_n))  # placeholder
    return 'reg_heavy'


# ── Table score (0-100) ───────────────────────────────────────────────────────

def _table_score(
    vpips: List[float],
    stacks_bb: List[float],
    hero_seat: int,
    table_size: int,
) -> float:
    """Score the table attractiveness 0-100."""
    n = len(vpips)
    score = 50.0  # baseline

    fish_n = _fish_count(vpips)
    reg_n = _reg_count(vpips)

    # Fish premium (+25 per fish, max +50)
    score += min(fish_n * 25.0, 50.0)

    # Reg penalty (-10 per reg, max -35)
    score -= min(reg_n * 10.0, 35.0)

    # Stack depth bonus
    avg_stack = sum(stacks_bb) / max(len(stacks_bb), 1)
    if avg_stack >= 150:
        score += 10.0  # deep stacks = better implied odds
    elif avg_stack >= 100:
        score += 5.0
    elif avg_stack < 50:
        score -= 8.0   # short stack table limits implied odds

    # Fish proximity bonus: fish immediately to RIGHT of hero = best seat
    # Check if next player to act before hero (right side) is a fish
    right_seat = (hero_seat - 1) % n if n > 0 else 0
    left_seat = (hero_seat + 1) % n if n > 0 else 0
    if 0 <= right_seat < len(vpips) and vpips[right_seat] >= _FISH_VPIP_THRESHOLD:
        score += 15.0  # fish to right = position advantage
    if 0 <= left_seat < len(vpips) and vpips[left_seat] >= _FISH_VPIP_THRESHOLD:
        score -= 8.0   # fish to left = you lose positional edge

    return round(max(0.0, min(100.0, score)), 1)


def _best_seat(vpips: List[float], hero_seat: int) -> int:
    """Return the best seat relative to player VPIP profiles."""
    n = len(vpips)
    if n == 0:
        return 0
    # Best: sit left of biggest fish (position on fish = maximum value)
    best_seat = hero_seat
    best_score = -1.0
    for candidate in range(n):
        if candidate == hero_seat:
            continue
        # Score this candidate seat: want fish to candidate's right
        right = (candidate - 1) % n
        left = (candidate + 1) % n
        s = 0.0
        if vpips[right] >= _FISH_VPIP_THRESHOLD:
            s += 30.0 * vpips[right]  # value of having fish to right
        if vpips[left] >= _FISH_VPIP_THRESHOLD:
            s -= 10.0  # fish to left is bad
        if s > best_score:
            best_score = s
            best_seat = candidate
    return best_seat


def _seat_quality(hero_seat: int, vpips: List[float]) -> str:
    n = len(vpips)
    if n == 0:
        return 'unknown'
    right = (hero_seat - 1) % n
    left = (hero_seat + 1) % n
    has_fish_right = vpips[right] >= _FISH_VPIP_THRESHOLD if 0 <= right < n else False
    has_reg_left = vpips[left] <= _REG_VPIP_THRESHOLD if 0 <= left < n else False
    if has_fish_right and not has_reg_left:
        return 'excellent'
    if has_fish_right:
        return 'good'
    if has_reg_left:
        return 'poor'
    return 'average'


def _estimate_winrate(
    table_type: str,
    fish_n: int,
    hero_winrate_baseline: float,
) -> float:
    """Estimate BB/100 adjustment from baseline given table type."""
    adj = {
        'fish_heavy':   +8.0,
        'soft_average': +4.0,
        'balanced':     +1.0,
        'reg_heavy':    -4.0,
        'all_reg':      -6.0,
        'short_handed': +2.0,
        'nit_table':    -1.0,
    }.get(table_type, 0.0)
    # Fish bonus on top
    adj += fish_n * 2.0
    return round(hero_winrate_baseline + adj, 1)


def _exploit_notes(vpips: List[float], hero_seat: int) -> List[str]:
    """Generate specific exploit notes for each player at table."""
    notes = []
    n = len(vpips)
    for seat, vpip in enumerate(vpips):
        if seat == hero_seat:
            continue
        ptype = _classify_player(vpip)
        direction = 'to your right' if seat == (hero_seat - 1) % n else (
            'to your left' if seat == (hero_seat + 1) % n else f'seat {seat}'
        )
        if ptype == 'fish':
            notes.append(
                f'FISH (seat {seat}, VPIP={vpip:.0%}) {direction}: '
                f'Value bet 3 streets. Never bluff. Seat left of this player for max value.'
            )
        elif ptype == 'nit':
            notes.append(
                f'NIT (seat {seat}, VPIP={vpip:.0%}) {direction}: '
                f'Steal blinds freely. Fold to their raises. Do not bluff-catch vs their bets.'
            )
        elif ptype == 'loose_passive':
            notes.append(
                f'LOOSE PASSIVE (seat {seat}, VPIP={vpip:.0%}) {direction}: '
                f'Value bet wide. They call too much. Stop bluffing.'
            )
    return notes[:5]  # cap output


@dataclass
class GameSelectionAdvice:
    """Table and seat selection analysis."""
    player_vpips: List[float]
    player_stacks_bb: List[float]
    hero_seat: int
    table_size: int
    avg_pot_bb: float
    rake_structure: str
    hero_winrate_baseline_bb100: float

    # Analysis
    fish_count: int
    reg_count: int
    avg_table_vpip: float
    table_type: str                   # 'fish_heavy', 'balanced', 'reg_heavy', etc.
    table_score: float                # 0-100
    seat_quality: str                 # 'excellent', 'good', 'average', 'poor'
    best_available_seat: int

    # Win rate
    estimated_winrate_bb100: float    # adjusted from baseline
    winrate_confidence: str           # 'high' (3+ fish) / 'medium' / 'low'

    # Decision
    stay_or_leave: str                # 'stay', 'leave', 'stay_and_move_seat'
    verdict: str

    player_types: List[str]           # classification per seat
    exploit_notes: List[str]
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_game_selection(
    player_vpips: List[float] = None,
    player_stacks_bb: List[float] = None,
    hero_seat: int = 0,
    table_size: int = 6,
    avg_pot_bb: float = 15.0,
    rake_structure: str = 'nl100',
    hero_winrate_baseline_bb100: float = 3.0,
) -> GameSelectionAdvice:
    """
    Analyze table attractiveness and provide game selection advice.

    Args:
        player_vpips:              List of VPIP for each seat (including hero) as decimals (0.28 = 28%)
        player_stacks_bb:          Stack depth in BB for each seat
        hero_seat:                 Hero's seat index (0-based)
        table_size:                Max seats at this table
        avg_pot_bb:                Average pot size in BB
        rake_structure:            Rake structure name (e.g., 'nl100', 'live_1_2')
        hero_winrate_baseline_bb100: Hero's typical BB/100 at a balanced table

    Returns:
        GameSelectionAdvice
    """
    if player_vpips is None:
        player_vpips = [0.28, 0.32, 0.48, 0.20, 0.35, 0.22]
    if player_stacks_bb is None:
        player_stacks_bb = [100.0] * len(player_vpips)

    # Remove hero from player analysis
    opponent_vpips = [v for i, v in enumerate(player_vpips) if i != hero_seat]

    fish_n = _fish_count(opponent_vpips)
    reg_n = _reg_count(opponent_vpips)
    avg_vpip_val = _avg_vpip(opponent_vpips)
    ttype = _table_type(fish_n, reg_n, len(player_vpips) - 1)
    score = _table_score(player_vpips, player_stacks_bb, hero_seat, table_size)
    seat_qual = _seat_quality(hero_seat, player_vpips)
    best_seat = _best_seat(player_vpips, hero_seat)
    est_wr = _estimate_winrate(ttype, fish_n, hero_winrate_baseline_bb100)
    wr_conf = 'high' if fish_n >= 3 else ('medium' if fish_n >= 1 else 'low')
    player_types = [_classify_player(v) for v in player_vpips]
    exploit_notes_list = _exploit_notes(player_vpips, hero_seat)

    # Decision
    if score >= 75:
        stay = 'stay'
        verdict = (
            f'EXCELLENT TABLE (score={score:.0f}): {fish_n} fish detected. '
            f'Estimated winrate {est_wr:+.1f}BB/100. Do NOT leave this table.'
        )
    elif score >= 55:
        if seat_qual in ('poor',) and best_seat != hero_seat:
            stay = 'stay_and_move_seat'
            verdict = (
                f'GOOD TABLE but POOR SEAT (score={score:.0f}). '
                f'Consider moving to seat {best_seat} for better position on fish. '
                f'Estimated winrate {est_wr:+.1f}BB/100.'
            )
        else:
            stay = 'stay'
            verdict = (
                f'DECENT TABLE (score={score:.0f}): {fish_n} fish. '
                f'Estimated winrate {est_wr:+.1f}BB/100. Reasonable game to stay.'
            )
    elif score >= 35:
        stay = 'stay_and_move_seat' if best_seat != hero_seat else 'stay'
        verdict = (
            f'MARGINAL TABLE (score={score:.0f}): few fish, {reg_n} regs. '
            f'Estimated winrate {est_wr:+.1f}BB/100. Look for better tables.'
        )
    else:
        stay = 'leave'
        verdict = (
            f'LEAVE THIS TABLE (score={score:.0f}): '
            f'Only {fish_n} fish, {reg_n} regs. '
            f'Estimated winrate {est_wr:+.1f}BB/100 — your edge is minimal. '
            f'Find a softer game or take a break.'
        )

    reasoning = (
        f'Table analysis: {fish_n} fish ({[f"{v:.0%}" for v in opponent_vpips if v >= 0.40]}). '
        f'{reg_n} regs. Avg VPIP={avg_vpip_val:.0%}. Type={ttype}. '
        f'Score={score:.0f}/100. Seat quality={seat_qual}. '
        f'Est winrate={est_wr:+.1f}BB/100 (baseline={hero_winrate_baseline_bb100:+.1f}). '
        f'Recommendation: {stay}.'
    )

    tips = []
    if fish_n > 0:
        fish_seats = [i for i, v in enumerate(player_vpips) if v >= _FISH_VPIP_THRESHOLD and i != hero_seat]
        tips.append(
            f'FISH IDENTIFIED (seats {fish_seats}): '
            f'Value bet 3 streets vs fish. Never bluff. '
            f'Ideally sit to the LEFT of them — you act after them on every street. '
            f'Bet 70-90% of pot vs fish when you have top pair+.'
        )
    if reg_n >= 3:
        tips.append(
            f'REG-HEAVY TABLE ({reg_n} regs detected): '
            f'Adjust: tighten opening ranges, reduce bluff frequency, '
            f'respect 3-bets more, avoid marginal spots. '
            f'Consider moving to a softer table if one is available.'
        )
    if seat_qual == 'poor':
        tips.append(
            f'POOR SEAT: You are NOT in position on the fish. '
            f'Best seat available: {best_seat}. '
            f'Request seat change ASAP or wait for it. '
            f'Being out of position on fish reduces your expected value by 2-4BB/100.'
        )
    if seat_qual == 'excellent':
        tips.append(
            f'EXCELLENT SEAT: Fish is to your right — you have position advantage. '
            f'ISO-raise fish when others fold to you. '
            f'Widen your opening range vs fish in position.'
        )
    if score < 40:
        tips.append(
            f'GAME SELECTION ACTION: Open new table lobby immediately. '
            f'Look for tables with: avg VPIP > 30%, any player with VPIP > 45%, '
            f'short stacks (likely fish who are losing). '
            f'An hour in a better game is worth more than 2 hours grinding this one.'
        )
    if not tips:
        tips.append(
            f'{ttype.replace("_", " ").title()} table. Score={score:.0f}/100. '
            f'Fish={fish_n} Regs={reg_n}. Est winrate {est_wr:+.1f}BB/100. '
            f'Seat quality={seat_qual}.'
        )

    return GameSelectionAdvice(
        player_vpips=[round(v, 3) for v in player_vpips],
        player_stacks_bb=[round(s, 1) for s in player_stacks_bb],
        hero_seat=hero_seat,
        table_size=table_size,
        avg_pot_bb=round(avg_pot_bb, 1),
        rake_structure=rake_structure.lower(),
        hero_winrate_baseline_bb100=round(hero_winrate_baseline_bb100, 1),
        fish_count=fish_n,
        reg_count=reg_n,
        avg_table_vpip=avg_vpip_val,
        table_type=ttype,
        table_score=score,
        seat_quality=seat_qual,
        best_available_seat=best_seat,
        estimated_winrate_bb100=est_wr,
        winrate_confidence=wr_conf,
        stay_or_leave=stay,
        verdict=verdict,
        player_types=player_types,
        exploit_notes=exploit_notes_list,
        reasoning=reasoning,
        tips=tips,
    )


def game_selection_one_liner(r: GameSelectionAdvice) -> str:
    return (
        f'[GS {r.table_type}|{r.table_size}-max] {r.stay_or_leave.upper()} | '
        f'score={r.table_score:.0f}/100 fish={r.fish_count} regs={r.reg_count} | '
        f'wr={r.estimated_winrate_bb100:+.1f}BB/100 seat={r.seat_quality}'
    )
