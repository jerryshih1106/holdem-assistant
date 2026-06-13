"""Monte Carlo + exact enumeration equity calculator using treys hand evaluator.

P0 fix：
  1. 自適應模擬次數（依剩餘公牌數選 5K/10K/25K/精確枚舉）
  2. 河牌單對手精確枚舉（≈990次，誤差 0%）
  3. Wilson 95% 信賴區間回傳
  4. 新增 EquityResult dataclass（向後相容：calculate_equity 仍回傳 Tuple）
"""

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from treys import Card, Evaluator

_evaluator = Evaluator()

_ALL_CARDS: List[int] = []
for _r in "23456789TJQKA":
    for _s in "cdhs":
        _ALL_CARDS.append(Card.new(_r + _s))


# ─── 結果型別 ──────────────────────────────────────────────────────────────────

@dataclass
class EquityResult:
    win:       float    # 勝率 [0,1]
    tie:       float    # 平手率 [0,1]
    loss:      float    # 負率 [0,1]
    ci_half:   float    # 95% Wilson CI 半寬 [0,1]
    n_samples: int      # 實際模擬次數（精確枚舉時 = 枚舉組合數）
    exact:     bool = False   # True = 精確枚舉，誤差為 0

    @property
    def equity(self) -> float:
        """勝率 + 一半平手率（標準 equity 定義）。"""
        return self.win + self.tie / 2.0

    @property
    def ci_pct(self) -> int:
        """95% CI 半寬，取上限整數百分點（顯示用）。"""
        return math.ceil(self.ci_half * 100)

    def ci_str(self) -> str:
        """'±1%' 格式字串，精確枚舉時回傳空字串。"""
        if self.exact:
            return ""
        pct = self.ci_pct
        if pct == 0:
            return "±<1%"
        return f"±{pct}%"


# ─── 工具函式 ──────────────────────────────────────────────────────────────────

def _parse_cards(card_strings: List[str]) -> List[int]:
    result = []
    for cs in card_strings:
        try:
            result.append(Card.new(cs))
        except Exception:
            pass
    return result


def _auto_iterations(n_community: int) -> int:
    """根據還要發幾張公牌決定模擬次數。"""
    if n_community >= 5: return 0        # 0 = 精確枚舉
    if n_community == 4: return 25_000   # 1 張轉/河
    if n_community == 3: return 10_000   # 2 張（翻牌圈）
    return 5_000                          # 翻前 / 早期


def _wilson_ci(wins: int, n: int, z: float = 1.96) -> float:
    """Wilson Score Interval 半寬（二項比例 95% CI）。"""
    if n == 0:
        return 0.5
    p     = wins / n
    z2    = z * z
    denom = 1.0 + z2 / n
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return margin


# ─── 精確枚舉（河牌，單對手）─────────────────────────────────────────────────

def _exact_river_1opp(hero: List[int], board: List[int]) -> Tuple[int, int, int, int]:
    """
    精確枚舉河牌全部對手 hole card 組合（C(45,2)=990 次）。
    hero_score 是常數，算一次即可。
    Returns (wins, ties, losses, total)
    """
    known      = set(hero + board)
    deck       = [c for c in _ALL_CARDS if c not in known]
    n          = len(deck)
    hero_score = _evaluator.evaluate(board, hero)
    wins = ties = losses = 0

    for i in range(n):
        for j in range(i + 1, n):
            opp_score = _evaluator.evaluate(board, [deck[i], deck[j]])
            if   hero_score < opp_score:  wins   += 1
            elif hero_score == opp_score: ties   += 1
            else:                         losses += 1

    total = wins + ties + losses
    return wins, ties, losses, total


# ─── 主要函式：帶 CI ───────────────────────────────────────────────────────────

def calculate_equity_ci(
    hole_cards:      List[str],
    community_cards: List[str],
    num_opponents:   int = 1,
    iterations:      int = 0,   # 0 = 自動選
) -> EquityResult:
    """
    計算勝率並附帶 95% Wilson 信賴區間。

    - 河牌（5張公牌）+ 單對手 → 精確枚舉，誤差 0%
    - 其他情況 → Monte Carlo，依街道自動選次數
    """
    hero  = _parse_cards(hole_cards)
    board = _parse_cards(community_cards)

    if len(hero) < 2:
        return EquityResult(0.0, 0.0, 1.0, 0.5, 0)

    n_comm = len(board)

    # ── 河牌精確枚舉（單對手）──────────────────────────────────────
    if n_comm >= 5 and num_opponents == 1:
        w, t, l, total = _exact_river_1opp(hero, board)
        if total > 0:
            return EquityResult(
                win=w/total, tie=t/total, loss=l/total,
                ci_half=0.0, n_samples=total, exact=True,
            )

    # ── Monte Carlo ─────────────────────────────────────────────────
    if iterations == 0:
        iterations = _auto_iterations(n_comm) or 50_000   # 多人河牌回退 50K

    known             = set(hero + board)
    deck              = [c for c in _ALL_CARDS if c not in known]
    cards_board_left  = 5 - n_comm
    cards_opp         = 2 * num_opponents

    wins = ties = losses = actual = 0

    for _ in range(iterations):
        if len(deck) < cards_board_left + cards_opp:
            break
        sample    = random.sample(deck, cards_board_left + cards_opp)
        run_board = board + sample[:cards_board_left]
        opp_hands = [
            sample[cards_board_left + i * 2: cards_board_left + i * 2 + 2]
            for i in range(num_opponents)
        ]
        hero_score = _evaluator.evaluate(run_board, hero)
        best_opp   = min(_evaluator.evaluate(run_board, h) for h in opp_hands)

        if   hero_score < best_opp:  wins   += 1
        elif hero_score == best_opp: ties   += 1
        else:                        losses += 1
        actual += 1

    total = wins + ties + losses
    if total == 0:
        return EquityResult(0.0, 0.0, 1.0, 0.5, 0)

    # CI 以「勝利 + 半平手」為 p 計算
    combined_wins = wins + ties // 2
    ci = _wilson_ci(combined_wins, total)

    return EquityResult(
        win=wins/total, tie=ties/total, loss=losses/total,
        ci_half=ci, n_samples=actual, exact=False,
    )


# ─── 向後相容介面 ──────────────────────────────────────────────────────────────

def calculate_equity(
    hole_cards:      List[str],
    community_cards: List[str],
    num_opponents:   int = 1,
    iterations:      int = 5000,
) -> Tuple[float, float, float]:
    """
    Legacy 介面，回傳 (win, tie, loss)。
    內部改用自適應次數（iterations 作為最低保底）。
    """
    n_comm     = len([c for c in community_cards if c])
    actual_its = max(iterations, _auto_iterations(n_comm) or iterations)
    r          = calculate_equity_ci(hole_cards, community_cards, num_opponents, actual_its)
    return r.win, r.tie, r.loss


# ─── 手牌分類 ─────────────────────────────────────────────────────────────────

def hand_category(equity: float) -> str:
    if equity >= 0.80: return "怪獸牌"
    if equity >= 0.65: return "強牌"
    if equity >= 0.50: return "中等"
    if equity >= 0.35: return "聽牌/邊緣"
    return "弱牌"
