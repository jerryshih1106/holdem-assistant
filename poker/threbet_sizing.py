"""
3-bet 注碼最優化器 (3-bet Raise Sizing Optimizer)

回答：「我要 3-bet 到多少？」

現有 threbet_bluff.py 決定是否 3-bet 以及手牌選擇，
本模組專門決定 3-bet 的確切注碼。

核心框架：
  基礎尺寸（無位置、無dead money）：
    IP（有位置）：開牌注 × 3.0
    OOP（無位置）：開牌注 × 3.5 + 1BB

  調整因素（每項加或減 BB）：
    1. Squeeze（dead money）：+1BB per cold caller
    2. 籌碼深度：200bb+ = +2BB，<50bb = 可考慮線性 push
    3. 對手 4-bet 頻率：>20% = -1BB（size down，保留 fold equity）
    4. vs 魚（VPIP>40%）：+1-2BB（他們傾向跟注，取值更大）
    5. 翻前位置修正：
       - BTN vs CO: 2.5x open × 3 = 7.5-8BB
       - BB vs BTN: 2.2x open × 3.5+1 = 8.7-9BB
       - CO vs UTG: 2.5x open × 3.5+1 = 9.75-10BB

為什麼不能一律用 3x：
  太小 = 對手 IP 可獲利跟注（pot odds 更好）
  太大 = 詐唬用 3-bet 風險太高，值得 fold 而非繼續詐唬計劃

GTO 研究摘要（基於 solver output）：
  IP 3-bet 平均:   2.8x - 3.2x 開牌注
  OOP 3-bet 平均:  3.3x - 4.0x 開牌注 + dead money
  Squeeze:         +1BB per caller
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class ThreeBetSizing:
    hero_pos:        str
    villain_pos:     str
    open_size_bb:    float
    stack_bb:        float
    n_dead_callers:  int       # dead callers between opener and hero
    is_value:        bool      # value hand (True) or bluff (False)

    # 建議尺寸
    recommended_bb:  float     # 建議 3-bet 到這麼多 BB
    min_bb:          float     # 合理範圍下限
    max_bb:          float     # 合理範圍上限
    size_x_open:     float     # 以開牌注的倍數表示 (e.g., 3.2)

    # 情境標籤
    is_squeeze:      bool      # 有 dead callers → squeeze 情境
    is_oop:          bool      # 英雄無位置
    sizing_style:    str       # 'standard'/'value_overbet'/'bluff_min'/'squeeze'/'linear_push'

    # 推理
    adjustments:     List[str]
    reasoning:       str
    tip:             str


# ── 各位置 IP/OOP 分類 ─────────────────────────────────────────────────────────

_IP_POSITIONS  = {'BTN', 'CO', 'HJ'}
_OOP_POSITIONS = {'SB', 'BB', 'UTG', 'UTG1', 'UTG2', 'LJ'}

_POS_ORDER = ['UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def _is_ip(hero_pos: str, villain_pos: str) -> bool:
    """判斷英雄是否有位置（翻後在後行動）。"""
    hp = hero_pos.upper()
    # BTN always last to act post-flop
    if hp == 'BTN':
        return True
    # SB/BB always OOP vs all non-blind positions
    if hp in ('SB', 'BB'):
        return False
    try:
        hi = _POS_ORDER.index(hp)
        vi = _POS_ORDER.index(villain_pos.upper())
        return hi > vi   # later in order = more IP
    except ValueError:
        return hp in _IP_POSITIONS


def _base_size(open_size_bb: float, is_oop: bool) -> float:
    """基礎 3-bet 尺寸（未調整）。"""
    if is_oop:
        return open_size_bb * 3.5 + 1.0
    else:
        return open_size_bb * 3.0


def recommend_3bet_size(
    hero_pos:        str,
    villain_pos:     str   = 'CO',
    open_size_bb:    float = 2.5,
    stack_bb:        float = 100.0,
    villain_4bet_pct: float = 0.08,   # 0-1：對手 4-bet 頻率
    villain_vpip:    float = 0.28,    # 0-1：對手 VPIP
    n_dead_callers:  int   = 0,       # dead callers（squeeze 用）
    is_value:        bool  = True,    # True=價值手，False=詐唬手
) -> ThreeBetSizing:
    """
    計算最優 3-bet 注碼。

    Args:
        hero_pos:         英雄位置
        villain_pos:      開牌者位置
        open_size_bb:     開牌者注碼（BB）
        stack_bb:         有效籌碼（BB）
        villain_4bet_pct: 對手面對 3-bet 的 4-bet 頻率（0-1）
        villain_vpip:     對手 VPIP（0-1）
        n_dead_callers:   介於開牌者和英雄之間的跟注者數
        is_value:         True=價值牌（AA/KK/QQ/AK等），False=詐唬
    """
    hero_pos    = hero_pos.upper()    if hero_pos    else 'BTN'
    villain_pos = villain_pos.upper() if villain_pos else 'CO'

    is_oop  = not _is_ip(hero_pos, villain_pos)
    is_sq   = n_dead_callers > 0

    base_bb = _base_size(open_size_bb, is_oop)
    adj     = 0.0
    adjustments: List[str] = []

    # ── 調整 1：Squeeze dead money ──────────────────────────────────────
    if n_dead_callers > 0:
        dead_adj = n_dead_callers * 1.0
        adj += dead_adj
        adjustments.append(f'{n_dead_callers}個dead money → +{dead_adj:.0f}BB（squeeze加大）')

    # ── 調整 2：籌碼深度 ──────────────────────────────────────────────
    if stack_bb >= 200:
        adj += 2.0
        adjustments.append(f'深籌碼 {stack_bb:.0f}bb → +2BB')
    elif stack_bb >= 150:
        adj += 1.0
        adjustments.append(f'深籌碼 {stack_bb:.0f}bb → +1BB')
    elif stack_bb <= 30:
        # 短籌碼：linear push 比 3-bet fold 更好
        adj -= 2.0
        adjustments.append(f'短籌碼 {stack_bb:.0f}bb → -2BB（考慮線性 push）')

    # ── 調整 3：對手 4-bet 頻率 ────────────────────────────────────────
    if villain_4bet_pct >= 0.20:
        adj -= 1.5
        adjustments.append(f'對手高4-bet率 {villain_4bet_pct:.0%} → -1.5BB（保留 fold equity）')
    elif villain_4bet_pct >= 0.14:
        adj -= 0.8
        adjustments.append(f'對手偏高4-bet率 {villain_4bet_pct:.0%} → -0.8BB')
    elif villain_4bet_pct <= 0.04:
        adj += 0.5
        adjustments.append(f'對手低4-bet率 {villain_4bet_pct:.0%} → +0.5BB（可加大詐唬）')

    # ── 調整 4：對手 VPIP（魚傾向跟注，取值加大）───────────────────────
    if villain_vpip >= 0.45 and is_value:
        adj += 2.0
        adjustments.append(f'魚（VPIP={villain_vpip:.0%}）傾向跟注 → +2BB 取值')
    elif villain_vpip >= 0.35 and is_value:
        adj += 1.0
        adjustments.append(f'鬆散（VPIP={villain_vpip:.0%}）→ +1BB 取值')

    # ── 調整 5：詐唬手用最小合理尺寸 ────────────────────────────────────
    if not is_value:
        adj -= 0.5
        adjustments.append('詐唬手 → -0.5BB（節省注碼，若被跟注仍可放棄）')

    # ── 計算最終尺寸 ──────────────────────────────────────────────────
    raw_bb = base_bb + adj

    # 不超過 50% 籌碼（否則可直接 push）
    max_allowed = min(stack_bb * 0.50, stack_bb - open_size_bb)
    rec_bb = round(max(open_size_bb * 2.2, min(raw_bb, max_allowed)), 1)

    # 合理範圍
    min_bb = round(max(open_size_bb * 2.2, rec_bb - 1.5), 1)
    max_bb = round(min(max_allowed, rec_bb + 1.5), 1)

    size_x = round(rec_bb / max(open_size_bb, 0.1), 2)

    # ── 尺寸風格 ─────────────────────────────────────────────────────
    if stack_bb <= 30:
        style = 'linear_push'
    elif is_sq:
        style = 'squeeze'
    elif not is_value and rec_bb <= base_bb - 1:
        style = 'bluff_min'
    elif is_value and villain_vpip >= 0.40:
        style = 'value_overbet'
    else:
        style = 'standard'

    reasoning = (
        f'{"OOP" if is_oop else "IP"} {hero_pos} vs {villain_pos}  '
        f'基礎 {base_bb:.1f}BB  調整 {adj:+.1f}BB  '
        f'→ 建議 {rec_bb}BB ({size_x:.1f}x 開注)'
    )

    tip = _get_tip(style, is_oop, villain_vpip, villain_4bet_pct, is_value, stack_bb)

    return ThreeBetSizing(
        hero_pos       = hero_pos,
        villain_pos    = villain_pos,
        open_size_bb   = open_size_bb,
        stack_bb       = stack_bb,
        n_dead_callers = n_dead_callers,
        is_value       = is_value,
        recommended_bb = rec_bb,
        min_bb         = min_bb,
        max_bb         = max_bb,
        size_x_open    = size_x,
        is_squeeze     = is_sq,
        is_oop         = is_oop,
        sizing_style   = style,
        adjustments    = adjustments,
        reasoning      = reasoning,
        tip            = tip,
    )


def _get_tip(style, is_oop, vpip, v4b, is_value, stack_bb) -> str:
    if style == 'linear_push':
        return f'短籌碼({stack_bb:.0f}bb)：考慮直接 all-in 而非 3-bet/fold'
    if style == 'squeeze':
        return 'Squeeze：dead money 在底池，加大尺寸讓跟注者折疊更困難'
    if style == 'value_overbet' and vpip >= 0.45:
        return '魚喜歡跟注：大注建鍋，翻後繼續大注取值'
    if style == 'bluff_min':
        return '詐唬 3-bet：最小合理尺寸，被跟注後保留放棄空間'
    if v4b >= 0.18:
        return f'對手 4-bet 率高({v4b:.0%})：縮小尺寸，避免大賠小賺的不對稱風險'
    if is_oop:
        return 'OOP 3-bet 需要大一些補償無位置劣勢，確保翻後計劃明確'
    return f'{"取值" if is_value else "詐唬"} 3-bet 標準尺寸，根據對手反應調整頻率'


def threbet_sizing_summary(r: ThreeBetSizing) -> str:
    """單行 overlay 摘要。"""
    sq_tag = f'+{r.n_dead_callers}dead ' if r.is_squeeze else ''
    style_tag = {'squeeze': 'Squeeze', 'linear_push': 'Push?',
                 'value_overbet': '大注取值', 'bluff_min': '詐唬省',
                 'standard': '標準'}.get(r.sizing_style, '')
    return (f'[3-bet] {sq_tag}{style_tag} → {r.recommended_bb}BB '
            f'({r.min_bb}-{r.max_bb}BB)  {r.size_x_open:.1f}x開注')
