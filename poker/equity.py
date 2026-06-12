"""Monte Carlo equity calculator using treys hand evaluator."""

import random
from typing import List, Tuple

from treys import Card, Deck, Evaluator

_evaluator = Evaluator()

# All 52 cards in treys integer format
_ALL_CARDS: List[int] = []
for r in "23456789TJQKA":
    for s in "cdhs":
        _ALL_CARDS.append(Card.new(r + s))


def _parse_cards(card_strings: List[str]) -> List[int]:
    result = []
    for cs in card_strings:
        try:
            result.append(Card.new(cs))
        except Exception:
            pass
    return result


def calculate_equity(
    hole_cards: List[str],
    community_cards: List[str],
    num_opponents: int = 1,
    iterations: int = 5000,
) -> Tuple[float, float, float]:
    """
    Run Monte Carlo simulation to estimate hero's equity.

    Returns:
        (win_rate, tie_rate, loss_rate) all in [0, 1]
    """
    hero = _parse_cards(hole_cards)
    board = _parse_cards(community_cards)

    if len(hero) < 2:
        return 0.0, 0.0, 1.0

    known = set(hero + board)
    deck = [c for c in _ALL_CARDS if c not in known]

    cards_needed_board = 5 - len(board)
    cards_needed_opp = 2 * num_opponents

    wins = ties = losses = 0

    for _ in range(iterations):
        if len(deck) < cards_needed_board + cards_needed_opp:
            break
        sample = random.sample(deck, cards_needed_board + cards_needed_opp)
        run_board = board + sample[:cards_needed_board]
        opp_hands = [
            sample[cards_needed_board + i * 2: cards_needed_board + i * 2 + 2]
            for i in range(num_opponents)
        ]

        hero_score = _evaluator.evaluate(run_board, hero)
        opp_scores = [_evaluator.evaluate(run_board, h) for h in opp_hands]
        best_opp = min(opp_scores)  # lower = better in treys

        if hero_score < best_opp:
            wins += 1
        elif hero_score == best_opp:
            ties += 1
        else:
            losses += 1

    total = wins + ties + losses
    if total == 0:
        return 0.0, 0.0, 1.0
    return wins / total, ties / total, losses / total


def hand_category(equity: float) -> str:
    if equity >= 0.80:
        return "怪獸牌"
    if equity >= 0.65:
        return "強牌"
    if equity >= 0.50:
        return "中等"
    if equity >= 0.35:
        return "聽牌/邊緣"
    return "弱牌"
