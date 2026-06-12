"""
半詐唬（Semi-bluff）決策顧問

當英雄持有聽牌（flush draw、OESD、gutshot 等）時，
計算下注（半詐唬）vs 過牌 vs 跟注的 EV，給出最優行動建議。

核心公式：
  EV_bet = fold_pct × P + (1 - fold_pct) × [eq × (P + b) + (1 - eq) × (-b)]
         = fold_pct × P + (1 - fold_pct) × (eq × P + b × (2 × eq - 1))

  EV_check_call（面對對手下注跟注）:
    = eq × (P + bet_to_call) - (1 - eq) × bet_to_call

  EV_check_behind（主動過牌，等下一街）:
    = eq × P   ← 簡化：只計算命中後贏得底池的期望值

當 EV_bet > max(EV_check_call, EV_check_behind) 時，建議半詐唬。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SemiBluffResult:
    # 輸入摘要
    outs:              int
    draw_equity:       float     # 命中率（0-1）
    cards_to_come:     int       # 1=轉牌, 2=翻牌
    pot_bb:            float
    bet_size_bb:       float     # 英雄下注大小（用於EV計算）
    fold_equity:       float     # 估算對手折疊率

    # EV 計算
    ev_bet:            float     # 半詐唬 EV
    ev_check_behind:   float     # 過牌等下一街 EV
    ev_check_call:     float     # 面對對手下注跟注 EV（如果 facing_bet=True）

    # 決策
    recommended:       str       # 'BET' / 'CHECK_CALL' / 'CHECK_FOLD' / 'CHECK_BEHIND'
    action_zh:         str       # 中文行動
    is_profitable_bet: bool      # 半詐唬有正EV
    edge_over_check:   float     # EV_bet - EV_check（EV優勢）

    # 細節
    sizing_pct:        float     # 建議下注比例（底池）
    breakeven_fold:    float     # 讓 EV_bet=0 所需的最低折疊率
    rationale:         str
    tips:              List[str] = field(default_factory=list)


def analyze_semibluff(
    outs:           int,
    pot_bb:         float,
    cards_to_come:  int,           # 1 = 轉牌 (1 card left), 2 = 翻牌 (2 cards left)
    fold_equity:    float = 0.45,  # 對手面對下注的折疊率
    bet_fraction:   float = 0.60,  # 打算下注的底池比例
    facing_bet:     bool  = False, # 是否已面對對手下注
    bet_to_call:    float = 0.0,   # 若面對下注，需要跟多少 BB
    stack_bb:       float = 100.0,
    has_equity_share: float = 0.0, # 額外勝率（例如過對或有頂對）
) -> SemiBluffResult:
    """
    分析聽牌的半詐唬 EV，建議行動。

    Args:
        outs:           可進牌數（flush draw=9, OESD=8, gutshot=4 等）
        pot_bb:         當前底池（BB）
        cards_to_come:  剩餘公牌數（翻牌=2, 轉牌=1）
        fold_equity:    對手折疊率（HUD fcbet 或預設）
        bet_fraction:   計畫下注的底池比例（0.60 = 60% 底池）
        facing_bet:     True = 英雄面對對手下注需要決定是否跟注
        bet_to_call:    面對下注時需跟注的 BB 數
        stack_bb:       有效籌碼（用於 SPR 和 pot commitment 判斷）
        has_equity_share: 除聽牌外的額外勝率（如頂對加聽牌）
    """
    # ── 牌面勝率（rule of 2 & 4）──────────────────────────────────────────
    raw_eq = outs * (2 if cards_to_come == 1 else 4) / 100.0
    draw_equity = min(0.95, raw_eq + has_equity_share)

    bet_size = pot_bb * bet_fraction

    # ── EV 計算 ───────────────────────────────────────────────────────────

    # 半詐唬：我們主動下注
    # EV = fold_eq * P + (1-fold_eq) * [eq*(P+b) - (1-eq)*b]
    called_ev = draw_equity * (pot_bb + bet_size) - (1 - draw_equity) * bet_size
    ev_bet = fold_equity * pot_bb + (1 - fold_equity) * called_ev

    # 過牌等下一街（無對手下注）
    ev_check_behind = draw_equity * pot_bb

    # 面對對手下注的跟注 EV
    if facing_bet and bet_to_call > 0:
        ev_check_call = (draw_equity * (pot_bb + bet_to_call)
                         - (1 - draw_equity) * bet_to_call)
    else:
        ev_check_call = ev_check_behind  # 未面對下注，不適用

    # ── 決策 ─────────────────────────────────────────────────────────────
    is_profitable_bet = ev_bet > 0

    if facing_bet:
        if ev_check_call >= 0:
            recommended = 'CHECK_CALL'
            action_zh = '跟注（有利）'
        else:
            recommended = 'CHECK_FOLD'
            action_zh = '棄牌（負EV）'
        # 若半詐唬比純跟注更優（re-raise / squeeze）
        if ev_bet > ev_check_call + 1.0 and bet_size + bet_to_call <= stack_bb * 0.6:
            recommended = 'BET'
            action_zh = '半詐唬加注（EV最優）'
    else:
        # 英雄先行動
        if ev_bet > ev_check_behind + 0.5:
            recommended = 'BET'
            action_zh = '半詐唬下注（EV最優）'
        else:
            recommended = 'CHECK_BEHIND'
            action_zh = '過牌（EV相近或更優）'

    edge = round(ev_bet - max(ev_check_behind, ev_check_call), 2)

    # ── 建議注碼 ─────────────────────────────────────────────────────────
    if outs >= 12:
        sizing_pct = 0.75   # 強力 combo draw：大注
    elif outs >= 8:
        sizing_pct = 0.60   # flush/OESD：標準注
    elif outs >= 4:
        sizing_pct = 0.45   # gutshot：小注（較少折疊勝算需求）
    else:
        sizing_pct = 0.33   # 微弱聽牌：小注或不下注

    # ── 保本折疊率 ────────────────────────────────────────────────────────
    # 讓 EV_bet = 0：fold_eq * P + (1-fold_eq) * called_ev = 0
    # → fold_eq = -called_ev / (P - called_ev) if called_ev < 0
    if called_ev < 0:
        denom = pot_bb - called_ev
        breakeven_fold = (-called_ev / denom) if denom != 0 else 1.0
    else:
        breakeven_fold = 0.0  # 即使跟注也有正 EV，不需要折疊

    breakeven_fold = max(0.0, min(1.0, breakeven_fold))

    # ── 說明 ─────────────────────────────────────────────────────────────
    draw_type = (
        'Flush Draw' if outs >= 8 and outs <= 9
        else 'OESD' if outs == 8
        else 'Combo Draw' if outs >= 12
        else 'Gutshot' if outs == 4
        else f'{outs} outs'
    )
    ratio_pct = int(cards_to_come == 2 and 4 or 2)
    rationale = (
        f'{draw_type}（{outs} outs）  '
        f'命中率 {draw_equity:.0%}（rule of {ratio_pct}）  '
        f'折疊勝算 {fold_equity:.0%}  '
        f'EV_bet={ev_bet:.1f}BB vs EV_check={max(ev_check_behind,ev_check_call):.1f}BB'
    )

    tips: List[str] = []
    if is_profitable_bet:
        tips.append(f'半詐唬有利：需折疊 ≥ {breakeven_fold:.0%} 即收支平衡，'
                    f'當前估計 {fold_equity:.0%}')
    else:
        tips.append(f'折疊勝算不足（需 {breakeven_fold:.0%}，當前 {fold_equity:.0%}），'
                    f'考慮純跟注或過牌')
    if draw_equity > 0.35:
        tips.append(f'命中率高（{draw_equity:.0%}），即使無折疊勝算也有一定價值')
    if outs >= 9 and cards_to_come == 2:
        tips.append('同花聽牌翻牌圈：半詐唬 + 聽牌到轉牌繼續 barrel 是標準線')
    if facing_bet and ev_check_call >= 0:
        tips.append(f'跟注 {bet_to_call:.1f}BB：底池賠率足夠（EV={ev_check_call:.1f}BB）')

    return SemiBluffResult(
        outs             = outs,
        draw_equity      = round(draw_equity, 3),
        cards_to_come    = cards_to_come,
        pot_bb           = pot_bb,
        bet_size_bb      = round(bet_size, 1),
        fold_equity      = fold_equity,
        ev_bet           = round(ev_bet, 2),
        ev_check_behind  = round(ev_check_behind, 2),
        ev_check_call    = round(ev_check_call, 2),
        recommended      = recommended,
        action_zh        = action_zh,
        is_profitable_bet = is_profitable_bet,
        edge_over_check  = edge,
        sizing_pct       = sizing_pct,
        breakeven_fold   = round(breakeven_fold, 3),
        rationale        = rationale,
        tips             = tips,
    )


def semibluff_summary(r: SemiBluffResult) -> str:
    """單行 overlay 摘要。"""
    sign = '+' if r.ev_bet >= 0 else ''
    return (f'[半詐唬] {r.outs}outs {r.draw_equity:.0%}  '
            f'fold>{r.breakeven_fold:.0%}需要  '
            f'EV_bet={sign}{r.ev_bet:.1f}  → {r.action_zh}')
