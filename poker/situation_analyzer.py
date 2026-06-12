"""
情境綜合分析器 (Situation Analyzer)

一次呼叫整合所有關鍵模組：
  equity → hand_strength → board_texture → bet_sizing_ev → decision
輸出完整 FullAnalysis，包含最優下注大小和 EV 比較。

用法：
    from poker.situation_analyzer import analyze_situation, situation_one_liner
    r = analyze_situation(['Ah','Ks'], ['Ac','7h','2d'], pot_bb=10, eff_stack_bb=90)
    print(situation_one_liner(r))
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class FullAnalysis:
    # 手牌與勝率
    equity: float
    hand_class: str
    hand_percentile: float

    # 牌面
    board_type: str
    board_wetness: float

    # 決策
    primary_action: str
    confidence: str
    ev_breakdown: Dict[str, float]

    # 最優下注大小（來自 bet_sizing_ev）
    optimal_bet_bb: float
    optimal_bet_pct: float
    bet_ev_vs_check: float

    # SPR / 承諾判斷
    spr: float
    spr_label: str
    should_commit: bool

    # 摘要
    one_liner: str
    tips: List[str] = field(default_factory=list)


def analyze_situation(
    hole_cards: List[str],
    community_cards: List[str],
    pot_bb: float,
    eff_stack_bb: float,
    hero_pos: str = 'BTN',
    villain_pos: str = 'BB',
    call_amount: float = 0.0,
    villain_vpip: float = 0.30,
    villain_pfr: float = 0.22,
    villain_af: float = 1.5,
    villain_fcbet: float = 0.50,
    in_position: bool = True,
    num_opponents: int = 1,
    iterations: int = 800,
) -> FullAnalysis:
    """
    綜合分析當前情境，整合所有關鍵決策模組。

    Args:
        hole_cards:     英雄手牌，如 ['Ah', 'Ks']
        community_cards: 公共牌（0/3/4/5 張）
        pot_bb:         底池（BB 計）
        eff_stack_bb:   有效籌碼（BB 計）
        hero_pos:       英雄位置
        villain_pos:    對手位置
        call_amount:    需要跟注的金額（0 = 無需跟注）
        villain_vpip:   對手 VPIP（0-1）
        villain_pfr:    對手 PFR（0-1）
        villain_af:     對手侵略因子
        villain_fcbet:  對手面對 c-bet 棄牌率（0-1）
        in_position:    是否佔有位置優勢
        num_opponents:  對手數量
        iterations:     蒙特卡洛模擬次數

    Returns:
        FullAnalysis 綜合分析結果
    """
    # ── 1. Equity（蒙特卡洛）───────────────────────────────────────────────
    try:
        from poker.equity import calculate_equity
        win, tie, lose = calculate_equity(hole_cards, community_cards,
                                          num_opponents=num_opponents,
                                          iterations=iterations)
        equity = win + tie * 0.5
    except Exception:
        equity = 0.5

    # ── 2. 手牌強度分類 ────────────────────────────────────────────────────
    try:
        from poker.hand_strength import classify
        hs = classify(hole_cards, community_cards)
        hand_class = hs.class_str
        hand_percentile = float(getattr(hs, 'percentile', equity))
    except Exception:
        hand_class = 'Unknown'
        hand_percentile = equity

    # ── 3. 牌面分析 ───────────────────────────────────────────────────────
    try:
        from poker.board_texture import analyze_board
        bt = analyze_board(community_cards) if community_cards else None
        board_type    = bt.texture_label if bt else 'Preflop'
        board_wetness = float(getattr(bt, 'wetness', 0.0)) if bt else 0.0
    except Exception:
        board_type    = 'Unknown'
        board_wetness = 0.5

    # ── 4. SPR 計劃 ────────────────────────────────────────────────────────
    try:
        from poker.spr_planner import analyze_spr
        n_comm = len(community_cards)
        spr_plan = analyze_spr(
            pot_bb=pot_bb, eff_stack_bb=eff_stack_bb,
            hand_percentile=hand_percentile,
            n_comm=n_comm, in_position=in_position,
            villain_fold_pct=villain_fcbet,
        )
        spr_val    = spr_plan.spr
        spr_label  = spr_plan.spr_label
        should_commit = spr_plan.should_commit
    except Exception:
        spr_val = eff_stack_bb / pot_bb if pot_bb > 0 else 99
        spr_label = 'Unknown'
        should_commit = equity > 0.6

    # ── 5. 最優下注大小（bet_sizing_ev）──────────────────────────────────
    try:
        from poker.bet_sizing_ev import compare_bet_sizes
        bev = compare_bet_sizes(
            pot_bb=pot_bb,
            hero_equity=equity,
            base_fold_freq=villain_fcbet,
            street=_street_name(len(community_cards)),
            eff_stack_bb=eff_stack_bb,
        )
        optimal_bet_bb  = bev.optimal.bet_bb
        optimal_bet_pct = bev.optimal.pct
        bet_ev_vs_check = bev.ev_loss_from_check
    except Exception:
        optimal_bet_bb  = pot_bb * 0.5
        optimal_bet_pct = 0.5
        bet_ev_vs_check = 0.0

    # ── 6. EV 分解（decision module）──────────────────────────────────────
    try:
        from poker.decision import GameState, ev_breakdown as _ev_breakdown
        gs = GameState(
            hole_cards=hole_cards,
            community_cards=community_cards,
            pot=int(pot_bb),
            call_amount=int(call_amount),
            hero_stack=int(eff_stack_bb),
            position='ip' if in_position else 'oop',
            num_opponents=num_opponents,
        )
        ev_map = _ev_breakdown(gs, equity)
    except Exception:
        ev_map = {'fold': 0.0, 'check': equity * pot_bb,
                  'call': equity * pot_bb - (1 - equity) * call_amount,
                  'raise': equity * pot_bb * 1.1, 'allin': equity * eff_stack_bb}

    # ── 7. 主要決策 ────────────────────────────────────────────────────────
    primary_action, confidence = _derive_action(
        equity, call_amount, pot_bb, ev_map, bet_ev_vs_check, should_commit
    )

    # ── 8. 提示列表 ────────────────────────────────────────────────────────
    tips = _build_tips(equity, spr_val, board_wetness, call_amount, pot_bb,
                       villain_fcbet, optimal_bet_pct)

    # ── 9. 單行摘要 ────────────────────────────────────────────────────────
    one_liner = (
        f'{hand_class}  勝率{equity:.0%}  '
        f'SPR{spr_val:.1f}  '
        f'{primary_action}  '
        f'最優下注{optimal_bet_bb:.1f}BB({optimal_bet_pct:.0%}底池)'
    )

    return FullAnalysis(
        equity=equity,
        hand_class=hand_class,
        hand_percentile=hand_percentile,
        board_type=board_type,
        board_wetness=board_wetness,
        primary_action=primary_action,
        confidence=confidence,
        ev_breakdown=ev_map,
        optimal_bet_bb=optimal_bet_bb,
        optimal_bet_pct=optimal_bet_pct,
        bet_ev_vs_check=bet_ev_vs_check,
        spr=spr_val,
        spr_label=spr_label,
        should_commit=should_commit,
        one_liner=one_liner,
        tips=tips,
    )


def situation_one_liner(r: FullAnalysis) -> str:
    """傳回單行摘要（用於 overlay）。"""
    return r.one_liner


def situation_full_report(r: FullAnalysis) -> str:
    """傳回多行完整報告（用於手牌覆盤）。"""
    lines = [
        f'手牌強度：{r.hand_class}（前 {r.hand_percentile:.0%}）',
        f'勝率：{r.equity:.1%}  SPR：{r.spr:.1f}（{r.spr_label}）',
        f'牌面：{r.board_type}  濕度：{r.board_wetness:.2f}',
        f'決策：{r.primary_action}  信心：{r.confidence}',
        f'最優下注：{r.optimal_bet_bb:.1f} BB（{r.optimal_bet_pct:.0%} 底池）',
        f'下注 vs 過牌 EV 差：+{r.bet_ev_vs_check:.2f} BB',
        f'EV 分解：' + '  '.join(f'{k}={v:.1f}' for k, v in r.ev_breakdown.items()),
        '提示：',
    ] + [f'  · {t}' for t in r.tips]
    return '\n'.join(lines)


# ── 內部工具 ──────────────────────────────────────────────────────────────────

def _street_name(n_comm: int) -> str:
    return {0: 'preflop', 3: 'flop', 4: 'turn', 5: 'river'}.get(n_comm, 'flop')


def _derive_action(equity, call_amount, pot_bb, ev_map, bet_ev_vs_check, should_commit):
    if call_amount > 0:
        pot_odds = call_amount / (pot_bb + call_amount)
        if equity >= pot_odds + 0.15:
            return '加注', 'high'
        elif equity >= pot_odds:
            return '跟注', 'medium'
        else:
            return '棄牌', 'high' if equity < pot_odds - 0.15 else 'medium'
    else:
        if equity > 0.75 or (should_commit and equity > 0.55):
            return '下注', 'high'
        elif bet_ev_vs_check > 1.0:
            return '下注', 'medium'
        else:
            return '過牌', 'medium'


def _build_tips(equity, spr, wetness, call_amount, pot_bb, fcbet, opt_pct):
    tips = []
    if spr < 4 and equity > 0.55:
        tips.append('低 SPR：優先全押，保護勝率')
    if wetness > 0.7 and call_amount == 0:
        tips.append('濕潤牌面：用更大尺寸保護，防止追牌')
    if fcbet > 0.6 and call_amount == 0:
        tips.append('對手高棄牌率：可提高 c-bet 頻率並加大尺寸')
    if equity < 0.35 and call_amount > 0:
        tips.append('勝率不足：除非有隱含賠率否則棄牌')
    if opt_pct > 0.75:
        tips.append(f'此情境最優下注偏大（{opt_pct:.0%}）：對手跟注範圍寬')
    if not tips:
        tips.append('標準線：按最優尺寸執行')
    return tips
