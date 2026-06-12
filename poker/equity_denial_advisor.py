"""
Equity Denial Advisor (equity_denial_advisor.py)

Computes the mathematically precise bet size needed to make villain's
specific draws unprofitable to call, accounting for:
  - All draws present on the board (flush, straight, overcards, combo draws)
  - Villain's implied odds (future streets remaining)
  - Hero's stack-off risk if villain hits
  - Optimal balance between denial and value extraction

Core math:
  For a draw with N outs and R cards remaining:
    P(hit) = N/R (simplified one-card)
    Break-even call: bet/(pot + bet) = P(hit)
    → Denial bet = P(hit) * pot / (1 - P(hit))
    → Denial bet = N * pot / (R - N)

  With implied odds (villain still profits even with -EV call):
    Implied-adjusted breakeven: slightly larger bet
    Approx: denial_bet *= (1 + implied_factor)

  But: betting too large over-commits hero to a bad SPR; calibrate.

Usage:
    from poker.equity_denial_advisor import analyze_equity_denial, DenialResult
    result = analyze_equity_denial(
        pot_bb=10.0,
        eff_stack_bb=90.0,
        community=['Ah', '7h', '2s'],  # flush draw board
        hero_hand_class='top_pair',
        hero_equity=0.72,
        street='flop',
        villain_vpip=0.30,
    )
    print(result.denial_bet_bb, result.reasoning)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# Draw type: (name, outs, implied_factor, scare_factor)
# implied_factor: how much implied odds inflate villain's true EV (0=none, 1=strong)
# scare_factor: how much the draw scares hero if it completes (0=ok, 1=bad)
_DRAW_TYPES = [
    ('flush_draw',     9, 0.30, 0.85),
    ('oesd',           8, 0.25, 0.80),
    ('combo_draw',    15, 0.35, 0.95),  # flush draw + OESD
    ('gutshot',        4, 0.10, 0.40),  # 4 outs only — less threatening
    ('overcards',      6, 0.15, 0.40),
    ('backdoor_flush', 3, 0.05, 0.20),
    ('backdoor_oesd',  2, 0.05, 0.15),
]

_DRAW_MAP = {d[0]: d for d in _DRAW_TYPES}


def _cards_remaining(street: str) -> int:
    """Cards remaining to be dealt."""
    return {'flop': 2, 'turn': 1, 'river': 0}.get(street, 1)


def _one_card_outs_pct(outs: int, remaining: int = 1) -> float:
    if remaining <= 0 or outs <= 0:
        return 0.0
    return outs / 46.0  # approx deck size after hole+community


def _two_card_outs_pct(outs: int) -> float:
    """Rule-of-4 approximation for two remaining cards."""
    return min(0.95, outs * 4 / 100)


def _denial_bet(outs: int, pot_bb: float, remaining_cards: int,
                implied_factor: float, eff_stack_bb: float) -> float:
    """
    Compute the bet size needed to make villain's call –EV,
    adjusted for implied odds.
    """
    if remaining_cards <= 0 or outs <= 0:
        return 0.0

    # Use one-card approximation (most conservative for turn; two-card for flop)
    if remaining_cards >= 2:
        p_hit = _two_card_outs_pct(outs)
    else:
        p_hit = _one_card_outs_pct(outs)

    # Base denial bet: p_hit * pot / (1 - p_hit)
    if p_hit >= 1.0:
        return eff_stack_bb
    base = p_hit * pot_bb / (1.0 - p_hit)

    # Implied odds adjustment: villain calls with implied odds, so we need to bet more
    # Implied odds add value to villain's call proportional to implied_factor and stack depth
    stack_ratio = min(1.0, eff_stack_bb / (pot_bb * 5))  # deeper = more implied odds
    implied_adj = base * implied_factor * stack_ratio * 0.5
    adjusted = base + implied_adj

    return min(adjusted, eff_stack_bb)


def _detect_draws(community: List[str]) -> List[str]:
    """
    Detect draw types present on the board based on community cards.
    Returns list of draw type keys.
    """
    if not community:
        return []

    draws = []

    # Count suits
    suits = [c[-1].lower() for c in community if len(c) >= 2]
    suit_counts = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1

    # Flush draw: 2+ of same suit on flop, 3+ means flush possible
    max_suit = max(suit_counts.values()) if suit_counts else 0
    if max_suit >= 3:
        draws.append('flush_draw')  # completed flush, still an issue vs hero non-flush
    elif max_suit == 2 and len(community) <= 4:
        draws.append('flush_draw')

    # Straight draw detection: look for connected ranks
    ranks = []
    for c in community:
        r = c[0].upper()
        rank_val = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10}.get(r, 0)
        if rank_val == 0:
            try:
                rank_val = int(r)
            except ValueError:
                pass
        if rank_val > 0:
            ranks.append(rank_val)
    ranks.sort()

    if len(ranks) >= 2:
        # Check for connected board (2 consecutive ranks → OESD with 2 hole cards)
        gaps = [ranks[i+1] - ranks[i] for i in range(len(ranks)-1)]
        min_gap = min(gaps) if gaps else 99
        if min_gap <= 1:
            draws.append('oesd')
        elif min_gap == 2:
            draws.append('gutshot')

    # Combo draw (flush + straight)
    if 'flush_draw' in draws and ('oesd' in draws or 'gutshot' in draws):
        # If both present, upgrade to combo on wet boards
        if 'oesd' in draws:
            draws = [d for d in draws if d not in ('flush_draw', 'oesd')]
            draws.append('combo_draw')

    # Overcards: if board has mostly low cards (5-8), overcards are possible draws
    if ranks and max(ranks) <= 9:
        draws.append('overcards')

    return draws if draws else ['gutshot']  # always some draw risk


@dataclass
class DrawThreat:
    """One specific draw threat on the board."""
    draw_type: str
    outs: int
    p_hit: float           # probability villain hits next card
    denial_bet_bb: float   # bet needed to deny this draw
    implied_factor: float
    scare_factor: float    # how bad it is if draw completes


@dataclass
class DenialResult:
    """Equity denial analysis."""
    # Board context
    street: str
    community: List[str]
    pot_bb: float
    eff_stack_bb: float
    spr: float

    # Draw threats
    draws_detected: List[DrawThreat]
    primary_draw: Optional[str]
    max_denial_bet_bb: float   # bet needed to deny strongest draw
    min_denial_bet_bb: float   # bet needed to deny weakest significant draw

    # Optimal sizing
    recommended_denial_bet_bb: float
    recommended_denial_pct: float    # as fraction of pot
    should_bet_for_denial: bool
    should_allow_draws: bool         # sometimes allowing a draw is +EV (build pot)

    # EV of denying vs allowing
    ev_if_denied: float
    ev_if_allowed: float
    denial_advantage_bb: float

    # SPR and stack-off risk
    stack_off_risk: str            # 'low', 'medium', 'high'
    hero_committed_if_raised: bool

    # Hero context
    hero_equity: float
    hero_hand_class: str

    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_equity_denial(
    pot_bb: float,
    eff_stack_bb: float,
    community: List[str],
    hero_hand_class: str = 'top_pair',
    hero_equity: float = 0.72,
    street: str = 'flop',
    villain_vpip: float = 0.28,
    villain_cbet_freq: float = 0.60,
    n_opponents: int = 1,
    explicit_draws: Optional[List[str]] = None,
) -> DenialResult:
    """
    Compute optimal bet size to deny equity to villain's draws.

    Args:
        pot_bb:           Current pot size in BB
        eff_stack_bb:     Effective stack remaining in BB
        community:        Community cards (used to auto-detect draws)
        hero_hand_class:  Hero's hand (affects how much denial matters)
        hero_equity:      Hero's current equity
        street:           'flop', 'turn', 'river'
        villain_vpip:     Villain VPIP (higher = more draws in range)
        villain_cbet_freq: How often villain bets (affects EV calculations)
        n_opponents:      Number of opponents
        explicit_draws:   Override auto-detection with explicit draw list

    Returns:
        DenialResult
    """
    spr = eff_stack_bb / pot_bb if pot_bb > 0 else 99.0
    remaining = _cards_remaining(street)

    # Detect draws
    draw_types = explicit_draws if explicit_draws else _detect_draws(community)

    threats: List[DrawThreat] = []
    for draw_type in draw_types:
        if draw_type not in _DRAW_MAP:
            continue
        name, outs, impl_factor, scare = _DRAW_MAP[draw_type]
        if remaining >= 2:
            p = _two_card_outs_pct(outs)
        elif remaining == 1:
            p = _one_card_outs_pct(outs)
        else:
            p = 0.0  # river: no cards left to come
        denial = _denial_bet(outs, pot_bb, remaining, impl_factor, eff_stack_bb)
        threats.append(DrawThreat(
            draw_type=name,
            outs=outs,
            p_hit=round(p, 3),
            denial_bet_bb=round(denial, 1),
            implied_factor=impl_factor,
            scare_factor=scare,
        ))

    # Sort by denial bet (most dangerous draw requires largest bet)
    threats.sort(key=lambda t: -t.denial_bet_bb)

    primary = threats[0].draw_type if threats else None
    max_denial = threats[0].denial_bet_bb if threats else pot_bb * 0.50
    min_denial = threats[-1].denial_bet_bb if threats else pot_bb * 0.33

    # Optimal denial bet: aim to deny primary draw, cap at 80% pot for value
    recommended = min(max_denial, pot_bb * 0.80)
    # Don't go below 33% pot (too cheap for villain to call even without draws)
    recommended = max(recommended, pot_bb * 0.33)
    # Don't exceed stack
    recommended = min(recommended, eff_stack_bb)
    rec_pct = recommended / pot_bb

    # Should we bet for denial?
    # Only deny if we're currently ahead AND draws could overtake
    max_scare = max((t.scare_factor for t in threats), default=0.0)
    should_deny = (hero_equity >= 0.55 and max_scare >= 0.50 and remaining > 0)
    should_allow = (spr >= 6 and hero_equity >= 0.80 and max_scare < 0.50)

    # EV estimates
    # If we deny: villain folds draws, we win pot frequently
    primary_p_hit = threats[0].p_hit if threats else 0.10
    ev_if_denied = (
        hero_equity * (pot_bb + 2 * recommended) - recommended
        + (1 - hero_equity) * (-recommended)
    )
    # If we allow (check): villain sees free card, some will hit
    adj_equity_after_free_card = hero_equity * (1 - primary_p_hit * max_scare)
    ev_if_allowed = adj_equity_after_free_card * pot_bb

    denial_advantage = ev_if_denied - ev_if_allowed

    # Stack-off risk if villain raises our bet
    raise_size = recommended * 2.5  # standard raise
    remaining_after = eff_stack_bb - recommended
    stack_off_risk = (
        'high' if remaining_after < raise_size
        else 'medium' if remaining_after < raise_size * 2
        else 'low'
    )
    committed = remaining_after <= recommended * 1.2

    # Villain adjustments: loose players have more draws in range
    draw_freq = min(0.35, 0.15 + (villain_vpip - 0.25) * 0.4)

    # Tips
    tips = []
    if should_allow:
        tips.append(
            f'Equity={hero_equity:.0%} is so strong that allowing a free card '
            f'is still +EV. Consider slow-playing to induce bluffs.'
        )
    if primary and max_scare >= 0.80:
        tips.append(
            f'Primary draw ({primary}) is very dangerous (scare={max_scare:.0f}). '
            f'Bet at least {max_denial:.1f}BB ({max_denial/pot_bb:.0%} pot) to deny.'
        )
    if spr < 2.5:
        tips.append(
            f'Low SPR={spr:.1f}: just jam {eff_stack_bb:.0f}BB. '
            f'Denial sizing matters less when you can commit the whole stack.'
        )
    if n_opponents > 1:
        tips.append(
            f'Multiway ({n_opponents} opponents): increase denial bet by '
            f'~{(n_opponents-1)*10:.0f}% to deny all players their draws simultaneously.'
        )
    if street == 'river':
        tips.append(
            'River: no more draws. Size based on value extraction, not equity denial.'
        )
    if denial_advantage > 3.0:
        tips.append(
            f'Denial advantage = {denial_advantage:+.1f}BB: betting for denial is '
            f'significantly better than checking here.'
        )

    reasoning = (
        f'Board: {" ".join(community[:4])} [{street}]. '
        f'Draws detected: {", ".join(t.draw_type for t in threats) or "none"}. '
        f'Primary draw: {primary or "none"} (denial bet={max_denial:.1f}BB). '
        f'Hero eq={hero_equity:.0%}, SPR={spr:.1f}. '
        f'Recommended bet: {recommended:.1f}BB ({rec_pct:.0%} pot). '
        f'EV(deny)={ev_if_denied:+.1f} EV(allow)={ev_if_allowed:+.1f} '
        f'advantage={denial_advantage:+.1f}BB.'
    )

    return DenialResult(
        street=street,
        community=list(community),
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        spr=round(spr, 2),
        draws_detected=threats,
        primary_draw=primary,
        max_denial_bet_bb=round(max_denial, 1),
        min_denial_bet_bb=round(min_denial, 1),
        recommended_denial_bet_bb=round(recommended, 1),
        recommended_denial_pct=round(rec_pct, 2),
        should_bet_for_denial=should_deny,
        should_allow_draws=should_allow,
        ev_if_denied=round(ev_if_denied, 2),
        ev_if_allowed=round(ev_if_allowed, 2),
        denial_advantage_bb=round(denial_advantage, 2),
        stack_off_risk=stack_off_risk,
        hero_committed_if_raised=committed,
        hero_equity=hero_equity,
        hero_hand_class=hero_hand_class,
        reasoning=reasoning,
        tips=tips,
    )


def denial_one_liner(result: DenialResult) -> str:
    """Single-line overlay summary."""
    draw_str = result.primary_draw or 'no draw'
    return (
        f'Denial [{draw_str}] bet {result.recommended_denial_bet_bb:.1f}BB '
        f'({result.recommended_denial_pct:.0%}pot) | '
        f'EV gain={result.denial_advantage_bb:+.1f}BB | '
        f'stack-off={result.stack_off_risk}'
    )
