"""
3-bet 尺寸計算器 (3-Bet Sizing Calculator)

3-bet 尺寸的核心原則：
  - IP（有位置）：2.5-3x 開注尺寸（+跟注者每人 +1bb）
  - OOP（無位置）：3-4x 開注尺寸（+跟注者每人 +1bb）
  - 淺籌碼（SPR低）：縮小尺寸，保留更多有效籌碼比例
  - 深籌碼（SPR高）：可以更大以保護手牌/建築底池

為什麼尺寸很重要：
  - 太小：對手有利賠率跟注，更多手牌進入翻牌
  - 太大：只有極強手牌跟注，本身成為整合
  - 正確尺寸：讓對手在跟注時沒有賠率，或強迫棄牌

計算公式：
  base_3bet = open_size × multiplier
  for each caller between open and hero: base_3bet += 1  (BB)
  final = round to nearest 0.5 BB

線性 3-bet（有實力）vs 極化 3-bet（強牌+詐唬）：
  線性：用於 IP + 對手 VPIP 高（他跟注太多）
  極化：用於 OOP 或對手是緊型（不想被跟注的手牌用來詐唬）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# ── Multiplier tables ─────────────────────────────────────────────────────────

# (is_ip, stack_depth) → base multiplier
def _base_multiplier(is_ip: bool, open_size_bb: float, stack_bb: float) -> float:
    """Base 3-bet multiplier based on position and stack depth."""
    spr_pre = stack_bb / max(1.0, open_size_bb)

    if is_ip:
        if spr_pre < 15:   return 2.3    # short stack: smaller 3bet
        if spr_pre < 25:   return 2.5
        if spr_pre < 50:   return 2.8
        return 3.0                        # deep: slightly larger
    else:  # OOP
        if spr_pre < 15:   return 2.8
        if spr_pre < 25:   return 3.0
        if spr_pre < 50:   return 3.3
        return 3.8                        # deep OOP: larger to compensate


# ── Strategy classification ───────────────────────────────────────────────────

def _strategy_type(
    hero_hand_pct: float,
    is_ip:         bool,
    villain_vpip:  float,
) -> str:
    """Linear vs polarized 3-bet strategy."""
    if is_ip and villain_vpip > 0.38:
        return 'linear'      # IP vs fish/LAG: linear (good hands+medium)
    if hero_hand_pct >= 0.90 or hero_hand_pct <= 0.12:
        return 'polarized'   # strong hand or bluff: polarized
    if not is_ip:
        return 'polarized'   # OOP: prefer polarized (protect range)
    return 'linear'


_STRATEGY_ZH = {
    'linear':    '線性 3-bet（中強牌範圍）',
    'polarized': '極化 3-bet（超強牌+詐唬）',
}


# ── Squeeze adjustment ────────────────────────────────────────────────────────

def _squeeze_multiplier(n_callers: int, open_size_bb: float) -> float:
    """Extra BB to add per limper/caller between open and hero."""
    return n_callers * 1.0


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ThreeBetSizingResult:
    # Sizing
    recommended_size_bb:  float
    min_size_bb:          float
    max_size_bb:          float

    # Context
    open_size_bb:         float
    n_callers:            int       # callers between open and hero
    is_ip:                bool
    stack_bb:             float
    multiplier:           float

    # Strategy
    strategy_type:        str       # 'linear'/'polarized'
    strategy_zh:          str
    hero_hand_pct:        float

    # Villain context
    villain_vpip:         float
    villain_hands:        int

    # SPR after 3-bet call
    spr_if_called:        float     # stack remaining / pot if villain calls

    reasoning:            str
    tips:                 List[str]
    summary_zh:           str


def analyze_threebet_sizing(
    open_size_bb:  float,
    hero_hand_pct: float = 0.85,
    is_ip:         bool  = True,
    n_callers:     int   = 0,
    stack_bb:      float = 100.0,
    villain_vpip:  float = 0.28,
    villain_hands: int   = 0,
    hero_pos:      str   = 'BTN',
) -> ThreeBetSizingResult:
    """
    Calculate optimal 3-bet sizing.

    Args:
        open_size_bb:  Villain's open raise size in BB
        hero_hand_pct: Hero's hand percentile (0-1)
        is_ip:         True if hero is in position after 3-bet
        n_callers:     Number of callers between open and hero
        stack_bb:      Effective stack (before any bets) in BB
        villain_vpip:  Villain VPIP from HUD
        villain_hands: HUD sample size
        hero_pos:      Hero's position string
    """
    tips: List[str] = []

    mult     = _base_multiplier(is_ip, open_size_bb, stack_bb)
    squeeze  = _squeeze_multiplier(n_callers, open_size_bb)
    raw_size = open_size_bb * mult + squeeze

    # Round to nearest 0.5 BB
    rec_size = round(raw_size * 2) / 2

    # Bounds
    min_size = open_size_bb * (mult - 0.3) + squeeze
    max_size = open_size_bb * (mult + 0.5) + squeeze

    # SPR if villain calls 3-bet
    pot_if_called = rec_size + open_size_bb + n_callers * open_size_bb + 0.5
    remain_stack  = stack_bb - rec_size
    spr_if_called = round(remain_stack / max(0.5, pot_if_called), 2)

    strategy = _strategy_type(hero_hand_pct, is_ip, villain_vpip)
    strategy_zh = _STRATEGY_ZH.get(strategy, strategy)

    # Tips
    if open_size_bb >= 4.0:
        tips.append(f'對手開注 {open_size_bb:.1f}BB（偏大），3-bet 尺寸自動增大')
    if n_callers >= 2:
        tips.append(f'有 {n_callers} 名跟注者：擠壓下注 +{n_callers:.0f}BB，只用強牌')
    if spr_if_called < 3:
        tips.append(f'跟注後 SPR={spr_if_called:.1f}（超低），翻牌自動全押')
    elif spr_if_called > 10:
        tips.append(f'跟注後 SPR={spr_if_called:.1f}（高），翻牌仍有深度決策空間')
    if villain_vpip > 0.40 and is_ip:
        tips.append('vs 魚（VPIP>40%）：線性 3-bet 用更多優質手牌，不用純詐唬')
    if villain_vpip < 0.20 and not is_ip:
        tips.append('vs 緊型 OOP：極化 3-bet，超強牌下注，中等牌跟注')
    if rec_size > stack_bb * 0.35:
        tips.append(f'3-bet 占籌碼 {rec_size/stack_bb:.0%}（偏高），考慮縮小或直接全押')
    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），以標準尺寸為準')

    pos_str   = 'IP（有位置）' if is_ip else 'OOP（無位置）'
    caller_str = f', 另有{n_callers}名跟注者' if n_callers else ''
    reasoning = (
        f'翻前{pos_str}，對手開注={open_size_bb:.1f}BB{caller_str}，'
        f'3-bet倍數={mult:.1f}x，建議={rec_size:.1f}BB（{min_size:.1f}-{max_size:.1f}BB）。'
        f'跟注後SPR={spr_if_called:.1f}。策略={strategy_zh}'
    )

    summary_zh = f'[3-bet尺寸] {rec_size:.1f}BB ({mult:.1f}x) {pos_str[:6]}'[:85]

    return ThreeBetSizingResult(
        recommended_size_bb = rec_size,
        min_size_bb         = round(min_size * 2) / 2,
        max_size_bb         = round(max_size * 2) / 2,
        open_size_bb        = open_size_bb,
        n_callers           = n_callers,
        is_ip               = is_ip,
        stack_bb            = stack_bb,
        multiplier          = mult,
        strategy_type       = strategy,
        strategy_zh         = strategy_zh,
        hero_hand_pct       = hero_hand_pct,
        villain_vpip        = villain_vpip,
        villain_hands       = villain_hands,
        spr_if_called       = spr_if_called,
        reasoning           = reasoning,
        tips                = tips,
        summary_zh          = summary_zh,
    )


def threebet_sizing_summary(r: ThreeBetSizingResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
