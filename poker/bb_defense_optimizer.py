"""
BB Defense Optimizer (bb_defense_optimizer.py)

Calculates the optimal Big Blind defense frequency and strategy
against opens from each position. This is a RANGE-LEVEL tool:
rather than advising on one specific hand, it answers:

  "How wide should I defend the BB overall vs this position?
   What fraction should I 3-bet vs call? What pot odds am I getting?"

KEY CONCEPTS:
  MDF (Minimum Defense Frequency):
    MDF = pot / (pot + raise) = prevents villain's bluffs from being +EV
    vs 2.5BB open: MDF = 1.5 / (1.5 + 2.5) = 37.5%
    vs 3.0BB open:  MDF = 1.5 / (1.5 + 3.0) = 33.3%

  TOTAL DEFENSE = call% + 3-bet%
    Hero must defend at least MDF total, or villain can profitably raise any two.

  3-BET FREQUENCY WITHIN DEFENSE:
    Polar 3-bet strategy: 3-bet ~25-30% of defending range
    (value hands + bluffs with blockers)

  DEFENDING RANGE COMPOSITION:
    BB can call with wider range than button callers due to pot odds and
    already having 1BB invested.

  POSITION ADJUSTMENTS:
    vs UTG open:   tighten (villain has strong range); MDF stays constant
    vs BTN/SB:     widen (villain has wide stealing range)

Usage:
    from poker.bb_defense_optimizer import optimize_bb_defense, BBDefenseAdvice, bbd_one_liner

    advice = optimize_bb_defense(
        villain_position='BTN',
        open_size_bb=2.5,
        effective_stack_bb=100.0,
        villain_open_pct=0.44,
        villain_fold_to_3b=0.55,
    )
    print(bbd_one_liner(advice))
"""

from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Villain open range width by position (fraction of all hands)
_VILLAIN_OPEN_PCT = {
    'UTG':  0.14,
    'UTG1': 0.16,
    'MP':   0.20,
    'HJ':   0.22,
    'CO':   0.28,
    'BTN':  0.44,
    'SB':   0.40,
}

# Baseline GTO BB defend range vs each position (call + 3bet)
_GTO_DEFEND_PCT = {
    'UTG':  0.38,   # tight: villain has strong range
    'UTG1': 0.40,
    'MP':   0.42,
    'HJ':   0.44,
    'CO':   0.46,
    'BTN':  0.50,   # wider: villain is stealing often
    'SB':   0.52,   # widest: SB is most aggressive stealer
}

# GTO 3-bet % from BB vs each position
_GTO_3BET_PCT = {
    'UTG':  0.06,
    'UTG1': 0.07,
    'MP':   0.08,
    'HJ':   0.09,
    'CO':   0.10,
    'BTN':  0.11,
    'SB':   0.13,
}

# Hand categories and their base calling frequencies in BB
# Lower number = tighter (e.g., vs UTG). Scaled by position.
_HAND_CATEGORY_CALL_PCTS = {
    'top_pair_hands':    0.95,   # TPTK type hands (AK, AQ, KQ suited)
    'medium_pairs':      0.80,   # 99-JJ (mostly 3-bet, some call)
    'small_pairs':       0.65,   # 22-55 (implied odds)
    'broadways_suited':  0.70,   # KJs, QJs, JTs
    'broadways_offsuit': 0.40,   # KJo, QJo, JTo
    'suited_connectors': 0.55,   # 87s, 76s, 65s
    'weak_aces_suited':  0.50,   # A2s-A5s (3-bet bluff candidates)
    'weak_trash':        0.05,   # 72o type hands
}

# Estimated fold equity (villain folds to 3-bet)
_FOLD_TO_3BET_BY_POS = {
    'UTG':  0.45,
    'UTG1': 0.48,
    'MP':   0.50,
    'HJ':   0.52,
    'CO':   0.55,
    'BTN':  0.57,
    'SB':   0.60,
}


def _mdf(open_bb: float, dead_money: float = 1.0) -> float:
    """Minimum defense frequency for BB."""
    call_cost = open_bb - dead_money  # BB already has 1BB invested
    pot = open_bb + dead_money        # pot if BB folds
    return round(call_cost / (open_bb + dead_money), 3)


def _pot_odds(open_bb: float, dead_money: float = 1.0) -> float:
    """BB's pot odds to call."""
    call_cost = open_bb - dead_money
    pot_after = open_bb + dead_money + call_cost
    return round(call_cost / pot_after, 3)


def _ev_3bet_bluff(
    open_bb: float,
    threeb_size: float,
    fold_to_3b: float,
) -> float:
    """EV of a 3-bet bluff from BB."""
    pot_before = open_bb + 1.0  # open + BB post
    ev_fold = fold_to_3b * pot_before
    ev_call = (1.0 - fold_to_3b) * (-threeb_size * 0.6)  # simplified: lose most when called
    return round(ev_fold + ev_call, 2)


def _optimal_defend_pct(
    villain_pos: str,
    open_pct: float,
    open_bb: float,
    fold_to_3b: float,
) -> float:
    """Compute optimal BB defend rate accounting for villain tendencies."""
    gto = _GTO_DEFEND_PCT.get(villain_pos, 0.45)
    mdf = _mdf(open_bb)

    # If villain opens very loose: can defend wider (more fold equity)
    gto_open = _VILLAIN_OPEN_PCT.get(villain_pos, 0.30)
    open_adj = (open_pct - gto_open) * 0.30

    # If villain rarely folds to 3-bet: 3-bet less, defend slightly less
    gto_fold3b = _FOLD_TO_3BET_BY_POS.get(villain_pos, 0.50)
    fold3b_adj = (fold_to_3b - gto_fold3b) * 0.20

    optimal = gto + open_adj + fold3b_adj
    # Never go below MDF (would make villain's bluffs +EV)
    return round(max(mdf, min(0.65, optimal)), 3)


def _optimal_3bet_pct(
    villain_pos: str,
    fold_to_3b: float,
    optimal_defend_pct: float,
) -> float:
    """Optimal 3-bet % from BB."""
    gto_3b = _GTO_3BET_PCT.get(villain_pos, 0.09)
    # More fold equity -> can 3-bet more bluffs
    gto_fold = _FOLD_TO_3BET_BY_POS.get(villain_pos, 0.50)
    fold_adj = (fold_to_3b - gto_fold) * 0.15

    opt_3b = gto_3b + fold_adj
    # Cap 3-bet at 35% of total defending range
    max_3b = optimal_defend_pct * 0.35
    return round(max(0.03, min(max_3b, opt_3b)), 3)


def _threeb_size(open_bb: float) -> float:
    """Standard BB 3-bet sizing."""
    return round(open_bb * 3.2, 1)


@dataclass
class BBDefenseAdvice:
    # Inputs
    villain_position: str
    open_size_bb: float
    effective_stack_bb: float
    villain_open_pct: float
    villain_fold_to_3b: float

    # Pot odds and MDF
    call_cost_bb: float
    mdf: float          # minimum defense frequency
    pot_odds: float     # hero's pot odds (required equity to call)
    spr_postflop: float

    # Defense strategy
    optimal_defend_pct: float    # total defense (call + 3-bet)
    optimal_call_pct: float      # call fraction
    optimal_3bet_pct: float      # 3-bet fraction
    threeb_size_bb: float        # recommended 3-bet size

    # EV
    ev_3bet_bluff: float         # EV of 3-bet bluff from BB
    bluff_3b_breakeven_fold: float  # fold% needed for 3-bet bluff to be +EV

    # Range composition guidance
    defend_range_guide: str      # which hand types to defend/3-bet/fold
    threeb_value_range: str      # hands to 3-bet for value
    threeb_bluff_range: str      # hands to 3-bet as bluffs
    calling_range: str           # hands to call with

    # Adjustment flags
    defending_too_tight_threshold: float  # if actual defend < this: too tight
    defending_too_loose_threshold: float  # if actual defend > this: too loose

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def optimize_bb_defense(
    villain_position: str = 'BTN',
    open_size_bb: float = 2.5,
    effective_stack_bb: float = 100.0,
    villain_open_pct: float = 0.44,
    villain_fold_to_3b: float = 0.55,
) -> BBDefenseAdvice:
    """
    Calculate optimal BB defense strategy vs a specific villain's open.

    Args:
        villain_position:   Where villain is opening from ('UTG', 'HJ', 'CO', 'BTN', 'SB')
        open_size_bb:       Villain's open raise size in BB
        effective_stack_bb: Effective stack depth
        villain_open_pct:   Villain's actual open frequency from this position
        villain_fold_to_3b: Villain's fold-to-3-bet frequency

    Returns:
        BBDefenseAdvice
    """
    villain_position = villain_position.upper()

    call_cost = open_bb = open_size_bb - 1.0   # BB already has 1BB in
    mdf = _mdf(open_size_bb)
    po = _pot_odds(open_size_bb)
    spr = round(effective_stack_bb / (open_size_bb * 2 + 1.0), 1)

    opt_defend = _optimal_defend_pct(villain_position, villain_open_pct, open_size_bb, villain_fold_to_3b)
    opt_3b = _optimal_3bet_pct(villain_position, villain_fold_to_3b, opt_defend)
    opt_call = round(opt_defend - opt_3b, 3)

    threeb_sz = _threeb_size(open_size_bb)
    bluff_3b_be = round(threeb_sz / (open_size_bb + 1.0 + threeb_sz), 3)
    ev_3b_bluff = _ev_3bet_bluff(open_size_bb, threeb_sz, villain_fold_to_3b)

    # Range composition guidance
    if villain_position in ('UTG', 'UTG1', 'MP'):
        threeb_value = 'QQ+, AKs, AKo (narrow: villain has strong range)'
        threeb_bluff = 'A5s-A2s (blocker), KQs (equity + blocker)'
        calling = 'JJ-TT, AQs-AJs, KQs, suited connectors (87s-54s), small pairs (implied odds)'
        defend_guide = 'Tight defense: villain UTG range is very strong. Fold most suited connectors, most Axo, weak K/Qo.'
    elif villain_position in ('HJ', 'CO'):
        threeb_value = 'QQ+, AKs, AKo; mix in JJ, AQs at 3-bet'
        threeb_bluff = 'A5s-A3s, KQs, JTs as semi-bluff'
        calling = 'JJ-77, AQs-ATs, KQs-KJs, suited connectors (98s-54s), broadways (KJo, QJo marginal)'
        defend_guide = 'Standard defense: balance value 3-bets with Axs bluffs. Call medium pairs and speculative hands.'
    else:  # BTN, SB
        threeb_value = 'JJ+, AKs, AQs, AKo (can include TT vs wide BTN)'
        threeb_bluff = 'A5s-A2s (best), K4s-K2s, T9s, 87s, 65s (playability)'
        calling = 'TT-55, AJs-A8s, KQs-KTs, QJs-T9s, 76s-54s, broadways (AQo, KQo, KJo)'
        defend_guide = 'Wide defense vs BTN/SB steal: 3-bet polar (nuts + bluffs), call all medium value/playability hands.'

    tight_threshold = round(opt_defend - 0.08, 3)
    loose_threshold = round(opt_defend + 0.10, 3)

    reasoning = (
        f'BB vs {villain_position} open {open_size_bb:.1f}BB. '
        f'Villain open={villain_open_pct:.0%} fold_3b={villain_fold_to_3b:.0%}. '
        f'MDF={mdf:.0%} pot_odds={po:.0%}. '
        f'Optimal defend={opt_defend:.0%} (call={opt_call:.0%} 3bet={opt_3b:.0%}). '
        f'3-bet size={threeb_sz:.1f}BB EV_bluff_3b={ev_3b_bluff:+.2f}BB.'
    )

    verdict = (
        f'[BBD vs {villain_position}|{open_size_bb:.1f}BB] '
        f'defend={opt_defend:.0%} (call={opt_call:.0%} + 3bet={opt_3b:.0%}) | '
        f'MDF={mdf:.0%} pot_odds={po:.0%} | '
        f'3b_size={threeb_sz:.1f}BB ev_bluff={ev_3b_bluff:+.2f}BB'
    )

    tips = []
    tips.append(
        f'DEFENSE FREQUENCY: Defend {opt_defend:.0%} total vs {villain_position} {open_size_bb:.1f}BB. '
        f'({opt_call:.0%} call + {opt_3b:.0%} 3-bet). MDF={mdf:.0%} -- going below this makes villain bluffs profitable.'
    )
    tips.append(defend_guide)

    if villain_open_pct > _VILLAIN_OPEN_PCT.get(villain_position, 0.30) + 0.10:
        tips.append(
            f'VILLAIN OPENS WIDE ({villain_open_pct:.0%} vs GTO {_VILLAIN_OPEN_PCT.get(villain_position,0.30):.0%}): '
            f'3-bet more bluffs -- their range is weaker and fold equity is higher. '
            f'Can profitably 3-bet hands like 87s, T9s that normally just call.'
        )

    if villain_fold_to_3b >= 0.65:
        tips.append(
            f'HIGH FOLD TO 3-BET ({villain_fold_to_3b:.0%}): Increase 3-bet frequency. '
            f'3-bet bluff EV={ev_3b_bluff:+.2f}BB. Add more Axs bluffs and semi-bluffs.'
        )
    elif villain_fold_to_3b <= 0.35:
        tips.append(
            f'LOW FOLD TO 3-BET ({villain_fold_to_3b:.0%}): Reduce bluff 3-bets. '
            f'Villain calls/4-bets too much. 3-bet mostly for value (QQ+/AK only). '
            f'Flat more hands in position.'
        )

    return BBDefenseAdvice(
        villain_position=villain_position,
        open_size_bb=round(open_size_bb, 1),
        effective_stack_bb=round(effective_stack_bb, 1),
        villain_open_pct=round(villain_open_pct, 3),
        villain_fold_to_3b=round(villain_fold_to_3b, 3),
        call_cost_bb=round(call_cost, 1),
        mdf=mdf,
        pot_odds=po,
        spr_postflop=spr,
        optimal_defend_pct=opt_defend,
        optimal_call_pct=opt_call,
        optimal_3bet_pct=opt_3b,
        threeb_size_bb=threeb_sz,
        ev_3bet_bluff=ev_3b_bluff,
        bluff_3b_breakeven_fold=bluff_3b_be,
        defend_range_guide=defend_guide,
        threeb_value_range=threeb_value,
        threeb_bluff_range=threeb_bluff,
        calling_range=calling,
        defending_too_tight_threshold=tight_threshold,
        defending_too_loose_threshold=loose_threshold,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def bbd_one_liner(r: BBDefenseAdvice) -> str:
    return (
        f'[BBD vs {r.villain_position}|{r.open_size_bb:.1f}BB] '
        f'defend={r.optimal_defend_pct:.0%} (call={r.optimal_call_pct:.0%}+3b={r.optimal_3bet_pct:.0%}) | '
        f'MDF={r.mdf:.0%} po={r.pot_odds:.0%} | 3b_ev={r.ev_3bet_bluff:+.2f}BB'
    )
