"""
多街詐唬規劃器 (Multi-Street Bluff Planner)

回答：「我打算在接下來的 N 街詐唬，每街要求的棄牌率是多少才保本？」

核心邏輯：
  每街詐唬的 EV = (fold_equity × pot) - (1-fold_equity) × bet
  要讓詐唬保本（EV >= 0）：
    fold_equity >= bet / (pot + bet) = alpha

  但多街詐唬是連鎖的：
    Street 1 不棄牌 → 進入 Street 2 → Street 2 不棄牌 → 進入 Street 3

  所以總保本公式：
    P(fold_street1) + P(no_fold_1) × P(fold_street2) + ... >= 總成本/總底池

  直觀理解：
    33% 底池的 alpha = 25%
    若翻牌+轉牌都下 33%，河牌詐唬需要的保本棄牌率反而更高
    → 多街詐唬更貴，要求更謹慎

典型問答：
  「BTN vs BB，翻牌 40% + 轉牌 55% + 河牌 75%，整體保本棄牌率是多少？」
  → 單街保本率分別 29%/35%/43%，但組合保本率是 67%
  → 意思是：如果對手整體下三條街棄牌率不到 67%，這個詐唬計劃虧錢
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class BluffStreet:
    street_name:    str      # '翻牌'/'轉牌'/'河牌'
    bet_pct:        float    # 本街下注額佔底池比例（0-1）
    pot_before:     float    # 下注前的底池（BB）
    bet_amount:     float    # 本街下注額（BB）
    alpha:          float    # 本街保本棄牌率 = bet/(pot+bet)
    stack_committed: float   # 本街後已投入的總額


@dataclass
class BluffPlan:
    # ── 輸入情境 ──────────────────────────────────────────────────────────────
    streets:            List[BluffStreet]
    n_streets:          int         # 計劃跨越幾街詐唬
    total_investment:   float       # 整個詐唬計劃投入的總額（BB）
    starting_pot:       float       # 第一街開始的底池

    # ── 各街保本率 ────────────────────────────────────────────────────────────
    per_street_alpha:   List[float]  # 每街的獨立保本棄牌率

    # ── 組合分析 ──────────────────────────────────────────────────────────────
    cumulative_fold_needed: float    # 對手需要在整個計劃中棄牌的概率
    bluff_ev:               float    # 若對手正好在保本點時的 EV（=0）
    ev_per_pct_fold:        float    # 棄牌率每高出 1% 的 EV 收益（BB）

    # ── 可行性評估 ────────────────────────────────────────────────────────────
    is_feasible:        bool         # 計劃是否可行（保本折疊率是否合理）
    feasibility_note:   str
    recommendation:     str          # 行動建議

    # ── 顯示 ─────────────────────────────────────────────────────────────────
    summary:            str
    full_analysis:      str
    tips:               List[str] = field(default_factory=list)


# ── 主函數 ────────────────────────────────────────────────────────────────────

def plan_bluff(
    pot_bb:     float,
    stack_bb:   float,
    bet_sizes:  List[float],          # 各街下注比例（例如 [0.40, 0.60, 0.75]）
    street_names: Optional[List[str]] = None,
    villain_fold_estimate: float = 0.50,   # 對手整體棄牌估算（用於 EV 計算）
) -> BluffPlan:
    """
    計算多街詐唬計劃的保本折疊率和 EV。

    Args:
        pot_bb:                第一街的底池大小（BB）
        stack_bb:              有效籌碼（BB）
        bet_sizes:             各街的下注比例（相對於該街底池），如 [0.40, 0.60, 0.75]
        street_names:          各街名稱，默認 ['翻牌','轉牌','河牌']
        villain_fold_estimate: 對手整體棄牌率估算（用於展示 EV，不影響保本計算）

    Returns:
        BluffPlan
    """
    n = len(bet_sizes)
    if street_names is None:
        default_names = ['翻牌', '轉牌', '河牌', '河牌+']
        street_names = default_names[:n]

    # 初始化
    streets         = []
    per_street_alpha = []
    cur_pot         = pot_bb
    total_bet       = 0.0
    remaining_stack = stack_bb

    for i, size_pct in enumerate(bet_sizes):
        bet_bb = min(size_pct * cur_pot, remaining_stack)  # 不超過有效籌碼
        alpha  = bet_bb / (cur_pot + bet_bb) if (cur_pot + bet_bb) > 0 else 0.0

        streets.append(BluffStreet(
            street_name     = street_names[i] if i < len(street_names) else f'街{i+1}',
            bet_pct         = size_pct,
            pot_before      = round(cur_pot, 2),
            bet_amount      = round(bet_bb, 2),
            alpha           = round(alpha, 4),
            stack_committed = round(total_bet + bet_bb, 2),
        ))
        per_street_alpha.append(round(alpha, 4))
        total_bet += bet_bb
        # 如果被跟注，底池增加
        cur_pot = cur_pot + 2 * bet_bb
        remaining_stack -= bet_bb

    # ── 組合保本折疊率計算 ──────────────────────────────────────────────────
    # 對於 N 街詐唬計劃：
    # EV = p1 × pot1 + (1-p1) × [p2 × pot2 + (1-p2) × [...]] - total_cost
    # 其中 pi = 對手在第 i 街棄牌的機率
    #
    # 簡化假設：對手在每街棄牌機率相同（等效 fold rate per street）
    # 求：整體折疊率 F 使 EV = 0
    #
    # 更精確的計算：
    # total_cost = sum of all bets
    # fold_ev = 對手在第 i 街棄牌時的盈利 × P(reach street i)
    #
    # 假設每街獨立且等機率折疊 f：
    # EV = f*pot_1 + (1-f)*f*(pot_1+bet_1*2) + (1-f)^2*f*(pot_2*...) - total_cost = 0

    # 用數值方法求解保本折疊率 F
    cumulative_fold_needed = _solve_breakeven_fold(streets, pot_bb)

    # ── EV 分析（給定對手的折疊率估算）─────────────────────────────────────────
    bluff_ev = _compute_bluff_ev(streets, pot_bb, villain_fold_estimate)

    # 每 1% 額外棄牌的價值
    ev_per_pct = (
        _compute_bluff_ev(streets, pot_bb, min(1.0, villain_fold_estimate + 0.01))
        - bluff_ev
    ) if villain_fold_estimate < 1.0 else 0.0

    # ── 可行性評估 ────────────────────────────────────────────────────────────
    if cumulative_fold_needed <= 0.40:
        is_feasible = True
        feasibility = f'保本棄牌率 {int(cumulative_fold_needed*100)}%，詐唬計劃可行'
    elif cumulative_fold_needed <= 0.60:
        is_feasible = True
        feasibility = f'保本棄牌率 {int(cumulative_fold_needed*100)}%，需要對手有相當棄牌傾向'
    elif cumulative_fold_needed <= 0.75:
        is_feasible = False
        feasibility = f'保本棄牌率 {int(cumulative_fold_needed*100)}%，詐唬計劃風險高'
    else:
        is_feasible = False
        feasibility = f'保本棄牌率 {int(cumulative_fold_needed*100)}%，詐唬計劃不可行'

    # 行動建議
    ev_sign = '+' if bluff_ev >= 0 else ''
    if bluff_ev >= 1.5 and is_feasible:
        rec = f'強烈建議詐唬（估算 EV {ev_sign}{bluff_ev:.1f}BB）'
    elif bluff_ev >= 0 and is_feasible:
        rec = f'可以詐唬（估算 EV {ev_sign}{bluff_ev:.1f}BB）'
    elif villain_fold_estimate < cumulative_fold_needed:
        gap = int((cumulative_fold_needed - villain_fold_estimate) * 100)
        rec = f'對手棄牌率不足（差 {gap}%），不建議詐唬'
    else:
        rec = f'謹慎評估，EV {ev_sign}{bluff_ev:.1f}BB'

    # 摘要行
    street_parts = ' → '.join(
        f'{s.street_name}{int(s.bet_pct*100)}%({s.bet_amount:.1f}BB)'
        for s in streets
    )
    summary = (
        f'{street_parts}  '
        f'保本折疊率{int(cumulative_fold_needed*100)}%  '
        f'估EV{ev_sign}{bluff_ev:.1f}BB'
    )

    # 完整分析
    lines = [f'多街詐唬計劃（{n}街）', f'起始底池: {pot_bb:.1f}BB', '']
    for s in streets:
        lines.append(
            f'  {s.street_name}: 下注 {int(s.bet_pct*100)}% × {s.pot_before:.1f}BB底池 '
            f'= {s.bet_amount:.1f}BB  保本棄牌率 {int(s.alpha*100)}%'
        )
    lines += [
        '',
        f'總投入: {total_bet:.1f}BB',
        f'組合保本棄牌率: {int(cumulative_fold_needed*100)}%',
        f'估算 EV（對手棄牌率={int(villain_fold_estimate*100)}%）: {ev_sign}{bluff_ev:.1f}BB',
        feasibility,
    ]

    tips = []
    if n >= 2 and per_street_alpha[-1] > 0.40:
        tips.append(f'河牌保本率 {int(per_street_alpha[-1]*100)}%，確認對手有足夠棄牌傾向再繼續')
    if cumulative_fold_needed > villain_fold_estimate:
        tips.append('對手估算棄牌率低於保本點 → 計劃虧錢，改為取值')
    if total_bet / pot_bb > 1.5:
        tips.append(f'總投入 {total_bet:.1f}BB 超過起始底池 1.5 倍，詐唬成本高')

    return BluffPlan(
        streets                 = streets,
        n_streets               = n,
        total_investment        = round(total_bet, 2),
        starting_pot            = pot_bb,
        per_street_alpha        = per_street_alpha,
        cumulative_fold_needed  = round(cumulative_fold_needed, 4),
        bluff_ev                = round(bluff_ev, 2),
        ev_per_pct_fold         = round(ev_per_pct * 100, 3),
        is_feasible             = is_feasible,
        feasibility_note        = feasibility,
        recommendation          = rec,
        summary                 = summary,
        full_analysis           = '\n'.join(lines),
        tips                    = tips,
    )


# ── 數學輔助函數 ─────────────────────────────────────────────────────────────

def _compute_bluff_ev(
    streets: List[BluffStreet],
    start_pot: float,
    fold_per_street: float,
) -> float:
    """
    計算多街詐唬的 EV。
    假設對手在每街以相同機率 fold_per_street 棄牌。

    EV = sum over street i of:
      P(reach i) × [fold_rate × pot_before_i - bet_i]

    若棄牌：贏得 pot_before_i（下注前的底池），但需支付 bet_i
    若不棄牌：進入下一街（繼續扣成本）
    """
    ev = 0.0
    reach_prob = 1.0   # 機率到達這一街

    for s in streets:
        # 本街的 EV 貢獻：
        #   棄牌：贏得「底池+我們的注碼」，扣掉我們的注碼 = 贏 pot_before
        #     但正確公式：fold時贏到 pot_before+bet，淨盈 = pot_before
        #     對方棄牌機率 f，EV_fold = f × pot_before
        #   不棄牌：花了 bet，進入下一街
        #     EV_nofold = -(1-f) × bet (已支付成本，後續街再算)
        # 合併：EV = reach × [f×(pot_before+bet) - bet]
        #           = reach × [f×pot_before - (1-f)×bet]
        ev += reach_prob * (fold_per_street * (s.pot_before + s.bet_amount) - s.bet_amount)
        reach_prob *= (1 - fold_per_street)

    return ev


def _solve_breakeven_fold(
    streets: List[BluffStreet],
    start_pot: float,
    precision: float = 0.001,
) -> float:
    """用二分法求使詐唬 EV=0 的折疊率。"""
    lo, hi = 0.0, 1.0
    for _ in range(20):
        mid = (lo + hi) / 2
        ev = _compute_bluff_ev(streets, start_pot, mid)
        if ev > 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < precision:
            break
    return (lo + hi) / 2


def bluff_summary(plan: BluffPlan) -> str:
    """單行摘要，用於 overlay 顯示。"""
    ev_sign = '+' if plan.bluff_ev >= 0 else ''
    return (
        f'詐唬{plan.n_streets}街  '
        f'保本折疊{int(plan.cumulative_fold_needed*100)}%  '
        f'EV{ev_sign}{plan.bluff_ev:.1f}BB  '
        f'{"可行" if plan.is_feasible else "不建議"}'
    )


def quick_bluff_check(
    pot_bb:    float,
    bet_sizes: List[float],
    fold_est:  float = 0.50,
) -> str:
    """快速查詢，回傳單行結果。"""
    plan = plan_bluff(pot_bb=pot_bb, stack_bb=pot_bb*20, bet_sizes=bet_sizes,
                      villain_fold_estimate=fold_est)
    return bluff_summary(plan)
