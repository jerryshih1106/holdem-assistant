"""
最優翻前開牌注碼顧問 (Optimal Preflop Open Sizing Advisor)

核心問題：「我應該開多大？」

不同尺寸的效果：
  小開注（2x-2.2x）：吸引更多跟注，但底池小 → 適合強牌想多街取值
  中等開注（2.5x-3x）：均衡，減少多人底池
  大開注（3x-4x）：對抗鬆散跟注者時建鍋，或 SB/BTN 孤立

調整因素：
  1. 位置：BTN 基礎 2.2x，UTG 基礎 2.5x，SB iso 3.5x
  2. 對手 VPIP（越鬆散 → 越大，建大鍋取值）
  3. 對手 fold-to-steal（太緊 → 縮小，太鬆 → 加大）
  4. 籌碼深度（200bb+ 加大，<50bb 縮小）
  5. 多人底池情況（幾個跟注者 → 加大）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class OpenSizingResult:
    hero_pos:         str
    villain_pos:      str     # 主要防守者（BB 或 主要對手）
    stack_bb:         float

    recommended_x:    float   # 建議開注倍數（例如 2.5）
    recommended_bb:   float   # 換算 BB（例如 5.0BB）

    min_x:            float   # 合理範圍下限
    max_x:            float   # 合理範圍上限

    # EV 比較（3個代表尺寸）
    ev_small:         float   # 2.0x 估算 EV (BB/100)
    ev_medium:        float   # recommended_x 估算 EV
    ev_large:         float   # recommended_x + 0.8x 估算 EV

    # 調整理由
    adjustments:      List[str]
    reasoning:        str
    tip:              str


# ── 各位置基礎開注倍數 ────────────────────────────────────────────────────────

_BASE_X: Dict[str, float] = {
    'UTG':  2.5,
    'UTG1': 2.5,
    'UTG2': 2.5,
    'LJ':   2.5,
    'HJ':   2.4,
    'CO':   2.3,
    'BTN':  2.2,
    'SB':   3.0,    # SB opens large to avoid multiway vs BB
    'BB':   2.5,    # BB vs SB steal defense 3bet
}


def _estimate_ev(
    size_x:       float,
    hero_pos:     str,
    villain_vpip: float,  # 0-1
    fold_to_st:   float,  # 0-1, fold to steal frequency
    stack_bb:     float,
    hand_strength: float = 0.65,  # rough equity vs random
) -> float:
    """
    粗略估算開注 EV（BB/100 hands）。

    EV = fold_rate × steal_gain + call_rate × postflop_EV(hand, position)

    fold_rate 隨 size 增加而增加（非線性）。
    postflop_EV 隨 size 增加而增加（更大底池），但也需要更強手牌。
    """
    # 折疊率隨尺寸上升（sigmoid-ish）
    size_factor = (size_x - 2.0) / 2.0   # 0 at 2x, 1 at 4x
    # base fold at 2x ≈ fold_to_st; each extra BB increases fold ~5%
    fold_rate = min(0.92, fold_to_st + size_factor * 0.20)

    steal_gain = 1.5  # 典型竊取所得（blinds）

    # 翻後 EV（有位置的估算）
    pos_premium = {'BTN': 0.12, 'CO': 0.08, 'HJ': 0.05, 'SB': -0.05,
                   'BB': -0.08, 'UTG': 0.0}.get(hero_pos, 0.0)
    hand_edge = hand_strength - 0.50 + pos_premium   # 相對隨機手的優勢
    pot_when_called = size_x * 2 + 1.5   # open + call + blinds
    postflop_ev_per_call = hand_edge * pot_when_called

    call_rate = 1 - fold_rate
    ev = fold_rate * steal_gain + call_rate * postflop_ev_per_call
    return round(ev, 2)


def recommend_open_size(
    hero_pos:         str,
    villain_pos:      str  = 'BB',
    stack_bb:         float = 100.0,
    villain_vpip:     float = 0.28,   # 主要對手的 VPIP（0-1）
    villain_fold_to_steal: float = 0.60,  # 對手 fold-to-steal（0-1）
    n_players_to_act: int   = 2,      # 仍需行動的玩家數（包含 BB）
    hand_strength:    float = 0.65,   # 手牌對抗隨機手的勝率
) -> OpenSizingResult:
    """
    計算當前情境的最優開注尺寸。

    Args:
        hero_pos:         英雄位置
        villain_pos:      主要防守者
        stack_bb:         有效籌碼深度
        villain_vpip:     對手 VPIP（影響建鍋大小）
        villain_fold_to_steal: 對手 fold-to-steal 率
        n_players_to_act: 還在等待行動的玩家數
        hand_strength:    手牌強度估算
    """
    hero_pos = hero_pos.upper() if hero_pos else 'BTN'
    base_x = _BASE_X.get(hero_pos, 2.5)

    adjustments: List[str] = []
    adj = 0.0

    # ── 調整 1：對手 VPIP（鬆散對手 → 開大，鎖定利潤）────────────────
    if villain_vpip >= 0.45:
        adj += 0.8
        adjustments.append(f'對手VPIP {villain_vpip:.0%}（魚）→ +0.8x 建大鍋')
    elif villain_vpip >= 0.35:
        adj += 0.5
        adjustments.append(f'對手VPIP {villain_vpip:.0%}（鬆散）→ +0.5x 取值')
    elif villain_vpip <= 0.18:
        adj -= 0.2
        adjustments.append(f'對手VPIP {villain_vpip:.0%}（緊）→ -0.2x 小注偷盲')

    # ── 調整 2：fold-to-steal（高折疊率 → 縮小，低折疊率 → 加大）──────
    if villain_fold_to_steal >= 0.75:
        adj -= 0.2
        adjustments.append(f'對手折疊率 {villain_fold_to_steal:.0%}（高）→ -0.2x 省籌碼')
    elif villain_fold_to_steal <= 0.40:
        adj += 0.4
        adjustments.append(f'對手折疊率 {villain_fold_to_steal:.0%}（低）→ +0.4x 防寬跟注')

    # ── 調整 3：籌碼深度 ─────────────────────────────────────────────
    if stack_bb >= 200:
        adj += 0.3
        adjustments.append(f'深籌碼 {stack_bb:.0f}bb → +0.3x')
    elif stack_bb <= 40:
        adj -= 0.3
        adjustments.append(f'短籌碼 {stack_bb:.0f}bb → -0.3x（all-in 節奏）')

    # ── 調整 4：多人底池風險 ───────────────────────────────────────────
    if n_players_to_act >= 4:
        adj += 0.4
        adjustments.append(f'{n_players_to_act}人等待 → +0.4x 減少多人底池')
    elif n_players_to_act >= 3:
        adj += 0.2
        adjustments.append(f'{n_players_to_act}人等待 → +0.2x')

    # ── SB 特殊處理：vs BB 隔離用大注 ──────────────────────────────────
    if hero_pos == 'SB':
        adj += 0.3  # SB oop 需要更大的底池優勢
        adjustments.append('SB vs BB（無位置）→ +0.3x 補償 OOP 劣勢')

    recommended_x = round(max(2.0, min(5.0, base_x + adj)), 1)
    recommended_bb = round(recommended_x * 2, 1)  # multiply by BB (1BB = 2 units if BB=2)

    # ── EV 比較 ─────────────────────────────────────────────────────────
    ev_s = _estimate_ev(2.0, hero_pos, villain_vpip, villain_fold_to_steal,
                        stack_bb, hand_strength)
    ev_m = _estimate_ev(recommended_x, hero_pos, villain_vpip, villain_fold_to_steal,
                        stack_bb, hand_strength)
    ev_l = _estimate_ev(min(recommended_x + 0.8, 5.0), hero_pos, villain_vpip,
                        villain_fold_to_steal, stack_bb, hand_strength)

    # ── 人性化理由 ──────────────────────────────────────────────────────
    adj_summary = '、'.join(adjustments) if adjustments else '標準尺寸'
    reasoning = (f'{hero_pos} 基礎 {base_x}x  調整: {adj:+.1f}x  '
                 f'→ 推薦 {recommended_x}x ({recommended_bb}BB)')

    tip = _get_tip(hero_pos, villain_vpip, villain_fold_to_steal, recommended_x)

    return OpenSizingResult(
        hero_pos        = hero_pos,
        villain_pos     = villain_pos,
        stack_bb        = stack_bb,
        recommended_x   = recommended_x,
        recommended_bb  = recommended_bb,
        min_x           = max(2.0, recommended_x - 0.5),
        max_x           = min(5.0, recommended_x + 0.5),
        ev_small        = ev_s,
        ev_medium       = ev_m,
        ev_large        = ev_l,
        adjustments     = adjustments,
        reasoning       = reasoning,
        tip             = tip,
    )


def _get_tip(pos: str, vpip: float, fold: float, rec_x: float) -> str:
    if vpip >= 0.45:
        return '魚的跟注率高——用大注建鍋，方便翻後大注取值'
    if fold >= 0.75:
        return '對手容易棄牌——可縮小尺寸，用省下的籌碼更高頻下注'
    if fold <= 0.40:
        return '對手喜歡跟注——確保手牌有翻後可玩性再加大注'
    if pos == 'SB':
        return 'SB 開注必須大一些補償 OOP 劣勢，或選擇棄牌/push策略'
    if rec_x >= 3.5:
        return '大注模式：翻後需要更強手牌才能繼續，確保有計劃'
    return f'{pos} 標準開注 {rec_x}x，可根據 HUD 微調'


def open_sizing_summary(r: OpenSizingResult) -> str:
    """單行 overlay 摘要。"""
    return (f'[開注] {r.hero_pos} 推薦 {r.recommended_x}x = {r.recommended_bb}BB  '
            f'({r.min_x}x-{r.max_x}x)  '
            f'EV~{r.ev_medium:+.1f}BB/100')
