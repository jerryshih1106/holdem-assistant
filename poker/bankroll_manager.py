"""
Bankroll Manager (bankroll_manager.py)

Proper bankroll management is worth more than any in-game adjustment.
Playing above your bankroll leads to tilt, forced decisions, and ruin.
Playing below costs opportunity. This module finds the sweet spot.

BANKROLL REQUIREMENTS:
  Cash NL (6-max):    20-30 buy-ins (conservative: 40 BI)
  Cash NL (full ring): 30-40 buy-ins
  MTT:                100-200 buy-ins for your typical buy-in
  SNG:                30-50 buy-ins
  Spin & Go:          50-100+ (high variance)
  Heads-Up NL:        50 buy-ins (more swing)

RISK OF RUIN (ROR):
  Formula: ROR = exp(-2 × winrate × bankroll / variance)
  where winrate is in BB/hand, variance is BB^2/hand

  Typical 6-max NL values (per hand):
  - Winrate: 5 BB/100 = 0.05 BB/hand
  - Standard deviation: ~80 BB/100 = 0.80 BB/hand per hand variance ≈ 0.64 BB^2/hand

  Target ROR <= 5% (conservative) or <= 1% (very conservative)

MOVE UP CRITERIA:
  - Reached 40 buy-ins at next stake? → Consider moving up
  - Win rate at current stake confirmed (>10,000 hands)? → Safer to move up
  - Shot-taking: Use 5 buy-ins at next stake, move back if losing 3

MOVE DOWN CRITERIA:
  - Fallen to 15 buy-ins? → Move down immediately
  - Running bad for >30,000 hands? → Consider move-down to rebuild confidence
  - Tilting frequently? → Move down to reduce stress

Usage:
    from poker.bankroll_manager import advise_bankroll, BankrollAdvice, bankroll_one_liner

    advice = advise_bankroll(
        bankroll_bb=2000.0,
        current_stake_bb=100.0,
        winrate_bb100=5.0,
        hands_played=15000,
        std_dev_bb100=80.0,
        game_type='cash_6max',
        rakeback_pct=0.0,
        session_buyin_count=3,
        tilt_score=0.0,
    )
    print(bankroll_one_liner(advice))
"""

import math
from dataclasses import dataclass, field
from typing import List


# ── Buy-in requirements by game type ─────────────────────────────────────────

_BUYIN_REQUIREMENTS = {
    'cash_6max':      {'min': 20, 'standard': 30, 'conservative': 40},
    'cash_full_ring': {'min': 25, 'standard': 35, 'conservative': 50},
    'cash_hu':        {'min': 30, 'standard': 50, 'conservative': 80},
    'mtt':            {'min': 50, 'standard': 100, 'conservative': 200},
    'sng':            {'min': 20, 'standard': 30, 'conservative': 50},
    'spin_n_go':      {'min': 50, 'standard': 100, 'conservative': 150},
    'plo_6max':       {'min': 40, 'standard': 60, 'conservative': 100},
}


def _risk_of_ruin(
    winrate_per_hand: float,
    variance_per_hand: float,
    bankroll_hands: float,
) -> float:
    """
    Gambler's ruin formula: ROR = exp(-2 × mu × B / sigma^2)
    where mu=winrate/hand, B=bankroll in BB, sigma^2=variance/hand
    """
    if variance_per_hand <= 0 or winrate_per_hand <= 0:
        return 1.0  # infinite risk if 0 winrate
    exponent = -2 * winrate_per_hand * bankroll_hands / variance_per_hand
    return round(min(1.0, max(0.0, math.exp(exponent))), 4)


def _hands_to_confirm_edge(
    winrate_bb100: float,
    std_dev_bb100: float,
    confidence: float = 0.95,
) -> int:
    """
    Hands needed to confirm winrate > 0 at given confidence.
    Using z-score test: n = (z * sigma / mu)^2 (in units of 100 hands)
    """
    if winrate_bb100 <= 0:
        return 999_999  # can't confirm negative
    z = 1.96 if confidence == 0.95 else 2.58  # 95% or 99%
    # n in 100-hand units
    n_100 = (z * std_dev_bb100 / winrate_bb100) ** 2
    return int(n_100 * 100)


def _move_up_stake_bb(current_stake_bb: float) -> float:
    """Next stake up (standard stake ladder)."""
    stakes = [2, 5, 10, 25, 50, 100, 200, 500, 1000, 2000, 5000]
    for s in stakes:
        if s > current_stake_bb:
            return float(s)
    return current_stake_bb * 2.0


def _move_down_stake_bb(current_stake_bb: float) -> float:
    """Next stake down."""
    stakes = [2, 5, 10, 25, 50, 100, 200, 500, 1000, 2000, 5000]
    for s in reversed(stakes):
        if s < current_stake_bb:
            return float(s)
    return max(1.0, current_stake_bb / 2.0)


def _stake_recommendation(
    bankroll_bb: float,
    current_stake_bb: float,
    game_type: str,
    winrate_bb100: float,
) -> str:
    reqs = _BUYIN_REQUIREMENTS.get(game_type, _BUYIN_REQUIREMENTS['cash_6max'])
    buyins = bankroll_bb / current_stake_bb
    conservative_req = reqs['conservative']
    standard_req = reqs['standard']
    min_req = reqs['min']

    if buyins >= conservative_req * 1.5:
        return 'move_up'
    elif buyins >= conservative_req:
        return 'ready_to_move_up'
    elif buyins >= standard_req:
        return 'stay_current'
    elif buyins >= min_req:
        return 'caution'
    else:
        return 'move_down'


@dataclass
class BankrollAdvice:
    """Bankroll management analysis."""
    bankroll_bb: float
    current_stake_bb: float
    winrate_bb100: float
    hands_played: int
    std_dev_bb100: float
    game_type: str
    rakeback_pct: float
    session_buyin_count: int
    tilt_score: float

    # Key metrics
    buyins_at_stake: float                 # bankroll / stake
    min_buyins_required: int               # minimum BI for game type
    standard_buyins_required: int          # standard BI
    conservative_buyins_required: int      # conservative BI

    # Risk of ruin
    risk_of_ruin_pct: float               # ROR at current bankroll
    risk_of_ruin_label: str               # 'acceptable', 'high', 'extreme'

    # Winrate validation
    hands_to_confirm_edge: int             # hands needed to confirm positive winrate
    is_winrate_confirmed: bool             # has enough sample?

    # Stake recommendations
    stake_recommendation: str              # 'move_up', 'stay_current', 'move_down', etc.
    next_stake_up_bb: float
    next_stake_down_bb: float
    bankroll_for_moveup_bb: float          # bankroll needed to move up safely

    # Effective winrate with rake
    gross_winrate_bb100: float
    rake_cost_bb100: float
    net_winrate_bb100: float               # after rake

    # Decision
    action: str                            # 'move_up', 'take_shot', 'stay', 'move_down', 'emergency_move_down'
    verdict: str
    monthly_ev_estimate_bb: float

    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_bankroll(
    bankroll_bb: float = 2000.0,
    current_stake_bb: float = 100.0,
    winrate_bb100: float = 5.0,
    hands_played: int = 15000,
    std_dev_bb100: float = 80.0,
    game_type: str = 'cash_6max',
    rakeback_pct: float = 0.0,
    session_buyin_count: int = 3,
    tilt_score: float = 0.0,
) -> BankrollAdvice:
    """
    Provide comprehensive bankroll management advice.

    Args:
        bankroll_bb:           Total bankroll in big blinds at current stake
        current_stake_bb:      Max buy-in at current stake in BB (usually 100)
        winrate_bb100:         Observed winrate in BB/100 hands
        hands_played:          Total hands played at this stake
        std_dev_bb100:         Standard deviation in BB/100
        game_type:             Game type for BI requirements
        rakeback_pct:          Rakeback fraction (0.30 = 30%)
        session_buyin_count:   How many buy-ins lost this session (for tilt alert)
        tilt_score:            Tilt score from villain_tilt_detector (0-1)

    Returns:
        BankrollAdvice
    """
    reqs = _BUYIN_REQUIREMENTS.get(game_type, _BUYIN_REQUIREMENTS['cash_6max'])
    buyins = round(bankroll_bb / current_stake_bb, 1)

    # Risk of ruin
    # Convert BB/100 to per-hand units
    wr_per_hand = winrate_bb100 / 100.0
    var_per_hand = (std_dev_bb100 / 10.0) ** 2  # variance = (SD/10)^2 approx for 100-hand blocks
    ror = _risk_of_ruin(wr_per_hand, var_per_hand, bankroll_bb)
    if ror <= 0.05:
        ror_label = 'acceptable'
    elif ror <= 0.20:
        ror_label = 'moderate'
    elif ror <= 0.50:
        ror_label = 'high'
    else:
        ror_label = 'extreme'

    # Winrate confirmation
    confirm_hands = _hands_to_confirm_edge(winrate_bb100, std_dev_bb100)
    is_confirmed = hands_played >= confirm_hands

    # Stake recommendation
    stake_rec = _stake_recommendation(bankroll_bb, current_stake_bb, game_type, winrate_bb100)
    next_up = _move_up_stake_bb(current_stake_bb)
    next_down = _move_down_stake_bb(current_stake_bb)

    # Bankroll needed to move up safely (conservative BI at next stake)
    conservative_req = reqs['conservative']
    bankroll_for_moveup = next_up * conservative_req

    # Rake impact
    # Typical rake cost = 2-5 BB/100 at micro/small stakes
    # Simple estimate: 5BB/100 base, reduced by rakeback
    rake_cost = 3.0 * (1 - rakeback_pct)  # rough average rake cost
    net_wr = round(winrate_bb100 - rake_cost, 2)
    gross_wr = winrate_bb100

    # Monthly EV estimate (assume 25000 hands/month live)
    hands_per_month = 25000
    monthly_ev = round(net_wr * hands_per_month / 100, 0)

    # Emergency tilt override
    emergency_tilt = session_buyin_count >= 4 or tilt_score >= 0.75

    # Final action
    if emergency_tilt:
        action = 'emergency_move_down' if session_buyin_count >= 4 else 'stop_session'
    elif stake_rec == 'move_up' and is_confirmed and net_wr >= 3.0:
        action = 'move_up'
    elif stake_rec == 'ready_to_move_up' and not is_confirmed:
        action = 'take_shot'
    elif stake_rec in ('move_down',):
        action = 'move_down'
    elif stake_rec == 'caution' and net_wr < 0:
        action = 'move_down'
    else:
        action = 'stay'

    verdict = (
        f'Bankroll: {bankroll_bb:.0f}BB = {buyins:.1f} buy-ins at {current_stake_bb:.0f}BB stake. '
        f'Required: {reqs["conservative"]} BI (conservative). '
        f'Winrate: {winrate_bb100:+.1f}BB/100 (net after rake: {net_wr:+.1f}BB/100). '
        f'ROR: {ror:.1%} ({ror_label}). '
        f'Recommendation: {action.upper()}.'
    )

    reasoning = (
        f'Game: {game_type}, stake: {current_stake_bb:.0f}BB, BR: {bankroll_bb:.0f}BB. '
        f'Buy-ins: {buyins:.1f} (need {reqs["standard"]}-{reqs["conservative"]}). '
        f'WR: {gross_wr:+.1f}BB/100 gross, {net_wr:+.1f}BB/100 net. '
        f'Confirmed: {is_confirmed} ({hands_played}/{confirm_hands} hands). '
        f'ROR: {ror:.1%} ({ror_label}). '
        f'Session: {session_buyin_count} BI lost, tilt={tilt_score:.2f}. '
        f'Action: {action}.'
    )

    tips = []
    if emergency_tilt:
        tips.append(
            f'EMERGENCY STOP: {session_buyin_count} buy-ins lost this session '
            f'(tilt={tilt_score:.2f}). '
            f'Stop immediately. Come back tomorrow with fresh mindset. '
            f'Moving down is MANDATORY after 4+ BI sessions to prevent further damage.'
        )
    if ror_label in ('high', 'extreme'):
        tips.append(
            f'HIGH RISK OF RUIN ({ror:.0%}): Your bankroll ({buyins:.0f}BI) is too small. '
            f'Target: {reqs["conservative"]} BI = {reqs["conservative"] * current_stake_bb:.0f}BB. '
            f'Move down to {next_down:.0f}BB stake where you have '
            f'{bankroll_bb / next_down:.0f} BI. '
            f'Grinding with insufficient BR leads to forced bad decisions.'
        )
    if not is_confirmed:
        tips.append(
            f'EDGE UNCONFIRMED: Need {confirm_hands:,} hands to confirm {winrate_bb100:+.1f}BB/100 '
            f'at 95% confidence. You have {hands_played:,}. '
            f'Do not move up stakes until your edge is confirmed. '
            f'What looks like skill may be variance.'
        )
    if action in ('move_up', 'take_shot'):
        tips.append(
            f'MOVE UP ADVICE: You qualify for {next_up:.0f}BB stake '
            f'(need {bankroll_for_moveup:.0f}BB = {conservative_req} BI, have {bankroll_bb:.0f}BB). '
            f'"Shot-taking" rule: Move up with 5 BI budget. '
            f'If you lose 3 BI, move back down immediately. '
            f'Do NOT rebuy more than 5 times at new stake without analysis.'
        )
    if rake_cost > 2.0:
        tips.append(
            f'RAKE IMPACT: You pay ~{rake_cost:.1f}BB/100 in rake '
            f'({int(rakeback_pct*100)}% rakeback applied). '
            f'Gross WR {gross_wr:+.1f}BB/100 → Net {net_wr:+.1f}BB/100. '
            f'Rakeback programs can add 1-3BB/100 to your effective winrate. '
            f'Apply for VIP/rakeback at your site.'
        )
    if not tips:
        tips.append(
            f'{game_type}: {buyins:.1f} BI at {current_stake_bb:.0f}BB stake. '
            f'WR={net_wr:+.1f}BB/100 net. ROR={ror:.1%}. Action: {action}.'
        )

    return BankrollAdvice(
        bankroll_bb=round(bankroll_bb, 1),
        current_stake_bb=round(current_stake_bb, 1),
        winrate_bb100=round(winrate_bb100, 2),
        hands_played=hands_played,
        std_dev_bb100=round(std_dev_bb100, 1),
        game_type=game_type,
        rakeback_pct=round(rakeback_pct, 3),
        session_buyin_count=session_buyin_count,
        tilt_score=round(tilt_score, 3),
        buyins_at_stake=buyins,
        min_buyins_required=reqs['min'],
        standard_buyins_required=reqs['standard'],
        conservative_buyins_required=reqs['conservative'],
        risk_of_ruin_pct=round(ror, 4),
        risk_of_ruin_label=ror_label,
        hands_to_confirm_edge=confirm_hands,
        is_winrate_confirmed=is_confirmed,
        stake_recommendation=stake_rec,
        next_stake_up_bb=next_up,
        next_stake_down_bb=next_down,
        bankroll_for_moveup_bb=bankroll_for_moveup,
        gross_winrate_bb100=round(gross_wr, 2),
        rake_cost_bb100=round(rake_cost, 2),
        net_winrate_bb100=round(net_wr, 2),
        action=action,
        verdict=verdict,
        monthly_ev_estimate_bb=monthly_ev,
        reasoning=reasoning,
        tips=tips,
    )


def bankroll_one_liner(r: BankrollAdvice) -> str:
    return (
        f'[BR {r.game_type}|{r.current_stake_bb:.0f}BB] {r.action.upper()} | '
        f'bi={r.buyins_at_stake:.1f}/{r.conservative_buyins_required} ror={r.risk_of_ruin_pct:.0%} '
        f'wr={r.net_winrate_bb100:+.1f}BB/100 | '
        f'edge_confirmed={r.is_winrate_confirmed}'
    )
