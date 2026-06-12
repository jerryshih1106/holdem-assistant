"""
範圍優勢 C-bet 整合決策器 (Range Advantage C-bet Integrator)

職業玩家的 C-bet 決策核心：
  「我的翻前範圍在這個牌面上比對手範圍強多少？」

整合三個模組：
  board_texture.py  → 牌面濕度、連張性、高牌密度
  range_equity.py   → 範圍 vs 範圍股票（hero range equity advantage）
  exploit.py        → 對手 HUD 調整（FCbet 高 → 更積極）

核心概念：
  範圍優勢 (Range Advantage) = hero_range_equity - 0.5
    > +0.10 → 強範圍優勢  → 高頻小注（全範圍）
    +0.03 ~ +0.10 → 輕微優勢 → 中頻中注
    -0.03 ~ +0.03 → 中性 → 低頻或混合
    < -0.03 → 對手範圍優勢 → 謹慎 C-bet，以強牌為主

典型高頻 C-bet 情境（BTN 開牌，BB 防守）：
  A-high 乾燥面：BTN 範圍命中更多 Ax，高頻 1/3 底池
  低對低連張：BB 範圍命中更多（低對、小連張），降低頻率
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from poker.board_texture import analyze_board, BoardTexture


@dataclass
class RangeCbetResult:
    # 輸入摘要
    hero_pos:           str
    villain_pos:        str
    community:          List[str]
    street:             str           # 'flop'/'turn'/'river'

    # 牌面分析
    texture:            BoardTexture
    wetness:            float         # 0=乾燥 1=極潮濕
    board_type:         str           # 'dry_high'/'wet_low'/'monotone' etc.

    # 範圍優勢
    range_advantage:    float         # hero range equity - 0.5 (-0.5 to +0.5)
    range_adv_label:    str           # '強/輕微/中性/劣勢'
    hero_range_equity:  float         # hero range equity vs villain range

    # C-bet 建議（未調整，純 GTO）
    cbet_freq_gto:      float         # GTO 建議頻率
    cbet_size_gto:      float         # GTO 建議注碼（底池比例）

    # 對手 HUD 調整後
    cbet_freq_adj:      float         # 調整後頻率
    cbet_size_adj:      float         # 調整後注碼
    exploit_note:       str           # 剝削性說明

    # 最終建議
    should_cbet:        bool
    recommended_size_bb: float        # 換算 BB
    reasoning:          str
    tips:               List[str] = field(default_factory=list)


# ── 位置對應的 C-bet 基礎範圍優勢 ────────────────────────────────────────────

# 各位置組合的翻前範圍優勢估算（基於 solver 近似值）
# (hero_pos, villain_pos) → 翻牌面的 range equity advantage by texture
_RANGE_ADV_TABLE: Dict[tuple, Dict[str, float]] = {
    # BTN 開牌 vs BB 防守 — BTN 通常有顯著範圍優勢（除低牌面外）
    ('BTN', 'BB'): {
        'dry_high':    +0.14,   # A-high / K-high 乾燥 → BTN 優勢大
        'dry_low':     -0.02,   # 低牌面 → BB 命中更多
        'wet_high':    +0.08,   # 高潮濕 → BTN 仍有優勢
        'wet_low':     -0.05,   # 低潮濕 → BB 略有優勢
        'paired_high': +0.10,   # 配對高牌 → BTN 優勢
        'paired_low':  +0.02,   # 配對低牌 → 接近中性
        'monotone':    +0.04,   # 單色 → 略偏向 BTN
    },
    ('CO', 'BB'): {
        'dry_high':    +0.12, 'dry_low':     -0.03,
        'wet_high':    +0.06, 'wet_low':     -0.06,
        'paired_high': +0.08, 'paired_low':  +0.01, 'monotone': +0.03,
    },
    ('BTN', 'SB'): {
        'dry_high': +0.10, 'dry_low': +0.02, 'wet_high': +0.07,
        'wet_low':  +0.02, 'paired_high': +0.08, 'paired_low': +0.03, 'monotone': +0.04,
    },
    ('SB', 'BB'): {
        'dry_high': +0.08, 'dry_low': -0.04, 'wet_high': +0.05,
        'wet_low':  -0.06, 'paired_high': +0.06, 'paired_low': -0.01, 'monotone': +0.02,
    },
    ('CO', 'SB'): {
        'dry_high': +0.10, 'dry_low': +0.01, 'wet_high': +0.06,
        'wet_low':  -0.02, 'paired_high': +0.08, 'paired_low': +0.02, 'monotone': +0.03,
    },
    ('HJ', 'BB'): {
        'dry_high': +0.10, 'dry_low': -0.04, 'wet_high': +0.05,
        'wet_low':  -0.06, 'paired_high': +0.07, 'paired_low': 0.0, 'monotone': +0.02,
    },
}

_DEFAULT_ADV: Dict[str, float] = {
    'dry_high': +0.08, 'dry_low': -0.02, 'wet_high': +0.04,
    'wet_low':  -0.04, 'paired_high': +0.05, 'paired_low': 0.0, 'monotone': +0.02,
}


def _board_type(texture: BoardTexture) -> str:
    """將 BoardTexture 分類為 7 種牌面類型。"""
    if texture.monotone:
        return 'monotone'
    if texture.has_pair:
        return 'paired_high' if texture.top_rank >= 10 else 'paired_low'
    if texture.top_rank >= 10:
        return 'wet_high' if texture.wetness >= 0.5 else 'dry_high'
    return 'wet_low' if texture.wetness >= 0.5 else 'dry_low'


def _range_adv_label(adv: float) -> str:
    if adv >= 0.10: return '強範圍優勢'
    if adv >= 0.03: return '輕微範圍優勢'
    if adv >= -0.03: return '範圍中性'
    return '範圍劣勢（對手優勢）'


# ── GTO C-bet 頻率/注碼 由範圍優勢決定 ──────────────────────────────────────

def _gto_cbet(
    range_adv:   float,
    wetness:     float,
    board_type:  str,
    in_position: bool,
) -> tuple:
    """
    回傳 (cbet_freq, cbet_size_pct) 的 GTO 基準值。

    核心邏輯：
      強範圍優勢 + 乾燥 → 全範圍高頻小注（1/3 底池）
      輕微優勢   + 濕潤 → 中等頻率中注（1/2 底池）
      中性/劣勢  + 乾燥 → 低頻中注（強牌）
      對手優勢   + 濕潤 → 很低頻，以強牌/超強牌為主
    """
    if range_adv >= 0.10:
        # 強優勢：全範圍下注
        if wetness <= 0.3:
            freq, size = 0.80, 0.33   # 乾燥高頻小注
        elif wetness <= 0.6:
            freq, size = 0.65, 0.50   # 半潮濕中注
        else:
            freq, size = 0.50, 0.67   # 潮濕大注（保護）
    elif range_adv >= 0.03:
        if wetness <= 0.3:
            freq, size = 0.60, 0.33
        elif wetness <= 0.6:
            freq, size = 0.50, 0.50
        else:
            freq, size = 0.40, 0.67
    elif range_adv >= -0.03:
        # 中性：低頻中注
        if wetness <= 0.3:
            freq, size = 0.40, 0.40
        else:
            freq, size = 0.30, 0.50
    else:
        # 範圍劣勢：很低頻，以強牌（nuts/overpair）為主
        freq, size = 0.20, 0.50

    # 無位置降頻
    if not in_position:
        freq = max(0.10, freq * 0.80)

    # 特殊牌面調整
    if board_type == 'monotone':
        freq = max(0.15, freq * 0.75)  # 單色牌面降頻
        size = max(size, 0.50)         # 但注碼偏大
    elif board_type in ('paired_high', 'paired_low'):
        freq = min(freq + 0.05, 0.85)  # 配對牌面稍微提高頻率

    return round(freq, 2), round(size, 2)


# ── 主函數 ────────────────────────────────────────────────────────────────────

def analyze_range_cbet(
    hero_pos:         str,
    villain_pos:      str,
    community:        List[str],
    pot_bb:           float = 10.0,
    in_position:      bool  = True,
    # HUD 調整參數
    villain_fcbet:    float = 0.50,    # 對手對 C-bet 的棄牌率
    villain_vpip:     float = 0.25,    # 對手 VPIP
    villain_aggr:     float = 1.5,     # 對手 AF
    # 可選：來自 range_equity 的真實範圍勝率（若有可覆蓋估算）
    hero_range_equity_override: Optional[float] = None,
) -> RangeCbetResult:
    """
    分析特定牌面的 C-bet 策略。

    Args:
        hero_pos:         英雄位置（翻前主動方）
        villain_pos:      對手位置（跟注方）
        community:        公牌（3-5 張）
        pot_bb:           目前底池（BB）
        in_position:      是否有位置優勢
        villain_fcbet:    對手對 C-bet 的棄牌率（HUD）
        villain_vpip:     對手 VPIP（HUD）
        villain_aggr:     對手 Aggression Factor（HUD）
        hero_range_equity_override: 若有 range_equity.py 計算的真實值可傳入
    """
    street = {3: 'flop', 4: 'turn', 5: 'river'}.get(len(community), 'flop')

    # ── 牌面分析 ────────────────────────────────────────────────────
    texture = analyze_board(community)
    btype   = _board_type(texture)

    # ── 範圍優勢估算 ─────────────────────────────────────────────────
    pos_key = (hero_pos.upper(), villain_pos.upper())
    adv_table = _RANGE_ADV_TABLE.get(pos_key, _DEFAULT_ADV)
    range_adv = adv_table.get(btype, 0.0)

    if hero_range_equity_override is not None:
        hero_eq = hero_range_equity_override
        range_adv = hero_eq - 0.50
    else:
        hero_eq = 0.50 + range_adv

    adv_label = _range_adv_label(range_adv)

    # ── GTO 建議 ─────────────────────────────────────────────────────
    gto_freq, gto_size = _gto_cbet(range_adv, texture.wetness, btype, in_position)

    # ── HUD 調整 ──────────────────────────────────────────────────────
    adj_freq = gto_freq
    adj_size = gto_size
    exploit_parts = []

    # FCbet 高 → 積極 C-bet（對手棄牌太多）
    if villain_fcbet >= 0.65:
        adj_freq = min(0.95, adj_freq + (villain_fcbet - 0.50) * 0.40)
        exploit_parts.append(f'FCbet={villain_fcbet:.0%} 高→提升頻率至{adj_freq:.0%}')
    elif villain_fcbet <= 0.35:
        adj_freq = max(0.10, adj_freq - (0.50 - villain_fcbet) * 0.30)
        exploit_parts.append(f'FCbet={villain_fcbet:.0%} 低→減少頻率至{adj_freq:.0%}，以強牌為主')

    # VPIP 高（Fish）→ 大注取值
    if villain_vpip >= 0.40:
        adj_size = min(1.0, adj_size * 1.25)
        exploit_parts.append(f'Fish(VPIP={villain_vpip:.0%})→增大注碼至{int(adj_size*100)}%底池')
    elif villain_vpip <= 0.18:
        adj_size = max(0.25, adj_size * 0.85)
        exploit_parts.append(f'Nit(VPIP={villain_vpip:.0%})→縮小注碼至{int(adj_size*100)}%底池')

    # AF 高（積極型）→ 降低 C-bet 頻率，更多 check-raise trap
    if villain_aggr >= 2.5:
        adj_freq = max(0.15, adj_freq - 0.10)
        exploit_parts.append(f'AF={villain_aggr:.1f} 積極→降低頻率，增加 check-raise 陷阱')

    exploit_note = '；'.join(exploit_parts) if exploit_parts else '標準調整（無顯著偏差）'

    # ── 最終建議 ─────────────────────────────────────────────────────
    should_cbet = adj_freq >= 0.30
    rec_bb = round(pot_bb * adj_size, 1)

    reasons = [
        f'{btype.replace("_"," ")} 牌面  {adv_label}（{range_adv:+.0%}）',
        f'GTO: {gto_freq:.0%} @ {int(gto_size*100)}% 底池',
    ]
    if exploit_parts:
        reasons.append(exploit_note)

    tips = [
        f'範圍優勢 {range_adv:+.0%}：你的翻前範圍在此牌面的股票 {hero_eq:.0%}',
        f'板面濕度 {texture.wetness:.0%}（{texture.texture_name}）',
    ]
    if range_adv >= 0.10:
        tips.append('強範圍優勢：可高頻全範圍下注，以 1/3 底池為主（Piosolve 策略）')
    elif range_adv < -0.03:
        tips.append('範圍劣勢：謹慎 C-bet，只用超強牌（overpair+）和強 draws')
    if texture.flush_draw:
        tips.append('有同花聽牌：降低 C-bet 頻率或提高注碼以保護強牌')

    return RangeCbetResult(
        hero_pos          = hero_pos,
        villain_pos       = villain_pos,
        community         = community,
        street            = street,
        texture           = texture,
        wetness           = texture.wetness,
        board_type        = btype,
        range_advantage   = round(range_adv, 3),
        range_adv_label   = adv_label,
        hero_range_equity = round(hero_eq, 3),
        cbet_freq_gto     = gto_freq,
        cbet_size_gto     = gto_size,
        cbet_freq_adj     = round(adj_freq, 2),
        cbet_size_adj     = round(adj_size, 2),
        exploit_note      = exploit_note,
        should_cbet       = should_cbet,
        recommended_size_bb = rec_bb,
        reasoning         = '；'.join(reasons),
        tips              = tips,
    )


def cbet_summary(r: RangeCbetResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    act = 'C-bet' if r.should_cbet else '過牌'
    return (f'{r.street} {act} {r.cbet_freq_adj:.0%}  '
            f'{int(r.cbet_size_adj*100)}%底池({r.recommended_size_bb:.1f}BB)  '
            f'[範圍{r.range_advantage:+.0%} {r.range_adv_label[:4]}]')


def quick_cbet_advice(
    hero_pos:      str,
    villain_pos:   str,
    community:     List[str],
    pot_bb:        float = 10.0,
    in_position:   bool  = True,
    villain_fcbet: float = 0.50,
    villain_vpip:  float = 0.25,
) -> str:
    """一行快速查詢，回傳 C-bet 建議字串。"""
    r = analyze_range_cbet(
        hero_pos, villain_pos, community, pot_bb,
        in_position, villain_fcbet, villain_vpip,
    )
    return cbet_summary(r)
