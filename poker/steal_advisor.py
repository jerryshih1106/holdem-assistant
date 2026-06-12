"""
Blind Steal / Resteal Advisor (steal_advisor.py)

Models the EV of stealing blinds from late position (BTN/CO/SB)
and restealing (3-betting) against steal attempts.

Usage:
    from poker.steal_advisor import analyze_steal, analyze_resteal
    steal = analyze_steal('BTN', bb_fold_pct=0.65, sb_fold_pct=0.70,
                          hand=['As', 'Td'], open_size_bb=2.5, stack_bb=100)
    resteal = analyze_resteal('BB', opener_pos='BTN', opener_pfr=0.42,
                              hand=['Kh', 'Jh'], stack_bb=100)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Position mappings ─────────────────────────────────────────────────────────

# Which positions are stealing FROM (late position)
_STEAL_POSITIONS = {'BTN', 'CO', 'SB', 'HJ'}

# Estimated baseline blind defense rates (fold to steal) by position
# These are starting points; user provides actual stats when available
_DEFAULT_BB_FOLD = 0.60   # BB folds ~60% to BTN steal
_DEFAULT_SB_FOLD = 0.75   # SB folds ~75% to steal (acts first postflop)

# Positional steal frequency multipliers (vs baseline)
_POS_STEAL_MULT = {
    'BTN': 1.00,   # reference
    'CO':  0.85,   # slightly less steal equity than BTN
    'HJ':  0.70,
    'SB':  0.90,   # only vs BB; high fold equity since BB plays OOP
}

# Hand quality buckets for steal EV estimation
_STEAL_HAND_QUALITY = {
    # (rank1_idx, rank2_idx, suited) → quality 0-4
}


@dataclass
class StealResult:
    """Blind steal analysis from late position."""
    hand: str
    hero_pos: str
    open_size_bb: float

    # Fold equity from each blind
    sb_fold_pct: float
    bb_fold_pct: float
    total_fold_equity: float   # P(both fold)

    # EV components
    ev_steal: float            # EV if all fold (win blinds)
    ev_call: float             # EV when called (postflop estimate)
    total_ev: float

    # Decision
    action: str                # 'steal', 'limp', 'fold'
    steal_ok: bool
    recommended_freq: float    # fraction of this hand type to steal

    # Hand classification
    hand_quality: str          # 'premium', 'strong', 'speculative', 'trash'
    postflop_edge: float       # estimated edge when called

    # Reasoning
    reasoning: str
    tips: List[str] = field(default_factory=list)


@dataclass
class RestealResult:
    """3-bet resteal analysis vs a steal attempt."""
    hand: str
    hero_pos: str
    opener_pos: str

    # Villain fold equity
    opener_fold_pct: float     # estimated % opener folds to 3-bet
    total_fold_equity: float

    # Sizing
    three_bet_size_bb: float
    open_size_bb: float

    # EV
    ev_resteal: float
    ev_call: float
    total_ev: float

    # Decision
    action: str                # '3bet', 'call', 'fold'
    resteal_ok: bool
    is_value: bool
    is_bluff: bool

    # Reasoning
    reasoning: str
    tips: List[str] = field(default_factory=list)


def _parse_hand(hole_cards: List[str]) -> str:
    """Convert ['As', '5s'] → 'A5s' canonical form."""
    if len(hole_cards) != 2:
        return 'XX'
    ranks = '23456789TJQKA'
    c1, c2 = hole_cards[0], hole_cards[1]
    r1, s1 = c1[0].upper(), c1[1].lower()
    r2, s2 = c2[0].upper(), c2[1].lower()
    suited = s1 == s2
    if ranks.index(r1) < ranks.index(r2):
        r1, r2 = r2, r1
    return f'{r1}{r2}{"s" if suited else "o"}'


def _hand_quality(hand_str: str) -> tuple:
    """Return (quality_label, postflop_edge) for steal analysis."""
    base = hand_str[:2]
    suited = hand_str.endswith('s')
    ranks = '23456789TJQKA'
    r1 = ranks.index(base[0]) if base[0] in ranks else 0
    r2 = ranks.index(base[1]) if base[1] in ranks else 0

    # Premium: always steal
    if base in ('AA', 'KK', 'QQ', 'JJ', 'AK'):
        return 'premium', 0.65
    # Strong
    if base in ('TT', '99', '88', 'AQ', 'AJ', 'KQ') or (base == 'AT' and suited):
        return 'strong', 0.58
    # Speculative: connected, suited, reasonable ranks
    if suited and r1 >= 5 and r2 >= 3:  # 54s+
        return 'speculative', 0.52
    if suited and base[0] in 'AK':
        return 'speculative', 0.54
    if r1 + r2 >= 16:  # any two cards summing to J-high+
        return 'speculative', 0.51
    # Trash
    return 'trash', 0.46


def analyze_steal(
    hero_pos: str,
    bb_fold_pct: float = _DEFAULT_BB_FOLD,
    sb_fold_pct: float = _DEFAULT_SB_FOLD,
    hand: Optional[List[str]] = None,
    open_size_bb: float = 2.5,
    stack_bb: float = 100.0,
    antes_bb: float = 0.0,
) -> StealResult:
    """
    Analyze the EV and recommendation for a blind steal attempt.

    Args:
        hero_pos:      Hero's position ('BTN', 'CO', 'HJ', 'SB')
        bb_fold_pct:   Fraction BB folds to steal (0-1)
        sb_fold_pct:   Fraction SB folds to steal (0-1, 0 if hero is SB)
        hand:          Hero's hole cards (optional, for hand-specific advice)
        open_size_bb:  Open raise size in BBs
        stack_bb:      Effective stack in BBs
        antes_bb:      Total antes in pot (adds dead money)

    Returns:
        StealResult
    """
    hand_str = _parse_hand(hand) if hand else 'XX'
    quality, postflop_edge = _hand_quality(hand_str) if hand else ('speculative', 0.52)

    pos_mult = _POS_STEAL_MULT.get(hero_pos.upper(), 0.80)

    # From SB, only BB can defend
    if hero_pos.upper() == 'SB':
        total_fold_eq = bb_fold_pct
        sb_fold_eff = 1.0   # SB has already "folded" by being the hero
    else:
        total_fold_eq = sb_fold_pct * bb_fold_pct

    # ── Dead money and pot ──────────────────────────────────────────────
    blinds_in_pot = 1.5 + antes_bb   # SB(0.5) + BB(1.0)
    # EV if everyone folds: hero wins the dead blinds (net gain = blinds_in_pot)
    ev_steal = blinds_in_pot   # net when all fold

    # EV when called: equity * (others' money in pot) - (1-equity) * hero's call cost
    # called_pot = blinds + hero_open + opponent_call; hero invested open_size_bb
    called_pot = blinds_in_pot + open_size_bb * 2
    opponents_money = called_pot - open_size_bb   # what hero wins if they win
    ev_if_called = postflop_edge * opponents_money - (1 - postflop_edge) * open_size_bb

    # Total EV = weighted average of outcomes
    total_ev = total_fold_eq * ev_steal + (1 - total_fold_eq) * ev_if_called

    # ── Decision ─────────────────────────────────────────────────────────
    steal_ok = total_ev > 0 and hero_pos.upper() in _STEAL_POSITIONS

    # Recommended steal frequency by hand quality
    if quality == 'premium':
        freq = 1.0
        action = 'steal'
    elif quality == 'strong':
        freq = 0.95
        action = 'steal'
    elif quality == 'speculative':
        freq = 0.65 * pos_mult if total_fold_eq > 0.40 else 0.40 * pos_mult
        action = 'steal' if total_ev > 0 else 'fold'
    else:  # trash
        freq = 0.25 * pos_mult if total_fold_eq > 0.60 else 0.0
        action = 'steal' if (total_fold_eq > 0.65 and hero_pos.upper() == 'BTN') else 'fold'

    freq = min(1.0, max(0.0, freq))

    # ── Tips ─────────────────────────────────────────────────────────────
    tips = []
    if bb_fold_pct > 0.70:
        tips.append(f'BB folds {bb_fold_pct:.0%} — widen steal range significantly.')
    if bb_fold_pct < 0.45:
        tips.append(f'BB defends wide ({1-bb_fold_pct:.0%} VPIP vs steal) — tighten range.')
    if hero_pos.upper() == 'BTN' and total_fold_eq > 0.55:
        tips.append('BTN steal is highly profitable — open 45-55% of hands here.')
    if quality == 'trash' and total_fold_eq < 0.60:
        tips.append('Trash hand with low fold equity — avoid; only play quality hands.')
    if antes_bb > 0:
        tips.append(f'Antes ({antes_bb:.1f}BB) increase steal EV — expand range further.')

    sb_fold_display = sb_fold_pct if hero_pos.upper() != 'SB' else 'n/a'
    reasoning = (
        f'{hand_str} steal from {hero_pos}: '
        f'fold_eq={total_fold_eq:.0%} '
        f'(SB={sb_fold_display if isinstance(sb_fold_display, str) else f"{sb_fold_display:.0%}"}, '
        f'BB={bb_fold_pct:.0%}). '
        f'total_ev={total_ev:+.2f}BB. Action: {action.upper()}.'
    )

    return StealResult(
        hand=hand_str,
        hero_pos=hero_pos,
        open_size_bb=open_size_bb,
        sb_fold_pct=sb_fold_pct,
        bb_fold_pct=bb_fold_pct,
        total_fold_equity=total_fold_eq,
        ev_steal=round(ev_steal, 2),
        ev_call=round(ev_if_called, 2),
        total_ev=round(total_ev, 2),
        action=action,
        steal_ok=steal_ok,
        recommended_freq=round(freq, 2),
        hand_quality=quality,
        postflop_edge=postflop_edge,
        reasoning=reasoning,
        tips=tips,
    )


def analyze_resteal(
    hero_pos: str,
    opener_pos: str,
    opener_pfr: float = 0.35,
    hand: Optional[List[str]] = None,
    stack_bb: float = 100.0,
    open_size_bb: float = 2.5,
    sb_bb: float = 0.5,
    bb_bb: float = 1.0,
) -> RestealResult:
    """
    Analyze a resteal (3-bet) against a steal from late position.

    Args:
        hero_pos:      Hero's position ('BB', 'SB')
        opener_pos:    Position of the steal attempt ('BTN', 'CO', etc.)
        opener_pfr:    Opener's PFR (higher PFR → steals wider → folds more to 3-bet)
        hand:          Hero's hole cards
        stack_bb:      Effective stack
        open_size_bb:  Size of open raise
        sb_bb:         SB amount posted
        bb_bb:         BB amount posted

    Returns:
        RestealResult
    """
    hand_str = _parse_hand(hand) if hand else 'XX'
    quality, postflop_edge = _hand_quality(hand_str) if hand else ('speculative', 0.52)

    # ── Opener fold to 3-bet estimate ────────────────────────────────────
    # Late position openers who steal wide fold a lot to 3-bets
    # Base fold rate adjusted by PFR (high PFR → stealing wide → folds more)
    base_fold = {'BTN': 0.55, 'CO': 0.48, 'HJ': 0.42, 'SB': 0.58}.get(
        opener_pos.upper(), 0.45)
    pfr_adj = (opener_pfr - 0.25) * 0.40   # +0.04 per 10% above 25% PFR
    opener_fold = min(0.85, max(0.25, base_fold + pfr_adj))

    total_fold_eq = opener_fold

    # ── 3-bet sizing ──────────────────────────────────────────────────────
    # Standard resteal: 3x-4x the open from the blinds
    three_bet_size = 3.0 * open_size_bb + (sb_bb + bb_bb) * 0.5
    three_bet_size = min(three_bet_size, stack_bb * 0.30)

    # ── EV calculation ────────────────────────────────────────────────────
    dead_money = open_size_bb + sb_bb + bb_bb
    ev_if_fold = dead_money   # win the dead money
    pot_if_call = dead_money + three_bet_size
    ev_if_call = postflop_edge * pot_if_call - (1 - postflop_edge) * three_bet_size

    ev_resteal = total_fold_eq * ev_if_fold + (1 - total_fold_eq) * ev_if_call
    ev_call = postflop_edge * (dead_money + open_size_bb) - (1 - postflop_edge) * open_size_bb

    # ── Decision ─────────────────────────────────────────────────────────
    is_value = quality in ('premium', 'strong')
    is_bluff = quality == 'speculative' and opener_fold > 0.50
    resteal_ok = ev_resteal > ev_call

    if quality == 'premium':
        action = '3bet'
    elif is_bluff and opener_fold > 0.45:
        action = '3bet'
    elif quality == 'strong':
        action = '3bet'
    elif ev_call > 0 and quality != 'trash':
        action = 'call'
    else:
        action = 'fold'

    # ── Tips ─────────────────────────────────────────────────────────────
    tips = []
    if opener_pfr > 0.35 and quality == 'speculative':
        tips.append(f'{opener_pos} opens wide ({opener_pfr:.0%} PFR) — '
                    f'resteal range expands. Add suited connectors and Axs.')
    if opener_fold < 0.40:
        tips.append(f'{opener_pos} folds only {opener_fold:.0%} to 3-bets — '
                    f'only resteal with value hands.')
    if hero_pos.upper() == 'BB' and opener_pos.upper() == 'BTN':
        tips.append('BTN vs BB: classic steal-resteal dynamic. '
                    'Resteal polar range: premiums + bluffs.')
    if quality == 'speculative' and not is_bluff:
        tips.append('Marginal hand: consider calling in position instead of 3-betting OOP.')

    reasoning = (
        f'{hand_str} resteal from {hero_pos} vs {opener_pos} ({opener_pfr:.0%} PFR). '
        f'opener_fold={opener_fold:.0%}  3bet_size={three_bet_size:.1f}BB. '
        f'EV(3bet)={ev_resteal:+.2f} vs EV(call)={ev_call:+.2f}. '
        f'Action: {action.upper()}.'
    )

    return RestealResult(
        hand=hand_str,
        hero_pos=hero_pos,
        opener_pos=opener_pos,
        opener_fold_pct=round(opener_fold, 2),
        total_fold_equity=total_fold_eq,
        three_bet_size_bb=round(three_bet_size, 1),
        open_size_bb=open_size_bb,
        ev_resteal=round(ev_resteal, 2),
        ev_call=round(ev_call, 2),
        total_ev=round(ev_resteal, 2),
        action=action,
        resteal_ok=resteal_ok,
        is_value=is_value,
        is_bluff=is_bluff,
        reasoning=reasoning,
        tips=tips,
    )


def steal_one_liner(result: StealResult) -> str:
    """Single-line overlay summary."""
    return (f'Steal {result.hero_pos}: {result.action.upper()} '
            f'fold_eq={result.total_fold_equity:.0%} '
            f'EV={result.total_ev:+.2f}BB '
            f'freq={result.recommended_freq:.0%}')


def resteal_one_liner(result: RestealResult) -> str:
    """Single-line overlay summary."""
    return (f'Resteal {result.hero_pos} vs {result.opener_pos}: '
            f'{result.action.upper()} {result.three_bet_size_bb:.1f}BB | '
            f'fold_eq={result.total_fold_equity:.0%} '
            f'EV={result.ev_resteal:+.2f}BB')
