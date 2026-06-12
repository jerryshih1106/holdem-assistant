"""
即時牌型辨識與強度百分位。

使用 treys Evaluator 辨識：
  同花順 / 四條 / 葫蘆 / 同花 / 順子 / 三條 / 兩對 / 一對 / 高牌

百分位 = (7462 - hand_rank) / 7462
  hand_rank 1 = 最強（皇家同花順）
  hand_rank 7462 = 最弱（2-3-4-5-7 散牌高牌）

另提供「相對強度」：在這個牌面上，英雄的手牌落在哪個分位。
"""

from dataclasses import dataclass
from typing import List, Optional
from treys import Card, Evaluator

_eval = Evaluator()

# treys class_to_string 對應中文
_CLASS_ZH = {
    'Straight Flush': '同花順',
    'Four of a Kind': '四條',
    'Full House':     '葫蘆',
    'Flush':          '同花',
    'Straight':       '順子',
    'Three of a Kind':'三條',
    'Two Pair':       '兩對',
    'Pair':           '一對',
    'High Card':      '高牌',
}

# 各牌型的粗略頂部百分位（用來顯示「全部手牌中前 X%」）
_CLASS_RANGES = {
    'Straight Flush': (0.0,  0.03),
    'Four of a Kind': (0.03, 0.17),
    'Full House':     (0.17, 2.6),
    'Flush':          (2.6,  3.0),   # 約 3% 的手牌
    'Straight':       (3.0,  4.6),
    'Three of a Kind':(4.6,  9.4),
    'Two Pair':       (9.4,  23.5),
    'Pair':           (23.5, 49.9),
    'High Card':      (49.9, 100.0),
}

# 牌型強度（數字越大越強，用來顯示進度條）
_CLASS_STRENGTH = {
    'Straight Flush': 9, 'Four of a Kind': 8, 'Full House': 7,
    'Flush': 6, 'Straight': 5, 'Three of a Kind': 4,
    'Two Pair': 3, 'Pair': 2, 'High Card': 1,
}


@dataclass
class HandStrength:
    # 基本分類
    class_str:   str    # 英文類別（treys 原生）
    name_zh:     str    # 中文牌型名稱
    hand_rank:   int    # treys rank (1=best, 7462=worst)
    # 百分位（越高越強）
    percentile:  float  # 0-1, 1=最強
    top_pct:     int    # 前幾 %（1=前1%最強）
    # 強度條 (0-9)
    strength_level: int
    # 旗標
    is_made_hand:  bool   # True = 已成牌（非高牌）
    is_monster:    bool   # 三條以上
    is_strong:     bool   # 兩對以上
    has_draws:     bool   # 尚未到 river 且非最強牌
    # 詳細描述
    desc_zh:     str    # 一行中文描述


def classify(hole_cards: List[str], community_cards: List[str]) -> Optional[HandStrength]:
    """
    辨識英雄的即時牌型。
    需要至少 3 張公牌。回傳 None 如果牌數不足。
    """
    try:
        hole  = [Card.new(c.strip()) for c in hole_cards  if c and len(c) >= 2]
        board = [Card.new(c.strip()) for c in community_cards if c and len(c) >= 2]
    except Exception:
        return None

    if len(hole) < 2 or len(board) < 3:
        return None

    try:
        rank    = _eval.evaluate(board, hole)
        cls_int = _eval.get_rank_class(rank)
        cls_str = _eval.class_to_string(cls_int)
    except Exception:
        return None

    name_zh  = _CLASS_ZH.get(cls_str, cls_str)
    pct      = (7462 - rank) / 7462          # 0-1，1=最強
    top_pct  = max(1, int((1 - pct) * 100))  # 前 top_pct%
    strength = _CLASS_STRENGTH.get(cls_str, 1)

    is_made    = cls_str != 'High Card'
    is_monster = strength >= 4   # 三條以上
    is_strong  = strength >= 3   # 兩對以上
    has_draws  = len(board) < 5 and strength <= 2  # 翻/轉牌上的弱牌

    # 詳細描述
    desc = _describe(cls_str, name_zh, top_pct, len(board))

    return HandStrength(
        class_str     = cls_str,
        name_zh       = name_zh,
        hand_rank     = rank,
        percentile    = pct,
        top_pct       = top_pct,
        strength_level= strength,
        is_made_hand  = is_made,
        is_monster    = is_monster,
        is_strong     = is_strong,
        has_draws     = has_draws,
        desc_zh       = desc,
    )


def _describe(cls_str: str, name_zh: str, top_pct: int, n_board: int) -> str:
    street = {3:'翻牌', 4:'轉牌', 5:'河牌'}.get(n_board, '')
    if top_pct <= 5:
        strength_desc = '極強'
    elif top_pct <= 15:
        strength_desc = '強'
    elif top_pct <= 35:
        strength_desc = '中等'
    elif top_pct <= 55:
        strength_desc = '偏弱'
    else:
        strength_desc = '弱'

    if n_board < 5:
        return f'{street} {name_zh}（全部手牌前 {top_pct}%，{strength_desc}）'
    return f'{name_zh}（前 {top_pct}%，{strength_desc}）'


def strength_bar(level: int, width: int = 9) -> str:
    """回傳視覺化強度條，例如 '████░░░░░'"""
    filled = max(0, min(width, level))
    return '█' * filled + '░' * (width - filled)


def hand_vs_range_percentile(
    hole_cards:      List[str],
    community_cards: List[str],
    samples:         int = 200,
) -> float:
    """
    在目前的公牌上，英雄的牌型落在所有可能手牌組合中的哪個百分位。
    透過隨機抽樣評估。
    回傳 0-1（越高表示英雄的牌比更多隨機手牌強）。
    """
    import random
    from treys import Deck

    try:
        hole  = [Card.new(c) for c in hole_cards if c]
        board = [Card.new(c) for c in community_cards if c]
    except Exception:
        return 0.0

    if len(hole) < 2 or len(board) < 3:
        return 0.0

    hero_rank = _eval.evaluate(board, hole)
    known     = set(hole + board)

    RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
    SUITS = ['h','d','c','s']
    all_cards = [Card.new(r+s) for r in RANKS for s in SUITS]
    deck      = [c for c in all_cards if c not in known]

    beat_count = 0
    for _ in range(samples):
        if len(deck) < 2:
            break
        sample_hand = random.sample(deck, 2)
        sample_rank = _eval.evaluate(board, sample_hand)
        if hero_rank < sample_rank:  # lower = better in treys
            beat_count += 1

    return beat_count / samples
