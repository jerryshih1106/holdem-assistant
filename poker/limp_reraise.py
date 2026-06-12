"""
Limp-Reraise Advisor (limp_reraise.py)

A limp-reraise (LRR) is when hero limps preflop and then re-raises
after a villain raises behind them. It is a deceptive trap move:

Why limp-reraise works:
  - Hero's limping range looks weak, so villain raises wide
  - Hero then springs the trap with a massive re-raise
  - Villain is now facing a pot-committed decision with a weaker hand
  - Works best at passive tables where limps are common and raises happen

When to limp-reraise:
  - Table is passive (most players limp, raises indicate strength)
  - Villain directly behind hero is very aggressive (3-bets/opens wide)
  - Stack depth is 60-150BB (too deep = awkward sizing; too short = just shove)
  - Hero is in early position with AA/KK (too strong to risk being squeezed)
  - Sometimes with AKs, QQ as balanced trapping range

When NOT to limp-reraise:
  - Table is aggressive (many 3-bettors behind) — limp may never face a raise
  - Stack is short (<40BB) — just shove instead
  - Hero is on BTN/CO — better to open-raise and build pot in position
  - Villain rarely raises limpers — limp will just limp multiway

EV comparison: open-raise vs limp-reraise
  - Open-raise: immediately builds pot, less trappy, shows strength
  - Limp-reraise: larger pot when it works (bigger re-raise), but:
      * Sometimes walks through (no one raises) — lose value vs just raising
      * In position opens lose the positional advantage

Optimal limp-reraise sizing:
  - Villain open to X BB → re-raise to 3.0x–3.5x villain's open
  - Typically: 9-11x original limp (1BB)
  - Leave villain with SPR ~1.0-1.5 post-flop (pot-committed)

Usage:
    from poker.limp_reraise import advise_limp_reraise, LimpReraiseAdvice
    result = advise_limp_reraise(
        hero_hand_class='premium',
        hero_pos='UTG',
        villain_open_freq=0.30,
        table_type='passive',
        eff_stack_bb=100.0,
        n_players=6,
        villain_vpip=0.40,
    )
    print(result.action, result.limp_reraise_freq)
"""

from dataclasses import dataclass, field
from typing import List


def _hand_rank(hand_class: str) -> int:
    return {
        'premium': 10,    # AA, KK
        'strong': 8,      # QQ, JJ, AKs
        'medium_pair': 6, # TT-88, AQs, AJs
        'medium': 5,
        'speculative': 3, # Small pairs, suited connectors
        'marginal': 2,
        'trash': 0,
        'air': 0,
        'top_pair': 5, 'two_pair': 7, 'set': 9, 'tptk': 6, 'overpair': 8,
    }.get(hand_class.lower(), 4)


def _villain_raise_prob(villain_open_freq: float, table_type: str,
                        n_players: int) -> float:
    """Probability that someone raises hero's limp."""
    base = villain_open_freq
    # More players → higher chance someone raises
    multi_adj = (n_players - 2) * 0.05
    table_adj = {'passive': -0.10, 'standard': 0.0, 'aggressive': 0.15}.get(
        table_type, 0.0)
    return round(min(0.85, max(0.10, base + multi_adj + table_adj)), 3)


def _lrr_size(villain_open_bb: float, eff_stack_bb: float) -> float:
    """Optimal limp-reraise size in BB."""
    # Re-raise to 3.0-3.5x villain's open
    mult = 3.2 if eff_stack_bb <= 80 else 3.0
    raw = villain_open_bb * mult
    # Cap at 33% of stack (keep villain with chips to call)
    return round(min(eff_stack_bb * 0.33, max(7.0, raw)), 1)


def _ev_open(hand_rank: int, hero_equity: float, pot_bb: float,
             villain_fold_pct: float) -> float:
    """Simple EV of open-raising."""
    open_size = 2.5  # standard open
    ev = villain_fold_pct * 1.5 + (1 - villain_fold_pct) * (hero_equity * (pot_bb + 2 * open_size) - open_size)
    return round(ev, 2)


def _ev_limp(hero_equity: float, p_raise: float, lrr_bb: float,
             villain_fold_to_3b: float, pot_before: float) -> float:
    """EV of limp-reraise plan."""
    # Scenario 1: No one raises — see flop cheaply (1BB invested)
    ev_no_raise = hero_equity * pot_before  # multiway, discounted
    # Scenario 2: Villain raises, hero re-raises, villain folds
    pot_if_fold = pot_before + lrr_bb  # win dead money
    ev_raise_fold = villain_fold_to_3b * pot_if_fold
    # Scenario 3: Villain raises, hero re-raises, villain calls
    pot_if_call = pot_before + lrr_bb * 2
    ev_raise_call = (1 - villain_fold_to_3b) * (hero_equity * pot_if_call - lrr_bb)
    ev_raise = ev_raise_fold + ev_raise_call
    total_ev = p_raise * ev_raise + (1 - p_raise) * ev_no_raise
    return round(total_ev, 2)


@dataclass
class LimpReraiseAdvice:
    """Preflop limp-reraise strategy analysis."""
    hero_pos: str
    hero_hand_class: str
    table_type: str
    n_players: int

    # Decision
    action: str               # 'limp_reraise', 'open_raise', 'fold'
    limp_reraise_freq: float  # frequency to use LRR (0-1)
    open_raise_freq: float    # frequency to open-raise instead
    villain_expected_open_bb: float
    reraise_size_bb: float    # recommended LRR re-raise size

    # Probabilities
    p_villain_raises_limp: float
    villain_fold_to_reraise_pct: float

    # EV comparison
    ev_open_bb: float
    ev_limp_bb: float

    # Context
    primary_trigger: str      # what condition makes LRR best
    reasoning: str
    strategic_tips: List[str] = field(default_factory=list)


def advise_limp_reraise(
    hero_hand_class: str = 'premium',
    hero_pos: str = 'UTG',
    villain_open_freq: float = 0.30,
    villain_vpip: float = 0.40,
    table_type: str = 'passive',
    eff_stack_bb: float = 100.0,
    n_players: int = 6,
    hero_equity: float = 0.70,
    villain_fold_to_3b: float = 0.55,
) -> LimpReraiseAdvice:
    """
    Advise on preflop limp-reraise strategy.

    Args:
        hero_hand_class:      Hero's hand strength class
        hero_pos:             Hero's position ('UTG', 'UTG1', 'HJ', 'CO', 'BTN', 'SB')
        villain_open_freq:    Fraction of time villain opens after a limp (0-1)
        villain_vpip:         Villain's overall VPIP
        table_type:           'passive', 'standard', 'aggressive'
        eff_stack_bb:         Effective stack depth
        n_players:            Number of players at table
        hero_equity:          Hero's equity when stacks go in
        villain_fold_to_3b:   Villain's fold-to-3bet frequency

    Returns:
        LimpReraiseAdvice
    """
    rank = _hand_rank(hero_hand_class)
    p_raise = _villain_raise_prob(villain_open_freq, table_type, n_players)

    # Expected villain open size when they raise a limp
    villain_open_bb = round(villain_vpip * 6 + 2.5, 1)  # loose players open bigger
    villain_open_bb = min(8.0, max(3.0, villain_open_bb))

    lrr_size = _lrr_size(villain_open_bb, eff_stack_bb)
    pot_before = 1.5 + 1.0  # SB + hero's limp

    ev_open = _ev_open(rank, hero_equity, 5.0, villain_fold_to_3b * 0.5)
    ev_limp = _ev_limp(hero_equity, p_raise, lrr_size, villain_fold_to_3b, pot_before)

    # LRR conditions:
    # 1. Villain raises limps frequently
    # 2. Stack depth allows it (40-150BB)
    # 3. Hero has premium hand
    # 4. Hero is out of position (OOP loses value from IP open)
    ip_positions = {'CO', 'BTN'}
    hero_is_ip = hero_pos in ip_positions
    short_stack = eff_stack_bb < 40
    deep_stack = eff_stack_bb > 150

    lrr_is_valid = (
        rank >= 8 and            # premium/strong hand
        not short_stack and       # enough chips to LRR
        not hero_is_ip            # IP should open, not limp
    )

    # Frequency guidance
    if not lrr_is_valid:
        if short_stack:
            action = 'open_raise'
            lrr_freq = 0.0
            open_freq = 1.0
            trigger = 'Stack <40BB: just shove or open-raise'
        elif hero_is_ip:
            action = 'open_raise'
            lrr_freq = 0.0
            open_freq = 1.0
            trigger = 'In position: open-raise to maintain positional advantage'
        elif rank < 8:
            action = 'open_raise'
            lrr_freq = 0.0
            open_freq = 1.0
            trigger = 'Hand not strong enough to justify limp-trap (need premium/strong)'
        else:
            action = 'open_raise'
            lrr_freq = 0.0
            open_freq = 1.0
            trigger = 'Default: open-raise'
    elif table_type == 'passive':
        # Passive table: limps rarely get raised → open preferred regardless of hand
        lrr_freq = min(0.20, p_raise * 0.6)  # small balanced fraction only
        open_freq = 1.0 - lrr_freq
        action = 'open_raise'
        trigger = f'Passive table: only {p_raise:.0%} raise prob → open preferred'
    elif table_type == 'aggressive' and p_raise >= 0.50:
        # Aggressive table: LRR is optimal when villain will raise frequently
        action = 'limp_reraise'
        lrr_freq = 0.80
        open_freq = 0.20
        trigger = f'Aggressive table: villain raises limps {p_raise:.0%} → trap with LRR'
    elif rank >= 10:  # true premium (AA/KK)
        action = 'limp_reraise'
        lrr_freq = min(0.70, 0.40 + p_raise)
        open_freq = 1.0 - lrr_freq
        trigger = f'AA/KK: LRR {lrr_freq:.0%} to balance range and trap aggression'
    else:
        # Strong (QQ, JJ, AKs): mix
        action = 'open_raise' if ev_open > ev_limp else 'limp_reraise'
        lrr_freq = 0.30
        open_freq = 0.70
        trigger = f'Strong hand: mostly open-raise, mix LRR ({lrr_freq:.0%}) for balance'

    # Build reasoning
    if action == 'limp_reraise':
        reasoning = (
            f'{hero_hand_class} from {hero_pos}: LRR {lrr_freq:.0%} of time. '
            f'Villain opens limps {p_raise:.0%}. When raised, re-raise to {lrr_size:.0f}BB. '
            f'EV(LRR) = {ev_limp:.1f}BB vs EV(open) = {ev_open:.1f}BB.'
        )
    else:
        reasoning = (
            f'{hero_hand_class} from {hero_pos}: open-raise is preferred. '
            f'LRR freq = {lrr_freq:.0%} for balance only. '
            f'EV(open) = {ev_open:.1f}BB > EV(limp) = {ev_limp:.1f}BB.'
        )

    tips = []
    if table_type == 'passive':
        tips.append(
            'Passive table: limps rarely get raised. LRR walks through too often. '
            'Prefer open-raising to build pot reliably.'
        )
    if p_raise >= 0.50:
        tips.append(
            f'Villain raises limps {p_raise:.0%}: prime LRR territory. '
            f'Limp-reraise to {lrr_size:.0f}BB leaves SPR ~{(eff_stack_bb - lrr_size)/(lrr_size*2 + pot_before):.1f} post-flop.'
        )
    if deep_stack:
        tips.append(
            'Deep stack (>150BB): LRR creates awkward SPR. '
            'Consider open-raise to control pot size.'
        )
    if hero_is_ip:
        tips.append(
            f'{hero_pos} is in position: limping gives up positional advantage. '
            'Strong hands want to open-raise and play big pots IP.'
        )
    tips.append(
        'vs Villain reads: If villain shows "limp then raise" pattern (LRR themselves), '
        'they are trapping — give them more respect when they raise your open.'
    )

    return LimpReraiseAdvice(
        hero_pos=hero_pos,
        hero_hand_class=hero_hand_class,
        table_type=table_type,
        n_players=n_players,
        action=action,
        limp_reraise_freq=round(lrr_freq, 2),
        open_raise_freq=round(open_freq, 2),
        villain_expected_open_bb=villain_open_bb,
        reraise_size_bb=lrr_size,
        p_villain_raises_limp=p_raise,
        villain_fold_to_reraise_pct=villain_fold_to_3b,
        ev_open_bb=ev_open,
        ev_limp_bb=ev_limp,
        primary_trigger=trigger,
        reasoning=reasoning,
        strategic_tips=tips,
    )


def limp_reraise_one_liner(result: LimpReraiseAdvice) -> str:
    return (
        f'[LRR {result.hero_hand_class}@{result.hero_pos}] '
        f'{result.action.upper()} | '
        f'LRR={result.limp_reraise_freq:.0%} to {result.reraise_size_bb:.0f}BB | '
        f'p_raise={result.p_villain_raises_limp:.0%} | '
        f'EV_open={result.ev_open_bb:.1f}BB'
    )
