"""
超池下注識別器 (Overbet Spot Detector)

核心問題：「我應該下注超過底池嗎？（1.0x-2.0x）」

超池下注在以下情況最優：
  1. 河牌有強範圍優勢（英雄有更多堅果 combo）
  2. 對手有「呼叫站」傾向（高 VPIP/低 fold freq）
  3. 高 SPR（籌碼充足，有空間使用大注）
  4. 極化河牌（英雄要麼最強要麼在詐唬）
  5. 轉牌強勢 combo 聽牌（13+ outs）→ 建大底池

GTO 研究支持：
  - 對手折疊率高（>55%）→ 標準注碼或小注更好（他們反正折疊）
  - 對手折疊率低（<35%）+ 英雄有強手 → 超池是最優取值手段
  - 深籌碼（SPR>8）河牌：超池迫使對手以更糟的賠率跟注弱手
  - 呼叫站對大注的反應：他們通常維持高跟注率 → 可提取更多

超池不適合：
  - 多人底池（要求所有人折疊）
  - 弱牌/中等牌（只有弱牌跟注你更弱的手）
  - 低 SPR（<3）→ 已經近全下，超池沒有意義
  - OOP 且無位置優勢（被跟注後仍在不利位置）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class OverbetResult:
    # 情境
    street:            str     # 'turn' / 'river'
    equity:            float
    pot_bb:            float
    stack_bb:          float
    spr:               float

    # 超池建議
    should_overbet:    bool
    recommended_pct:   float   # 建議注碼（底池%）：0.33/0.50/0.75/1.0/1.25/1.5/2.0
    recommended_bb:    float   # 換算 BB

    # EV 比較（三個注碼）
    ev_standard:       float   # 0.67x 底池 EV (normalized)
    ev_overbet:        float   # recommended_pct EV
    ev_small:          float   # 0.33x 底池 EV

    # 觸發因素
    triggers:          List[str]   # 滿足的超池條件
    blockers:          List[str]   # 阻礙超池的因素

    # 輸出
    sizing_label:      str     # '超池1.5x' / '標準75%' 等
    confidence:        str     # 'high' / 'medium' / 'low'
    reasoning:         str
    tip:               str


def _ev_estimate(
    size_pct:      float,   # bet / pot
    equity:        float,   # 0-1
    pot_bb:        float,
    villain_fold:  float,   # 0-1
    villain_vpip:  float,   # 0-1 (higher = calls wider)
) -> float:
    """
    估算下注 EV（簡化模型）。

    EV = fold_adj × pot + call_adj × (eq × (pot + bet) - (1-eq) × bet)
    fold_adj 受注碼大小影響：大注折疊更多
    """
    bet = pot_bb * size_pct

    # 折疊率隨注碼增大而升高，但呼叫站對大注折疊少
    base_fold = villain_fold
    size_impact = (size_pct - 0.5) * 0.15     # +0.15 per 100% extra
    vpip_dampener = max(0, (villain_vpip - 0.30) * 0.5)  # fish call more
    fold_rate = min(0.90, max(0.05, base_fold + size_impact - vpip_dampener))

    win_ev   = equity * (pot_bb + bet) - (1 - equity) * bet
    ev = fold_rate * pot_bb + (1 - fold_rate) * win_ev
    return round(ev, 2)


def analyze_overbet(
    equity:          float,
    pot_bb:          float,
    stack_bb:        float,
    street:          str   = 'river',
    villain_vpip:    float = 0.28,     # 0-1
    villain_fold:    float = 0.50,     # fold freq (0-1)
    villain_af:      float = 1.5,
    range_advantage: float = 0.55,     # 0-1: hero's range equity advantage (0.5=neutral)
    num_opponents:   int   = 1,
    is_oop:          bool  = False,
    has_strong_draw: bool  = False,    # combo draw 13+ outs (turn only)
) -> OverbetResult:
    """
    判斷是否適合超池下注，並建議注碼。

    Args:
        equity:         英雄勝率（0-1）
        pot_bb:         底池（BB）
        stack_bb:       有效籌碼
        street:         'turn' or 'river'
        villain_vpip:   對手 VPIP（0-1）
        villain_fold:   對手 fold-to-bet 頻率（0-1）
        villain_af:     對手 Aggression Factor
        range_advantage: 英雄範圍勝率優勢（0=對手優，0.5=均衡，1=英雄優）
        num_opponents:  對手數（多人底池不適合超池）
        is_oop:         英雄是否無位置
        has_strong_draw: 是否有強力聽牌（13+ outs，turn only）
    """
    spr = stack_bb / max(pot_bb, 0.1)
    triggers: List[str] = []
    blockers: List[str] = []
    score = 0.0

    # ── 觸發條件（加分）──────────────────────────────────────────────────────

    # 1. 強牌（高勝率）
    if equity >= 0.80:
        triggers.append(f'強牌（勝率{equity:.0%}）→ 超池取值最大化')
        score += 0.35
    elif equity >= 0.65:
        triggers.append(f'較強牌（勝率{equity:.0%}）→ 可考慮超池')
        score += 0.15

    # 2. 對手 VPIP 高（呼叫站傾向）
    if villain_vpip >= 0.40:
        triggers.append(f'對手 VPIP {villain_vpip:.0%}（魚）→ 大注仍跟，超池取值')
        score += 0.30
    elif villain_vpip >= 0.32:
        triggers.append(f'對手 VPIP {villain_vpip:.0%}（鬆散）→ 對大注跟注頻率偏高')
        score += 0.15

    # 3. 對手折疊率低（大注他們仍然跟注）
    if villain_fold <= 0.35:
        triggers.append(f'對手 fold-to-bet {villain_fold:.0%}（低）→ 超池不會嚇跑他們')
        score += 0.20
    elif villain_fold <= 0.45:
        triggers.append(f'對手 fold-to-bet {villain_fold:.0%}（中低）→ 大注較有效')
        score += 0.10

    # 4. 範圍優勢
    if range_advantage >= 0.70:
        triggers.append(f'範圍優勢極大（{range_advantage:.0%}）→ 超池是正確策略')
        score += 0.25
    elif range_advantage >= 0.60:
        triggers.append(f'範圍優勢（{range_advantage:.0%}）→ 支持大注')
        score += 0.12

    # 5. 高 SPR（有空間使用大注）
    if spr >= 8:
        triggers.append(f'深籌碼 SPR={spr:.1f} → 超池有足夠空間')
        score += 0.15
    elif spr >= 5:
        triggers.append(f'SPR={spr:.1f} → 可使用超池')
        score += 0.08

    # 6. 轉牌強力 combo 聽牌
    if has_strong_draw and street == 'turn':
        triggers.append('強力 Combo 聽牌（13+ outs）→ 轉牌超池建底池')
        score += 0.20

    # ── 阻礙因素（減分）──────────────────────────────────────────────────────

    if num_opponents >= 2:
        blockers.append(f'{num_opponents}人底池 → 超池需所有對手折疊，不建議')
        score -= 1.00   # hard block: multiway almost always kills overbet EV

    if is_oop:
        blockers.append('無位置 → 超池後仍先行動，難以控制底池')
        score -= 0.20

    if villain_fold >= 0.65:
        blockers.append(f'對手 fold-to-bet {villain_fold:.0%}（高）→ 標準注碼已夠壓制')
        score -= 0.25

    if equity < 0.55:
        blockers.append(f'勝率 {equity:.0%} 不足以超池取值')
        score -= 0.30

    if spr < 3:
        blockers.append(f'SPR={spr:.1f}（低）→ 籌碼不足以超池，考慮全下')
        score -= 0.35

    if street == 'turn' and not has_strong_draw:
        blockers.append('轉牌無強力聽牌 → 等河牌確認再超池')
        score -= 0.10

    # ── 決策 ──────────────────────────────────────────────────────────────────
    should_overbet = score >= 0.40

    # ── 建議注碼 ──────────────────────────────────────────────────────────────
    if not should_overbet:
        # 標準注碼（根據勝率）
        if equity >= 0.70:
            rec_pct = 0.75
        elif equity >= 0.55:
            rec_pct = 0.60
        else:
            rec_pct = 0.40
    else:
        # 超池：根據分數和因素決定大小
        if score >= 0.80 and villain_vpip >= 0.40:
            rec_pct = 1.50   # 魚 + 強牌 → 1.5x
        elif score >= 0.65:
            rec_pct = 1.20   # 較大超池
        elif score >= 0.40:
            rec_pct = 1.00   # 剛好超池

        # 河牌 vs 呼叫站
        if street == 'river' and villain_vpip >= 0.45 and equity >= 0.80:
            rec_pct = min(2.0, rec_pct + 0.30)

    # 限制不超過籌碼
    max_pct = stack_bb / max(pot_bb, 0.1)
    rec_pct = round(min(rec_pct, max_pct), 2)

    rec_bb = round(pot_bb * rec_pct, 1)

    # ── EV 比較 ──────────────────────────────────────────────────────────────
    ev_s = _ev_estimate(0.33, equity, pot_bb, villain_fold, villain_vpip)
    ev_std = _ev_estimate(0.67, equity, pot_bb, villain_fold, villain_vpip)
    ev_ob = _ev_estimate(rec_pct, equity, pot_bb, villain_fold, villain_vpip)

    # ── 注碼標籤 ─────────────────────────────────────────────────────────────
    if rec_pct >= 1.50:
        sizing_label = f'超池 {rec_pct:.1f}x'
    elif rec_pct >= 1.00:
        sizing_label = f'超池 {rec_pct:.0%}'
    else:
        sizing_label = f'標準 {rec_pct:.0%}'

    # ── 信心等級 ──────────────────────────────────────────────────────────────
    if should_overbet and score >= 0.65:
        confidence = 'high'
    elif should_overbet:
        confidence = 'medium'
    else:
        confidence = 'low'

    # ── 推理 + 提示 ──────────────────────────────────────────────────────────
    if should_overbet:
        reasoning = (f'超池識別：{len(triggers)}個觸發條件，'
                     f'分數={score:.1f}  建議 {rec_pct:.0%} 底池 = {rec_bb:.1f}BB')
        tip = _overbet_tip(villain_vpip, villain_fold, equity, street)
    else:
        reasoning = (f'標準注碼：{len(blockers)}個阻礙因素，'
                     f'分數={score:.1f}  建議 {rec_pct:.0%} 底池 = {rec_bb:.1f}BB')
        tip = _standard_tip(villain_fold, equity, street)

    return OverbetResult(
        street           = street,
        equity           = equity,
        pot_bb           = pot_bb,
        stack_bb         = stack_bb,
        spr              = round(spr, 1),
        should_overbet   = should_overbet,
        recommended_pct  = rec_pct,
        recommended_bb   = rec_bb,
        ev_standard      = ev_std,
        ev_overbet       = ev_ob,
        ev_small         = ev_s,
        triggers         = triggers,
        blockers         = blockers,
        sizing_label     = sizing_label,
        confidence       = confidence,
        reasoning        = reasoning,
        tip              = tip,
    )


def _overbet_tip(vpip: float, fold: float, eq: float, street: str) -> str:
    if vpip >= 0.45:
        return f'魚(VPIP={vpip:.0%})跟大注：盡量加大取值，他會跟到底'
    if fold <= 0.30:
        return f'對手折疊率低({fold:.0%})：大注是正確施壓，讓他用劣勢牌跟注'
    if eq >= 0.85:
        return f'勝率{eq:.0%}近堅果：超池取值最大化，注碼越大EV越高'
    if street == 'turn':
        return '強力聽牌轉牌超池：建立底池，命中河牌可全下取值'
    return f'超池取值：確保範圍中有足夠弱牌（詐唬）維持均衡'


def _standard_tip(fold: float, eq: float, street: str) -> str:
    if fold >= 0.65:
        return f'對手易折疊({fold:.0%})：小注即可，大注只是多冒險'
    if eq < 0.55:
        return f'勝率不足({eq:.0%})：標準注碼，不要超池取值導致損失加大'
    return '標準均衡注碼，無明顯超池理由'


def overbet_summary(r: OverbetResult) -> str:
    """單行 overlay 摘要。"""
    ev_diff = r.ev_overbet - r.ev_standard
    ev_str = f'EV{ev_diff:+.1f}' if r.should_overbet else ''
    return (f'[注碼] {r.sizing_label} = {r.recommended_bb:.0f}BB  '
            f'{ev_str}  {r.tip[:30]}')[:80]
