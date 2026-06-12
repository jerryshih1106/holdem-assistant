"""
面對 4-bet 決策顧問 (Facing 4-bet Advisor)

場景：英雄 3-bet 後對手 4-bet，英雄需要決定：
  - 繼續加注（5-bet 推牌）
  - 跟注（IP 或 OOP 打翻後）
  - 棄牌

為什麼這個場景特別重要？
  1. 底池極大（4-bet pot 通常 30-50BB），決策錯誤非常昂貴
  2. 大多數玩家憑感覺決定，缺乏系統框架
  3. 對手 4-bet 範圍通常極緊（2-5%），需要準確估算
  4. 籌碼深度決定：有時叫注後翻牌 SPR 太低，直接推更好

核心邏輯：
  1. 根據對手位置 + 4-bet % 估算對手範圍
  2. 計算英雄的勝率 vs 那個範圍（基於手牌百分位）
  3. 計算底池賠率（所需最低勝率）
  4. 決策：推牌（最高 EV） / 跟注（有利賠率） / 棄牌

關鍵原則：
  - 100BB 深度：AA/KK → 推牌；QQ/AK → 視情況推或跟；JJ → 多數情況棄牌/偶爾跟
  - 短籌碼（30-50BB）：跟注範圍縮小，轉換為推牌
  - 如果跟注後 SPR < 2：應該直接推（已基本 committed）

"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Facing4betResult:
    # 決策
    action:         str    # 'jam'/'call'/'fold'
    action_zh:      str
    jam_frequency:  float  # 推牌頻率（GTO 混合策略）
    call_frequency: float  # 跟注頻率
    fold_frequency: float  # 棄牌頻率

    # 賠率分析
    required_equity:      float  # 跟注/推牌所需最低勝率
    hero_equity_vs_range: float  # 英雄 vs 對手 4-bet 範圍的估算勝率
    ev_margin:            float  # hero_equity - required_equity（正=有利可圖）

    # 對手範圍
    villain_4bet_range_pct: float   # 估算對手的 4-bet 範圍（0-1）
    villain_range_zh:       str     # 中文範圍描述

    # 籌碼分析
    hero_call_bb:      float  # 英雄需追加的籌碼
    pot_before_bb:     float  # 英雄行動前的底池
    total_pot_if_call: float  # 跟注後底池
    spr_if_call:       float  # 跟注後的 SPR（非全下時）
    is_all_in_if_call: bool   # 跟注即全下

    # 情境
    hero_hand_pct: float   # 英雄手牌百分位（0-1，越高越強）
    stack_bb:      float
    villain_pos:   str

    # 說明
    verdict_zh:  str
    reasoning:   str
    tips:        List[str]
    summary_zh:  str


_VILLAIN_4BET_ZH = {
    'fish':    '魚型玩家',
    'passive': '被動型玩家',
    'tag':     'TAG 玩家',
    'nit':     '縮牌玩家',
    'unknown': '未知類型',
}

# Villain 4-bet range by position (base fraction of all starting hands)
# These approximate GTO/population 4-bet frequencies
_4BET_RANGE_BASE = {
    'BTN': 0.045,    # wider (BTN vs SB/BB 3-bet)
    'CO':  0.035,
    'HJ':  0.028,
    'UTG': 0.020,
    'SB':  0.050,    # SB 4-bets IP vs all
    'BB':  0.040,    # BB defends vs steal
    'LJ':  0.025,
}


def _estimate_range(villain_pos: str, villain_4bet_pct: float, villain_vpip: float) -> float:
    """
    Estimate villain's 4-bet range as fraction of all hands.

    villain_4bet_pct: observed 4-bet% from HUD (0-1), or -1 if unknown
    """
    pos = villain_pos.upper()
    if pos not in _4BET_RANGE_BASE:
        pos = 'CO'
    base = _4BET_RANGE_BASE[pos]

    # If HUD 4-bet% is available and reliable, use it directly
    if 0.01 <= villain_4bet_pct <= 0.20:
        base = villain_4bet_pct

    # VPIP adjustment: fish may 4-bet wider (value-heavy) or nit much tighter
    if villain_vpip >= 0.40:      # fish: wider but mostly value (they don't bluff-4-bet)
        base *= 1.15
    elif villain_vpip < 0.18:     # nit: very tight, almost always KK+
        base *= 0.65

    return round(min(0.20, max(0.01, base)), 3)


def _range_to_zh(range_pct: float) -> str:
    """Describe the 4-bet range in Chinese."""
    if range_pct <= 0.015:
        return 'AA（超緊，可能只 KK+）'
    if range_pct <= 0.025:
        return 'QQ+, AKs（極緊）'
    if range_pct <= 0.040:
        return 'QQ+, AK（標準 4-bet 範圍）'
    if range_pct <= 0.060:
        return 'JJ+, AK, 部分 A5s（含詐唬）'
    if range_pct <= 0.090:
        return 'TT+, AQ+, 詐唬組合（激進）'
    return '寬 4-bet 範圍（魚型或激進玩家）'


def _estimate_equity(hero_hand_pct: float, villain_range_pct: float) -> float:
    """
    Estimate hero's equity vs villain's 4-bet range using calibrated breakpoints.

    villain_range_pct: fraction of all hands (e.g. 0.03 = top 3% = QQ+/AK)
    hero_hand_pct:     hero's hand percentile (0-1)

    Calibration anchors:
      - AA (0.995) vs BTN range (4.5%): ~78% equity
      - KK (0.990) vs BTN range (4.5%): ~65%
      - QQ (0.985) vs BTN range (4.5%): ~52%
      - JJ (0.975) vs BTN range (4.5%): ~44%
      - JJ (0.975) vs UTG range (2.0%): ~34%
      - JJ (0.975) vs nit range (1.3%): ~26-28%  ← below pot odds → fold
    """
    villain_threshold  = 1.0 - villain_range_pct
    # normalized position: >0 = hero within/above range, <0 = hero below range
    # scale: ±1 = one full range width above/below threshold
    normalized_pos = (hero_hand_pct - villain_threshold) / max(0.01, villain_range_pct)

    # Piecewise linear calibrated to real poker equity values
    _BREAKPOINTS = [
        (-2.0, 0.22), (-1.5, 0.24), (-1.0, 0.27),
        (-0.5, 0.34), ( 0.0, 0.44), ( 0.3, 0.47),
        ( 0.5, 0.50), ( 0.7, 0.56), ( 0.9, 0.68),
        ( 1.0, 0.76), ( 1.5, 0.82),
    ]

    if normalized_pos <= _BREAKPOINTS[0][0]:
        return _BREAKPOINTS[0][1]
    if normalized_pos >= _BREAKPOINTS[-1][0]:
        return _BREAKPOINTS[-1][1]

    for i in range(len(_BREAKPOINTS) - 1):
        x0, y0 = _BREAKPOINTS[i]
        x1, y1 = _BREAKPOINTS[i + 1]
        if x0 <= normalized_pos <= x1:
            t = (normalized_pos - x0) / (x1 - x0)
            return round(y0 + t * (y1 - y0), 3)

    return 0.45


def analyze_facing_4bet(
    villain_pos:        str   = 'BTN',
    fourbet_size_bb:    float = 24.0,   # villain's 4-bet total size in BB
    threebet_size_bb:   float = 9.0,    # hero's 3-bet total size in BB
    pot_pre_3bet_bb:    float = 5.0,    # pot before hero's 3-bet (open + blinds)
    hero_hand_pct:      float = 0.975,  # hand percentile (AA=0.995, KK=0.990, QQ=0.985, JJ=0.975)
    hero_stack_bb:      float = 100.0,
    villain_vpip:       float = 0.28,
    villain_4bet_pct:   float = -1.0,   # -1 = unknown (use position-based estimate)
    villain_hands:      int   = 0,
) -> Facing4betResult:
    """
    Analyze hero's decision when facing a preflop 4-bet.

    Args:
        villain_pos:      Villain's position
        fourbet_size_bb:  Total 4-bet size in BB (not the raise amount)
        threebet_size_bb: Hero's 3-bet size in BB (already invested)
        pot_pre_3bet_bb:  Pot size before hero's 3-bet (includes open + blinds)
        hero_hand_pct:    Hero's hand percentile (e.g. 0.995=AA, 0.975=JJ)
        hero_stack_bb:    Effective stack (after posting)
        villain_vpip:     Villain's VPIP from HUD (0-1)
        villain_4bet_pct: Villain's 4-bet% from HUD (-1 = unknown)
        villain_hands:    HUD sample size
    """
    tips: List[str] = []

    # ── Range estimation ───────────────────────────────────────────────────────
    villain_range_pct = _estimate_range(villain_pos, villain_4bet_pct, villain_vpip)
    villain_range_zh  = _range_to_zh(villain_range_pct)

    if villain_hands < 20 and villain_4bet_pct > 0:
        tips.append(f'樣本不足（{villain_hands}手）：4-bet 範圍基於位置估算')

    # ── Pot odds ──────────────────────────────────────────────────────────────
    # Current pot = pot_before_3bet + threebet + fourbet
    pot_before_bb     = pot_pre_3bet_bb + threebet_size_bb + fourbet_size_bb
    hero_call_bb      = max(0.0, fourbet_size_bb - threebet_size_bb)
    total_if_call     = pot_before_bb + hero_call_bb

    if total_if_call <= 0:
        required_equity = 0.50
    else:
        required_equity = round(hero_call_bb / total_if_call, 4)

    # ── Is calling = all-in? ──────────────────────────────────────────────────
    remaining_after_call = hero_stack_bb - hero_call_bb
    is_all_in = remaining_after_call <= 1.0
    spr_if_call = remaining_after_call / total_if_call if not is_all_in else 0.0

    # ── Hero equity vs range ─────────────────────────────────────────────────
    hero_equity = _estimate_equity(hero_hand_pct, villain_range_pct)
    ev_margin   = round(hero_equity - required_equity, 4)

    # ── Decision logic ────────────────────────────────────────────────────────
    # For very short SPR after calling (< 2), shoving is often better than flatting
    spr_too_low_to_flat = (not is_all_in) and (spr_if_call < 2.0)

    # Base decision framework:
    # 1. Always jam with premium (hero_equity >= 0.65)
    # 2. Call if pot-odds positive and SPR viable
    # 3. Fold otherwise

    if hero_equity >= 0.65:
        # Premium hands: AA, KK vs any 4-bet range → jam
        action = 'jam'
        action_zh = '5-bet 推牌'
        jam_frequency  = 1.0
        call_frequency = 0.0
        fold_frequency = 0.0
        verdict_zh = '溢價手牌，永遠推牌'

    elif hero_equity >= required_equity + 0.08:
        # Clear call or jam depending on SPR
        if is_all_in or spr_too_low_to_flat:
            action = 'jam'
            action_zh = '5-bet 推牌（SPR 太低，叫注幾乎等於全下）'
            jam_frequency  = 0.85
            call_frequency = 0.15
            fold_frequency = 0.0
            verdict_zh = '推牌（短籌碼/低 SPR）'
        else:
            action = 'call'
            action_zh = '跟注（打翻後）'
            jam_frequency  = 0.20
            call_frequency = 0.70
            fold_frequency = 0.10
            verdict_zh = '有利賠率，跟注打翻後'

    elif hero_equity >= required_equity + 0.02:
        # Marginal call
        if is_all_in or spr_too_low_to_flat:
            action = 'fold'
            action_zh = '棄牌（邊緣手牌，短籌碼不划算）'
            jam_frequency  = 0.05
            call_frequency = 0.05
            fold_frequency = 0.90
            verdict_zh = '邊緣棄牌（SPR 短，GTO 傾向棄牌）'
        else:
            action = 'call'
            action_zh = '跟注（邊緣，偶爾混合棄牌）'
            jam_frequency  = 0.10
            call_frequency = 0.55
            fold_frequency = 0.35
            verdict_zh = '邊緣跟注（混合策略）'

    elif ev_margin >= -0.03:
        # Near-zero: very marginal, mostly fold
        action = 'fold'
        action_zh = '棄牌（略虧，偶爾跟注保持平衡）'
        jam_frequency  = 0.05
        call_frequency = 0.15
        fold_frequency = 0.80
        verdict_zh = '邊緣棄牌'

    else:
        # Clear fold
        action = 'fold'
        action_zh = '棄牌'
        jam_frequency  = 0.0
        call_frequency = 0.0
        fold_frequency = 1.0
        verdict_zh = '明確棄牌（勝率不足）'

    # ── GTO bluff-catch consideration ─────────────────────────────────────────
    # If villain 4-bets very wide (> 6%), some fold equity exists for 5-bet bluffs
    if villain_range_pct > 0.06 and hero_hand_pct > 0.95:
        tips.append(f'對手 4-bet 範圍較寬（{villain_range_pct:.0%}）：A5s 等阻斷牌可考慮 5-bet 詐唬')
    if spr_if_call > 0 and spr_if_call < 2.0 and action == 'call':
        tips.append(f'跟注後 SPR={spr_if_call:.1f} 很低，考慮直接推牌（避免 OOP 尷尬）')
    if villain_vpip >= 0.40:
        tips.append('魚型玩家 4-bet 通常是強手牌（不會詐唬）：更謹慎對待')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = (
        f'{villain_pos} 4-bet 到 {fourbet_size_bb:.0f}BB，估算範圍 {villain_range_pct:.0%}'
        f'（{villain_range_zh[:12]}），英雄勝率 {hero_equity:.0%} vs 所需 {required_equity:.0%}'
        f'，叫注額 {hero_call_bb:.0f}BB'
    )

    # ── Summary ────────────────────────────────────────────────────────────────
    summary_zh = (
        f'[面對4bet] {verdict_zh[:12]}  '
        f'勝率{hero_equity:.0%}(需{required_equity:.0%})  '
        f'{villain_range_pct:.0%}範圍  '
        f'叫{hero_call_bb:.0f}BB'
    )[:85]

    return Facing4betResult(
        action              = action,
        action_zh           = action_zh,
        jam_frequency       = round(jam_frequency, 2),
        call_frequency      = round(call_frequency, 2),
        fold_frequency      = round(fold_frequency, 2),
        required_equity     = required_equity,
        hero_equity_vs_range = hero_equity,
        ev_margin           = ev_margin,
        villain_4bet_range_pct = villain_range_pct,
        villain_range_zh    = villain_range_zh,
        hero_call_bb        = hero_call_bb,
        pot_before_bb       = pot_before_bb,
        total_pot_if_call   = total_if_call,
        spr_if_call         = round(spr_if_call, 2),
        is_all_in_if_call   = is_all_in,
        hero_hand_pct       = hero_hand_pct,
        stack_bb            = hero_stack_bb,
        villain_pos         = villain_pos,
        verdict_zh          = verdict_zh,
        reasoning           = reasoning,
        tips                = tips,
        summary_zh          = summary_zh,
    )


def facing_4bet_summary(r: Facing4betResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
