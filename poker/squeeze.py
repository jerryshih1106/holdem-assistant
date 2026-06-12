"""
Squeeze play analyzer — 計算擠注機會的頻率、底注與範圍建議。

情境：有人開牌 + 1 名以上跟注者，你從後手擠注。
死錢（dead money）越多、開牌者越弱的位置，擠注越有利。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SqueezeResult:
    should_squeeze:  bool
    squeeze_freq:    float        # 建議擠注頻率 (0-1)
    squeeze_size:    float        # 建議底注倍數（相對於開牌注）
    squeeze_size_bb: float        # 換算成 BB 數
    ev_estimate:     float        # 相對於跟注的 EV 估算（BB）
    reasoning:       str
    range_hint:      str          # 擠注範圍提示


# 各位置開牌範圍估算（用於死錢計算）
_OPENER_RANGE_PCT = {
    'UTG': 0.13, 'UTG1': 0.14, 'UTG2': 0.16,
    'LJ': 0.18, 'HJ': 0.22, 'CO': 0.27,
    'BTN': 0.42, 'SB': 0.35,
}

# 各位置跟注範圍估算（比開牌範圍窄）
_CALLER_RANGE_PCT = {
    'UTG': 0.07, 'UTG1': 0.08, 'UTG2': 0.09,
    'LJ': 0.10, 'HJ': 0.12, 'CO': 0.15,
    'BTN': 0.20, 'SB': 0.12, 'BB': 0.18,
}


def analyze_squeeze(
    hero_pos:        str,
    opener_pos:      str,
    num_callers:     int,
    open_size_bb:    float = 2.5,
    effective_stack: float = 100.0,
    hero_hand:       Optional[str] = None,
) -> SqueezeResult:
    """
    計算擠注機會的品質與建議。

    Args:
        hero_pos:        英雄座位 (BTN/CO/SB/BB...)
        opener_pos:      開牌者座位
        num_callers:     開牌後的跟注人數
        open_size_bb:    開牌注大小（BB）
        effective_stack: 有效籌碼（BB）
        hero_hand:       英雄手牌（用於精確範圍，可省略）
    """
    # ── 死錢計算 ────────────────────────────────────────────────
    dead_money = open_size_bb + num_callers * open_size_bb  # 底池現有
    # 加上盲注
    dead_money += 1.5  # SB + BB

    # ── 建議擠注尺寸 ─────────────────────────────────────────────
    # GTO 公式：3-4x 開牌注 + 1BB 每個跟注者
    min_size = open_size_bb * 3.0 + num_callers * 1.0
    max_size = open_size_bb * 4.5 + num_callers * 1.5
    recommended_size = (min_size + max_size) / 2

    # SPR 限制
    spr = effective_stack / (dead_money + recommended_size)
    if spr < 2:
        recommended_size = min(recommended_size, effective_stack * 0.35)

    # ── 擠注頻率（基準）────────────────────────────────────────
    opener_strength = _OPENER_RANGE_PCT.get(opener_pos, 0.25)
    hero_pos_weight = {
        'BTN': 1.2, 'CO': 1.1, 'SB': 0.9, 'BB': 1.0,
        'HJ': 0.95, 'LJ': 0.85, 'UTG2': 0.75, 'UTG1': 0.65, 'UTG': 0.55,
    }.get(hero_pos, 1.0)

    # 跟注者越多死錢越多，但也讓我們的折疊機率降低
    caller_bonus   = min(num_callers * 0.08, 0.20)
    folder_penalty = max(0, (num_callers - 2) * 0.05)  # 3+ 跟注者更難讓所有人 fold

    # 開牌者越弱（範圍越寬）越適合擠注
    opener_bonus = (0.42 - opener_strength) / 0.42 * 0.15

    base_freq = 0.12 + opener_bonus + caller_bonus - folder_penalty
    freq = min(0.85, max(0.05, base_freq * hero_pos_weight))

    # ── EV 估算（簡化：折疊機率 × 死錢）──────────────────────
    fold_prob = (1 - opener_strength) * (0.75 ** num_callers)
    ev_fold   = fold_prob * dead_money
    ev_call   = -recommended_size * 0.3  # 近似：跟注後不利
    ev_estimate = ev_fold + (1 - fold_prob) * ev_call

    should_squeeze = freq >= 0.15 and ev_estimate > 0

    # ── 理由說明 ─────────────────────────────────────────────
    reasons = []
    if dead_money >= 6:
        reasons.append(f'死錢多 ({dead_money:.1f}BB)')
    if opener_strength <= 0.20:
        reasons.append(f'開牌者範圍弱 ({opener_pos}={int(opener_strength*100)}%)')
    if num_callers >= 2:
        reasons.append(f'{num_callers} 個跟注者=更多死錢')
    if hero_pos in ('BTN', 'CO'):
        reasons.append('位置有利')
    if not reasons:
        reasons.append('擠注機會一般')

    reasoning = '；'.join(reasons)

    # ── 範圍提示 ─────────────────────────────────────────────
    if freq >= 0.35:
        range_hint = '寬範圍擠注：AA/KK/QQ/JJ/AKs/AKo + 詐唬料（A5s/A4s/KQs/89s）'
    elif freq >= 0.20:
        range_hint = '中等範圍：AA/KK/QQ/JJ/TT/AKs/AKo/AQs'
    else:
        range_hint = '窄範圍：AA/KK/QQ/AKs/AKo（接近純價值）'

    return SqueezeResult(
        should_squeeze  = should_squeeze,
        squeeze_freq    = round(freq, 3),
        squeeze_size    = round(recommended_size / open_size_bb, 2),
        squeeze_size_bb = round(recommended_size, 1),
        ev_estimate     = round(ev_estimate, 2),
        reasoning       = reasoning,
        range_hint      = range_hint,
    )


def squeeze_summary(result: SqueezeResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    if not result.should_squeeze:
        return f'擠注機會弱 ({int(result.squeeze_freq*100)}%)'
    return (f'擠注 {int(result.squeeze_freq*100)}%  '
            f'建議注碼 {result.squeeze_size_bb:.1f}BB  '
            f'EV+{result.ev_estimate:.1f}BB')
