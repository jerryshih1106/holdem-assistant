"""
Turn Probe Bet Advisor (turn_probe_bet_advisor.py)

Advises OOP hero on whether and how to probe-bet the turn after BOTH
players checked the flop. When the pre-flop aggressor checks back the
flop, their range is capped and hero can exploit this with a probe bet.

KEY INSIGHT: When villain checks back the flop IP, their range is:
  - Mostly medium-strength hands (pairs, weak top pairs)
  - Draws (keeping pot small)
  - NOT strong value (they would have c-bet sets/two-pair)
  This creates a profitable probe window on the turn.

PROBE BET FREQUENCY (based on villain flop check-back rate):
  flop_check_back >= 50%: villain has very capped range → probe 60-70% of range
  flop_check_back 35-49%: probe ~45-55%
  flop_check_back 20-34%: probe ~30-40%
  flop_check_back < 20%: villain rarely checks back; range still strong → probe sparingly

HAND CATEGORIES FOR PROBING:
  Top pair+: probe for value (2/3 pot)
  Middle pair: probe small (1/3 pot) on dry boards; check wet boards
  Draws:       probe as semi-bluff on wet boards; check dry boards
  Air:         probe only on very dry boards with high fold equity; else check

SIZING:
  Dry board:   33-40% pot (range bet; no draws to charge)
  Wet board:   50-67% pot (need to charge draws/equity; bigger vs merged range)

DISTINCT FROM:
  donk_bet.py:               General donk/probe; not specific to check-check flop spot
  oop_turn_advisor.py:       Broader OOP turn strategy including vs c-bets
  THIS MODULE:               Specific to the "check-check flop → probe turn" spot;
                             calibrates frequency and sizing vs villain's check-back range

Usage:
    from poker.turn_probe_bet_advisor import advise_turn_probe, TurnProbeAdvice, tpa_one_liner

    result = advise_turn_probe(
        hero_hand_category='top_pair',
        board_texture='dry',
        villain_flop_check_back_pct=0.45,
        villain_af=1.8,
        villain_wtsd=0.32,
        pot_bb=12.0,
        hero_stack_bb=80.0,
        hero_position='oop',
        turn_card_changed_board=False,
    )
    print(tpa_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# Hand categories that benefit from probing
PROBE_FRIENDLY = {'top_pair', 'two_pair', 'set', 'overpair', 'draw', 'flush_draw', 'straight_draw'}
# Categories to rarely probe with
PROBE_UNFRIENDLY = {'air', 'missed_draw', 'weak_pair'}


def _villain_range_after_check(flop_check_back_pct: float, villain_af: float) -> str:
    """
    Characterize villain's range after checking back the flop.
    Higher check-back = more capped range = more profitable probe.
    """
    if flop_check_back_pct >= 0.50:
        return 'very_capped'    # pairs, weak draws; almost never nuts
    elif flop_check_back_pct >= 0.35:
        return 'capped'         # some strong hands missed c-bet; mostly medium
    elif flop_check_back_pct >= 0.20:
        return 'semi_capped'    # could have missed strong hand; harder to exploit
    else:
        return 'uncapped'       # villain check-backs are unusual; could be trapping


def _probe_frequency(
    villain_range: str,
    board_texture: str,
    hero_hand_category: str,
    turn_card_changed_board: bool,
) -> float:
    """
    Base probe frequency for hero's hand on this turn.
    Returns 0-1 (probability of probing).
    """
    base = {
        'very_capped':  0.62,
        'capped':       0.48,
        'semi_capped':  0.35,
        'uncapped':     0.20,
    }.get(villain_range, 0.40)

    # Hand category adjustment
    if hero_hand_category in ('top_pair', 'overpair', 'two_pair', 'set'):
        base += 0.15   # strong hands: probe for value
    elif hero_hand_category in ('flush_draw', 'straight_draw', 'draw'):
        base += 0.08 if board_texture == 'wet' else -0.05  # semi-bluff on wet boards
    elif hero_hand_category == 'middle_pair':
        base -= 0.05
    elif hero_hand_category in ('air', 'missed_draw', 'weak_pair'):
        base -= 0.20   # rarely probe; only when fold equity is very high

    # Board texture: wet boards discourage probing with air (villain may float)
    if board_texture == 'wet' and hero_hand_category in PROBE_UNFRIENDLY:
        base -= 0.10
    elif board_texture == 'dry' and hero_hand_category in PROBE_UNFRIENDLY:
        base += 0.05   # dry boards = more fold equity

    # Turn card that improves board: hero may improve or villain's draws hit
    if turn_card_changed_board:
        base -= 0.08   # harder to read; probe less with air; still probe value

    return round(max(0.0, min(0.95, base)), 3)


def _probe_size_pct(board_texture: str, hero_hand_category: str, villain_range: str) -> float:
    """
    Optimal probe bet size as fraction of pot.
    """
    if board_texture == 'dry':
        # Dry: small range bet; no draws to charge
        if hero_hand_category in ('top_pair', 'overpair', 'two_pair', 'set'):
            return 0.40   # build pot but don't over-bet dry board
        else:
            return 0.33   # range bet small
    else:
        # Wet: need to charge draws; size up
        if hero_hand_category in ('top_pair', 'overpair', 'two_pair', 'set'):
            return 0.67   # charge draws
        elif hero_hand_category in ('flush_draw', 'straight_draw', 'draw'):
            return 0.50   # semi-bluff at medium sizing
        else:
            return 0.40   # probing with medium hands on wet board

    return 0.40


def _should_probe(freq: float, hero_hand_category: str, villain_range: str) -> bool:
    """Decide YES/NO based on frequency threshold and hand quality."""
    if villain_range == 'uncapped' and hero_hand_category in PROBE_UNFRIENDLY:
        return False
    return freq >= 0.35   # probe if frequency threshold met


def _action_decision(freq: float, hero_hand_category: str, villain_range: str,
                     board_texture: str) -> str:
    if not _should_probe(freq, hero_hand_category, villain_range):
        return 'check'
    if hero_hand_category in ('top_pair', 'overpair', 'two_pair', 'set'):
        return 'probe_value'
    elif hero_hand_category in ('flush_draw', 'straight_draw', 'draw'):
        return 'probe_semi_bluff'
    elif hero_hand_category == 'middle_pair':
        return 'probe_thin' if board_texture == 'dry' else 'check'
    else:
        return 'probe_bluff' if freq >= 0.40 else 'check'


@dataclass
class TurnProbeAdvice:
    # Inputs
    hero_hand_category: str
    board_texture: str
    villain_flop_check_back_pct: float
    villain_af: float
    villain_wtsd: float
    pot_bb: float
    hero_stack_bb: float

    # Analysis
    villain_range_type: str     # 'very_capped' / 'capped' / 'semi_capped' / 'uncapped'
    probe_frequency: float      # 0-1 probability hero should probe
    probe_size_pct: float       # optimal bet size as fraction of pot
    probe_size_bb: float        # bet size in BB

    # Fold equity
    fold_equity_estimate: float  # estimated % of villain's range that folds to probe
    probe_ev_estimate: float     # rough EV of probe vs check (in BB)

    # Decision
    action: str                  # 'probe_value' / 'probe_semi_bluff' / 'probe_thin' / 'probe_bluff' / 'check'
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_turn_probe(
    hero_hand_category: str = 'top_pair',
    board_texture: str = 'dry',
    villain_flop_check_back_pct: float = 0.40,
    villain_af: float = 2.0,
    villain_wtsd: float = 0.30,
    pot_bb: float = 10.0,
    hero_stack_bb: float = 100.0,
    hero_position: str = 'oop',
    turn_card_changed_board: bool = False,
) -> TurnProbeAdvice:
    """
    Advise OOP hero on whether to probe-bet the turn after check-check flop.

    Args:
        hero_hand_category: 'top_pair' / 'middle_pair' / 'draw' / 'flush_draw' /
                            'straight_draw' / 'overpair' / 'two_pair' / 'set' /
                            'air' / 'missed_draw' / 'weak_pair'
        board_texture:      'dry' / 'wet' / 'semi_wet'
        villain_flop_check_back_pct: How often villain checks back flop IP (0-1)
        villain_af:         Villain's aggression factor
        villain_wtsd:       Villain's WTSD
        pot_bb:             Current pot size in BBs (after check-check flop)
        hero_stack_bb:      Hero's effective stack in BBs
        hero_position:      Should be 'oop' for this module's use case
        turn_card_changed_board: Whether the turn card significantly changed board texture

    Returns:
        TurnProbeAdvice
    """
    villain_range = _villain_range_after_check(villain_flop_check_back_pct, villain_af)
    freq = _probe_frequency(villain_range, board_texture, hero_hand_category, turn_card_changed_board)
    size_pct = _probe_size_pct(board_texture, hero_hand_category, villain_range)
    probe_bb = round(size_pct * pot_bb, 1)
    action = _action_decision(freq, hero_hand_category, villain_range, board_texture)

    # Fold equity: villain's capped range folds more to bets
    fold_eq_base = {
        'very_capped': 0.55,
        'capped':      0.42,
        'semi_capped': 0.32,
        'uncapped':    0.20,
    }.get(villain_range, 0.35)
    # Villain AF adjustment: aggressive villain counter-attacks vs probes
    if villain_af >= 3.0:
        fold_eq_base -= 0.10
    elif villain_af <= 1.2:
        fold_eq_base -= 0.05  # passive villain calls more
    fold_eq = round(max(0.05, min(0.80, fold_eq_base)), 3)

    # Very rough EV estimate (probe EV vs checking = 0)
    # ev = fold_eq * pot + (1-fold_eq) * -probe_bb * 0.3  (simplified)
    if action == 'check':
        probe_ev = 0.0
    else:
        win_when_fold = fold_eq * pot_bb
        lose_when_call = (1 - fold_eq) * probe_bb * 0.35
        probe_ev = round(win_when_fold - lose_when_call, 2)

    action_explanations = {
        'probe_value':     f'Probe {probe_bb:.1f}BB ({size_pct:.0%} pot) for value: villain range is {villain_range}; get thin value from pairs and draws.',
        'probe_semi_bluff': f'Probe {probe_bb:.1f}BB ({size_pct:.0%} pot) as semi-bluff: have equity + {fold_eq:.0%} fold equity.',
        'probe_thin':      f'Probe {probe_bb:.1f}BB ({size_pct:.0%} pot) for thin value on dry board: villain capped, folds {fold_eq:.0%}.',
        'probe_bluff':     f'Probe {probe_bb:.1f}BB ({size_pct:.0%} pot) as bluff: villain range is {villain_range} with {fold_eq:.0%} fold equity.',
        'check':           f'Check: insufficient fold equity ({fold_eq:.0%}) or villain range too strong to probe.',
    }
    action_exp = action_explanations.get(action, f'Action: {action}')

    reasoning = (
        f'Villain checked flop back {villain_flop_check_back_pct:.0%} → range={villain_range}. '
        f'Board={board_texture}. Hero={hero_hand_category}. '
        f'Turn changed={turn_card_changed_board}. '
        f'Probe freq={freq:.0%}, size={size_pct:.0%} pot={probe_bb:.1f}BB. '
        f'Fold_eq={fold_eq:.0%}. EV_probe={probe_ev:+.1f}BB. '
        f'Villain AF={villain_af} WTSD={villain_wtsd:.0%}. Action={action}.'
    )

    verdict = (
        f'[TPA {hero_hand_category.upper()}|{board_texture}|{villain_range}] '
        f'{action.upper()} | '
        f'freq={freq:.0%} size={size_pct:.0%}pot={probe_bb:.1f}BB | '
        f'fold_eq={fold_eq:.0%} ev={probe_ev:+.1f}BB'
    )

    tips = [action_exp]

    if villain_range == 'very_capped':
        tips.append(
            f'HIGHLY CAPPED RANGE: Villain checks back {villain_flop_check_back_pct:.0%} of flops IP — '
            f'they almost never have the nuts here. Probe your entire value range and '
            f'add bluffs up to {freq:.0%} frequency. Do not slow-play strong hands.'
        )
    elif villain_range == 'uncapped':
        tips.append(
            f'WARNING: Villain checks back only {villain_flop_check_back_pct:.0%} flops — '
            f'their range is NOT capped. They may be slow-playing or have a monster. '
            f'Check back turns with marginal hands; bet only strong value.'
        )

    if turn_card_changed_board:
        tips.append(
            f'TURN CARD ALERT: Board changed on turn. Re-evaluate ranges — '
            f'draws may have completed; villain may have connected or missed. '
            f'Probe with value hands more carefully on scare cards.'
        )

    if action == 'check' and hero_hand_category in PROBE_FRIENDLY:
        tips.append(
            f'CHECKING STRONG HAND: With {hero_hand_category}, checking is defensive — '
            f'villain range too uncapped or hand category not suited for probing on this texture. '
            f'Consider check-calling or check-raising if villain bets.'
        )

    if villain_af >= 3.0:
        tips.append(
            f'HIGH AF VILLAIN (AF={villain_af:.1f}): Aggressive villain may raise probe bets. '
            f'Have a plan for check-raises. Only probe with hands that can call a raise.'
        )

    return TurnProbeAdvice(
        hero_hand_category=hero_hand_category,
        board_texture=board_texture,
        villain_flop_check_back_pct=villain_flop_check_back_pct,
        villain_af=villain_af,
        villain_wtsd=villain_wtsd,
        pot_bb=pot_bb,
        hero_stack_bb=hero_stack_bb,
        villain_range_type=villain_range,
        probe_frequency=freq,
        probe_size_pct=size_pct,
        probe_size_bb=probe_bb,
        fold_equity_estimate=fold_eq,
        probe_ev_estimate=probe_ev,
        action=action,
        action_explanation=action_exp,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tpa_one_liner(r: TurnProbeAdvice) -> str:
    return (
        f'[TPA {r.hero_hand_category.upper()}|{r.board_texture}|{r.villain_range_type}] '
        f'{r.action.upper()} | '
        f'freq={r.probe_frequency:.0%} size={r.probe_size_pct:.0%}pot={r.probe_size_bb:.1f}BB | '
        f'fold_eq={r.fold_equity_estimate:.0%} ev={r.probe_ev_estimate:+.1f}BB'
    )
