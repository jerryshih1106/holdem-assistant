"""
Villain Bet Size Reader (villain_bet_size_read.py)

Villain bet size is one of the most reliable live poker tells. Many players
unconsciously size their bets differently with different hand strengths:

Bet size categories and typical meanings:
  Micro (0-25% pot):
    - Blocking bet: villain has showdown value but fears a large bet
    - OR: very weak probe to "see where they're at"
    - Rarely a value bet or bluff with any equity
    - Action: almost always call/raise; rarely fold

  Small (25-45% pot):
    - Thin value (top pair, medium pair) — not confident enough to bet big
    - Small bluff (scared to invest more)
    - OR: balanced range bet (GTO players)
    - Action: call with equity > 25%; raise strong hands

  Standard (45-70% pot):
    - Balanced range bet (polarized or merged)
    - Value hands and bluffs mixed
    - Most common GTO sizing
    - Action: call/fold based on equity vs range

  Large (70-100% pot):
    - Strong value (top pair+, sets, two pair)
    - OR: large bluff attempting to deny equity
    - Often shows less balance (recreational players bet large with strong hands)
    - Action: need 33-38% equity to call

  Overbet (100-150% pot):
    - VERY polarized: nuts or complete air
    - Recreational players: almost always have it
    - GTO players: balanced overbets with nut advantage
    - Action: need 38-43% equity to call; raise with best hands

  Massive overbet (150%+ pot):
    - Extreme polarization
    - River: villain committed to this bluff or has the nuts
    - Rarely seen from balanced players
    - Action: fold unless hero has strong call (40-50%+ equity)

Player-type adjustments:
  - Fish/calling station: larger bets MORE often mean value (they under-bluff large)
  - Nit/tight player: ANY large bet = strong hand (very rarely bluff large)
  - LAG/maniac: large bets could be anything (less reliable size tell)
  - Unknown: use population tendency (size ~ value correlation)

Usage:
    from poker.villain_bet_size_read import read_bet_size, BetSizeRead
    result = read_bet_size(
        bet_pct=1.20,
        pot_bb=30.0,
        street='river',
        villain_vpip=0.45,
        villain_af=1.2,
        villain_wtsd=0.42,
        hero_equity=0.48,
    )
    print(result.likely_category, result.recommended_action)
"""

from dataclasses import dataclass, field
from typing import List, Tuple


def _bet_category(bet_pct: float) -> str:
    """Classify bet size into category."""
    if bet_pct < 0.25:
        return 'micro'
    if bet_pct < 0.45:
        return 'small'
    if bet_pct < 0.70:
        return 'standard'
    if bet_pct < 1.05:
        return 'large'
    if bet_pct < 1.55:
        return 'overbet'
    return 'massive_overbet'


def _required_equity(bet_pct: float) -> float:
    """Break-even equity to call."""
    return round(bet_pct / (1 + 2 * bet_pct), 4)


def _value_probability(
    bet_category: str,
    villain_vpip: float,
    villain_af: float,
    villain_wtsd: float,
    street: str,
) -> float:
    """
    Estimated probability villain has a value hand (vs bluff).
    Higher = more likely value hand.
    """
    # Base probability by size
    base = {
        'micro': 0.45,          # could be block or weak value
        'small': 0.55,          # slight value bias
        'standard': 0.60,       # balanced
        'large': 0.70,          # skewed toward value (most players)
        'overbet': 0.55,        # polarized: could be either extreme
        'massive_overbet': 0.50,
    }.get(bet_category, 0.60)

    # Fish/calling_station: rarely large bluffs
    if villain_vpip > 0.45 and villain_af < 1.5:
        if bet_category in ('large', 'overbet', 'massive_overbet'):
            base += 0.20  # fish bet big with strong hands
    # Nit/tight: all large bets are value
    elif villain_vpip < 0.22 and villain_af < 2.0:
        if bet_category in ('large', 'overbet', 'massive_overbet'):
            base += 0.25
    # LAG/maniac: more balanced large bets
    elif villain_vpip > 0.40 and villain_af >= 3.0:
        base -= 0.10  # more likely to bluff large too

    # High WTSD: calls a lot, which correlates with more value hands (less bluffing)
    if villain_wtsd > 0.38 and bet_category in ('large', 'overbet'):
        base += 0.08  # station-type players have value more often when betting large

    # River: value hands bet more often (draws bricked → less bluffing)
    if street == 'river':
        base += 0.05

    return round(min(0.95, max(0.20, base)), 3)


def _likely_hand_category(
    bet_category: str,
    value_prob: float,
    villain_vpip: float,
    street: str,
) -> str:
    """Most likely hand category villain holds."""
    if bet_category == 'micro':
        return 'blocker_or_weak_value'
    if bet_category == 'small':
        return 'thin_value_or_probe' if value_prob >= 0.55 else 'semi_bluff'
    if bet_category == 'standard':
        return 'value_or_bluff'
    if bet_category == 'large':
        if value_prob >= 0.75:
            return 'strong_value'
        return 'top_pair_or_bluff'
    if bet_category in ('overbet', 'massive_overbet'):
        if value_prob >= 0.65:
            return 'nuts_or_near_nuts'
        return 'polarized_nuts_or_air'
    return 'unknown'


def _action_advice(
    bet_category: str,
    hero_equity: float,
    required_eq: float,
    value_prob: float,
    has_blocker: bool = False,
) -> Tuple[str, str]:
    """(action, reasoning)"""
    eq_margin = hero_equity - required_eq

    if bet_category == 'micro':
        # Nearly always call/raise
        if hero_equity >= 0.40:
            return ('raise', f'Micro bet ({bet_category}): raise to deny equity and extract value. '
                    f'Hero equity {hero_equity:.0%} > required {required_eq:.0%}. '
                    f'Villain rarely has a strong hand.')
        return ('call', f'Micro bet: call cheaply and re-evaluate.')

    if eq_margin >= 0.10:
        return ('raise', f'Hero equity ({hero_equity:.0%}) well above required ({required_eq:.0%}). '
                f'Raise with strong hands — villain may be betting thin.')

    if eq_margin >= 0.02:
        if bet_category in ('overbet', 'massive_overbet') and value_prob >= 0.65:
            return ('call', f'Overbet: profitable call ({hero_equity:.0%} > {required_eq:.0%}). '
                    f'Villain likely has strong value — do not raise.')
        return ('call', f'Profitable call: {hero_equity:.0%} equity > {required_eq:.0%} required. '
                f'Villain value probability: {value_prob:.0%}.')

    if eq_margin >= -0.03:
        # Marginal — consider blocker
        if has_blocker and bet_category in ('overbet', 'massive_overbet'):
            return ('call', f'Marginal call with blocker. '
                    f'Blocker reduces villain nut combos → call is closer.')
        return ('fold', f'Marginal: {hero_equity:.0%} equity slightly below {required_eq:.0%} required. '
                f'Lean fold — too close without blocker advantage.')

    return ('fold', f'Fold: equity ({hero_equity:.0%}) well below required ({required_eq:.0%}). '
            f'Villain likely has strong value ({value_prob:.0%}).')


@dataclass
class BetSizeRead:
    """Analysis of villain's bet size as a range tell."""
    bet_pct: float
    bet_bb: float
    pot_bb: float
    street: str
    villain_vpip: float
    villain_af: float
    hero_equity: float

    # Classification
    bet_category: str          # 'micro', 'small', 'standard', 'large', 'overbet', 'massive_overbet'
    value_probability: float   # P(villain has value hand)
    bluff_probability: float   # P(villain is bluffing)
    likely_hand_category: str  # description of villain's likely holdings

    # Decision
    required_equity: float
    mdf: float                 # Minimum Defense Frequency
    recommended_action: str    # 'call', 'fold', 'raise'
    action_reasoning: str

    # Notes
    size_tell_note: str
    player_type_note: str
    strategic_tips: List[str] = field(default_factory=list)


def read_bet_size(
    bet_pct: float = 0.75,
    pot_bb: float = 30.0,
    street: str = 'river',
    villain_vpip: float = 0.35,
    villain_af: float = 1.8,
    villain_wtsd: float = 0.32,
    hero_equity: float = 0.45,
    has_blocker: bool = False,
) -> BetSizeRead:
    """
    Read villain's bet size as a range tell.

    Args:
        bet_pct:          Villain bet size as fraction of pot (e.g., 0.75 = 75%)
        pot_bb:           Current pot before villain bet
        street:           'flop', 'turn', 'river'
        villain_vpip:     Villain's VPIP (0-1)
        villain_af:       Villain's aggression factor
        villain_wtsd:     Villain's went-to-showdown (0-1)
        hero_equity:      Hero's equity vs villain's range (0-1)
        has_blocker:      Hero has a key blocker card

    Returns:
        BetSizeRead
    """
    bet_bb = round(pot_bb * bet_pct, 1)
    category = _bet_category(bet_pct)
    req_eq = _required_equity(bet_pct)
    mdf = round(1.0 - bet_pct / (1.0 + bet_pct), 3)
    value_prob = _value_probability(category, villain_vpip, villain_af, villain_wtsd, street)
    bluff_prob = round(1.0 - value_prob, 3)
    hand_cat = _likely_hand_category(category, value_prob, villain_vpip, street)
    action, reasoning = _action_advice(category, hero_equity, req_eq, value_prob, has_blocker)

    # Size tell note
    tell_notes = {
        'micro': 'Micro bet: usually a blocker bet from OOP or a weak probe. Very rarely strong value.',
        'small': 'Small bet: thin value, blocking bet, or tentative bluff. Raise often profitable.',
        'standard': 'Standard sizing: balanced range. Cannot make strong reads — apply equity math.',
        'large': 'Large bet: most players polarize to value. Recreational players especially have it.',
        'overbet': 'Overbet: extreme polarization. Recreational players almost never overbet bluff.',
        'massive_overbet': 'Massive overbet: nutted hand or desperate bluff. Fold most hands; call with nuts.',
    }
    tell = tell_notes.get(category, 'Unknown sizing.')

    # Player type note
    if villain_vpip > 0.45 and villain_af < 1.5:
        ptype = f'Fish/calling station (VPIP={villain_vpip:.0%}): large bets almost always value.'
    elif villain_vpip < 0.22:
        ptype = f'Nit/tight (VPIP={villain_vpip:.0%}): any large bet = strong hand. Fold unless nuts.'
    elif villain_vpip > 0.40 and villain_af >= 3.0:
        ptype = f'LAG/maniac (VPIP={villain_vpip:.0%} AF={villain_af:.1f}): large bets less reliable — may bluff any size.'
    else:
        ptype = f'Regular player: use standard equity analysis. Bet size reliable at extremes.'

    tips = [f'Required equity to call {bet_pct:.0%}pot: {req_eq:.0%}. MDF: {mdf:.0%}.']
    if street == 'river' and category in ('overbet', 'massive_overbet'):
        tips.append(
            'River overbet: draws have bricked. Villain is either very strong or bluffing '
            'with a missed draw. Blockers to villain\'s nut hands are most important.'
        )
    if category == 'micro' and street == 'river':
        tips.append(
            'River micro-bet: typically a blocking bet. Hero should raise to deny '
            'showdown value and charge villain for a cheap river. Fold only vs nutted hands.'
        )
    if villain_wtsd > 0.40 and category in ('large', 'overbet'):
        tips.append(
            f'High WTSD villain ({villain_wtsd:.0%}): when they DO bet large, '
            f'they almost certainly have value. They do not bluff-bet large often.'
        )

    return BetSizeRead(
        bet_pct=round(bet_pct, 3),
        bet_bb=bet_bb,
        pot_bb=round(pot_bb, 1),
        street=street,
        villain_vpip=villain_vpip,
        villain_af=villain_af,
        hero_equity=round(hero_equity, 3),
        bet_category=category,
        value_probability=value_prob,
        bluff_probability=bluff_prob,
        likely_hand_category=hand_cat,
        required_equity=req_eq,
        mdf=mdf,
        recommended_action=action,
        action_reasoning=reasoning,
        size_tell_note=tell,
        player_type_note=ptype,
        strategic_tips=tips,
    )


def bet_size_read_one_liner(result: BetSizeRead) -> str:
    return (
        f'[BSR {result.bet_pct:.0%}pot|{result.bet_category}] '
        f'{result.recommended_action.upper()} | '
        f'value_prob={result.value_probability:.0%} | '
        f'req_eq={result.required_equity:.0%} | '
        f'{result.likely_hand_category}'
    )
