"""
ICM (Independent Chip Model) calculator.

Uses the Malmuth-Harville recursive algorithm:
  P(player i finishes k-th) computed by summing over all orderings where
  each player's probability of finishing next is proportional to their chips.

Complexity: O(n! / (n-p)!) where p = len(prizes), fast for p ≤ 5.
For 9 players with top-3 prizes: 9×8×7 = 504 leaf nodes — instant.

Key outputs:
  icm_equity(stacks, prizes) → [$equity per player]
  icm_push_fold(hero_idx, win_stack, lose_stack, stacks, prizes)
      → ICM EV of pushing (winning or losing all-in)
  risk_premium(hero_idx, stacks, prizes) → how much to discount chip EV
"""

from typing import List, Tuple


def icm_equity(stacks: List[int], prizes: List[float]) -> List[float]:
    """
    Calculate ICM equity ($) for each player.

    Args:
        stacks: chip counts for each player (same order as prizes output)
        prizes: prize payouts in descending order, e.g. [5000, 3000, 2000]
                Can be shorter than stacks (unplaced players get $0).

    Returns:
        List of $ equity, same length as stacks, sums to sum(prizes).
    """
    n       = len(stacks)
    equity  = [0.0] * n
    prizes_ = list(prizes)

    def recurse(remaining: list, prizes_left: list, path_prob: float):
        if not prizes_left or not remaining:
            return
        rem_chips = sum(stacks[p] for p in remaining)
        if rem_chips == 0:
            return
        prize = prizes_left[0]
        for p in remaining:
            prob = stacks[p] / rem_chips
            equity[p] += path_prob * prob * prize
            recurse(
                [q for q in remaining if q != p],
                prizes_left[1:],
                path_prob * prob,
            )

    recurse(list(range(n)), prizes_, 1.0)
    return equity


def icm_push_ev(
    hero_idx: int,
    win_stack: int,
    lose_stack: int,
    stacks: List[int],
    prizes: List[float],
    win_prob: float,
) -> Tuple[float, float, float]:
    """
    EV of pushing all-in given win/lose chip outcomes.

    Args:
        hero_idx:   hero's position in the stacks list
        win_stack:  hero's chips if the all-in is won
        lose_stack: hero's chips if the all-in is lost (0 = eliminated)
        stacks:     current chip counts
        prizes:     prize structure
        win_prob:   hero's equity (0-1) in the all-in

    Returns:
        (icm_ev_push, icm_ev_fold, chip_ev_push) in prize units
    """
    base_eq   = icm_equity(stacks, prizes)[hero_idx]

    win_stacks  = stacks[:]
    win_stacks[hero_idx] = win_stack
    win_eq    = icm_equity(win_stacks, prizes)[hero_idx]

    lose_stacks = stacks[:]
    lose_stacks[hero_idx] = lose_stack
    if lose_stack == 0:
        # Remove eliminated player
        lose_stacks.pop(hero_idx)
        eq_list   = icm_equity(lose_stacks, prizes)
        lose_eq   = 0.0           # hero is out
    else:
        lose_eq   = icm_equity(lose_stacks, prizes)[hero_idx]

    icm_ev_push = win_prob * win_eq + (1 - win_prob) * lose_eq
    chip_ev_push = win_prob * win_stack + (1 - win_prob) * lose_stack

    return icm_ev_push, base_eq, chip_ev_push


def risk_premium(
    hero_idx: int,
    stacks: List[int],
    prizes: List[float],
) -> float:
    """
    ICM risk premium: how many % points of equity hero must gain
    in an all-in to justify risking elimination.

    A positive risk premium means hero needs MORE equity than chip-EV
    would suggest — ICM makes calling/pushing riskier near the money.
    """
    n     = len(stacks)
    total = sum(stacks)
    # Chip-EV fair share of a double-up
    double_chips = min(stacks[hero_idx] * 2, total)
    chip_gain_pct = (double_chips - stacks[hero_idx]) / total

    # ICM gain from doubling up
    current_eq = icm_equity(stacks, prizes)[hero_idx]
    doubled_stacks = stacks[:]
    doubled_stacks[hero_idx] = min(doubled_stacks[hero_idx] * 2, total)
    doubled_eq = icm_equity(doubled_stacks, prizes)[hero_idx]
    icm_gain_pct = (doubled_eq - current_eq) / sum(prizes) if sum(prizes) > 0 else 0

    return chip_gain_pct - icm_gain_pct   # positive → pay risk premium


def format_icm_table(stacks: List[int], prizes: List[float],
                     names: List[str] = None) -> str:
    """Return a formatted string table for display."""
    eq = icm_equity(stacks, prizes)
    total = sum(stacks)
    lines = [f"{'Player':12s} {'Chips':>8s} {'Chip%':>7s} {'ICM$':>10s} {'ICM%':>7s}"]
    lines.append('-' * 48)
    for i, (s, e) in enumerate(zip(stacks, eq)):
        name  = (names[i] if names and i < len(names) else f'Seat {i+1}')[:12]
        chip_pct = s / total * 100 if total else 0
        icm_pct  = e / sum(prizes) * 100 if sum(prizes) else 0
        lines.append(f"{name:12s} {s:>8,} {chip_pct:>6.1f}% {e:>10,.0f} {icm_pct:>6.1f}%")
    return '\n'.join(lines)
