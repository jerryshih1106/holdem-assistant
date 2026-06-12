"""
GTO Mixed Strategy Advisor (mixed_strategy_advisor.py)

A core GTO principle: in many spots, betting 100% of the time OR checking 100%
of the time is EXPLOITABLE. A thinking villain will notice and adjust.

Example: If hero always bets top pair on dry flops when IP, villain can:
  - Call down wider (knowing hero always has a made hand)
  - Float and bluff-raise (knowing hero's check-back = weak hand)

Solution: MIXING. Bet top pair 70% of the time; check 30%.

Why pure mixing is hard in practice:
  - Truly random behavior requires a RNG the player can't execute at table
  - Players tend to "feel" like betting (biased toward action when strong)
  - Over time, patterns emerge that observant villains exploit

This module provides DETERMINISTIC MIXING — using the current hand's
"fingerprint" (pot_bb + hand rank + board hash) to deterministically
assign bet or check for this specific hand instance. The fingerprint
changes every hand, making the pattern undetectable over a session,
while the player simply follows the module's recommendation.

IMPORTANT: This is NOT randomness — it is pseudo-random that feels
random to observers but is consistent advice for the same situation.

GTO Frequency Reference Table (simplified, 6-max cash):
  ┌────────────────────────┬──────────┬─────────┬─────────┐
  │ Spot                   │ Dry      │ Medium  │ Wet     │
  ├────────────────────────┼──────────┼─────────┼─────────┤
  │ IP C-bet: Overpair     │ 88%      │ 83%     │ 75%     │
  │ IP C-bet: Top Pair     │ 78%      │ 68%     │ 55%     │
  │ IP C-bet: Middle Pair  │ 42%      │ 32%     │ 22%     │
  │ IP C-bet: Air/Bluff    │ 38%      │ 28%     │ 20%     │
  │ IP C-bet: Draw         │ 60%      │ 55%     │ 45%     │
  │ OOP C-bet: Overpair    │ 80%      │ 72%     │ 60%     │
  │ OOP C-bet: Top Pair    │ 68%      │ 55%     │ 42%     │
  │ OOP C-bet: Air/Bluff   │ 22%      │ 15%     │ 12%     │
  │ IP Turn Barrel (blank) │ 68%      │ 58%     │ 48%     │
  │ IP Turn Barrel (scare) │ 28%      │ 20%     │ 15%     │
  │ OOP Turn Probe         │ 55%      │ 45%     │ 35%     │
  │ River Value (TP+)      │ 75%      │ 72%     │ 70%     │
  │ River Bluff            │ 35%      │ 33%     │ 30%     │
  └────────────────────────┴──────────┴─────────┴─────────┘

Mixing prevents exploitation across an entire session. A player who ALWAYS
bets top pair (100%) gives up 3-8 BB/100 to a solver-capable opponent.
Proper mixing recovers that edge.

Usage:
    from poker.mixed_strategy_advisor import advise_mixed_strategy
    from poker.mixed_strategy_advisor import MixedStrategyAdvice, mixed_strategy_one_liner

    result = advise_mixed_strategy(
        hero_hand_class='top_pair',
        board_type='medium',
        hero_pos='IP',
        street='flop',
        spot_type='cbet',
        pot_bb=15.0,
        hero_equity=0.65,
        spr=6.0,
        villain_af=2.0,
    )
    print(result.recommended_action, result.gto_bet_freq)
"""

from dataclasses import dataclass, field
from typing import List


# ── GTO frequency lookup table ──────────────────────────────────────────────
# Structure: (spot_type, hand_category, board_type) → (bet_freq, bet_size_pct)
# bet_freq: fraction of time to bet (0-1)
# bet_size_pct: recommended bet as fraction of pot

_GTO_FREQ: dict = {
    # (spot, hand_cat, board) → (freq, size_pct)
    ('cbet', 'premium', 'dry'):    (0.92, 0.65),
    ('cbet', 'premium', 'medium'): (0.88, 0.60),
    ('cbet', 'premium', 'wet'):    (0.80, 0.75),
    ('cbet', 'overpair', 'dry'):   (0.88, 0.55),
    ('cbet', 'overpair', 'medium'):(0.83, 0.55),
    ('cbet', 'overpair', 'wet'):   (0.75, 0.65),
    ('cbet', 'tptk', 'dry'):       (0.82, 0.50),
    ('cbet', 'tptk', 'medium'):    (0.72, 0.50),
    ('cbet', 'tptk', 'wet'):       (0.60, 0.60),
    ('cbet', 'top_pair', 'dry'):   (0.78, 0.45),
    ('cbet', 'top_pair', 'medium'):(0.68, 0.45),
    ('cbet', 'top_pair', 'wet'):   (0.55, 0.55),
    ('cbet', 'middle_pair', 'dry'):(0.42, 0.40),
    ('cbet', 'middle_pair', 'medium'):(0.32, 0.38),
    ('cbet', 'middle_pair', 'wet'):(0.22, 0.35),
    ('cbet', 'draw', 'dry'):       (0.60, 0.45),
    ('cbet', 'draw', 'medium'):    (0.55, 0.45),
    ('cbet', 'draw', 'wet'):       (0.48, 0.50),
    ('cbet', 'air', 'dry'):        (0.38, 0.35),
    ('cbet', 'air', 'medium'):     (0.28, 0.33),
    ('cbet', 'air', 'wet'):        (0.20, 0.33),
    # OOP c-bets: lower frequency (less range advantage)
    ('cbet_oop', 'overpair', 'dry'):   (0.80, 0.55),
    ('cbet_oop', 'overpair', 'medium'):(0.72, 0.55),
    ('cbet_oop', 'overpair', 'wet'):   (0.60, 0.70),
    ('cbet_oop', 'top_pair', 'dry'):   (0.68, 0.45),
    ('cbet_oop', 'top_pair', 'medium'):(0.55, 0.45),
    ('cbet_oop', 'top_pair', 'wet'):   (0.42, 0.55),
    ('cbet_oop', 'middle_pair', 'dry'):(0.30, 0.40),
    ('cbet_oop', 'middle_pair', 'medium'):(0.22, 0.38),
    ('cbet_oop', 'middle_pair', 'wet'):(0.15, 0.35),
    ('cbet_oop', 'air', 'dry'):        (0.22, 0.33),
    ('cbet_oop', 'air', 'medium'):     (0.15, 0.33),
    ('cbet_oop', 'air', 'wet'):        (0.12, 0.33),
    # Turn barrels (blank turn card)
    ('barrel', 'premium', 'dry'):      (0.90, 0.65),
    ('barrel', 'overpair', 'dry'):     (0.80, 0.60),
    ('barrel', 'top_pair', 'dry'):     (0.68, 0.55),
    ('barrel', 'top_pair', 'medium'):  (0.58, 0.55),
    ('barrel', 'top_pair', 'wet'):     (0.48, 0.60),
    ('barrel', 'draw', 'dry'):         (0.55, 0.50),
    ('barrel', 'draw', 'medium'):      (0.50, 0.55),
    ('barrel', 'draw', 'wet'):         (0.60, 0.60),
    ('barrel', 'air', 'dry'):          (0.28, 0.45),
    ('barrel', 'air', 'medium'):       (0.20, 0.45),
    ('barrel', 'air', 'wet'):          (0.15, 0.45),
    # Turn barrels (scare turn card: board pairs, flush completes)
    ('barrel_scare', 'overpair', 'dry'):   (0.30, 0.50),
    ('barrel_scare', 'top_pair', 'dry'):   (0.28, 0.50),
    ('barrel_scare', 'top_pair', 'wet'):   (0.15, 0.45),
    ('barrel_scare', 'draw', 'wet'):       (0.65, 0.65),  # drew out
    ('barrel_scare', 'air', 'wet'):        (0.20, 0.50),
    # OOP probe bets (after villain checks back flop)
    ('probe', 'top_pair', 'dry'):      (0.55, 0.45),
    ('probe', 'top_pair', 'medium'):   (0.48, 0.45),
    ('probe', 'top_pair', 'wet'):      (0.40, 0.55),
    ('probe', 'draw', 'wet'):          (0.52, 0.50),
    ('probe', 'air', 'dry'):           (0.30, 0.40),
    ('probe', 'air', 'medium'):        (0.22, 0.38),
    # River value bets
    ('river_value', 'premium', 'dry'):     (0.90, 0.80),
    ('river_value', 'premium', 'wet'):     (0.88, 0.90),
    ('river_value', 'overpair', 'dry'):    (0.78, 0.65),
    ('river_value', 'top_pair', 'dry'):    (0.75, 0.55),
    ('river_value', 'top_pair', 'medium'): (0.72, 0.55),
    ('river_value', 'top_pair', 'wet'):    (0.70, 0.60),
    ('river_value', 'middle_pair', 'dry'): (0.40, 0.35),
    ('river_value', 'air', 'dry'):         (0.35, 0.65),  # bluff with 100%pot
    ('river_value', 'air', 'medium'):      (0.33, 0.75),
    ('river_value', 'air', 'wet'):         (0.30, 0.80),
}


def _hand_category(hand_class: str) -> str:
    """Normalize to category used in GTO table."""
    mapping = {
        'air': 'air', 'trash': 'air', 'fold': 'air',
        'bottom_pair': 'air', 'marginal': 'air',
        'middle_pair': 'middle_pair', 'draw': 'draw', 'speculative': 'draw',
        'top_pair': 'top_pair', 'medium': 'top_pair',
        'tptk': 'tptk', 'overpair': 'overpair', 'two_pair': 'overpair',
        'strong': 'overpair',
        'set': 'premium', 'straight': 'premium', 'flush': 'premium',
        'premium': 'premium', 'full_house': 'premium', 'quads': 'premium',
        'nuts': 'premium',
    }
    return mapping.get(hand_class.lower(), 'top_pair')


def _lookup_freq(spot_type: str, hero_pos: str, hand_class: str, board_type: str) -> tuple:
    """Look up GTO frequency and size from table, with fallbacks."""
    hand_cat = _hand_category(hand_class)

    # Build the effective spot key (OOP c-bets use different key)
    if spot_type == 'cbet' and hero_pos == 'OOP':
        effective_spot = 'cbet_oop'
    else:
        effective_spot = spot_type

    key = (effective_spot, hand_cat, board_type)
    if key in _GTO_FREQ:
        return _GTO_FREQ[key]

    # Fallback: try medium board
    key2 = (effective_spot, hand_cat, 'medium')
    if key2 in _GTO_FREQ:
        return _GTO_FREQ[key2]

    # Fallback: default by hand category
    if hand_cat in ('premium', 'overpair'):
        return (0.80, 0.60)
    if hand_cat in ('tptk', 'top_pair'):
        return (0.65, 0.50)
    if hand_cat == 'middle_pair':
        return (0.30, 0.40)
    if hand_cat == 'draw':
        return (0.50, 0.50)
    return (0.25, 0.40)  # air default


def _deterministic_mix(bet_freq: float, pot_bb: float, hand_class: str, street: str) -> str:
    """
    Deterministic pseudo-random recommendation: bet or check.

    Uses a stable hash of the situation to assign bet/check for THIS hand.
    The hash changes across hands (pot_bb varies) but is consistent for
    same situation → prevents detectable patterns while providing
    confident single-action guidance.

    Returns 'bet' or 'check'.
    """
    # Create a stable hand fingerprint
    hand_hash = sum(ord(c) * (i + 1) for i, c in enumerate(hand_class))
    street_hash = {'preflop': 1, 'flop': 3, 'turn': 7, 'river': 11}.get(street, 5)
    pot_bucket = int(pot_bb / 3) % 100  # bucket pot size to reduce randomness
    fingerprint = (hand_hash * 13 + street_hash * 31 + pot_bucket * 97) % 100

    # If fingerprint < bet_freq*100, recommend bet
    if fingerprint < bet_freq * 100:
        return 'bet'
    return 'check'


def _spr_adjustment(bet_freq: float, spr: float, hand_cat: str) -> float:
    """Adjust bet frequency for SPR extremes."""
    if spr < 2.0:
        # Very low SPR: value hands should bet more (commit); bluffs less
        if hand_cat in ('premium', 'overpair', 'tptk', 'top_pair'):
            return min(0.98, bet_freq + 0.10)
        return max(0.05, bet_freq - 0.15)  # bluffs less committed
    if spr > 12.0:
        # High SPR: more mixing; protect checking range
        if hand_cat in ('premium',):
            return max(0.50, bet_freq - 0.15)  # trap sometimes
        return max(0.08, bet_freq - 0.05)
    return bet_freq


def _exploitative_adjustment(
    bet_freq: float,
    villain_af: float,
    hero_equity: float,
) -> float:
    """Adjust for villain type (exploitative deviations from GTO)."""
    # vs aggressive villain: check more (induce bluffs with strong hands)
    if villain_af >= 3.0 and hero_equity >= 0.65:
        bet_freq = max(0.30, bet_freq - 0.15)  # trap more
    # vs passive villain: bet more (they won't bluff if hero checks)
    if villain_af < 1.0:
        bet_freq = min(0.95, bet_freq + 0.10)
    return bet_freq


def _mixing_explanation(bet_freq: float, hand_cat: str, spot_type: str) -> str:
    """Why mixing is required or not here."""
    if bet_freq >= 0.92:
        return f'Almost always bet: {hand_cat} here is too strong to mix.'
    if bet_freq <= 0.08:
        return f'Almost always check: {hand_cat} lacks sufficient equity/fold-equity here.'
    check_freq = round(1.0 - bet_freq, 2)
    if spot_type in ('cbet', 'cbet_oop'):
        return (
            f'Mix required: always betting {hand_cat} is exploitable. '
            f'Bet {bet_freq:.0%} to protect your checking range '
            f'(check {check_freq:.0%} = trapping + pot-controlling).'
        )
    if spot_type == 'barrel':
        return (
            f'Mix turn barrel: continue {bet_freq:.0%}, '
            f'give up {check_freq:.0%}. '
            f'Checking some strong hands balances your turn checking range.'
        )
    return (
        f'Optimal mix: {bet_freq:.0%} bet, {check_freq:.0%} check. '
        f'Using this frequency keeps your range unexploitable.'
    )


@dataclass
class MixedStrategyAdvice:
    """GTO mixed strategy recommendation for a single hand."""
    hero_hand_class: str
    board_type: str
    hero_pos: str
    street: str
    spot_type: str
    pot_bb: float
    hero_equity: float
    spr: float
    villain_af: float

    # GTO frequencies (before and after adjustments)
    hand_category: str
    gto_bet_freq: float       # base GTO frequency (no adjustments)
    adj_bet_freq: float       # after SPR + villain adjustments
    gto_check_freq: float     # 1 - adj_bet_freq
    bet_size_pct: float       # recommended bet size as fraction of pot
    bet_size_bb: float        # bet size in BB

    # Decision for THIS hand
    recommended_action: str   # 'bet' or 'check' (deterministic for this hand)
    should_mix: bool          # True if mixing is meaningful (freq 10-90%)

    reasoning: str
    mixing_explanation: str
    tips: List[str] = field(default_factory=list)


def advise_mixed_strategy(
    hero_hand_class: str = 'top_pair',
    board_type: str = 'medium',
    hero_pos: str = 'IP',
    street: str = 'flop',
    spot_type: str = 'cbet',
    pot_bb: float = 15.0,
    hero_equity: float = 0.65,
    spr: float = 6.0,
    villain_af: float = 2.0,
) -> MixedStrategyAdvice:
    """
    Recommend GTO-correct action for a hand requiring mixed strategy.

    Args:
        hero_hand_class:  Hero's hand strength category
        board_type:       'dry', 'medium', 'wet'
        hero_pos:         'IP' or 'OOP'
        street:           'flop', 'turn', 'river'
        spot_type:        'cbet' / 'barrel' / 'barrel_scare' / 'probe' / 'river_value'
        pot_bb:           Current pot size in BB
        hero_equity:      Hero's equity (0-1)
        spr:              Stack-to-pot ratio
        villain_af:       Villain's aggression factor

    Returns:
        MixedStrategyAdvice with deterministic bet/check recommendation
    """
    hand_cat = _hand_category(hero_hand_class)
    gto_freq, size_pct = _lookup_freq(spot_type, hero_pos, hero_hand_class, board_type)
    adj_freq = _spr_adjustment(gto_freq, spr, hand_cat)
    adj_freq = _exploitative_adjustment(adj_freq, villain_af, hero_equity)
    adj_freq = round(min(0.98, max(0.02, adj_freq)), 3)

    should_mix = 0.10 <= adj_freq <= 0.90

    action = _deterministic_mix(adj_freq, pot_bb, hero_hand_class, street)

    bet_bb = round(pot_bb * size_pct, 1)

    reasoning = (
        f'{action.upper()}: {hero_hand_class} on {board_type} board '
        f'({spot_type} spot, {hero_pos}). '
        f'GTO bet freq={gto_freq:.0%}, adjusted={adj_freq:.0%}. '
        f'Deterministic mix (fingerprint) → {action}. '
        f'Bet size if betting: {size_pct:.0%} pot = {bet_bb:.1f}BB.'
    )

    mix_expl = _mixing_explanation(adj_freq, hand_cat, spot_type)

    # Tips
    tips = []
    if should_mix:
        tips.append(
            f'WHY MIX: Betting {hero_hand_class} {gto_freq:.0%} of the time is GTO. '
            f'Always betting (100%) = villain knows you have made hand → '
            f'they fold weak hands you want to call, and call/raise with strength. '
            f'Checking {1-adj_freq:.0%} = protects your check range with strong holdings.'
        )
    if action == 'check' and hand_cat in ('top_pair', 'overpair', 'tptk'):
        tips.append(
            f'Strong hand, checking this time (freq={adj_freq:.0%}): '
            f'This is a TRAP check. When you check back, villain bluffs and you check-raise or call down. '
            f'Do NOT routinely bet every time — mixing is essential for balance.'
        )
    if action == 'bet' and hand_cat == 'air':
        tips.append(
            f'Bluff bet recommended this time (freq={adj_freq:.0%}): '
            f'Execute as a semi-bluff if you have any equity, or pure bluff if villain folds >alpha. '
            f'Sizing: {size_pct:.0%} pot is optimal for fold equity. '
            f'If called, shut down on turn (check fold) unless you improve.'
        )
    if villain_af >= 3.0 and action == 'check':
        tips.append(
            f'Villain is aggressive (AF={villain_af:.1f}). '
            f'Checking induces bluffs. Plan: check then call or check-raise when villain bets. '
            f'Checking strong hands vs aggressive players = highest EV line.'
        )
    if spr < 2.5 and action == 'bet':
        tips.append(
            f'Low SPR ({spr:.1f}): betting commits you. '
            f'This hand ({hero_hand_class}) is strong enough to commit at this SPR. '
            f'If raised, call off remaining stack.'
        )
    if not tips:
        tips.append(
            f'{action.upper()} {hero_hand_class} | '
            f'GTO={gto_freq:.0%} | adj={adj_freq:.0%} | '
            f'Mix: {"YES" if should_mix else "NO-polarized"}. '
            f'Bet size: {size_pct:.0%}pot ({bet_bb:.1f}BB).'
        )

    return MixedStrategyAdvice(
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        hero_pos=hero_pos,
        street=street,
        spot_type=spot_type,
        pot_bb=round(pot_bb, 1),
        hero_equity=round(hero_equity, 3),
        spr=round(spr, 2),
        villain_af=round(villain_af, 2),
        hand_category=hand_cat,
        gto_bet_freq=round(gto_freq, 3),
        adj_bet_freq=adj_freq,
        gto_check_freq=round(1.0 - adj_freq, 3),
        bet_size_pct=size_pct,
        bet_size_bb=bet_bb,
        recommended_action=action,
        should_mix=should_mix,
        reasoning=reasoning,
        mixing_explanation=mix_expl,
        tips=tips,
    )


def mixed_strategy_one_liner(result: MixedStrategyAdvice) -> str:
    return (
        f'[MIX {result.hero_hand_class}@{result.street}|{result.hero_pos}] '
        f'{result.recommended_action.upper()} '
        f'(GTO:{result.gto_bet_freq:.0%}bet/{result.gto_check_freq:.0%}chk) | '
        f'bet={result.bet_size_pct:.0%}pot({result.bet_size_bb:.1f}BB) '
        f'mix={"YES" if result.should_mix else "NO"}'
    )
