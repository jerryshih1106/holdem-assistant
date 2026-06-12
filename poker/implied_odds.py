"""
翻前隱含賠率計算器 (Preflop Speculative Hand Implied Odds)

核心問題：「我用這個跌牌聽牌/小對子跟注翻前，長期有利可圖嗎？」

適用手牌：
  - 小對子（22-88）：主要目標是暗三條（set）
  - 同花連張（T9s, 98s 等）：順子/同花或兩對以上
  - 同花間張（T8s, 97s 等）
  - 異色連張（在深籌碼 multiway 底池才有利）

核心公式：
  需要隱含賠率 = 1 / (hit_pct × stack_multiplier)
  實際隱含賠率 = effective_stack / call_amount

小對子翻牌 set 概率 ≈ 11.8%（≈ 1/8.5）
  → 需要 8.5x 的「額外」利潤才能回本
  → GTO 研究：需要約 15-20:1 隱含賠率才能 set mine 有利

同花連張各種命中概率（翻牌）：
  - 同花 flush：0.84%
  - 強力 OESD/同花：≈ 6%
  - 兩對或更強：≈ 4%
  → 整體「繼續手牌」概率：≈ 35%（有足夠 equity 繼續的翻牌）
  → 需要約 12:1 隱含賠率

調整因素：
  - 對手 VPIP（魚會給更多 implied odds → 降低門檻）
  - 籌碼深度（需要足夠籌碼才能得到 payoff）
  - 對手數（多對手 = 更多 implied odds）
  - 位置（有位置 = 更容易提取）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class ImpliedOddsResult:
    # 手牌信息
    hand_type:         str     # 'small_pair' / 'suited_connector' / 'suited_gapper' / 'offsuit_connector'
    hand_type_zh:      str

    # 賠率計算
    actual_ratio:      float   # 實際隱含賠率（effective_stack / call_amount）
    required_ratio:    float   # 需要的最低隱含賠率
    call_amount:       float   # 跟注金額（BB）
    effective_stack:   float   # 有效籌碼（BB）

    # 判斷
    has_implied_odds:  bool    # 是否有足夠隱含賠率
    ev_estimate:       float   # 估計每次跟注 EV（BB）

    # 條件和建議
    conditions:        List[str]  # 支持跟注的條件
    warnings:          List[str]  # 警告
    advice:            str
    tip:               str


# ── 手牌分類 ────────────────────────────────────────────────────────────────────

_SMALL_PAIR_RANKS = {'2','3','4','5','6','7','8'}
_MED_PAIR_RANKS   = {'9','T','J'}

def _classify_hand(
    card1: str,
    card2: str,
) -> Tuple[str, str, float, float]:
    """
    分類手牌，返回（hand_type, hand_type_zh, hit_pct, stack_multiplier）。

    hit_pct:        翻牌命中強手或聽牌的概率
    stack_multiplier: 每次命中需要從對手身上贏回的倍數（相對於跟注金額）
    """
    r1 = card1[0].upper() if card1 else '?'
    r2 = card2[0].upper() if card2 else '?'
    s1 = card1[1].lower() if len(card1) >= 2 else 'x'
    s2 = card2[1].lower() if len(card2) >= 2 else 'y'

    suited = (s1 == s2 and s1 != 'x')
    _RANK_VAL = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
                 'T':10,'J':11,'Q':12,'K':13,'A':14}
    v1 = _RANK_VAL.get(r1, 7)
    v2 = _RANK_VAL.get(r2, 7)
    gap = abs(v1 - v2)

    # 對子
    if r1 == r2:
        if r1 in _SMALL_PAIR_RANKS:
            return 'small_pair', '小對子(Set Mining)', 0.118, 8.5
        elif r1 in _MED_PAIR_RANKS:
            return 'medium_pair', '中對子', 0.118, 7.0
        else:
            return 'big_pair', '大對子(取值)', 0.118, 3.0

    # 同花牌
    if suited:
        if gap == 1:
            return 'suited_connector', '同花連張', 0.38, 4.5
        elif gap == 2:
            return 'suited_gapper', '同花間張', 0.30, 5.5
        elif gap == 3:
            return 'suited_2gap', '同花雙間張', 0.22, 7.0
        else:
            return 'suited_broadways', '同花高張', 0.32, 3.0

    # 異色連張
    if gap == 1:
        return 'offsuit_connector', '異色連張', 0.20, 7.0

    return 'offsuit_other', '無特殊潛力', 0.10, 12.0


def check_implied_odds(
    card1:           str   = '',     # 英雄手牌1（如 '6c'）
    card2:           str   = '',     # 英雄手牌2（如 '6d'）
    call_amount:     float = 3.0,    # 跟注金額（BB）
    effective_stack: float = 100.0,  # 有效籌碼（BB）
    villain_vpip:    float = 0.28,   # 對手 VPIP（0-1）
    num_opponents:   int   = 1,      # 對手數（影響 implied odds）
    is_ip:           bool  = True,   # 英雄是否有位置
    pot_bb:          float = 0.0,    # 當前底池（默認 0 = 翻前）
    villain_stack:   float = 0.0,    # 對手籌碼（0 = 使用 effective_stack）
) -> ImpliedOddsResult:
    """
    計算翻前跟注的隱含賠率。

    Args:
        card1, card2:    英雄手牌（如 '6c', '6d'）；可傳入 'rank' 或 'ranksuit'
        call_amount:     需要跟注的金額（BB）
        effective_stack: 有效籌碼（BB，跟注後剩餘）
        villain_vpip:    對手 VPIP（魚 = 更多 implied odds）
        num_opponents:   底池中的對手數
        is_ip:           英雄是否有位置
        pot_bb:          當前底池大小
        villain_stack:   對手籌碼（0 = 假設等於 effective_stack）
    """
    if not villain_stack:
        villain_stack = effective_stack

    hand_type, hand_type_zh, base_hit_pct, base_mult = _classify_hand(card1, card2)

    # ── 調整需要的隱含賠率倍數 ─────────────────────────────────────────────────

    required_mult = base_mult

    # 對手 VPIP 越高 → 他給的 implied odds 更多 → 降低門檻
    if villain_vpip >= 0.45:
        required_mult *= 0.75    # 魚大幅降低門檻
    elif villain_vpip >= 0.35:
        required_mult *= 0.85
    elif villain_vpip <= 0.18:
        required_mult *= 1.20    # TAG/Nit → 更難提取
    elif villain_vpip <= 0.24:
        required_mult *= 1.10

    # 多對手 → 更多 implied odds
    if num_opponents >= 3:
        required_mult *= 0.75
    elif num_opponents >= 2:
        required_mult *= 0.88

    # 有位置 → 更容易取值
    if is_ip:
        required_mult *= 0.90
    else:
        required_mult *= 1.10

    # 籌碼不夠深 → 難以獲得足夠 payoff
    stack_depth = effective_stack / max(call_amount, 0.1)
    if stack_depth < 12:
        required_mult *= 1.30    # 籌碼太淺
    elif stack_depth < 18:
        required_mult *= 1.10

    required_mult = round(required_mult, 1)

    # ── 實際隱含賠率 ──────────────────────────────────────────────────────────

    actual_ratio = effective_stack / max(call_amount, 0.1)
    required_ratio = required_mult

    has_implied_odds = actual_ratio >= required_ratio

    # ── EV 估計 ──────────────────────────────────────────────────────────────

    # 簡化：EV ≈ hit_pct × (expected_win - call_amount) - (1 - hit_pct) × call_amount
    # expected_win 假設命中後贏到對手籌碼的一定比例
    payoff_fraction = 0.50  # 命中後平均贏到對手 50% 籌碼

    # 魚的 payoff fraction 更高（他們不會放棄）
    if villain_vpip >= 0.45:
        payoff_fraction = 0.65
    elif villain_vpip >= 0.35:
        payoff_fraction = 0.55
    elif villain_vpip <= 0.20:
        payoff_fraction = 0.35

    expected_win = villain_stack * payoff_fraction
    ev = base_hit_pct * expected_win - call_amount
    ev = round(ev, 2)

    # ── 條件和警告 ────────────────────────────────────────────────────────────

    conditions: List[str] = []
    warnings: List[str] = []

    if actual_ratio >= required_ratio * 1.5:
        conditions.append(f'籌碼極深（{actual_ratio:.0f}:1 >> 需要 {required_ratio:.0f}:1）')
    elif actual_ratio >= required_ratio:
        conditions.append(f'隱含賠率足夠（{actual_ratio:.0f}:1 >= 需要 {required_ratio:.0f}:1）')

    if villain_vpip >= 0.40:
        conditions.append(f'對手 VPIP={villain_vpip:.0%}（呼叫站）→ 命中後容易拿到 payoff')
    elif villain_vpip >= 0.32:
        conditions.append(f'對手 VPIP={villain_vpip:.0%}（鬆散）→ 隱含賠率合理')

    if num_opponents >= 2:
        conditions.append(f'{num_opponents}個對手 → 多人底池 implied odds 更大')

    if is_ip:
        conditions.append('有位置 → 控制底池大小，提取最大 implied odds')

    if actual_ratio < required_ratio:
        gap = required_ratio - actual_ratio
        warnings.append(f'隱含賠率不足（差 {gap:.0f}x）→ 長期跟注虧損')

    if stack_depth < 18:
        warnings.append(f'籌碼太淺（{effective_stack:.0f}BB vs {call_amount:.0f}BB call）→ 命中後難以全下取值')

    if not is_ip and hand_type in ('small_pair', 'suited_gapper', 'offsuit_connector'):
        warnings.append('無位置：難以控制底池，implied odds 打折扣')

    if villain_vpip <= 0.20:
        warnings.append(f'對手 VPIP={villain_vpip:.0%}（Nit/TAG）→ 命中三條他可能直接棄牌')

    if hand_type == 'big_pair':
        warnings.append('大對子不需要隱含賠率，直接以公平賠率 / 主動加注計算')

    # ── 建議 ─────────────────────────────────────────────────────────────────

    if not has_implied_odds:
        advice = f'棄牌（隱含賠率不足：{actual_ratio:.0f}:1 < 需要 {required_ratio:.0f}:1）'
    elif ev <= 0:
        advice = f'邊界跟注（EV={ev:+.1f}BB）：勉強可接受，需要 reads 支持'
    elif ev >= 3:
        advice = f'強烈跟注（EV={ev:+.1f}BB）：隱含賠率充足，對魚/深籌碼極佳'
    else:
        advice = f'跟注（EV={ev:+.1f}BB）：隱含賠率滿足，繼續'

    tip = _generate_tip(hand_type, actual_ratio, required_ratio, villain_vpip, is_ip)

    return ImpliedOddsResult(
        hand_type        = hand_type,
        hand_type_zh     = hand_type_zh,
        actual_ratio     = round(actual_ratio, 1),
        required_ratio   = round(required_ratio, 1),
        call_amount      = call_amount,
        effective_stack  = effective_stack,
        has_implied_odds = has_implied_odds,
        ev_estimate      = ev,
        conditions       = conditions,
        warnings         = warnings,
        advice           = advice,
        tip              = tip,
    )


def _generate_tip(
    hand_type: str,
    actual: float,
    required: float,
    vpip: float,
    is_ip: bool,
) -> str:
    if hand_type == 'small_pair':
        if actual >= required * 1.3:
            return f'深籌碼({actual:.0f}:1)翻牌 set 賠率極佳，務必跟注'
        if vpip >= 0.40:
            return f'對魚 set mine：命中三條後全下，他通常跟到底'
        return f'Set mining 需要 {required:.0f}:1 以上（含命中概率 12%）'
    if hand_type == 'suited_connector':
        if is_ip:
            return '有位置同花連張：命中 flush 或 OESD 後利用位置建大底池'
        return '無位置同花連張：命中前控制底池，命中後敞開加注'
    if hand_type == 'suited_gapper':
        if actual >= required:
            return '同花間張：只在命中 flush/straight/兩對時繼續，否則棄牌'
        return '同花間張隱含賠率不足：等更深籌碼或更多對手再跟'
    if hand_type == 'offsuit_connector':
        return '異色連張在 HU 底池 implied odds 通常不足，建議 3-bet 或棄牌'
    return f'隱含賠率 {actual:.0f}:1（需要 {required:.0f}:1）'


def implied_odds_summary(r: ImpliedOddsResult) -> str:
    """單行 overlay 摘要（最多 80 字元）。"""
    status = 'OK' if r.has_implied_odds else '不足'
    return (f'[隱含賠率] {r.hand_type_zh}  '
            f'{r.actual_ratio:.0f}:1 ({status} 需{r.required_ratio:.0f}:1)  '
            f'EV{r.ev_estimate:+.1f}BB  {r.advice[:20]}')[:80]
