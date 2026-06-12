"""
BTN Play Optimizer (btn_play_optimizer.py)

The BUTTON is the most profitable seat in poker. The BTN player:
  - Acts LAST postflop on every street (maximum information advantage)
  - Can open wider than any other position
  - Has the highest Win Rate at 100BB stacks among all positions
  - Benefits most from positional c-bet frequency advantages

This module consolidates BTN-specific strategy into one actionable guide:

1. OPEN-RAISE RANGE:
   Standard BTN open = 42-46% of hands.
   Adjustments by blind profiles:
     - SB tight (VPIP<20%) + BB tight → open wider (50%+)
     - SB/BB both aggressive (3-bet freq high) → tighten (38-42%)
     - BB fish (VPIP>50%) → open wider, plan to c-bet vs call (not vs CR)
     - SB limp-call → open a bit wider, expect to c-bet HU in position

2. SIZING ADJUSTMENTS:
   Standard open: 2.5BB (BTN)
   Vs aggressive blinds: 2.2BB (smaller to risk less vs 3-bet)
   Vs passive blinds: 3.0BB (larger to deny equity)
   BB fish: 2.5-3.0BB (call off wider at 3BB)

3. VS 3-BET FROM BLINDS:
   From SB: SB 3-bet range is wide; hero can cold-call QQ/AK/KQ more
   From BB: BB 3-bet range is strongest; hero needs top 15% to continue
   4-bet frequency from BTN: ~9-11% of starting hands (QQ+, AKs, A5s-A3s blockers)

4. POSTFLOP C-BET FREQUENCIES (BTN IP):
   Dry board (852r): cbet 70-75% (high FE, unchallenged ranges)
   Medium board (J74r): cbet 60-65%
   Wet board (TJ9s): cbet 45-55% (draws hit villain's range too)
   Paired board (AA2): cbet 85% (range advantage, villain rarely has Ax)
   3-bet pot dry: cbet 50-60% (smaller range)
   3-bet pot wet: cbet 35-45%

5. MULTIWAY POTS (BTN vs 2+ callers):
   Tighten c-bet to 35-40% (only strong hands/top of range)
   Avoid bluffs in multiway (too many opponents)
   Value bet sizes: 40-50% pot (draw-heavy boards reward smaller bets)

6. EV ESTIMATION:
   Open from BTN: expected EV = +0.45 BB/hand (vs fold from blinds ~45% of time)
   C-bet success: avg 55% fold equity × pot stolen = +0.22 BB/hand from cbets
   Total positional edge: approximately +0.5-0.8 BB/100 over random position

Usage:
    from poker.btn_play_optimizer import advise_btn_play
    from poker.btn_play_optimizer import BtnPlayAdvice, btn_play_one_liner

    result = advise_btn_play(
        street='preflop',
        hero_hand_class='top_pair',
        board_type='medium',
        sb_vpip=0.18,
        sb_3bet_pct=0.08,
        bb_vpip=0.35,
        bb_3bet_pct=0.06,
        hero_stack_bb=100.0,
        pot_bb=0.0,
        n_callers=0,
        facing_3bet=False,
    )
    print(result.action, result.recommended_sizing_bb)
"""

from dataclasses import dataclass, field
from typing import List


# ── preflop open frequency baseline ──────────────────────────────────────────

_BASE_BTN_OPEN_PCT = 0.44   # 44% standard BTN open

def _btn_open_frequency(
    sb_vpip: float,
    sb_3bet_pct: float,
    bb_vpip: float,
    bb_3bet_pct: float,
) -> float:
    freq = _BASE_BTN_OPEN_PCT
    # Tight blinds → open wider
    if sb_vpip < 0.18 and bb_vpip < 0.22:
        freq += 0.06
    elif sb_vpip < 0.22 and bb_vpip < 0.28:
        freq += 0.03
    # Aggressive blinds → tighten
    if sb_3bet_pct > 0.12 or bb_3bet_pct > 0.10:
        freq -= 0.05
    elif sb_3bet_pct > 0.09 or bb_3bet_pct > 0.08:
        freq -= 0.02
    # Fish in BB → widen (value hands crush)
    if bb_vpip > 0.50:
        freq += 0.04
    return round(min(max(freq, 0.35), 0.58), 3)


# ── open-raise sizing ─────────────────────────────────────────────────────────

def _btn_open_sizing(
    sb_vpip: float,
    sb_3bet_pct: float,
    bb_vpip: float,
    bb_3bet_pct: float,
) -> float:
    # Baseline
    sizing = 2.5
    # Tight/passive blinds: can charge more
    if sb_vpip < 0.20 and bb_vpip < 0.25:
        sizing += 0.3
    # Aggressive 3-betters: go smaller to risk less
    if sb_3bet_pct > 0.12 or bb_3bet_pct > 0.10:
        sizing -= 0.3
    # Fish in BB: go a bit larger (they call off wide)
    if bb_vpip > 0.50:
        sizing += 0.3
    return round(sizing, 1)


# ── postflop c-bet frequency (BTN IP) ────────────────────────────────────────

_CBET_FREQ = {
    # (board_type, pot_type, n_opponents) → freq
    ('dry',    'single_raised', 1): 0.72,
    ('dry',    'single_raised', 2): 0.42,
    ('dry',    '3bet',          1): 0.58,
    ('medium', 'single_raised', 1): 0.63,
    ('medium', 'single_raised', 2): 0.37,
    ('medium', '3bet',          1): 0.48,
    ('wet',    'single_raised', 1): 0.50,
    ('wet',    'single_raised', 2): 0.32,
    ('wet',    '3bet',          1): 0.38,
    ('paired', 'single_raised', 1): 0.82,
    ('paired', 'single_raised', 2): 0.50,
    ('paired', '3bet',          1): 0.65,
}

def _btn_cbet_freq(
    board_type: str,
    pot_type: str,
    n_opponents: int,
) -> float:
    n = min(n_opponents, 2)
    bt = board_type if board_type in ('dry', 'medium', 'wet', 'paired') else 'medium'
    pt = pot_type if pot_type in ('single_raised', '3bet') else 'single_raised'
    key = (bt, pt, n)
    return _CBET_FREQ.get(key, 0.55)


# ── c-bet sizing ──────────────────────────────────────────────────────────────

def _btn_cbet_size(
    board_type: str,
    pot_type: str,
    hero_hand_cat: str,
    n_opponents: int,
) -> float:
    """Return recommended c-bet size as fraction of pot."""
    base = {'dry': 0.40, 'medium': 0.50, 'wet': 0.60, 'paired': 0.35}.get(board_type, 0.50)
    if pot_type == '3bet':
        base *= 0.85
    if n_opponents >= 2:
        base *= 0.85
    if hero_hand_cat in ('premium', 'overpair'):
        base = min(base * 1.1, 0.75)
    return round(base, 2)


# ── vs 3-bet from blinds ──────────────────────────────────────────────────────

def _vs_3bet_advice(
    hero_hand_class: str,
    four_bet_ev: float,
    call_ev: float,
    fold_ev: float,
) -> tuple:
    """Returns (action, reasoning)."""
    if four_bet_ev >= max(call_ev, fold_ev) + 0.05:
        return ('4bet', f'4-bet is best EV ({four_bet_ev:.1f}BB)')
    if call_ev >= fold_ev + 0.20:
        return ('cold_call', f'Cold-call IP EV ({call_ev:.1f}BB) > fold ({fold_ev:.1f}BB)')
    return ('fold', f'Fold vs 3-bet (EV: 4b={four_bet_ev:.1f} call={call_ev:.1f} fold={fold_ev:.1f})')


# ── EV estimations ────────────────────────────────────────────────────────────

def _open_ev(
    open_freq: float,
    open_sizing_bb: float,
    sb_vpip: float,
    bb_vpip: float,
    sb_3bet_pct: float,
    bb_3bet_pct: float,
) -> float:
    """Estimate EV of BTN open (simplified fold equity model)."""
    fold_both = (1 - sb_vpip * 0.5) * (1 - bb_vpip * 0.6)
    steal_ev = fold_both * 1.5   # win 1.5BB in blinds
    continue_pct = 1 - fold_both
    threbet_pct = (sb_3bet_pct + bb_3bet_pct) / 2 * continue_pct
    # When facing 3-bet: fold = -open_sizing, call = near 0 on average
    threbet_ev = threbet_pct * (-open_sizing_bb * 0.7)
    call_ev = (continue_pct - threbet_pct) * 0.15
    return round(steal_ev + threbet_ev + call_ev, 2)


def _cbet_ev(
    cbet_freq: float,
    cbet_size_pct: float,
    pot_bb: float,
    fold_equity: float,
) -> float:
    """Estimate EV of c-bet decision (when hero decides to bet)."""
    fold_profit = fold_equity * pot_bb
    call_loss = (1 - fold_equity) * cbet_size_pct * pot_bb * 0.5
    return round(fold_profit - call_loss, 2)


# ── hand category normalization ───────────────────────────────────────────────

def _hand_cat(hand_class: str) -> str:
    return {
        'air': 'air', 'trash': 'air', 'bottom_pair': 'air', 'marginal': 'air',
        'middle_pair': 'middle_pair', 'draw': 'draw',
        'top_pair': 'top_pair', 'medium': 'top_pair', 'tptk': 'top_pair',
        'overpair': 'overpair', 'two_pair': 'overpair', 'strong': 'overpair',
        'set': 'premium', 'straight': 'premium', 'flush': 'premium',
        'premium': 'premium', 'full_house': 'premium', 'nuts': 'premium',
    }.get(hand_class.lower(), 'top_pair')


# ── preflop 4-bet EV from BTN ─────────────────────────────────────────────────

def _btn_4bet_ev(
    hero_hand_cat: str,
    threbet_bb: float,
    hero_stack_bb: float,
    sb_3bet_pct: float,
    bb_3bet_pct: float,
) -> float:
    """Rough EV of 4-betting from BTN."""
    fourbet_size = threbet_bb * 2.3
    fold_to_4b_est = 0.50 if (sb_3bet_pct + bb_3bet_pct) / 2 < 0.08 else 0.40
    equity_vs_call = {'premium': 0.68, 'overpair': 0.58, 'top_pair': 0.50, 'draw': 0.45, 'air': 0.38}.get(hero_hand_cat, 0.50)
    pot_if_call = fourbet_size * 2 + 1.5
    fold_ev = fold_to_4b_est * threbet_bb * 0.5
    call_ev = (1 - fold_to_4b_est) * (equity_vs_call * pot_if_call - fourbet_size)
    return round(fold_ev + call_ev, 2)


def _btn_call_3bet_ev(
    hero_hand_cat: str,
    threbet_bb: float,
    pot_bb: float,
    hero_stack_bb: float,
) -> float:
    """Rough EV of cold-calling 3-bet from BTN (IP)."""
    implied_mult = {'premium': 1.5, 'overpair': 1.2, 'top_pair': 1.0, 'draw': 1.3, 'middle_pair': 0.8, 'air': 0.6}.get(hero_hand_cat, 1.0)
    equity_postflop = {'premium': 0.65, 'overpair': 0.60, 'top_pair': 0.56, 'draw': 0.50, 'middle_pair': 0.48, 'air': 0.40}.get(hero_hand_cat, 0.52)
    pot_3b = threbet_bb * 2 + 0.5
    realize_rate = 0.85 if hero_hand_cat in ('premium', 'overpair') else 0.70
    ev = (equity_postflop * pot_3b * realize_rate * implied_mult) - threbet_bb
    return round(ev, 2)


@dataclass
class BtnPlayAdvice:
    """Comprehensive BTN strategy advice."""
    street: str
    hero_hand_class: str
    board_type: str
    sb_vpip: float
    sb_3bet_pct: float
    bb_vpip: float
    bb_3bet_pct: float
    hero_stack_bb: float
    pot_bb: float
    n_callers: int
    facing_3bet: bool

    # Preflop outputs
    recommended_open_freq: float          # BTN open frequency recommendation
    recommended_sizing_bb: float          # recommended open/cbet size
    open_ev_estimate: float               # EV of opening from BTN

    # Postflop outputs
    cbet_frequency: float                 # recommended c-bet frequency this spot
    cbet_size_pct: float                  # c-bet size as fraction of pot
    cbet_size_bb: float                   # c-bet size in BB
    cbet_ev_estimate: float               # EV of c-bet

    # vs 3-bet
    vs_3bet_action: str                   # 'fold', 'cold_call', '4bet'
    vs_3bet_reasoning: str
    fourbet_ev: float
    call_3bet_ev: float

    action: str                           # main recommendation
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_btn_play(
    street: str = 'preflop',
    hero_hand_class: str = 'top_pair',
    board_type: str = 'medium',
    sb_vpip: float = 0.22,
    sb_3bet_pct: float = 0.07,
    bb_vpip: float = 0.30,
    bb_3bet_pct: float = 0.06,
    hero_stack_bb: float = 100.0,
    pot_bb: float = 0.0,
    n_callers: int = 0,
    facing_3bet: bool = False,
    threbet_bb: float = 9.0,
    pot_type: str = 'single_raised',
    fold_equity: float = 0.52,
) -> BtnPlayAdvice:
    """
    Generate comprehensive BTN-specific strategy advice.

    Args:
        street:           'preflop', 'flop', 'turn', 'river'
        hero_hand_class:  Hero's hand strength
        board_type:       'dry', 'medium', 'wet', 'paired'
        sb_vpip:          SB's VPIP (call/raise from SB)
        sb_3bet_pct:      SB's 3-bet frequency
        bb_vpip:          BB's VPIP
        bb_3bet_pct:      BB's 3-bet frequency
        hero_stack_bb:    Hero's stack in BB
        pot_bb:           Current pot (0 for preflop)
        n_callers:        Number of callers before action (multiway)
        facing_3bet:      Is hero facing a 3-bet preflop?
        threbet_bb:       Size of the 3-bet in BB (if facing_3bet)
        pot_type:         'single_raised' or '3bet'
        fold_equity:      Estimated fold equity for c-bet

    Returns:
        BtnPlayAdvice
    """
    cat = _hand_cat(hero_hand_class)
    open_freq = _btn_open_frequency(sb_vpip, sb_3bet_pct, bb_vpip, bb_3bet_pct)
    open_sizing = _btn_open_sizing(sb_vpip, sb_3bet_pct, bb_vpip, bb_3bet_pct)
    open_ev = _open_ev(open_freq, open_sizing, sb_vpip, bb_vpip, sb_3bet_pct, bb_3bet_pct)

    cbet_freq = _btn_cbet_freq(board_type, pot_type, max(1, n_callers + 1))
    cbet_size_pct = _btn_cbet_size(board_type, pot_type, cat, max(1, n_callers + 1))
    cbet_size_bb = round(pot_bb * cbet_size_pct, 1) if pot_bb > 0 else 0.0
    cbet_ev = _cbet_ev(cbet_freq, cbet_size_pct, pot_bb, fold_equity) if pot_bb > 0 else 0.0

    fourbet_ev = _btn_4bet_ev(cat, threbet_bb, hero_stack_bb, sb_3bet_pct, bb_3bet_pct)
    call_ev = _btn_call_3bet_ev(cat, threbet_bb, pot_bb, hero_stack_bb)
    fold_ev = -threbet_bb * 0.0   # fold = no loss beyond original open cost
    vs_3bet_action, vs_3bet_reasoning = _vs_3bet_advice(cat, fourbet_ev, call_ev, 0.0)

    # Determine main action
    if street == 'preflop':
        if facing_3bet:
            action = vs_3bet_action
            reasoning = (
                f'BTN vs 3-bet ({threbet_bb:.1f}BB): '
                f'4bet_ev={fourbet_ev:.1f}BB call_ev={call_ev:.1f}BB. '
                f'Recommended: {action}. {vs_3bet_reasoning}.'
            )
        else:
            action = 'open_raise'
            reasoning = (
                f'BTN open {open_freq:.0%} of hands. '
                f'Sizing={open_sizing:.1f}BB. '
                f'Open EV estimate={open_ev:.2f}BB. '
                f'vs SB(vpip={sb_vpip:.0%} 3b={sb_3bet_pct:.0%}) '
                f'BB(vpip={bb_vpip:.0%} 3b={bb_3bet_pct:.0%}).'
            )
    else:
        # Postflop: bet or check based on cbet freq and hand strength
        if cbet_freq >= 0.60 or cat in ('premium', 'overpair'):
            action = 'cbet'
        elif cbet_freq >= 0.40:
            action = 'cbet_mixed'
        else:
            action = 'check'
        reasoning = (
            f'BTN IP {street}: {board_type} board. '
            f'cbet_freq={cbet_freq:.0%} size={cbet_size_pct:.0%}pot ({cbet_size_bb:.1f}BB). '
            f'Fold_equity={fold_equity:.0%} cbet_ev={cbet_ev:.1f}BB. '
            f'Hand={hero_hand_class}({cat}). '
            f'n_callers={n_callers}.'
        )

    # Tips
    tips = []
    if street == 'preflop' and not facing_3bet:
        tips.append(
            f'BTN open range: {open_freq:.0%} ({open_sizing:.1f}BB open). '
            f'Standard 44% includes: all PP, all A-x suited, all broadways, '
            f'most suited connectors (54s+), suited gappers (75s+). '
            f'Adjust tighter vs aggressive SB/BB (3-bet pct > 9%).'
        )
        if bb_vpip > 0.50:
            tips.append(
                f'FISH in BB (vpip={bb_vpip:.0%}): '
                f'Open wider (50%+). Size up to 3.0BB. '
                f'Plan: c-bet frequently with strong hands, reduce bluffs. '
                f'Value bet relentlessly on all three streets with top pair+. '
                f'Never bluff fish — they call down with any pair.'
            )
        if sb_3bet_pct > 0.12:
            tips.append(
                f'AGGRESSIVE SB (3b={sb_3bet_pct:.0%}): '
                f'Open with 4-bet-ready hands only in marginal spots. '
                f'Go smaller preflop ({open_sizing - 0.3:.1f}BB) to risk less. '
                f'4-bet AA/KK/AKs/A5s-A3s for blockers. '
                f'Cold-call QQ, AQs in position.'
            )

    if street in ('flop', 'turn', 'river'):
        if n_callers >= 2:
            tips.append(
                f'MULTIWAY POT ({n_callers + 1}-way): '
                f'Tighten c-bet to 35-42% (only top of range). '
                f'No bluffs in multiway. '
                f'Use smaller sizing (35-45%pot) — more players = bet for value, not FE. '
                f'Strong draws can still bet on wet boards.'
            )
        if board_type == 'wet' and cat in ('air', 'middle_pair'):
            tips.append(
                f'WET BOARD + WEAK HAND: '
                f'Consider checking back (fold equity low on wet boards). '
                f'Villain draws reduce your FE to ~35-40%. '
                f'Only semi-bluff with combo draws (8-out+) or nut flush draws.'
            )
        if board_type == 'dry' and cat in ('premium', 'overpair'):
            tips.append(
                f'DRY BOARD + STRONG HAND: '
                f'Bet small (33-40%pot) to keep villain in pot. '
                f'Villain rarely has draws — protect less, extract more. '
                f'Consider checking some sets for deception vs good players.'
            )
        if facing_3bet and street == 'flop':
            tips.append(
                f'3-BET POT as BTN IP: '
                f'c-bet 45-60% depending on board. '
                f'Always c-bet premium/overpair. '
                f'Check back draws on wet boards to realize equity. '
                f'When villain check-raises in 3-bet pot: mostly fold bluffs, call/raise sets.'
            )

    if not tips:
        tips.append(
            f'BTN play optimal for current villain profile. '
            f'Open {open_freq:.0%}, cbet {cbet_freq:.0%} on {board_type} boards. '
            f'Adjust if villain deviates significantly from these profiles.'
        )

    return BtnPlayAdvice(
        street=street,
        hero_hand_class=hero_hand_class,
        board_type=board_type,
        sb_vpip=round(sb_vpip, 3),
        sb_3bet_pct=round(sb_3bet_pct, 3),
        bb_vpip=round(bb_vpip, 3),
        bb_3bet_pct=round(bb_3bet_pct, 3),
        hero_stack_bb=round(hero_stack_bb, 1),
        pot_bb=round(pot_bb, 1),
        n_callers=n_callers,
        facing_3bet=facing_3bet,
        recommended_open_freq=open_freq,
        recommended_sizing_bb=open_sizing,
        open_ev_estimate=open_ev,
        cbet_frequency=cbet_freq,
        cbet_size_pct=cbet_size_pct,
        cbet_size_bb=cbet_size_bb,
        cbet_ev_estimate=cbet_ev,
        vs_3bet_action=vs_3bet_action,
        vs_3bet_reasoning=vs_3bet_reasoning,
        fourbet_ev=fourbet_ev,
        call_3bet_ev=call_ev,
        action=action,
        reasoning=reasoning,
        tips=tips,
    )


def btn_play_one_liner(result: BtnPlayAdvice) -> str:
    if result.street == 'preflop':
        return (
            f'[BTN preflop] {result.action.upper()} | '
            f'open={result.recommended_open_freq:.0%} size={result.recommended_sizing_bb:.1f}BB '
            f'open_ev={result.open_ev_estimate:.2f}BB | '
            f'3b_vs={result.vs_3bet_action}'
        )
    return (
        f'[BTN {result.hero_hand_class}@{result.street}|{result.board_type}] '
        f'{result.action.upper()} | '
        f'cbet={result.cbet_frequency:.0%} size={result.cbet_size_pct:.0%}pot({result.cbet_size_bb:.1f}BB) '
        f'ev={result.cbet_ev_estimate:.1f}BB'
    )
