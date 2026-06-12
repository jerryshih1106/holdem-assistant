"""
4-bet 注碼最優化器 (4-bet Sizing Optimizer)

核心問題：「我要 4-bet，應該下多少？」

GTO 4-bet 注碼原則：
─────────────────────────────────────────────────────────────────────
類型        目標                    尺寸範圍
─────────────────────────────────────────────────────────────────────
取值 4-bet  迫使對手以差牌跟注       2.2-2.5x 3-bet 注
           讓對手難以用聽牌跟注
詐唬 4-bet  最小化風險，最大折疊率   2.0-2.2x 3-bet 注
（光注）    與取值混合保持均衡
─────────────────────────────────────────────────────────────────────

調整因素：
  1. 位置：IP（有位置）→ 縮小 10%（翻後位置優勢降低取值需求）
           OOP（無位置）→ 標準或加大（需要更大底池補償位置劣勢）
  2. 籌碼深度：>200BB → +15%（避免過淺 SPR 讓對手跟注勝率更高）
               <40BB → 直接全推（4-bet 後剩籌碼太少無意義）
               <30BB → 全推或棄牌（SPR 已達承諾區域）
  3. 對手 3-bet 頻率：高 3-bet 頻率（>15%）→ 可稍縮小（他們詐唬多，便宜跟也有利）
  4. 對手對 4-bet 的 fold 頻率：高 fold → 縮小（少注就能獲得相同 fold equity）
                                低 fold → 加大（需要更大壓力讓他折疊中等強牌）
  5. 極化程度：純 AA/KK 4-bet → 更大取值（不怕嚇走）
               半詐唬 4-bet（A4s 等）→ 標準偏小

數學支撐：
  最優 4-bet 尺寸使對手跟注所有手牌的 EV ≈ 0
  → 對手的跟注手牌數量 = SPR 後可接受的最低範圍
  → 實務：IP 4-bet → 2.2x; OOP 4-bet → 2.4-2.5x
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class FourBetSizing:
    # 情境
    hero_pos:           str
    villain_pos:        str
    threbet_size_bb:    float   # 對手 3-bet 金額
    stack_bb:           float

    # 建議
    is_jam:             bool    # 是否直接全推
    recommended_bb:     float   # 建議 4-bet 金額（BB）
    min_bb:             float   # 最小合理 4-bet
    max_bb:             float   # 最大合理 4-bet
    multiplier:         float   # 倍數（相對於 3-bet 注）

    # 決策類型
    bet_type:           str     # 'value'/'bluff'/'jam'/'fold'
    bet_type_zh:        str

    # 調整說明
    adjustments:        List[str]
    confidence:         str     # 'high'/'medium'/'low'
    key_note:           str
    summary_zh:         str


_POS_ORDER = ['UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def _is_ip(hero_pos: str, villain_pos: str) -> bool:
    """英雄是否有位置（翻後）。"""
    try:
        hi = _POS_ORDER.index(hero_pos)
        vi = _POS_ORDER.index(villain_pos)
        return hi > vi  # higher index = later position = IP
    except ValueError:
        return True


def recommend_4bet_size(
    hero_pos:          str   = 'BTN',
    villain_pos:       str   = 'CO',
    threbet_size_bb:   float = 11.0,   # 對手 3-bet 金額（BB）
    stack_bb:          float = 100.0,  # 有效籌碼（BB）
    is_value:          bool  = True,   # 取值 vs 詐唬（光注）
    villain_3bet_pct:  float = 0.08,   # 對手 3-bet 頻率（0-1）
    villain_fold_4bet: float = 0.55,   # 對手面對 4-bet 的棄牌率（0-1）
) -> FourBetSizing:
    """
    計算最優 4-bet 注碼。

    Args:
        hero_pos:         英雄位置
        villain_pos:      對手位置（3-bet 者）
        threbet_size_bb:  對手 3-bet 金額（BB）
        stack_bb:         有效籌碼（BB）
        is_value:         取值 4-bet（AA/KK）還是詐唬 4-bet（A5s）
        villain_3bet_pct: 對手 3-bet 頻率
        villain_fold_4bet: 對手面對 4-bet 的棄牌率
    """
    adjustments: List[str] = []

    # ── 短籌碼全推 ─────────────────────────────────────────────────────────────

    remaining_after_3bet = stack_bb - threbet_size_bb
    if stack_bb <= 35:
        return FourBetSizing(
            hero_pos          = hero_pos,
            villain_pos       = villain_pos,
            threbet_size_bb   = threbet_size_bb,
            stack_bb          = stack_bb,
            is_jam            = True,
            recommended_bb    = stack_bb,
            min_bb            = stack_bb,
            max_bb            = stack_bb,
            multiplier        = round(stack_bb / max(threbet_size_bb, 1), 1),
            bet_type          = 'jam',
            bet_type_zh       = '全推（短籌碼）',
            adjustments       = [f'籌碼僅 {stack_bb:.0f}BB：4-bet 後剩餘籌碼太少，全推最優'],
            confidence        = 'high',
            key_note          = f'全推 {stack_bb:.0f}BB（{stack_bb:.0f}BB 有效籌碼）',
            summary_zh        = f'[4-bet] 全推 {stack_bb:.0f}BB（短籌碼）',
        )

    # 3-bet 過大，全推更合算
    if threbet_size_bb > stack_bb * 0.40:
        return FourBetSizing(
            hero_pos          = hero_pos,
            villain_pos       = villain_pos,
            threbet_size_bb   = threbet_size_bb,
            stack_bb          = stack_bb,
            is_jam            = True,
            recommended_bb    = stack_bb,
            min_bb            = stack_bb,
            max_bb            = stack_bb,
            multiplier        = round(stack_bb / max(threbet_size_bb, 1), 1),
            bet_type          = 'jam',
            bet_type_zh       = '全推（3-bet 過大）',
            adjustments       = [f'3-bet {threbet_size_bb:.0f}BB 超過籌碼 40%：直接全推最優'],
            confidence        = 'high',
            key_note          = f'3-bet 超大：全推 {stack_bb:.0f}BB',
            summary_zh        = f'[4-bet] 全推（3-bet={threbet_size_bb:.0f}BB 過大）',
        )

    # ── 基礎倍數 ───────────────────────────────────────────────────────────────

    ip = _is_ip(hero_pos, villain_pos)

    if is_value:
        base_mult = 2.30 if ip else 2.45
    else:
        base_mult = 2.10 if ip else 2.25

    # ── 調整 ──────────────────────────────────────────────────────────────────

    mult = base_mult

    # 位置調整
    if ip:
        adjustments.append(f'有位置(IP {hero_pos} vs {villain_pos}) → 基準倍數 {base_mult:.2f}x')
    else:
        adjustments.append(f'無位置(OOP {hero_pos} vs {villain_pos}) → 基準倍數 {base_mult:.2f}x')

    # 籌碼深度
    if stack_bb >= 200:
        mult += 0.18
        adjustments.append(f'深籌碼（{stack_bb:.0f}BB）→ +0.18x 避免過淺 SPR')
    elif stack_bb >= 150:
        mult += 0.10
        adjustments.append(f'較深籌碼（{stack_bb:.0f}BB）→ +0.10x')
    elif stack_bb <= 50:
        mult -= 0.10
        adjustments.append(f'籌碼偏淺（{stack_bb:.0f}BB）→ -0.10x（接近 jam zone）')

    # 對手 3-bet 頻率
    if villain_3bet_pct >= 0.15:
        mult -= 0.10
        adjustments.append(f'對手 3-bet 頻率高({villain_3bet_pct:.0%}) → -0.10x（詐唬多）')
    elif villain_3bet_pct <= 0.05:
        mult += 0.10
        adjustments.append(f'對手 3-bet 頻率低({villain_3bet_pct:.0%}) → +0.10x（幾乎只有強牌）')

    # 對手 fold-to-4bet 頻率
    if villain_fold_4bet >= 0.70:
        mult -= 0.12
        adjustments.append(f'對手折疊率高({villain_fold_4bet:.0%}) → -0.12x（小注就夠壓制）')
    elif villain_fold_4bet <= 0.35:
        mult += 0.15
        adjustments.append(f'對手折疊率低({villain_fold_4bet:.0%}) → +0.15x（需更大壓力）')

    # 取值 vs 詐唬
    if not is_value:
        adjustments.append('詐唬 4-bet（光注）→ 偏小尺寸降低風險')
    else:
        adjustments.append('取值 4-bet → 標準至偏大尺寸')

    mult = round(max(2.0, min(3.5, mult)), 2)

    rec_bb  = round(threbet_size_bb * mult, 1)
    min_bb  = round(threbet_size_bb * 2.0, 1)
    max_bb  = round(threbet_size_bb * 2.8, 1)

    # 不超過全下
    rec_bb = min(rec_bb, stack_bb)
    max_bb = min(max_bb, stack_bb)

    bet_type    = 'value' if is_value else 'bluff'
    bet_type_zh = '取值' if is_value else '詐唬（光注）'

    conf = 'high' if villain_fold_4bet not in (0.0,) else 'medium'

    key_note = (
        f'4-bet {rec_bb:.0f}BB ({mult:.2f}x 3-bet {threbet_size_bb:.0f}BB)  '
        f'{"IP" if ip else "OOP"}  {"取值" if is_value else "詐唬"}'
    )

    summary_zh = (
        f'[4-bet] {bet_type_zh} {rec_bb:.0f}BB  '
        f'({min_bb:.0f}-{max_bb:.0f}BB)  {mult:.1f}x 3-bet'
    )[:70]

    return FourBetSizing(
        hero_pos          = hero_pos,
        villain_pos       = villain_pos,
        threbet_size_bb   = threbet_size_bb,
        stack_bb          = stack_bb,
        is_jam            = False,
        recommended_bb    = rec_bb,
        min_bb            = min_bb,
        max_bb            = max_bb,
        multiplier        = mult,
        bet_type          = bet_type,
        bet_type_zh       = bet_type_zh,
        adjustments       = adjustments,
        confidence        = conf,
        key_note          = key_note,
        summary_zh        = summary_zh,
    )


def fourbet_summary(r: FourBetSizing) -> str:
    """單行 overlay 摘要（最多 70 字）。"""
    return r.summary_zh[:70]
