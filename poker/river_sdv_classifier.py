"""
River Showdown Value Classifier (river_sdv_classifier.py)

On the river, every hand is one of three types:
  1. VALUE BET:      Strong enough to bet for value (villain calls with worse)
  2. SHOWDOWN VALUE: Medium strength — check to keep villain's bluffs in / call if bet
  3. GIVE UP:        Too weak for showdown — check/fold or fold to bet

This module makes the VALUE BET vs SDV vs GIVE UP distinction precise:
  - EV(value_bet) = fold% * pot + call% * (equity * pot_after - bet)
  - EV(check_call) = bluff_catch_eq * (pot + bet) - bet  [if villain bets]
  - EV(check_fold) = 0

KEY INSIGHT: Many players over-bet thin hands and under-check medium hands.
  - 57% equity hand: NOT always a value bet — depends on villain's calling range
  - 72% equity hand: NOT always a value bet — depends on bet size, villain type
  - Blocked draws: NEVER thin value — villain has air and will fold OR strong hand and call

DECISION FRAMEWORK:
  Step 1: Does villain call with worse? (value bet threshold)
  Step 2: Does villain bluff often enough to justify check-call? (SDV threshold)
  Step 3: If neither, check-fold (give up)

THIN VALUE THRESHOLD:
  vs calling station (WTSD>40%): value bet 55%+ equity
  vs standard villain (WTSD 30%): value bet 65%+ equity
  vs nit (WTSD<22%):             value bet 72%+ equity

DISTINCT FROM OTHER MODULES:
  river_value.py:       Finds optimal VALUE bet SIZE (assumes we're betting)
  river_medium.py:      42-60% equity decisions (broader)
  river_bluff_catch_advisor.py: Advises on bluff-catching vs overbets
  THIS MODULE:          Classifies hand type first, then advises accordingly

Usage:
    from poker.river_sdv_classifier import classify_river_hand, RiverSDVResult, sdv_one_liner

    result = classify_river_hand(
        hero_hand_rank_pct=0.62,
        villain_wtsd=0.30,
        villain_af=2.2,
        villain_vpip=0.28,
        pot_bb=25.0,
        bet_to_hero_bb=0.0,    # hero acts first
        hero_position='IP',
        board_type='dry',
        has_blocked_draw=False,
    )
    print(sdv_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# Core classification thresholds
# --------------------------------------------------------------------------

def _value_bet_threshold(villain_wtsd: float, villain_vpip: float) -> float:
    """Minimum equity to bet for value on the river."""
    # Base: WTSD drives calling tendencies more than VPIP
    if villain_wtsd >= 0.40:      # calling station
        base = 0.54
    elif villain_wtsd >= 0.33:    # loose caller
        base = 0.58
    elif villain_wtsd >= 0.27:    # standard
        base = 0.63
    elif villain_wtsd >= 0.22:    # tight
        base = 0.68
    else:                          # nit
        base = 0.72

    # VPIP secondary adjustment
    vpip_adj = (villain_vpip - 0.30) * -0.05
    return round(min(0.80, max(0.50, base + vpip_adj)), 3)


def _sdv_threshold(villain_af: float, villain_wtsd: float) -> float:
    """
    Minimum equity to have showdown value (worth checking back / check-calling).
    Below this = give up (check-fold or fold to bet).
    """
    # If villain bluffs a lot (high AF): SDV threshold goes up (worth calling down more)
    # If villain rarely bluffs (low AF): SDV threshold goes down (most bets are value)
    if villain_af >= 3.0:
        base = 0.35    # aggressive villain bluffs a lot; medium hands have SDV
    elif villain_af >= 2.0:
        base = 0.40
    elif villain_af >= 1.2:
        base = 0.45
    else:              # passive villain (low AF)
        base = 0.50    # they rarely bluff; need stronger hand to have SDV

    # WTSD: high WTSD means villain goes to SD often, meaning they have real hands
    wtsd_adj = (villain_wtsd - 0.30) * -0.10
    return round(min(0.60, max(0.25, base + wtsd_adj)), 3)


def _villain_bluff_freq(villain_af: float, villain_wtsd: float) -> float:
    """Estimate villain's river bluff frequency."""
    base = 0.30 + (villain_af - 1.5) * 0.06
    wtsd_adj = -(villain_wtsd - 0.30) * 0.30
    return round(min(0.55, max(0.08, base + wtsd_adj)), 3)


def _ev_value_bet(
    pot_bb: float,
    bet_bb: float,
    equity: float,
    villain_call_pct: float,
) -> float:
    """EV of betting for value."""
    total_pot = pot_bb + 2 * bet_bb
    ev_when_called = equity * total_pot - bet_bb
    return round(villain_call_pct * ev_when_called + (1 - villain_call_pct) * pot_bb * equity, 2)


def _ev_check_call(
    pot_bb: float,
    villain_bet_pct: float,
    villain_bet_size_pct: float,
    equity: float,
    bluff_freq: float,
) -> float:
    """EV of checking and calling villain's bet."""
    if villain_bet_pct <= 0.01:
        return round(equity * pot_bb, 2)
    bet_bb = pot_bb * villain_bet_size_pct
    total = pot_bb + 2 * bet_bb
    ev_call = equity * total - bet_bb
    ev_fold = 0.0
    # Decision within check: call if villain bluffs enough, fold otherwise
    # For SDV, hero usually calls
    p_bet = villain_bet_pct
    ev_check_call = p_bet * ev_call + (1 - p_bet) * equity * pot_bb
    return round(ev_check_call, 2)


def _ev_check_fold(pot_bb: float, villain_bet_pct: float, equity: float) -> float:
    """EV of checking and folding to villain's bet."""
    # Win the pot at showdown if villain checks back
    ev_check_back = (1 - villain_bet_pct) * equity * pot_bb
    ev_bet = villain_bet_pct * 0.0  # fold to bet = 0
    return round(ev_check_back + ev_bet, 2)


@dataclass
class RiverSDVResult:
    # Inputs
    hero_hand_rank_pct: float
    villain_wtsd: float
    villain_af: float
    villain_vpip: float
    pot_bb: float
    bet_to_hero_bb: float       # 0 = hero acts first; >0 = facing a bet
    hero_position: str
    board_type: str
    has_blocked_draw: bool

    # Thresholds
    value_bet_threshold: float      # min equity to bet for value
    sdv_threshold: float            # min equity to have showdown value

    # Classification
    hand_class: str     # 'value_bet' / 'showdown_value' / 'give_up' / 'thin_value'
    equity_margin_to_value: float   # hero_eq - value_bet_threshold
    equity_margin_to_sdv: float     # hero_eq - sdv_threshold

    # EV of each action (hero acts first scenario)
    ev_bet_75pct: float
    ev_bet_100pct: float
    ev_check_call: float
    ev_check_fold: float
    villain_bluff_freq: float

    # Recommended action
    action: str         # 'bet' / 'check_call' / 'check_fold' / 'fold'
    action_reason: str
    recommended_bet_size_pct: float     # if betting

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def classify_river_hand(
    hero_hand_rank_pct: float = 0.62,
    villain_wtsd: float = 0.30,
    villain_af: float = 2.0,
    villain_vpip: float = 0.28,
    pot_bb: float = 25.0,
    bet_to_hero_bb: float = 0.0,
    hero_position: str = 'IP',
    board_type: str = 'dry',
    has_blocked_draw: bool = False,
) -> RiverSDVResult:
    """
    Classify hero's river hand and recommend action.

    Args:
        hero_hand_rank_pct:  Hand strength 0-1 (0.62 ≈ two pair range boundary)
        villain_wtsd:        Villain's went-to-showdown%
        villain_af:          Villain's aggression factor
        villain_vpip:        Villain's VPIP
        pot_bb:              Pot in BB
        bet_to_hero_bb:      If >0, hero is facing this bet; if 0, hero acts first
        hero_position:       'IP' or 'OOP'
        board_type:          'dry', 'medium', 'wet', 'paired', 'monotone'
        has_blocked_draw:    True if hero's hand blocks main draw (reduces villain calling)

    Returns:
        RiverSDVResult
    """
    vb_thresh = _value_bet_threshold(villain_wtsd, villain_vpip)
    sdv_thresh = _sdv_threshold(villain_af, villain_wtsd)

    eq = hero_hand_rank_pct  # use rank pct as equity proxy
    bluff_freq = _villain_bluff_freq(villain_af, villain_wtsd)

    margin_to_vb = round(eq - vb_thresh, 3)
    margin_to_sdv = round(eq - sdv_thresh, 3)

    # Adjust for position: IP can bet thinly (villain can't raise river OOP as easily)
    if hero_position.upper() in ('IP', 'BTN', 'CO'):
        pos_vb_adj = -0.02   # lower threshold IP
    else:
        pos_vb_adj = +0.03   # higher threshold OOP

    eff_vb_thresh = vb_thresh + pos_vb_adj

    # Blocked draw: if hero blocks the main draw, villain's calling range has fewer draws
    # that missed → less bluffs to catch, more strong hands → makes thin value worse
    if has_blocked_draw:
        eff_vb_thresh += 0.03
        sdv_thresh += 0.02

    # Classify
    if eq >= eff_vb_thresh + 0.05:
        hand_class = 'value_bet'
    elif eq >= eff_vb_thresh:
        hand_class = 'thin_value'
    elif eq >= sdv_thresh:
        hand_class = 'showdown_value'
    else:
        hand_class = 'give_up'

    # EVs (hero acts first)
    villain_call_75 = max(0.15, villain_wtsd - 0.05)  # call %  to 75% bet
    villain_call_100 = max(0.10, villain_wtsd - 0.10)  # call % to 100% bet

    bet_75 = pot_bb * 0.75
    bet_100 = pot_bb * 1.0

    ev_bet_75 = _ev_value_bet(pot_bb, bet_75, eq, villain_call_75)
    ev_bet_100 = _ev_value_bet(pot_bb, bet_100, eq, villain_call_100)

    # Villain bet frequency on river when checked to
    villain_bet_pct_when_checked = 0.30 + (villain_af - 1.5) * 0.08
    villain_bet_pct_when_checked = min(0.65, max(0.10, villain_bet_pct_when_checked))

    ev_cc = _ev_check_call(pot_bb, villain_bet_pct_when_checked, 0.60, eq, bluff_freq)
    ev_cf = _ev_check_fold(pot_bb, villain_bet_pct_when_checked, eq)

    # Recommend action
    if hand_class == 'value_bet':
        action = 'bet'
        rec_size = 0.65 if villain_wtsd >= 0.35 else 0.75   # larger vs callers
        reason = f'Value bet: equity ({eq:.0%}) well above threshold ({eff_vb_thresh:.0%}) vs {villain_wtsd:.0%} WTSD villain'
    elif hand_class == 'thin_value':
        # IP thin value: usually bet; OOP thin value: often check
        if hero_position.upper() in ('IP', 'BTN'):
            action = 'bet'
            rec_size = 0.55
            reason = f'Thin value IP: bet small ({rec_size:.0%}pot). Villain calls worse ({villain_wtsd:.0%} WTSD)'
        else:
            action = 'check_call'
            rec_size = 0.0
            reason = f'Thin value OOP: check to protect range, call if villain bets reasonable size'
    elif hand_class == 'showdown_value':
        if bet_to_hero_bb > 0:
            # Facing a bet
            call_thresh = bet_to_hero_bb / (pot_bb + 2 * bet_to_hero_bb)
            if eq >= call_thresh + bluff_freq * 0.15:
                action = 'check_call'   # calling here means "call"
                rec_size = 0.0
                reason = f'SDV: call facing bet ({bet_to_hero_bb:.0f}BB). Bluff freq={bluff_freq:.0%} justifies call'
            else:
                action = 'fold'
                rec_size = 0.0
                reason = f'SDV: fold facing large bet. Pot odds insufficient vs value-heavy villain'
        else:
            action = 'check_call'
            rec_size = 0.0
            reason = f'SDV: check back (IP) or check-call (OOP). Villain bluffs {bluff_freq:.0%}'
    else:  # give_up
        if bet_to_hero_bb > 0:
            action = 'fold'
            rec_size = 0.0
            reason = f'Give up: equity ({eq:.0%}) below SDV threshold ({sdv_thresh:.0%}). Fold to bet.'
        else:
            action = 'check_fold'
            rec_size = 0.0
            reason = f'Give up: check-fold. Equity ({eq:.0%}) has no SDV or thin value'

    reasoning = (
        f'River {hero_position}: eq={eq:.0%} vs villain WTSD={villain_wtsd:.0%} AF={villain_af:.1f}. '
        f'Value threshold={eff_vb_thresh:.0%} SDV threshold={sdv_thresh:.0%}. '
        f'Classification: {hand_class}. '
        f'EV: bet75%={ev_bet_75:+.2f}BB bet100%={ev_bet_100:+.2f}BB check_call={ev_cc:+.2f}BB. '
        f'Action: {action}.'
    )

    verdict = (
        f'[SDV {hero_position}|{board_type}] {hand_class.upper()} -> {action.upper()} | '
        f'eq={eq:.0%} vb_thresh={eff_vb_thresh:.0%} sdv_thresh={sdv_thresh:.0%} | '
        f'ev_bet={ev_bet_75:+.2f}BB ev_check={ev_cc:+.2f}BB'
    )

    tips = []
    tips.append(
        f'{hand_class.upper()}: equity={eq:.0%}, value threshold={eff_vb_thresh:.0%}, SDV threshold={sdv_thresh:.0%}. '
        f'Action: {action}. Reason: {reason}.'
    )

    if hand_class in ('value_bet', 'thin_value'):
        tips.append(
            f'BET SIZING: {rec_size:.0%}pot recommended. '
            f'Villain WTSD={villain_wtsd:.0%}: '
            f'{"go bigger" if villain_wtsd >= 0.35 else "standard" if villain_wtsd >= 0.27 else "small bet, they rarely call"}. '
            f'EV(75%pot)={ev_bet_75:+.2f}BB vs EV(100%pot)={ev_bet_100:+.2f}BB.'
        )

    if has_blocked_draw:
        tips.append(
            f'BLOCKED DRAW: Hero blocks main draw. '
            f'Villain calling range has fewer missed draws (less bluff-catching equity). '
            f'Thin value becomes worse; prefer smaller bet or check.'
        )

    if villain_af >= 3.0:
        tips.append(
            f'AGGRESSIVE VILLAIN (AF={villain_af:.1f}): High bluff frequency ({bluff_freq:.0%}). '
            f'Medium hands (SDV class) should check-call rather than bet-fold. '
            f'Check-call EV={ev_cc:+.2f}BB vs check-fold={ev_cf:+.2f}BB.'
        )

    return RiverSDVResult(
        hero_hand_rank_pct=round(eq, 3),
        villain_wtsd=round(villain_wtsd, 3),
        villain_af=round(villain_af, 2),
        villain_vpip=round(villain_vpip, 3),
        pot_bb=round(pot_bb, 1),
        bet_to_hero_bb=round(bet_to_hero_bb, 1),
        hero_position=hero_position.upper(),
        board_type=board_type,
        has_blocked_draw=has_blocked_draw,
        value_bet_threshold=vb_thresh,
        sdv_threshold=sdv_thresh,
        hand_class=hand_class,
        equity_margin_to_value=margin_to_vb,
        equity_margin_to_sdv=margin_to_sdv,
        ev_bet_75pct=ev_bet_75,
        ev_bet_100pct=ev_bet_100,
        ev_check_call=ev_cc,
        ev_check_fold=ev_cf,
        villain_bluff_freq=bluff_freq,
        action=action,
        action_reason=reason,
        recommended_bet_size_pct=rec_size,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def sdv_one_liner(r: RiverSDVResult) -> str:
    return (
        f'[SDV {r.hero_position}|{r.board_type}] {r.hand_class.upper()} -> {r.action.upper()} | '
        f'eq={r.hero_hand_rank_pct:.0%} vb={r.value_bet_threshold:.0%} '
        f'sdv={r.sdv_threshold:.0%} | ev_bet={r.ev_bet_75pct:+.2f}BB'
    )
