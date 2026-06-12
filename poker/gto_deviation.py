"""
GTO 頻率偏差分析 (GTO Deviation Checker)

給定一個行動情境（跟哪條街、哪種位置），輸入你實際的下注頻率，
計算與 GTO 均衡頻率的偏差，並量化對手可以如何利用你，以及每 100 手的 EV 損失。

核心概念：
  GTO 均衡頻率保護你不被利用。若你的頻率偏離均衡：
  - 過高頻率（例如 cbet 90%）→ 對手可以廣泛 float 或 check-raise
  - 過低頻率（例如 cbet 20%）→ 對手可以廣泛 probe bet 或 free-card

EV 損失估算：
  EV_loss ≈ |deviation| × exploitation_factor × pot_bb
  其中 exploitation_factor 衡量對手能利用偏差的程度

輸出：
  DeviationResult — 包含 GTO 基準、你的頻率、偏差量、EV 損失、建議調整
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class DeviationResult:
    action_type:   str       # 'cbet' / '3bet' / 'barrel' / 'check_raise' / 'bluff_catch'
    position:      str       # 'IP' / 'OOP' / 'BTN' 等
    street:        str       # 'flop' / 'turn' / 'river'
    gto_freq:      float     # GTO 均衡頻率（0-1）
    hero_freq:     float     # 英雄實際頻率（0-1）
    deviation:     float     # hero_freq - gto_freq（正=偏高，負=偏低）
    ev_loss_bb100: float     # 每 100 手估算 EV 損失（BB/100）
    is_balanced:   bool      # abs(deviation) < 0.08 視為均衡
    direction:     str       # 'over' / 'under' / 'balanced'
    exploit_risk:  str       # 'high' / 'medium' / 'low'
    recommendation: str      # 中文建議
    gto_rationale: str       # 為什麼 GTO 是這個頻率


# ── GTO 基準頻率資料庫 ──────────────────────────────────────────────────────────
# 來源：Solver 均值（GTO Wizard / PioSOLVER 研究摘要）
# 格式：(action_type, position_key, street, board_texture) → (gto_freq, ev_per_unit)
# ev_per_unit：對手每 1 頻率偏差能獲得的 BB/100 收益

_GTO_DB: Dict[Tuple, Tuple[float, float]] = {
    # ── Flop C-bet ────────────────────────────────────────────────────────────
    ('cbet', 'IP',    'flop', 'dry'):    (0.65, 8.0),   # BTN vs BB，乾燥牌面
    ('cbet', 'IP',    'flop', 'wet'):    (0.45, 10.0),  # 濕潤牌面更低頻
    ('cbet', 'OOP',   'flop', 'dry'):    (0.50, 9.0),   # SB vs BB OOP
    ('cbet', 'OOP',   'flop', 'wet'):    (0.35, 12.0),  # OOP 濕牌面更謹慎
    ('cbet', 'IP',    'flop', 'paired'): (0.55, 7.0),   # 對子牌面
    ('cbet', 'OOP',   'flop', 'paired'): (0.45, 8.0),
    # ── Turn Barrel ───────────────────────────────────────────────────────────
    ('barrel', 'IP',  'turn', 'dry'):    (0.55, 9.0),
    ('barrel', 'IP',  'turn', 'wet'):    (0.48, 11.0),
    ('barrel', 'OOP', 'turn', 'dry'):    (0.45, 10.0),
    ('barrel', 'OOP', 'turn', 'wet'):    (0.38, 13.0),
    # ── River Bet ─────────────────────────────────────────────────────────────
    ('barrel', 'IP',  'river', 'dry'):   (0.50, 10.0),
    ('barrel', 'IP',  'river', 'wet'):   (0.45, 12.0),
    ('barrel', 'OOP', 'river', 'dry'):   (0.42, 11.0),
    ('barrel', 'OOP', 'river', 'wet'):   (0.38, 14.0),
    # ── 3-Bet ─────────────────────────────────────────────────────────────────
    ('3bet', 'IP',    'preflop', 'any'):  (0.10, 15.0),  # BTN vs CO 開牌
    ('3bet', 'OOP',   'preflop', 'any'):  (0.08, 12.0),  # BB vs BTN
    # ── Check-Raise ───────────────────────────────────────────────────────────
    ('check_raise', 'OOP', 'flop', 'dry'):  (0.12, 14.0),
    ('check_raise', 'OOP', 'flop', 'wet'):  (0.18, 16.0),
    ('check_raise', 'OOP', 'turn', 'dry'):  (0.15, 13.0),
    ('check_raise', 'OOP', 'turn', 'wet'):  (0.20, 15.0),
    # ── Bluff-Catch (call vs bet) ────────────────────────────────────────────
    ('bluff_catch', 'IP',  'river', 'any'): (0.50, 8.0),   # MDF 基準
    ('bluff_catch', 'OOP', 'river', 'any'): (0.45, 9.0),
    # ── Donk Bet ─────────────────────────────────────────────────────────────
    ('donk_bet', 'OOP', 'flop', 'any'):  (0.15, 11.0),
    ('donk_bet', 'OOP', 'turn', 'any'):  (0.20, 10.0),
}

# 如果找不到精確 board_texture，這些 fallback key 按順序嘗試
_TEXTURE_FALLBACKS = ['dry', 'any']


def _lookup(action_type: str, position: str, street: str,
            board_texture: str) -> Optional[Tuple[float, float]]:
    pos_key = _normalize_position(position)
    textures_to_try = [board_texture] + _TEXTURE_FALLBACKS
    for tex in textures_to_try:
        key = (action_type, pos_key, street, tex)
        if key in _GTO_DB:
            return _GTO_DB[key]
    # 嘗試通用 position
    for tex in textures_to_try:
        key = (action_type, 'IP', street, tex)
        val = _GTO_DB.get(key)
        if val:
            return val
    return None


def _normalize_position(position: str) -> str:
    ip_positions  = {'BTN', 'CO', 'HJ', 'IP'}
    oop_positions = {'SB', 'BB', 'UTG', 'OOP'}
    p = position.upper()
    if p in ip_positions:
        return 'IP'
    if p in oop_positions:
        return 'OOP'
    return 'IP'   # 預設


def check_deviation(
    action_type:   str,
    hero_freq:     float,
    position:      str   = 'IP',
    street:        str   = 'flop',
    board_texture: str   = 'dry',
    pot_bb:        float = 10.0,
) -> DeviationResult:
    """
    計算你的策略頻率與 GTO 的偏差並量化 EV 損失。

    Args:
        action_type:    'cbet'/'barrel'/'3bet'/'check_raise'/'bluff_catch'/'donk_bet'
        hero_freq:      你實際的行動頻率（0.0 – 1.0）
        position:       'IP'/'OOP'/'BTN'/'SB' 等
        street:         'preflop'/'flop'/'turn'/'river'
        board_texture:  'dry'/'wet'/'paired'/'any'
        pot_bb:         當前底池大小（BB）

    Returns:
        DeviationResult
    """
    hero_freq = max(0.0, min(1.0, hero_freq))
    result    = _lookup(action_type, position, street, board_texture)

    if result:
        gto_freq, ev_unit = result
    else:
        gto_freq, ev_unit = 0.50, 8.0   # 通用 fallback

    deviation  = hero_freq - gto_freq
    abs_dev    = abs(deviation)

    # EV 損失：偏差 × 每單位損失 × 底池調整
    pot_scale  = (pot_bb / 10.0) ** 0.6   # 底池越大損失越高但非線性
    ev_loss    = abs_dev * ev_unit * pot_scale

    is_balanced = abs_dev < 0.08
    if deviation > 0.04:
        direction = 'over'
    elif deviation < -0.04:
        direction = 'under'
    else:
        direction = 'balanced'

    if abs_dev >= 0.20:
        exploit_risk = 'high'
    elif abs_dev >= 0.10:
        exploit_risk = 'medium'
    else:
        exploit_risk = 'low'

    recommendation = _build_recommendation(action_type, direction, deviation, ev_loss, gto_freq)
    rationale      = _gto_rationale(action_type, gto_freq, position, street)

    return DeviationResult(
        action_type    = action_type,
        position       = position,
        street         = street,
        gto_freq       = round(gto_freq, 3),
        hero_freq      = round(hero_freq, 3),
        deviation      = round(deviation, 3),
        ev_loss_bb100  = round(ev_loss, 2),
        is_balanced    = is_balanced,
        direction      = direction,
        exploit_risk   = exploit_risk,
        recommendation = recommendation,
        gto_rationale  = rationale,
    )


def _build_recommendation(
    action_type: str, direction: str, deviation: float,
    ev_loss: float, gto_freq: float,
) -> str:
    gto_pct  = int(gto_freq * 100)
    loss_str = f'EV損失約 {ev_loss:.1f}BB/100'

    if direction == 'balanced':
        return f'頻率均衡，無需調整（{loss_str} < 1BB/100）'

    action_zh = {
        'cbet': 'C-BET', 'barrel': '繼續下注', '3bet': '3-BET',
        'check_raise': '暗轉', 'bluff_catch': '跟注', 'donk_bet': '引導注',
    }.get(action_type, action_type)

    if direction == 'over':
        pct_over = int(deviation * 100)
        return (f'{action_zh}頻率偏高 +{pct_over}%（GTO={gto_pct}%），'
                f'對手可以廣泛 float/raise 對抗。{loss_str}。'
                f'建議降低到約 {gto_pct}%，增加 check 保護頻率。')
    else:
        pct_under = int(abs(deviation) * 100)
        return (f'{action_zh}頻率偏低 -{pct_under}%（GTO={gto_pct}%），'
                f'對手可以免費拿牌或利用低頻率。{loss_str}。'
                f'建議提升到約 {gto_pct}%，加入更多半詐唬手牌。')


def _gto_rationale(action_type: str, gto_freq: float, position: str, street: str) -> str:
    """解釋 GTO 為什麼設定這個頻率。"""
    pct = int(gto_freq * 100)
    if action_type == 'cbet':
        return (f'翻牌 {pct}% cbet 讓你的下注範圍包含足夠 value 和 bluff，'
                f'使對手難以透過廣泛跟注獲利。')
    if action_type == 'barrel':
        return (f'多街 {pct}% 繼續下注平衡 value 與詐唬，'
                f'維持玩家對你範圍的不確定性。')
    if action_type == '3bet':
        return (f'{pct}% 3BET 頻率（約 1/3 value, 2/3 bluff）'
                f'最大化長期 EV 同時避免被 exploit。')
    if action_type == 'check_raise':
        return (f'暗轉頻率 {pct}% 保護你的過牌範圍，'
                f'防止對手在你過牌後無限制下注。')
    if action_type == 'bluff_catch':
        return (f'{pct}% 跟注率 ≈ MDF（最低防守頻率），'
                f'讓對手的詐唬 EV 趨近於零。')
    return f'GTO 均衡頻率 {pct}%'


def deviation_summary(r: DeviationResult) -> str:
    """單行摘要，適合 overlay 顯示。"""
    action_zh = {
        'cbet': 'CB', 'barrel': '繼注', '3bet': '3BET',
        'check_raise': 'CR', 'bluff_catch': '跟注', 'donk_bet': '引導注',
    }.get(r.action_type, r.action_type)
    hero_pct = int(r.hero_freq * 100)
    gto_pct  = int(r.gto_freq  * 100)
    dev_str  = f'+{int(r.deviation*100)}%' if r.deviation >= 0 else f'{int(r.deviation*100)}%'
    if r.is_balanced:
        return f'{r.street} {action_zh}: {hero_pct}% (GTO={gto_pct}%) 均衡'
    return (f'{r.street} {action_zh}: {hero_pct}% (GTO={gto_pct}%) '
            f'偏差{dev_str}  損失{r.ev_loss_bb100:.1f}BB/100  '
            f'[{r.exploit_risk}風險]')


def batch_check(scenarios: list) -> str:
    """
    一次檢查多個情境，回傳彙整報告。
    scenarios: List[dict] 每個 dict 包含 check_deviation 的 kwargs
    """
    lines = ['GTO 偏差分析報告', '=' * 40]
    total_loss = 0.0
    for sc in scenarios:
        r = check_deviation(**sc)
        total_loss += r.ev_loss_bb100
        lines.append(f'  {deviation_summary(r)}')
    lines.append('-' * 40)
    lines.append(f'  總估算 EV 損失: {total_loss:.1f} BB/100')
    return '\n'.join(lines)
