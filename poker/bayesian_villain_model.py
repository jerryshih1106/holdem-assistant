"""
Bayesian Villain Model (bayesian_villain_model.py)

Bayesian hand range estimation for villain based on observed actions.
Starts with prior distribution from HUD stats, updates posterior after
each observed action (bet/check/raise/call/fold).

THEORY:
  P(hand | actions) proportional to P(actions | hand) * P(hand)

  Prior P(hand) comes from villain's preflop range and HUD stats.
  Likelihood P(action | hand) comes from GTO action tendencies per hand category.

  Each action updates the distribution multiplicatively:
    posterior[cat] = prior[cat] * likelihood(action | cat)
  Then normalize so all categories sum to 1.0.

  LIKELIHOOD TABLES:
    Bet on dry flop:
      nuts/near_nuts:  0.60 (many slowplay)
      set:             0.75 (build pot)
      two_pair:        0.70
      overpair:        0.65
      top_pair:        0.55
      flush_draw:      0.35 (semi-bluff)
      air:             0.20 (bluff)

    Check on dry flop:
      nuts:            0.40 (trap)
      set:             0.25 (trap)
      top_pair:        0.45 (pot control)
      flush_draw:      0.65 (take free card)
      air:             0.80 (give up)

    Raise:
      nuts:            0.30 (often slow)
      set:             0.40 (semi-committed)
      flush_draw:      0.20 (semi-bluff)
      air:             0.05 (pure bluff)

  KEY INSIGHT: A passive villain (AF < 1.5) who raises has a very strong hand.
  An aggressive villain (AF > 3) who raises has a wider range.

DISTINCT FROM:
  hand_reading_guide.py:   Line-based hand range lookup (static table)
  range_narrower.py:       Sequential Bayesian narrower (street-level)
  THIS MODULE:             Action-by-action Bayesian posterior update;
                           outputs probability distribution over categories.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


HAND_CATEGORIES = [
    'nuts', 'near_nuts', 'full_house', 'flush', 'straight',
    'set', 'two_pair', 'overpair', 'top_pair', 'middle_pair',
    'bottom_pair', 'combo_draw', 'flush_draw', 'oesd', 'gutshot', 'air',
]

# Likelihood of action given hand category
# Keys: (action_type, board_texture)
# Values: dict of {hand_cat: likelihood}

_BASE_LIKELIHOOD: Dict[str, Dict[str, float]] = {
    'bet': {
        'nuts':         0.55,
        'near_nuts':    0.65,
        'full_house':   0.70,
        'flush':        0.72,
        'straight':     0.72,
        'set':          0.75,
        'two_pair':     0.68,
        'overpair':     0.62,
        'top_pair':     0.52,
        'middle_pair':  0.28,
        'bottom_pair':  0.18,
        'combo_draw':   0.40,
        'flush_draw':   0.35,
        'oesd':         0.28,
        'gutshot':      0.18,
        'air':          0.20,
    },
    'check': {
        'nuts':         0.45,   # trap check
        'near_nuts':    0.35,
        'full_house':   0.30,
        'flush':        0.28,
        'straight':     0.28,
        'set':          0.25,
        'two_pair':     0.32,
        'overpair':     0.38,
        'top_pair':     0.48,
        'middle_pair':  0.72,
        'bottom_pair':  0.82,
        'combo_draw':   0.60,
        'flush_draw':   0.65,
        'oesd':         0.72,
        'gutshot':      0.82,
        'air':          0.80,
    },
    'raise': {
        'nuts':         0.35,
        'near_nuts':    0.30,
        'full_house':   0.38,
        'flush':        0.40,
        'straight':     0.40,
        'set':          0.40,
        'two_pair':     0.28,
        'overpair':     0.22,
        'top_pair':     0.12,
        'middle_pair':  0.06,
        'bottom_pair':  0.04,
        'combo_draw':   0.20,
        'flush_draw':   0.18,
        'oesd':         0.12,
        'gutshot':      0.06,
        'air':          0.08,
    },
    'call': {
        'nuts':         0.10,   # nuts rarely calls, mostly raises
        'near_nuts':    0.40,
        'full_house':   0.20,
        'flush':        0.25,
        'straight':     0.28,
        'set':          0.35,
        'two_pair':     0.45,
        'overpair':     0.48,
        'top_pair':     0.52,
        'middle_pair':  0.38,
        'bottom_pair':  0.22,
        'combo_draw':   0.55,
        'flush_draw':   0.52,
        'oesd':         0.45,
        'gutshot':      0.35,
        'air':          0.15,
    },
    'fold': {
        'nuts':         0.00,
        'near_nuts':    0.00,
        'full_house':   0.00,
        'flush':        0.01,
        'straight':     0.01,
        'set':          0.02,
        'two_pair':     0.05,
        'overpair':     0.10,
        'top_pair':     0.20,
        'middle_pair':  0.40,
        'bottom_pair':  0.55,
        'combo_draw':   0.28,
        'flush_draw':   0.30,
        'oesd':         0.42,
        'gutshot':      0.58,
        'air':          0.68,
    },
}

# Texture adjustment multipliers for likelihood
_TEXTURE_ADJ: Dict[str, Dict[str, float]] = {
    # On wet boards: draws more likely; value bet more cautious
    'wet': {
        'flush_draw': 1.30,
        'combo_draw': 1.25,
        'oesd':       1.20,
        'air_bet':    0.85,    # less bluffing on wet
    },
    'dry': {
        'air':       1.15,    # more bluffing on dry
        'flush_draw': 0.80,   # less FD on dry
    },
    'monotone': {
        'flush_draw': 1.50,
        'flush':      1.20,
    },
    'paired': {
        'full_house': 1.30,
        'set':        1.15,
        'air':        0.90,   # less bluffing on paired (missed draws)
    },
}

# Villain AF modifier: aggressive AF means more bluffs and semi-bluffs
def _af_likelihood_mult(villain_af: float, hand_cat: str) -> float:
    if villain_af >= 3.0:
        if hand_cat in ('air', 'gutshot', 'flush_draw', 'oesd'):
            return 1.25
        if hand_cat in ('nuts', 'set'):
            return 0.90   # aggressive may check strong hands less
    elif villain_af < 1.5:
        if hand_cat in ('air', 'gutshot'):
            return 0.70   # passive rarely bluffs
        if hand_cat in ('nuts', 'set', 'full_house'):
            return 1.15   # passive check-raises = nuts
    return 1.0


def _get_likelihood(
    action: str,
    hand_cat: str,
    board_texture: str,
    villain_af: float,
) -> float:
    base = _BASE_LIKELIHOOD.get(action, {}).get(hand_cat, 0.25)
    adj = _TEXTURE_ADJ.get(board_texture, {}).get(hand_cat, 1.0)
    af_mult = _af_likelihood_mult(villain_af, hand_cat)
    return base * adj * af_mult


def _uniform_prior(vpip: float = 0.30) -> Dict[str, float]:
    """
    Build prior probability distribution over hand categories
    based on villain's VPIP. Wide VPIP = more weak hands in range.
    """
    if vpip >= 0.45:
        # Very loose: many weak hands
        weights = {
            'nuts': 0.02, 'near_nuts': 0.02, 'full_house': 0.01,
            'flush': 0.02, 'straight': 0.02, 'set': 0.04,
            'two_pair': 0.06, 'overpair': 0.06, 'top_pair': 0.12,
            'middle_pair': 0.10, 'bottom_pair': 0.08,
            'combo_draw': 0.04, 'flush_draw': 0.08, 'oesd': 0.08,
            'gutshot': 0.08, 'air': 0.17,
        }
    elif vpip <= 0.20:
        # Tight: concentrated in strong hands
        weights = {
            'nuts': 0.04, 'near_nuts': 0.04, 'full_house': 0.02,
            'flush': 0.03, 'straight': 0.03, 'set': 0.06,
            'two_pair': 0.08, 'overpair': 0.10, 'top_pair': 0.15,
            'middle_pair': 0.12, 'bottom_pair': 0.06,
            'combo_draw': 0.03, 'flush_draw': 0.07, 'oesd': 0.07,
            'gutshot': 0.05, 'air': 0.05,
        }
    else:
        # Standard: balanced distribution
        weights = {
            'nuts': 0.03, 'near_nuts': 0.03, 'full_house': 0.01,
            'flush': 0.02, 'straight': 0.02, 'set': 0.05,
            'two_pair': 0.07, 'overpair': 0.08, 'top_pair': 0.13,
            'middle_pair': 0.11, 'bottom_pair': 0.07,
            'combo_draw': 0.04, 'flush_draw': 0.08, 'oesd': 0.08,
            'gutshot': 0.07, 'air': 0.11,
        }
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def _normalize(dist: Dict[str, float]) -> Dict[str, float]:
    total = sum(dist.values())
    if total <= 0:
        return {k: 1.0 / len(dist) for k in dist}
    return {k: v / total for k, v in dist.items()}


def _update_posterior(
    prior: Dict[str, float],
    action: str,
    board_texture: str,
    villain_af: float,
) -> Dict[str, float]:
    posterior = {}
    for cat in HAND_CATEGORIES:
        likelihood = _get_likelihood(action, cat, board_texture, villain_af)
        posterior[cat] = prior.get(cat, 0.0) * likelihood
    return _normalize(posterior)


def _top_categories(dist: Dict[str, float], n: int = 3) -> List[str]:
    return sorted(dist, key=lambda k: -dist[k])[:n]


@dataclass
class VillainModelState:
    """Mutable state of the Bayesian villain model for one hand."""
    villain_af: float
    villain_vpip: float
    board_texture: str
    prior: Dict[str, float]
    posterior: Dict[str, float]
    action_history: List[str] = field(default_factory=list)
    top3_categories: List[str] = field(default_factory=list)
    most_likely_category: str = 'top_pair'
    most_likely_prob: float = 0.0
    confidence: str = 'low'


def _confidence_level(most_likely_prob: float, n_updates: int) -> str:
    if n_updates == 0:
        return 'prior_only'
    if most_likely_prob >= 0.50 and n_updates >= 2:
        return 'high'
    if most_likely_prob >= 0.35 or n_updates >= 2:
        return 'medium'
    return 'low'


@dataclass
class BayesianVillainResult:
    villain_af: float
    villain_vpip: float
    board_texture: str
    actions_observed: List[str]
    distribution: Dict[str, float]
    top3_categories: List[str]
    most_likely_category: str
    most_likely_prob: float
    confidence: str
    hero_action_advice: str
    tips: List[str] = field(default_factory=list)


def build_villain_model(
    villain_af: float = 2.0,
    villain_vpip: float = 0.30,
    board_texture: str = 'dry',
    actions_observed: Optional[List[str]] = None,
) -> BayesianVillainResult:
    """
    Build a Bayesian villain hand distribution based on observed actions.

    Args:
        villain_af:        Villain's aggression factor
        villain_vpip:      Villain's VPIP (0-1 decimal)
        board_texture:     'dry' / 'wet' / 'monotone' / 'paired'
        actions_observed:  List of observed actions: ['bet', 'call', 'check', 'raise', 'fold']

    Returns:
        BayesianVillainResult
    """
    if actions_observed is None:
        actions_observed = []

    prior = _uniform_prior(villain_vpip)
    posterior = dict(prior)

    for action in actions_observed:
        posterior = _update_posterior(posterior, action, board_texture, villain_af)

    top3 = _top_categories(posterior, 3)
    most_likely = top3[0]
    most_likely_prob = posterior.get(most_likely, 0.0)
    confidence = _confidence_level(most_likely_prob, len(actions_observed))

    # Hero action advice based on most likely villain category
    if most_likely in ('nuts', 'near_nuts', 'full_house', 'set', 'flush', 'straight'):
        hero_advice = f'CAUTION: Villain likely has {most_likely} ({most_likely_prob:.0%}). Avoid thin value; fold marginal hands to pressure.'
    elif most_likely in ('two_pair', 'overpair'):
        hero_advice = f'MEDIUM STRENGTH: Villain likely has {most_likely}. Hero can value-bet strong hands; bluff catch selectively.'
    elif most_likely in ('top_pair', 'middle_pair'):
        hero_advice = f'THIN: Villain likely {most_likely}. Hero can value-bet two_pair+ for 2-3 streets; check marginal made hands.'
    elif most_likely in ('flush_draw', 'combo_draw', 'oesd'):
        hero_advice = f'VILLAIN ON DRAW: Likely {most_likely} ({most_likely_prob:.0%}). Bet for protection; deny equity on wet boards.'
    elif most_likely == 'air':
        hero_advice = f'VILLAIN BLUFFING: Likely air ({most_likely_prob:.0%}). Call down with showdown value; avoid big folds.'
    else:
        hero_advice = f'Villain likely {most_likely} ({most_likely_prob:.0%}). Proceed with normal strategy.'

    tips = []
    tips.append(
        f'BAYESIAN MODEL ({len(actions_observed)} updates, confidence={confidence}): '
        f'Top categories: {", ".join(f"{c}({posterior.get(c,0):.0%})" for c in top3)}. '
        f'Most likely: {most_likely} at {most_likely_prob:.0%}.'
    )

    if len(actions_observed) == 0:
        tips.append(
            f'PRIOR ONLY: No actions observed. Distribution based on VPIP={villain_vpip:.0%} only. '
            f'Observe villain actions to refine.'
        )
    else:
        tips.append(
            f'UPDATED with: {" -> ".join(actions_observed)}. '
            f'{"High confidence -- strong range signal." if confidence == "high" else "More actions needed for high confidence."}'
        )

    tips.append(
        f'VILLAIN PROFILE: AF={villain_af:.1f} ({"aggressive" if villain_af>=3.0 else "passive" if villain_af<1.5 else "balanced"}), '
        f'VPIP={villain_vpip:.0%} ({"loose" if villain_vpip>0.40 else "tight" if villain_vpip<0.22 else "standard"}). '
        f'Bet range=~{posterior.get("nuts",0)+posterior.get("near_nuts",0)+posterior.get("set",0)+posterior.get("two_pair",0):.0%} strong value.'
    )

    return BayesianVillainResult(
        villain_af=villain_af,
        villain_vpip=villain_vpip,
        board_texture=board_texture,
        actions_observed=actions_observed,
        distribution=posterior,
        top3_categories=top3,
        most_likely_category=most_likely,
        most_likely_prob=most_likely_prob,
        confidence=confidence,
        hero_action_advice=hero_advice,
        tips=tips,
    )


def bvm_one_liner(r: BayesianVillainResult) -> str:
    top3_str = '/'.join(
        f'{c}({r.distribution.get(c,0):.0%})' for c in r.top3_categories
    )
    return (
        f'[BVM {r.most_likely_category}|{r.board_texture}|{r.confidence}] '
        f'{r.most_likely_prob:.0%} | '
        f'top3: {top3_str}'
    )
