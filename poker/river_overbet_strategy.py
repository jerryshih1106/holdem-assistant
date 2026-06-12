"""
River Overbet Strategy Advisor (river_overbet_strategy.py)

Advises on when and how to fire river overbets (125%+ pot) from the
AGGRESSOR's perspective. This is a distinct weapon from standard bets:

  - Only works with POLARIZED range (nuts + air, no medium hands)
  - Requires NUT ADVANTAGE over villain (hero has more flushes/straights/sets)
  - EV = p_fold * pot + p_call * (equity * total_pot - overbet)
  - Wrong opponent type (call station) makes overbets -EV even with edge

OVERBET SIZES:
  120% pot  — light overbet, induces crying calls from weak top pair
  150% pot  — standard overbet, extracts max from strong TPTK, polarizes range
  175% pot  — large overbet, used against strong but capped villain ranges
  200% pot  — massive overbet / near jam, used with full nut advantage

WHEN TO OVERBET (all conditions should be met):
  1. Hero has nut advantage (more flush/straight/set combos than villain)
  2. Range is polarized (committed all value + bluffs, no medium hands as checks)
  3. Villain range is capped (called preflop / called flop+turn — no premium hands)
  4. Villain is not a call station (WTSD < 38%)
  5. Board runout favored hero's range more than villain's

IMPORTANT DISTINCTION FROM OTHER MODULES:
  overbet_response.py:  how HERO should respond when VILLAIN overbets
  river_range_builder.py: constructs range composition
  river_bluff.py:        decides whether to bluff on river (small/medium bets)
  THIS MODULE:          when/how to FIRE an overbet as the aggressor

Usage:
    from poker.river_overbet_strategy import advise_river_overbet, RiverOverbetAdvice, rob_one_liner

    advice = advise_river_overbet(
        hero_nut_advantage=0.60,      # hero has moderate nut advantage
        hero_equity=0.72,
        pot_bb=40.0,
        effective_stack_bb=80.0,
        villain_wtsd=0.32,
        villain_af=1.8,
        villain_vpip=0.25,
        hero_position='IP',
        hero_hand_rank_pct=0.82,      # strong value hand
        board_type='paired',
        range_is_polarized=True,
    )
    print(rob_one_liner(advice))
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple


# --------------------------------------------------------------------------
# Core formulas
# --------------------------------------------------------------------------

def _ev_bet(
    pot_bb: float,
    bet_bb: float,
    fold_pct: float,
    hero_equity: float,
) -> float:
    """EV of a river bet."""
    total_pot = pot_bb + 2 * bet_bb
    ev_when_called = hero_equity * total_pot - bet_bb
    return round(fold_pct * pot_bb + (1 - fold_pct) * ev_when_called, 2)


def _ev_check(pot_bb: float, hero_equity: float) -> float:
    """EV of checking the river (simplified: equity * pot showdown value)."""
    return round(hero_equity * pot_bb * 0.90, 2)  # 0.90: some EV lost to bluff-catch errors


def _villains_fold_pct(
    bet_fraction: float,   # bet_bb / pot_bb
    villain_wtsd: float,
    villain_af: float,
    villain_vpip: float,
    hero_position: str,
) -> float:
    """
    Estimate villain's fold % to a river bet of size = bet_fraction * pot.
    Based on WTSD, AF, VPIP, and bet size.
    """
    # Base fold: 1 - WTSD (WTSD = went to showdown, so they don't fold much)
    base_fold = 1.0 - villain_wtsd

    # Size adjustment: bigger bet = more folds
    # At 50% pot: base; at 100%: +8%; at 150%: +14%; at 200%: +18%
    size_adj = math.log(max(0.25, bet_fraction)) * 0.10

    # AF adjustment: aggressive players (AF > 2.5) call river more
    af_adj = -(villain_af - 1.5) * 0.04

    # VPIP adjustment: fish (VPIP > 45%) are calling stations
    vpip_adj = -(villain_vpip - 0.30) * 0.20

    # Position: IP gets slightly more folds (villain less confident OOP)
    pos_adj = 0.03 if hero_position.upper() in ('IP', 'BTN', 'CO') else -0.02

    fold_pct = base_fold + size_adj + af_adj + vpip_adj + pos_adj
    return round(min(0.70, max(0.10, fold_pct)), 3)


def _fold_equity_needed(
    pot_bb: float,
    bet_bb: float,
    hero_equity: float,
) -> float:
    """Minimum fold % for bet to outperform check (at alpha equity)."""
    # bet_EV > check_EV when:
    # fold * pot + (1-fold) * (eq * (pot+2bet) - bet) > eq * pot * 0.90
    # Solving for fold:
    check_ev = hero_equity * pot_bb * 0.90
    ev_called = hero_equity * (pot_bb + 2 * bet_bb) - bet_bb
    if ev_called >= check_ev:
        return 0.0   # always bet regardless of folds
    # fold * (pot - ev_called) >= check_ev - ev_called
    if pot_bb <= ev_called:
        return 1.0
    return round((check_ev - ev_called) / (pot_bb - ev_called), 3)


def _optimal_overbet_size(
    pot_bb: float,
    villain_wtsd: float,
    villain_af: float,
    villain_vpip: float,
    hero_nut_advantage: float,
    hero_equity: float,
    hero_position: str,
    effective_stack_bb: float,
) -> Tuple[float, float]:
    """
    Find the overbet size (as fraction of pot) that maximizes EV.
    Returns: (optimal_fraction, optimal_ev)
    """
    best_ev = -999.0
    best_frac = 1.0

    # Test sizes: 0.75, 1.0, 1.20, 1.50, 1.75, 2.00 (and jam if stack allows)
    fracs = [0.75, 1.0, 1.20, 1.50, 1.75, 2.00]
    max_stack_frac = effective_stack_bb / max(pot_bb, 0.1)
    if max_stack_frac <= 3.0:
        fracs.append(min(max_stack_frac, 2.5))

    for frac in fracs:
        bet = pot_bb * frac
        if bet > effective_stack_bb:
            bet = effective_stack_bb
            frac = bet / pot_bb

        fold = _villains_fold_pct(frac, villain_wtsd, villain_af, villain_vpip, hero_position)
        # Nut advantage amplifies EV from overbets (villain calls with worse)
        eq_adj = hero_equity + (hero_nut_advantage - 0.50) * 0.06  # slight equity boost from nut adv
        eq_adj = min(0.95, max(0.10, eq_adj))

        ev = _ev_bet(pot_bb, bet, fold, eq_adj)
        if ev > best_ev:
            best_ev = ev
            best_frac = frac

    return round(best_frac, 2), round(best_ev, 2)


# --------------------------------------------------------------------------
# Overbet suitability scoring
# --------------------------------------------------------------------------

def _overbet_score(
    hero_nut_advantage: float,
    range_is_polarized: bool,
    villain_wtsd: float,
    villain_vpip: float,
    hero_equity: float,
    board_type: str,
    hero_position: str,
) -> float:
    """
    Score from 0.0 to 1.0 indicating how suitable an overbet is.
    >0.65 = overbet recommended; 0.40-0.65 = standard bet; <0.40 = check
    """
    score = 0.0

    # Nut advantage: most critical factor
    score += hero_nut_advantage * 0.35

    # Polarized range: required for overbet
    if range_is_polarized:
        score += 0.20
    else:
        score -= 0.15

    # Villain WTSD: low WTSD (tight) = more folds = better overbets
    wtsd_score = (0.38 - villain_wtsd) * 1.5    # 0.38=neutral; 0.28=+0.15; 0.48=-0.15
    score += max(-0.20, min(0.20, wtsd_score))

    # Villain VPIP: fish are calling stations = bad for overbets
    vpip_score = (0.35 - villain_vpip) * 0.60
    score += max(-0.15, min(0.15, vpip_score))

    # Hero equity: high equity = can size up
    if hero_equity >= 0.75:
        score += 0.15
    elif hero_equity >= 0.55:
        score += 0.05

    # Board type: dry/paired boards favor overbets (villain range is capped)
    if board_type in ('dry', 'paired'):
        score += 0.08
    elif board_type in ('wet', 'monotone'):
        score -= 0.05

    # IP position bonus
    if hero_position.upper() in ('IP', 'BTN', 'CO'):
        score += 0.05

    return round(max(0.0, min(1.0, score)), 3)


@dataclass
class RiverOverbetAdvice:
    # Inputs
    hero_nut_advantage: float       # 0=no advantage, 1=complete nut advantage
    hero_equity: float
    pot_bb: float
    effective_stack_bb: float
    villain_wtsd: float
    villain_af: float
    villain_vpip: float
    hero_position: str
    hero_hand_rank_pct: float
    board_type: str
    range_is_polarized: bool

    # Overbet suitability
    overbet_score: float            # 0-1, how suitable is an overbet
    overbet_recommended: bool       # True if score > 0.65

    # Size analysis (4 standard sizes)
    size_120_ev: float
    size_150_ev: float
    size_175_ev: float
    size_200_ev: float
    size_check_ev: float

    # Optimal size
    optimal_size_fraction: float    # e.g., 1.50 = 150% pot
    optimal_size_bb: float
    optimal_ev: float
    optimal_fold_pct: float

    # Fold equity analysis
    fold_pct_at_optimal: float
    fold_equity_needed: float       # minimum fold % to beat checking
    fold_equity_surplus: float      # actual - needed

    # Decision
    action: str         # 'overbet_200' / 'overbet_175' / 'overbet_150' / 'overbet_120' / 'standard_bet' / 'check'
    action_reason: str
    confidence: str     # 'high' / 'medium' / 'low'

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def advise_river_overbet(
    hero_nut_advantage: float = 0.55,
    hero_equity: float = 0.70,
    pot_bb: float = 30.0,
    effective_stack_bb: float = 70.0,
    villain_wtsd: float = 0.32,
    villain_af: float = 1.8,
    villain_vpip: float = 0.26,
    hero_position: str = 'IP',
    hero_hand_rank_pct: float = 0.82,
    board_type: str = 'dry',
    range_is_polarized: bool = True,
) -> RiverOverbetAdvice:
    """
    Advise on river overbet strategy as the aggressor.

    Args:
        hero_nut_advantage:   0=no nut advantage, 1=complete nuts (e.g., 0.7 if hero
                              has significantly more flushes/straights in range than villain)
        hero_equity:          Hero's overall equity on this river (0.0-1.0)
        pot_bb:               Current pot size in BB
        effective_stack_bb:   Effective stack remaining (hero can bet up to this)
        villain_wtsd:         Villain's went-to-showdown % (low=folds more)
        villain_af:           Villain's aggression factor (high=calls/raises more)
        villain_vpip:         Villain's VPIP (high=calling station)
        hero_position:        'IP' or 'OOP'
        hero_hand_rank_pct:   Hero hand strength (0-1)
        board_type:           'dry', 'medium', 'wet', 'paired', 'monotone'
        range_is_polarized:   True if hero's range is properly polarized (nuts+air)

    Returns:
        RiverOverbetAdvice
    """
    max_bet = min(effective_stack_bb, pot_bb * 2.5)

    # Compute EVs at standard sizes
    evs = {}
    folds_at = {}
    for frac, label in [(1.20, '120'), (1.50, '150'), (1.75, '175'), (2.00, '200')]:
        bet = min(pot_bb * frac, max_bet)
        actual_frac = bet / pot_bb
        fold = _villains_fold_pct(actual_frac, villain_wtsd, villain_af, villain_vpip, hero_position)
        eq_adj = min(0.95, hero_equity + (hero_nut_advantage - 0.50) * 0.06)
        evs[label] = _ev_bet(pot_bb, bet, fold, eq_adj)
        folds_at[label] = fold

    check_ev = _ev_check(pot_bb, hero_equity)

    opt_frac, opt_ev = _optimal_overbet_size(
        pot_bb, villain_wtsd, villain_af, villain_vpip,
        hero_nut_advantage, hero_equity, hero_position, effective_stack_bb,
    )
    opt_bet = min(pot_bb * opt_frac, max_bet)
    opt_fold = _villains_fold_pct(opt_frac, villain_wtsd, villain_af, villain_vpip, hero_position)

    fold_needed = _fold_equity_needed(pot_bb, opt_bet, hero_equity)
    fold_surplus = round(opt_fold - fold_needed, 3)

    ob_score = _overbet_score(
        hero_nut_advantage, range_is_polarized, villain_wtsd, villain_vpip,
        hero_equity, board_type, hero_position,
    )
    ob_recommended = ob_score >= 0.55

    # Decision logic
    if not range_is_polarized:
        action = 'standard_bet'
        reason = 'Range not polarized: overbet requires nuts+air composition; use standard sizing'
        conf = 'high'
    elif hero_nut_advantage < 0.35:
        action = 'standard_bet' if hero_equity >= 0.55 else 'check'
        reason = f'Insufficient nut advantage ({hero_nut_advantage:.0%}): villain calls profitably vs overbet'
        conf = 'medium'
    elif villain_vpip >= 0.45:
        action = 'standard_bet'
        reason = f'Calling station (VPIP={villain_vpip:.0%}): they call overbets with worse; use 75-100% pot instead'
        conf = 'medium'
    elif ob_score >= 0.75:
        if opt_frac >= 1.75:
            action = 'overbet_175' if opt_frac < 2.0 else 'overbet_200'
        else:
            action = 'overbet_150' if opt_frac >= 1.50 else 'overbet_120'
        reason = f'Strong overbet conditions (score={ob_score:.2f}): nut advantage + polarized range + villain folds'
        conf = 'high'
    elif ob_score >= 0.55:
        action = 'overbet_120' if opt_frac >= 1.20 else 'standard_bet'
        reason = f'Moderate overbet conditions (score={ob_score:.2f}): light overbet captures extra EV'
        conf = 'medium'
    elif hero_equity >= 0.55:
        action = 'standard_bet'
        reason = f'Suboptimal overbet conditions (score={ob_score:.2f}): standard bet maximizes EV'
        conf = 'medium'
    else:
        action = 'check'
        reason = 'Low equity + poor overbet conditions: check to showdown or give up'
        conf = 'medium'

    reasoning = (
        f'River {hero_position}: pot={pot_bb:.0f}BB stack={effective_stack_bb:.0f}BB. '
        f'Nut advantage={hero_nut_advantage:.0%} equity={hero_equity:.0%} polarized={range_is_polarized}. '
        f'Villain WTSD={villain_wtsd:.0%} AF={villain_af:.1f} VPIP={villain_vpip:.0%}. '
        f'Overbet score={ob_score:.2f}. Optimal: {opt_frac:.0%}pot ({opt_bet:.0f}BB) EV={opt_ev:+.2f}BB. '
        f'Check EV={check_ev:+.2f}BB. Action: {action}.'
    )

    verdict = (
        f'[ROB {hero_position}|{board_type}|na={hero_nut_advantage:.0%}] {action.upper()} ({conf}) | '
        f'score={ob_score:.2f} opt={opt_frac:.0%}pot({opt_bet:.0f}BB) ev={opt_ev:+.2f}BB | '
        f'fold={opt_fold:.0%} needed={fold_needed:.0%}'
    )

    tips = []

    # Main action tip
    if 'overbet' in action:
        size_pct = int(opt_frac * 100)
        tips.append(
            f'OVERBET {size_pct}% POT ({opt_bet:.0f}BB): '
            f'EV={opt_ev:+.2f}BB vs check={check_ev:+.2f}BB (+{opt_ev-check_ev:.2f}BB gain). '
            f'Villain folds {opt_fold:.0%} (need {fold_needed:.0%} to break even). '
            f'Nut advantage={hero_nut_advantage:.0%}: hero has more nutted combos than villain.'
        )
    elif action == 'standard_bet':
        tips.append(
            f'STANDARD BET (75-100% pot): '
            f'Optimal overbet conditions not met (score={ob_score:.2f}/0.55 threshold). '
            f'Use {round(pot_bb * 0.75, 1):.0f}-{round(pot_bb * 1.0, 1):.0f}BB bet for max EV.'
        )
    else:
        tips.append(
            f'CHECK/GIVE UP: EV={check_ev:+.2f}BB. '
            f'Hero equity ({hero_equity:.0%}) + nut advantage ({hero_nut_advantage:.0%}) insufficient for profitable bet.'
        )

    # Size comparison
    ev_120 = evs['120']
    ev_150 = evs['150']
    tips.append(
        f'SIZE COMPARISON: check={check_ev:+.2f}BB | 120%={ev_120:+.2f}BB | '
        f'150%={ev_150:+.2f}BB | 175%={evs["175"]:+.2f}BB | 200%={evs["200"]:+.2f}BB'
    )

    # Call station warning
    if villain_vpip >= 0.40:
        tips.append(
            f'CALL STATION WARNING: Villain VPIP={villain_vpip:.0%}. '
            f'They call overbets wide. Use value-heavy 75-100% pot bets instead. '
            f'Overbet bluffing is -EV vs this opponent type.'
        )

    # Nut advantage guidance
    if hero_nut_advantage >= 0.65:
        tips.append(
            f'HIGH NUT ADVANTAGE ({hero_nut_advantage:.0%}): '
            f'Hero dominates this board with the most flushes/straights/sets. '
            f'Can comfortably fire large overbets as bluffs without equity risk.'
        )
    elif hero_nut_advantage < 0.40:
        tips.append(
            f'LOW NUT ADVANTAGE ({hero_nut_advantage:.0%}): '
            f'Villain calls overbet with many combos that beat hero bluffs. '
            f'Restrict overbet bluffing; only overbet confirmed value hands.'
        )

    if fold_surplus < -0.10:
        tips.append(
            f'FOLD SHORTFALL: Villain only folds {opt_fold:.0%} but need {fold_needed:.0%}. '
            f'Overbet EV is negative unless hero has strong value. '
            f'Switch to checking or smaller bet.'
        )

    return RiverOverbetAdvice(
        hero_nut_advantage=round(hero_nut_advantage, 3),
        hero_equity=round(hero_equity, 3),
        pot_bb=round(pot_bb, 1),
        effective_stack_bb=round(effective_stack_bb, 1),
        villain_wtsd=round(villain_wtsd, 3),
        villain_af=round(villain_af, 2),
        villain_vpip=round(villain_vpip, 3),
        hero_position=hero_position.upper(),
        hero_hand_rank_pct=round(hero_hand_rank_pct, 3),
        board_type=board_type,
        range_is_polarized=range_is_polarized,
        overbet_score=ob_score,
        overbet_recommended=ob_recommended,
        size_120_ev=evs['120'],
        size_150_ev=evs['150'],
        size_175_ev=evs['175'],
        size_200_ev=evs['200'],
        size_check_ev=check_ev,
        optimal_size_fraction=opt_frac,
        optimal_size_bb=round(opt_bet, 1),
        optimal_ev=opt_ev,
        optimal_fold_pct=opt_fold,
        fold_pct_at_optimal=opt_fold,
        fold_equity_needed=fold_needed,
        fold_equity_surplus=fold_surplus,
        action=action,
        action_reason=reason,
        confidence=conf,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def rob_one_liner(r: RiverOverbetAdvice) -> str:
    return (
        f'[ROB {r.hero_position}|{r.board_type}|na={r.hero_nut_advantage:.0%}] '
        f'{r.action.upper()} ({r.confidence}) | '
        f'score={r.overbet_score:.2f} opt={r.optimal_size_fraction:.0%}pot '
        f'ev={r.optimal_ev:+.2f}BB | fold={r.fold_pct_at_optimal:.0%}'
    )
