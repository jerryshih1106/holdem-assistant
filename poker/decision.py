"""GTO-simplified decision engine: produces action recommendations.

P0 fix — 多人底池模式：
  - value_thresh 隨對手數遞增（+7% / 多一人）
  - EV breakdown 加入多人折疊率指數衰減
  - 3人以上底池禁止詐唬
  - reasoning 明確標示 [N人底池]
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class GameState:
    hole_cards:      list       # e.g. ["Ah", "Kd"]
    community_cards: list       # e.g. ["2h", "7c", "Jd"]
    pot:             int        # total pot size in chips
    call_amount:     int        # chips needed to call (0 = can check)
    hero_stack:      int        # hero remaining stack
    position:        str = "unknown"
    num_opponents:   int = 1


@dataclass
class Decision:
    action:       str
    raise_size:   Optional[int]
    reasoning:    str
    equity:       float
    pot_odds:     float
    ev:           float
    ev_breakdown: Dict[str, float] = field(default_factory=dict)

    # P1 enriched fields（由 decision_enricher.enrich() 填入，預設空值保持向後相容）
    range_adv_label:      str   = ""   # "我方優勢 9/10（A高乾燥）"
    nut_adv_label:        str   = ""   # "堅果優勢：我方（可 overbet 100-120%）"
    range_adv_score:      int   = 0    # 1-10，5=均衡
    gto_bet_freq:         float = 0.0  # GTO 下注頻率 0-1
    gto_check_freq:       float = 0.0  # GTO 過牌頻率 0-1
    gto_mix_note:         str   = ""   # "混合：下注 68% / 過牌 32%"
    precise_size_pct:     float = 0.0  # 精確注碼（底池倍數，如 0.66）
    precise_size_label:   str   = ""   # "66% pot"
    spr_verdict:          str   = ""   # "SPR 3.0 → 已承諾，頂對好踢可全下"
    icm_note:             str   = ""   # "ICM 壓力 60%，需多 15% 勝率才跟注"
    icm_equity_premium:   float = 0.0  # 額外需要的勝率（如 0.15 = 需多 15%）


def pot_odds(call_amount: int, pot: int) -> float:
    if call_amount <= 0:
        return 0.0
    return call_amount / (pot + call_amount)


def spr(stack: int, pot: int) -> float:
    return stack / pot if pot > 0 else 999.0


# ─── 多人底池參數 ─────────────────────────────────────────────────────────────

# 每多一個對手，價值下注閾值上升 7%（單挑基準 55%）
_VALUE_BASE      = 0.55
_VALUE_STEP      = 0.07
_VALUE_CAP       = 0.85

# 每多一個對手，免費下注閾值上升 6%（單挑基準 65%）
_FREE_BASE       = 0.65
_FREE_STEP       = 0.06

# 對手折疊到 75% 底池下注的機率（單人）
_PER_OPP_FOLD_RATE = 0.52

def _value_thresh(n_opp: int) -> float:
    """多人底池價值下注勝率門檻。"""
    return min(_VALUE_CAP, _VALUE_BASE + (n_opp - 1) * _VALUE_STEP)

def _free_thresh(n_opp: int) -> float:
    return min(_VALUE_CAP, _FREE_BASE + (n_opp - 1) * _FREE_STEP)

def _multiway_fold_eq(n_opp: int) -> float:
    """所有對手同時棄牌的折疊率（獨立假設）。"""
    return _PER_OPP_FOLD_RATE ** n_opp


# ─── 主決策函式 ───────────────────────────────────────────────────────────────

def recommend(state: GameState, equity: float, tie_rate: float) -> Decision:
    """
    根據遊戲狀態與勝率給出行動建議。

    多人底池調整：
    - 3人+底池：禁止詐唬；下注門檻提高
    - EV breakdown：折疊率指數衰減
    - reasoning 標示人數
    """
    po        = pot_odds(state.call_amount, state.pot)
    edge      = equity - po
    stack_pot = spr(state.hero_stack, state.pot)
    ev        = edge * (state.pot + state.call_amount)
    n_opp     = max(1, state.num_opponents)
    evb       = ev_breakdown(state, equity)

    is_multiway   = n_opp > 1
    bluff_allowed = n_opp <= 2   # 3人以上不詐唬
    v_thresh      = _value_thresh(n_opp)
    f_thresh      = _free_thresh(n_opp)

    pct    = f"{equity:.0%}"
    po_pct = f"{po:.0%}"
    tag    = f"[{n_opp}人底池] " if is_multiway else ""

    def mk(action, raise_sz, reason):
        return Decision(action, raise_sz, f"{tag}{reason}", equity, po, ev, evb)

    # ── 免費選項（可過牌）──────────────────────────────────────────
    if state.call_amount <= 0:
        if equity >= f_thresh:
            size = _calc_raise(state, 0.5 if is_multiway else 0.75)
            hint = f"（多人底池保護注，需≥{f_thresh:.0%}）" if is_multiway else ""
            return mk("加注", size, f"強牌（{pct}），下注取值{hint}")

        if equity < 0.35 or not bluff_allowed:
            verb = "多人底池—禁止詐唬，" if not bluff_allowed else "弱牌，"
            return mk("過牌", None, f"{verb}過牌控牌（{pct}）")

        return mk("過牌", None, f"中等牌力（{pct}），過牌控制底池")

    # ── 需要付錢繼續 ───────────────────────────────────────────────

    # 怪獸牌（≥80%）永遠加注
    if equity >= 0.80:
        size = _calc_raise(state, 1.0)
        return mk("加注", size, f"怪獸牌（{pct}），加注或再加注")

    # 多人底池強牌 / 單挑強牌
    if equity >= v_thresh:
        if stack_pot < 2.0:
            return mk("全下", state.hero_stack,
                      f"強牌（{pct}）+ 低SPR {stack_pot:.1f}，全下")
        size = _calc_raise(state, 0.5 if is_multiway else 0.75)
        hint = f"（多人價值門檻 {v_thresh:.0%}）" if is_multiway else ""
        return mk("加注", size, f"強牌（{pct} ≥ {v_thresh:.0%}），加注取值{hint}")

    # +EV 跟注
    if equity >= po + 0.05:
        return mk("跟注", None, f"勝率 {pct} > 底池賠率 {po_pct}，正EV跟注")

    # 邊緣局面
    if abs(equity - po) <= 0.04:
        hint = _position_hint(state.position)
        if hint == "aggressive" and bluff_allowed:
            return mk("跟注", None, f"邊緣局，有位置優勢跟注（{pct}）")
        fold_reason = "多人底池建議棄牌" if is_multiway else "沒有位置優勢棄牌"
        return mk("棄牌", None, f"邊緣局，{fold_reason}（{pct}）")

    return mk("棄牌", None, f"勝率 {pct} < 底池賠率 {po_pct}，棄牌")


def _calc_raise(state: GameState, pot_fraction: float) -> int:
    size = int((state.pot + state.call_amount) * pot_fraction)
    size = max(size, state.call_amount * 2)
    size = min(size, state.hero_stack)
    return size


def _position_hint(position: str) -> str:
    if position.lower() in {"late", "btn", "co", "hj"}:
        return "aggressive"
    if position.lower() in {"early", "utg", "utg+1", "mp", "sb"}:
        return "passive"
    return "neutral"


ACTION_COLOR = {
    "棄牌": "#FF4444", "過牌": "#AAAAAA", "跟注": "#44AAFF",
    "加注": "#00CC66", "全下": "#FF9900",
    "FOLD": "#FF4444", "CHECK": "#AAAAAA", "CALL": "#44AAFF",
    "RAISE": "#00CC66", "ALL-IN": "#FF9900",
}

ACTION_ZH = {
    "FOLD": "棄牌", "CHECK": "過牌", "CALL": "跟注",
    "RAISE": "加注", "ALL-IN": "全下",
}


# ─── EV 分解（多人折疊率指數衰減）────────────────────────────────────────────

def ev_breakdown(state: GameState, equity: float) -> Dict[str, float]:
    """
    計算各行動期望值。

    多人底池關鍵差異：
    - fold_equity = per_opp_fold_rate ^ num_opponents（指數衰減）
    - 3人以上底池：詐唬 EV 大幅下降
    """
    po       = pot_odds(state.call_amount, state.pot)
    s_pot    = spr(state.hero_stack, state.pot)
    n_opp    = max(1, state.num_opponents)

    ev_fold  = 0.0
    ev_check = equity * state.pot

    if state.call_amount > 0:
        ev_call = equity * (state.pot + state.call_amount) - state.call_amount
    else:
        ev_call = ev_check

    raise_sz = _calc_raise(state, 0.75)
    # 多人底池：折疊率 = per_opp_fold ^ n_opp（全員棄牌機率）
    fold_eq   = _multiway_fold_eq(n_opp) if n_opp > 1 else 0.35
    ev_raise  = (fold_eq * state.pot
                 + (1 - fold_eq) * (equity * (state.pot + raise_sz + state.call_amount)
                                    - raise_sz))

    allin_base = max(0.05, 0.40 - s_pot * 0.03)
    allin_fold = allin_base * (_PER_OPP_FOLD_RATE ** (n_opp - 1)) if n_opp > 1 else allin_base
    allin_fold = max(0.02, allin_fold)
    ev_allin   = (allin_fold * state.pot
                  + (1 - allin_fold) * (equity * (state.pot + state.hero_stack)
                                        - state.hero_stack))

    return {
        "fold":  round(ev_fold,  1),
        "check": round(ev_check, 1),
        "call":  round(ev_call,  1),
        "raise": round(ev_raise, 1),
        "allin": round(ev_allin, 1),
    }
