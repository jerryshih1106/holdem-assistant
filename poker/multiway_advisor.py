"""
Multiway Pot Advisor (multiway_advisor.py)

Adjusts equity and strategy recommendations for 3+ player pots.
Multiway dynamics dramatically reduce the value of medium-strength
hands and require tighter value betting ranges.

Usage:
    from poker.multiway_advisor import advise_multiway, MultiwayAdvice
    advice = advise_multiway(
        hole_cards=['Ah', 'Kh'],
        community=['Ac', '7h', '2d'],
        pot_bb=15, eff_stack_bb=80,
        hero_equity=0.65, num_players=3,
        hero_pos='BTN', in_position=True,
    )
    print(advice.one_liner)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class PlayerEquity:
    """Equity breakdown for one player in a multiway pot."""
    player_label: str
    equity: float
    hand_class: str


@dataclass
class MultiwayAdvice:
    """Complete multiway strategy advice."""
    num_players: int
    hero_equity: float
    adjusted_equity: float    # equity adjusted for multiway dynamics
    equity_drop_pct: float    # how much equity drops vs heads-up

    # Strategy thresholds for this player count
    value_bet_threshold: float    # min equity needed to value bet
    commit_threshold: float       # min equity to stack off
    bluff_frequency_mult: float   # multiply HU bluff freq by this

    # Recommended action and sizing
    primary_action: str
    bet_size_pct: float        # recommended bet as fraction of pot
    pot_control: bool          # True = avoid inflating pot with medium hands

    # Street-specific advice
    flop_advice: str
    turn_advice: str
    river_advice: str

    # Key warnings
    warnings: List[str]

    # Summary
    one_liner: str
    confidence: str


# Equity adjustment factors per number of players
# In a 3-way pot, your raw equity understates the field's combined holdings
_EQUITY_ADJ: Dict[int, float] = {
    2: 1.00,
    3: 0.94,
    4: 0.90,
    5: 0.87,
    6: 0.84,
    7: 0.82,
    8: 0.80,
    9: 0.78,
}

# Minimum equity to value bet by player count (rough GTO thresholds)
_VALUE_THRESHOLD: Dict[int, float] = {
    2: 0.50,
    3: 0.58,
    4: 0.63,
    5: 0.67,
    6: 0.70,
    7: 0.72,
    8: 0.74,
    9: 0.76,
}

# Bluff frequency multiplier: in multiway pots, bluffing is less profitable
# because at least one opponent is more likely to have a strong hand
_BLUFF_MULT: Dict[int, float] = {
    2: 1.00,
    3: 0.60,
    4: 0.40,
    5: 0.28,
    6: 0.20,
    7: 0.15,
    8: 0.12,
    9: 0.10,
}


def advise_multiway(
    hole_cards: List[str],
    community: List[str],
    pot_bb: float,
    eff_stack_bb: float,
    hero_equity: float,
    num_players: int,
    hero_pos: str = 'BTN',
    in_position: bool = True,
    villain_vpip: float = 0.30,
) -> MultiwayAdvice:
    """
    Generate strategy advice adjusted for multiway pot dynamics.

    Args:
        hole_cards:    Hero's hole cards e.g. ['Ah', 'Kh']
        community:     Community cards (0/3/4/5 cards)
        pot_bb:        Current pot in big blinds
        eff_stack_bb:  Effective stack in big blinds
        hero_equity:   Hero's raw equity (0-1) from Monte Carlo
        num_players:   Total players in the hand (including hero)
        hero_pos:      Hero's position ('BTN', 'CO', 'BB', etc.)
        in_position:   True if hero acts last postflop
        villain_vpip:  Average villain VPIP (used for range reasoning)

    Returns:
        MultiwayAdvice with adjusted thresholds and strategy
    """
    n = max(2, min(9, num_players))
    adj_factor = _EQUITY_ADJ.get(n, 0.78)
    adjusted_eq = hero_equity * adj_factor
    equity_drop = (1 - adj_factor) * 100

    value_thresh = _VALUE_THRESHOLD.get(n, 0.76)
    commit_thresh = value_thresh + 0.12    # need significant edge to stack off
    bluff_mult = _BLUFF_MULT.get(n, 0.10)

    spr = eff_stack_bb / pot_bb if pot_bb > 0 else 99

    # ── Pot control decision ─────────────────────────────────────────────
    # Control pot with medium hands (near threshold) in multiway
    pot_control = (adjusted_eq < value_thresh + 0.08) and (n >= 3)

    # ── Primary action ────────────────────────────────────────────────────
    if adjusted_eq >= commit_thresh and spr < 4:
        primary_action = 'commit / push'
        bet_size_pct = 1.0
    elif adjusted_eq >= value_thresh:
        if in_position and n <= 3:
            primary_action = 'value bet'
            bet_size_pct = 0.50 if n == 2 else 0.40  # smaller multiway
        elif not in_position and n >= 4:
            primary_action = 'lead small or check'
            bet_size_pct = 0.33
        else:
            primary_action = 'value bet small'
            bet_size_pct = 0.40
    elif adjusted_eq >= value_thresh - 0.10:
        primary_action = 'check / pot control'
        bet_size_pct = 0.0
    else:
        if hero_equity * bluff_mult > 0.10:
            primary_action = 'check (or small probe OOP)'
            bet_size_pct = 0.25 * bluff_mult
        else:
            primary_action = 'check / fold'
            bet_size_pct = 0.0

    # ── Street-specific advice ────────────────────────────────────────────
    n_comm = len(community)
    if n_comm <= 3:  # flop
        if n >= 4:
            flop_advice = (f'Multiway flop ({n} players): tighten c-bet range to '
                           f'top 30% of your range. Prefer polarised: strong value '
                           f'and nut draws only. Avoid betting weak top pairs.')
        elif n == 3:
            flop_advice = ('3-way flop: c-bet only strong value (>55% equity) '
                           'or strong draws. Reduce bluff frequency by 40%.')
        else:
            flop_advice = 'Heads-up: standard c-bet strategy applies.'

        turn_advice = ('Turn: tighten further — only continue with hands that '
                       'have strong equity or nut potential.')
        river_advice = ('River: multiway pots need top 15-20% of your range '
                        'to value bet. Bluffing is rarely profitable.')
    elif n_comm == 4:  # turn
        flop_advice = 'Flop: already past.'
        if adjusted_eq >= value_thresh:
            turn_advice = (f'Turn value bet {bet_size_pct:.0%} pot with {hero_equity:.0%} '
                           f'equity. Protect your hand against draws.')
        else:
            turn_advice = ('Turn: check back or check-fold. Your adjusted equity '
                           f'({adjusted_eq:.0%}) is below the {value_thresh:.0%} '
                           f'multiway threshold for {n} players.')
        river_advice = 'River: evaluate based on runout — check with medium-strength hands.'
    else:  # river
        flop_advice = 'Flop/Turn: already past.'
        turn_advice = 'Turn: already past.'
        if adjusted_eq >= value_thresh:
            river_advice = (f'River: value bet {bet_size_pct:.0%} pot — you have '
                            f'{hero_equity:.0%} equity in a {n}-way pot.')
        else:
            river_advice = ('River: check-call or fold depending on sizing. '
                            f'Adjusted equity ({adjusted_eq:.0%}) is marginal multiway.')

    # ── Warnings ─────────────────────────────────────────────────────────
    warnings = []
    if n >= 4 and hero_equity > 0.55 and adjusted_eq < value_thresh:
        warnings.append(
            f'TPWK danger: {hero_equity:.0%} raw equity drops to {adjusted_eq:.0%} '
            f'in {n}-way pot — avoid committing stack.'
        )
    if n >= 3 and bluff_mult <= 0.60:
        warnings.append(
            f'Bluffing not recommended: fold equity reduced to ~{bluff_mult:.0%} '
            f'of HU rate with {n} players.'
        )
    if spr < 3 and adjusted_eq < commit_thresh:
        warnings.append(
            f'Low SPR ({spr:.1f}) but below commit threshold ({commit_thresh:.0%}) '
            f'— avoid getting stacked with marginal hands.'
        )
    if in_position is False and n >= 4:
        warnings.append(
            'OOP in multiway pot: drastically reduce betting frequency. '
            'Prefer check-call or check-raise with top of range only.'
        )

    # ── Confidence ────────────────────────────────────────────────────────
    confidence = 'high' if n <= 4 else 'medium' if n <= 6 else 'low'

    one_liner = (f'{n}-way | equity {hero_equity:.0%}→{adjusted_eq:.0%} adj | '
                 f'{primary_action} | '
                 f'value>={value_thresh:.0%} | bluff x{bluff_mult:.2f}')

    return MultiwayAdvice(
        num_players=n,
        hero_equity=hero_equity,
        adjusted_equity=adjusted_eq,
        equity_drop_pct=equity_drop,
        value_bet_threshold=value_thresh,
        commit_threshold=commit_thresh,
        bluff_frequency_mult=bluff_mult,
        primary_action=primary_action,
        bet_size_pct=bet_size_pct,
        pot_control=pot_control,
        flop_advice=flop_advice,
        turn_advice=turn_advice,
        river_advice=river_advice,
        warnings=warnings,
        one_liner=one_liner,
        confidence=confidence,
    )


def multiway_equity_table(hero_equity: float, max_players: int = 6) -> str:
    """
    Show how hero's equity drops as number of players increases.
    Returns a formatted ASCII table.
    """
    lines = ['Players | Raw Eq | Adj Eq | Value Thresh | Bluff Mult']
    lines.append('-' * 55)
    for n in range(2, max_players + 1):
        adj = hero_equity * _EQUITY_ADJ.get(n, 0.78)
        vt  = _VALUE_THRESHOLD.get(n, 0.76)
        bm  = _BLUFF_MULT.get(n, 0.10)
        lines.append(f'  {n}      | {hero_equity:.0%}   | {adj:.0%}   | {vt:.0%}         | x{bm:.2f}')
    return '\n'.join(lines)
