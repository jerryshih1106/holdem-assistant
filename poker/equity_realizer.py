"""
勝率實現調整器 (Equity Realization Adjuster)

核心問題：「顯示的勝率 47% 代表我實際能贏多少？」

原始蒙特卡羅勝率 ≠ 實際實現勝率：
  - 有位置（IP）手牌比無位置（OOP）實現更多勝率（翻後主動權）
  - 有牌路的手牌（如中對子）遇到大壓力時常被迫棄牌，實現率低
  - 強聽牌（同花聽牌、OESD）即使未完成也能取得部分 EV（詐唬/保護注）
  - 多人底池大幅降低任何手牌的勝率實現
  - 籌碼/底池比（SPR）低時實現率高（已承諾底池），高時低（有更多棄牌壓力）

勝率實現係數（ER）：
  調整後勝率 = 原始勝率 × ER 係數
  ER 係數 = position_factor × hand_factor × board_factor × spr_factor × multiway_factor

位置係數（position_factor）：
  IP（有位置）:  1.05   翻後可最後行動，額外信息優勢
  OOP（無位置）: 0.91   需要面對額外下注壓力

手牌係數（hand_factor）：
  超強牌（組合/葫蘆+）: 1.10  可全力提取三街價值
  強牌（頂對強踢/暗三）: 1.00  標準實現
  中等牌（頂對弱踢/中對）: 0.92  常被大注壓下
  強聽牌（同花聽牌/OESD）: 0.90  命中時取值，未命中時被棄
  弱牌（底對/高牌）: 0.80  高 SPR 下常被迫棄牌

牌面係數（board_factor）：
  乾燥牌面: 1.03    牌型穩定，較好實現
  標準牌面: 1.00
  濕潤牌面: 0.95    更多聽牌威脅，實現率下降

SPR 係數（spr_factor）：
  SPR < 3（承諾）: 1.02  幾乎全額實現
  SPR 3-8（中等）: 0.97
  SPR > 8（深籌）: 0.93  更多街道決策，實現難度更高

多人係數（multiway_factor）：
  單挑:    1.00
  三人底池: 0.85  額外對手增加面對強牌機率
  四人+底池: 0.75
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EquityRealizationResult:
    raw_equity:        float
    realized_equity:   float
    er_factor:         float

    position_factor:   float
    hand_factor:       float
    board_factor:      float
    spr_factor:        float
    multiway_factor:   float

    position_label:    str
    hand_category:     str
    board_texture:     str
    adjustments_zh:    List[str]

    equity_delta:      float
    summary_zh:        str


# ─── 分類函數 ─────────────────────────────────────────────────────────────────

def _classify_hand(
    hand_category: str,     # from hand_strength.py category_zh or hand_percentile
    equity: float,
    has_draw: bool = False,
) -> tuple:
    """Return (hand_factor, hand_cat_en)."""
    cat = hand_category.lower() if hand_category else ''

    if any(k in cat for k in ('怪獸', '超強', '順子', '同花', '葫蘆', 'full', 'quads', 'straight flush')):
        return 1.10, 'monster'
    if has_draw and any(k in cat for k in ('聽牌', 'draw', 'flush', 'oesd', '邊緣')):
        return 0.90, 'draw'
    if any(k in cat for k in ('強牌', 'strong', '頂對', 'top pair', 'tptk', '暗三', 'set')):
        return 1.00, 'strong'
    if any(k in cat for k in ('中等', 'medium', '中對', '二對', 'two pair', '弱踢', 'weak kicker')):
        return 0.92, 'medium'
    if any(k in cat for k in ('弱牌', 'weak', '底對', '高牌', 'overcards')):
        return 0.80, 'weak'

    # Fallback: use equity thresholds
    if equity >= 0.80:
        return 1.05, 'strong'
    if equity >= 0.55:
        return 0.97, 'medium'
    if equity >= 0.35:
        return 0.90, 'draw'
    return 0.82, 'weak'


def _classify_board(board_texture: str) -> tuple:
    """Return (board_factor, board_label)."""
    b = board_texture.lower() if board_texture else ''
    if any(k in b for k in ('dry', '乾燥', 'paired', '配對', '彩虹')):
        return 1.03, 'dry'
    if any(k in b for k in ('wet', '濕潤', 'monotone', '單色', 'connected', '連張', 'flush')):
        return 0.95, 'wet'
    return 1.00, 'standard'


# ─── 公共 API ─────────────────────────────────────────────────────────────────

def calculate_equity_realization(
    raw_equity:     float,
    is_ip:          bool    = True,
    hand_category:  str     = '',    # from hand_strength.py or hand_percentile
    board_texture:  str     = '',    # from board_texture.py texture_label
    spr:            float   = 6.0,
    n_opponents:    int     = 1,
    has_draw:       bool    = False,
) -> EquityRealizationResult:
    """
    Adjust raw Monte Carlo equity for real-world equity realization.

    Args:
        raw_equity:    Win probability from Monte Carlo simulation (0-1)
        is_ip:         True if hero has position (acts after villain postflop)
        hand_category: Hand strength description string (Chinese or English)
        board_texture: Board texture label (dry/wet/monotone etc.)
        spr:           Stack-to-pot ratio
        n_opponents:   Number of active opponents
        has_draw:      True if hero has a significant draw component
    """
    adjustments: list = []

    # ── Position factor ────────────────────────────────────────────────────────
    if is_ip:
        pos_factor  = 1.05
        pos_label   = 'IP（有位置）'
        adjustments.append('有位置 +5%')
    else:
        pos_factor  = 0.91
        pos_label   = 'OOP（無位置）'
        adjustments.append('無位置 -9%')

    # ── Hand factor ────────────────────────────────────────────────────────────
    hand_factor, hand_cat = _classify_hand(hand_category, raw_equity, has_draw)
    _hand_delta_pct = round((hand_factor - 1.0) * 100)
    if _hand_delta_pct != 0:
        sign = '+' if _hand_delta_pct > 0 else ''
        adjustments.append(f'牌型({hand_cat}) {sign}{_hand_delta_pct}%')

    # ── Board factor ───────────────────────────────────────────────────────────
    board_factor, board_label = _classify_board(board_texture)
    _board_delta_pct = round((board_factor - 1.0) * 100)
    if _board_delta_pct != 0:
        sign = '+' if _board_delta_pct > 0 else ''
        adjustments.append(f'牌面({board_label}) {sign}{_board_delta_pct}%')

    # ── SPR factor ─────────────────────────────────────────────────────────────
    if spr < 3:
        spr_factor = 1.02
        adjustments.append('SPR<3(已承諾) +2%')
    elif spr <= 8:
        spr_factor = 0.97
        adjustments.append('SPR中等 -3%')
    else:
        spr_factor = 0.93
        adjustments.append('SPR高(深籌) -7%')

    # ── Multiway factor ────────────────────────────────────────────────────────
    if n_opponents >= 3:
        mw_factor = 0.75
        adjustments.append('四人+底池 -25%')
    elif n_opponents == 2:
        mw_factor = 0.85
        adjustments.append('三人底池 -15%')
    else:
        mw_factor = 1.00

    # ── Composite ER ──────────────────────────────────────────────────────────
    er_factor = pos_factor * hand_factor * board_factor * spr_factor * mw_factor
    er_factor = round(er_factor, 3)

    realized = round(min(0.99, max(0.01, raw_equity * er_factor)), 3)
    delta    = round(realized - raw_equity, 3)

    # ── Summary line ──────────────────────────────────────────────────────────
    delta_pct = round(delta * 100, 1)
    sign = '+' if delta_pct >= 0 else ''
    adj_parts = '+'.join(
        p.split(' ')[0] for p in adjustments[:3]   # first 3 adjustments
    )
    summary_zh = (
        f'[實現勝率] {realized:.0%}（{sign}{delta_pct:.0f}%  {adj_parts}）'
    )[:80]

    return EquityRealizationResult(
        raw_equity       = round(raw_equity, 3),
        realized_equity  = realized,
        er_factor        = er_factor,
        position_factor  = pos_factor,
        hand_factor      = hand_factor,
        board_factor     = board_factor,
        spr_factor       = spr_factor,
        multiway_factor  = mw_factor,
        position_label   = pos_label,
        hand_category    = hand_cat,
        board_texture    = board_label,
        adjustments_zh   = adjustments,
        equity_delta     = delta,
        summary_zh       = summary_zh,
    )


def equity_realization_summary(r: EquityRealizationResult) -> str:
    """Single-line overlay display (≤80 chars)."""
    return r.summary_zh
