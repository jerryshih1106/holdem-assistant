"""
河牌綜合決策優化器 (River Decision Optimizer)

整合 blockers、MDF、polarization、range_narrower，
提供完整的河牌行動建議：

  面對下注 (facing bet)：
    → call / fold / raise
    基於：equity_needed vs 實際 equity、MDF、blockers call_score

  主動下注 (hero act first)：
    → value_bet / check_call / check_fold / bluff
    基於：hand strength、villain range、polarization ratio、blockers bluff_score

薄薄取值（Thin Value）門檻：
  若 equity >= villain_call_rate + margin，就算弱頂對也可以薄薄下注
  關鍵：villain 必須跟注足夠多的更弱的牌

Bluff Catch（跟注詐唬）：
  若 villain_bluff_freq > alpha（詐唬保本折疊率），則跟注獲利
  alpha = bet / (pot + bet)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple


@dataclass
class RiverDecision:
    # 情境
    situation:          str      # 'facing_bet' | 'hero_acts_first'
    pot_bb:             float
    bet_bb:             float    # 對手下注大小（facing_bet 時有效）
    equity:             float
    position:           str      # 'ip' | 'oop'

    # 主要建議
    action:             str      # '跟注'/'棄牌'/'加注'/'下注取值'/'薄薄取值'/'過牌跟注'/'過牌棄牌'/'詐唬'
    action_confidence:  str      # 'high'/'medium'/'low'
    sizing_bb:          float    # 建議注碼（主動下注時有效）
    sizing_pct:         float    # 底池比例

    # 數學指標
    equity_needed:      float    # 跟注所需最低勝率
    mdf:                float    # 最低防守頻率
    villain_bluff_freq: float    # 估算對手詐唬頻率
    alpha:              float    # 詐唬保本折疊率

    # 輔助分析
    blocker_score:      float    # 0-1，關鍵阻擋效果
    thin_value_ok:      bool     # 是否適合薄薄取值
    polarization_note:  str      # GTO 詐唬:價值比提示

    reasoning:          str
    tips:               List[str] = field(default_factory=list)


# ── 手牌強度分類 ──────────────────────────────────────────────────────────────

def _classify_equity(equity: float) -> str:
    if equity >= 0.85: return 'nuts'
    if equity >= 0.70: return 'strong'
    if equity >= 0.55: return 'medium_strong'
    if equity >= 0.40: return 'medium'
    if equity >= 0.25: return 'bluff_catcher'
    return 'air'


# ── 對手詐唬頻率估算 ──────────────────────────────────────────────────────────

def _estimate_villain_bluff_freq(
    villain_range_bluff_pct: float,   # 來自 range_narrower 的弱牌比例
    bet_size_pct:            float,   # 對手下注尺寸（相對底池）
    villain_af:              float,   # HUD Aggression Factor
) -> float:
    """
    估算對手在此注碼下詐唬的頻率。

    大注下注（>75%）通常更極化，詐唬比例接近 GTO 均衡。
    小注下注（<40%）通常合併，詐唬比例較低。
    """
    # 基於 GTO：alpha = bet / (pot + bet) 是均衡詐唬頻率
    alpha = bet_size_pct / (1 + bet_size_pct)

    # 從 range_narrower 的弱牌比例調整（弱牌多 = 更多詐唬空間）
    range_adj = villain_range_bluff_pct * 0.5

    # AF 調整：AF > 2 的積極玩家詐唬更多
    af_adj = max(-0.10, min(0.15, (villain_af - 1.5) * 0.05))

    est = alpha + range_adj * 0.3 + af_adj
    return round(min(0.55, max(0.05, est)), 3)


# ── 薄薄取值分析 ──────────────────────────────────────────────────────────────

def _thin_value_ok(
    equity:             float,
    position:           str,
    villain_range_weak: float,   # 對手範圍中弱牌比例
    pot_bb:             float,
    stack_bb:           float,
) -> Tuple[bool, float, str]:
    """
    判斷是否值得薄薄取值。
    回傳 (should_value, suggested_size_pct, reasoning)

    薄薄取值條件：
      1. equity 40-65%（真正的強牌用大注）
      2. 對手有足夠的弱牌範圍（villain_range_weak > 30%）
      3. 小注（25-40% 底池）讓對手更容易跟注
    """
    spr = stack_bb / pot_bb if pot_bb > 0 else 99

    if equity < 0.40:
        return False, 0.0, '勝率過低，無法取值'
    if equity >= 0.70:
        return True, 0.67, '強牌，建議大注取值'

    if villain_range_weak < 0.25:
        return False, 0.0, '對手範圍太強，薄薄取值難以被跟注'

    # 薄薄取值：尺寸越小越容易被跟注
    if position == 'ip':
        size = 0.35 if equity < 0.55 else 0.50
    else:
        size = 0.28 if equity < 0.55 else 0.40

    # 低 SPR 直接大注
    if spr <= 1.5:
        size = 1.0

    reason = (f'薄薄取值：勝率{equity:.0%}，對手弱牌{villain_range_weak:.0%}，'
              f'建議{int(size*100)}%底池小注')
    return True, size, reason


# ── 面對下注決策 ──────────────────────────────────────────────────────────────

def decide_facing_bet(
    equity:                  float,
    pot_bb:                  float,
    villain_bet_bb:          float,
    position:                str = 'oop',
    villain_range_bluff_pct: float = 0.30,   # 從 range_narrower 取
    villain_af:              float = 1.5,
    blocker_call_score:      float = 0.5,    # 從 blockers.py 取
    stack_bb:                float = 100.0,
) -> RiverDecision:
    """
    面對對手河牌下注，決定跟注/棄牌/加注。

    Args:
        equity:                 手牌勝率（vs 對手下注範圍）
        pot_bb:                 下注前底池
        villain_bet_bb:         對手下注大小
        position:               'ip' 或 'oop'
        villain_range_bluff_pct: 對手範圍中的弱牌比例（來自 range_narrower）
        villain_af:             對手 Aggression Factor（HUD）
        blocker_call_score:     blockers.py 的跟注分數（0-1）
        stack_bb:               有效籌碼
    """
    bet_pct = villain_bet_bb / pot_bb if pot_bb > 0 else 0.5
    alpha = villain_bet_bb / (pot_bb + villain_bet_bb)   # 跟注所需勝率
    mdf   = 1 - alpha
    total_pot = pot_bb + villain_bet_bb

    villain_bluff_freq = _estimate_villain_bluff_freq(
        villain_range_bluff_pct, bet_pct, villain_af
    )

    hand_class = _classify_equity(equity)
    reasons    = []
    tips       = []

    # ── 決策邏輯 ────────────────────────────────────────────────────
    if equity >= alpha + 0.15:
        # 勝率遠超底池賠率 → 考慮加注
        raise_sz = round(pot_bb * 2.3, 1)  # 2.3x 是河牌加注標準
        if stack_bb <= pot_bb * 1.5:
            action = '全下'
            raise_sz = stack_bb
        else:
            action = '加注'
        confidence = 'high'
        reasons.append(f'勝率{equity:.0%}遠超底池賠率{alpha:.0%}，加注取最大EV')
        sizing_bb  = raise_sz
        sizing_pct = raise_sz / pot_bb
    elif equity >= alpha + 0.03:
        action, sizing_bb, sizing_pct = '跟注', 0.0, 0.0
        confidence = 'high' if equity >= alpha + 0.08 else 'medium'
        reasons.append(f'勝率{equity:.0%} > 底池賠率{alpha:.0%}，正EV跟注')
    elif villain_bluff_freq > alpha:
        action, sizing_bb, sizing_pct = '跟注', 0.0, 0.0
        confidence = 'medium' if villain_bluff_freq > alpha + 0.05 else 'low'
        reasons.append(f'對手詐唬頻率{villain_bluff_freq:.0%} > alpha{alpha:.0%}，'
                        f'跟注抓詐唬有利')
        tips.append(f'Bluff catch：對手下注{int(bet_pct*100)}%底池，需要對手詐唬率>{alpha:.0%}才跟注盈利')
    elif blocker_call_score >= 0.65:
        action, sizing_bb, sizing_pct = '跟注', 0.0, 0.0
        confidence = 'low'
        reasons.append(f'阻擋牌有利（call_score={blocker_call_score:.2f}）：你的手牌阻擋對手價值牌')
        tips.append('阻擋效果提升跟注EV，但邊緣決策需謹慎')
    else:
        action, sizing_bb, sizing_pct = '棄牌', 0.0, 0.0
        confidence = 'high' if equity < alpha - 0.08 else 'medium'
        reasons.append(f'勝率{equity:.0%} < 底池賠率{alpha:.0%}，詐唬頻率{villain_bluff_freq:.0%}不足，棄牌')

    # MDF 提示
    tips.append(f'MDF={mdf:.0%}：防守低於此頻率對手可無限詐唬')
    if bet_pct >= 0.80:
        tips.append(f'大注({int(bet_pct*100)}%底池)：極化範圍，詐唬和強牌各半，謹慎評估')
    elif bet_pct <= 0.35:
        tips.append(f'小注({int(bet_pct*100)}%底池)：合併範圍，對手多為薄薄取值')

    # 極化比率
    gto_bluff = alpha
    polar_note = (f'GTO均衡：對手每{round(1/gto_bluff,1) if gto_bluff>0 else "∞"}個價值注，'
                  f'配{1}個詐唬（詐唬{gto_bluff:.0%}）')

    return RiverDecision(
        situation           = 'facing_bet',
        pot_bb              = pot_bb,
        bet_bb              = villain_bet_bb,
        equity              = equity,
        position            = position,
        action              = action,
        action_confidence   = confidence,
        sizing_bb           = sizing_bb,
        sizing_pct          = sizing_pct,
        equity_needed       = round(alpha, 3),
        mdf                 = round(mdf, 3),
        villain_bluff_freq  = villain_bluff_freq,
        alpha               = round(alpha, 3),
        blocker_score       = blocker_call_score,
        thin_value_ok       = False,
        polarization_note   = polar_note,
        reasoning           = '；'.join(reasons),
        tips                = tips,
    )


# ── 主動下注決策 ──────────────────────────────────────────────────────────────

def decide_river_action(
    equity:                  float,
    pot_bb:                  float,
    position:                str = 'ip',
    villain_range_bluff_pct: float = 0.25,   # 對手範圍弱牌比例
    villain_range_strong_pct: float = 0.20,  # 對手範圍強牌比例
    blocker_bluff_score:     float = 0.5,    # blockers.py 的詐唬分數
    blocker_call_score:      float = 0.5,    # blockers.py 的跟注分數
    stack_bb:                float = 100.0,
    villain_fold_to_bet:     float = 0.50,   # 對手對下注的棄牌率
) -> RiverDecision:
    """
    英雄先行動，決定是否下注（取值/詐唬）或過牌（過牌跟注/過牌棄牌）。

    Args:
        villain_range_bluff_pct:  對手弱牌比例（好的詐唬目標）
        villain_range_strong_pct: 對手強牌比例（影響取值風險）
        blocker_bluff_score:      我持有的牌是否阻擋了對手強牌
        blocker_call_score:       我持有的牌是否阻擋了對手跟注牌
    """
    hand_class = _classify_equity(equity)
    spr = stack_bb / pot_bb if pot_bb > 0 else 99
    reasons = []
    tips    = []

    # ── 薄薄取值分析 ────────────────────────────────────────────────
    thin_ok, thin_size, thin_reason = _thin_value_ok(
        equity, position, villain_range_bluff_pct + villain_range_strong_pct * 0.3,
        pot_bb, stack_bb,
    )

    # ── 詐唬 EV 計算 ─────────────────────────────────────────────────
    # EV(bluff) = fold_rate × pot - (1-fold_rate) × bet
    # 最優詐唬尺寸讓對手無差異（alpha 注碼）
    bluff_size_pct = 0.75 if position == 'ip' else 0.60
    bluff_bet = pot_bb * bluff_size_pct
    bluff_alpha = bluff_bet / (pot_bb + bluff_bet)
    ev_bluff = villain_fold_to_bet * pot_bb - (1 - villain_fold_to_bet) * bluff_bet
    bluff_profitable = ev_bluff > 0

    # ── 主要決策 ────────────────────────────────────────────────────
    if hand_class == 'nuts':
        # 超強牌：大注取值
        size_pct = 0.85 if position == 'ip' else 0.67
        if spr <= 1.5: size_pct = 1.0
        action = '下注取值'
        sizing_bb = round(pot_bb * size_pct, 1)
        confidence = 'high'
        reasons.append(f'超強牌（勝率{equity:.0%}），大注取最大值{int(size_pct*100)}%底池')

    elif hand_class == 'strong':
        # 強牌：取值下注
        size_pct = 0.65 if position == 'ip' else 0.50
        action = '下注取值'
        sizing_bb = round(pot_bb * size_pct, 1)
        confidence = 'high'
        reasons.append(f'強牌（{equity:.0%}），取值下注{int(size_pct*100)}%底池')

    elif hand_class == 'medium_strong' and thin_ok:
        # 中等偏強：薄薄取值
        size_pct = thin_size
        action = '薄薄取值'
        sizing_bb = round(pot_bb * size_pct, 1)
        confidence = 'medium'
        reasons.append(thin_reason)
        tips.append('薄薄取值：注碼小，讓對手以為你在詐唬，維持跟注頻率')

    elif hand_class == 'medium_strong' and not thin_ok:
        # 中等偏強但對手範圍緊 → 過牌跟注
        action = '過牌跟注'
        sizing_bb = 0.0
        size_pct = 0.0
        confidence = 'medium'
        reasons.append(f'中等強牌（{equity:.0%}）但對手範圍緊，過牌保留 showdown value')

    elif hand_class == 'medium':
        # 中等牌：通常過牌跟注（取決於對手）
        if blocker_call_score >= 0.65:
            action = '過牌跟注'
            reasons.append(f'中等牌力 + 良好阻擋（call_score={blocker_call_score:.2f}），過牌跟注')
        else:
            action = '過牌棄牌'
            reasons.append(f'中等牌力（{equity:.0%}），對手範圍強，過牌棄牌保守')
        sizing_bb, size_pct = 0.0, 0.0
        confidence = 'medium'

    elif hand_class == 'bluff_catcher':
        # 弱中等：通常過牌棄牌，除非有很好的阻擋牌
        if blocker_call_score >= 0.72 and villain_range_bluff_pct >= 0.35:
            action = '過牌跟注'
            reasons.append(f'Bluff catcher：阻擋效果好 + 對手弱牌多（{villain_range_bluff_pct:.0%}），過牌跟注')
        else:
            action = '過牌棄牌'
            reasons.append(f'弱牌（{equity:.0%}），沒有足夠阻擋效果，過牌棄牌')
        sizing_bb, size_pct = 0.0, 0.0
        confidence = 'medium' if hand_class == 'bluff_catcher' else 'high'

    else:
        # 空氣：考慮詐唬
        if bluff_profitable and blocker_bluff_score >= 0.55:
            action = '詐唬'
            size_pct = bluff_size_pct
            sizing_bb = round(pot_bb * size_pct, 1)
            confidence = 'medium'
            reasons.append(f'詐唬EV={ev_bluff:.1f}BB > 0，阻擋分數{blocker_bluff_score:.2f}，詐唬合理')
            tips.append(f'詐唬{int(size_pct*100)}%底池（={sizing_bb:.1f}BB），'
                        f'需要對手棄牌{bluff_alpha:.0%}才獲利')
        else:
            action = '過牌棄牌'
            size_pct = 0.0
            sizing_bb = 0.0
            confidence = 'high'
            reasons.append(f'空氣（{equity:.0%}），詐唬EV={ev_bluff:.1f}BB，放棄底池')

    # GTO 極化比率
    value_bet = pot_bb * (0.75 if position == 'ip' else 0.60)
    gto_alpha = value_bet / (pot_bb + value_bet)
    tips.append(f'GTO均衡注碼：每{round((1-gto_alpha)/gto_alpha,1)}個價值配1個詐唬')

    return RiverDecision(
        situation           = 'hero_acts_first',
        pot_bb              = pot_bb,
        bet_bb              = 0.0,
        equity              = equity,
        position            = position,
        action              = action,
        action_confidence   = confidence,
        sizing_bb           = round(sizing_bb, 1),
        sizing_pct          = round(size_pct, 2),
        equity_needed       = 0.0,
        mdf                 = 0.0,
        villain_bluff_freq  = 0.0,
        alpha               = round(gto_alpha, 3),
        blocker_score       = max(blocker_bluff_score, blocker_call_score),
        thin_value_ok       = thin_ok,
        polarization_note   = f'GTO詐唬{gto_alpha:.0%}：每{round((1-gto_alpha)/gto_alpha,1)}個價值1個詐唬',
        reasoning           = '；'.join(reasons),
        tips                = tips,
    )


# ── 統一入口 ─────────────────────────────────────────────────────────────────

def analyze_river(
    equity:       float,
    pot_bb:       float,
    position:     str = 'ip',
    villain_bet:  float = 0.0,     # 0 = 對手過牌，英雄先行
    stack_bb:     float = 100.0,
    # 可選：來自 range_narrower 的對手範圍資訊
    villain_bluff_pct:  float = 0.25,
    villain_strong_pct: float = 0.20,
    villain_af:         float = 1.5,
    # 可選：來自 blockers.py 的阻擋分數
    blocker_bluff:  float = 0.5,
    blocker_call:   float = 0.5,
    villain_fold_to_bet: float = 0.50,
) -> RiverDecision:
    """
    統一河牌分析入口：自動判斷是 facing_bet 還是 hero_acts_first。
    """
    if villain_bet > 0:
        return decide_facing_bet(
            equity, pot_bb, villain_bet, position,
            villain_bluff_pct, villain_af, blocker_call, stack_bb,
        )
    else:
        return decide_river_action(
            equity, pot_bb, position,
            villain_bluff_pct, villain_strong_pct,
            blocker_bluff, blocker_call, stack_bb, villain_fold_to_bet,
        )


def river_summary(r: RiverDecision) -> str:
    """單行摘要，用於 overlay 顯示。"""
    conf = {'high': '確定', 'medium': '建議', 'low': '邊緣'}.get(r.action_confidence, '')
    size_str = f' {r.sizing_bb:.1f}BB({int(r.sizing_pct*100)}%底池)' if r.sizing_bb > 0 else ''
    return (f'河牌 [{conf}] {r.action}{size_str}  '
            f'勝率{r.equity:.0%}  '
            f'{r.reasoning[:35]}')
