"""
頻繁 3-bet 對手調整顧問 (Vs Frequent 3-Bettor Adjustment)

問題：preflop_advisor.py 假設對手的 3-bet 頻率是正常的 ~6%。
但當面對一個 3-bet 頻率 12-15% 的對手時，英雄的開牌策略需要根本性調整：

當對手 3-bet 頻率增加時：
  每次開牌被 3-bet 的機率更高 → 開牌的 EV 下降
  需要：
  1. 縮窄開牌範圍（只開期望值為正的手牌）
  2. 降低 4-bet 取值門檻（JJ+ 代替 QQ+）
  3. 加入更多 4-bet 詐唬（以 AXs/KQs 型手牌平衡）
  4. IP 時跟注 3-bet 範圍更寬（更有利的位置賠率）
  5. OOP 時跟注 3-bet 更謹慎（位置劣勢 × 被 3-bet 損失 EV）

3-bet 頻率調整表（翻前開牌範圍 & 反應建議）：
  3Bet% ≤ 6%  → 正常打法（preflop_advisor.py 標準）
  3Bet% 7-9%  → 縮窄開牌5%，4-bet價值 QQ+/AK
  3Bet% 10-12% → 縮窄開牌12%，4-bet價值 JJ+/AK，開始加入4-bet詐唬
  3Bet% 13-16% → 縮窄開牌20%，4-bet價值 TT+/AQs+，更多4-bet詐唬
  3Bet% > 16%  → 開牌極度收緊，但也更激進地 4-bet（不能只折疊）

4-Bet 策略：
  當對手 3-bet 頻繁時，他們的 3-bet 範圍寬 → 他們對 4-bet 的回應更弱
  → 4-bet EV 更高（更多人折疊）
  → 4-bet bluff 頻率提高（AXs/KQs 型）

跟注 3-bet 調整：
  IP：可以跟注到 65th pct（TT、AJs、KQs 等）
  OOP：只跟注到 75th pct（JJ+、AQs+）
  對手 3-bet% > 12%：兩者都降低5-8%（對手range更廣→你的勝率相對更高）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple


# ── Opening range tightening by villain 3-bet % ───────────────────────────────
# Returns: (open_tighten_pct, four_bet_value_thresh, call_3bet_ip_thresh, call_3bet_oop_thresh)
def _3bet_adjustment_params(v_3bet: float) -> Tuple[float, float, float, float]:
    """
    v_3bet: villain's 3-bet fraction (e.g. 0.09 = 9%)
    Returns:
        open_tighten: how much to tighten opening range (fraction of normal range)
        fb_value_thresh: min hero hand pct for 4-bet value
        call_3b_ip_thresh: min hero hand pct to call 3-bet IP
        call_3b_oop_thresh: min hero hand pct to call 3-bet OOP
    """
    if v_3bet <= 0.06:
        return 0.00,  0.78, 0.65, 0.75   # normal: QQ+/AK for value; TT+ IP
    if v_3bet <= 0.09:
        return 0.05,  0.76, 0.63, 0.74   # slight tighten: QQ+
    if v_3bet <= 0.12:
        return 0.12,  0.72, 0.60, 0.72   # JJ+/AK for value
    if v_3bet <= 0.16:
        return 0.20,  0.68, 0.57, 0.70   # TT+/AQs for value
    # >16%: extreme 3-bettor → very tight open but fight back hard
    return 0.28,      0.63, 0.53, 0.67


def _four_bet_bluff_freq(v_3bet: float, hero_pos: str) -> float:
    """How often hero should include 4-bet bluffs in response."""
    # As villain 3-bets more, their fold to 4-bet rate is higher → 4-bet bluff more profitable
    base = {
        'BTN': 0.20, 'CO': 0.18, 'HJ': 0.15, 'UTG': 0.10,
        'SB': 0.22, 'BB': 0.12,
    }.get(hero_pos, 0.16)
    # Scale by how much villain over-3-bets above normal 6%
    scale = min(2.0, max(1.0, v_3bet / 0.06))
    return round(min(0.35, base * scale), 3)


def _estimated_villain_fold_to_4bet(v_3bet: float, villain_vpip: float) -> float:
    """
    Estimate how often villain folds to 4-bet.
    High 3-bet% usually means they bluff 3-bet frequently → fold more to 4-bet.
    Low VPIP villain who 3-bets: very strong → fold less.
    """
    # Baseline: most 3-bet ranges fold ~55% to 4-bet
    base_fold = 0.55
    # High 3-bet% implies more bluffs → more folds to 4-bet
    bluff_adj = (v_3bet - 0.06) * 2.0   # +14% fold at 3bet=13%
    # High VPIP villain → looser range → slightly less folding to 4-bet
    vpip_adj = -(villain_vpip - 0.28) * 0.3
    return round(min(0.85, max(0.30, base_fold + bluff_adj + vpip_adj)), 3)


def _ev_open_tighten(
    normal_ev_bb: float, tighten_pct: float, v_3bet: float,
    stack_bb: float, hero_pos: str
) -> float:
    """
    Estimate EV improvement from tightening opening range.
    Removes marginal hands that are unprofitable against frequent 3-bettor.
    """
    # Simplified: each percentage point of range tightened removes hands with ~-0.1BB EV
    marginal_hand_ev = -0.08    # typical marginal open vs freq 3-bettor
    return round(tighten_pct * marginal_hand_ev * 0.8, 2)


@dataclass
class AggressorAdjustResult:
    # Input context
    villain_3bet_pct:      float
    villain_vpip:          float
    villain_fold_to_4bet:  float   # estimated
    hero_position:         str

    # Adjusted opening strategy
    open_tighten_pct:      float   # how much to narrow opening range
    adjusted_open_label:   str     # e.g. "縮窄至原本80%"

    # 4-bet strategy
    fourbet_value_thresh:  float   # min hand_pct to 4-bet for value
    fourbet_bluff_freq:    float   # frequency to include 4-bet bluffs
    fourbet_size_bb:       float   # recommended 4-bet size

    # Call 3-bet strategy
    call_3bet_ip_thresh:   float   # min hand_pct to call 3-bet IP
    call_3bet_oop_thresh:  float   # min hand_pct to call 3-bet OOP

    # Hero current hand assessment
    hero_hand_pct:         float
    hero_should_4bet:      bool
    hero_should_call_3bet: bool    # depends on position
    hero_is_ip:            bool

    # EV estimates
    ev_tighten_gain:       float   # EV improvement from tightening (per hand)

    # Villain category
    aggressor_level:       str     # 'normal'/'slightly_aggro'/'aggro'/'very_aggro'/'maniac_3better'
    aggressor_level_zh:    str

    reasoning:             str
    tips:                  List[str]
    summary_zh:            str


def analyze_aggressor_adjust(
    villain_3bet_pct:  float,    # villain's 3-bet fraction (e.g. 0.10 = 10%)
    hero_position:     str = 'BTN',
    hero_hand_pct:     float = 0.65,
    hero_is_ip:        bool  = True,
    villain_vpip:      float = 0.28,
    villain_hands:     int   = 0,
    stack_bb:          float = 100.0,
    threebet_size_bb:  float = 9.0,    # villain's 3-bet size
) -> AggressorAdjustResult:
    """
    Advise hero on how to adjust preflop strategy vs frequent 3-bettor.

    Args:
        villain_3bet_pct: Villain's 3-bet fraction (0.10 = 10%)
        hero_position:    Hero's position ('BTN'/'CO'/'HJ'/'UTG'/'SB'/'BB')
        hero_hand_pct:    Hero's hand percentile (0-1)
        hero_is_ip:       True if hero is IP vs villain in the hand
        villain_vpip:     Villain's VPIP
        villain_hands:    HUD sample size
        stack_bb:         Effective stack in BB
        threebet_size_bb: Villain's 3-bet size in BB
    """
    tips: List[str] = []
    v3 = villain_3bet_pct

    # ── Adjustment parameters ──────────────────────────────────────────────────
    tighten, fb_val_thresh, call_ip, call_oop = _3bet_adjustment_params(v3)
    fb_bluff_freq = _four_bet_bluff_freq(v3, hero_position)
    fold_4bet     = _estimated_villain_fold_to_4bet(v3, villain_vpip)

    # Adjusted labels
    if tighten == 0:
        open_label = '正常開牌範圍（無需調整）'
    else:
        open_label = f'縮窄至原本{100-int(tighten*100)}%（移除低EV邊緣手牌）'

    # 4-bet sizing: typically 2.2-2.5× villain's 3-bet
    fb_size = round(threebet_size_bb * 2.35, 1)

    # ── Hero hand assessment ───────────────────────────────────────────────────
    hero_should_4bet = hero_hand_pct >= fb_val_thresh
    call_thresh = call_ip if hero_is_ip else call_oop
    hero_should_call_3bet = (not hero_should_4bet and hero_hand_pct >= call_thresh)

    # ── Aggressor classification ───────────────────────────────────────────────
    if v3 <= 0.06:
        aggr_level = 'normal';        aggr_zh = '正常3-bet頻率（≤6%）'
    elif v3 <= 0.09:
        aggr_level = 'slightly_aggro'; aggr_zh = '略微激進3-bet（7-9%）'
    elif v3 <= 0.12:
        aggr_level = 'aggro';         aggr_zh = '激進3-better（10-12%）'
    elif v3 <= 0.16:
        aggr_level = 'very_aggro';    aggr_zh = '高頻3-better（13-16%）'
    else:
        aggr_level = 'maniac_3better'; aggr_zh = 'Maniac 3-better（>16%）'

    # ── EV estimate ───────────────────────────────────────────────────────────
    ev_gain = _ev_open_tighten(0.3, tighten, v3, stack_bb, hero_position)

    # ── Tips ──────────────────────────────────────────────────────────────────
    if v3 > 0.09:
        tips.append(
            f'對手3-bet={v3:.0%}（對{hero_position}的正常3-bet是~6%），'
            f'他的3-bet range更廣→你的4-bet EV提高'
        )
    if fold_4bet >= 0.65:
        tips.append(
            f'估算對手面對4-bet棄牌={fold_4bet:.0%}，4-bet bluff {fb_bluff_freq:.0%}頻率是有利的'
        )
    if not hero_is_ip:
        tips.append('你在OOP位置：面對3-bet的跟注範圍更嚴格，傾向4-bet或棄牌，避免OOP跟注')
    if v3 > 0.14 and tighten > 0.18:
        tips.append(
            f'對手3-bet>14%：不要只棄牌！縮窄開牌同時增加4-bet反擊，讓他知道你會反擊'
        )
    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），3-bet%={v3:.0%}可能不準確，先觀察')
    if v3 > 0.06:
        bluff_hands = '（建議：AXs/KQs/JTs型的4-bet詐唬）'
        tips.append(
            f'4-bet bluff頻率={fb_bluff_freq:.0%} {bluff_hands}'
        )

    # ── Hero hand action ──────────────────────────────────────────────────────
    if hero_should_4bet:
        action_str = f'4-bet取值（手牌{hero_hand_pct:.0%} >= 調整後門檻{fb_val_thresh:.0%}）'
    elif hero_should_call_3bet:
        pos_label = 'IP' if hero_is_ip else 'OOP'
        action_str = (
            f'{pos_label}跟注3-bet（手牌{hero_hand_pct:.0%} >= {pos_label}跟注門檻{call_thresh:.0%}）'
        )
    else:
        action_str = (
            f'棄牌或4-bet詐唬（手牌{hero_hand_pct:.0%} < 跟注門檻{call_thresh:.0%}）'
        )

    # ── Reasoning ─────────────────────────────────────────────────────────────
    if fb_val_thresh >= 0.76:
        val_range_label = 'QQ+/AK'
    elif fb_val_thresh >= 0.70:
        val_range_label = 'JJ+/AK'
    else:
        val_range_label = 'TT+/AQs+'
    reasoning = (
        f'對手{aggr_zh}，估算4-bet棄牌率={fold_4bet:.0%}，'
        f'建議：{open_label}；4-bet取值門檻={fb_val_thresh:.0%}（{val_range_label}）；'
        f'4-bet詐唬={fb_bluff_freq:.0%}頻率；'
        f'跟注3-bet：IP>={call_ip:.0%}/OOP>={call_oop:.0%}。'
        f'英雄手牌{hero_hand_pct:.0%}→{action_str}'
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    summary_zh = f'[3bet應對] {aggr_zh} {action_str}'[:85]

    return AggressorAdjustResult(
        villain_3bet_pct      = v3,
        villain_vpip          = villain_vpip,
        villain_fold_to_4bet  = fold_4bet,
        hero_position         = hero_position,
        open_tighten_pct      = tighten,
        adjusted_open_label   = open_label,
        fourbet_value_thresh  = fb_val_thresh,
        fourbet_bluff_freq    = fb_bluff_freq,
        fourbet_size_bb       = fb_size,
        call_3bet_ip_thresh   = call_ip,
        call_3bet_oop_thresh  = call_oop,
        hero_hand_pct         = hero_hand_pct,
        hero_should_4bet      = hero_should_4bet,
        hero_should_call_3bet = hero_should_call_3bet,
        hero_is_ip            = hero_is_ip,
        ev_tighten_gain       = ev_gain,
        aggressor_level       = aggr_level,
        aggressor_level_zh    = aggr_zh,
        reasoning             = reasoning,
        tips                  = tips,
        summary_zh            = summary_zh,
    )


def aggressor_summary(r: AggressorAdjustResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
