"""
River Bet Size Selector (river_bet_size_selector.py)

Selects the optimal river bet size from multiple options by modeling
villain's calling frequency at each size and computing EV.

KEY INSIGHT: Different bet sizes extract different EV:
  - Small bets (33-50%): call from wider range; more total calls but less per call
  - Large bets (75-100%): call from stronger range; fewer calls but more per call
  - Overbets (125-200%): only very strong calling range; max extraction vs nuts

CALLING FREQUENCY MODEL:
  Villain's call rate depends on:
  1. Their WTSD (base willingness to go to showdown)
  2. Bet size (larger = fewer calls)
  3. Board texture (wet boards = more draws = more calls vs any size)
  4. Villain VPIP (loose players call more regardless of size)
  5. Street (river callers are stronger than turn callers)

FORMULA PER SIZE:
  call_rate(size) = base_wtsd × size_discount × texture_factor
  ev(size) = call_rate × (size - avg_lose_when_called × (1-hero_eq))
           = call_rate × hero_eq × (pot + 2×size) - size
  Actually simplified: ev = call_rate × hero_eq × total_pot_if_called - size

OPTIMAL SIZE SELECTION:
  - Value betting: pick size with highest EV
  - Bluffing: pick size with highest EV given fold equity
  - Thin value with unclear equity: model both call and fold scenarios

DISTINCT FROM:
  river_value.py:       Models specific call curve for optimal size (simpler)
  ev_all_actions.py:    Compares all actions including check
  THIS MODULE:          Dedicated size selector for river bets; outputs
                        ranked EV comparison table for 5+ sizes; handles
                        both value and bluff contexts

Usage:
    from poker.river_bet_size_selector import select_river_size, RiverSizeSelection, rss_one_liner

    result = select_river_size(
        hero_equity=0.70,
        pot_bb=30.0,
        hero_stack_bb=100.0,
        villain_wtsd=0.32,
        villain_vpip=0.30,
        villain_af=2.0,
        board_texture='dry',
        hero_hand_type='value',
    )
    print(rss_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# Available sizes as fraction of pot
CANDIDATE_SIZES = [0.33, 0.50, 0.67, 1.00, 1.50, 2.00]
SIZE_LABELS = {0.33: '33%', 0.50: '50%', 0.67: '67%', 1.00: 'pot', 1.50: '150%', 2.00: '2x'}


def _base_call_rate(villain_wtsd: float, villain_vpip: float) -> float:
    """Base calling frequency before size/texture adjustments."""
    # WTSD is the primary indicator; VPIP adjusts slightly
    wtsd_component = villain_wtsd
    vpip_adj = (villain_vpip - 0.28) * 0.15   # loose players call ~15% more per 10% VPIP
    return round(min(0.80, max(0.15, wtsd_component + vpip_adj)), 3)


def _size_discount(size_pct: float) -> float:
    """Multiplicative discount on call rate for larger bet sizes."""
    # Larger bets fold out marginal hands
    discounts = {
        0.33: 1.20,   # small: 20% MORE calls (price is right)
        0.50: 1.00,   # baseline
        0.67: 0.85,
        1.00: 0.70,
        1.50: 0.52,
        2.00: 0.38,
    }
    return discounts.get(size_pct, 0.70)


def _texture_factor(board_texture: str) -> float:
    """How much board texture affects villain's call rate."""
    # Wet boards have more draws → more calls regardless of bet size
    factors = {
        'dry':       0.90,
        'semi_wet':  1.00,
        'wet':       1.12,
        'paired':    0.88,
        'monotone':  1.08,
    }
    return factors.get(board_texture, 1.00)


def _call_rate_at_size(
    size_pct: float,
    base_call: float,
    texture_factor: float,
    villain_af: float,
) -> float:
    """Final call rate for a specific bet size."""
    disc = _size_discount(size_pct)
    af_adj = 0.0
    if villain_af >= 3.0:
        af_adj = -0.05  # aggressive players fold more to polarized-looking overbets
    elif villain_af <= 1.0:
        af_adj = 0.06   # passive players call wider

    rate = base_call * disc * texture_factor + af_adj
    return round(max(0.05, min(0.90, rate)), 3)


def _ev_at_size(
    size_pct: float,
    pot_bb: float,
    call_rate: float,
    hero_equity: float,
    hero_hand_type: str,
) -> float:
    """
    EV of betting `size_pct * pot_bb` on the river.
    hero_equity is used for value betting; for bluffs, equity near 0.
    """
    bet_bb = size_pct * pot_bb
    total_pot_if_called = pot_bb + 2 * bet_bb

    if hero_hand_type == 'bluff':
        # Bluff: win only when villain folds
        fold_rate = 1 - call_rate
        ev = fold_rate * pot_bb - call_rate * bet_bb
    else:
        # Value: win (pot + bet) when villain calls and hero wins; lose bet when called and loses
        ev_when_called = hero_equity * total_pot_if_called - bet_bb
        ev_when_fold = pot_bb - bet_bb   # negative (villain folds; we win less than full pot)
        # Actually: when fold, hero wins pot but paid bet = net = pot_bb - bet_bb...
        # Wait. When villain FOLDS, hero wins the pot (pot_bb) and doesn't need bet_bb back:
        # Hero invested bet_bb; gets pot_bb + bet_bb back = nets +pot_bb.
        # When villain CALLS: hero invested bet_bb; pot = total_pot; nets equity * total - bet_bb
        ev_when_fold = pot_bb  # net gain when fold: villain folds, hero gets pot
        ev = call_rate * ev_when_called + (1 - call_rate) * ev_when_fold

    return round(ev, 3)


def _rank_sizes(evs: Dict[float, float]) -> List[Tuple[float, float]]:
    """Sort sizes by EV descending."""
    return sorted(evs.items(), key=lambda x: -x[1])


@dataclass
class SizeOption:
    size_pct: float
    size_bb: float
    label: str
    call_rate: float
    ev_bb: float
    rank: int


@dataclass
class RiverSizeSelection:
    # Inputs
    hero_equity: float
    pot_bb: float
    hero_stack_bb: float
    villain_wtsd: float
    villain_vpip: float
    villain_af: float
    board_texture: str
    hero_hand_type: str   # 'value' / 'bluff' / 'thin_value'

    # Results
    optimal_size_pct: float
    optimal_size_bb: float
    optimal_size_label: str
    optimal_ev_bb: float

    # All options ranked
    size_options: List[SizeOption]

    # Context
    base_call_rate: float
    ev_check: float          # EV of checking (rough estimate)

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def select_river_size(
    hero_equity: float = 0.70,
    pot_bb: float = 30.0,
    hero_stack_bb: float = 100.0,
    villain_wtsd: float = 0.32,
    villain_vpip: float = 0.30,
    villain_af: float = 2.0,
    board_texture: str = 'dry',
    hero_hand_type: str = 'value',
) -> RiverSizeSelection:
    """
    Select the optimal river bet size from multiple candidates.

    Args:
        hero_equity:    Hero's equity vs villain's calling range (0-1)
        pot_bb:         Pot size in BBs before hero bets
        hero_stack_bb:  Effective stack in BBs
        villain_wtsd:   Villain's WTSD stat
        villain_vpip:   Villain's VPIP
        villain_af:     Villain's aggression factor
        board_texture:  'dry' / 'semi_wet' / 'wet' / 'paired' / 'monotone'
        hero_hand_type: 'value' / 'bluff' / 'thin_value'

    Returns:
        RiverSizeSelection
    """
    base_call = _base_call_rate(villain_wtsd, villain_vpip)
    tex_factor = _texture_factor(board_texture)

    # Evaluate each size
    evs = {}
    call_rates = {}
    for size in CANDIDATE_SIZES:
        # Skip sizes that exceed hero's stack
        max_bet = min(size, hero_stack_bb / pot_bb)
        actual_size = min(size, max_bet)
        cr = _call_rate_at_size(actual_size, base_call, tex_factor, villain_af)
        ev = _ev_at_size(actual_size, pot_bb, cr, hero_equity, hero_hand_type)
        evs[size] = ev
        call_rates[size] = cr

    # Thin value: use lower equity estimate
    if hero_hand_type == 'thin_value':
        adj_equity = hero_equity * 0.75   # discount equity (villain calls better range)
        for size in CANDIDATE_SIZES:
            cr = call_rates[size]
            ev = _ev_at_size(size, pot_bb, cr, adj_equity, 'value')
            evs[size] = ev

    ranked = _rank_sizes(evs)
    optimal_size, optimal_ev = ranked[0]
    optimal_bb = round(optimal_size * pot_bb, 1)

    # EV of checking (rough: hero keeps pot if wins; equity × pot)
    ev_check = round(hero_equity * pot_bb, 1) if hero_hand_type in ('value', 'thin_value') else 0.0

    # Build size options list
    size_options = []
    for rank, (size, ev) in enumerate(ranked, 1):
        size_options.append(SizeOption(
            size_pct=size,
            size_bb=round(size * pot_bb, 1),
            label=SIZE_LABELS.get(size, f'{size:.0%}'),
            call_rate=call_rates[size],
            ev_bb=ev,
            rank=rank,
        ))

    label = SIZE_LABELS.get(optimal_size, f'{optimal_size:.0%}')

    reasoning = (
        f'River bet size optimization for {hero_hand_type} hand. '
        f'Pot={pot_bb:.0f}BB, villain WTSD={villain_wtsd:.0%}, VPIP={villain_vpip:.0%}, AF={villain_af:.1f}. '
        f'Board={board_texture}. Base call rate={base_call:.0%}. '
        f'Optimal: {label} ({optimal_bb:.1f}BB), EV={optimal_ev:+.1f}BB. '
        f'Check EV={ev_check:+.1f}BB. Betting gains {optimal_ev - ev_check:+.1f}BB vs checking.'
    )

    verdict = (
        f'[RSS {hero_hand_type.upper()}|{board_texture}] '
        f'{label} ({optimal_bb:.1f}BB) EV={optimal_ev:+.1f}BB | '
        f'call_rate={call_rates[optimal_size]:.0%} | '
        f'vs_check={optimal_ev - ev_check:+.1f}BB'
    )

    tips = []
    tips.append(
        f'OPTIMAL SIZE: {label} ({optimal_bb:.1f}BB). '
        f'EV={optimal_ev:+.1f}BB at {call_rates[optimal_size]:.0%} call rate. '
        f'2nd best: {SIZE_LABELS.get(ranked[1][0], "")} ({ranked[1][1]:+.1f}BB).'
    )

    # Gain vs check
    gain_vs_check = round(optimal_ev - ev_check, 1)
    if gain_vs_check > 1.0:
        tips.append(
            f'BETTING ADDS VALUE: {label} adds {gain_vs_check:+.1f}BB vs checking. '
            f'Do not miss this bet -- villain calls {call_rates[optimal_size]:.0%} of the time.'
        )
    elif gain_vs_check <= 0 and hero_hand_type == 'value':
        tips.append(
            f'CONSIDER CHECKING: Bet EV only {gain_vs_check:+.1f}BB vs check. '
            f'Villain calls too rarely or hero equity is low; check-call may be better.'
        )

    if hero_hand_type == 'bluff' and villain_wtsd >= 0.35:
        tips.append(
            f'WARNING CALLING STATION: Villain WTSD={villain_wtsd:.0%}. '
            f'All bet sizes have low fold equity vs this player. '
            f'Reduce bluffing frequency; only bluff with strong blockers.'
        )

    if optimal_size >= 1.50:
        tips.append(
            f'OVERBET SELECTED: {label} is the optimal size. '
            f'This signals a very polarized range to villain. '
            f'Only use if you have the nuts or a pure bluff -- never overbet medium-strength hands.'
        )

    if board_texture == 'dry' and hero_hand_type == 'value':
        tips.append(
            f'DRY BOARD VALUE: On dry boards, smaller sizes extract more total EV -- '
            f'villain has no draws to call with; they call for showdown value. '
            f'{label} balances between fold pressure and call frequency.'
        )

    return RiverSizeSelection(
        hero_equity=hero_equity,
        pot_bb=pot_bb,
        hero_stack_bb=hero_stack_bb,
        villain_wtsd=villain_wtsd,
        villain_vpip=villain_vpip,
        villain_af=villain_af,
        board_texture=board_texture,
        hero_hand_type=hero_hand_type,
        optimal_size_pct=optimal_size,
        optimal_size_bb=optimal_bb,
        optimal_size_label=label,
        optimal_ev_bb=optimal_ev,
        size_options=size_options,
        base_call_rate=base_call,
        ev_check=ev_check,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rss_one_liner(r: RiverSizeSelection) -> str:
    gain = round(r.optimal_ev_bb - r.ev_check, 1)
    return (
        f'[RSS {r.hero_hand_type.upper()}|{r.board_texture}] '
        f'{r.optimal_size_label} ({r.optimal_size_bb:.1f}BB) EV={r.optimal_ev_bb:+.1f}BB | '
        f'call={r.base_call_rate:.0%} gain_vs_check={gain:+.1f}BB'
    )
