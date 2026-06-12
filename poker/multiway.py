"""
多人底池策略調整器 (Multiway Pot Advisor)

3人+底池策略與單挑截然不同：
  - 詐唬需要所有對手同時棄牌 → fold equity 指數下降
  - 價值要求提高（對手中獎概率更高）
  - C-bet 頻率須大幅降低
  - 過牌-跟注範圍需擴大

核心公式：
  fold_equity(N) = fold_rate ^ N   (N 個對手都要棄)
  value_threshold(N) = base_threshold + N * 0.08
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class MultiwayResult:
    num_opponents:      int
    pot_bb:             float
    bet_bb:             float

    # C-bet 建議
    cbet_recommended:   bool
    cbet_freq:          float        # 建議頻率（0-1）
    cbet_size_pct:      float        # 建議注碼（底池比例）

    # 價值/詐唬閾值
    value_equity_min:   float        # 需要這個以上勝率才建議下注取值
    bluff_allowed:      bool         # 多人底池是否建議詐唬
    bluff_max_freq:     float        # 詐唬上限頻率

    # 折疊勝算
    fold_equity:        float        # 預估對手全員棄牌機率
    fold_equity_needed: float        # 詐唬獲利需要的最低棄牌機率

    # 行動建議
    recommended_action: str          # 'bet_value'/'check'/'bet_bluff'
    reasoning:          str
    tips:               List[str] = field(default_factory=list)


# 按玩家類型估算單人棄牌率（面對 ~50% 底池下注）
_DEFAULT_FOLD_RATE = 0.52   # 普通玩家對 50% 底池 C-bet 的棄牌率


def analyze_multiway(
    num_opponents:    int,
    pot_bb:           float,
    equity:           float,
    in_position:      bool = True,
    street:           str = 'flop',      # 'flop'/'turn'/'river'
    bet_size_pct:     float = 0.5,
    per_opp_fold_rate: float = _DEFAULT_FOLD_RATE,
) -> MultiwayResult:
    """
    分析多人底池的最佳策略。

    Args:
        num_opponents:       對手人數（不含英雄）
        pot_bb:              目前底池（BB）
        equity:              英雄手牌勝率（蒙地卡羅估算）
        in_position:         是否有位置優勢
        street:              目前街道
        bet_size_pct:        考慮下注的注碼比例
        per_opp_fold_rate:   每位對手對下注的估算棄牌率
    """
    n = max(1, num_opponents)

    # ── 折疊勝算（所有對手同時棄牌）──────────────────────────────
    fold_equity = per_opp_fold_rate ** n

    # 詐唬獲利所需的最低棄牌機率
    # EV(bluff) ≥ 0  →  fold_eq × pot ≥ (1-fold_eq) × bet
    # fold_eq ≥ bet / (pot + bet)
    bet_bb = pot_bb * bet_size_pct
    fold_needed = bet_bb / (pot_bb + bet_bb) if (pot_bb + bet_bb) > 0 else 0.5

    # ── 價值下注閾值（多人底池需更強牌力）────────────────────────
    base_value_thresh = 0.55   # 單挑最低價值下注勝率
    value_thresh = min(0.85, base_value_thresh + (n - 1) * 0.07)

    # 無位置再提高
    if not in_position:
        value_thresh = min(0.90, value_thresh + 0.05)

    # ── C-bet 頻率（多人底池大幅降低）────────────────────────────
    # 翻牌單挑基準約 60%，每增加一位對手降低 18pp
    base_cbet = {'flop': 0.62, 'turn': 0.52, 'river': 0.45}.get(street, 0.55)
    if not in_position:
        base_cbet *= 0.85
    cbet_freq = max(0.05, base_cbet - (n - 1) * 0.18)

    # ── 詐唬決策 ──────────────────────────────────────────────────
    bluff_allowed = fold_equity >= fold_needed and n <= 2
    # 3人+底池幾乎不應詐唬，除非有強 blocker
    bluff_max_freq = max(0.0, fold_equity - fold_needed) if bluff_allowed else 0.0
    if n >= 3:
        bluff_allowed = False
        bluff_max_freq = 0.0

    # ── 建議下注注碼（多人底池縮小）──────────────────────────────
    if n >= 3:
        rec_size = 0.33  # 小注保護，避免嚇跑所有人
    elif n == 2:
        rec_size = 0.45
    else:
        rec_size = bet_size_pct

    cbet_recommended = equity >= value_thresh or (bluff_allowed and fold_equity >= fold_needed + 0.05)

    # ── 建議行動 ──────────────────────────────────────────────────
    if equity >= value_thresh:
        action = 'bet_value'
    elif bluff_allowed and fold_equity > fold_needed:
        action = 'bet_bluff'
    else:
        action = 'check'

    # ── 理由 ──────────────────────────────────────────────────────
    reasons = []
    if n >= 3:
        reasons.append(f'{n}人底池：詐唬 EV 極低（棄牌率僅 {fold_equity:.0%}）')
    elif n == 2:
        reasons.append(f'2人底池：棄牌率 {fold_equity:.0%}，可選擇性詐唬')

    if action == 'bet_value':
        reasons.append(f'勝率 {equity:.0%} ≥ 多人底池價值門檻 {value_thresh:.0%}，建議下注取值')
    elif action == 'check':
        reasons.append(f'勝率 {equity:.0%} 低於門檻 {value_thresh:.0%}，詐唬無利可圖，建議過牌')
    elif action == 'bet_bluff':
        reasons.append(f'折疊勝算 {fold_equity:.0%} > 需求 {fold_needed:.0%}，可詐唬')

    # ── 小提示 ─────────────────────────────────────────────────────
    tips = []
    if n >= 2:
        tips.append(f'多人底池：價值閾值升至 {value_thresh:.0%}（單挑 55%）')
    if n >= 3:
        tips.append('3人+底池：幾乎不詐唬，只下注強牌保護和建鍋')
    if not in_position:
        tips.append('無位置：過牌-加注範圍擴大，避免被對手浮牌')
    if equity >= value_thresh:
        tips.append(f'建議注碼：{int(rec_size*100)}% 底池（={round(pot_bb*rec_size,1)}BB）')
    if street == 'flop' and n >= 2:
        tips.append('翻牌多人：優先保護手牌，次要考慮詐唬')

    return MultiwayResult(
        num_opponents      = n,
        pot_bb             = pot_bb,
        bet_bb             = bet_bb,
        cbet_recommended   = cbet_recommended,
        cbet_freq          = round(cbet_freq, 2),
        cbet_size_pct      = rec_size,
        value_equity_min   = round(value_thresh, 2),
        bluff_allowed      = bluff_allowed,
        bluff_max_freq     = round(bluff_max_freq, 2),
        fold_equity        = round(fold_equity, 3),
        fold_equity_needed = round(fold_needed, 3),
        recommended_action = action,
        reasoning          = '；'.join(reasons),
        tips               = tips,
    )


def multiway_summary(r: MultiwayResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    action_zh = {
        'bet_value': f'下注取值（{int(r.cbet_size_pct*100)}% 底池）',
        'bet_bluff': f'詐唬（{int(r.cbet_size_pct*100)}% 底池）',
        'check':     '過牌（多人底池勝率不足）',
    }.get(r.recommended_action, '')
    return (f'{r.num_opponents}人底池  {action_zh}  '
            f'C-bet {int(r.cbet_freq*100)}%  '
            f'棄牌率 {int(r.fold_equity*100)}%')


def multiway_equity_adjustment(equity: float, num_opponents: int) -> float:
    """
    多人底池勝率調整：N人底池中英雄的「有效勝率」。
    近似：在 N 位對手中，每位都有 (1-equity)/N 的勝率，
    但非線性——對手的最強牌才能獲勝。
    簡化：equity_adj = equity ^ (1 + 0.15*(N-1))
    """
    if num_opponents <= 1:
        return equity
    exponent = 1.0 + 0.15 * (num_opponents - 1)
    return round(equity ** exponent, 3)
