"""
ICM Deal Calculator (icm_deal_calculator.py)

At final tables, players frequently negotiate deals to split the remaining
prize pool. This module calculates the fairest deal structures:

  1. CHIP CHOP    — each player gets proportional to chip count
  2. ICM DEAL     — each player gets their ICM equity of prize pool
  3. SAVE DEAL    — guarantee each player min + split remainder by ICM
  4. LAST LONGER  — side-bet variant (hero gets agreed if they outlast villain)

WHY ICM DEALS BEAT CHIP CHOPS:
  Short stacks benefit from ICM (their chips have higher marginal value).
  Chip leaders are penalized by ICM (doubling chips < doubling equity).
  The ICM deal is theoretically "fair" from a game-theory perspective.
  The chip chop favors the chip leader vs. ICM equity.

DEAL NEGOTIATION STRATEGY:
  - If you are chip leader:  push for chip chop (you get more)
  - If you are short stack:  push for ICM deal (you get more)
  - Accept any deal where your deal_equity > ICM_equity (hero wins)
  - Reject deals where your deal_equity < ICM_equity - risk_tolerance

MALMUTH-HARVILLE ICM MODEL:
  P(player i wins) = chips_i / total_chips
  P(player i finishes 2nd | player j wins) = chips_i / (total - chips_j)
  ICM_equity(i) = sum over all finish combinations × prize for that position

Usage:
    from poker.icm_deal_calculator import calculate_deal, DealResult, deal_one_liner

    result = calculate_deal(
        player_chips=[50000, 30000, 20000],
        prize_pool=[10000, 6000, 3000],
        hero_index=0,
    )
    print(deal_one_liner(result))
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional


# --------------------------------------------------------------------------
# ICM engine (Malmuth-Harville)
# --------------------------------------------------------------------------

def _icm_equity(chips: List[float], prizes: List[float]) -> List[float]:
    """
    Compute ICM equity for each player given chip counts and prize payouts.
    Uses the Malmuth-Harville model (recursive enumeration, exact).
    Handles up to ~9 players efficiently with memoization.
    """
    n = len(chips)
    total = sum(chips)
    equities = [0.0] * n

    def recurse(remaining_chips: tuple, remaining_prizes: List[float], depth: int):
        if not remaining_prizes or all(c == 0.0 for c in remaining_chips):
            return [0.0] * len(remaining_chips)

        pool = sum(c for c in remaining_chips)
        prize = remaining_prizes[0]
        local_eq = [0.0] * len(remaining_chips)

        for i, c in enumerate(remaining_chips):
            if c == 0.0:
                continue
            p_win = c / pool
            # Player i wins this position
            new_chips = list(remaining_chips)
            new_chips[i] = 0.0
            sub_eq = recurse(tuple(new_chips), remaining_prizes[1:], depth + 1)
            for j in range(len(remaining_chips)):
                if j == i:
                    local_eq[i] += p_win * prize
                else:
                    local_eq[j] += p_win * sub_eq[j]
        return local_eq

    result = recurse(tuple(chips), prizes, 0)
    return [round(v, 4) for v in result]


# --------------------------------------------------------------------------
# Deal calculators
# --------------------------------------------------------------------------

def _chip_chop_equity(chips: List[float], prize_pool: List[float]) -> List[float]:
    """Each player gets (chips/total) * total_prizes."""
    total_chips = sum(chips)
    total_prizes = sum(prize_pool)
    return [round(c / total_chips * total_prizes, 2) for c in chips]


def _save_deal_equity(
    chips: List[float],
    prize_pool: List[float],
    icm_equities: List[float],
) -> List[float]:
    """
    Save deal: guarantee each player the minimum payout (last place prize),
    then split the remainder by ICM equity.
    """
    n = len(chips)
    min_prize = min(prize_pool) if prize_pool else 0.0
    # Guarantee: each player gets at least their ICM equity floored at min_prize
    saves = [min(icm_equities[i], min_prize) for i in range(n)]
    saved_total = sum(saves)
    remainder = sum(prize_pool) - saved_total

    # Distribute remainder proportionally to ICM equity above the save
    icm_above_save = [max(0.0, icm_equities[i] - saves[i]) for i in range(n)]
    total_above = sum(icm_above_save)

    deal = []
    for i in range(n):
        if total_above > 0:
            share = icm_above_save[i] / total_above * remainder
        else:
            share = remainder / n
        deal.append(round(saves[i] + share, 2))
    return deal


def _ev_of_playing_out(icm_equities: List[float]) -> List[float]:
    """Playing out to completion = ICM equity (by definition)."""
    return icm_equities


@dataclass
class PlayerDeal:
    index: int
    chips: float
    chip_pct: float
    icm_equity: float
    chip_chop_equity: float
    save_deal_equity: float
    icm_vs_chipchop: float    # ICM - chip chop (positive = ICM better for this player)
    best_deal_type: str       # which deal type is best for this player
    best_deal_value: float


@dataclass
class DealResult:
    # Inputs
    player_chips: List[float]
    prize_pool: List[float]
    hero_index: int
    n_players: int
    total_chips: float
    total_prizes: float

    # Per-player
    players: List[PlayerDeal]

    # Hero summary
    hero_icm_equity: float
    hero_chip_chop: float
    hero_save_deal: float
    hero_best_deal_type: str
    hero_best_deal_value: float

    # Negotiation advice
    negotiation_advice: str   # 'push_for_icm', 'push_for_chip_chop', 'accept_either'
    deal_recommendation: str  # 'icm', 'chip_chop', 'save', 'play_out'
    deal_ev_advantage: float  # hero_best_deal - icm_equity (how much deal saves vs playing out)

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def calculate_deal(
    player_chips: List[float],
    prize_pool: List[float],
    hero_index: int = 0,
    risk_tolerance: float = 0.05,
) -> DealResult:
    """
    Calculate deal equities for a final-table situation.

    Args:
        player_chips:      List of chip counts for each player (hero at hero_index)
        prize_pool:        List of prizes for each finishing position [1st, 2nd, 3rd, ...]
                           Length must match number of players.
        hero_index:        Index of the hero in player_chips (0-based)
        risk_tolerance:    Fraction of total prize hero is willing to sacrifice for a deal
                           (e.g., 0.05 = accept a deal up to 5% worse than ICM)

    Returns:
        DealResult with all deal structures and negotiation advice
    """
    n = len(player_chips)

    # Normalize prize pool to match number of players
    prizes = list(prize_pool)
    while len(prizes) < n:
        prizes.append(0.0)
    prizes = prizes[:n]
    prizes_sorted = sorted(prizes, reverse=True)

    total_chips = sum(player_chips)
    total_prizes = sum(prizes_sorted)

    # ICM equity
    icm_eqs = _icm_equity(player_chips, prizes_sorted)

    # Chip chop
    chipchop_eqs = _chip_chop_equity(player_chips, prizes_sorted)

    # Save deal (based on ICM)
    save_eqs = _save_deal_equity(player_chips, prizes_sorted, icm_eqs)

    players = []
    for i in range(n):
        chip_pct = player_chips[i] / max(total_chips, 1.0)
        best = max(
            ('icm', icm_eqs[i]),
            ('chip_chop', chipchop_eqs[i]),
            ('save', save_eqs[i]),
            key=lambda x: x[1],
        )
        players.append(PlayerDeal(
            index=i,
            chips=player_chips[i],
            chip_pct=round(chip_pct, 4),
            icm_equity=icm_eqs[i],
            chip_chop_equity=chipchop_eqs[i],
            save_deal_equity=save_eqs[i],
            icm_vs_chipchop=round(icm_eqs[i] - chipchop_eqs[i], 2),
            best_deal_type=best[0],
            best_deal_value=round(best[1], 2),
        ))

    hero = players[hero_index]

    # Negotiation advice
    if hero.icm_vs_chipchop > total_prizes * 0.02:
        neg_advice = 'push_for_icm'
    elif hero.icm_vs_chipchop < -total_prizes * 0.02:
        neg_advice = 'push_for_chip_chop'
    else:
        neg_advice = 'accept_either'

    # Best deal for hero
    best_deal = hero.best_deal_type
    best_deal_value = hero.best_deal_value
    deal_ev_adv = round(best_deal_value - hero.icm_equity, 2)

    # Recommendation: take any deal if it's >= ICM equity (variance reduction)
    min_acceptable = hero.icm_equity * (1.0 - risk_tolerance)
    if best_deal_value >= min_acceptable:
        deal_rec = best_deal
    else:
        deal_rec = 'play_out'

    reasoning = (
        f'{n}-player deal. Chips: {player_chips}. '
        f'Total prizes: ${total_prizes:,.0f}. '
        f'Hero (P{hero_index+1}) chips={player_chips[hero_index]:,.0f} '
        f'({hero.chip_pct:.1%} of chips). '
        f'ICM=${hero.icm_equity:,.0f} vs ChipChop=${hero.chip_chop_equity:,.0f}. '
        f'Best deal: {best_deal} (${best_deal_value:,.0f}).'
    )

    verdict = (
        f'DEAL CALC P{hero_index+1}: '
        f'ICM=${hero.icm_equity:,.0f} | '
        f'ChipChop=${hero.chip_chop_equity:,.0f} | '
        f'Save=${hero.save_deal_equity:,.0f} | '
        f'Best={best_deal.upper()} (${best_deal_value:,.0f}). '
        f'Advice: {neg_advice.upper()}.'
    )

    tips = []

    if neg_advice == 'push_for_icm':
        advantage = hero.icm_vs_chipchop
        tips.append(
            f'PUSH FOR ICM DEAL: Your ICM equity (${hero.icm_equity:,.0f}) is ${advantage:,.0f} '
            f'MORE than a chip chop (${hero.chip_chop_equity:,.0f}). '
            f'Chip leader wants a chip chop — resist. Demand ICM deal.'
        )
    elif neg_advice == 'push_for_chip_chop':
        advantage = hero.chip_chop_equity - hero.icm_equity
        tips.append(
            f'PUSH FOR CHIP CHOP: Your chip chop (${hero.chip_chop_equity:,.0f}) is ${advantage:,.0f} '
            f'MORE than ICM equity (${hero.icm_equity:,.0f}). '
            f'You are chip leader — chip chop rewards your stack advantage.'
        )
    else:
        tips.append(
            f'ACCEPT EITHER: ICM (${hero.icm_equity:,.0f}) and chip chop '
            f'(${hero.chip_chop_equity:,.0f}) are close. Any deal is reasonable.'
        )

    tips.append(
        f'DEAL vs PLAY-OUT: Best deal (${best_deal_value:,.0f}) vs playing out (${hero.icm_equity:,.0f}). '
        f'{"Deal saves $" + str(abs(deal_ev_adv)) + " in variance." if deal_ev_adv >= 0 else "Playing out is technically better but has more variance."}'
    )

    # Warn if chip leader is far ahead
    chips_sorted = sorted(player_chips, reverse=True)
    if player_chips[hero_index] == chips_sorted[0]:
        lead_pct = player_chips[hero_index] / total_chips
        if lead_pct > 0.50:
            tips.append(
                f'CHIP LEADER (${player_chips[hero_index]:,.0f} = {lead_pct:.0%} of chips): '
                f'ICM penalizes you for having more chips. '
                f'You should prefer chip chop or play it out if ICM deal is offered.'
            )
    elif player_chips[hero_index] == chips_sorted[-1]:
        tips.append(
            f'SHORT STACK: ICM protects your equity (${hero.icm_equity:,.0f}) vs '
            f'proportional (${hero.chip_chop_equity:,.0f}). '
            f'Do NOT accept chip chop — demand ICM or play it out.'
        )

    return DealResult(
        player_chips=player_chips,
        prize_pool=prizes_sorted,
        hero_index=hero_index,
        n_players=n,
        total_chips=round(total_chips, 0),
        total_prizes=round(total_prizes, 2),
        players=players,
        hero_icm_equity=hero.icm_equity,
        hero_chip_chop=hero.chip_chop_equity,
        hero_save_deal=hero.save_deal_equity,
        hero_best_deal_type=best_deal,
        hero_best_deal_value=best_deal_value,
        negotiation_advice=neg_advice,
        deal_recommendation=deal_rec,
        deal_ev_advantage=deal_ev_adv,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def deal_one_liner(r: DealResult) -> str:
    return (
        f'[DEAL {r.n_players}players|P{r.hero_index+1}] '
        f'{r.negotiation_advice.upper()} | '
        f'ICM=${r.hero_icm_equity:,.0f} chip_chop=${r.hero_chip_chop:,.0f} '
        f'best={r.hero_best_deal_type}(${r.hero_best_deal_value:,.0f}) | '
        f'adv={r.deal_ev_advantage:+,.0f}'
    )
