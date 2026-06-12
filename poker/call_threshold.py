"""
剝削性跟注門檻計算器 (Exploitative Call Threshold Calculator)

問題：底池賠率告訴你需要多少勝率，但沒告訴你對手實際有多少詐唬。
當對手詐唬頻率高於均衡時，你可以以更低勝率有利跟注；反之需要更高勝率。

核心公式：
  純底池賠率門檻 = call / (pot + call)

  剝削性調整：
    對手詐唬頻率 b_freq（估算）
    均衡詐唬頻率 b_gto = call / (pot + call)   ← 讓你無差異的詐唬頻率

    若 b_freq > b_gto：對手過度詐唬 → 你可以降低門檻（廣泛跟注）
    若 b_freq < b_gto：對手詐唬不足 → 你需要提高門檻（謹慎跟注）

    剝削調整量 = (b_freq - b_gto) × 0.5 × 勝率   ← 0.5 = 保守調整係數
    剝削門檻   = 純底池賠率門檻 - 剝削調整量

  詐唬頻率估算（基於 WTSD + 街道 + 注碼大小）：

    基礎詐唬頻率（標準玩家）：
      翻牌：b_base = 0.45（C-bet 範圍約 45% 詐唬）
      轉牌：b_base = 0.35（barrel 範圍約 35% 詐唬）
      河牌：b_base = 0.25（river bet 約 25% 詐唬）

    WTSD 調整（WTSD 高 = 玩家喜歡攤牌 = 他們詐唬更少）：
      WTSD < 24%：+0.10 (he folds rivers easily → must have value when betting)
      WTSD 24-30%：+0.0（標準）
      WTSD 30-38%：-0.05（他喜歡攤牌，因此範圍寬 → 更多詐唬）
      WTSD > 38%：-0.10（跟注站，他很少詐唬大注）

    注碼大小調整（大注 = 更極化 = 更多強牌也更多詐唬）：
      小注（≤ 33%）：-0.05（合併範圍，較少純詐唬）
      標準注（34-67%）：+0.0
      大注（68-100%）：+0.05（極化，更多詐唬）
      超池（> 100%）：+0.08（高度極化，詐唬比例高）

    AF 調整（AF 高 = 下注更激進 = 更多詐唬）：
      AF > 2.5：+0.06
      AF < 0.8：-0.08（被動，下注 = 真實牌力）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# ── Population bluff frequency baselines by street ────────────────────────────

_BASE_BLUFF = {'flop': 0.45, 'turn': 0.35, 'river': 0.25, 'preflop': 0.40}


def _estimate_bluff_freq(
    street:       str,
    villain_wtsd: float,     # -1 = unknown
    villain_af:   float,     # -1 = unknown
    bet_pot_ratio: float,    # bet / pot
) -> float:
    """Estimate villain's bluff frequency for a specific bet."""
    base = _BASE_BLUFF.get(street, 0.30)

    # WTSD adjustment
    eff_wtsd = villain_wtsd if villain_wtsd > 0 else 0.29
    if eff_wtsd < 0.24:
        wtsd_adj = +0.10   # low WTSD = nit, bets = value (folds at showdown → ranges up)
    elif eff_wtsd < 0.34:
        wtsd_adj = 0.0     # standard (24-34% is normal range)
    elif eff_wtsd < 0.40:
        wtsd_adj = -0.05   # above average, slightly more value-heavy bets
    else:
        wtsd_adj = -0.10   # calling station, bets = value (doesn't bluff into caller)

    # Bet size adjustment (polarized = more bluffs, merged = fewer bluffs)
    if bet_pot_ratio <= 0.33:
        size_adj = -0.05
    elif bet_pot_ratio <= 0.67:
        size_adj = 0.0
    elif bet_pot_ratio <= 1.0:
        size_adj = +0.05
    else:
        size_adj = +0.08

    # AF adjustment — high AF = more betting = more bluffs
    eff_af = villain_af if villain_af > 0 else 1.5
    if eff_af > 3.0:
        af_adj = +0.12
    elif eff_af > 2.5:
        af_adj = +0.07
    elif eff_af < 0.8:
        af_adj = -0.08
    else:
        af_adj = 0.0

    return round(max(0.02, min(0.80, base + wtsd_adj + size_adj + af_adj)), 3)


# ── GTO indifference bluff frequency ─────────────────────────────────────────

def _gto_bluff_freq(call_bb: float, pot_bb: float) -> float:
    """Bluff frequency that makes hero indifferent (pot odds breakeven)."""
    return round(call_bb / (pot_bb + call_bb), 3)


# ── Exploitative threshold ────────────────────────────────────────────────────

def _exploitative_threshold(
    call_bb:      float,
    pot_bb:       float,
    bluff_freq:   float,
    gto_freq:     float,
    hero_equity:  float,
) -> float:
    """Adjusted equity threshold based on villain's bluff deviation."""
    base_threshold = call_bb / (pot_bb + call_bb)
    # If villain bluffs more than GTO → lower threshold (call wider)
    # If villain bluffs less than GTO → higher threshold (call tighter)
    bluff_deviation = bluff_freq - gto_freq
    adjustment = bluff_deviation * 0.50   # conservative 0.5 scaling
    return round(max(0.05, min(0.95, base_threshold - adjustment)), 3)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CallThresholdResult:
    # Pot context
    pot_bb:            float
    call_bb:           float
    bet_pot_ratio:     float
    street:            str

    # Equity
    hero_equity:       float
    pot_odds_threshold: float     # pure pot odds (no exploitation)
    estimated_bluff:   float      # villain's estimated bluff frequency
    gto_bluff:         float      # break-even bluff frequency
    exploitative_threshold: float # adjusted threshold

    # Decision
    should_call:       bool
    equity_margin:     float      # hero_equity - threshold (+ = call, - = fold)
    action:            str        # 'call'/'fold'/'marginal'
    action_zh:         str

    # Villain context
    villain_wtsd:      float
    villain_af:        float
    villain_hands:     int

    reasoning:         str
    tips:              List[str]
    summary_zh:        str


def analyze_call_threshold(
    pot_bb:       float,
    call_bb:      float,
    hero_equity:  float,
    street:       str   = 'river',
    villain_wtsd: float = -1.0,
    villain_af:   float = -1.0,
    villain_vpip: float = 0.28,
    villain_hands: int  = 0,
) -> CallThresholdResult:
    """
    Calculate exploitative call threshold based on villain's estimated bluff frequency.

    Args:
        pot_bb:       Pot before call in BB
        call_bb:      Amount to call in BB
        hero_equity:  Hero's MC equity (0-1)
        street:       'flop'/'turn'/'river'
        villain_wtsd: WTSD from HUD (-1=unknown)
        villain_af:   AF from HUD (-1=unknown)
        villain_vpip: VPIP from HUD
        villain_hands: HUD sample size
    """
    tips: List[str] = []

    bet_ratio  = round(call_bb / max(0.5, pot_bb), 3)
    bluff_est  = _estimate_bluff_freq(street, villain_wtsd, villain_af, bet_ratio)
    gto_bluff  = _gto_bluff_freq(call_bb, pot_bb)
    threshold  = _exploitative_threshold(call_bb, pot_bb, bluff_est, gto_bluff, hero_equity)
    pure_po    = call_bb / (pot_bb + call_bb)
    margin     = round(hero_equity - threshold, 3)
    should_call = margin >= 0

    if margin > 0.08:
        action, action_zh = 'call', '強勢跟注（有利可圖）'
    elif margin >= 0:
        action, action_zh = 'call', '跟注（達到門檻）'
    elif margin >= -0.04:
        action, action_zh = 'marginal', '邊緣決策（謹慎）'
    else:
        action, action_zh = 'fold', '棄牌（不足門檻）'

    eff_wtsd = villain_wtsd if villain_wtsd > 0 else 0.29

    # Tips
    if bluff_est > gto_bluff + 0.08:
        tips.append(f'對手詐唬頻率{bluff_est:.0%} > 均衡{gto_bluff:.0%}：廣泛跟注，他過度詐唬')
    elif bluff_est < gto_bluff - 0.08:
        tips.append(f'對手詐唬頻率{bluff_est:.0%} < 均衡{gto_bluff:.0%}：謹慎跟注，他下注偏向真實牌力')
    if eff_wtsd < 0.24 and street == 'river':
        tips.append('對手低WTSD（緊型）：河牌下注幾乎全是真實牌力，提高棄牌頻率')
    if eff_wtsd > 0.38 and street == 'river':
        tips.append('對手高WTSD（跟注站）：他也會詐唬河牌（有寬廣範圍），可稍廣跟注')
    if bet_ratio > 1.0:
        tips.append(f'超額注碼（{bet_ratio:.0%}pot）：極化範圍，用強牌跟注棄牌中等手牌')
    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），使用人口平均估算詐唬頻率')

    street_zh = {'flop': '翻牌', 'turn': '轉牌', 'river': '河牌', 'preflop': '翻前'}.get(street, street)
    reasoning = (
        f'{street_zh}：面對{bet_ratio:.0%}pot下注，底池賠率門檻={pure_po:.0%}，'
        f'估算對手詐唬頻率={bluff_est:.0%}（均衡={gto_bluff:.0%}），'
        f'剝削門檻={threshold:.0%}，英雄勝率={hero_equity:.0%} → {action_zh}'
    )

    diff_str  = f'+{margin:.0%}' if margin >= 0 else f'{margin:.0%}'
    summary_zh = (
        f'[跟注門檻] 需>{threshold:.0%} 你有{hero_equity:.0%}({diff_str}) → {action_zh}'
    )[:85]

    return CallThresholdResult(
        pot_bb               = pot_bb,
        call_bb              = call_bb,
        bet_pot_ratio        = bet_ratio,
        street               = street,
        hero_equity          = hero_equity,
        pot_odds_threshold   = round(pure_po, 3),
        estimated_bluff      = bluff_est,
        gto_bluff            = gto_bluff,
        exploitative_threshold = threshold,
        should_call          = should_call,
        equity_margin        = margin,
        action               = action,
        action_zh            = action_zh,
        villain_wtsd         = eff_wtsd,
        villain_af           = villain_af if villain_af > 0 else 1.5,
        villain_hands        = villain_hands,
        reasoning            = reasoning,
        tips                 = tips,
        summary_zh           = summary_zh,
    )


def call_threshold_summary(r: CallThresholdResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
