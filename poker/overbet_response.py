"""
Overbet Response Advisor (overbet_response.py)

Covers the DEFENDER's perspective when villain bets more than the pot (1.0x-2.5x).

Why overbets are hard to defend against:
  - Alpha is high: a 1.5x pot overbet requires fold 60% to break even
  - Villain's range is maximally polarized (nuts or air, nothing in between)
  - Medium-strength hands lose to villain's value and beat villain's air —
    but villain's air was going to fold to any bet, so calling with medium
    hands just means losing to the value half of the range
  - The correct defend range consists almost entirely of bluff-catchers with
    blockers to villain's nuts, plus your own nutted hands (but nutted hands
    are rare enough that mostly you're calling with bluff-catchers)

Key formulas:
  alpha = bet / (pot + bet)     <- fraction of range villain needs to fold
  MDF  = 1 - alpha              <- minimum defend frequency
  Required equity to call = alpha (if villain's range is pure value)
                          = lower (if villain is bluffing often)

When alpha is 60%, MDF = 40%: hero must continue with 40% of range.
With a typical calling range, that means folding 60% including medium hands.

Raise scenario:
  Raise is only correct with the top fraction of hero's range.
  Raise sizing against overbet: typically 2.2-2.5x the overbet.
  Very infrequent (< 5% of situations) because:
  - Villain's value range is very strong
  - A raise commits hero to a large pot with a strong hand (which is fine,
    but there are few such hands)

Key principle:
  - CALL with: bluff-catchers that block villain's nuts (e.g., have an ace
    on a board where villain can have nut flush with A-high flush)
  - FOLD with: medium-strength hands that lose to value and beat folded air
  - RAISE with: true nutted holdings (top 5-10% of range)

Usage:
    from poker.overbet_response import respond_to_overbet, OverbetResponse
    result = respond_to_overbet(
        hero_hand_class='top_pair',
        hero_equity=0.55,
        hero_has_blocker=True,
        villain_bet_pct=1.50,
        pot_bb=20.0,
        eff_stack_bb=80.0,
        street='river',
        villain_af=2.5,
        villain_wtsd=0.30,
    )
    print(result.action, result.ev)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _alpha(bet_pct: float) -> float:
    """Fold equity villain needs. alpha = bet / (pot + bet)."""
    return bet_pct / (1.0 + bet_pct)


def _mdf(bet_pct: float) -> float:
    return 1.0 - _alpha(bet_pct)


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'draw': 1, 'backdoor_draw': 1, 'bottom_pair': 2,
        'middle_pair': 3, 'top_pair_weak': 4, 'top_pair': 5, 'tptk': 6,
        'top_pair_strong': 6, 'overpair': 6, 'two_pair': 7, 'set': 8,
        'straight': 9, 'flush': 10, 'full_house': 11, 'quads': 12,
    }.get(hand_class.lower(), 5)


def _villain_bluff_freq_estimate(villain_af: float, villain_wtsd: float,
                                  bet_pct: float) -> float:
    """
    Estimate how often villain is bluffing in an overbet.
    - High AF + low WTSD = balanced or even bluff-heavy with overbets
    - Low AF + high WTSD = very value-heavy with overbets
    - bet_pct > 1.5 = typically more polar (more bluffs mixed in)
    """
    # Base: assume GTO roughly half bluff half value at MDF
    base = _mdf(bet_pct)   # villain needs to bluff this % to make hero indifferent

    # Villain AF adjustment: aggressive players bluff more
    af_adj = (villain_af - 2.0) * 0.05
    # WTSD adjustment: high WTSD = tends to showdown value, not bluff heavy
    wtsd_adj = -(villain_wtsd - 0.30) * 0.20

    estimated = base + af_adj + wtsd_adj
    return round(max(0.05, min(0.80, estimated)), 3)


def _required_equity_to_call(
    villain_bluff_freq: float,
    bet_pct: float,
    pot_bb: float,
    hero_equity_vs_value: float,
    hero_equity_vs_bluff: float,
) -> float:
    """
    Minimum equity needed to make calling +EV.
    EV(call) = bluff_freq × (pot + bet) × hero_wins_vs_bluff
               + value_freq × (pot + bet) × hero_wins_vs_value
               - bet
    """
    value_freq = 1.0 - villain_bluff_freq
    bet_bb = pot_bb * bet_pct
    total_pot = pot_bb + bet_bb

    ev_call = (villain_bluff_freq * total_pot * hero_equity_vs_bluff +
               value_freq * total_pot * hero_equity_vs_value - bet_bb)
    ev_fold = 0.0

    return ev_call  # positive = call is +EV


def _raise_sizing(overbet_bb: float, pot_bb: float) -> float:
    """Raise to this many BB when raising vs an overbet."""
    # Standard: raise to ~2.3x the overbet (to maintain pot geometry)
    return round(overbet_bb * 2.3, 1)


def _decide_action(
    rank: int,
    hero_equity: float,
    hero_has_blocker: bool,
    bet_pct: float,
    villain_bluff_freq: float,
    alpha: float,
    mdf: float,
    pot_bb: float,
    eff_stack_bb: float,
    street: str,
) -> tuple:
    """Return (action, ev_estimate, reasoning)."""
    bet_bb = pot_bb * bet_pct
    total_pot_if_call = pot_bb + bet_bb
    raise_to = _raise_sizing(bet_bb, pot_bb)

    # Very nutted hands — raise or call
    if rank >= 9:  # straight+
        ev_raise = hero_equity * (pot_bb + 2 * raise_to) - raise_to
        return ('raise', round(ev_raise, 2),
                f'Nutted hand ({rank}): raise to {raise_to:.0f}BB. '
                f'Villain is polarized — if value, you beat it; if bluff, you win more.')

    # Two pair / set — usually call, sometimes raise on river
    if rank >= 7:
        # EV of calling
        ev_call = hero_equity * total_pot_if_call - bet_bb
        if rank == 8 and hero_equity >= 0.80:
            return ('raise', round(ev_call * 1.15, 2),
                    f'Set: raise to {raise_to:.0f}BB. High equity beats most value; '
                    f'bluffs fold and you win pot.')
        return ('call', round(ev_call, 2),
                f'Strong hand (two pair+): call. Equity={hero_equity:.0%} vs polarized range. '
                f'Blocker={hero_has_blocker}.')

    # Bluff catchers — call only with blockers + enough equity
    if rank >= 5:  # TPTK, overpair, top pair
        ev_call = (villain_bluff_freq * total_pot_if_call * 0.90 +  # vs bluff: win ~90%
                   (1 - villain_bluff_freq) * total_pot_if_call * (hero_equity * 0.4) -  # vs value: usually lose
                   bet_bb)
        # Blocker improves by reducing villain value combos
        blocker_boost = 0.05 if hero_has_blocker else -0.05
        adj_ev = round(ev_call + blocker_boost * pot_bb, 2)

        if hero_equity >= alpha + 0.05 and hero_has_blocker:
            return ('call', adj_ev,
                    f'Bluff-catcher with blocker: call. Equity={hero_equity:.0%} > alpha={alpha:.0%}. '
                    f'Blocker reduces villain nut combos. Villain bluffing ~{villain_bluff_freq:.0%}.')
        elif hero_equity >= alpha:
            return ('call', adj_ev,
                    f'Marginal call: equity={hero_equity:.0%} barely >= alpha={alpha:.0%}. '
                    f'Prefer to have blocker. Villain bluff freq ~{villain_bluff_freq:.0%}.')
        else:
            return ('fold', 0.0,
                    f'Fold top pair: equity={hero_equity:.0%} < alpha={alpha:.0%}. '
                    f'Against polarized overbet, medium hands are dominated. '
                    f'Villain bluffing only ~{villain_bluff_freq:.0%} here.')

    # Middle pair, bottom pair, draws — typically fold
    if rank >= 2:
        if hero_has_blocker and villain_bluff_freq >= 0.45 and street != 'river':
            ev_call = villain_bluff_freq * total_pot_if_call - bet_bb
            return ('call', round(ev_call, 2),
                    f'Marginal: middle/bottom pair + blocker + high bluff freq. '
                    f'Thin call only when villain is bluffing heavily.')
        return ('fold', 0.0,
                f'Fold {rank}-rank hand to {bet_pct:.0%} pot overbet. '
                f'Medium hands are the worst to defend with: lose to value, beat air that folds anyway.')

    # Air / total miss
    return ('fold', 0.0,
            f'Fold air. No equity, no blocker value. '
            f'alpha={alpha:.0%}, villain bluff freq={villain_bluff_freq:.0%}.')


@dataclass
class OverbetResponse:
    """Advice for responding to a villain overbet."""
    # Bet context
    villain_bet_pct: float      # e.g., 1.50 = 150% pot
    villain_bet_bb: float
    pot_bb: float
    eff_stack_bb: float
    street: str

    # Math
    alpha: float                # fold equity villain needs
    mdf: float                  # minimum defend frequency
    villain_bluff_freq: float   # estimated bluff rate in this spot
    required_equity: float      # minimum equity to call

    # Hero hand
    hero_hand_class: str
    hero_equity: float
    hero_has_blocker: bool

    # Decision
    action: str                 # 'fold', 'call', 'raise'
    ev: float
    raise_to_bb: float          # 0 if not raising

    # Explanation
    action_reasoning: str
    key_concepts: List[str] = field(default_factory=list)
    range_notes: str = ''


def respond_to_overbet(
    hero_hand_class: str,
    hero_equity: float,
    hero_has_blocker: bool,
    villain_bet_pct: float,
    pot_bb: float,
    eff_stack_bb: float,
    street: str = 'river',
    villain_af: float = 2.0,
    villain_wtsd: float = 0.30,
) -> OverbetResponse:
    """
    How to respond when villain overbets (bets > pot).

    Args:
        hero_hand_class:   Hand classification (e.g., 'top_pair', 'set')
        hero_equity:       Hero's equity vs villain's entire range
        hero_has_blocker:  Hero holds a card that blocks villain's nut hands
        villain_bet_pct:   Bet size as fraction of pot (e.g., 1.5 = 150%)
        pot_bb:            Pot size in BB before the bet
        eff_stack_bb:      Effective stack remaining (excluding bet)
        street:            'flop', 'turn', 'river'
        villain_af:        Villain's aggression factor
        villain_wtsd:      Villain's went-to-showdown rate

    Returns:
        OverbetResponse with fold/call/raise decision and reasoning
    """
    a = _alpha(villain_bet_pct)
    m = _mdf(villain_bet_pct)
    bet_bb = round(pot_bb * villain_bet_pct, 1)
    bluff_freq = _villain_bluff_freq_estimate(villain_af, villain_wtsd, villain_bet_pct)
    rank = _hand_rank(hero_hand_class)
    raise_to = _raise_sizing(bet_bb, pot_bb)

    action, ev, reasoning = _decide_action(
        rank, hero_equity, hero_has_blocker, villain_bet_pct,
        bluff_freq, a, m, pot_bb, eff_stack_bb, street,
    )

    # Key concepts to teach
    concepts = [
        f'Overbet alpha={a:.0%}: villain needs {a:.0%} folds. '
        f'MDF={m:.0%}: hero must continue {m:.0%} of range.',
        f'Villain range is polarized (nuts or bluff). Medium hands are '
        f'the worst to defend — they lose to value, beat air that folds anyway.',
        f'Estimated villain bluff frequency: {bluff_freq:.0%}. '
        f'{"High" if bluff_freq >= 0.45 else "Low" if bluff_freq < 0.30 else "Moderate"} — '
        f'{"call wider than usual" if bluff_freq >= 0.45 else "tighten vs likely value-heavy overbet" if bluff_freq < 0.30 else "standard response"}.',
    ]

    if hero_has_blocker:
        concepts.append(
            'Hero has blocker to villain nuts: each blocker card reduces villain '
            'value combos by ~25-50%, making a call more profitable.'
        )
    else:
        concepts.append(
            'No blocker to villain nuts: hero cannot unblock villain bluffs. '
            'Bias toward folding medium strength hands.'
        )

    range_notes = (
        f'{villain_bet_pct:.0%} pot overbet ({bet_bb:.0f}BB into {pot_bb:.0f}BB pot). '
        f'Call with: nutted hands + bluff-catchers with blockers. '
        f'Fold: medium strength. Raise: top 5% of range (pure nuts). '
        f'MDF={m:.0%} — fold everything below threshold.'
    )

    return OverbetResponse(
        villain_bet_pct=villain_bet_pct,
        villain_bet_bb=bet_bb,
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        street=street,
        alpha=round(a, 3),
        mdf=round(m, 3),
        villain_bluff_freq=bluff_freq,
        required_equity=round(a, 3),
        hero_hand_class=hero_hand_class,
        hero_equity=round(hero_equity, 3),
        hero_has_blocker=hero_has_blocker,
        action=action,
        ev=ev,
        raise_to_bb=raise_to if action == 'raise' else 0.0,
        action_reasoning=reasoning,
        key_concepts=concepts,
        range_notes=range_notes,
    )


def overbet_response_one_liner(result: OverbetResponse) -> str:
    """Single-line overlay summary."""
    return (
        f'vs OB {result.villain_bet_pct:.0%}pot: {result.action.upper()} | '
        f'alpha={result.alpha:.0%} MDF={result.mdf:.0%} | '
        f'vbluff~{result.villain_bluff_freq:.0%} | '
        f'EV={result.ev:+.1f}BB'
    )
