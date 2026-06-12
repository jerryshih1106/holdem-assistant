"""
河牌價值下注注碼最優化器 (River Value Bet Sizing Optimizer)

問題：大多數玩家在河牌圈對強手牌使用固定 60-70% 底池注碼，
而忽略了根據對手的跟注傾向調整注碼可以帶來巨大的 EV 提升。

核心公式：
  EV(bet X) = P(call | X) × X + EV_check

  其中 P(call | X) 是對手在面對 X 注碼時的跟注率。
  由於 P(call) 隨注碼增大而下降，存在一個最優點。

對手跟注率估算模型（基於 WTSD% 和下注大小）：
  基礎跟注率 = f(WTSD%, 對手類型)
  在注碼增大時：每增加 10% 底池，跟注率約降低 3-6%

不同對手類型的最優策略：
  - 跟注站（WTSD > 40%）: 超額下注 1.2-1.5×pot，榨取最多價值
  - 普通玩家（WTSD 28-35%）: 標準 70-90%pot
  - 謹慎型（WTSD 20-28%）: 50-65%pot，太大他們會棄牌
  - 縮牌型（WTSD < 20%）: 40-50%pot，小注碼套他們剩餘的跟注

手牌強度影響（避免因下太大而嚇跑對手）：
  - 堅果手牌（top 5%）: 可用最大值
  - 強手牌（top 10-20%）: 標準最優值
  - 次強手牌（top 20-40%）: 減少 10-20%（避免 fold-equity 損失）
  - 薄價值（top 40-60%）: 偏小（25-40%pot，確保跟注）

"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class SizeEV:
    pct:    float   # bet as fraction of pot (0 = check)
    bb:     float   # bet in BB
    p_call: float   # estimated call probability
    ev_add: float   # EV added vs checking (= p_call × bb)


@dataclass
class RiverValueResult:
    # 最優注碼建議
    optimal_pct:  float   # 0-2.0 (e.g. 0.75 = 75% pot)
    optimal_bb:   float   # in BB
    ev_gain:      float   # EV gain over checking in BB

    # 各注碼 EV 比較
    sizes:        List[SizeEV]

    # 手牌分類
    value_type:   str   # 'nuts'/'strong'/'standard'/'thin'
    value_zh:     str

    # 對手模型
    villain_call_at_opt: float   # estimated call rate at optimal size
    villain_type:        str
    villain_wtsd_used:   float   # actual WTSD used in model

    # 情境
    pot_bb:      float
    stack_bb:    float
    hero_hand_pct: float

    # 說明
    reasoning:   str
    tips:        List[str]
    summary_zh:  str


_VILLAIN_ZH = {
    'fish':    '跟注站(魚)',
    'passive': '被動型',
    'tag':     'TAG 型',
    'nit':     '縮牌型',
    'unknown': '未知',
}

# Base call rates at each size for an average villain (WTSD≈30%)
# Format: (size_pct_of_pot, base_call_rate)
_BASE_CALL_CURVE = [
    (0.00, 1.00),   # check: no bet, villain always "calls" in sense of not folding
    (0.25, 0.65),
    (0.40, 0.57),
    (0.50, 0.52),
    (0.60, 0.47),
    (0.75, 0.42),
    (1.00, 0.34),
    (1.25, 0.27),
    (1.50, 0.22),
    (2.00, 0.15),
]

_SIZES_TO_TEST = [0.25, 0.40, 0.50, 0.60, 0.75, 1.00, 1.25, 1.50, 2.00]


def _classify_villain(vpip: float, wtsd: float) -> str:
    if vpip >= 0.40 or wtsd >= 0.40:
        return 'fish'
    if vpip >= 0.30 or wtsd >= 0.32:
        return 'passive'
    if vpip >= 0.18 or wtsd >= 0.24:
        return 'tag'
    return 'nit'


def _effective_wtsd(villain_type: str, wtsd_observed: float) -> float:
    """
    Convert villain's observed WTSD% to effective river call rate.
    River call rate is higher than raw WTSD because villain has already invested.
    """
    multipliers = {'fish': 1.50, 'passive': 1.30, 'tag': 1.10, 'nit': 0.90, 'unknown': 1.15}
    base = wtsd_observed if wtsd_observed > 0 else {
        'fish': 0.42, 'passive': 0.34, 'tag': 0.28, 'nit': 0.20, 'unknown': 0.30
    }[villain_type]
    return min(0.80, base * multipliers.get(villain_type, 1.15))


def _call_rate(size_pct: float, eff_call_rate_base: float) -> float:
    """
    Estimate villain's call probability at a given bet size.
    Linearly interpolates from the base curve then scales by villain's tendency.
    """
    # Interpolate base curve
    for i in range(len(_BASE_CALL_CURVE) - 1):
        x0, y0 = _BASE_CALL_CURVE[i]
        x1, y1 = _BASE_CALL_CURVE[i + 1]
        if x0 <= size_pct <= x1:
            t = (size_pct - x0) / (x1 - x0)
            base = y0 + t * (y1 - y0)
            break
    else:
        base = _BASE_CALL_CURVE[-1][1]

    # Scale by villain's effective WTSD relative to average (0.35 baseline)
    scale = eff_call_rate_base / 0.35
    return round(min(0.90, max(0.05, base * scale)), 3)


def _value_type(hero_hand_pct: float) -> Tuple[str, str]:
    """Classify hero's hand strength for value betting."""
    if hero_hand_pct >= 0.92:
        return 'nuts', '堅果/準堅果'
    if hero_hand_pct >= 0.80:
        return 'strong', '強手牌'
    if hero_hand_pct >= 0.65:
        return 'standard', '標準價值'
    return 'thin', '薄價值'


def analyze_river_value(
    pot_bb:        float,
    hero_hand_pct: float = 0.85,  # 0-1, higher = stronger
    stack_bb:      float = 100.0,
    villain_wtsd:  float = -1.0,  # from HUD (-1 = unknown)
    villain_vpip:  float = 0.28,  # from HUD
    villain_hands: int   = 0,
    board_static:  bool  = True,   # True = dry board (villain more likely to fold draws)
) -> RiverValueResult:
    """
    Calculate optimal river value bet size to maximize EV.

    Args:
        pot_bb:        Current pot in BB (before hero bets)
        hero_hand_pct: Hero's hand strength percentile (0=worst, 1=best)
                       0.92+ = nuts/near-nuts; 0.80 = set/flush; 0.65 = two pair
        stack_bb:      Effective stack (caps max bet)
        villain_wtsd:  Villain's WTSD% from HUD (-1 = unknown)
        villain_vpip:  Villain's VPIP from HUD
        villain_hands: HUD sample size
        board_static:  True if board is dry (no flush/straight possible)
    """
    tips: List[str] = []

    # ── Villain model ─────────────────────────────────────────────────────────
    villain_type = _classify_villain(villain_vpip, max(0, villain_wtsd))
    wtsd_base    = max(0, villain_wtsd) if villain_wtsd > 0 else 0.0
    eff_wtsd     = _effective_wtsd(villain_type, wtsd_base)

    if villain_hands < 20:
        tips.append(f'樣本不足（{villain_hands}手）：跟注率基於對手類型估算')

    # ── Hand classification ───────────────────────────────────────────────────
    val_type, val_zh = _value_type(hero_hand_pct)

    # Thin value hands should avoid max sizing (risk inducing folds of calling hands)
    max_size_pct = {
        'nuts':     2.00,
        'strong':   1.25,
        'standard': 0.90,
        'thin':     0.50,
    }[val_type]
    max_size_pct = min(max_size_pct, stack_bb / pot_bb)   # can't bet more than stack

    # ── EV calculation at each size ───────────────────────────────────────────
    sizes: List[SizeEV] = []
    best_ev  = 0.0
    best_pct = 0.0

    for pct in _SIZES_TO_TEST:
        if pct > max_size_pct:
            break
        bb       = round(pot_bb * pct, 1)
        p_call   = _call_rate(pct, eff_wtsd)
        ev_added = round(p_call * bb, 2)   # EV gain = P(call) × bet_amount
        sizes.append(SizeEV(pct=pct, bb=bb, p_call=p_call, ev_add=ev_added))
        if ev_added > best_ev:
            best_ev  = ev_added
            best_pct = pct

    if not sizes:
        # No viable bet (stack too small)
        best_pct = 0.25
        best_ev  = 0.0

    # ── Optimal call rate ─────────────────────────────────────────────────────
    opt_call = _call_rate(best_pct, eff_wtsd)
    opt_bb   = round(pot_bb * best_pct, 1)

    # ── Tips ─────────────────────────────────────────────────────────────────
    if villain_type == 'fish':
        tips.append(f'跟注站({villain_vpip:.0%} VPIP)：可以超額下注 1.2-1.5×pot 榨取最大價值')
    elif villain_type == 'nit':
        tips.append(f'縮牌型({villain_vpip:.0%} VPIP)：避免大注碼，用 40-50%pot 讓他們跟注')
    if val_type == 'thin':
        tips.append('薄價值：避免下太大（對手可能有更強的手牌），小注碼確保跟注')
    if not board_static:
        tips.append('牌面有聽牌：部分跟注者可能是聽牌，可以適當增加注碼保護')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = (
        f'{_VILLAIN_ZH[villain_type]}，估算跟注率基礎 {eff_wtsd:.0%}，'
        f'最優注碼 {best_pct:.0%}pot = {opt_bb:.0f}BB，'
        f'估算跟注率 {opt_call:.0%}，'
        f'EV 增益 {best_ev:.1f}BB vs 過牌'
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    summary_zh = (
        f'[河牌價值] {val_zh}  '
        f'{best_pct:.0%}pot={opt_bb:.0f}BB  '
        f'跟注率{opt_call:.0%}  '
        f'+{best_ev:.1f}BB vs 過牌'
    )[:85]

    return RiverValueResult(
        optimal_pct          = best_pct,
        optimal_bb           = opt_bb,
        ev_gain              = round(best_ev, 2),
        sizes                = sizes,
        value_type           = val_type,
        value_zh             = val_zh,
        villain_call_at_opt  = opt_call,
        villain_type         = villain_type,
        villain_wtsd_used    = round(eff_wtsd, 3),
        pot_bb               = pot_bb,
        stack_bb             = stack_bb,
        hero_hand_pct        = hero_hand_pct,
        reasoning            = reasoning,
        tips                 = tips,
        summary_zh           = summary_zh,
    )


def river_value_summary(r: RiverValueResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
