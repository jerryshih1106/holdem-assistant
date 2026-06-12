"""
注碼 EV 比較器 (Bet Sizing EV Optimizer)

核心問題：「我應該用 33% 還是 75% pot 下注？哪個 EV 最高？」

計算公式（每個注碼方案）：
  EV(bet b into pot P) =
      f(b) × P                              # 對手棄牌，贏得底池
    + (1-f(b)) × [eq × (P + 2b) - b]       # 對手跟注，攤牌勝率 × 總籌碼 - 我們的注碼

  其中 f(b) = 折疊頻率（注碼越大，折疊越多）
  vs EV(check) = eq × P（簡化：不考慮後續行動）

可玩性說明：
  - f(b) 依注碼大小調整：小注(33%)折疊偏少，大注(100%)折疊偏多
  - 近似公式：f(b) ≈ base_fold × size_multiplier(b/P)
  - base_fold 從 HUD FCbet 推算

EV 損失：
  若目前下注尺寸偏離最佳尺寸，每 100 手損失估算 BB/100
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SizingEV:
    label:          str     # '33% 底池' / '75% 底池' 等
    pct:            float   # 相對底池 (0.33 = 33%)
    bet_bb:         float   # 注碼 BB 數
    fold_freq:      float   # 預計折疊頻率
    ev_bb:          float   # EV（BB）
    ev_vs_check:    float   # 相比過牌的 EV 增益
    is_optimal:     bool    # 是否為最佳尺寸
    note:           str     # 簡短說明


@dataclass
class SizingEVResult:
    pot_bb:         float
    hero_equity:    float
    base_fold_freq: float      # villain 的基礎折疊頻率（from HUD）
    street:         str
    options:        List[SizingEV]
    optimal:        SizingEV   # 最佳方案
    check_ev:       float      # 過牌的 EV 基準
    ev_loss_from_check: float  # 如果過牌損失多少 EV
    summary:        str


# 不同注碼下折疊頻率的調整倍數（相對於 50% pot 基準）
# 來源：簡化的 GTO solver 觀察值
_FOLD_MULTIPLIER = {
    0.25: 0.78,   # 25% pot — 對手較少折疊
    0.33: 0.85,
    0.50: 1.00,   # 基準
    0.67: 1.10,
    0.75: 1.15,
    1.00: 1.28,
    1.25: 1.38,
    1.50: 1.48,
    2.00: 1.62,
}

# 可選注碼方案（pct, label）
_SIZES = [
    (0.33, '33%'),
    (0.50, '50%'),
    (0.67, '67%'),
    (0.75, '75%'),
    (1.00, '100%'),
    (1.50, '150%'),
]


def _fold_multiplier(bet_pct: float) -> float:
    """插值計算折疊倍數。"""
    keys = sorted(_FOLD_MULTIPLIER.keys())
    if bet_pct <= keys[0]:
        return _FOLD_MULTIPLIER[keys[0]]
    if bet_pct >= keys[-1]:
        return _FOLD_MULTIPLIER[keys[-1]]
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= bet_pct <= hi:
            t = (bet_pct - lo) / (hi - lo)
            return _FOLD_MULTIPLIER[lo] * (1 - t) + _FOLD_MULTIPLIER[hi] * t
    return 1.0


def _ev_for_size(
    bet_pct:        float,
    pot_bb:         float,
    hero_equity:    float,
    base_fold_freq: float,
) -> tuple:
    """
    計算特定注碼的 EV。
    回傳 (ev_bb, fold_freq)。
    """
    bet_bb    = bet_pct * pot_bb
    fold_freq = min(0.95, base_fold_freq * _fold_multiplier(bet_pct))

    # EV = fold × (win pot) + call × (equity × total pot − bet)
    ev_fold   = fold_freq * pot_bb
    ev_call   = (1 - fold_freq) * (hero_equity * (pot_bb + 2 * bet_bb) - bet_bb)
    ev_total  = ev_fold + ev_call
    return ev_total, fold_freq


def _size_note(pct: float, equity: float, fold_freq: float, ev: float, check_ev: float) -> str:
    gain = ev - check_ev
    gain_str = f'+{gain:.1f}BB' if gain >= 0 else f'{gain:.1f}BB'
    if pct <= 0.35:
        note = f'薄取值/保護 {gain_str}'
    elif pct <= 0.55:
        note = f'標準半池 {gain_str}'
    elif pct <= 0.80:
        note = f'強牌/半詐唬 {gain_str}'
    else:
        note = f'極化 {gain_str}'
    return note


def compare_bet_sizes(
    pot_bb:         float,
    hero_equity:    float,    # 0-1，Monte Carlo 勝率
    base_fold_freq: float = 0.50,  # 對手基礎棄牌頻率（HUD FCbet / 50%）
    street:         str   = 'flop',
    eff_stack_bb:   float = 100.0,
    sizes:          Optional[List[float]] = None,   # 覆蓋預設注碼清單
) -> SizingEVResult:
    """
    比較多個注碼方案的 EV，找出最優方案。

    Args:
        pot_bb:         當前底池（BB）
        hero_equity:    英雄勝率（Monte Carlo，0-1）
        base_fold_freq: 對手面對 50% pot 的棄牌頻率（0-1）
        street:         'flop'/'turn'/'river'
        eff_stack_bb:   有效籌碼（BB）
        sizes:          注碼比例清單，None = 預設

    Returns:
        SizingEVResult
    """
    pot_bb         = max(0.1, pot_bb)
    hero_equity    = max(0.0, min(1.0, hero_equity))
    base_fold_freq = max(0.0, min(0.95, base_fold_freq))

    size_list = sizes or [s for s, _ in _SIZES]

    # 確保不超過有效籌碼
    max_size_pct = eff_stack_bb / pot_bb if pot_bb > 0 else 2.0
    size_list = [s for s in size_list if s <= max_size_pct + 0.01]
    if not size_list:
        size_list = [0.33]

    # 過牌 EV 基準（簡化：假設過牌後攤牌，但忽略後續動態）
    check_ev = hero_equity * pot_bb

    options: List[SizingEV] = []
    for pct in size_list:
        label = next((l for p, l in _SIZES if abs(p - pct) < 0.03), f'{int(pct*100)}%')
        ev, fold = _ev_for_size(pct, pot_bb, hero_equity, base_fold_freq)
        note = _size_note(pct, hero_equity, fold, ev, check_ev)
        bet_bb = pct * pot_bb

        # 超過有效籌碼的 SPR 警告
        if bet_bb > eff_stack_bb * 0.8:
            note += ' [接近全下]'

        options.append(SizingEV(
            label       = f'{label} 底池',
            pct         = pct,
            bet_bb      = round(bet_bb, 1),
            fold_freq   = round(fold, 3),
            ev_bb       = round(ev, 2),
            ev_vs_check = round(ev - check_ev, 2),
            is_optimal  = False,
            note        = note,
        ))

    # 標記最佳方案
    best = max(options, key=lambda x: x.ev_bb)
    best.is_optimal = True

    # 若最佳 EV 低於過牌，則建議過牌
    if best.ev_bb < check_ev * 0.98:
        summary = (f'建議過牌（check EV={check_ev:.1f}BB > 最佳注碼 EV={best.ev_bb:.1f}BB）')
    else:
        gain = best.ev_bb - check_ev
        summary = (f'最佳注碼: {best.label}={best.bet_bb:.0f}BB  '
                   f'EV+{best.ev_bb:.1f}BB  比過牌多{gain:+.1f}BB  '
                   f'折疊頻率 {best.fold_freq:.0%}')

    return SizingEVResult(
        pot_bb          = pot_bb,
        hero_equity     = hero_equity,
        base_fold_freq  = base_fold_freq,
        street          = street,
        options         = options,
        optimal         = best,
        check_ev        = round(check_ev, 2),
        ev_loss_from_check = round(best.ev_bb - check_ev, 2),
        summary         = summary,
    )


def sizing_ev_summary(r: SizingEVResult) -> str:
    """單行 overlay 顯示。"""
    opt = r.optimal
    if opt.ev_bb < r.check_ev * 0.98:
        return f'[注碼EV] 建議過牌 EV={r.check_ev:.1f}BB (下注 EV 更低)'
    gain = opt.ev_bb - r.check_ev
    return (f'[注碼EV] 最佳:{opt.label}={opt.bet_bb:.0f}BB  '
            f'EV+{opt.ev_bb:.1f}BB  +{gain:.1f}BB vs 過牌')


def sizing_ev_table(r: SizingEVResult) -> str:
    """多行詳細表，用於面板或偵錯。"""
    lines = [
        f'注碼 EV 比較（底池={r.pot_bb:.0f}BB  勝率={r.hero_equity:.0%}  '
        f'對手棄牌={r.base_fold_freq:.0%}）',
        f'  過牌 EV 基準: {r.check_ev:.2f}BB',
        '-' * 50,
    ]
    for o in r.options:
        star = ' *' if o.is_optimal else ''
        lines.append(
            f'  {o.label:10s}  下注={o.bet_bb:4.0f}BB  '
            f'折疊={o.fold_freq:.0%}  EV={o.ev_bb:+.2f}BB{star}'
        )
    lines.append('-' * 50)
    lines.append(f'  {r.summary}')
    return '\n'.join(lines)
