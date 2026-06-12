"""
BB/SB vs Limper Advisor (bb_vs_limper.py)

When one or more players limp (call the BB instead of raising), hero in BB
or SB has a unique decision:

BB options:
  1. CHECK  — free entry, cheapest way to see a flop
  2. RAISE  — ISO raise to isolate vs the weakest limper(s)
  3. (No fold — already paid)

SB options:
  1. COMPLETE  — cheapest entry (pays 0.5BB more)
  2. FOLD      — give up the half BB invested
  3. RAISE     — ISO raise from SB (positional disadvantage, so less common)

Why ISO-raise from BB is so profitable:
  - Limpers have weak ranges (VPIP high, PFR low, often weak passives)
  - ISO creates a larger pot that hero dominates with a stronger range
  - Hero gets post-flop position... wait, no — BB is OOP
  - But BB's range is far stronger than limper's range → range advantage
  - Typical ISO size: 3BB + 1BB per limper (standard)
  - Looser/fishier limpers: go even bigger (4-5BB + 1/limper)

Why NOT to always ISO raise from BB:
  - Hero is OOP post-flop
  - With speculative hands (suited connectors, small pairs), calling is
    often better than ISO-raising (implied odds in multiway pot)
  - Too many ISO raises → limpers start squeezing back

Optimal BB strategy vs limpers:
  - Strong hands (AA-JJ, AK, AQ): always ISO raise, size up vs fish
  - Medium hands (TT-88, AJ, KQ, AT): ISO raise typically
  - Speculative IP draw hands (78s, 67s, small pairs): check more
  - Trash (72o, 83o, etc.): check and hope for miracle flop
  - Suited connectors: mixed — check some, raise others for balance

SB vs limp decision:
  - SB is OOP against BB AND limpers → rarely profitable to complete
  - SB should fold most of their non-raising range
  - SB should raise or fold, almost never just complete
  - Exception: complete with strong drawing hands in multiway implied odds spot

Usage:
    from poker.bb_vs_limper import advise_bb_vs_limper, BBLimperAdvice
    result = advise_bb_vs_limper(
        hero_pos='BB',
        hero_hand_class='medium_pair',
        hero_equity_vs_limp=0.55,
        n_limpers=2,
        villain_vpip=0.45,
        eff_stack_bb=100.0,
    )
    print(result.action, result.iso_size_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Hand strength rank for decision making
def _hand_rank(hand_class: str) -> int:
    return {
        'premium': 10, 'strong': 8, 'medium_pair': 6, 'medium': 5,
        'speculative': 3, 'marginal': 2, 'trash': 0,
        # Also handle generic classes
        'air': 0, 'draw': 3, 'bottom_pair': 2, 'middle_pair': 4,
        'top_pair': 6, 'tptk': 7, 'overpair': 7, 'two_pair': 8, 'set': 9,
    }.get(hand_class.lower(), 4)


def _iso_size(n_limpers: int, villain_vpip: float, hero_pos: str) -> float:
    """Recommended ISO raise size in BB."""
    # Base: 3BB + 1BB per limper
    base = 3.0 + n_limpers * 1.0
    # Loose limpers: raise bigger
    if villain_vpip >= 0.45:
        base += 1.5
    elif villain_vpip >= 0.35:
        base += 0.5
    # SB: raise bigger (OOP)
    if hero_pos == 'SB':
        base += 0.5
    return round(base, 1)


def _check_fold_limper_pct(n_limpers: int, villain_vpip: float) -> float:
    """Estimated fold-to-ISO frequency from limpers."""
    # Loose limpers fold less to ISO
    base = 0.55
    if villain_vpip >= 0.50:
        base -= 0.15
    elif villain_vpip >= 0.40:
        base -= 0.08
    # More limpers → lower fold rate (at least one may call)
    multi_adj = -(n_limpers - 1) * 0.08
    return round(max(0.20, min(0.75, base + multi_adj)), 3)


def _iso_ev(iso_bb: float, fold_pct: float, hero_equity: float,
            pot_before: float) -> float:
    """EV of ISO raise."""
    call_pct = 1.0 - fold_pct
    pot_if_fold = pot_before  # win pot before
    pot_if_call = pot_before + iso_bb * 2  # pot grows
    ev_fold = fold_pct * pot_if_fold
    ev_call = call_pct * (hero_equity * pot_if_call - iso_bb)
    return round(ev_fold + ev_call, 2)


def _check_ev(hero_equity: float, pot_bb: float) -> float:
    """EV of checking (seeing flop for free)."""
    return round(hero_equity * pot_bb, 2)


def _decision(
    hero_pos: str,
    hand_rank: int,
    iso_ev: float,
    check_ev: float,
    n_limpers: int,
    villain_vpip: float,
    is_speculative: bool,
) -> tuple:
    """Return (action, reasoning)."""
    is_bb = hero_pos == 'BB'

    # SB: almost always raise or fold (never complete)
    if hero_pos == 'SB':
        if hand_rank >= 8:  # strong hands
            return ('raise', f'SB: ISO-raise strong hand (rank={hand_rank}). '
                    f'OOP postflop — need strong range advantage.')
        elif hand_rank >= 5 and not is_speculative:
            return ('raise', f'SB: ISO-raise medium hand to deny cheap entry. '
                    f'SB should not complete (OOP all streets).')
        else:
            return ('fold', f'SB: fold weak/speculative hands. '
                    f'Completing from SB is almost always wrong — OOP vs everyone.')

    # BB: can check for free
    if hand_rank >= 8:  # premium/strong hands
        return ('raise', f'BB: ISO-raise strong hand (rank={hand_rank}) to {iso_ev:.1f}BB EV. '
                f'Build a big pot with range advantage.')

    if hand_rank >= 6:  # medium pairs, AJ+, KQ
        if iso_ev > check_ev + 2.0:
            return ('raise', f'BB: ISO-raise medium hand (EV={iso_ev:.1f} > check={check_ev:.1f}). '
                    f'Exploit limpers\' weak ranges with aggression.')
        return ('check', f'BB: check with medium hand. '
                f'Implied odds in multiway pot acceptable. ISO EV marginal.')

    if is_speculative and n_limpers >= 2:
        return ('check', f'BB: check speculative hand in {n_limpers}-way pot. '
                f'Multiway implied odds > ISO value. Hope for strong flop.')

    if hand_rank <= 2:
        return ('check', f'BB: check trash/marginal hand for free. '
                f'No reason to build a pot with dominated range.')

    # Default: EV comparison
    if iso_ev > check_ev + 1.5:
        return ('raise', f'BB: ISO-raise (EV={iso_ev:.1f}BB > check={check_ev:.1f}BB). '
                f'Exploit loose limpers with strong opening range.')
    return ('check', f'BB: check for free (EV={check_ev:.1f}BB). '
            f'Multiway pot preferred with this hand class.')


@dataclass
class BBLimperAdvice:
    """BB/SB decision when facing one or more limpers."""
    hero_pos: str
    n_limpers: int
    villain_vpip: float
    eff_stack_bb: float

    # Decision
    action: str           # 'raise', 'check', 'fold' (SB only)
    iso_size_bb: float    # 0 if checking/folding
    iso_ev_bb: float      # EV of ISO raise
    check_ev_bb: float    # EV of checking

    # Math
    fold_to_iso_pct: float  # estimated villain fold % to ISO
    pot_before_bb: float

    # Notes
    action_reasoning: str
    strategic_tips: List[str] = field(default_factory=list)


def advise_bb_vs_limper(
    hero_pos: str = 'BB',
    hero_hand_class: str = 'medium',
    hero_equity_vs_limp: float = 0.55,
    n_limpers: int = 1,
    villain_vpip: float = 0.40,
    eff_stack_bb: float = 100.0,
    is_speculative: bool = False,
) -> BBLimperAdvice:
    """
    BB or SB decision when facing limpers.

    Args:
        hero_pos:              'BB' or 'SB'
        hero_hand_class:       Hand classification
        hero_equity_vs_limp:   Hero's equity vs limper range (0-1)
        n_limpers:             Number of limpers
        villain_vpip:          Average VPIP of limpers
        eff_stack_bb:          Effective stack
        is_speculative:        True for small pairs, suited connectors

    Returns:
        BBLimperAdvice
    """
    rank = _hand_rank(hero_hand_class)
    iso_bb = _iso_size(n_limpers, villain_vpip, hero_pos)
    fold_pct = _check_fold_limper_pct(n_limpers, villain_vpip)

    # Pot before hero acts
    pot_before = 1.5 + n_limpers  # SB + BB + n_limpers × 1BB

    iso_ev = _iso_ev(iso_bb, fold_pct, hero_equity_vs_limp, pot_before)
    check_ev = _check_ev(hero_equity_vs_limp, pot_before)

    action, reasoning = _decision(
        hero_pos, rank, iso_ev, check_ev, n_limpers, villain_vpip, is_speculative,
    )

    actual_iso = iso_bb if action == 'raise' else 0.0

    tips = []
    if hero_pos == 'BB' and action == 'raise':
        tips.append(
            f'ISO to {iso_bb:.0f}BB (3BB + {n_limpers}BB limper): '
            f'expected fold {fold_pct:.0%} of time. '
            f'EV = {iso_ev:.1f}BB vs check {check_ev:.1f}BB.'
        )
    if hero_pos == 'SB':
        tips.append(
            'SB vs limpers: raise or fold — NEVER complete. '
            'Completing from SB is OOP vs all players and lacks initiative.'
        )
    if villain_vpip >= 0.45:
        tips.append(
            f'Loose limper (VPIP={villain_vpip:.0%}): raise bigger to extract value. '
            f'They\'ll call with many dominated hands.'
        )
    if n_limpers >= 3:
        tips.append(
            f'{n_limpers} limpers = large dead money. '
            f'ISO is very profitable with any decent hand. '
            f'But lower fold rate → needs stronger hand to ISO-raise.'
        )

    return BBLimperAdvice(
        hero_pos=hero_pos,
        n_limpers=n_limpers,
        villain_vpip=villain_vpip,
        eff_stack_bb=round(eff_stack_bb, 1),
        action=action,
        iso_size_bb=actual_iso,
        iso_ev_bb=iso_ev,
        check_ev_bb=check_ev,
        fold_to_iso_pct=fold_pct,
        pot_before_bb=pot_before,
        action_reasoning=reasoning,
        strategic_tips=tips,
    )


def bb_limper_one_liner(result: BBLimperAdvice) -> str:
    return (
        f'[BBL {result.hero_pos} x{result.n_limpers}L] '
        f'{result.action.upper()} '
        f'(ISO={result.iso_size_bb:.0f}BB|EV={result.iso_ev_bb:.1f} '
        f'chk={result.check_ev_bb:.1f})'
    )
