"""
Float / Probe Bet Advisor (probe_advisor.py)

Analyzes when to probe (lead into the preflop aggressor) or fire a turn barrel
after the villain checks back or checks to hero. Combines villain pattern data
with equity to give concrete bet/check recommendations.

Usage:
    from poker.probe_advisor import analyze_probe, ProbeAdvice
    result = analyze_probe(
        hero_equity=0.52,
        pot_bb=12.0,
        eff_stack_bb=75.0,
        villain_turn_check_freq=0.65,  # from VillainPatternTracker
        villain_fold_to_probe=0.55,
        board_wetness=0.30,
        street='turn',
        in_position=True,
    )
    print(result.action, result.bet_size_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProbeAdvice:
    """Float/probe bet analysis."""
    street: str
    hero_equity: float
    pot_bb: float

    # Villain pattern data
    villain_check_freq: float      # how often villain checks this street
    villain_fold_to_probe: float   # how often villain folds to a probe

    # Bet sizing
    bet_size_bb: float             # recommended bet size
    bet_size_pct: float            # as fraction of pot

    # EV components
    ev_bet: float                  # EV of probing
    ev_check: float                # EV of checking back

    # Decision
    action: str                    # 'bet', 'check'
    probe_type: str                # 'value', 'semi-bluff', 'pure-bluff', 'none'
    fold_equity_gained: float      # EV gained purely from fold equity

    # Reasoning
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_probe(
    hero_equity: float,
    pot_bb: float,
    eff_stack_bb: float,
    villain_turn_check_freq: float = 0.50,
    villain_fold_to_probe: float = 0.50,
    board_wetness: float = 0.40,
    street: str = 'turn',
    in_position: bool = True,
    hero_has_draw: bool = False,
    villain_cbet_flop_freq: float = 0.60,
) -> ProbeAdvice:
    """
    Analyze whether to probe (bet) or check when villain checks to hero
    or hero is deciding whether to lead into the aggressor.

    Args:
        hero_equity:             Hero's equity vs villain's perceived range (0-1)
        pot_bb:                  Current pot size in BBs
        eff_stack_bb:            Effective stack in BBs
        villain_turn_check_freq: How often villain gives up on this street (0-1)
        villain_fold_to_probe:   How often villain folds to a bet here (0-1)
        board_wetness:           Board texture (0=dry, 1=wet)
        street:                  'flop', 'turn', 'river'
        in_position:             Hero acts after villain
        hero_has_draw:           True if hero has a draw
        villain_cbet_flop_freq:  Villain's flop cbet freq (context for turns)

    Returns:
        ProbeAdvice
    """
    spr = eff_stack_bb / pot_bb if pot_bb > 0 else 99

    # ── Bet sizing ────────────────────────────────────────────────────────
    # Turn/River probes: typically 55-70% pot; River value: larger
    if street == 'flop':
        base_pct = 0.45 + board_wetness * 0.20
    elif street == 'turn':
        base_pct = 0.55 + board_wetness * 0.15
    else:  # river
        base_pct = 0.65 + board_wetness * 0.10

    # Adjust for draw: protect with larger sizes
    if hero_has_draw and board_wetness > 0.5:
        base_pct += 0.10

    base_pct = min(1.0, max(0.30, base_pct))
    bet_size = pot_bb * base_pct
    bet_size = min(bet_size, eff_stack_bb * 0.60)

    # ── EV calculations ────────────────────────────────────────────────────
    total_pot_if_bet = pot_bb + bet_size

    # EV of betting:
    #   P(fold) * win_pot + P(call) * (equity * new_pot - (1-equity) * bet)
    ev_if_fold = pot_bb   # win current pot
    ev_if_call = hero_equity * total_pot_if_bet - (1 - hero_equity) * bet_size

    ev_bet = (villain_fold_to_probe * ev_if_fold
              + (1 - villain_fold_to_probe) * ev_if_call)

    # EV of checking back: equity * pot (no bet, just showdown or future streets)
    ev_check = hero_equity * pot_bb

    # EV gain purely from fold equity (what probe adds vs check)
    fold_eq_gained = villain_fold_to_probe * pot_bb * (1 - hero_equity)

    # ── Probe type classification ─────────────────────────────────────────
    # Value probe: strong equity, get called by worse
    value_threshold = 0.60
    # Semi-bluff probe: has equity + fold equity
    semi_threshold = 0.40

    if hero_equity >= value_threshold:
        probe_type = 'value'
    elif hero_equity >= semi_threshold and (hero_has_draw or villain_fold_to_probe > 0.50):
        probe_type = 'semi-bluff'
    elif villain_fold_to_probe > 0.60 and hero_equity < semi_threshold:
        probe_type = 'pure-bluff'
    else:
        probe_type = 'none'

    # ── Decision ─────────────────────────────────────────────────────────
    should_probe = (
        ev_bet > ev_check
        and probe_type != 'none'
        and (villain_turn_check_freq >= 0.45 or probe_type == 'value')
    )

    # Always bet value; probe bluff only when villain gives up often
    if probe_type == 'value':
        action = 'bet'
    elif probe_type in ('semi-bluff', 'pure-bluff') and villain_fold_to_probe > 0.48:
        action = 'bet' if ev_bet > ev_check else 'check'
    else:
        action = 'check'

    # ── Tips ──────────────────────────────────────────────────────────────
    tips = []
    if villain_turn_check_freq > 0.65:
        tips.append(f'Villain gives up on {street} {villain_turn_check_freq:.0%} '
                    f'of the time — their range is capped. Probe wide.')
    if villain_cbet_flop_freq > 0.70 and street == 'turn' and villain_turn_check_freq > 0.50:
        tips.append('High flop cbet + low turn follow-through — villain bluffs flop '
                    'and gives up turns. Attack mercilessly.')
    if probe_type == 'pure-bluff' and not in_position:
        tips.append('OOP pure bluff probe: risky — only attempt if villain has '
                    'demonstrated passivity on this street.')
    if board_wetness > 0.65 and probe_type == 'value':
        tips.append('Wet board: use larger bet size to charge draws and protect hand.')
    if spr < 3 and hero_equity > 0.55:
        tips.append('Low SPR: consider shoving instead of a standard probe.')
    if not tips:
        tips.append('Standard probe: use recommended bet size and proceed with GTO.')

    reasoning = (
        f'{street.capitalize()} probe: equity={hero_equity:.0%} '
        f'villain_check={villain_turn_check_freq:.0%} '
        f'fold_to_probe={villain_fold_to_probe:.0%}. '
        f'Bet {bet_size:.1f}BB ({base_pct:.0%} pot). '
        f'EV(bet)={ev_bet:+.2f} vs EV(check)={ev_check:+.2f}. '
        f'Type: {probe_type}. Action: {action.upper()}.'
    )

    return ProbeAdvice(
        street=street,
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        villain_check_freq=villain_turn_check_freq,
        villain_fold_to_probe=villain_fold_to_probe,
        bet_size_bb=round(bet_size, 1),
        bet_size_pct=round(base_pct, 2),
        ev_bet=round(ev_bet, 2),
        ev_check=round(ev_check, 2),
        action=action,
        probe_type=probe_type,
        fold_equity_gained=round(fold_eq_gained, 2),
        reasoning=reasoning,
        tips=tips,
    )


def probe_one_liner(result: ProbeAdvice) -> str:
    """Single-line overlay summary."""
    return (f'{result.street.capitalize()} probe [{result.probe_type}]: '
            f'{result.action.upper()} {result.bet_size_bb:.1f}BB | '
            f'EV={result.ev_bet:+.2f} vs check={result.ev_check:+.2f}')
