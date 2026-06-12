"""GTO-simplified decision engine: produces action recommendations."""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class GameState:
    hole_cards: list       # e.g. ["Ah", "Kd"]
    community_cards: list  # e.g. ["2h", "7c", "Jd"]
    pot: int               # total pot size in chips
    call_amount: int       # chips needed to call (0 = can check)
    hero_stack: int        # hero remaining stack
    position: str = "unknown"  # "early", "middle", "late", "sb", "bb"
    num_opponents: int = 1


@dataclass
class Decision:
    action: str            # "FOLD" | "CHECK" | "CALL" | "RAISE" | "ALL-IN"
    raise_size: Optional[int]
    reasoning: str
    equity: float
    pot_odds: float
    ev: float              # estimated EV in chips (rough)
    ev_breakdown: Dict[str, float] = field(default_factory=dict)
    # ev_breakdown keys: "fold", "check", "call", "raise", "allin"


def pot_odds(call_amount: int, pot: int) -> float:
    """Minimum equity needed to break even on a call."""
    if call_amount <= 0:
        return 0.0
    total = pot + call_amount
    return call_amount / total


def spr(stack: int, pot: int) -> float:
    """Stack-to-pot ratio."""
    return stack / pot if pot > 0 else 999.0


def recommend(state: GameState, equity: float, tie_rate: float) -> Decision:
    """
    Produce a decision recommendation given game state and equity.

    Logic:
    - Check if we have a free option (call_amount == 0)
    - Compare equity to pot odds
    - Adjust for position and SPR
    """
    po = pot_odds(state.call_amount, state.pot)
    edge = equity - po          # positive = profitable call
    stack_pot = spr(state.hero_stack, state.pot)

    # EV estimate (rough): edge * pot
    ev = edge * (state.pot + state.call_amount)
    evb = ev_breakdown(state, equity)

    def mk(action, raise_sz, reason):
        return Decision(action, raise_sz, reason, equity, po, ev, evb)

    pct = f"{equity:.0%}"
    po_pct = f"{po:.0%}"

    # --- 免費選項（過牌） ---
    if state.call_amount <= 0:
        if equity >= 0.65:
            raise_sz = _calc_raise(state, 0.75)
            return mk("加注", raise_sz, f"強牌（勝率 {pct}），下注取得價值")
        if equity >= 0.40:
            return mk("過牌", None, f"中等牌力（勝率 {pct}），過牌控制底池")
        return mk("過牌", None, f"弱牌（勝率 {pct}），過牌觀望")

    # --- 需要付錢繼續 ---
    if equity >= 0.80:
        raise_sz = _calc_raise(state, 1.0)
        return mk("加注", raise_sz, f"怪獸牌（勝率 {pct}），加注或再加注")

    if equity >= 0.65:
        if stack_pot < 2.0:
            return mk("全下", state.hero_stack,
                      f"高勝率（{pct}）+ 短籌碼，直接全下")
        raise_sz = _calc_raise(state, 0.75)
        return mk("加注", raise_sz, f"強牌（勝率 {pct}），加注取得價值")

    if equity >= po + 0.05:
        return mk("跟注", None,
                  f"勝率 {pct} > 底池賠率 {po_pct}，正期望值跟注")

    if abs(equity - po) <= 0.04:
        hint = _position_hint(state.position)
        if hint == "aggressive":
            return mk("跟注", None,
                      f"邊緣局面，有位置優勢跟注（勝率 {pct}）")
        return mk("棄牌", None,
                  f"邊緣局面，沒有位置優勢棄牌（勝率 {pct}）")

    return mk("棄牌", None, f"勝率 {pct} < 底池賠率 {po_pct}，棄牌")


def _calc_raise(state: GameState, pot_fraction: float) -> int:
    """Recommend raise size as a fraction of pot."""
    size = int((state.pot + state.call_amount) * pot_fraction)
    size = max(size, state.call_amount * 2)
    size = min(size, state.hero_stack)
    return size


def _position_hint(position: str) -> str:
    late = {"late", "btn", "co", "hj"}
    early = {"early", "utg", "utg+1", "mp", "sb"}
    p = position.lower()
    if p in late:
        return "aggressive"
    if p in early:
        return "passive"
    return "neutral"


ACTION_COLOR = {
    "棄牌":  "#FF4444",
    "過牌":  "#AAAAAA",
    "跟注":  "#44AAFF",
    "加注":  "#00CC66",
    "全下":  "#FF9900",
    # 英文備用（向後相容）
    "FOLD":   "#FF4444",
    "CHECK":  "#AAAAAA",
    "CALL":   "#44AAFF",
    "RAISE":  "#00CC66",
    "ALL-IN": "#FF9900",
}

ACTION_ZH = {
    "FOLD":   "棄牌",
    "CHECK":  "過牌",
    "CALL":   "跟注",
    "RAISE":  "加注",
    "ALL-IN": "全下",
}


# ── EV breakdown ──────────────────────────────────────────────────────────────

def ev_breakdown(state: GameState, equity: float) -> Dict[str, float]:
    """
    Calculate EV for each possible action given game state and equity.

    Simplified EV model:
      EV(fold)  = 0  (reference point)
      EV(check) = equity × pot  (hero wins the pot at showdown)
      EV(call)  = equity × (pot + call) - call
      EV(raise) = equity × (pot + raise_size) - raise_size
                  with some fold-equity assumption (opponent folds ~40% to a PSB)
      EV(allin) = equity × (pot + stack) - stack
                  with fold equity based on SPR
    """
    po     = pot_odds(state.call_amount, state.pot)
    s_pot  = spr(state.hero_stack, state.pot)

    ev_fold  = 0.0
    ev_check = equity * state.pot

    if state.call_amount > 0:
        ev_call = equity * (state.pot + state.call_amount) - state.call_amount
    else:
        ev_call = ev_check   # checking is calling with 0

    # Raise: assume opponent folds ~35% to a 75%-pot raise
    raise_sz  = _calc_raise(state, 0.75)
    fold_eq   = 0.35   # opponent's fold frequency to a raise
    ev_raise  = (fold_eq * state.pot
                 + (1 - fold_eq) * (equity * (state.pot + raise_sz + state.call_amount)
                                    - raise_sz))

    # All-in: fold equity drops with deep stacks
    allin_fold = max(0.05, 0.40 - s_pot * 0.03)
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
