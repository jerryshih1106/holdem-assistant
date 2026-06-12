"""
SPR 多街承諾規劃器 (Stack-to-Pot Ratio Multi-Street Planner)

SPR = 有效籌碼 / 底池大小

核心用途：
  「在這個 SPR 下，我需要什麼牌力才應該把籌碼推進去？
   如果要推，各街應該怎麼注？」

SPR 分類與承諾門檻（以 100BB 深度為標準）：
  SPR < 2   : Micro — 任何頂對以上即可 stack-off
  SPR 2-5   : 低    — 需要頂對好踢腳，或者超對 (overpair)
  SPR 5-13  : 中    — 需要兩對或以上才考慮 stack-off；吊三條機會佳
  SPR > 13  : 高    — 需要順子/同花以上；同花/順子聽牌隱含賠率絕佳

幾何注碼規劃 (Geometric Sizing)：
  給定 SPR，計算使底池在 N 街後達到籌碼深度所需的各街注碼比例。
  公式：每街注碼 = 底池 × factor，factor 由 SPR 和剩餘街數決定。
  例：SPR=6, 3 街計劃 → Flop 33% + Turn 50% + River 75% ≈ 全下

使用：
    from poker.spr_planner import analyze_spr
    plan = analyze_spr(pot_bb=12, eff_stack_bb=72, hand_pct=0.75, n_comm=3)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math


@dataclass
class SPRPlan:
    # 輸入
    pot_bb:           float
    eff_stack_bb:     float
    spr:              float
    streets_left:     int        # 翻牌=3街，轉牌=2街，河牌=1街

    # 分類
    spr_category:     str        # 'micro'/'low'/'medium'/'high'
    spr_label_zh:     str        # 中文標籤

    # 承諾決策
    commit_threshold: str        # 需要什麼牌力才 stack-off
    hand_clears_bar:  bool       # 英雄手牌是否達到 commit 門檻
    should_commit:    bool       # 是否建議推進籌碼
    commit_urgency:   str        # 'now'/'plan_for_it'/'be_cautious'/'avoid'

    # 幾何注碼計劃
    geo_sizes:        List[float]   # 各街建議注碼（底池 %），長度=streets_left
    geo_sizes_bb:     List[float]   # 換算成 BB
    get_in_by_street: str           # '翻牌'/'轉牌'/'河牌'/'不計劃'

    # EV 估算
    pot_odds_if_call: float         # 若面對下注的底池賠率
    breakeven_equity: float         # 保本勝率

    reasoning:        str
    tips:             List[str] = field(default_factory=list)


# ── SPR 分類表 ─────────────────────────────────────────────────────────────────

_SPR_CATEGORIES = [
    # (max_spr, category, zh_label, commit_threshold, urgency)
    (2.0,  'micro',  '微 SPR（幾乎全下）',      '任何頂對或更強',       'now'),
    (4.0,  'low',    '低 SPR（積極承諾）',       '頂對好踢腳或超對',     'now'),
    (7.0,  'medium', '中低 SPR（謹慎承諾）',     '強兩對/頂三條以上',    'plan_for_it'),
    (13.0, 'medium', '中高 SPR（需強牌）',       '順子/同花/強兩對',     'plan_for_it'),
    (float('inf'), 'high', '高 SPR（隱含賠率局）', '順子/同花以上',       'be_cautious'),
]


def _categorize_spr(spr: float) -> Tuple[str, str, str, str]:
    """回傳 (category, zh_label, commit_threshold, urgency)。"""
    for max_s, cat, zh, thresh, urgency in _SPR_CATEGORIES:
        if spr <= max_s:
            return cat, zh, thresh, urgency
    return 'high', '極高 SPR', '近乎堅果牌', 'avoid'


# ── 幾何注碼計算 ───────────────────────────────────────────────────────────────

def _geometric_sizes(spr: float, streets_left: int) -> List[float]:
    """
    計算各街的注碼比例（相對底池），目標是在 streets_left 街內達到全下。

    基於 solver 常用的幾何規劃：
      若 SPR=S，需要在 N 街把底池擴大到 S 倍以上以囊括所有籌碼。
      每街注碼 f 滿足：∏(1+2f)^N ≈ SPR + 1
      → f = (SPR+1)^(1/N)/2 - 0.5（近似）

    對 SPR 極大時，只取值不強行推進。
    """
    if spr <= 0 or streets_left == 0:
        return []

    if spr > 20:
        # 高 SPR：保守注碼，不計劃 stack-off
        return [0.50 if streets_left >= 3 else 0.67] * min(2, streets_left)

    # 河牌（單街）：直接用合理的取值注碼，不強求 stack-off
    if streets_left == 1:
        if spr <= 0.8:
            return [round(min(spr, 1.0), 2)]   # 幾乎全下
        elif spr <= 2.0:
            return [0.75]   # 75% 底池
        else:
            return [0.60]   # 60% 底池（取值為主）

    # 目標：每街注碼 × 邊注 → 擴大底池到全包含籌碼
    # f = (spr+1)^(1/N) / 2 - 0.5
    factor = ((spr + 1) ** (1 / streets_left)) / 2 - 0.5
    factor = max(0.25, min(1.00, factor))  # 夾在合理區間（最大底池注）

    # 採用遞增注碼（後街注碼更大，更符合實戰）
    sizes = []
    remaining_spr = spr
    for i in range(streets_left):
        if remaining_spr <= 0.8:
            # 餘下籌碼相對底池很少 → 全下或大注
            sizes.append(min(1.0, remaining_spr))
        else:
            # 本街注碼
            this_factor = factor * (1.0 + i * 0.15)  # 後街稍大
            this_factor = min(this_factor, remaining_spr)
            sizes.append(round(this_factor, 2))
            remaining_spr /= (1 + 2 * this_factor)

    return [round(s, 2) for s in sizes]


# ── 手牌強度判斷 ───────────────────────────────────────────────────────────────

def _hand_clears_commit(
    hand_percentile: float,   # 0-1，在對手範圍中的百分位
    spr_cat:         str,
) -> bool:
    """
    根據 SPR 分類，判斷手牌百分位是否達到承諾門檻。

    hand_percentile 來自 hand_percentile.py 的計算結果。
    """
    thresholds = {
        'micro':  0.55,   # 任何略強於平均即可 stack-off
        'low':    0.70,   # 需要前 30% 的強度
        'medium': 0.80,   # 需要前 20% 的強度
        'high':   0.90,   # 需要前 10% 的強度
    }
    return hand_percentile >= thresholds.get(spr_cat, 0.80)


# ── 主函數 ────────────────────────────────────────────────────────────────────

def analyze_spr(
    pot_bb:           float,
    eff_stack_bb:     float,
    hand_percentile:  float = 0.60,    # 來自 hand_percentile.py（0-1）
    n_comm:           int   = 3,       # 公牌張數（3=翻牌,4=轉牌,5=河牌）
    in_position:      bool  = True,
    villain_fold_pct: float = 0.50,    # 對手對我們加注的棄牌率（影響 FE）
) -> SPRPlan:
    """
    分析 SPR 並給出多街承諾建議。

    Args:
        pot_bb:           目前底池（BB）
        eff_stack_bb:     有效籌碼（BB）— 兩人中較小的那個
        hand_percentile:  英雄手牌在對手範圍中的百分位（來自 hand_percentile 模組）
        n_comm:           公牌張數（3=翻牌, 4=轉牌, 5=河牌）
        in_position:      是否有位置
        villain_fold_pct: 對手棄牌率（影響半詐唬 EV）
    """
    spr = eff_stack_bb / pot_bb if pot_bb > 0 else float('inf')
    streets_left = max(1, 6 - n_comm)   # 翻牌=3街, 轉牌=2街, 河牌=1街

    cat, zh, thresh, urgency = _categorize_spr(spr)
    clears = _hand_clears_commit(hand_percentile, cat)

    # ── 承諾決策 ─────────────────────────────────────────────────────────────
    if not clears and urgency in ('now', 'plan_for_it'):
        urgency = 'be_cautious'
    if hand_percentile >= 0.92:
        urgency = 'now'   # 堅果/超強手牌永遠推進

    should_commit = clears and urgency in ('now', 'plan_for_it')

    # ── 幾何注碼計算 ─────────────────────────────────────────────────────────
    geo_sizes = _geometric_sizes(spr, streets_left)
    geo_sizes_bb = [round(s * pot_bb, 1) for s in geo_sizes]

    # 預計在哪一街堆進底池
    street_names = ['翻牌', '轉牌', '河牌']
    if not should_commit or not geo_sizes:
        get_in_by = '不計劃推進'
    else:
        # 找到我們的籌碼會在哪街被推完
        cum_pot = pot_bb
        get_in_by = '河牌'   # default
        for i, f in enumerate(geo_sizes):
            bet = f * cum_pot
            if eff_stack_bb <= bet * 1.5:
                get_in_by = street_names[i] if i < len(street_names) else '河牌'
                break
            cum_pot += 2 * bet

    # ── 保本勝率 ─────────────────────────────────────────────────────────────
    # 假設下注 33% 底池：alpha = 0.33/(1+0.33) = 25%
    bet_frac = geo_sizes[0] if geo_sizes else 0.33
    breakeven = bet_frac / (1 + 2 * bet_frac + bet_frac)  # 對手跟注時保本
    pot_odds_if_call = round(bet_frac / (1 + 2 * bet_frac), 3)

    # ── 建議理由 ─────────────────────────────────────────────────────────────
    reasons = [
        f'SPR = {spr:.1f}（{zh}）',
        f'手牌百分位 {hand_percentile:.0%} vs 門檻 {thresh}',
    ]
    if should_commit:
        reasons.append(f'建議計劃推進：各街注碼 {[int(s*100) for s in geo_sizes]}% 底池')
        reasons.append(f'預計在{get_in_by}達到 stack-off')
    else:
        if not clears:
            reasons.append(f'手牌未達承諾門檻（{hand_percentile:.0%} < {thresh}）')
        reasons.append('建議控制底池大小（pot control）')

    tips = [
        f'SPR {spr:.1f}：{thresh}才考慮 stack-off',
    ]
    if spr <= 4:
        tips.append(f'低 SPR 局：翻牌一旦有中牌或更強，建議快速建底池')
    elif spr <= 13:
        tips.append(f'中 SPR 局：吊三條隱含賠率佳；純頂對需要慎重 stack-off')
    else:
        tips.append(f'高 SPR 局：聽牌的隱含賠率很高；一對很難 stack-off')

    oop_note = '（OOP 時承諾門檻應稍高）' if not in_position else ''
    if oop_note:
        tips.append(oop_note)

    return SPRPlan(
        pot_bb           = pot_bb,
        eff_stack_bb     = eff_stack_bb,
        spr              = round(spr, 2),
        streets_left     = streets_left,
        spr_category     = cat,
        spr_label_zh     = zh,
        commit_threshold = thresh,
        hand_clears_bar  = clears,
        should_commit    = should_commit,
        commit_urgency   = urgency,
        geo_sizes        = geo_sizes,
        geo_sizes_bb     = geo_sizes_bb,
        get_in_by_street = get_in_by,
        pot_odds_if_call = pot_odds_if_call,
        breakeven_equity = round(breakeven, 3),
        reasoning        = '；'.join(reasons),
        tips             = tips,
    )


def spr_summary(plan: SPRPlan) -> str:
    """單行摘要，用於 overlay 顯示。"""
    commit_str = f'推進→{plan.get_in_by_street}' if plan.should_commit else '控制底池'
    if plan.should_commit and plan.geo_sizes:
        sizes_str = '/'.join(f'{int(s*100)}%' for s in plan.geo_sizes)
        return f'SPR {plan.spr:.1f} {plan.spr_label_zh[:4]}  {commit_str}  注碼:{sizes_str}底池'
    return f'SPR {plan.spr:.1f} {plan.spr_label_zh[:4]}  {commit_str}'


def quick_spr(
    pot_bb:      float,
    stack_bb:    float,
    hand_pct:    float = 0.60,
    n_comm:      int   = 3,
) -> str:
    """一行快速查詢。"""
    return spr_summary(analyze_spr(pot_bb, stack_bb, hand_pct, n_comm))
