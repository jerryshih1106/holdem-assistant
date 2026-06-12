"""
Turn Runout Analysis (turn_runout_analysis.py)

Analyzes how the turn card changes range advantages, c-bet frequencies,
and strategic adjustments. More comprehensive than turn_scare_card_advisor.py
(which covers scary cards only) - this covers ALL turn card types and
computes the FULL strategic picture.

TURN CARD CATEGORIES:
  1. Blank: No meaningful change to ranges (e.g., 2 on A-K-7 board)
  2. Pairs the board: Reduces straight/flush draws; changes value range
  3. Flush completes: Critical for FD holders; changes equity dramatically
  4. Straight completes: Changes who has the nuts
  5. Broadway: High card arrives; changes PFR range advantage
  6. Scare card: Ace or overcard that hits PFR range hard

  RANGE ADVANTAGE SHIFT:
  - For each card type, compute how advantage shifts between PFR and caller
  - PFR advantage is most stable on blanks
  - Low cards: caller (suited connectors, small pairs) gain
  - High cards: PFR (opens more premiums) gains
  - Flush completes: advantage shifts to whoever has flush blockers

KEY CALCULATIONS:
  1. New PFR cbet frequency given turn card type
  2. Optimal bet sizing adjustment
  3. Hero's range hit percentage for each card type
  4. Villain's range benefit from turn card

DISTINCT FROM:
  turn_scare_card_advisor.py:  Only handles scare cards (ace/king arriving)
  turn_texture_change.py:      Size adjustment for texture changes
  turn_check_raise.py:         Check-raise situations on turn
  THIS MODULE:                 COMPREHENSIVE turn card analysis;
                               ALL card types; full range-advantage computation;
                               optimal cbet freq + sizing for EVERY turn scenario.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Range benefit for each turn card type (for PFR)
# Positive = PFR benefits; negative = caller benefits
PFR_RANGE_BENEFIT: dict = {
    'blank':              0.10,   # slight PFR advantage maintained
    'pairs_board':       -0.05,   # pairs often help caller (trips/FH for slowplays)
    'flush_completes':   -0.20,   # callers have more FD (wider range)
    'straight_completes': 0.00,   # depends on board; roughly neutral
    'broadway':           0.15,   # PFR opens broadway heavy
    'scare_ace':          0.20,   # PFR has more aces in range
    'scare_king':         0.12,   # PFR has some kings; caller can have KX too
    'low_card':          -0.15,   # callers have more low suited connectors/pairs
}

# Cbet frequency adjustment on turn given card type (from baseline)
CBET_ADJ_BY_CARD: dict = {
    'blank':              1.00,   # no change from flop cbet frequency
    'pairs_board':        0.80,   # pair reduces draw equity; bet less for protection
    'flush_completes':    0.65,   # villain may have flush; check more
    'straight_completes': 0.70,
    'broadway':           1.10,   # ace/king hits PFR range; bet more
    'scare_ace':          1.15,
    'scare_king':         1.05,
    'low_card':           0.85,   # low card helps caller; check more
}

# Optimal bet sizing adjustment
SIZE_ADJ_BY_CARD: dict = {
    'blank':              1.00,
    'pairs_board':        0.75,   # smaller after pairing (block misses)
    'flush_completes':    1.25,   # larger to charge draws if any left
    'straight_completes': 1.20,
    'broadway':           1.10,
    'scare_ace':          1.00,
    'scare_king':         0.90,
    'low_card':           0.90,
}

# Flop c-bet baselines (IP PFR)
FLOP_CBET_BASE: dict = {
    'dry':      0.62,
    'medium':   0.52,
    'wet':      0.45,
    'paired':   0.55,
    'monotone': 0.40,
}


def _classify_turn_card(
    flop_cards: list,
    turn_card: str,
) -> str:
    """Classify the turn card type given flop."""
    if not turn_card or len(turn_card) < 2:
        return 'blank'

    turn_rank = turn_card[0].upper()
    turn_suit = turn_card[-1].lower()

    rank_map = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,'7':7,
                '6':6,'5':5,'4':4,'3':3,'2':2}
    turn_rank_int = rank_map.get(turn_rank, 7)

    # Check if board pairs
    flop_ranks = [c[0].upper() for c in flop_cards[:3] if c]
    if turn_rank in flop_ranks:
        return 'pairs_board'

    # Check for flush
    flop_suits = [c[-1].lower() for c in flop_cards[:3] if len(c) >= 2]
    flush_suit_count = flop_suits.count(turn_suit)
    if flush_suit_count >= 2:
        return 'flush_completes'

    # Check for straight potential (simplified)
    flop_rank_ints = [rank_map.get(r, 7) for r in flop_ranks]
    all_ranks = sorted(flop_rank_ints + [turn_rank_int])
    if len(all_ranks) >= 4:
        span = max(all_ranks) - min(all_ranks)
        if span <= 4:
            return 'straight_completes'

    # Broadway check
    if turn_rank in ('A', 'K', 'Q', 'J', 'T'):
        if turn_rank in ('A',):
            return 'scare_ace'
        if turn_rank in ('K',):
            return 'scare_king'
        return 'broadway'

    # Low card
    if turn_rank_int <= 7:
        return 'low_card'

    return 'blank'


def _compute_turn_cbet(
    card_type: str,
    flop_texture: str,
    hero_position: str,
    hand_category: str,
    villain_af: float,
) -> float:
    base = FLOP_CBET_BASE.get(flop_texture, 0.55)
    adj = CBET_ADJ_BY_CARD.get(card_type, 1.0)
    freq = base * adj

    if hero_position in ('oop',):
        freq *= 0.80

    # Hand-specific adjustments
    if hand_category in ('set', 'flush', 'straight', 'full_house', 'nuts'):
        freq = min(1.0, freq * 1.20)
    elif hand_category in ('air', 'gutshot'):
        freq = max(0.05, freq * 0.70)

    # Villain adjustment
    if villain_af >= 3.0:
        freq *= 0.85  # bluff less vs aggressive; they will call/raise
    elif villain_af < 1.5:
        freq *= 1.10  # bet more vs passive; they won't bet for you

    return round(min(1.0, max(0.05, freq)), 2)


def _range_advantage_label(pfr_benefit: float) -> str:
    if pfr_benefit >= 0.15:
        return 'strong_pfr_advantage'
    elif pfr_benefit >= 0.05:
        return 'slight_pfr_advantage'
    elif pfr_benefit >= -0.05:
        return 'neutral'
    elif pfr_benefit >= -0.15:
        return 'slight_caller_advantage'
    else:
        return 'strong_caller_advantage'


@dataclass
class TurnRunoutResult:
    flop_texture: str
    turn_card: str
    card_type: str
    pfr_benefit: float
    range_advantage: str
    turn_cbet_freq: float
    bet_size_adjustment: float
    hero_position: str
    hand_category: str

    verdict: str
    reasoning: str
    tips: List[str] = field(default_factory=list)


def analyze_turn_runout(
    flop_cards: Optional[list] = None,
    turn_card: str = '2s',
    flop_texture: str = 'dry',
    hero_position: str = 'ip',
    hand_category: str = 'top_pair',
    villain_af: float = 2.0,
    hero_is_pfr: bool = True,
    flop_cbet_freq_used: float = 0.60,
) -> TurnRunoutResult:
    """
    Analyze the turn card and compute strategic adjustments.

    Args:
        flop_cards:         Flop cards (e.g., ['As', 'Kh', '7c'])
        turn_card:          Turn card (e.g., '2s')
        flop_texture:       Flop texture
        hero_position:      'ip' / 'oop'
        hand_category:      Hero's hand category
        villain_af:         Villain's aggression factor
        hero_is_pfr:        Is hero the preflop raiser?
        flop_cbet_freq_used: Hero's actual flop cbet frequency

    Returns:
        TurnRunoutResult
    """
    if flop_cards is None:
        flop_cards = ['As', 'Kh', '7c']

    card_type = _classify_turn_card(flop_cards, turn_card)
    pfr_benefit = PFR_RANGE_BENEFIT.get(card_type, 0.0)
    if not hero_is_pfr:
        pfr_benefit = -pfr_benefit  # caller view
    range_adv = _range_advantage_label(pfr_benefit)
    turn_freq = _compute_turn_cbet(card_type, flop_texture, hero_position, hand_category, villain_af)
    size_adj = SIZE_ADJ_BY_CARD.get(card_type, 1.0)

    verdict = (
        f'[TRA {turn_card}={card_type}|{hero_position}|{hand_category}] '
        f'cbet={turn_freq:.0%} size_adj={size_adj:.2f}x | {range_adv}'
    )

    reasoning = (
        f'Turn card {turn_card}: type={card_type}. '
        f'{"PFR" if hero_is_pfr else "Caller"} benefit={pfr_benefit:+.2f}. '
        f'Range advantage: {range_adv}. '
        f'Turn cbet recommendation: {turn_freq:.0%} ({size_adj:.0%} size adjustment).'
    )

    tips = []

    tips.append(
        f'TURN CARD TYPE: {turn_card} = {card_type}. '
        f'{"PFR" if hero_is_pfr else "Caller"} range benefit: {pfr_benefit:+.2f}. '
        f'Advantage: {range_adv}.'
    )

    tips.append(
        f'CBET DECISION: {flop_texture} board, {card_type} turn. '
        f'Recommended cbet: {turn_freq:.0%} '
        f'(flop base: {FLOP_CBET_BASE.get(flop_texture, 0.55):.0%} x {CBET_ADJ_BY_CARD.get(card_type, 1.0):.2f} adj). '
        f'Size: adjust x{size_adj:.2f} vs flop size.'
    )

    if card_type in ('flush_completes', 'straight_completes'):
        tips.append(
            f'DRAW COMPLETES: {card_type} on turn. '
            f'{"Villain may have hit. Check marginal hands." if pfr_benefit < 0 else "You may have hit. Bet strong value."} '
            f'Cbet reduced to {turn_freq:.0%}.'
        )
    elif card_type == 'pairs_board':
        tips.append(
            f'BOARD PAIRS: Pairs reduce straight/flush draws but add full-house potential. '
            f'Sets and two-pair now more vulnerable to FH possibilities. '
            f'Check trips/boat hands to trap. Bluff on paired boards (most draws missed).'
        )
    elif card_type in ('scare_ace', 'scare_king', 'broadway'):
        tips.append(
            f'HIGH CARD TURN: {turn_card} is strong PFR card. '
            f'PFR opened with more A/K hands. '
            f'{"Hero PFR: range advantage -- bet confidently." if hero_is_pfr else "Villain is PFR: respect their c-bet. Fold marginal pairs."}'
        )
    elif card_type == 'blank':
        tips.append(
            f'BLANK TURN: {turn_card} changes little. Continue flop plan. '
            f'If you cbetted flop and were called: evaluate based on flop read. '
            f'Villain called with {("draws or top pair" if flop_texture in ("wet","medium") else "pair or better")}.'
        )

    return TurnRunoutResult(
        flop_texture=flop_texture,
        turn_card=turn_card,
        card_type=card_type,
        pfr_benefit=pfr_benefit,
        range_advantage=range_adv,
        turn_cbet_freq=turn_freq,
        bet_size_adjustment=size_adj,
        hero_position=hero_position,
        hand_category=hand_category,
        verdict=verdict,
        reasoning=reasoning,
        tips=tips,
    )


def tra_one_liner(r: TurnRunoutResult) -> str:
    return (
        f'[TRA {r.turn_card}|{r.card_type}|{r.hero_position}] '
        f'cbet={r.turn_cbet_freq:.0%} size_adj={r.bet_size_adjustment:.2f}x | '
        f'{r.range_advantage}'
    )
