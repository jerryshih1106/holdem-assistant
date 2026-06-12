"""
Check-Raise 決策顧問 (Check-Raise Decision Advisor)

面對對手下注時（翻牌/轉牌），OOP 玩家何時應該 Check-Raise？

策略背景：
  Check-Raise 是 OOP 玩家保護 checking range、防止對手無限小注的工具。
  缺少 check-raise range → 對手可以對你的每一個 check 都自動小注獲利。

三種 Check-Raise 類型：
  1. 價值 Check-Raise (Value CR)
     - 需要強牌（前 15-20% vs 對手範圍）
     - 兩對/三條/強超對/頂對頂踢腳（部分）
     - 目標：建底池，同時讓對手面對艱難跟注決策

  2. 半詐唬 Check-Raise (Semi-Bluff CR)
     - 強聽牌（同花聽牌 9 outs、兩端順子 8 outs、Combo draw 12+）
     - 有 fold equity：對手棄牌時立即獲利；跟注後仍有機會完成聽牌
     - 濕潤牌面（連張+同花）更適合半詐唬 CR

  3. 純詐唬 Check-Raise (Bluff CR)
     - 頻率極低（5-10%），只在特定條件下執行
     - 需要：blockers + 可信 story + 對手 FCbet 高
     - 風險最高，只在有明顯折疊勝算時使用

Check-Raise 頻率（vs 33% 底池 C-bet）：
  GTO 均衡下 CR 頻率 ≈ 10-20%（依牌面和位置）
  - 乾燥牌面（A-high dry rainbow）：低頻（8-12%）
  - 連張/同花牌面（678 two-tone）：高頻（18-25%）
  - 高牌配對牌面：低頻（10%）

Check-Raise 注碼：
  通常 = 對手下注 × 2.5-3 倍 + alpha 保護
  例：對手下注 4BB，CR = 12-14BB
  避免過小（對手賠率過好）或過大（無謂犯規）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from poker.board_texture import analyze_board, BoardTexture
from poker.mdf import analyse_bet


@dataclass
class CheckRaiseResult:
    # 輸入摘要
    street:             str
    equity:             float
    hand_percentile:    float    # 0-1，vs villain range
    pot_bb:             float
    villain_bet_bb:     float

    # 決策
    action:             str      # 'value_cr' / 'semibleff_cr' / 'bluff_cr' / 'call' / 'fold'
    action_zh:          str      # 中文
    cr_freq:            float    # check-raise 頻率
    cr_size_bb:         float    # check-raise 注碼（BB）
    cr_size_pct:        float    # check-raise 注碼（底池 %）

    # 分析
    is_value:           bool
    is_semibleff:       bool
    is_bluff:           bool
    hand_class:         str      # 'strong'/'draw'/'weak'
    draw_outs:          int      # 聽牌 outs 數量
    fold_equity:        float    # 對手面對 CR 的折疊率
    alpha:              float    # 對手保本折疊率 = CR / (pot + CR)

    # 牌面
    texture:            Optional[BoardTexture]
    board_wetness:      float

    # 輸出
    reasoning:          str
    tips:               List[str] = field(default_factory=list)


# ── 輔助函數 ──────────────────────────────────────────────────────────────────

def _estimate_draw_outs(hole: List[str], community: List[str]) -> int:
    """估算聽牌 outs（不 import outs.py 以避免 circular，使用近似邏輯）。"""
    if len(hole) < 2 or len(community) < 3:
        return 0
    try:
        from poker.outs import count_outs
        result = count_outs(hole, community, pot_size=10, call_amount=3)
        return result.total_outs
    except Exception:
        return 0


def _cr_size(villain_bet_bb: float, pot_bb: float) -> Tuple[float, float]:
    """
    計算最優 check-raise 注碼。

    標準：CR = villain_bet × 2.5 到 3.0，最少保留合理的 alpha。
    也要確保 CR 注碼相對底池至少 2x（對手不能便宜跟注）。

    回傳 (cr_bb, cr_pct_of_pot)
    """
    # 最小 CR 注碼：villain bet × 2.5
    min_cr = villain_bet_bb * 2.5
    # 理想 CR 注碼：建底池同時讓對手 alpha ≈ 30-40%
    # pot_after_call = pot + villain_bet + villain_bet (英雄跟注)
    pot_after_hero_call = pot_bb + 2 * villain_bet_bb
    ideal_cr = max(min_cr, pot_after_hero_call * 0.75)
    cr_bb = round(max(min_cr, ideal_cr), 1)
    cr_pct = round(cr_bb / (pot_bb + villain_bet_bb), 2)
    return cr_bb, cr_pct


def _villain_fold_vs_cr(
    villain_bet_bb:  float,
    pot_bb:          float,
    villain_cbet_pct: float = 0.60,
    villain_af:      float = 1.5,
) -> float:
    """
    估算對手面對 CR 的棄牌率。

    高頻 C-bet 玩家 (cbet > 65%) 通常包含更多詐唬 → 面對 CR 棄牌更多。
    高 AF 玩家 (> 2.0) 更可能繼續 → 棄牌更少。
    """
    base_fold = 0.55   # 預設基準：對手 CR 後棄牌 55%

    # C-bet 頻率調整：高頻 cbet 包含更多空氣 → 面對 CR 更多棄牌
    cbet_adj = (villain_cbet_pct - 0.60) * 0.40
    # AF 調整：高 AF 玩家更積極 → 面對 CR 不易棄牌
    af_adj = -(villain_af - 1.5) * 0.08

    fold_rate = max(0.25, min(0.80, base_fold + cbet_adj + af_adj))
    return round(fold_rate, 2)


# ── 主函數 ────────────────────────────────────────────────────────────────────

def analyze_check_raise(
    hole_cards:         List[str],
    community:          List[str],
    villain_bet_bb:     float,
    pot_bb:             float,
    equity:             float = 0.50,
    hand_percentile:    float = 0.50,    # 來自 hand_percentile.py（0-1）
    position:           str   = 'oop',   # 通常 OOP 才考慮 CR
    villain_cbet_pct:   float = 0.60,
    villain_af:         float = 1.5,
    villain_vpip:       float = 0.30,
    eff_stack_bb:       float = 100.0,
) -> CheckRaiseResult:
    """
    分析面對對手下注時是否應 check-raise。

    Args:
        hole_cards:        英雄手牌
        community:         公牌（3 或 4 張）
        villain_bet_bb:    對手下注金額（BB）
        pot_bb:            下注前底池
        equity:            英雄勝率（0-1）
        hand_percentile:   英雄手牌在對手範圍中的百分位（0-1）
        position:          'oop'（需要在 IP 對手 C-bet 後 OOP 判斷）
        villain_cbet_pct:  對手 C-bet 頻率（HUD）
        villain_af:        對手 AF
        villain_vpip:      對手 VPIP
        eff_stack_bb:      有效籌碼
    """
    street = {3: 'flop', 4: 'turn'}.get(len(community), 'flop')
    street_zh = {'flop': '翻牌', 'turn': '轉牌'}.get(street, '翻牌')

    # ── 牌面分析 ─────────────────────────────────────────────────────────────
    texture: Optional[BoardTexture] = None
    wetness = 0.30
    if community:
        try:
            texture = analyze_board(community)
            wetness = texture.wetness
        except Exception:
            pass

    # ── 聽牌 outs ────────────────────────────────────────────────────────────
    draw_outs = _estimate_draw_outs(hole_cards, community)
    has_flush_draw   = draw_outs >= 9
    has_oesd         = 7 <= draw_outs < 9
    has_gutshot      = 4 <= draw_outs < 7
    has_combo_draw   = draw_outs >= 12
    is_strong_draw   = has_flush_draw or has_oesd or has_combo_draw

    # ── 手牌分類 ─────────────────────────────────────────────────────────────
    if hand_percentile >= 0.80:
        hand_class = 'strong'   # 強牌：兩對/三條/超對
    elif hand_percentile >= 0.65:
        hand_class = 'top_pair' # 頂對強踢腳
    elif is_strong_draw:
        hand_class = 'draw'     # 強聽牌
    elif hand_percentile >= 0.45:
        hand_class = 'medium'   # 中等：弱頂對/中對
    else:
        hand_class = 'weak'     # 弱牌

    # ── 計算 CR 注碼和 alpha ─────────────────────────────────────────────────
    cr_bb, cr_pct = _cr_size(villain_bet_bb, pot_bb)

    # 對手保本折疊率
    total_pot_if_cr = pot_bb + villain_bet_bb + cr_bb
    alpha = villain_bet_bb / (pot_bb + 2 * villain_bet_bb + cr_bb)  # 對手跟注賠率
    alpha = round(alpha, 3)

    # 對手實際折疊率估算
    fold_eq = _villain_fold_vs_cr(villain_bet_bb, pot_bb, villain_cbet_pct, villain_af)

    # ── 確定 Check-Raise 類型和建議 ──────────────────────────────────────────
    reasons = []
    tips    = []

    is_value     = False
    is_semibleff = False
    is_bluff     = False

    if hand_class == 'strong':
        is_value = True
        action_type = 'value_cr'
        base_freq   = 0.85
        reasons.append(f'強牌（百分位{hand_percentile:.0%}）→ 價值 CR 建底池')

    elif hand_class == 'top_pair' and wetness >= 0.40:
        # 潮濕牌面的頂對可以 CR 防守
        is_value    = True
        action_type = 'value_cr'
        base_freq   = 0.55
        reasons.append(f'頂對 + 潮濕牌面 → 保護性 CR（防止對手廉價看轉牌）')

    elif has_combo_draw:
        is_semibleff = True
        action_type  = 'semibleff_cr'
        base_freq    = 0.75
        reasons.append(f'Combo draw ({draw_outs} outs) → 半詐唬 CR，fold 即贏，call 有聽牌勝率')

    elif is_strong_draw and fold_eq >= 0.45:
        is_semibleff = True
        action_type  = 'semibleff_cr'
        draw_type    = '同花聽牌' if has_flush_draw else '兩端順子聽牌'
        base_freq    = 0.60
        reasons.append(f'{draw_type}（{draw_outs} outs）+ fold equity {fold_eq:.0%} → 半詐唬 CR')

    elif hand_class == 'weak' and villains_fold_high(villain_cbet_pct, villain_af):
        is_bluff    = True
        action_type = 'bluff_cr'
        base_freq   = 0.10
        reasons.append(f'對手 CBet 頻率高({villain_cbet_pct:.0%})，偶爾純詐唬 CR（低頻）')

    else:
        # 不適合 CR：跟注或棄牌
        bet_pct   = villain_bet_bb / (pot_bb + villain_bet_bb)
        pot_odds  = villain_bet_bb / (pot_bb + 2 * villain_bet_bb)
        if equity >= pot_odds:
            action_type = 'call'
            base_freq   = 0.0
            reasons.append(f'跟注有利：勝率{equity:.0%} > 底池賠率{pot_odds:.0%}')
        else:
            action_type = 'fold'
            base_freq   = 0.0
            reasons.append(f'棄牌：勝率{equity:.0%} < 底池賠率{pot_odds:.0%}，手牌弱')

    # ── 頻率調整 ─────────────────────────────────────────────────────────────
    cr_freq = base_freq

    # 牌面潮濕度調整（更潮濕 → 更高頻 CR，保護聽牌）
    if action_type in ('value_cr', 'semibleff_cr'):
        cr_freq *= (0.85 + wetness * 0.30)
        cr_freq = min(1.0, cr_freq)

    # 位置：IP 也可以 CR（相對少見）
    if position == 'ip':
        cr_freq *= 0.60
        tips.append('IP 玩家 check-raise 較少見，通常傾向 bet 或 check-call')

    # 對手 AF 高 → CR 後他可能再次加注，謹慎
    if villain_af >= 2.5:
        tips.append(f'對手 AF={villain_af:.1f} 積極，CR 後可能面對 4-bet，確保手牌夠強')

    # 短籌碼：CR 後 SPR 可能很低，需要承諾
    spr_after_cr = (eff_stack_bb - cr_bb) / (pot_bb + cr_bb + villain_bet_bb)
    if spr_after_cr < 1.5:
        tips.append(f'CR 後 SPR={spr_after_cr:.1f} 極低，等同承諾全下 — 確保手牌值得')

    # ── 中文行動標籤 ─────────────────────────────────────────────────────────
    action_zh_map = {
        'value_cr':      f'價值 Check-Raise ({cr_bb:.1f}BB)',
        'semibleff_cr':  f'半詐唬 Check-Raise ({cr_bb:.1f}BB)',
        'bluff_cr':      f'純詐唬 Check-Raise ({cr_bb:.1f}BB)',
        'call':          f'跟注 ({villain_bet_bb:.1f}BB)',
        'fold':          '棄牌',
    }
    action_zh = action_zh_map.get(action_type, action_type)

    # 標準提示
    if action_type.endswith('_cr'):
        tips.insert(0, f'CR 注碼建議：{cr_bb:.1f}BB（{int(cr_pct*100)}% 底池），對手保本折疊率 alpha={alpha:.0%}')
        if fold_eq < alpha:
            tips.append(f'折疊勝算{fold_eq:.0%} < alpha{alpha:.0%}：CR 只有在叫注時有股票才合算（半詐唬必要）')

    return CheckRaiseResult(
        street          = street_zh,
        equity          = equity,
        hand_percentile = hand_percentile,
        pot_bb          = pot_bb,
        villain_bet_bb  = villain_bet_bb,
        action          = action_type,
        action_zh       = action_zh,
        cr_freq         = round(min(1.0, cr_freq), 2),
        cr_size_bb      = cr_bb,
        cr_size_pct     = cr_pct,
        is_value        = is_value,
        is_semibleff    = is_semibleff,
        is_bluff        = is_bluff,
        hand_class      = hand_class,
        draw_outs       = draw_outs,
        fold_equity     = fold_eq,
        alpha           = alpha,
        texture         = texture,
        board_wetness   = wetness,
        reasoning       = '；'.join(reasons),
        tips            = tips,
    )


def villains_fold_high(cbet_pct: float, af: float) -> bool:
    """判斷對手是否面對 CR 容易棄牌（純詐唬 CR 的前提）。"""
    return cbet_pct >= 0.65 and af <= 1.8


def cr_summary(r: CheckRaiseResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    if r.action.endswith('_cr'):
        cr_type = {'value_cr': '取值', 'semibleff_cr': '半詐唬', 'bluff_cr': '詐唬'}.get(r.action, '')
        return (f'{r.street} Check-Raise({cr_type}) {r.cr_freq:.0%}  '
                f'{r.cr_size_bb:.1f}BB  fold_eq={r.fold_equity:.0%}')
    return f'{r.street} {r.action_zh}  勝率{r.equity:.0%}'


def analyze_facing_bet(
    hole_cards:       List[str],
    community:        List[str],
    villain_bet_bb:   float,
    pot_bb:           float,
    equity:           float = 0.50,
    hand_percentile:  float = 0.50,
    position:         str   = 'oop',
    villain_cbet_pct: float = 0.60,
    villain_af:       float = 1.5,
    eff_stack_bb:     float = 100.0,
) -> CheckRaiseResult:
    """
    統一入口：面對對手下注時的完整決策（翻牌/轉牌）。
    自動判斷 check-raise / call / fold。
    """
    return analyze_check_raise(
        hole_cards, community, villain_bet_bb, pot_bb,
        equity, hand_percentile, position,
        villain_cbet_pct, villain_af, 0.30, eff_stack_bb,
    )
