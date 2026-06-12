"""
Dead Money Analyzer (dead_money_analyzer.py)

Calculates dead money in preflop spots and how it affects optimal strategy.
Dead money is chips in the pot from players who are no longer contesting it
(folded) or from mandatory contributions (antes, blinds when uncontested).

DEAD MONEY THEORY:
  Dead money increases the pot without adding equity: it's "free money"
  available to whoever wins the pot. This changes:
  1. Squeeze EV: more dead money = more profitable to squeeze
  2. Steal profitability: antes make stealing more profitable
  3. Open-raise ROI: blinds are dead money once they fold
  4. Short-stack shoving: more dead money = wider shove range

  ANTES IN MODERN POKER:
    Standard 6-max ante: 1 BB per player = 6 BB total dead money
    Live straddle (2 BB): adds 2 BB dead money; opens play like +2BB pot
    Big blind ante (tournament): 6 BB antes from one player; same effect

  DEAD MONEY COMPONENTS:
    Blinds: SB (0.5BB) and BB (1BB) are dead if they fold = 1.5BB
    Antes: each player posts 1 BB = N × 1BB dead money
    Limper folds: each limper who folds = 1BB dead money
    Straddle folds: straddle = 2BB dead money if straddler folds

  EFFECT ON OPEN RAISE ROI:
    No antes:     Open steal EV = fold_freq * 1.5BB - (1-fold_freq) * raise_size
    With antes:   Open steal EV = fold_freq * (1.5 + ante) BB - (1-fold_freq) * raise_size
    More ante:    Opens with wider hands are profitable

DISTINCT FROM:
  preflop_squeeze_range.py: Squeeze EV with dead money math
  preflop_ev.py:            General preflop EV calculations
  blind_steal.py:           Stealing from late position
  THIS MODULE:              Precise dead money QUANTIFICATION;
                            how antes/straddles/limpers affect EV
                            of raises; adjusting open/squeeze range
                            width based on dead money magnitude.

Usage:
    from poker.dead_money_analyzer import analyze_dead_money, DeadMoneyAnalysis, dma_one_liner

    result = analyze_dead_money(
        hero_position='btn',
        small_blind=0.5,
        big_blind=1.0,
        ante_per_player=1.0,
        players_at_table=6,
        limpers=1,
        straddle=0.0,
        hero_open_size_bb=2.5,
        villain_fold_to_steal=0.60,
    )
    print(dma_one_liner(result))
"""

from dataclasses import dataclass, field
from typing import List


def _total_dead_money(
    small_blind: float,
    big_blind: float,
    ante_per_player: float,
    players_at_table: int,
    limpers: int,
    straddle: float,
) -> float:
    """Total dead money in pot before hero acts."""
    blind_dead = small_blind + big_blind
    ante_dead = ante_per_player * players_at_table
    limper_dead = limpers * big_blind   # each limper = 1BB, assumed to fold to raise
    straddle_dead = straddle            # straddle assumed to fold to raise
    return round(blind_dead + ante_dead + limper_dead + straddle_dead, 2)


def _steal_ev(
    dead_money: float,
    hero_open_size: float,
    fold_prob: float,
) -> float:
    """EV of open-raise as a steal."""
    ev_fold = fold_prob * dead_money
    # If called: roughly neutral (assume 0 EV when called; full model needs equity)
    ev_call = 0.0
    return round(ev_fold + (1 - fold_prob) * ev_call - hero_open_size * (1 - fold_prob), 2)


def _break_even_fold_prob(
    dead_money: float,
    hero_open_size: float,
) -> float:
    """Minimum fold probability for open steal to be +EV."""
    # EV = fold * dead - (1-fold) * open_size = 0
    # fold * (dead + open_size) = open_size
    # fold = open_size / (dead + open_size)
    if dead_money + hero_open_size <= 0:
        return 1.0
    return round(hero_open_size / (dead_money + hero_open_size), 3)


def _open_range_widening(dead_money: float, base_range_pct: float) -> float:
    """How much wider to open given dead money vs standard 1.5BB."""
    standard_dead = 1.5   # just blinds
    extra_dead = dead_money - standard_dead
    # Each BB of extra dead money allows ~2% wider opening range
    widening = extra_dead * 0.02
    return round(min(base_range_pct + widening, 0.85), 3)


def _squeeze_opportunity(
    dead_money: float,
    callers: int,
) -> str:
    if callers >= 1 and dead_money >= 4.0:
        return 'strong_squeeze_opportunity'
    elif callers >= 1 and dead_money >= 2.5:
        return 'moderate_squeeze_opportunity'
    elif dead_money >= 3.0:
        return 'steal_opportunity'
    return 'standard_raise'


def _straddle_impact(straddle: float, big_blind: float) -> str:
    if straddle <= 0:
        return 'no_straddle'
    multiplier = straddle / big_blind
    if multiplier >= 2:
        return 'standard_straddle_2x'
    return f'straddle_{multiplier:.0f}x'


@dataclass
class DeadMoneyAnalysis:
    # Inputs
    hero_position: str
    small_blind: float
    big_blind: float
    ante_per_player: float
    players_at_table: int
    limpers: int
    straddle: float
    hero_open_size_bb: float
    villain_fold_to_steal: float

    # Analysis
    total_dead_money: float
    steal_ev: float
    break_even_fold_prob: float
    widened_open_range: float     # suggested open% given dead money
    squeeze_opportunity: str
    straddle_impact: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_dead_money(
    hero_position: str = 'btn',
    small_blind: float = 0.5,
    big_blind: float = 1.0,
    ante_per_player: float = 1.0,
    players_at_table: int = 6,
    limpers: int = 0,
    straddle: float = 0.0,
    hero_open_size_bb: float = 2.5,
    villain_fold_to_steal: float = 0.60,
) -> DeadMoneyAnalysis:
    """
    Analyze dead money and its effect on open-raise and squeeze decisions.

    Args:
        hero_position:        Hero's position
        small_blind:          Small blind amount (in BB: 0.5)
        big_blind:            Big blind amount (1.0)
        ante_per_player:      Ante each player posts (e.g. 1.0 BB)
        players_at_table:     Number of players at table
        limpers:              Number of limpers who called and will likely fold
        straddle:             Straddle amount (0 if none)
        hero_open_size_bb:    Hero's planned open-raise size in BB
        villain_fold_to_steal: Estimated fold frequency of remaining players

    Returns:
        DeadMoneyAnalysis
    """
    dead = _total_dead_money(small_blind, big_blind, ante_per_player,
                              players_at_table, limpers, straddle)
    ev = _steal_ev(dead, hero_open_size_bb, villain_fold_to_steal)
    be_fold = _break_even_fold_prob(dead, hero_open_size_bb)
    wide = _open_range_widening(dead, 0.25)  # assume BTN base = 25% without antes
    sq_opp = _squeeze_opportunity(dead, limpers)
    strad = _straddle_impact(straddle, big_blind)

    verdict = (
        f'[DMA {hero_position}|dead={dead:.1f}BB] '
        f'steal_ev={ev:+.2f}BB be_fold={be_fold:.0%} | '
        f'open_range={wide:.0%} {sq_opp}'
    )

    reasoning = (
        f'Dead money analysis at {hero_position}. '
        f'Components: blinds={small_blind+big_blind:.1f}BB + '
        f'antes={ante_per_player * players_at_table:.1f}BB + '
        f'limpers={limpers * big_blind:.1f}BB + straddle={straddle:.1f}BB = '
        f'total={dead:.1f}BB dead. '
        f'Steal EV @ {villain_fold_to_steal:.0%} fold: {ev:+.2f}BB. '
        f'Break-even fold: {be_fold:.0%}. '
        f'Open range widens to {wide:.0%} (vs 25% base). '
        f'Squeeze: {sq_opp}.'
    )

    tips = []

    tips.append(
        f'DEAD MONEY BREAKDOWN: '
        f'Blinds: {small_blind+big_blind:.1f}BB | '
        f'Antes ({players_at_table} players x {ante_per_player}BB): {ante_per_player*players_at_table:.1f}BB | '
        f'Limpers ({limpers}): {limpers*big_blind:.1f}BB | '
        f'Straddle: {straddle:.1f}BB. '
        f'TOTAL dead: {dead:.1f}BB. '
        f'Every chip in the pot that is not from hero or the calling villain is pure profit when they fold.'
    )

    tips.append(
        f'STEAL EV: Stealing {dead:.1f}BB dead money with {hero_open_size_bb:.1f}BB open. '
        f'At {villain_fold_to_steal:.0%} fold rate: EV = {ev:+.2f}BB/hand. '
        f'Break-even fold rate = {be_fold:.0%}: "I need villain to fold at least {be_fold:.0%} to profit." '
        f'{"PROFITABLE steal." if ev > 0 else "UNPROFITABLE steal at this fold rate -- tighten range."}'
    )

    tips.append(
        f'RANGE WIDENING: With {dead:.1f}BB dead money, open wider. '
        f'Standard (1.5BB dead) = 25% BTN range. '
        f'With antes+straddle: open {wide:.0%}. '
        f'Each additional BB of dead money allows ~2% wider opening range.'
    )

    if sq_opp == 'strong_squeeze_opportunity':
        tips.append(
            f'SQUEEZE OPPORTUNITY: {limpers} limper(s) + {dead:.1f}BB dead money. '
            f'3-betting over a limper captures significant dead money EV. '
            f'Squeeze range: widen to include medium suited aces, suited connectors. '
            f'Limper tends to fold to squeeze; raiser also folds often.'
        )
    elif sq_opp == 'steal_opportunity':
        tips.append(
            f'STEAL OPPORTUNITY: Large dead money ({dead:.1f}BB) with no limpers. '
            f'Open wider from late position. '
            f'Antes create extra incentive: every extra BB of antes = ~2% wider profitable opens.'
        )

    if strad != 'no_straddle':
        tips.append(
            f'STRADDLE IMPACT ({strad}): Straddle increases BB effective; everyone plays with worse pot odds. '
            f'Effective blinds now = {big_blind+straddle:.1f}BB. '
            f'If straddle folds: contributes {straddle:.1f}BB dead money. '
            f'Adjust stack-to-effective-blind ratio: SPR is lower in straddled pots.'
        )

    return DeadMoneyAnalysis(
        hero_position=hero_position,
        small_blind=small_blind,
        big_blind=big_blind,
        ante_per_player=ante_per_player,
        players_at_table=players_at_table,
        limpers=limpers,
        straddle=straddle,
        hero_open_size_bb=hero_open_size_bb,
        villain_fold_to_steal=villain_fold_to_steal,
        total_dead_money=dead,
        steal_ev=ev,
        break_even_fold_prob=be_fold,
        widened_open_range=wide,
        squeeze_opportunity=sq_opp,
        straddle_impact=strad,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def dma_one_liner(r: DeadMoneyAnalysis) -> str:
    return (
        f'[DMA {r.hero_position}|dead={r.total_dead_money:.1f}BB] '
        f'ev={r.steal_ev:+.2f}BB be={r.break_even_fold_prob:.0%} | '
        f'open={r.widened_open_range:.0%} {r.squeeze_opportunity}'
    )
