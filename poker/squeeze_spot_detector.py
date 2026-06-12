"""
Squeeze Spot Detector (squeeze_spot_detector.py)

Detects and evaluates profitable squeeze opportunities in real-time.
A "squeeze" is a 3-bet after one player opens and at least one player
cold-calls, creating a unique dynamic where:

WHY SQUEEZES ARE PROFITABLE:
  1. ISOLATION: Forces the callers (with capped ranges) to fold
  2. DEAD MONEY: Multiple cold calls = more dead money in the pot
  3. RANGE ADVANTAGE: Opener has wide range; callers even wider (flatting range)
  4. FOLD EQUITY: Both opener AND caller(s) must navigate calling a 3-bet
     with other players still to act

SQUEEZE SIZE FORMULA:
  With 1 caller: 3-bet to 3x-4x open + 1 call = open * 3 + callers * open
  With 2 callers: 3-bet to open * 3 + 2 * open = 5x open
  Rule of thumb: add 1 open_size per caller to standard 3x raise

SQUEEZE SUCCESS RATES (approximate by stack depth):
  100BB: opener folds ~55%; caller(s) fold ~70% (wider range, pot odds changed)
  40-60BB: opener less likely to fold; squeeze more for push-fold value
  25BB (Nash push/fold): squeeze = open jam

VILLAIN STATS FOR SQUEEZE DECISION:
  opener fold_to_3bet: primary metric
  caller fold_to_3bet: secondary (caller range even wider)
  opener 3bet%: if very low -> only 4-bets strong hands; squeeze more liberally

DISTINCT FROM:
  squeeze_ev_optimizer.py:  Optimizes sizing given a squeeze decision
  threebet_sizing.py:       3-bet sizing in isolation
  THIS MODULE:              DETECTS when squeezing is optimal vs flat-calling or folding;
                            accounts for multiple callers and dead money dynamics

Usage:
    from poker.squeeze_spot_detector import detect_squeeze, SqueezeOpportunity, sqz_one_liner

    result = detect_squeeze(
        hero_hand_category='suited_connector',
        hero_position='btn',
        open_size_bb=3.0,
        caller_count=2,
        opener_vpip=0.28,
        opener_fold_to_3bet=0.58,
        caller_avg_vpip=0.35,
        caller_avg_fold_to_3bet=0.72,
        hero_stack_bb=100.0,
        pot_bb=7.5,
    )
    print(sqz_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


def _dead_money_factor(open_size_bb: float, caller_count: int) -> float:
    """
    Dead money = callers' contributions that stay in pot if they fold.
    Higher dead money makes squeeze more profitable.
    Returns dead money as fraction of hero's squeeze size.
    """
    caller_dead = open_size_bb * caller_count   # callers' money if they fold
    squeeze_size = _squeeze_size(open_size_bb, caller_count)
    return round(caller_dead / max(squeeze_size, 1.0), 3)


def _squeeze_size(open_size_bb: float, caller_count: int) -> float:
    """
    Recommended squeeze size in BBs.
    Standard: 3x open + 1 open per caller.
    """
    base = open_size_bb * 3.0
    per_caller = open_size_bb * caller_count
    return round(base + per_caller, 1)


def _fold_probability(
    opener_fold_to_3bet: float,
    caller_avg_fold_to_3bet: float,
    caller_count: int,
    hero_position: str,
) -> float:
    """
    Probability ALL villains fold to the squeeze.
    P(all fold) = P(opener folds) * P(each caller folds)^n
    """
    ip_bonus = 0.04 if hero_position in ('btn', 'co') else 0.0
    p_opener_fold = min(0.92, opener_fold_to_3bet + ip_bonus)
    p_each_caller_fold = min(0.88, caller_avg_fold_to_3bet + ip_bonus + 0.05)
    # callers have wider range → fold slightly more to 3-bets
    p_all_fold = p_opener_fold * (p_each_caller_fold ** caller_count)
    return round(p_all_fold, 3)


def _squeeze_ev(
    squeeze_bb: float,
    dead_money_bb: float,
    pot_before_bb: float,
    p_all_fold: float,
    hero_equity_if_called: float,
    avg_stack_bb: float,
) -> float:
    """
    EV of squeeze (net profit).
    When all fold: hero wins pot_before_bb (nets +pot_before).
    When called: equity * total_pot - hero_squeeze_cost.
    """
    ev_fold_out = p_all_fold * pot_before_bb

    p_called = 1 - p_all_fold
    total_pot_if_called = pot_before_bb + 2 * squeeze_bb   # hero bet + one caller calls
    ev_called = p_called * (hero_equity_if_called * total_pot_if_called - squeeze_bb)

    return round(ev_fold_out + ev_called, 2)


def _hand_suitability(hero_hand_category: str) -> tuple:
    """
    Returns (suited_for_squeeze: bool, equity_if_called: float, note: str)
    Best squeeze hands: high blockers (have As/Ks), or strong value (AA/KK).
    """
    category_map = {
        'premium_pair':     (True,  0.80, 'Pure value squeeze; always profitable.'),
        'strong_pair':      (True,  0.68, 'Good value squeeze; occasionally fold-or-call vs 4-bet.'),
        'medium_pair':      (True,  0.52, 'Squeeze for fold equity; fold to 4-bet.'),
        'suited_ace':       (True,  0.47, 'Excellent blocker to AA; high fold equity.'),
        'ace_king':         (True,  0.68, 'Strong squeeze; often a flip vs remaining caller.'),
        'suited_connector': (True,  0.42, 'Squeeze as semi-bluff; need high fold equity.'),
        'broadways':        (True,  0.50, 'Blocker squeeze; good equity if called.'),
        'offsuit_connector':(False, 0.38, 'Weak squeeze candidate; lacks blockers and equity.'),
        'small_pair':       (False, 0.40, 'Poor squeeze hand; prefer set-mine vs flat-call.'),
        'trash':            (False, 0.28, 'Only squeeze as pure bluff with extreme fold equity.'),
    }
    return category_map.get(hero_hand_category, (False, 0.40, 'Unknown hand type; proceed with caution.'))


def _squeeze_decision(
    ev: float,
    p_all_fold: float,
    hand_suited: bool,
    caller_count: int,
    opener_fold_to_3bet: float,
    hero_stack_bb: float,
) -> str:
    if hero_stack_bb <= 20.0:
        return 'jam'   # short stack: squeeze = shove
    if ev > 1.5 and p_all_fold >= 0.35 and hand_suited:
        return 'squeeze'
    elif ev > 0.5 and p_all_fold >= 0.50:
        return 'squeeze'   # high fold equity even if hand is marginal
    elif p_all_fold < 0.25 and not hand_suited:
        return 'fold'
    elif ev <= 0.0:
        return 'fold'
    else:
        return 'flat_call'   # borderline: call instead of squeeze


@dataclass
class SqueezeOpportunity:
    # Inputs
    hero_hand_category: str
    hero_position: str
    open_size_bb: float
    caller_count: int
    opener_fold_to_3bet: float
    caller_avg_fold_to_3bet: float
    hero_stack_bb: float
    pot_bb: float

    # Analysis
    dead_money_factor: float      # dead money / squeeze size
    squeeze_size_bb: float        # recommended squeeze size
    fold_probability: float       # P(all opponents fold)
    hand_suitable: bool           # hand is a good squeeze candidate
    equity_if_called: float       # estimated equity vs calling range
    squeeze_ev: float             # EV vs folding
    hand_note: str                # note about hand suitability

    # Decision
    action: str                   # 'squeeze' / 'flat_call' / 'fold' / 'jam'
    action_explanation: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def detect_squeeze(
    hero_hand_category: str = 'suited_connector',
    hero_position: str = 'btn',
    open_size_bb: float = 3.0,
    caller_count: int = 1,
    opener_vpip: float = 0.28,
    opener_fold_to_3bet: float = 0.58,
    caller_avg_vpip: float = 0.35,
    caller_avg_fold_to_3bet: float = 0.70,
    hero_stack_bb: float = 100.0,
    pot_bb: float = 7.5,
) -> SqueezeOpportunity:
    """
    Detect whether a squeeze opportunity is profitable.

    Args:
        hero_hand_category: Hand type (premium_pair/strong_pair/medium_pair/
                            suited_ace/ace_king/suited_connector/broadways/
                            offsuit_connector/small_pair/trash)
        hero_position:      'utg'/'mp'/'co'/'btn'/'sb'/'bb'
        open_size_bb:       Size of the opening raise in BBs
        caller_count:       Number of players who cold-called the open (1-3)
        opener_vpip:        Opener's VPIP
        opener_fold_to_3bet: Opener's fold-to-3bet frequency
        caller_avg_vpip:    Average VPIP of callers
        caller_avg_fold_to_3bet: Average fold-to-3bet of callers
        hero_stack_bb:      Hero's effective stack
        pot_bb:             Current pot before hero's action

    Returns:
        SqueezeOpportunity
    """
    squeeze_bb = _squeeze_size(open_size_bb, caller_count)
    dm_factor = _dead_money_factor(open_size_bb, caller_count)
    dead_money = open_size_bb * caller_count
    p_fold = _fold_probability(opener_fold_to_3bet, caller_avg_fold_to_3bet,
                                caller_count, hero_position)
    hand_suited, eq_if_called, hand_note = _hand_suitability(hero_hand_category)

    ev = _squeeze_ev(
        squeeze_bb=squeeze_bb,
        dead_money_bb=dead_money,
        pot_before_bb=pot_bb,
        p_all_fold=p_fold,
        hero_equity_if_called=eq_if_called,
        avg_stack_bb=hero_stack_bb,
    )

    decision = _squeeze_decision(
        ev=ev,
        p_all_fold=p_fold,
        hand_suited=hand_suited,
        caller_count=caller_count,
        opener_fold_to_3bet=opener_fold_to_3bet,
        hero_stack_bb=hero_stack_bb,
    )

    action_map = {
        'squeeze':    f'SQUEEZE to {squeeze_bb:.1f}BB: EV={ev:+.1f}BB, fold_prob={p_fold:.0%}, dead_money={dead_money:.1f}BB.',
        'flat_call':  f'FLAT CALL: Squeeze EV={ev:+.1f}BB marginal; fold_prob={p_fold:.0%} borderline. Call to realize equity.',
        'fold':       f'FOLD: EV={ev:+.1f}BB negative; fold_prob={p_fold:.0%} too low for squeeze.',
        'jam':        f'JAM: Stack {hero_stack_bb:.0f}BB is short -- squeeze = shove. EV={ev:+.1f}BB.',
    }
    action_exp = action_map.get(decision, f'Action: {decision}')

    reasoning = (
        f'Hero {hero_hand_category} in {hero_position}. '
        f'Opener raised {open_size_bb:.1f}BB, {caller_count} caller(s). '
        f'Pot={pot_bb:.1f}BB. Squeeze to {squeeze_bb:.1f}BB. '
        f'Dead money={dead_money:.1f}BB (dm_factor={dm_factor:.2f}). '
        f'P(all_fold)={p_fold:.0%}: opener_f3b={opener_fold_to_3bet:.0%}, caller_f3b={caller_avg_fold_to_3bet:.0%}. '
        f'Equity if called={eq_if_called:.0%}. EV={ev:+.1f}BB. Decision={decision}.'
    )

    verdict = (
        f'[SQZ {hero_hand_category.upper()}|{hero_position}|{caller_count}caller] '
        f'{decision.upper()} | '
        f'to={squeeze_bb:.1f}BB ev={ev:+.1f}BB fold={p_fold:.0%} | '
        f'dead={dead_money:.1f}BB'
    )

    tips = [action_exp, hand_note]

    if caller_count >= 2:
        tips.append(
            f'MULTI-CALLER SQUEEZE: {caller_count} callers = {dead_money:.1f}BB dead money. '
            f'Increase squeeze size by 1 open ({open_size_bb:.1f}BB) per caller. '
            f'Each additional caller increases dead money but also reduces fold probability.'
        )

    if opener_fold_to_3bet < 0.45:
        tips.append(
            f'STICKY OPENER (f3b={opener_fold_to_3bet:.0%}): Opener calls 3-bets frequently. '
            f'Only squeeze with value hands ({hero_hand_category} needs equity if called). '
            f'Bluff squeezes are unprofitable vs this player.'
        )
    elif opener_fold_to_3bet >= 0.70:
        tips.append(
            f'FOLDS TO 3-BET A LOT (f3b={opener_fold_to_3bet:.0%}): Squeeze any two cards profitably. '
            f'Use a wider squeeze range; this is free money at the right price.'
        )

    if hero_stack_bb <= 30.0:
        tips.append(
            f'SHORT STACK ({hero_stack_bb:.0f}BB): Squeeze = jam. No fold equity in 3-bet/fold; '
            f'commit if you squeeze. Use Nash push/fold charts for this stack depth.'
        )

    return SqueezeOpportunity(
        hero_hand_category=hero_hand_category,
        hero_position=hero_position,
        open_size_bb=open_size_bb,
        caller_count=caller_count,
        opener_fold_to_3bet=opener_fold_to_3bet,
        caller_avg_fold_to_3bet=caller_avg_fold_to_3bet,
        hero_stack_bb=hero_stack_bb,
        pot_bb=pot_bb,
        dead_money_factor=dm_factor,
        squeeze_size_bb=squeeze_bb,
        fold_probability=p_fold,
        hand_suitable=hand_suited,
        equity_if_called=eq_if_called,
        squeeze_ev=ev,
        hand_note=hand_note,
        action=decision,
        action_explanation=action_exp,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sqz_one_liner(r: SqueezeOpportunity) -> str:
    return (
        f'[SQZ {r.hero_hand_category.upper()}|{r.hero_position}|{r.caller_count}caller] '
        f'{r.action.upper()} | '
        f'to={r.squeeze_size_bb:.1f}BB ev={r.squeeze_ev:+.1f}BB fold={r.fold_probability:.0%} | '
        f'dead={r.caller_count * r.open_size_bb:.1f}BB'
    )
