"""
Range vs Range 勝率計算。

根據對手 HUD 統計（VPIP/PFR）和街道行動構建對手預估範圍，
再用 Monte Carlo 計算英雄手牌 vs 該範圍的勝率
（比 vs 隨機手牌更準確）。

對手範圍構建邏輯（簡化）：
  VPIP 20% → 使用翻前範圍表前 20% 的手牌
  若對手翻前加注（PFR）→ 使用 PFR% 的子集（更緊的範圍）
  若對手翻後持續注 → 進一步縮小到強牌
"""

import random
from typing import Dict, FrozenSet, List, Optional, Tuple

from treys import Card, Evaluator
from poker.pushfold import PUSH_ORDER   # 169 手牌的強度排序（通用排序）

_eval = Evaluator()

# 所有 52 張牌
_RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
_SUITS = ['h','d','c','s']
_ALL_CARDS = [Card.new(r+s) for r in _RANKS for s in _SUITS]


# ── 範圍構建 ──────────────────────────────────────────────────────────────────

def _hand_to_combos(hand: str) -> List[Tuple[int, int]]:
    """將手牌字串（如 'AKs'）展開成所有合法的雙牌組合（treys int 格式）。"""
    if len(hand) == 2:                           # 對子
        r = hand[0]
        cards = [Card.new(r+s) for s in _SUITS]
        return [(cards[i], cards[j]) for i in range(4) for j in range(i+1, 4)]
    r1, r2, stype = hand[0], hand[1], hand[2]
    c1 = [Card.new(r1+s) for s in _SUITS]
    c2 = [Card.new(r2+s) for s in _SUITS]
    if stype == 's':                             # 同花
        return [(c1[i], c2[i]) for i in range(4)]
    else:                                        # 不同花
        return [(a, b) for a in c1 for b in c2 if _suit(a) != _suit(b)]


def _suit(card: int) -> int:
    return Card.get_suit_int(card)


def build_range(vpip_pct: float, action: str = 'open') -> FrozenSet[str]:
    """
    根據 VPIP% 和行動類型構建對手手牌範圍。

    action:
      'open'     → 翻前首次加注（使用 PFR% ≈ VPIP×0.75）
      'call'     → 翻前跟注（寬鬆，VPIP but not PFR）
      'cbet'     → 翻牌持續注（縮小至前 60% 的開牌範圍）
      'check'    → 翻牌過牌（弱牌或陷阱，假設隨機分佈）

    回傳手牌集合（使用 PUSH_ORDER 的前 N% 作為強度代理）。
    """
    # 限制範圍
    pct = max(5.0, min(vpip_pct, 100.0))

    if action == 'open':
        # 加注範圍 ≈ VPIP×0.75（通常 PFR < VPIP）
        pct = pct * 0.75
    elif action == 'cbet':
        pct = pct * 0.60
    elif action == 'check':
        pct = pct  # 過牌範圍難以縮小，保持原始寬度

    n = max(1, int(pct / 100 * 169))
    return frozenset(PUSH_ORDER[:n])


def _filter_by_blockers(combos: List[Tuple[int, int]],
                         known_cards: List[int]) -> List[Tuple[int, int]]:
    """移除含有已知牌的組合。"""
    known = set(known_cards)
    return [(a, b) for a, b in combos if a not in known and b not in known]


# ── 勝率計算 ──────────────────────────────────────────────────────────────────

def equity_vs_range(
    hero_hole:       List[str],
    community_cards: List[str],
    opp_vpip:        float = 25.0,
    opp_action:      str   = 'open',
    iterations:      int   = 1000,
) -> Dict:
    """
    計算英雄手牌 vs 對手預估範圍的勝率。

    回傳：
      win_rate      — 勝率 (0-1)
      range_pct     — 對手範圍寬度 (%)
      range_size    — 對手範圍手牌數
      vs_random     — 對比：vs 隨機手牌的勝率（Monte Carlo）
      improvement   — range equity 比 random equity 高/低多少個百分點
    """
    try:
        hero  = [Card.new(c.strip()) for c in hero_hole if c]
        board = [Card.new(c.strip()) for c in community_cards if c]
    except Exception:
        return _empty_result()

    if len(hero) < 2:
        return _empty_result()

    known    = set(hero + board)
    opp_rng  = build_range(opp_vpip, opp_action)
    rng_size = len(opp_rng)
    rng_pct  = rng_size / 169 * 100

    # 展開範圍為組合並過濾死牌
    all_combos: List[Tuple[int, int]] = []
    for hand in opp_rng:
        combos = _hand_to_combos(hand)
        all_combos.extend(_filter_by_blockers(combos, list(known)))

    if not all_combos:
        return _empty_result()

    cards_left = 5 - len(board)
    deck = [c for c in _ALL_CARDS if c not in known]

    wins = ties = total = 0

    for _ in range(iterations):
        if not all_combos:
            break
        opp_hand = list(random.choice(all_combos))

        # 過濾對手手牌不在 deck
        if opp_hand[0] not in deck or opp_hand[1] not in deck:
            continue

        remaining = [c for c in deck if c not in opp_hand]
        if len(remaining) < cards_left:
            continue

        run_board = board + random.sample(remaining, cards_left)

        hero_rank = _eval.evaluate(run_board, hero)
        opp_rank  = _eval.evaluate(run_board, opp_hand)

        if hero_rank < opp_rank:
            wins += 1
        elif hero_rank == opp_rank:
            ties += 1
        total += 1

    if total == 0:
        return _empty_result()

    win_rate = wins / total + ties / total * 0.5

    # 對比 vs 隨機（簡化：只跑 200 次）
    vs_random = _equity_vs_random(hero, board, deck, cards_left, 200)

    return {
        'win_rate':    win_rate,
        'range_pct':   rng_pct,
        'range_size':  rng_size,
        'opp_action':  opp_action,
        'vs_random':   vs_random,
        'improvement': (win_rate - vs_random) * 100,   # 百分點差距
        'valid':       True,
    }


def _equity_vs_random(hero, board, deck, cards_left, n) -> float:
    wins = total = 0
    for _ in range(n):
        if len(deck) < cards_left + 2:
            break
        sample = random.sample(deck, cards_left + 2)
        opp  = sample[:2]
        run  = board + sample[2:]
        if _eval.evaluate(run, hero) < _eval.evaluate(run, opp):
            wins += 1
        total += 1
    return wins / total if total else 0.5


def _empty_result() -> Dict:
    return {'win_rate': 0.0, 'range_pct': 100.0, 'range_size': 169,
            'opp_action': 'unknown', 'vs_random': 0.0, 'improvement': 0.0,
            'valid': False}


def format_range_equity(result: Dict) -> str:
    """一行中文摘要。"""
    if not result.get('valid'):
        return ''
    wr   = result['win_rate'] * 100
    rp   = result['range_pct']
    imp  = result['improvement']
    sign = '+' if imp >= 0 else ''
    return f'vs 範圍({rp:.0f}%手牌): {wr:.0f}%  （{sign}{imp:.0f}pp vs 隨機）'
