"""
面對全下跟注計算器 (Jam Call Threshold Calculator)

場景：對手推牌（All-in Shove），英雄需要決定是否跟注。
典型情況：有效籌碼 15-50BB，對手翻前或翻後推牌。

核心邏輯：
  1. 根據對手位置 + 籌碼深度 + VPIP 估算對手的推牌範圍
  2. 計算所需權益（required equity）= call / (pot + call)
  3. 與英雄的實際股權比較
  4. 計算 EV（期望值）

推牌範圍估算模型：
  - 對手籌碼越少，推牌範圍越寬
  - 後位（BTN/SB）推牌範圍最寬
  - 被動型玩家（高 VPIP）推牌範圍更寬
  - 縮牌型玩家推牌範圍更窄（代表更強手牌）

所需最低勝率公式：
  required_eq = call / (current_pot + call)

  這裡 call 是英雄需要叫進的額外籌碼（如果英雄已入注，則為差額）

EV 公式：
  EV_call = hero_equity × (pot_after) - (1 - hero_equity) × call
  EV_fold = 0（已投入的籌碼不計）
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class JamCallResult:
    # 決策
    should_call:     bool
    call_frequency:  float    # 推薦跟注頻率（0=棄牌, 1=永遠跟注）

    # 所需權益
    required_equity: float    # 跟注所需最低勝率（pot odds）
    hero_equity:     float    # 英雄估算勝率

    # EV 分析
    ev_call:         float    # 跟注的期望值（BB）
    ev_fold:         float    # 棄牌的期望值（= 0，已入注不計）
    ev_advantage:    float    # call_ev - fold_ev（即淨 EV 差）

    # 對手範圍
    villain_range_pct:  float    # 估算的對手推牌範圍（0-1）
    villain_range_zh:   str      # 中文範圍描述

    # 情境
    villain_stack_bb:   float
    pot_before_bb:      float
    call_amount_bb:     float    # 英雄需要追加的籌碼
    villain_pos:        str
    villain_profile:    str      # 'fish'/'nit'/'passive'/'unknown'

    # 說明
    equity_margin:   float    # hero_equity - required_equity（正=有利可圖）
    verdict:         str      # 'clear_call'/'marginal_call'/'marginal_fold'/'clear_fold'
    verdict_zh:      str
    reasoning:       str
    tips:            List[str]
    summary_zh:      str


_VILLAIN_ZH = {
    'fish':    '魚型玩家',
    'passive': '被動型玩家',
    'tag':     'TAG 玩家',
    'nit':     '縮牌玩家',
    'unknown': '未知類型',
}

# (position, effective_stack_bb) → base shove range pct
# Values estimated from Nash equilibrium and solver data
_SHOVE_RANGE_BASE = {
    # BTN is the most liberal shover
    ('BTN', 10): 0.70, ('BTN', 15): 0.55, ('BTN', 20): 0.42,
    ('BTN', 25): 0.32, ('BTN', 30): 0.25, ('BTN', 35): 0.18,
    ('BTN', 40): 0.14, ('BTN', 50): 0.10,
    # SB shoves wide into BB
    ('SB',  10): 0.75, ('SB',  15): 0.60, ('SB',  20): 0.48,
    ('SB',  25): 0.36, ('SB',  30): 0.28, ('SB',  35): 0.20,
    ('SB',  40): 0.16, ('SB',  50): 0.11,
    # CO slightly tighter than BTN
    ('CO',  10): 0.60, ('CO',  15): 0.46, ('CO',  20): 0.34,
    ('CO',  25): 0.25, ('CO',  30): 0.19, ('CO',  35): 0.14,
    ('CO',  40): 0.11, ('CO',  50): 0.08,
    # HJ/MP moderately tight
    ('HJ',  10): 0.50, ('HJ',  15): 0.38, ('HJ',  20): 0.28,
    ('HJ',  25): 0.20, ('HJ',  30): 0.15, ('HJ',  35): 0.11,
    ('HJ',  40): 0.09, ('HJ',  50): 0.06,
    # UTG/EP tightest
    ('UTG', 10): 0.38, ('UTG', 15): 0.28, ('UTG', 20): 0.20,
    ('UTG', 25): 0.14, ('UTG', 30): 0.10, ('UTG', 35): 0.07,
    ('UTG', 40): 0.05, ('UTG', 50): 0.04,
    # BB defending vs SB shove (defence is widest)
    ('BB',  10): 0.72, ('BB',  15): 0.58, ('BB',  20): 0.45,
    ('BB',  25): 0.34, ('BB',  30): 0.26, ('BB',  35): 0.19,
    ('BB',  40): 0.15, ('BB',  50): 0.11,
}

# Range-to-equity mapping: how much equity does a random hand have vs villain's range?
# A stronger (tighter) villain range → hero's hand has LESS equity vs it
# Approximation: avg equity ≈ 0.36 + (0.50 - villain_range_pct) × 0.18
# At range=50% → avg equity ≈ 0.36, at range=10% → avg equity ≈ 0.43 (villain is stronger)
# This is deliberately approximate; replace with MC sim if available.
def _hero_equity_vs_range(hero_hand_pct: float, villain_range_pct: float) -> float:
    """
    Estimate hero's equity vs villain's range.

    hero_hand_pct: hero's hand strength percentile (0-1, higher = stronger)
    villain_range_pct: fraction of hands villain is shoving (smaller = tighter = stronger)
    """
    # Base equity a 50th-percentile hand has vs villain's range
    base = 0.37 + (0.50 - min(0.50, villain_range_pct)) * 0.20

    # Adjust for hero's hand strength relative to median (0.50)
    # +1% per 5 percentile above/below median (rough linear)
    hero_adj = (hero_hand_pct - 0.50) * 0.30

    equity = base + hero_adj
    return max(0.20, min(0.80, round(equity, 3)))


def _classify_villain(vpip: float) -> str:
    if vpip >= 0.40:
        return 'fish'
    if vpip >= 0.30:
        return 'passive'
    if vpip >= 0.18:
        return 'tag'
    return 'nit'


def _interpolate_shove_range(pos: str, stack_bb: float) -> float:
    """
    Interpolate shove range from lookup table.
    Returns fraction of hands villain shoves (0-1).
    """
    pos = pos.upper()
    if pos in ('MP', 'MP1', 'MP2', 'LJ'):
        pos = 'HJ'
    if pos not in ('BTN', 'SB', 'CO', 'HJ', 'UTG', 'BB'):
        pos = 'UTG'

    # Find bracket
    breakpoints = [10, 15, 20, 25, 30, 35, 40, 50]
    stack_bb = max(5, min(50, stack_bb))

    if stack_bb <= 10:
        return _SHOVE_RANGE_BASE.get((pos, 10), 0.35)
    if stack_bb >= 50:
        return _SHOVE_RANGE_BASE.get((pos, 50), 0.06)

    # Linear interpolation
    for i in range(len(breakpoints) - 1):
        lo, hi = breakpoints[i], breakpoints[i + 1]
        if lo <= stack_bb <= hi:
            lo_val = _SHOVE_RANGE_BASE.get((pos, lo), 0.20)
            hi_val = _SHOVE_RANGE_BASE.get((pos, hi), 0.15)
            t = (stack_bb - lo) / (hi - lo)
            return lo_val + (hi_val - lo_val) * t

    return 0.20


# Map range fraction to a human-readable hand description
def _range_to_zh(range_pct: float) -> str:
    if range_pct >= 0.60:
        return '非常寬（幾乎任何兩張牌）'
    if range_pct >= 0.45:
        return '很寬（22+, A2s+, K5s+, A8o+, KJo+...）'
    if range_pct >= 0.30:
        return '寬（44+, A4s+, KTs+, ATo+, KQo...）'
    if range_pct >= 0.20:
        return '標準（66+, A7s+, KQs, AJo+, KQo）'
    if range_pct >= 0.13:
        return '偏緊（88+, ATs+, AJo+, KQs）'
    if range_pct >= 0.08:
        return '很緊（TT+, AQs+, AKo）'
    return '極緊（QQ+, AKs）'


def analyze_jam_call(
    villain_pos:       str   = 'BTN',
    villain_stack_bb:  float = 25.0,   # effective shove size
    hero_hand_pct:     float = 0.60,   # hero hand strength percentile (0-1)
    pot_before_bb:     float = 3.0,    # pot before villain shoves
    hero_invested_bb:  float = 0.0,    # chips hero already put in (0 if not yet bet)
    villain_vpip:      float = 0.28,   # villain's VPIP from HUD
    villain_hands:     int   = 0,      # sample size for VPIP reliability
) -> JamCallResult:
    """
    Calculate whether hero should call an all-in shove.

    Args:
        villain_pos:      Villain's position when they shoved
        villain_stack_bb: Effective stack / shove size in BB
        hero_hand_pct:    Hero's hand strength (0=worst, 1=best; AA=0.99, AKs=0.92)
        pot_before_bb:    Pot size before villain shoves
        hero_invested_bb: Chips hero already invested in this pot
        villain_vpip:     Villain's VPIP from HUD (0-1)
        villain_hands:    How many hands we have on villain
    """
    tips: List[str] = []

    # ── Villain range estimation ───────────────────────────────────────────────
    villain_type  = _classify_villain(villain_vpip)
    base_range    = _interpolate_shove_range(villain_pos, villain_stack_bb)

    # VPIP adjustment: fish shoves wider, nit shoves tighter
    vpip_adj = {
        'fish':    1.30,
        'passive': 1.10,
        'tag':     1.00,
        'nit':     0.75,
        'unknown': 1.00,
    }[villain_type]

    # Small sample penalty: with <20 hands, revert partially to unknown (1.0)
    if villain_hands > 0 and villain_hands < 20:
        sample_weight  = villain_hands / 20.0
        vpip_adj = 1.0 + (vpip_adj - 1.0) * sample_weight

    villain_range_pct = round(min(0.85, max(0.03, base_range * vpip_adj)), 3)

    # ── Pot odds (required equity) ────────────────────────────────────────────
    # call = shove_size - hero_invested (cannot be negative)
    call_amount = max(0.0, villain_stack_bb - hero_invested_bb)
    total_pot_if_call = pot_before_bb + villain_stack_bb + call_amount

    if total_pot_if_call <= 0:
        required_equity = 0.50
    else:
        required_equity = round(call_amount / total_pot_if_call, 4)

    # ── Hero equity ───────────────────────────────────────────────────────────
    hero_equity = _hero_equity_vs_range(hero_hand_pct, villain_range_pct)

    # ── EV ────────────────────────────────────────────────────────────────────
    # If hero calls: win total pot × equity, lose call amount × (1-equity)
    ev_call = round(hero_equity * total_pot_if_call - call_amount * (1 - hero_equity), 2)
    ev_fold  = 0.0  # already-invested chips are sunk cost

    ev_advantage   = round(ev_call - ev_fold, 2)
    equity_margin  = round(hero_equity - required_equity, 4)

    # ── Verdict ───────────────────────────────────────────────────────────────
    if equity_margin >= 0.10:
        verdict    = 'clear_call'
        verdict_zh = '明確跟注'
        should_call = True
        call_frequency = min(1.0, 0.85 + equity_margin * 0.5)
    elif equity_margin >= 0.03:
        verdict    = 'marginal_call'
        verdict_zh = '邊緣跟注'
        should_call = True
        call_frequency = 0.60 + equity_margin * 2.0
    elif equity_margin >= -0.03:
        verdict    = 'marginal_fold'
        verdict_zh = '邊緣棄牌'
        should_call = False
        call_frequency = 0.30 + equity_margin * 2.0
    else:
        verdict    = 'clear_fold'
        verdict_zh = '明確棄牌'
        should_call = False
        call_frequency = max(0.0, 0.20 + equity_margin * 2.0)

    call_frequency = round(max(0.0, min(1.0, call_frequency)), 2)

    # ── Tips ─────────────────────────────────────────────────────────────────
    if villain_hands < 15:
        tips.append(f'樣本不足（{villain_hands}手）：範圍估算基於位置，不夠精確')
    if villain_type == 'fish':
        tips.append(f'魚型玩家(VPIP={villain_vpip:.0%})：推牌範圍更寬，跟注門檻降低')
    elif villain_type == 'nit':
        tips.append(f'縮牌玩家(VPIP={villain_vpip:.0%})：推牌範圍很緊，謹慎跟注')
    if villain_stack_bb <= 15:
        tips.append(f'籌碼 {villain_stack_bb:.0f}BB 很短：推牌範圍極寬，低勝率也可跟注')
    if abs(equity_margin) < 0.03:
        tips.append(f'邊緣情況（邊際 {equity_margin:+.1%}）：GTO 建議混合策略')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = (
        f'{villain_pos} {villain_type} {villain_stack_bb:.0f}BB 推牌，'
        f'估算範圍 {villain_range_pct:.0%}（{_range_to_zh(villain_range_pct)[:8]}）'
        f'，英雄勝率 {hero_equity:.0%} vs 所需 {required_equity:.0%}'
        f'，EV {ev_call:+.1f}BB'
    )

    # ── Summary ────────────────────────────────────────────────────────────────
    summary_zh = (
        f'[跟注分析] {verdict_zh}  '
        f'勝率{hero_equity:.0%}(需{required_equity:.0%})  '
        f'EV{ev_call:+.1f}BB  '
        f'{villain_range_pct:.0%}範圍'
    )[:85]

    return JamCallResult(
        should_call        = should_call,
        call_frequency     = call_frequency,
        required_equity    = required_equity,
        hero_equity        = hero_equity,
        ev_call            = ev_call,
        ev_fold            = ev_fold,
        ev_advantage       = ev_advantage,
        villain_range_pct  = villain_range_pct,
        villain_range_zh   = _range_to_zh(villain_range_pct),
        villain_stack_bb   = villain_stack_bb,
        pot_before_bb      = pot_before_bb,
        call_amount_bb     = call_amount,
        villain_pos        = villain_pos,
        villain_profile    = villain_type,
        equity_margin      = equity_margin,
        verdict            = verdict,
        verdict_zh         = verdict_zh,
        reasoning          = reasoning,
        tips               = tips,
        summary_zh         = summary_zh,
    )


def jam_call_summary(r: JamCallResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
