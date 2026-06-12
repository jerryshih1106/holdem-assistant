"""
翻後統一策略摘要 (Postflop Strategy Summary)

整合所有翻後分析模組，輸出一個簡潔、可直接執行的行動建議。

整合模組：
  hand_percentile.py  → 我的牌力在對手範圍的百分位
  spr_planner.py      → SPR 承諾規劃
  check_raise.py      → 面對下注時的 CR / call / fold 決策
  range_cbet.py       → C-bet 頻率和注碼（主動方）
  board_texture.py    → 牌面濕度
  exploit.py          → HUD 對手類型剝削提示

核心輸出：
  「你目前的牌力在對手範圍排 XX%。
    本局 SPR=X.X（低/中/高），你應該計劃推進/控制底池。
    建議行動：C-bet 60% @ 33% 底池 / Check-Raise 45% 12.5BB / 跟注 / 棄牌。
    對手是 Fish（VPIP 45%）：加大取值注碼。」
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from poker.hand_percentile import calc_hand_percentile, HandPercentileResult
from poker.spr_planner     import analyze_spr, SPRPlan, spr_summary
from poker.board_texture   import analyze_board, BoardTexture
from poker.range_cbet      import analyze_range_cbet, RangeCbetResult


@dataclass
class PostflopSummary:
    # ── 情境 ────────────────────────────────────────────────────────
    street:           str     # '翻牌'/'轉牌'/'河牌'
    position:         str     # 'BTN'/'CO'/'BB'...
    is_aggressor:     bool    # True = 翻前發動者（C-bet角色）
    facing_bet:       bool    # True = 面對對手下注

    # ── 牌力 ─────────────────────────────────────────────────────────
    percentile:       float   # 在對手範圍的百分位（0-1）
    percentile_bucket: str    # '超強'/'強'/'中'/'邊緣'/'弱'
    equity:           float   # 勝率

    # ── SPR ──────────────────────────────────────────────────────────
    spr:              float
    spr_label:        str
    should_commit:    bool
    commit_plan:      str     # '翻牌推進'/'轉牌推進'/'河牌推進'/'控制底池'

    # ── 主要行動 ─────────────────────────────────────────────────────
    primary_action:   str     # 建議行動（中文）
    action_detail:    str     # 注碼/頻率等細節
    confidence:       str     # 'high'/'medium'/'low'

    # ── 輔助資訊 ─────────────────────────────────────────────────────
    board_type:       str     # 牌面類型
    board_wetness:    float
    exploit_note:     str     # 對手剝削提示

    # ── 完整推理 ─────────────────────────────────────────────────────
    summary_line:     str     # 一行摘要（適合 overlay 顯示）
    full_reasoning:   str
    tips:             List[str] = field(default_factory=list)


# ── 桶位標籤（中文） ──────────────────────────────────────────────────────────

_BUCKET_ZH = {
    'nuts+':   '超強牌',
    'strong':  '強牌',
    'medium':  '中等牌',
    'marginal':'邊緣牌',
    'weak':    '弱牌',
}

_ACTION_ZH = {
    'value':       '取值下注',
    'thin_value':  '薄取值',
    'check_call':  '過牌跟注',
    'bluff_catch': '詐唬接住',
    'fold':        '棄牌',
}


def summarize_postflop(
    hole_cards:        List[str],
    community:         List[str],
    pot_bb:            float,
    eff_stack_bb:      float,
    hero_pos:          str   = 'BTN',
    villain_pos:       str   = 'BB',
    is_aggressor:      bool  = True,   # True = 翻前加注者/C-bet 角色
    facing_bet:        bool  = False,  # True = 面對對手下注
    villain_bet_bb:    float = 0.0,    # 若 facing_bet，對手下注金額
    # HUD 數據（可選）
    villain_vpip:      float = 0.30,
    villain_pfr:       float = 0.22,
    villain_cbet_pct:  float = 0.60,
    villain_af:        float = 1.5,
    villain_fcbet_pct: float = 0.50,
) -> PostflopSummary:
    """
    翻後情境一站式分析。

    Args:
        hole_cards:     英雄手牌
        community:      公牌（3-5 張）
        pot_bb:         當前底池
        eff_stack_bb:   有效籌碼
        hero_pos:       英雄位置
        villain_pos:    對手位置
        is_aggressor:   是否為翻前加注者（有 C-bet 機會）
        facing_bet:     是否面對對手下注
        villain_bet_bb: 對手下注金額（facing_bet 時使用）
        villain_vpip:   對手 VPIP（HUD）
        villain_pfr:    對手 PFR（HUD）
        villain_cbet_pct: 對手 C-bet 頻率
        villain_af:     對手 AF
        villain_fcbet_pct: 對手 FCbet
    """
    n_comm = len(community)
    street_zh = {3: '翻牌', 4: '轉牌', 5: '河牌'}.get(n_comm, '翻牌')
    in_position = hero_pos in ('BTN', 'CO', 'HJ')

    # ── 牌力百分位 ───────────────────────────────────────────────────────────
    pct_result: Optional[HandPercentileResult] = None
    percentile = 0.50
    bucket     = 'medium'
    equity     = 0.50

    if n_comm >= 3:
        try:
            villain_action = 'bet' if facing_bet else 'any'
            pct_result = calc_hand_percentile(
                hole_cards, community,
                villain_range_pct=villain_vpip,
                villain_action=villain_action,
                position='ip' if in_position else 'oop',
                pot_bb=pot_bb,
                is_river=(n_comm == 5),
            )
            if pct_result:
                percentile = pct_result.percentile
                bucket     = pct_result.bucket
                equity     = pct_result.vs_range_equity
        except Exception:
            pass

    bucket_zh = _BUCKET_ZH.get(bucket, bucket)

    # ── SPR 規劃 ──────────────────────────────────────────────────────────────
    spr_plan: Optional[SPRPlan] = None
    spr_val   = eff_stack_bb / pot_bb if pot_bb > 0 else 99.0
    spr_label = '未知'

    try:
        spr_plan = analyze_spr(
            pot_bb        = pot_bb,
            eff_stack_bb  = eff_stack_bb,
            hand_percentile = percentile,
            n_comm        = n_comm,
            in_position   = in_position,
        )
        spr_val   = spr_plan.spr
        spr_label = spr_plan.spr_label_zh[:6]
    except Exception:
        pass

    should_commit = spr_plan.should_commit if spr_plan else False
    commit_plan   = spr_plan.get_in_by_street if spr_plan else '控制底池'

    # ── 主要行動決策 ──────────────────────────────────────────────────────────
    primary_action = '待分析'
    action_detail  = ''
    confidence     = 'medium'
    reasons        = []

    if facing_bet and villain_bet_bb > 0:
        # ── 面對對手下注：CR / Call / Fold ──────────────────────────────────
        try:
            from poker.check_raise import analyze_check_raise, cr_summary
            cr_result = analyze_check_raise(
                hole_cards, community, villain_bet_bb, pot_bb,
                equity, percentile,
                position='oop' if not in_position else 'ip',
                villain_cbet_pct=villain_cbet_pct,
                villain_af=villain_af,
                villain_vpip=villain_vpip,
                eff_stack_bb=eff_stack_bb,
            )
            if cr_result.action.endswith('_cr') and cr_result.cr_freq >= 0.30:
                primary_action = cr_result.action_zh
                action_detail  = f'頻率{cr_result.cr_freq:.0%}  fold_eq={cr_result.fold_equity:.0%}'
                confidence = 'high' if cr_result.cr_freq >= 0.60 else 'medium'
            elif cr_result.action == 'call':
                primary_action = '跟注'
                action_detail  = f'保本勝率{villain_bet_bb/(pot_bb+2*villain_bet_bb):.0%}  我的勝率{equity:.0%}'
                confidence = 'high' if equity >= 0.50 else 'medium'
            else:
                primary_action = '棄牌'
                action_detail  = f'勝率{equity:.0%} 不足'
                confidence = 'medium'
            reasons.append(f'面對下注{villain_bet_bb:.1f}BB：{primary_action}')
        except Exception as e:
            primary_action = '跟注' if equity >= 0.35 else '棄牌'
            action_detail  = f'勝率{equity:.0%}'

    elif is_aggressor and n_comm == 3:
        # ── 翻牌 C-bet 機會 ──────────────────────────────────────────────────
        try:
            cbet_res = analyze_range_cbet(
                hero_pos=hero_pos, villain_pos=villain_pos,
                community=community, pot_bb=pot_bb,
                in_position=in_position,
                villain_fcbet=villain_fcbet_pct,
                villain_vpip=villain_vpip,
            )
            if cbet_res.should_cbet:
                primary_action = f'C-bet {cbet_res.cbet_freq_adj:.0%}'
                action_detail  = f'{int(cbet_res.cbet_size_adj*100)}% 底池  {cbet_res.recommended_size_bb:.1f}BB'
                confidence = 'high' if cbet_res.cbet_freq_adj >= 0.60 else 'medium'
                reasons.append(f'範圍優勢{cbet_res.range_advantage:+.0%}，建議 C-bet')
            else:
                primary_action = '過牌'
                action_detail  = f'範圍優勢{cbet_res.range_advantage:+.0%} 不足，選擇過牌'
                confidence = 'medium'
        except Exception:
            primary_action = 'C-bet' if percentile >= 0.55 else '過牌'

    elif pct_result:
        # ── 主動行動（轉牌/河牌，或無 C-bet 機會）────────────────────────────
        primary_action = _ACTION_ZH.get(pct_result.action_advice, pct_result.action_zh)
        if pct_result.bet_size_hint > 0:
            action_detail = f'{int(pct_result.bet_size_hint*100)}% 底池'
        confidence = 'high' if percentile >= 0.75 or percentile < 0.30 else 'medium'
        reasons.append(f'牌力百分位{percentile:.0%}（{bucket_zh}）')

    # ── 對手剝削提示 ─────────────────────────────────────────────────────────
    exploit_note = _build_exploit_note(
        villain_vpip, villain_pfr, villain_cbet_pct, villain_af, percentile
    )

    # ── 牌面資訊 ─────────────────────────────────────────────────────────────
    board_type = '未知'
    board_wetness = 0.0
    try:
        tex = analyze_board(community)
        board_type    = tex.texture_name
        board_wetness = tex.wetness
    except Exception:
        pass

    # ── 最終摘要行 ───────────────────────────────────────────────────────────
    summary_line = (
        f'{street_zh} 百分位{percentile:.0%}({bucket_zh})  '
        f'SPR{spr_val:.1f}  '
        f'{primary_action} {action_detail}'
    )

    full_reasons = reasons + [
        f'SPR={spr_val:.1f}（{spr_label}）→ {"推進" if should_commit else "控制"}底池',
        exploit_note,
    ]

    tips = []
    if should_commit and spr_val <= 4:
        tips.append(f'低 SPR 局：強牌應積極建底池，不要慢打')
    if villain_vpip >= 0.40:
        tips.append(f'Fish 玩家（VPIP {villain_vpip:.0%}）：提高取值注碼，減少詐唬')
    if villain_cbet_pct >= 0.70:
        tips.append(f'對手 C-bet 高（{villain_cbet_pct:.0%}）：可以更頻繁 float 和 check-raise')

    return PostflopSummary(
        street           = street_zh,
        position         = hero_pos,
        is_aggressor     = is_aggressor,
        facing_bet       = facing_bet,
        percentile       = round(percentile, 3),
        percentile_bucket = bucket_zh,
        equity           = round(equity, 3),
        spr              = round(spr_val, 2),
        spr_label        = spr_label,
        should_commit    = should_commit,
        commit_plan      = commit_plan,
        primary_action   = primary_action,
        action_detail    = action_detail,
        confidence       = confidence,
        board_type       = board_type,
        board_wetness    = round(board_wetness, 2),
        exploit_note     = exploit_note,
        summary_line     = summary_line,
        full_reasoning   = '；'.join(r for r in full_reasons if r),
        tips             = tips,
    )


def _build_exploit_note(vpip, pfr, cbet, af, hero_pct) -> str:
    """根據 HUD 數據建立一行剝削提示。"""
    parts = []
    if vpip >= 0.40:
        parts.append(f'Fish(VPIP{vpip:.0%})→大注取值')
    elif vpip <= 0.18:
        parts.append(f'Nit(VPIP{vpip:.0%})→縮小取值/多棄牌')
    elif af >= 2.5:
        parts.append(f'積極(AF{af:.1f})→薄跟注/trap')
    elif cbet >= 0.70:
        parts.append(f'高CBet({cbet:.0%})→頻繁float/CR')
    if not parts:
        return f'TAG({vpip:.0%}/{pfr:.0%})→標準策略'
    return '；'.join(parts)


def postflop_one_liner(
    hole:       List[str],
    community:  List[str],
    pot_bb:     float,
    stack_bb:   float,
    hero_pos:   str   = 'BTN',
    villain_pos: str  = 'BB',
    facing_bet: bool  = False,
    bet_bb:     float = 0.0,
    vpip:       float = 0.30,
) -> str:
    """一行快速查詢，適合 overlay 顯示。"""
    r = summarize_postflop(
        hole, community, pot_bb, stack_bb,
        hero_pos, villain_pos,
        is_aggressor=True,
        facing_bet=facing_bet,
        villain_bet_bb=bet_bb,
        villain_vpip=vpip,
    )
    return r.summary_line
