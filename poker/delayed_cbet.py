"""
Delayed Continuation Bet Advisor (delayed_cbet.py)

Covers the specific spot:
  1. Hero raises preflop (PFR)
  2. Hero is in position (IP) on the flop
  3. Hero checks back on the flop (from check_back_ip.py)
  4. Villain also checks on the turn
  → Now what does hero do?

Why this spot is strategically distinct:
  - Hero's checking range is UNCAPPED: it contains sets, overpairs, strong
    made hands that chose to check for trapping, plus draws and air
  - Villain's checking range on the turn is ALSO uncapped but typically
    weak: villain missed the flop and is giving up, OR has a marginal hand
    trying to pot control, OR is slow-playing (rare)
  - Hero has the initiative back: hero should bet a wide range

Who to bet on the turn (delayed C-bet range):
  1. VALUE HANDS that wanted to trap: sets, two pair, overpairs
     → Now bet for value since villain checked twice (gives up or missed)
     → Turn bets build the pot and often get called by marginal hands
  2. IMPROVED HANDS: any hand that picked up equity on the turn
     → Top pair that paired on turn, flush draw that improved, etc.
  3. PURE BLUFFS: air hands with zero equity that can bluff profitably
     → Turn barrel with backdoor draws that bricked
     → But only at a balanced frequency (don't over-bluff)
  4. DRAWS: semi-bluff with strong draws that check flop, now bet turn
     → Flush draw, OESD: bet to build pot + equity if called

Who to check back again (second check):
  - Medium-strength hands at high SPR (pot control — same as flop)
  - Weak draws with no equity (give up)
  - Hands that prefer to see a free river

Key sizing principle:
  Delayed C-bets are typically 55-75% pot because:
  - Hero's range is wide (uncapped) → can use larger sizing
  - Villain has shown weakness by checking twice
  - Unlike flop C-bets (which use 33-50%), hero can put maximum pressure
  - Smaller turn bets (< 40% pot) are too cheap on turn; villain calls with anything

Turn card assessment:
  GOOD turn cards to bet:
  - Blank turns (2, 3, 4, 7, 8 offsuit — don't complete draws): range advantage
  - Hero's draw completing: obvious value bet
  - Scare cards for villain (paired board changes dynamics)

  BAD turn cards to bluff:
  - Draw-completing cards (flush or straight arrives): villain may have made hand
  - High Broadway cards that hit villain's calling range (K, Q on J-high flop)

Usage:
    from poker.delayed_cbet import advise_delayed_cbet, DelayedCBetAdvice
    result = advise_delayed_cbet(
        hero_hand_class='overpair',
        hero_equity=0.72,
        flop_board_type='dry',
        turn_card_type='blank',
        pot_bb=12.0,
        eff_stack_bb=88.0,
        villain_vpip=0.28,
        villain_af=1.5,
        n_opponents=1,
    )
    print(result.action, result.recommended_bet_bb)
"""

from dataclasses import dataclass, field
from typing import List, Optional


def _hand_rank(hand_class: str) -> int:
    return {
        'air': 0, 'draw': 1, 'backdoor_draw': 1, 'bottom_pair': 2,
        'middle_pair': 3, 'top_pair_weak': 4, 'top_pair': 5, 'tptk': 6,
        'top_pair_strong': 6, 'overpair': 6, 'two_pair': 7, 'set': 8,
        'straight': 9, 'flush': 10, 'full_house': 11,
    }.get(hand_class.lower(), 5)


def _spr(pot_bb: float, eff_stack_bb: float) -> float:
    return eff_stack_bb / pot_bb if pot_bb > 0 else 99.0


# Turn card quality: how good is this turn card for hero to bet?
# 'blank': brick card, no draws complete, hero range advantage maintained
# 'hero_draw_hit': hero's draw (flush/straight) completed
# 'scare': flush or straight arrives on board (villain may have hit)
# 'broadways': K/Q/J arrives on a low flop — hits villain's opening range
# 'paired': board pairs (hero may have trips/boat)
_TURN_CARD_BET_BONUS = {
    'blank':         +0.20,   # great bluff spot
    'hero_draw_hit': +0.30,   # obvious value
    'paired':        +0.10,   # hero may have full house; villain capped
    'scare':         -0.25,   # flush/straight arrives — villain may have it
    'broadways':     -0.10,   # hits villain's preflop calling range
    'unknown':        0.0,
}

_FLOP_BOARD_BET_BASE = {
    'dry':       0.70,   # high base frequency after dry flop check-through
    'semi_dry':  0.65,
    'medium':    0.60,
    'semi_wet':  0.55,
    'wet':       0.50,   # more cautious on wet flops (draws may have got there)
    'monotone':  0.45,
    'paired':    0.72,   # paired flop checks back, now villain is weak
}


def _delayed_cbet_freq(
    hand_class: str,
    hero_equity: float,
    flop_board_type: str,
    turn_card_type: str,
    spr: float,
    villain_vpip: float,
    villain_af: float,
) -> tuple:
    """
    Return (bet_freq, action, reasoning) for the delayed C-bet turn spot.
    bet_freq: 0.0 - 1.0, how often hero should bet this hand class
    """
    rank = _hand_rank(hand_class)
    base = _FLOP_BOARD_BET_BASE.get(flop_board_type.lower(), 0.60)
    turn_adj = _TURN_CARD_BET_BONUS.get(turn_card_type.lower(), 0.0)

    # SPR adjustment: high SPR → check more (pot control); low SPR → bet more (commit)
    spr_adj = -min(0.15, max(-0.10, (spr - 7.0) * 0.015))

    # Villain passive (low AF) → villain's check is weak → bet more
    af_adj = max(0.0, (2.0 - villain_af) * 0.08)

    # Villain loose (high VPIP) → more calls → bet value more, bluff less
    vpip_val_adj = min(0.15, (villain_vpip - 0.25) * 0.30)

    # AIR — bluff delayed C-bet only on blank turns, moderate frequency
    if rank == 0:
        bluff_freq = 0.35 + turn_adj * 0.5 + af_adj * 0.3
        bluff_freq = round(max(0.0, min(0.65, bluff_freq)), 2)
        if turn_card_type in ('scare', 'broadways'):
            bluff_freq = max(0.0, bluff_freq - 0.15)
        action = 'bet' if bluff_freq >= 0.40 else 'check'
        return (bluff_freq, action,
                f'Air: delayed bluff {bluff_freq:.0%} frequency on {turn_card_type} turn. '
                f'Villain checked twice → weakness. Bluff blank turns most profitably.')

    # DRAWS — semi-bluff the delayed C-bet
    if rank == 1:
        draw_freq = 0.65 + turn_adj * 0.3 + af_adj
        draw_freq = round(max(0.20, min(0.90, draw_freq)), 2)
        if turn_card_type == 'hero_draw_hit':
            draw_freq = 0.95  # hit the draw → bet for value
            action = 'bet'
            return (draw_freq, action,
                    f'Draw completed on turn: bet {draw_freq:.0%} for value. '
                    f'Villain does not know hero has the nuts.')
        action = 'bet' if draw_freq >= 0.50 else 'check'
        return (draw_freq, action,
                f'Draw: semi-bluff delayed C-bet {draw_freq:.0%}. '
                f'Equity + fold equity makes turn semi-bluff profitable.')

    # BOTTOM / MIDDLE PAIR — pot control preferred
    if rank <= 3:
        check_freq = base + 0.15  # prefer to check for pot control
        bet_freq = 1.0 - min(0.90, check_freq)
        bet_freq += af_adj * 0.5
        bet_freq = round(max(0.0, min(0.45, bet_freq + vpip_val_adj * 0.3)), 2)
        action = 'bet' if bet_freq >= 0.30 else 'check'
        return (bet_freq, action,
                f'{hand_class}: mostly check (pot control). '
                f'Bet {bet_freq:.0%} for thin value vs passive villain. '
                f'Villain equity ranges are unknown after two checks.')

    # TOP PAIR WEAK (rank 4) — value bet but pot control some
    if rank == 4:
        bet_freq = max(0.45, base - 0.10 + turn_adj * 0.3 + af_adj + vpip_val_adj * 0.5)
        bet_freq = round(min(0.85, bet_freq), 2)
        action = 'bet' if bet_freq >= 0.55 else 'check'
        return (bet_freq, action,
                f'Top pair weak: bet {bet_freq:.0%} for value. '
                f'Villain checked twice → likely has nothing or medium hand. '
                f'Extract value before river.')

    # TOP PAIR / TPTK / OVERPAIR (ranks 5-6) — mostly bet for value
    if rank <= 6:
        bet_freq = base + turn_adj * 0.5 + af_adj + vpip_val_adj * 0.4 + spr_adj
        bet_freq = round(max(0.50, min(0.95, bet_freq)), 2)
        action = 'bet'  # almost always bet
        return (bet_freq, action,
                f'{hand_class}: value bet {bet_freq:.0%} of the time. '
                f'Villain has shown weakness × 2. '
                f'Extract max value on turn before potentially scary river.')

    # TWO PAIR (rank 7) — strongly bet for value and protection
    if rank == 7:
        bet_freq = round(min(0.95, base + 0.15 + af_adj + spr_adj), 2)
        action = 'bet'
        return (bet_freq, action,
                f'Two pair: bet {bet_freq:.0%} for value/protection. '
                f'Build pot while ahead. Villain checked twice — commit.')

    # SET+ (rank 8+) — almost always bet (delayed slowplay is complete)
    bet_freq = round(min(0.98, base + 0.20 + af_adj), 2)
    action = 'bet'
    return (bet_freq, action,
            f'{hand_class}: bet {bet_freq:.0%}. '
            f'Trapping is complete; extract value. '
            f'Villain is now weak — charge for the pot.')


def _delayed_cbet_size(
    hand_class: str,
    flop_board_type: str,
    turn_card_type: str,
    spr: float,
) -> float:
    """Recommended bet size as fraction of pot for the delayed C-bet."""
    rank = _hand_rank(hand_class)

    # Base sizing: delayed C-bets are larger than flop C-bets
    if rank >= 8:        # set+: build pot
        base = 0.75
    elif rank >= 6:      # overpair/tptk
        base = 0.65
    elif rank >= 4:      # top pair
        base = 0.60
    elif rank == 1:      # draw: semi-bluff sizing
        base = 0.65
    else:                # bluff
        base = 0.55

    # Board type: wet boards → larger (want to charge draws)
    board_adj = {'wet': 0.10, 'semi_wet': 0.05, 'dry': -0.05,
                 'paired': -0.05, 'monotone': 0.08}.get(flop_board_type.lower(), 0.0)

    # Turn card: scare card → smaller (don't bomb into villain's hit)
    turn_adj = {'scare': -0.10, 'hero_draw_hit': 0.15, 'blank': 0.05}.get(
        turn_card_type.lower(), 0.0)

    # SPR: low SPR → larger as fraction (near all-in anyway)
    spr_adj = -min(0.10, max(-0.15, (spr - 6.0) * 0.012))

    size = base + board_adj + turn_adj + spr_adj
    return round(max(0.35, min(1.20, size)), 2)


def _build_recommendations(
    hand_class: str,
    action: str,
    bet_freq: float,
    turn_card_type: str,
    villain_af: float,
    spr: float,
    bet_pct: float,
    bet_bb: float,
) -> List[str]:
    rank = _hand_rank(hand_class)
    recs = []

    if action == 'bet' and rank >= 5:
        recs.append(
            f'Value bet {bet_bb:.0f}BB ({bet_pct:.0%} pot). '
            f'Villain checked the flop AND turn — range is weak. '
            f'Extract value now before river complications.'
        )

    if action == 'bet' and rank == 0:
        recs.append(
            f'Delayed bluff on {turn_card_type} turn. '
            f'Represents top pair/overpair (hero had same range on flop). '
            f'Do not overdo this — villain eventually catches on if always checked flop then bet turn.'
        )

    if action == 'bet' and rank == 1:
        recs.append(
            f'Semi-bluff with draw: bet {bet_bb:.0f}BB. '
            f'Combine equity (if called) + fold equity (if folded). '
            f'Balanced with value hands in same line.'
        )

    if action == 'check' and rank <= 3:
        recs.append(
            f'Second check with {hand_class}: pot control. '
            f'Proceed to showdown cheaply. Call small river bets; fold to large ones.'
        )

    if turn_card_type == 'scare' and action == 'bet':
        recs.append(
            f'Scare card arrived but still betting: size down ({bet_pct:.0%} pot). '
            f'Villain may have completed a draw — smaller sizing gets thin calls.'
        )

    if villain_af < 1.0 and action == 'bet':
        recs.append(
            f'Passive villain (AF={villain_af:.1f}): when they check, they are weak. '
            f'Delayed C-bet is highly profitable in this spot.'
        )

    if not recs:
        recs.append(
            f'Delayed C-bet {bet_freq:.0%} frequency. '
            f'Villain checked twice → show weakness. '
            f'Balance value bets with occasional bluffs to avoid being exploited.'
        )

    return recs


@dataclass
class DelayedCBetAdvice:
    """Advice for the delayed continuation bet on the turn."""
    # Situation
    hero_hand_class: str
    hero_equity: float
    flop_board_type: str
    turn_card_type: str
    spr: float
    pot_bb: float
    eff_stack_bb: float

    # Decision
    action: str               # 'bet' or 'check'
    bet_frequency: float      # how often to take this action (0-1)
    recommended_bet_pct: float
    recommended_bet_bb: float

    # Context
    action_reasoning: str
    recommendations: List[str] = field(default_factory=list)
    strategic_summary: str = ''
    one_liner: str = ''


def advise_delayed_cbet(
    hero_hand_class: str,
    hero_equity: float,
    flop_board_type: str = 'medium',
    turn_card_type: str = 'blank',
    pot_bb: float = 12.0,
    eff_stack_bb: float = 88.0,
    villain_vpip: float = 0.28,
    villain_af: float = 1.8,
    n_opponents: int = 1,
) -> DelayedCBetAdvice:
    """
    Advice for the delayed continuation bet turn spot.

    Scenario: Hero PFR → IP on flop → hero checks flop → villain checks → TURN.

    Args:
        hero_hand_class:  Current hand strength classification
        hero_equity:      Equity vs villain's full range
        flop_board_type:  Original flop texture (affects what hero's check range looks like)
        turn_card_type:   'blank', 'hero_draw_hit', 'scare', 'broadways', 'paired', 'unknown'
        pot_bb:           Current pot in BB (after flop check-check)
        eff_stack_bb:     Effective stack remaining
        villain_vpip:     Villain's VPIP (0.0-1.0)
        villain_af:       Villain's aggression factor
        n_opponents:      Number of opponents (1 = heads-up)

    Returns:
        DelayedCBetAdvice
    """
    spr = _spr(pot_bb, eff_stack_bb)

    # Multiway: much tighter delayed C-bet range
    multiway_adj = max(0.0, (n_opponents - 1) * 0.15)
    effective_villain_af = villain_af + multiway_adj

    bet_freq, action, reasoning = _delayed_cbet_freq(
        hero_hand_class, hero_equity, flop_board_type,
        turn_card_type, spr, villain_vpip, effective_villain_af,
    )

    # Reduce frequency in multiway
    if n_opponents > 1:
        bet_freq = round(max(0.0, bet_freq - multiway_adj), 2)

    bet_pct = _delayed_cbet_size(hero_hand_class, flop_board_type, turn_card_type, spr)
    bet_bb = round(pot_bb * bet_pct, 1)

    recs = _build_recommendations(
        hero_hand_class, action, bet_freq, turn_card_type,
        villain_af, spr, bet_pct, bet_bb,
    )

    strategic_summary = (
        f'Delayed C-bet spot: Hero checked flop IP → villain also checked → turn. '
        f'Hero range is UNCAPPED (has sets/overpairs/draws). '
        f'Villain range is WEAK. '
        f'Bet {bet_freq:.0%} of this hand class ({hero_hand_class}), '
        f'{bet_pct:.0%} pot ({bet_bb:.0f}BB). '
        f'Overall turn bet range: ~60-70% of all hands in this spot.'
    )

    one_liner = (
        f'[DCB {hero_hand_class}] {action.upper()} {bet_freq:.0%} | '
        f'{bet_pct:.0%}pot={bet_bb:.0f}BB | '
        f'SPR={spr:.1f} | {turn_card_type}'
    )

    return DelayedCBetAdvice(
        hero_hand_class=hero_hand_class,
        hero_equity=round(hero_equity, 3),
        flop_board_type=flop_board_type,
        turn_card_type=turn_card_type,
        spr=round(spr, 2),
        pot_bb=round(pot_bb, 1),
        eff_stack_bb=round(eff_stack_bb, 1),
        action=action,
        bet_frequency=bet_freq,
        recommended_bet_pct=bet_pct,
        recommended_bet_bb=bet_bb,
        action_reasoning=reasoning,
        recommendations=recs,
        strategic_summary=strategic_summary,
        one_liner=one_liner,
    )


def delayed_cbet_one_liner(result: DelayedCBetAdvice) -> str:
    return result.one_liner
