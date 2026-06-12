"""
Flop Thin Value Advisor (flop_thin_value.py)

"Thin value" on the flop = betting with hands in the 40-65% equity range
that are ahead of villain's calling range more often than not, but not
strongly enough to build the pot maximally.

Why thin value on the flop matters:
  - Not betting with TPTK or overpair on favorable flop = leaving value
  - Thin value bets get called by worse hands and fold out equity
  - But: betting too thin bloats the pot into unfavorable SPR

The key distinction from turn_value.py:
  - Flop: 2 more streets; villain has draws to improve; SPR changes more
  - Flop equity is "raw" (villain's draws are live)
  - Turn: draws partially resolved; equity is more realized
  - River: pure showdown equity

Flop thin value decision framework:
  1. Identify villain's calling range (based on VPIP, position)
  2. Estimate hero's equity vs calling range
  3. Calculate EV(bet) vs EV(check)
  4. Adjust for: board texture, position, villain WTSD, SPR

EV(bet b into pot P):
  ev_bet = P(fold) × P + P(call) × [P(win) × (P + 2b) - b - P(villain_draw_hits) × bleed]
  ≈ f × P + (1-f) × [eq × (P + 2b) - b]
  where f = fold frequency (depends on bet size)

Thin value threshold: ev_bet > ev_check
  ev_check ≈ equity × pot (simplified: hero goes to showdown without growth)

When NOT to thin value bet:
  1. Wet board: villain's draws are too live; they call with 30-40% equity draws
     then improve to beat you on turn/river (reverse implied odds)
  2. OOP + aggressive villain: they might raise your thin value bet
  3. Low SPR + weak kicker: if they raise, you're in a bad spot
  4. Multiway pot: thin value bets get called by multiple players; each caller
     has their own equity share

Typical thin value hands on flop:
  - Top pair with decent kicker (not TPTK): e.g., K5 on K72 board
  - Overpair that might be dominated: e.g., QQ on K87 board (could be behind KK/sets)
  - Two pair with straight/flush danger: 8♥7♠ on 8♣7♣2♦ (flopped two pair, wet)

Usage:
    from poker.flop_thin_value import advise_flop_thin_value, FlopThinValueAdvice
    from poker.flop_thin_value import flop_thin_value_one_liner

    result = advise_flop_thin_value(
        hero_hand_class='top_pair',
        board_type='dry',
        hero_pos='IP',
        hero_equity=0.60,
        spr=7.0,
        villain_vpip=0.30,
        villain_wtsd=0.28,
        villain_af=1.8,
        pot_bb=15.0,
        hero_stack_bb=100.0,
        n_opponents=1,
    )
    print(result.action, result.ev_bet, result.ev_check)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'trash': 0, 'bottom_pair': 2, 'marginal': 2,
        'middle_pair': 3, 'draw': 3, 'speculative': 2,
        'top_pair': 4, 'medium': 4, 'tptk': 5,
        'overpair': 6, 'two_pair': 6, 'strong': 7,
        'set': 9, 'straight': 8, 'flush': 8, 'premium': 9,
    }.get(hand_class.lower(), 4)


def _is_thin_value_range(hand_class: str, hero_equity: float) -> bool:
    """True when the hand is in thin value territory (not clear value, not fold)."""
    rank = _hand_rank(hand_class)
    # True thin value: moderate hand rank + moderate equity
    return 3 <= rank <= 6 or (0.40 <= hero_equity <= 0.68)


def _fold_frequency(bet_pct: float, villain_vpip: float, board_type: str) -> float:
    """
    Estimate fraction of villain's range that folds to a bet of bet_pct × pot.
    Base fold rate from GTO tables adjusted by villain VPIP and board type.
    """
    # GTO base fold rate by size (these are approximations for 6-max)
    gto_fold = {
        0.25: 0.55, 0.33: 0.50, 0.50: 0.43, 0.67: 0.37,
        0.75: 0.34, 1.00: 0.28,
    }
    # Interpolate
    sizes = sorted(gto_fold.keys())
    if bet_pct <= sizes[0]:
        base = gto_fold[sizes[0]]
    elif bet_pct >= sizes[-1]:
        base = gto_fold[sizes[-1]]
    else:
        for i in range(len(sizes) - 1):
            if sizes[i] <= bet_pct <= sizes[i + 1]:
                t = (bet_pct - sizes[i]) / (sizes[i + 1] - sizes[i])
                base = gto_fold[sizes[i]] * (1 - t) + gto_fold[sizes[i + 1]] * t
                break
        else:
            base = 0.40

    # Tight villains fold more
    if villain_vpip < 0.20:
        base += 0.08
    elif villain_vpip > 0.45:
        base -= 0.12
    elif villain_vpip > 0.35:
        base -= 0.06

    # Wet boards: villain calls with draws more
    if board_type == 'wet':
        base -= 0.08
    elif board_type == 'dry':
        base += 0.05

    return round(min(0.85, max(0.10, base)), 3)


def _implied_odds_bleed(
    board_type: str,
    hero_equity: float,
    spr: float,
) -> float:
    """
    How much equity leaks on future streets when villain calls with draws.
    Returns fraction of pot that villain's draws will "win" on average.
    (This is a simplified reverse implied odds estimate.)
    """
    if board_type == 'wet':
        # Many draws: villain will improve ~35% of the time from flop
        draw_improve_rate = 0.35
    elif board_type == 'medium':
        draw_improve_rate = 0.20
    else:
        draw_improve_rate = 0.08

    # When villain improves, they win extra value
    bleed_fraction = draw_improve_rate * 0.60  # 60% of the time their improvement wins
    return round(bleed_fraction, 3)


def _ev_bet(
    pot_bb: float,
    bet_pct: float,
    hero_equity: float,
    fold_freq: float,
    bleed: float,
) -> float:
    """
    EV of betting bet_pct × pot.
    EV = fold × pot + (1-fold) × [eq × (pot + 2×bet) - bet - bleed × bet]
    """
    bet = pot_bb * bet_pct
    total_pot_if_called = pot_bb + 2 * bet
    ev_when_called = hero_equity * total_pot_if_called - bet - bleed * bet
    ev = fold_freq * pot_bb + (1 - fold_freq) * ev_when_called
    return round(ev, 2)


def _ev_check(pot_bb: float, hero_equity: float) -> float:
    """Simplified EV of checking (no growth, goes to showdown at current equity)."""
    return round(hero_equity * pot_bb, 2)


def _optimal_bet_size(
    hero_equity: float,
    hero_hand_rank: int,
    board_type: str,
    villain_vpip: float,
    villain_wtsd: float,
    spr: float,
) -> float:
    """
    Find the bet size (as fraction of pot) that maximizes EV for thin value.
    Returns a value in [0.25, 0.75].
    """
    # High WTSD villain: bet larger (they call wide regardless)
    if villain_wtsd > 0.38:
        base = 0.60
    elif villain_wtsd > 0.32:
        base = 0.50
    else:
        base = 0.40

    # Wet board: size down (don't inflate pot vs draws)
    if board_type == 'wet':
        base -= 0.10

    # High equity: bet bigger
    if hero_equity >= 0.65:
        base += 0.10
    elif hero_equity < 0.50:
        base -= 0.05

    # Low SPR: smaller (don't overcommit thin)
    if spr < 3.0:
        base -= 0.10

    # Strong rank: slightly larger
    if hero_hand_rank >= 6:
        base += 0.05

    return round(min(0.70, max(0.25, base)), 2)


def _multiway_adjustment(n_opponents: int, base_bet_pct: float) -> tuple:
    """Returns (adjusted_bet_pct, multiway_penalty_pct) for n opponents."""
    if n_opponents <= 1:
        return base_bet_pct, 0.0
    # Each additional opponent requires ~5% more equity to thin value bet
    eq_penalty = (n_opponents - 1) * 0.05
    # Reduce bet size slightly in multiway (less fold equity per opponent)
    size_adj = max(0.25, base_bet_pct - 0.08 * (n_opponents - 1))
    return round(size_adj, 2), round(eq_penalty, 2)


@dataclass
class FlopThinValueAdvice:
    """Thin value betting advice for the flop."""
    hero_hand_class: str
    board_type: str
    hero_pos: str
    hero_equity: float
    spr: float
    villain_vpip: float
    villain_wtsd: float
    villain_af: float
    pot_bb: float
    hero_stack_bb: float
    n_opponents: int

    # Decision
    action: str             # 'bet', 'check'
    recommended_bet_pct: float
    recommended_bet_bb: float

    # EV breakdown
    ev_bet: float
    ev_check: float
    ev_advantage: float     # ev_bet - ev_check
    fold_freq: float

    # Context
    is_thin_value_spot: bool
    multiway_equity_penalty: float
    draw_bleed_pct: float   # reverse implied odds estimate

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_flop_thin_value(
    hero_hand_class: str = 'top_pair',
    board_type: str = 'dry',
    hero_pos: str = 'IP',
    hero_equity: float = 0.60,
    spr: float = 7.0,
    villain_vpip: float = 0.30,
    villain_wtsd: float = 0.28,
    villain_af: float = 1.8,
    pot_bb: float = 15.0,
    hero_stack_bb: float = 100.0,
    n_opponents: int = 1,
) -> FlopThinValueAdvice:
    """
    Advise on thin value betting on the flop (40-65% equity hands).

    Args:
        hero_hand_class:  Hero's hand strength
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' or 'OOP'
        hero_equity:      Hero's equity vs villain's entire range (raw flop equity)
        spr:              Stack-to-pot ratio
        villain_vpip:     Villain's VPIP (0-1)
        villain_wtsd:     Villain's WTSD (0-1)
        villain_af:       Villain's aggression factor
        pot_bb:           Pot size in BB
        hero_stack_bb:    Hero's effective stack in BB
        n_opponents:      Number of opponents

    Returns:
        FlopThinValueAdvice
    """
    rank = _hand_rank(hero_hand_class)
    is_thin = _is_thin_value_range(hero_hand_class, hero_equity)

    # Optimal bet size for this spot
    base_bet = _optimal_bet_size(hero_equity, rank, board_type, villain_vpip, villain_wtsd, spr)
    adj_bet, mw_penalty = _multiway_adjustment(n_opponents, base_bet)

    # OOP: slightly smaller (position disadvantage; risk of raise)
    if hero_pos == 'OOP':
        adj_bet = max(0.25, adj_bet - 0.05)
    # High AF villain: size down (risk of raise)
    if villain_af >= 3.0:
        adj_bet = max(0.25, adj_bet - 0.08)

    fold_freq = _fold_frequency(adj_bet, villain_vpip, board_type)
    bleed = _implied_odds_bleed(board_type, hero_equity, spr)

    # Adjust hero equity for multiway (each opponent has their own equity share)
    adj_equity = max(0.15, hero_equity - mw_penalty)

    ev_b = _ev_bet(pot_bb, adj_bet, adj_equity, fold_freq, bleed)
    ev_c = _ev_check(pot_bb, adj_equity)

    # Position-adjusted EV check: IP checks have more equity realization
    if hero_pos == 'IP':
        ev_c *= 1.05  # IP can improve check value with position
    elif hero_pos == 'OOP':
        ev_c *= 0.92  # OOP checking gives up value

    action = 'bet' if ev_b >= ev_c else 'check'

    # Reasoning
    ev_adv = round(ev_b - ev_c, 2)
    if action == 'bet':
        reason = (
            f'BET {adj_bet:.0%} pot: EV_bet={ev_b:.1f}BB > EV_check={ev_c:.1f}BB '
            f'(+{ev_adv:.1f}BB). '
            f'Fold_freq={fold_freq:.0%}, equity={adj_equity:.0%}, '
            f'draw_bleed={bleed:.0%}.'
        )
    else:
        reason = (
            f'CHECK: EV_check={ev_c:.1f}BB > EV_bet={ev_b:.1f}BB '
            f'(bet EV {ev_adv:.1f}BB). '
            f'Thin value not profitable: fold_freq={fold_freq:.0%} too low '
            f'or draw_bleed={bleed:.0%} too high.'
        )

    # Tips
    tips = []
    if board_type == 'wet' and action == 'check':
        tips.append(
            f'Wet board: draws are live and villain calls with 30-40% equity. '
            f'Checking back with {hero_hand_class} keeps pot manageable. '
            f'Bet SMALL ({max(0.25, adj_bet-0.10):.0%} pot) if you do bet — not standard size.'
        )
    if hero_pos == 'OOP' and villain_af >= 2.5:
        tips.append(
            f'OOP vs aggressive villain (AF={villain_af:.1f}): '
            f'thin value bet risks being raised. '
            f'Consider check-call line instead of bet-fold.'
        )
    if n_opponents >= 2:
        tips.append(
            f'{n_opponents} opponents: equity penalty -{mw_penalty:.0%}. '
            f'Thin value bet is less profitable in multiway pots. '
            f'Only bet if your hand is strong enough to be ahead of BOTH callers.'
        )
    if villain_wtsd > 0.38:
        tips.append(
            f'High WTSD villain ({villain_wtsd:.0%}): they call down with weak hands. '
            f'Thin value bet is more profitable vs calling stations. '
            f'Size up slightly ({min(0.70, adj_bet+0.10):.0%} pot) to extract more.'
        )
    if spr < 3.0 and action == 'bet':
        tips.append(
            f'Low SPR ({spr:.1f}): your bet may commit you to stacking off. '
            f'Ensure {hero_hand_class} is worth getting all-in for.'
        )
    if not tips:
        tips.append(
            f'{action.upper()} {hero_hand_class} on {board_type} flop ({hero_pos}). '
            f'EV_bet={ev_b:.1f}BB vs EV_check={ev_c:.1f}BB. '
            f'Thin value {"profitable" if action == "bet" else "not profitable"}: '
            f'equity={adj_equity:.0%}, fold={fold_freq:.0%}, bleed={bleed:.0%}.'
        )

    return FlopThinValueAdvice(
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        hero_pos=hero_pos,
        hero_equity=round(hero_equity, 3),
        spr=round(spr, 2),
        villain_vpip=round(villain_vpip, 3),
        villain_wtsd=round(villain_wtsd, 3),
        villain_af=round(villain_af, 2),
        pot_bb=round(pot_bb, 1),
        hero_stack_bb=round(hero_stack_bb, 1),
        n_opponents=n_opponents,
        action=action,
        recommended_bet_pct=adj_bet,
        recommended_bet_bb=round(pot_bb * adj_bet, 1),
        ev_bet=ev_b,
        ev_check=ev_c,
        ev_advantage=ev_adv,
        fold_freq=fold_freq,
        is_thin_value_spot=is_thin,
        multiway_equity_penalty=mw_penalty,
        draw_bleed_pct=bleed,
        reasoning=reason,
        tips=tips,
    )


def flop_thin_value_one_liner(result: FlopThinValueAdvice) -> str:
    return (
        f'[FTV {result.hero_hand_class}@flop|{result.hero_pos}] '
        f'{result.action.upper()} | '
        f'EV_bet={result.ev_bet:.1f} EV_chk={result.ev_check:.1f} (+{result.ev_advantage:.1f}BB) | '
        f'bet={result.recommended_bet_pct:.0%}pot eq={result.hero_equity:.0%}'
    )
