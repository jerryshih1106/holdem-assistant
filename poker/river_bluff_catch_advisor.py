"""
River Bluff Catch Advisor (river_bluff_catch_advisor.py)

Bluff catching on the river is one of the most psychologically difficult decisions
in poker. Unlike normal calls (where equity matters), a bluff catch is made with
hands that rarely win at showdown — the ONLY reason to call is if villain is
bluffing often enough.

This module is specifically for river calls with very low SDV (0-35% equity),
where the call decision is entirely about:
  1. Villain's bluffing frequency
  2. Bet size (determines alpha = break-even fold frequency villain needs to bluff)
  3. Blocker effects (holding cards that reduce villain's value combos)
  4. Hand reading (villain's line suggests polarized range)

Key formula:
  alpha = bet / (pot + 2 × bet)  = break-even equity needed
  If villain_bluff_freq > alpha: call is +EV
  If villain_bluff_freq < alpha: fold is correct

How to estimate villain bluff frequency:
  - From HUD: if villain bets river after missed draws and has high AF
  - From betting line: triple-barrel = polarized range; single-barrel = wider
  - From bet sizing: overbet → very polarized; small bet → wider range
  - From blockers: if villain holds flush draw that missed, they may bluff

Bluff catch hand categories:
  1. Pure bluff catcher: e.g., Kx on AQJ9x board (K blocks villain's Broadway)
     → Only wins vs bluffs; loses to all value bets
  2. SDV bluff catcher: e.g., mid pair on A-high board (some SDV but usually losing)
     → Wins vs some SDV hands AND vs bluffs
  3. Float-turned-catcher: Called flop/turn with draws, missed, but holding blockers
     → Pure bluff catcher status

Blocker analysis:
  - Holding Ah on AQ982 (three-flush board): blocks some nut flush combos
  - Holding Kd on Qd8d3h2c (missed flush draw): blocks Kd-x flush combos villain could have
  - Holding Jd on KT95 board: blocks J8 straight combos in villain's value range

Frequency of villain bluffs by line:
  - Value-bet line (2 barrels): ~30-45% bluffs in range (GTO)
  - Overbet line: ~45-55% bluffs (necessary for polar betting to be balanced)
  - Triple barrel: ~35-50% bluffs depending on board
  - Passive check-then-bet: ~20-35% bluffs (less polarized)

Usage:
    from poker.river_bluff_catch_advisor import advise_river_bluff_catch
    from poker.river_bluff_catch_advisor import RiverBluffCatchAdvice, bluff_catch_one_liner

    result = advise_river_bluff_catch(
        hero_hand_sdv=0.20,
        villain_bet_pct=0.75,
        villain_line='triple_barrel',
        villain_af=2.5,
        villain_wtsd=0.30,
        villain_river_bet_pct=0.40,
        hero_has_blocker=True,
        blocker_strength='medium',
        board_type='dry',
        pot_bb=40.0,
        n_value_combos=12,
        n_bluff_combos_est=8,
    )
    print(result.action, result.bluff_catch_ev)
"""

from dataclasses import dataclass, field
from typing import List


def _alpha(bet_pct: float) -> float:
    """Break-even equity needed to call: alpha = bet / (pot + 2*bet)."""
    return round(bet_pct / (1.0 + 2.0 * bet_pct), 4)


def _villain_bluff_freq_from_combos(n_value: int, n_bluff: int) -> float:
    """If combo counts known: bluff freq = n_bluff / (n_value + n_bluff)."""
    total = n_value + n_bluff
    if total <= 0:
        return 0.35  # default
    return round(n_bluff / total, 3)


def _villain_bluff_freq_from_line(
    villain_line: str,
    villain_af: float,
    villain_wtsd: float,
    villain_river_bet_pct: float,
) -> float:
    """
    Estimate villain's bluff frequency from their betting line and HUD stats.
    """
    # Base bluff frequency by line type
    base = {
        'triple_barrel': 0.42,
        'double_barrel': 0.38,
        'single_barrel_turn': 0.35,
        'check_raise_river': 0.30,
        'overbet': 0.48,
        'donk_bet_river': 0.25,
        'delayed_cbet': 0.32,
    }.get(villain_line.lower(), 0.35)

    # High AF → bluffs more
    if villain_af >= 3.0:
        base += 0.08
    elif villain_af >= 2.0:
        base += 0.04
    elif villain_af < 1.0:
        base -= 0.12

    # High WTSD → calls a lot but doesn't bluff as often
    if villain_wtsd > 0.38:
        base -= 0.05

    # High river bet frequency → more bluffs in range
    if villain_river_bet_pct > 0.55:
        base += 0.06
    elif villain_river_bet_pct < 0.30:
        base -= 0.06

    return round(min(0.75, max(0.05, base)), 3)


def _blocker_adjustment(
    hero_has_blocker: bool,
    blocker_strength: str,
) -> float:
    """Adjustment to bluff frequency based on blocker effect (+ve = more bluffs in villain's range)."""
    if not hero_has_blocker:
        return 0.0
    adj = {
        'strong': 0.08,   # Ace blocker for nut flush, etc.
        'medium': 0.04,
        'weak': 0.01,
    }.get(blocker_strength.lower(), 0.03)
    return adj


def _bluff_catch_ev(
    pot_bb: float,
    bet_pct: float,
    villain_bluff_freq: float,
    hero_sdv: float,
) -> float:
    """
    EV of calling as bluff catcher.
    EV = P(bluff) × pot - P(value) × call_cost + hero_sdv × P(bluff) × pot × 0.10
    Simplified: EV = villain_bluff_freq × pot - (1 - villain_bluff_freq) × bet
    (The SDV adjustment is small and omitted for simplicity)
    """
    call_cost = pot_bb * bet_pct
    total_pot = pot_bb + 2 * call_cost
    # Hero wins total pot when villain bluffs, loses call when villain has value
    ev = villain_bluff_freq * total_pot - (1 - villain_bluff_freq) * call_cost
    return round(ev, 2)


def _fold_ev(pot_bb: float) -> float:
    """EV of folding: always 0 (reference point)."""
    return 0.0


def _action(
    bluff_catch_ev: float,
    villain_bluff_freq: float,
    alpha: float,
    hero_sdv: float,
    board_type: str,
    villain_line: str,
) -> tuple:
    """(action, confidence)"""
    if bluff_catch_ev > 0:
        confidence = min(1.0, bluff_catch_ev / 10.0)  # scale by EV magnitude
        return 'call', round(confidence, 2)

    # Below break-even but close: marginal
    if villain_bluff_freq >= alpha * 0.85:
        return 'fold_marginal', 0.40  # close to indifference

    return 'fold', round(max(0.50, 1.0 - villain_bluff_freq / alpha), 2)


@dataclass
class RiverBluffCatchAdvice:
    """Advice for river bluff catch decision."""
    hero_hand_sdv: float       # Showdown value (0-1)
    villain_bet_pct: float     # Bet size as fraction of pot
    villain_line: str
    villain_af: float
    villain_wtsd: float
    villain_river_bet_pct: float
    hero_has_blocker: bool
    blocker_strength: str
    board_type: str
    pot_bb: float
    n_value_combos: int
    n_bluff_combos_est: int

    # Decision
    action: str                # 'call', 'fold', 'fold_marginal'
    confidence: float          # 0-1 confidence in action

    # Math
    alpha: float               # Break-even equity needed
    villain_bluff_freq: float  # Estimated bluff frequency
    blocker_adj: float         # How much blocker helps
    bluff_catch_ev: float      # EV of calling
    call_cost_bb: float

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_river_bluff_catch(
    hero_hand_sdv: float = 0.20,
    villain_bet_pct: float = 0.75,
    villain_line: str = 'double_barrel',
    villain_af: float = 2.5,
    villain_wtsd: float = 0.30,
    villain_river_bet_pct: float = 0.40,
    hero_has_blocker: bool = False,
    blocker_strength: str = 'medium',
    board_type: str = 'dry',
    pot_bb: float = 40.0,
    n_value_combos: int = 0,
    n_bluff_combos_est: int = 0,
) -> RiverBluffCatchAdvice:
    """
    Advise on a river bluff catch decision.

    Args:
        hero_hand_sdv:        Hero's showdown value (0-1); pure catcher = 0-0.15
        villain_bet_pct:      Villain's bet size as fraction of pot
        villain_line:         Villain's betting line (describes the street sequence):
                              'triple_barrel', 'double_barrel', 'overbet',
                              'check_raise_river', 'delayed_cbet', etc.
        villain_af:           Villain's aggression factor
        villain_wtsd:         Villain's WTSD (went to showdown)
        villain_river_bet_pct: Villain's river bet frequency
        hero_has_blocker:     True if hero has cards blocking villain's value combos
        blocker_strength:     'strong', 'medium', 'weak' (if hero_has_blocker)
        board_type:           'dry', 'medium', 'wet'
        pot_bb:               Pot size before villain's bet
        n_value_combos:       If known: number of villain's value combos
        n_bluff_combos_est:   If known: estimated villain bluff combos

    Returns:
        RiverBluffCatchAdvice
    """
    alpha_val = _alpha(villain_bet_pct)
    blk_adj = _blocker_adjustment(hero_has_blocker, blocker_strength)

    # Determine bluff frequency: use combo counts if available, else estimate from line
    if n_value_combos > 0 or n_bluff_combos_est > 0:
        base_bluff_freq = _villain_bluff_freq_from_combos(n_value_combos, n_bluff_combos_est)
    else:
        base_bluff_freq = _villain_bluff_freq_from_line(
            villain_line, villain_af, villain_wtsd, villain_river_bet_pct
        )

    # Adjust for blocker (hero holding blocker → villain has fewer value combos → more of their bets are bluffs)
    adj_bluff_freq = round(min(0.80, base_bluff_freq + blk_adj), 3)

    call_cost = round(pot_bb * villain_bet_pct, 1)
    ev = _bluff_catch_ev(pot_bb, villain_bet_pct, adj_bluff_freq, hero_hand_sdv)
    action, confidence = _action(ev, adj_bluff_freq, alpha_val, hero_hand_sdv, board_type, villain_line)

    # Build reasoning
    if action == 'call':
        reason = (
            f'CALL: villain_bluff_freq={adj_bluff_freq:.0%} > alpha={alpha_val:.0%}. '
            f'EV_call={ev:.1f}BB. '
            f'{"Blocker boosts bluff est by " + f"{blk_adj:.0%}. " if hero_has_blocker else ""}'
            f'Line ({villain_line}) suggests polarized range.'
        )
    elif action == 'fold_marginal':
        reason = (
            f'MARGINAL FOLD: villain_bluff_freq={adj_bluff_freq:.0%} ~= alpha={alpha_val:.0%}. '
            f'EV_call={ev:.1f}BB (near 0). '
            f'Close to indifference — can call or fold without major EV impact.'
        )
    else:
        reason = (
            f'FOLD: villain_bluff_freq={adj_bluff_freq:.0%} < alpha={alpha_val:.0%}. '
            f'EV_call={ev:.1f}BB (negative). '
            f'Not enough bluffs in villain range to justify call.'
        )

    # Tips
    tips = []
    if villain_bet_pct >= 1.0:
        tips.append(
            f'Overbet ({villain_bet_pct:.0%} pot): villain is polarized between nuts and bluffs. '
            f'Alpha={alpha_val:.0%} — you need villain bluffing {alpha_val:.0%} of river bets. '
            f'{"Call with blockers to nuts." if hero_has_blocker else "Fold without blockers or nut blockers."}'
        )
    if villain_line == 'triple_barrel':
        tips.append(
            'Triple barrel: villain is highly polarized. '
            'Most passive players do not triple-barrel without value. '
            'Only call if you have strong reads on villain as an aggressive bluffer (AF>=3).'
        )
    if hero_has_blocker and blocker_strength == 'strong':
        tips.append(
            'Strong blocker: you hold cards that significantly reduce villain\'s value combos. '
            'This increases villain\'s bluff percentage. '
            'Call wider than you would without the blocker.'
        )
    if action == 'fold_marginal':
        tips.append(
            f'Near-indifference spot (villain_bluff={adj_bluff_freq:.0%} vs alpha={alpha_val:.0%}). '
            f'Consider additional reads: Is villain known as a bluffer? '
            f'Have you seen them bluff-catch-able hands at showdown before? '
            f'Use those reads to tip the decision.'
        )
    if board_type == 'wet' and action == 'call':
        tips.append(
            'Wet board: villain may have missed draws too. '
            'Bluff frequency is naturally higher on wet boards since '
            'more draws miss → more bluff candidates in villain\'s range.'
        )
    if not tips:
        tips.append(
            f'{action.upper()}: alpha={alpha_val:.0%}, villain_bluff={adj_bluff_freq:.0%}, '
            f'EV={ev:.1f}BB. '
            f'{"Call — villain bluffs enough." if action == "call" else "Fold — villain too value-heavy."}'
        )

    return RiverBluffCatchAdvice(
        hero_hand_sdv=round(hero_hand_sdv, 3),
        villain_bet_pct=round(villain_bet_pct, 3),
        villain_line=villain_line,
        villain_af=round(villain_af, 2),
        villain_wtsd=round(villain_wtsd, 3),
        villain_river_bet_pct=round(villain_river_bet_pct, 3),
        hero_has_blocker=hero_has_blocker,
        blocker_strength=blocker_strength,
        board_type=board_type,
        pot_bb=round(pot_bb, 1),
        n_value_combos=n_value_combos,
        n_bluff_combos_est=n_bluff_combos_est,
        action=action,
        confidence=confidence,
        alpha=alpha_val,
        villain_bluff_freq=adj_bluff_freq,
        blocker_adj=blk_adj,
        bluff_catch_ev=ev,
        call_cost_bb=call_cost,
        reasoning=reason,
        tips=tips,
    )


def bluff_catch_one_liner(result: RiverBluffCatchAdvice) -> str:
    return (
        f'[RBC {result.villain_line[:8]}|{result.board_type}] '
        f'{result.action.upper()} | '
        f'bluff={result.villain_bluff_freq:.0%} alpha={result.alpha:.0%} | '
        f'EV={result.bluff_catch_ev:.1f}BB | '
        f'bet={result.villain_bet_pct:.0%}pot'
    )
