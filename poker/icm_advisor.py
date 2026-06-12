"""
ICM Bubble Play Advisor

在錦標賽接近 bubble（泡沫圈）時，ICM 壓力讓棄牌 EV 比籌碼 EV 更保守。
本模組計算：
  1. ICM 壓力係數（0-1）
  2. 需要的額外勝率才能合理跟注
  3. 具體的範圍調整建議

核心邏輯（Malmuth-Harville 近似）：
  - 距離入錢越近 + 籌碼越短 → ICM 壓力越大
  - ICM 壓力高時：折疊邊緣手牌，主動進攻短籌碼，避免與大籌碼翻牌

預計 EV 調整：
  near_bubble(3 spots, 平均籌碼) → 需要額外 ~8% 勝率才值得跟注 all-in
  bubble_shot(1 spot, 短籌碼)   → 需要額外 ~20% 勝率
  comfortable(5+ spots)         → 幾乎無 ICM 壓力
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from poker.icm import icm_equity, risk_premium


@dataclass
class BubbleAdvice:
    spots_from_money:   int          # 距離入錢名次
    hero_rank:          str          # 'big'/'medium'/'short'/'micro'
    hero_stack_bb:      float
    avg_stack_bb:       float
    icm_pressure:       float        # 0-1，越高壓力越大
    equity_premium:     float        # 跟注需多加的勝率（0.08 = 需多 8%）
    call_threshold:     float        # 最低跟注全下勝率（0.5 + premium）
    range_tighten_pct:  float        # 建議縮減的開牌範圍（0.15 = 減 15%）
    priority_action:    str          # 'attack_short'/'survive'/'normal'/'chip_lead'
    advice:             str          # 主要建議
    hand_adjustments:   str          # 具體手牌例子
    pct_from_money:     float        # 距入錢的剩餘百分比


def calc_bubble_advice(
    spots_from_money: int,
    hero_stack_bb:    float,
    avg_stack_bb:     float,
    total_players:    int      = 9,
    payouts:          Optional[List[float]] = None,
) -> BubbleAdvice:
    """
    計算 ICM bubble 建議。

    Args:
        spots_from_money: 幾名才能入錢（1=下一名被淘汰就入錢）
        hero_stack_bb:    英雄籌碼（BB）
        avg_stack_bb:     平均籌碼（BB）
        total_players:    目前剩餘人數
        payouts:          獎金結構（可省略，使用預設比例）

    Returns:
        BubbleAdvice
    """
    hero_stack_bb = max(1.0, hero_stack_bb)
    avg_stack_bb  = max(1.0, avg_stack_bb)

    # 推算籌碼排名
    stack_ratio = hero_stack_bb / avg_stack_bb
    if stack_ratio >= 1.6:
        hero_rank = 'big'
    elif stack_ratio >= 0.85:
        hero_rank = 'medium'
    elif stack_ratio >= 0.40:
        hero_rank = 'short'
    else:
        hero_rank = 'micro'

    # ── ICM 壓力計算 ─────────────────────────────────────────────────────────
    # 用近似公式（Malmuth-Harville 精確計算需要知道所有人籌碼）
    # 主要因素：距離入錢名次、籌碼排名
    #
    # 基礎壓力：由 spots_from_money 決定
    if spots_from_money <= 1:
        base_pressure = 0.90   # 極限 bubble — 非常謹慎
    elif spots_from_money <= 2:
        base_pressure = 0.70
    elif spots_from_money <= 3:
        base_pressure = 0.50
    elif spots_from_money <= 5:
        base_pressure = 0.30
    else:
        base_pressure = 0.10   # 遠離 bubble，幾乎沒有 ICM 壓力

    # 籌碼調整：短籌碼壓力更大，大籌碼可以更積極
    rank_adj = {
        'micro':  +0.20,   # 超短籌碼，每手都是生死
        'short':  +0.10,
        'medium': +0.00,
        'big':    -0.15,   # 大籌碼受 ICM 保護，可以施壓
    }
    icm_pressure = max(0.0, min(1.0, base_pressure + rank_adj[hero_rank]))

    # ── 需額外的勝率 ─────────────────────────────────────────────────────────
    # equity_premium = ICM 壓力 × 最大調整（大約 25% 在最極端情況）
    equity_premium  = icm_pressure * 0.25
    call_threshold  = min(0.90, 0.50 + equity_premium)

    # ── 開牌範圍縮減 ──────────────────────────────────────────────────────────
    # 壓力越大，縮減越多
    if hero_rank == 'big':
        range_tighten = max(0.0, icm_pressure * 0.10)   # 大籌碼略縮
    elif hero_rank == 'micro':
        range_tighten = 0.0    # 超短籌碼反而要推寬（快死了）
    else:
        range_tighten = icm_pressure * 0.25   # 中等/短籌碼縮減最多

    # ── 優先行動 ─────────────────────────────────────────────────────────────
    if hero_rank == 'big' and icm_pressure >= 0.40:
        priority_action = 'attack_short'   # 大籌碼→壓短籌碼
    elif hero_rank in ('micro', 'short') and icm_pressure >= 0.60:
        priority_action = 'survive'        # 短籌碼→求生
    elif icm_pressure >= 0.70:
        priority_action = 'survive'
    elif icm_pressure < 0.15:
        priority_action = 'normal'
    else:
        priority_action = 'attack_short' if hero_rank == 'big' else 'survive'

    # ── 建議文字 ─────────────────────────────────────────────────────────────
    advice = _build_advice(
        spots_from_money, hero_rank, icm_pressure, call_threshold,
        range_tighten, priority_action,
    )
    hand_adj = _hand_adjustments(icm_pressure, hero_rank, hero_stack_bb)

    # 距入錢的百分比（假設已知剩餘人數）
    paying_spots = total_players - spots_from_money
    pct_from_money = spots_from_money / max(1, total_players) * 100

    return BubbleAdvice(
        spots_from_money  = spots_from_money,
        hero_rank         = hero_rank,
        hero_stack_bb     = hero_stack_bb,
        avg_stack_bb      = avg_stack_bb,
        icm_pressure      = round(icm_pressure, 2),
        equity_premium    = round(equity_premium, 3),
        call_threshold    = round(call_threshold, 3),
        range_tighten_pct = round(range_tighten, 2),
        priority_action   = priority_action,
        advice            = advice,
        hand_adjustments  = hand_adj,
        pct_from_money    = round(pct_from_money, 1),
    )


def _build_advice(spots, rank, pressure, threshold, tighten, action) -> str:
    thresh_pct = int(threshold * 100)
    tighten_pct = int(tighten * 100)
    pressure_pct = int(pressure * 100)

    if pressure < 0.15:
        return f'ICM壓力低（{pressure_pct}%），正常策略'

    if action == 'attack_short':
        return (f'大籌碼ICM壓力{pressure_pct}%：積極壓短籌碼；'
                f'跟注全下需勝率{thresh_pct}%以上；'
                f'避免與其他大籌碼翻牌')

    if action == 'survive':
        if rank == 'micro':
            return (f'超短籌碼ICM壓力{pressure_pct}%：別被動等死！'
                    f'找機會推牌，推牌範圍{100-tighten_pct}%（放寬）；'
                    f'跟注全下需勝率{thresh_pct}%以上')
        return (f'短籌碼ICM壓力{pressure_pct}%：求生模式；'
                f'縮減開牌{tighten_pct}%；'
                f'跟注全下需勝率{thresh_pct}%以上；'
                f'距入錢{spots}名')

    return (f'ICM壓力{pressure_pct}%：縮減開牌{tighten_pct}%；'
            f'跟注全下需勝率{thresh_pct}%以上；距入錢{spots}名')


def _hand_adjustments(pressure: float, rank: str, stack_bb: float) -> str:
    """給出具體手牌調整建議。"""
    if pressure < 0.20:
        return '正常開牌範圍'

    if rank == 'micro':
        return f'超短籌碼({stack_bb:.0f}bb)：任何 Ax/suited/對子都推；67%+ 手牌推牌'

    if pressure >= 0.70:
        if rank == 'big':
            return '大籌碼：開牌全位置正常；跟注全下只用 QQ+ AKs；壓短籌碼可寬'
        return '棄牌 AJo/KQo/A9s 以下 UTG-HJ；BB 防守縮 20%；避免跟注大籌碼全下'

    if pressure >= 0.40:
        if rank == 'big':
            return '大籌碼：UTG/HJ 縮 10%；跟注全下 TT+ AQs+；主動施壓短籌碼'
        return 'UTG/HJ 棄牌 ATo 以下/K9s 以下；CO/BTN 範圍不縮；BB 縮 10%'

    return f'輕度調整：UTG 縮 {int(pressure*20)}% 開牌範圍；中位置以後正常'


def bubble_summary(r: BubbleAdvice) -> str:
    """單行摘要，適合 overlay 顯示。"""
    rank_zh = {'big': '大籌碼', 'medium': '中籌碼', 'short': '短籌碼', 'micro': '超短'}
    rank_txt = rank_zh.get(r.hero_rank, r.hero_rank)
    pressure_pct = int(r.icm_pressure * 100)
    return (f'[ICM] {r.spots_from_money}名入錢  {rank_txt}  '
            f'壓力{pressure_pct}%  跟注全下需{int(r.call_threshold*100)}%勝率')


def quick_bubble(spots: int, stack_bb: float, avg_bb: float) -> str:
    """一行快速查詢。"""
    r = calc_bubble_advice(spots, stack_bb, avg_bb)
    return bubble_summary(r)
