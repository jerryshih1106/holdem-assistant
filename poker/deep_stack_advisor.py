"""
Deep Stack Advisor (deep_stack_advisor.py)

Strategy shifts when effective stacks are 100-300+ BB — significantly deeper
than the standard 100 BB game most training materials assume.

Key strategic changes at deep stacks:

  Set mining (small pairs, suited connectors):
    Standard 15:1 rule applies at 100 BB.
    At 200 BB, mine with any call ≤ 6.5% of stack (implied odds better).
    At 300 BB, mine with any call ≤ 9% of stack (even easier).
    Rule: call ≤ stack / (15 × 1 / depth_mult)

  Speculative hands (suited connectors, suited aces, small pairs):
    At 200 BB: ATC (any two cards) in position for small raise → profitable.
    Hands like 65s gain ~2x implied value vs 100 BB game.
    Key: you need stacks to win big pots when you hit.

  SPR and commitment:
    100 BB open-raise pot flop SPR ≈ 12-15 (TPGK is NOT committed)
    200 BB open-raise pot flop SPR ≈ 24-30 (TPTK barely committed)
    Need two pair+ to commit in single-raised pots.
    Top pair = thin value at best; avoid big pots without top two+.

  Bet sizing:
    Use smaller flop C-bets (25-33% pot) to maintain range across 3 streets.
    Avoid PSB (pot-size bets) on flop — too many chips invested without equity.
    Turn: 50-66% preferred sizing in deep stack pots.
    River: can overbet comfortably since there's room to value-bet large.

  3-bet and 4-bet dynamics:
    3-bet pots: SPR ≈ 5-8 even at 200 BB → still committed with top pair+.
    4-bet pots: SPR ≈ 0.5-1.0 → committing full stack preflop effectively.
    Can 3-bet wider IP since you can outplay postflop with position.

  Bluffing:
    Deep stacks = more multi-street bluff opportunities.
    C-bet + turn barrel + river shove is viable with naked backdoors.
    Don't over-bluff; balance bluff:value ratio for each street.

Usage:
    from poker.deep_stack_advisor import analyze_deep_stack, DeepStackAdvice
    result = analyze_deep_stack(
        eff_stack_bb=200.0,
        pot_bb=8.0,
        hero_pos='BTN',
        hero_hand_class='top_pair',
        hero_equity=0.65,
        street='flop',
    )
    print(result.stack_regime, result.action)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Stack depth regimes
_DEEP_REGIMES = [
    (100, 150, 'standard',    'Standard 100BB game — default strategy applies'),
    (150, 200, 'moderately_deep', '150-200 BB: speculative hands gain value; avoid big SPR with one pair'),
    (200, 250, 'deep',        '200-250 BB: set mining any reasonable price; use small flop bets'),
    (250, 350, 'very_deep',   '250-350 BB: implied odds dominate; play for big pots only with 2 pair+'),
    (350, 999, 'super_deep',  '350+ BB: only nutted holdings justify big pots; exploit with position'),
]


def _regime(eff_stack: float) -> tuple:
    for lo, hi, key, desc in _DEEP_REGIMES:
        if lo <= eff_stack < hi:
            return key, desc
    return 'standard', 'Standard 100BB game'


def _spr(pot_bb: float, eff_stack_bb: float) -> float:
    return eff_stack_bb / pot_bb if pot_bb > 0 else 99.0


def _set_mine_threshold(eff_stack_bb: float) -> float:
    """Max call size (BB) for profitable set mining at given depth."""
    # Standard: need 15:1 pot odds. At deeper stacks, implied odds improve.
    # depth_factor: deeper stacks mean more money to win when you hit
    depth_factor = min(3.0, eff_stack_bb / 100.0)
    implied_multiplier = 1.0 + (depth_factor - 1.0) * 0.5
    max_call = eff_stack_bb / (15.0 / implied_multiplier)
    return round(max_call, 1)


def _cbet_size_pct(eff_stack_bb: float, spr: float, board_type: str) -> float:
    """
    Recommended C-bet size (fraction of pot) at deep stacks.
    Deeper stacks → smaller bets to stay in proportion over 3 streets.
    """
    # At 200BB, SPR ≈ 25 on flop → need 3 streets to get stacks in
    # Geometric bet size: (SPR^(1/3) - 1) / 2 ≈ 0.22 for SPR=25
    # But we want practical sizing not exact math
    if spr >= 20:
        base = 0.28
    elif spr >= 12:
        base = 0.35
    elif spr >= 7:
        base = 0.50
    else:
        base = 0.65

    # Board type adjustment
    board_adj = {'wet': 0.10, 'semi_wet': 0.05, 'dry': -0.05,
                 'monotone': 0.05, 'paired': -0.03}.get(board_type, 0.0)

    return round(max(0.20, min(0.90, base + board_adj)), 2)


def _implied_odds_factor(eff_stack_bb: float) -> float:
    """How much speculative hands gain relative to 100 BB game."""
    # 1.0 = standard; 2.0 = double value
    return min(3.0, eff_stack_bb / 100.0)


def _commitment_threshold(spr: float) -> tuple:
    """(equity_thresh, hand_strength_min) to commit stack at deep SPR."""
    if spr <= 3:
        return 0.35, 'top_pair'
    elif spr <= 6:
        return 0.45, 'top_pair_strong'
    elif spr <= 10:
        return 0.55, 'two_pair'
    elif spr <= 18:
        return 0.65, 'set_or_better'
    else:
        return 0.75, 'set_or_better'


def _action_deep(
    eff_stack_bb: float,
    spr: float,
    hero_equity: float,
    hand_class: str,
    hero_is_pfr: bool,
    in_position: bool,
    regime: str,
    cbet_pct: float,
    pot_bb: float,
) -> tuple:
    """Return (action, ev_note)."""
    eq_thresh, min_hand = _commitment_threshold(spr)
    cbet_size_bb = pot_bb * cbet_pct

    # Hand strength ranking
    hand_rank = {
        'air': 0, 'draw': 1, 'bottom_pair': 2, 'middle_pair': 3,
        'top_pair_weak': 4, 'top_pair': 5, 'tptk': 6, 'top_pair_strong': 6,
        'two_pair': 7, 'set': 8, 'straight': 9, 'flush': 10, 'full_house': 11,
    }.get(hand_class.lower(), 5)

    if hand_rank >= 8 and in_position:  # set or better
        return ('bet_trap_mix', f'Strong hand at SPR={spr:.1f}: mix betting and trapping. '
                f'Deep stacks mean villain can pay off big on later streets.')

    if hand_rank >= 7:  # two pair+
        if hero_is_pfr:
            return ('bet_commit', f'Two pair+ at SPR={spr:.1f}: build pot. '
                    f'C-bet {cbet_size_bb:.1f}BB, plan to commit over {max(1, min(3, int(spr/3)))} streets.')
        return ('check_raise', 'Two pair+ OOP: check-raise to build pot and protect.')

    if hand_rank == 1 and hero_equity >= 0.40:  # draw — semi-bluff before SPR guard
        return ('bet_semi', f'Draw: semi-bluff {cbet_size_bb:.1f}BB. '
                f'Deep stacks mean hitting gives massive implied odds.')

    # At high SPR, one pair is NOT a commitment hand (but air must still fold)
    if spr >= 12 and 2 <= hand_rank <= 5 and hero_equity < 0.70:
        if hero_is_pfr and hero_equity >= 0.55:
            return ('bet_small', f'Thin value: bet {cbet_size_bb:.1f}BB ({cbet_pct:.0%} pot). '
                    f'SPR={spr:.1f} → avoid over-committing with one pair.')
        else:
            return ('check_call', 'One pair at high SPR: check-call 1-2 streets max, give up if raised.')

    if hero_equity < 0.30:
        return ('check_fold', 'Weak hand at deep stacks: avoid burning chips. Check-fold.')

    if hero_is_pfr and in_position and hero_equity >= 0.50:
        return ('bet_small', f'Merged bet {cbet_size_bb:.1f}BB for thin value + info.')

    return ('check', 'Check to control pot size with medium-strength hand at deep stacks.')


def _speculative_hand_ev(eff_stack_bb: float, call_bb: float, hand_class: str) -> dict:
    """EV estimate for calling with speculative hands at deep stacks."""
    implied = _implied_odds_factor(eff_stack_bb)
    mine_thresh = _set_mine_threshold(eff_stack_bb)

    if hand_class.lower() in ('pair', 'small_pair', 'pocket_pair'):
        set_rate = 1 / 8.5
        win_when_set = eff_stack_bb * 0.45  # often stack off when flopping set
        raw_ev = set_rate * win_when_set - (1 - set_rate) * call_bb
        profitable = call_bb <= mine_thresh
        return {
            'hand_type': 'small_pair_set_mine',
            'set_rate': set_rate,
            'ev_bb': round(raw_ev, 2),
            'profitable': profitable,
            'note': f'Set mining: call up to {mine_thresh:.0f}BB at {eff_stack_bb:.0f}BB effective.'
        }

    if 'suited' in hand_class.lower() or hand_class.lower() in ('sc', 'suited_connector'):
        # Suited connectors hit nut-flush, str8, two-pair etc ~15% of flops
        hit_rate = 0.15
        win_when_hit = eff_stack_bb * 0.35 * implied
        raw_ev = hit_rate * win_when_hit - (1 - hit_rate) * call_bb
        profitable = call_bb <= eff_stack_bb * 0.04
        return {
            'hand_type': 'suited_connector',
            'hit_rate': hit_rate,
            'ev_bb': round(raw_ev, 2),
            'profitable': profitable,
            'note': f'Suited connector: call up to {eff_stack_bb*0.04:.0f}BB at {eff_stack_bb:.0f}BB.'
        }

    return {'hand_type': 'unknown', 'ev_bb': 0.0, 'profitable': False, 'note': ''}


@dataclass
class DeepStackAdvice:
    """Strategy advice for deep stack situations (100-300+ BB)."""
    # Stack context
    eff_stack_bb: float
    pot_bb: float
    spr: float
    stack_regime: str         # 'standard', 'moderately_deep', 'deep', 'very_deep', 'super_deep'
    regime_description: str

    # Sizing adjustments
    recommended_cbet_pct: float     # smaller at deep stacks
    recommended_cbet_bb: float
    implied_odds_factor: float      # multiplier vs standard 100BB game

    # Set mining thresholds
    set_mine_max_call_bb: float     # max call size for profitable set mining
    suited_connector_max_call_bb: float

    # Commitment
    commitment_equity_thresh: float  # min equity to commit stack
    commitment_hand_min: str         # 'two_pair', 'set_or_better', etc.
    hero_should_commit: bool

    # Action
    action: str
    action_note: str

    # Reasoning
    reasoning: str
    deep_stack_tips: List[str] = field(default_factory=list)

    # Optional speculative hand analysis
    spec_hand_ev: Optional[dict] = None


def analyze_deep_stack(
    eff_stack_bb: float,
    pot_bb: float,
    hero_pos: str = 'BTN',
    hero_hand_class: str = 'top_pair',
    hero_equity: float = 0.65,
    street: str = 'flop',
    board_type: str = 'semi_wet',
    hero_is_pfr: bool = True,
    in_position: bool = True,
    call_bb: float = 0.0,          # if hero is considering calling a raise
    speculative_hand: str = '',    # optional: 'small_pair', 'suited_connector'
) -> DeepStackAdvice:
    """
    Strategy advice for deep-stack (100-300+ BB) situations.

    Args:
        eff_stack_bb:    Effective stack in BB
        pot_bb:          Current pot
        hero_pos:        Position
        hero_hand_class: Hand classification
        hero_equity:     Current equity
        street:          'flop', 'turn', 'river'
        board_type:      'dry', 'wet', 'semi_wet', 'monotone', 'paired'
        hero_is_pfr:     Hero raised preflop
        in_position:     Hero acts after villain
        call_bb:         Call size if hero facing a bet (for spec hand EV)
        speculative_hand: 'small_pair', 'suited_connector', or ''

    Returns:
        DeepStackAdvice
    """
    regime, regime_desc = _regime(eff_stack_bb)
    spr = _spr(pot_bb, eff_stack_bb)
    cbet_pct = _cbet_size_pct(eff_stack_bb, spr, board_type)
    cbet_bb = round(pot_bb * cbet_pct, 1)
    impl_factor = _implied_odds_factor(eff_stack_bb)
    mine_thresh = _set_mine_threshold(eff_stack_bb)
    sc_thresh = round(eff_stack_bb * 0.04, 1)
    eq_thresh, hand_min = _commitment_threshold(spr)
    should_commit = (hero_equity >= eq_thresh and
                     _hand_rank_ge(hero_hand_class, hand_min))

    action, action_note = _action_deep(
        eff_stack_bb, spr, hero_equity, hero_hand_class,
        hero_is_pfr, in_position, regime, cbet_pct, pot_bb,
    )

    # Spec hand EV
    spec_ev = None
    if speculative_hand:
        spec_ev = _speculative_hand_ev(eff_stack_bb, call_bb or pot_bb * 0.20, speculative_hand)

    # Tips
    tips = []

    if spr >= 12:
        tips.append(
            f'SPR={spr:.1f} at {eff_stack_bb:.0f}BB: do NOT over-commit with top pair. '
            f'Need {hand_min} to commit. Use small bets ({cbet_pct:.0%} pot) to build pot efficiently.'
        )

    if eff_stack_bb >= 150:
        tips.append(
            f'At {eff_stack_bb:.0f}BB: set mine with calls up to {mine_thresh:.0f}BB '
            f'(vs standard ~{100/15:.0f}BB at 100BB). Suited connectors: call up to {sc_thresh:.0f}BB.'
        )

    if eff_stack_bb >= 200 and regime in ('deep', 'very_deep', 'super_deep'):
        tips.append(
            f'Implied odds at {eff_stack_bb:.0f}BB are {impl_factor:.1f}x stronger than 100BB game. '
            f'Play speculative hands in position for a small price. Avoid them OOP.'
        )

    if action in ('check_call', 'check') and spr >= 12:
        tips.append(
            'Checking is often correct at deep stacks with one pair. You preserve stack '
            'and keep SPR manageable. Villain cannot take away your hand equity.'
        )

    if not tips:
        tips.append(
            f'{regime_desc}. SPR={spr:.1f}. '
            f'Commitment threshold: {eq_thresh:.0%} equity + {hand_min}. '
            f'Use {cbet_pct:.0%} pot bets on this street.'
        )

    reasoning = (
        f'Stack {eff_stack_bb:.0f}BB [{regime}]. SPR={spr:.1f}. '
        f'Hero eq={hero_equity:.0%} ({hero_hand_class}). '
        f'Commit threshold: {eq_thresh:.0%} equity + {hand_min}. '
        f'Recommended C-bet: {cbet_bb:.1f}BB ({cbet_pct:.0%} pot). '
        f'Action: {action}.'
    )

    return DeepStackAdvice(
        eff_stack_bb=round(eff_stack_bb, 1),
        pot_bb=round(pot_bb, 1),
        spr=round(spr, 2),
        stack_regime=regime,
        regime_description=regime_desc,
        recommended_cbet_pct=cbet_pct,
        recommended_cbet_bb=cbet_bb,
        implied_odds_factor=round(impl_factor, 2),
        set_mine_max_call_bb=mine_thresh,
        suited_connector_max_call_bb=sc_thresh,
        commitment_equity_thresh=round(eq_thresh, 2),
        commitment_hand_min=hand_min,
        hero_should_commit=should_commit,
        action=action,
        action_note=action_note,
        reasoning=reasoning,
        deep_stack_tips=tips,
        spec_hand_ev=spec_ev,
    )


def _hand_rank_ge(hand_class: str, min_hand: str) -> bool:
    """True if hand_class strength >= min_hand."""
    rank = {
        'air': 0, 'draw': 1, 'bottom_pair': 2, 'middle_pair': 3,
        'top_pair_weak': 4, 'top_pair': 5, 'tptk': 6, 'top_pair_strong': 6,
        'two_pair': 7, 'set': 8, 'set_or_better': 8,
        'straight': 9, 'straight_or_better': 9,
        'flush': 10, 'full_house': 11,
    }
    hand_r = rank.get(hand_class.lower(), 5)
    min_r  = rank.get(min_hand.lower(), 0)
    return hand_r >= min_r


def deep_stack_one_liner(result: DeepStackAdvice) -> str:
    """Single-line overlay summary."""
    commit_str = '[COMMIT]' if result.hero_should_commit else '[ctrl]'
    return (
        f'DS {result.eff_stack_bb:.0f}BB [{result.stack_regime}] SPR={result.spr:.1f} | '
        f'{result.action.upper()} {commit_str} | '
        f'cbet={result.recommended_cbet_pct:.0%}pot | '
        f'mine<={result.set_mine_max_call_bb:.0f}BB'
    )
