"""
多人底池跟注顧問 (Multiway Pot Calling Advisor)

問題：在 3+ 人底池中面對下注，跟注的勝率門檻比單挑高多少？

核心理論：
  1. 勝率折扣（Equity Discount）
     多人底池中，你的原始勝率與「你能獨自獲得底池」的機率不同。
     當有 N-1 個對手時，你贏取底池需要擊敗所有人：
       有效勝率 ≈ 原始勝率 × (1 + fold_discount × 其他玩家棄牌率)
     但通常多人底池中你的原始勝率本就比 HU 低。

  2. 玩家身後擠注風險（Squeeze Risk）
     跟注後，身後的玩家可能加注（擠注），讓你的跟注成本更高甚至無效。
     擠注風險調整：每位身後玩家 → 需要額外 4-6% 勝率作為緩衝。

  3. 多路攤牌均分風險（Split Pot Risk）
     在均等情況下，多人底池的期望值 < 單挑底池。

跟注門檻公式（簡化）：
  基礎底池賠率 = call / (pot + call)
  身後玩家調整 = n_behind × 0.04（每位身後玩家需要額外 4% 勝率）
  多人攤牌調整 = (n_total - 2) × 0.03（每增加一個對手額外 3%）
  總需要勝率 = 基礎底池賠率 + 身後玩家調整 + 多人攤牌調整

詐唬勝算調整：
  多人底池詐唬幾乎無效（需所有對手棄牌）
  → 詐唬機率 ≈ fold_rate ^ n_opponents（指數級下降）

典型示例：
  HU: 面對 50% pot 下注，需要 33% 勝率
  3-way: 面對 50% pot 下注 + 1 人身後，需要 33% + 4% + 3% = 40% 勝率
  4-way: 面對 50% pot 下注 + 2 人身後，需要 33% + 8% + 6% = 47% 勝率
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple


# ── Equity requirements ───────────────────────────────────────────────────────

def _pot_odds_equity(call_bb: float, pot_bb: float) -> float:
    """Baseline equity needed from pot odds alone."""
    return call_bb / (pot_bb + call_bb)


def _multiway_equity_threshold(
    call_bb:      float,
    pot_bb:       float,
    n_behind:     int,
    n_opponents:  int,
) -> float:
    """
    Total equity threshold for calling in a multiway pot.
    n_behind: players still to act behind hero (can squeeze or call)
    n_opponents: total opponents in hand (including bettor)
    """
    base       = _pot_odds_equity(call_bb, pot_bb)
    behind_adj = n_behind     * 0.04   # 4% per player behind
    multi_adj  = max(0, (n_opponents - 1)) * 0.03  # 3% per extra opponent
    return round(min(0.95, base + behind_adj + multi_adj), 3)


# ── Fold equity in multiway ───────────────────────────────────────────────────

def _multiway_fold_equity(
    single_fold_rate: float,
    n_opponents:      int,
) -> float:
    """
    Estimated fold equity when bluffing in multiway pot.
    All opponents must fold simultaneously.
    """
    return round(single_fold_rate ** n_opponents, 3)


def _default_fold_rate(villain_vpip: float) -> float:
    """Estimate single-villain fold rate to ~50% pot bet based on VPIP."""
    if villain_vpip < 0.20:
        return 0.62   # nit: folds a lot
    if villain_vpip < 0.28:
        return 0.55   # tag: moderate
    if villain_vpip < 0.38:
        return 0.48   # lag: calls more
    return 0.38       # fish: rarely folds


# ── EV calculation ────────────────────────────────────────────────────────────

def _ev_call_multiway(
    call_bb:      float,
    pot_bb:       float,
    hero_equity:  float,
    n_opponents:  int,
) -> float:
    """Simplified EV of calling in multiway pot."""
    total_pot    = pot_bb + call_bb * (1 + n_opponents)   # rough: all call
    effective_eq = hero_equity / (n_opponents)             # must beat all opponents
    ev           = hero_equity * total_pot - call_bb
    return round(ev, 2)


# ── Action recommendation ─────────────────────────────────────────────────────

def _recommend_multiway(
    hero_equity:  float,
    threshold:    float,
    n_behind:     int,
    n_opponents:  int,
    villain_vpip: float,
    pot_bb:       float,
    call_bb:      float,
) -> Tuple[str, str, str]:
    """Returns (action, action_zh, reasoning_brief)."""
    margin       = hero_equity - threshold
    fold_equity  = _multiway_fold_equity(_default_fold_rate(villain_vpip), n_opponents)
    ev           = _ev_call_multiway(call_bb, pot_bb, hero_equity, n_opponents)

    if margin >= 0.12 and ev > 0:
        return 'call_wide',   '強勢跟注（勝率充裕）', f'勝率={hero_equity:.0%} >> 門檻={threshold:.0%}'
    elif margin >= 0.0 and ev > 0:
        return 'call',        '跟注（達到門檻）',       f'勝率={hero_equity:.0%} ≈ 門檻={threshold:.0%}'
    elif margin >= -0.04:
        return 'marginal',    '邊緣跟注（謹慎）',        f'勝率={hero_equity:.0%} 略低於門檻={threshold:.0%}'
    else:
        return 'fold',        '棄牌（勝率不足）',        f'勝率={hero_equity:.0%} < 門檻={threshold:.0%}'


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class MultiwayCallResult:
    # Pot context
    pot_bb:           float
    call_bb:          float
    n_opponents:      int    # total opponents (including bettor)
    n_behind:         int    # players still to act behind hero

    # Equity analysis
    hero_equity:      float
    pot_odds_only:    float  # baseline equity if HU
    equity_threshold: float  # adjusted threshold for multiway
    equity_margin:    float  # hero_equity - threshold (+ means call, - means fold)

    # Fold equity (for potential bluff-raises)
    single_villain_fold_rate: float
    multiway_fold_equity: float
    bluff_viable:     bool   # is bluff-raising viable?

    # EV
    ev_call:          float

    # Decision
    action:           str    # 'call_wide'/'call'/'marginal'/'fold'
    action_zh:        str
    reasoning:        str

    # Tips
    tips:             List[str]
    summary_zh:       str


def analyze_multiway_call(
    pot_bb:       float,
    call_bb:      float,
    hero_equity:  float,
    n_opponents:  int   = 2,    # total opponents in hand
    n_behind:     int   = 0,    # players to act after hero
    villain_vpip: float = 0.28,
    villain_hands: int  = 0,
) -> MultiwayCallResult:
    """
    Advise on calling in a multiway pot (3+ players).

    Args:
        pot_bb:       Pot size before call in BB
        call_bb:      Amount to call in BB
        hero_equity:  Hero's raw MC equity (0-1)
        n_opponents:  Total opponents in hand (including bettor), typically 2+
        n_behind:     Players still to act behind hero (squeeze risk)
        villain_vpip: Average villain VPIP (used for fold rate estimate)
        villain_hands: HUD sample size
    """
    tips: List[str] = []

    n_opp     = max(2, n_opponents)
    n_beh     = max(0, n_behind)
    threshold = _multiway_equity_threshold(call_bb, pot_bb, n_beh, n_opp)
    base_po   = _pot_odds_equity(call_bb, pot_bb)
    fold_rate = _default_fold_rate(villain_vpip)
    mw_fold   = _multiway_fold_equity(fold_rate, n_opp)
    ev        = _ev_call_multiway(call_bb, pot_bb, hero_equity, n_opp)
    action, action_zh, reason = _recommend_multiway(
        hero_equity, threshold, n_beh, n_opp, villain_vpip, pot_bb, call_bb
    )
    margin    = round(hero_equity - threshold, 3)
    bluff_ok  = mw_fold > 0.30 and n_opp <= 2  # bluffing only viable in near-HU

    # Tips
    if n_beh >= 1:
        tips.append(f'{n_beh}名玩家在英雄身後：擠注風險存在，需要額外 +{n_beh*4}% 勝率')
    if n_opp >= 3:
        tips.append(f'{n_opp+1}人底池：棄牌率超低（詐唬幾乎無效），以真實手牌強度為準')
    if not bluff_ok:
        tips.append(f'多人底池詐唬勝算={mw_fold:.0%}（過低），避免純詐唬加注')
    if hero_equity < base_po:
        tips.append(f'勝率={hero_equity:.0%} 低於底池賠率={base_po:.0%}，標準應棄牌')
    if margin >= 0 and abs(margin) < 0.05:
        tips.append('邊緣決策：考慮對手類型 — vs 緊型偏向棄牌，vs 鬆型偏向跟注')
    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），使用預設對手類型估算')

    po_str   = f'{base_po:.0%}'
    thr_str  = f'{threshold:.0%}'
    opp_str  = f'{n_opp+1}人底池'
    summary_zh = (
        f'[多人跟注] {opp_str} 需>{thr_str} 你有{hero_equity:.0%} → {action_zh}'
    )[:85]

    return MultiwayCallResult(
        pot_bb               = pot_bb,
        call_bb              = call_bb,
        n_opponents          = n_opp,
        n_behind             = n_beh,
        hero_equity          = hero_equity,
        pot_odds_only        = base_po,
        equity_threshold     = threshold,
        equity_margin        = margin,
        single_villain_fold_rate = fold_rate,
        multiway_fold_equity = mw_fold,
        bluff_viable         = bluff_ok,
        ev_call              = ev,
        action               = action,
        action_zh            = action_zh,
        reasoning            = reason,
        tips                 = tips,
        summary_zh           = summary_zh,
    )


def multiway_call_summary(r: MultiwayCallResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
