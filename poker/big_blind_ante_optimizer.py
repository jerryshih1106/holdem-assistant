"""
Big Blind Ante Optimizer (big_blind_ante_optimizer.py)

BBA (Big Blind Ante) format is now standard in online MTTs and many live events.
Instead of every player paying a small ante each orbit, ONE player (the BB)
pays a single large ante equal to 1 BB for the entire table.

HOW BBA CHANGES STRATEGY vs STANDARD ANTE:
  Standard: cada player pays 0.1-0.15 BB per hand in antes
  BBA:      BB player pays 1 BB extra (total of 2 BB: their blind + the ante)
            All other players pay 0 in antes

BBA DYNAMICS:
  1. More dead money in every pot
  2. Steal profitability DRAMATICALLY increases from LP
  3. BB defense WIDENS (they've already paid an extra blind)
  4. Effective M-ratio changes (BBA increases orbit cost for BB)
  5. Opens from EP/MP become less punishing (no antes from those positions)

KEY CALCULATIONS:
  With 9 players and 1BB ante:
    Dead money = 1.5 BB (SB) + 2.0 BB (BB+ante) = 3.5 BB total
    Standard dead money = 1.5 + 1.0 = 2.5 BB
    Extra dead money = 1.0 BB = 40% MORE dead money per hand

  BTN steal breakeven fold% = raise_size / (raise_size + 3.5)
  vs standard:                raise_size / (raise_size + 2.5)

  At 2.5x raise:
    BBA:      2.5 / (2.5 + 3.5) = 41.7% breakeven fold
    Standard: 2.5 / (2.5 + 2.5) = 50.0% breakeven fold
    BBA steals are MORE profitable!

Usage:
    from poker.big_blind_ante_optimizer import optimize_bba_strategy, BBAStrategyAdvice, bba_one_liner

    advice = optimize_bba_strategy(
        stack_bb=40.0,
        position='BTN',
        n_players=9,
        bb_fold_pct=0.60,
        sb_fold_pct=0.70,
    )
    print(bba_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import Dict, List


# --------------------------------------------------------------------------
# BBA math helpers
# --------------------------------------------------------------------------

def _dead_money_bba(n_players: int) -> float:
    """Dead money in BBA format: SB(0.5) + BB(1.0) + ante(1.0 for BB)."""
    return 2.5   # 0.5 SB + 1.0 BB + 1.0 BBA


def _dead_money_standard(n_players: int, ante_per_player: float = 0.1) -> float:
    """Dead money in standard ante: SB + BB + antes."""
    return 0.5 + 1.0 + ante_per_player * n_players


def _breakeven_fold_pct(raise_bb: float, dead_money_bb: float) -> float:
    """Fold% where a steal becomes breakeven: raise / (raise + dead_money)."""
    total = raise_bb + dead_money_bb
    if total <= 0:
        return 0.5
    return round(raise_bb / total, 4)


def _steal_ev(fold_pct: float, raise_bb: float, dead_money_bb: float,
              equity_if_called: float = 0.35) -> float:
    """EV of stealing: fold*dead_money + (1-fold)*(equity*(dm+2*raise) - raise)."""
    pot_after = dead_money_bb + 2 * raise_bb
    ev = fold_pct * dead_money_bb + (1 - fold_pct) * (equity_if_called * pot_after - raise_bb)
    return round(ev, 3)


def _bb_defend_threshold_bba(raise_bb: float) -> float:
    """
    MDF for BB in BBA format: villain raised to raise_bb.
    BB has already put in 2BB (1 BB blind + 1 BB ante).
    Call cost = raise_bb - 2.0 (the call is raise - already_in)
    """
    call_cost = max(0.0, raise_bb - 2.0)  # already invested 2BB (1 blind + 1 ante)
    pot_after_call = raise_bb + call_cost + 0.5  # raise + call + SB
    if pot_after_call <= 0:
        return 0.0
    return round(call_cost / pot_after_call, 4)


# --------------------------------------------------------------------------
# Position-specific BBA adjustments
# --------------------------------------------------------------------------

# Standard open range vs BBA open range (expanded ranges due to dead money)
_OPEN_RANGE_STD = {
    'UTG':  '13%',
    'UTG+1': '15%',
    'MP':   '18%',
    'HJ':   '22%',
    'CO':   '28%',
    'BTN':  '45%',
    'SB':   '40%',
}

_OPEN_RANGE_BBA = {
    'UTG':  '14%',
    'UTG+1': '17%',
    'MP':   '20%',
    'HJ':   '25%',
    'CO':   '32%',
    'BTN':  '55%',   # biggest adjustment: BTN should steal nearly any two
    'SB':   '50%',   # SB also opens very wide vs 1 player (BB+ante)
}

# Open sizing adjustment (BBA allows slightly smaller opens due to extra dead money)
_OPEN_SIZE_BBA = {
    'UTG':   '2.5x',
    'UTG+1': '2.5x',
    'MP':    '2.3x',
    'HJ':    '2.2x',
    'CO':    '2.2x',
    'BTN':   '2.0x',  # small open because more dead money makes it profitable already
    'SB':    '3.0x',  # SB opens larger to discourage BB from defending wide
}


@dataclass
class BBAStrategyAdvice:
    # Inputs
    stack_bb: float
    position: str
    n_players: int
    bb_fold_pct: float
    sb_fold_pct: float

    # BBA math
    dead_money_bba: float
    dead_money_standard: float
    extra_dead_money_pct: float     # how much more dead money BBA creates

    # Per-position
    breakeven_fold_bba: float
    breakeven_fold_standard: float
    steal_ev_bba: float
    steal_ev_standard: float
    steal_ev_advantage: float       # how much more EV BBA provides vs standard

    # Recommendations
    recommended_open_range_bba: str
    recommended_open_range_std: str
    recommended_open_size: str
    bb_defend_threshold: float      # BB should defend at least this % of hands
    steal_profitable: bool

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def optimize_bba_strategy(
    stack_bb: float = 40.0,
    position: str = 'BTN',
    n_players: int = 9,
    bb_fold_pct: float = 0.60,
    sb_fold_pct: float = 0.70,
    ante_per_player_standard: float = 0.1,
) -> BBAStrategyAdvice:
    """
    Optimize strategy for Big Blind Ante format.

    Args:
        stack_bb:       Hero's stack in BB
        position:       Hero's position ('UTG', 'MP', 'HJ', 'CO', 'BTN', 'SB')
        n_players:      Number of players at the table
        bb_fold_pct:    How often the BB folds to a steal
        sb_fold_pct:    How often the SB folds to a steal (when hero is BTN)
        ante_per_player_standard: Ante each player pays in standard format

    Returns:
        BBAStrategyAdvice
    """
    dm_bba = _dead_money_bba(n_players)
    dm_std = _dead_money_standard(n_players, ante_per_player_standard)
    extra_dm_pct = round((dm_bba - dm_std) / dm_std, 4) if dm_std > 0 else 0.0

    # Steal sizing (typical 2.0-2.5x)
    open_size_str = _OPEN_SIZE_BBA.get(position, '2.5x')
    open_size_mult = float(open_size_str.replace('x', ''))
    raise_bb = round(open_size_mult * 1.0, 2)  # normalized: 1.0 BB = big blind

    be_fold_bba = _breakeven_fold_pct(raise_bb, dm_bba)
    be_fold_std = _breakeven_fold_pct(raise_bb, dm_std)

    # Combined fold% from remaining players (SB + BB in most steal spots)
    if position in ('BTN', 'CO'):
        combined_fold = sb_fold_pct * bb_fold_pct
    elif position == 'SB':
        combined_fold = bb_fold_pct
    else:
        # EP/MP: many players left, fold pct drops
        players_to_act = {'UTG': 8, 'UTG+1': 7, 'MP': 6, 'HJ': 5}.get(position, 6)
        combined_fold = 0.70 ** players_to_act   # approximate

    ev_bba = _steal_ev(combined_fold, raise_bb, dm_bba)
    ev_std = _steal_ev(combined_fold, raise_bb, dm_std)
    ev_adv = round(ev_bba - ev_std, 3)

    # BB defend threshold in BBA
    bb_defend = _bb_defend_threshold_bba(raise_bb)

    steal_profitable = ev_bba > 0

    open_range_bba = _OPEN_RANGE_BBA.get(position, '20%')
    open_range_std = _OPEN_RANGE_STD.get(position, '18%')

    reasoning = (
        f'BBA format: {position} with {stack_bb:.0f}BB stack. '
        f'Dead money: BBA={dm_bba:.1f}BB vs standard={dm_std:.1f}BB (+{extra_dm_pct:.0%} more). '
        f'Breakeven fold: BBA={be_fold_bba:.0%} vs standard={be_fold_std:.0%}. '
        f'Steal EV: BBA={ev_bba:+.3f}BB vs standard={ev_std:+.3f}BB (adv={ev_adv:+.3f}BB). '
        f'Combined fold={combined_fold:.0%}.'
    )

    verdict = (
        f'BBA {position}: Open {open_range_bba} (vs std {open_range_std}). '
        f'Steal profitable={steal_profitable} (EV={ev_bba:+.3f}BB). '
        f'BE fold={be_fold_bba:.0%} (lower than std {be_fold_std:.0%}). '
        f'BB should defend >= {bb_defend:.0%} of hands.'
    )

    tips = []

    tips.append(
        f'BBA DEAD MONEY: {dm_bba:.1f}BB total ({extra_dm_pct:+.0%} more than standard). '
        f'This makes stealing {ev_adv:+.3f}BB more profitable per attempt at {position}. '
        f'Open wider -- especially BTN/CO/SB.'
    )

    if position in ('BTN', 'CO', 'SB'):
        tips.append(
            f'{position} STEAL: Breakeven fold drops from {be_fold_std:.0%} (standard) to {be_fold_bba:.0%} (BBA). '
            f'You need {(be_fold_bba-be_fold_std)*100:.1f}% LESS fold equity to steal profitably. '
            f'Widen your opening range to {open_range_bba}.'
        )

    if position == 'BB':
        tips.append(
            f'BB DEFENSE IN BBA: You invested 2BB (1 blind + 1 ante). '
            f'Your pot odds are better -- defend {1-bb_defend:.0%}+ of hands vs steals. '
            f'GTO says defend at least {bb_defend:.0%} to prevent exploitive opening. '
            f'Actually, since you paid 2BB, defend even WIDER than standard BB.'
        )

    if stack_bb < 20:
        tips.append(
            f'SHORT STACK ({stack_bb:.0f}BB) in BBA: Push/fold becomes important. '
            f'Extra dead money means shoves have MORE EV -- shove wider in BBA. '
            f'At 15BB: shove 40%+ from BTN; 30%+ from CO.'
        )

    if extra_dm_pct > 0:
        tips.append(
            f'KEY BBA INSIGHT: Antes are effectively FREE for non-BB players. '
            f'Only the BB pays the ante. This means EP/MP players are slightly LESS penalized '
            f'vs standard antes (no orbit cost from antes). Conversely, BB pays MORE.'
        )

    return BBAStrategyAdvice(
        stack_bb=round(stack_bb, 1),
        position=position,
        n_players=n_players,
        bb_fold_pct=round(bb_fold_pct, 3),
        sb_fold_pct=round(sb_fold_pct, 3),
        dead_money_bba=dm_bba,
        dead_money_standard=round(dm_std, 2),
        extra_dead_money_pct=round(extra_dm_pct, 4),
        breakeven_fold_bba=be_fold_bba,
        breakeven_fold_standard=be_fold_std,
        steal_ev_bba=ev_bba,
        steal_ev_standard=ev_std,
        steal_ev_advantage=ev_adv,
        recommended_open_range_bba=open_range_bba,
        recommended_open_range_std=open_range_std,
        recommended_open_size=open_size_str,
        bb_defend_threshold=bb_defend,
        steal_profitable=steal_profitable,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bba_one_liner(r: BBAStrategyAdvice) -> str:
    return (
        f'[BBA {r.position}|{r.stack_bb:.0f}BB] '
        f'open={r.recommended_open_range_bba}(vs{r.recommended_open_range_std}) '
        f'steal_ev={r.steal_ev_bba:+.3f}BB(adv={r.steal_ev_advantage:+.3f}) | '
        f'be_fold={r.breakeven_fold_bba:.0%}(was {r.breakeven_fold_standard:.0%})'
    )
