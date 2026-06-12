"""
對手自適應注碼引擎 (Villain-Adaptive Bet Sizing Engine)

GTO 注碼是最差情況下的基準，但針對特定玩家類型大幅調整注碼可顯著提升 EV。

核心調整邏輯：

Fish（呼叫站 / Calling Station）VPIP >= 35%：
  → 價值注碼提高 30-60%（他們會以更差的牌跟注）
  → 停止詐唬（降低詐唬頻率至接近 0）
  → 薄取值範圍擴大（中等牌也值得下注）
  → 面對他們的大注時跟注閾值降低（他們也會詐唬）

Nit（岩石）VPIP <= 18%：
  → 價值注碼縮小 20%（大注會嚇跑他們）
  → 提高詐唬頻率（他們的棄牌率高）
  → 面對他們的加注時棄牌頻率大幅提高（幾乎永遠有好牌）
  → 頻繁偷盲（他們不防守）

TAG（標準緊積極）VPIP 22-28%：
  → 接近 GTO，調整幅度小
  → 若 FCbet 高（> 65%）：增加 C-bet 頻率

LAG（鬆積極）VPIP 28-40%, PFR 25-35%：
  → 陷阱取值（check-call 強牌讓他們建底池）
  → 薄注碼縮小（避免他們用劣勢牌加注）
  → 面對他們的下注減少折疊

Maniac VPIP >= 45%, PFR >= 30%：
  → 純陷阱策略（幾乎不主動下注）
  → 超薄取值（讓他們詐唬所有街）
  → 完全不詐唬

AF 調整（獨立於 VPIP/PFR）：
  高 AF (>= 2.5)：縮小注碼，他們的加注頻率高 → 避免被 bluff raise
  低 AF (<= 0.8)：增大注碼，他們極少加注 → 可以更自由下注

FCbet 調整：
  高 FCbet (>= 70%)：縮小 C-bet 注碼（他們反正會棄牌，無需大注）
  低 FCbet (<= 30%)：增大 C-bet 注碼（需要更大注碼才能讓他們不利）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class AdaptiveSizing:
    # 對手描述
    villain_type:       str      # 'fish'/'nit'/'tag'/'lag'/'maniac'
    villain_type_zh:    str      # 中文
    hands_observed:     int

    # 注碼調整
    value_size_pct:     float    # 建議取值注碼（底池比例）
    value_size_bb:      float    # 換算 BB
    bluff_size_pct:     float    # 建議詐唬注碼
    thin_value_ok:      bool     # 是否可以薄薄取值（下延伸對方邊緣跟注）
    bluff_ok:           bool     # 是否適合詐唬

    # 頻率調整
    cbet_freq:          float    # 建議 C-bet 頻率
    value_bet_freq:     float    # 價值下注頻率
    bluff_freq:         float    # 詐唬頻率

    # 防守調整
    call_equity_threshold: float # 面對對手下注的最低跟注勝率
    fold_vs_raise:      bool     # 面對他們的加注是否應大量棄牌

    # EV 估算（vs GTO baseline）
    ev_gain_per_100:    float    # 比純 GTO 多贏的估算 BB/100

    # 輸出
    key_advice:         str      # 最重要的一條建議
    full_advice:        str      # 完整建議
    tips:               List[str] = field(default_factory=list)


# ── 玩家類型定義 ───────────────────────────────────────────────────────────────

_TYPE_ZH = {
    'fish':   '魚型（呼叫站）',
    'nit':    '岩石（超緊）',
    'tag':    '標準 TAG',
    'lag':    '鬆積極 LAG',
    'maniac': '狂人 Maniac',
    'unknown': '未知類型',
}


def _classify_villain(
    vpip:  float,   # 百分比 0-100
    pfr:   float,   # 百分比 0-100
    af:    float,   # aggression factor
    fcbet: float,   # fold to c-bet %
) -> str:
    """根據 HUD 數據分類對手類型。"""
    if vpip >= 45 and pfr >= 30:
        return 'maniac'
    if vpip >= 35 and pfr <= 18:
        return 'fish'
    if vpip >= 28 and pfr >= 22:
        return 'lag'
    if vpip <= 18:
        return 'nit'
    if 20 <= vpip <= 30 and pfr >= 16:
        return 'tag'
    if vpip >= 35:
        return 'fish'   # 寬鬆玩家但 PFR 也偏高
    return 'tag'        # 默認 TAG


# ── 各類型基礎注碼策略 ─────────────────────────────────────────────────────────

_BASE_STRATEGY: Dict[str, Dict] = {
    'fish': {
        'value_size_pct':        0.75,    # 75% 底池取值（他們會用差牌跟注）
        'bluff_size_pct':        0.50,    # 保留詐唬尺寸不變（但頻率降低）
        'thin_value_ok':         True,    # 可以薄取值
        'bluff_ok':              False,   # 停止詐唬
        'cbet_freq':             0.70,    # 高頻 C-bet（他們 FCbet 低）
        'value_bet_freq':        0.90,    # 幾乎對所有強牌取值
        'bluff_freq':            0.05,    # 幾乎不詐唬
        'call_eq_threshold':     0.25,    # 用更低勝率跟注（因為他們也詐唬）
        'fold_vs_raise':         False,   # 不輕易棄牌
        'ev_gain_per_100':       8.0,     # 比 GTO 多賺約 8BB/100
        'key_advice':            '加大取值注碼，停止詐唬，更薄的牌也可以取值',
    },
    'nit': {
        'value_size_pct':        0.40,    # 40% 底池取值（大注嚇跑他們）
        'bluff_size_pct':        0.50,    # 標準詐唬尺寸
        'thin_value_ok':         False,   # 不要薄取值
        'bluff_ok':              True,    # 多詐唬
        'cbet_freq':             0.80,    # 高頻偷底（他們棄牌率高）
        'value_bet_freq':        0.70,    # 只有強牌才取值
        'bluff_freq':            0.35,    # 高詐唬頻率
        'call_eq_threshold':     0.45,    # 面對他們的下注需要更高勝率
        'fold_vs_raise':         True,    # 面對加注基本棄牌（他們很少詐唬加注）
        'ev_gain_per_100':       5.0,
        'key_advice':            '縮小取值注碼，大幅增加詐唬，面對加注基本棄牌',
    },
    'tag': {
        'value_size_pct':        0.55,    # 接近 GTO（55%）
        'bluff_size_pct':        0.55,
        'thin_value_ok':         False,
        'bluff_ok':              True,    # 適量詐唬
        'cbet_freq':             0.60,    # GTO 近似頻率
        'value_bet_freq':        0.75,
        'bluff_freq':            0.20,    # 標準詐唬
        'call_eq_threshold':     0.35,    # GTO 標準跟注閾值
        'fold_vs_raise':         False,
        'ev_gain_per_100':       2.0,
        'key_advice':            '標準 GTO 策略，若 FCbet 高則提高 C-bet 頻率',
    },
    'lag': {
        'value_size_pct':        0.50,    # 稍微縮小（避免他們加注拿走 EV）
        'bluff_size_pct':        0.40,    # 縮小詐唬注碼
        'thin_value_ok':         False,
        'bluff_ok':              False,   # 停止詐唬（他們會加注繼續）
        'cbet_freq':             0.45,    # 降低 C-bet（他們頻繁 float/raise）
        'value_bet_freq':        0.85,    # 強牌要積極取值
        'bluff_freq':            0.10,    # 極少詐唬
        'call_eq_threshold':     0.30,    # 更低閾值跟注（他們有詐唬）
        'fold_vs_raise':         False,   # 不輕易棄牌
        'ev_gain_per_100':       4.0,
        'key_advice':            '減少 C-bet，陷阱取值，降低詐唬，用差牌跟注他們',
    },
    'maniac': {
        'value_size_pct':        0.45,    # 縮小（讓他們繼續詐唬）
        'bluff_size_pct':        0.40,
        'thin_value_ok':         True,    # 超薄取值（任何中等牌都值得取值）
        'bluff_ok':              False,   # 絕不詐唬
        'cbet_freq':             0.30,    # 低頻 C-bet（多過牌-call 設陷阱）
        'value_bet_freq':        0.90,    # 強牌要取值
        'bluff_freq':            0.0,     # 完全不詐唬
        'call_eq_threshold':     0.25,    # 非常低的跟注閾值
        'fold_vs_raise':         False,   # 幾乎不棄牌面對他們的加注
        'ev_gain_per_100':       12.0,    # 最大利潤來源
        'key_advice':            '設陷阱，超薄取值，永遠不詐唬，幾乎不棄牌',
    },
    'unknown': {
        'value_size_pct':        0.55,
        'bluff_size_pct':        0.50,
        'thin_value_ok':         False,
        'bluff_ok':              True,
        'cbet_freq':             0.60,
        'value_bet_freq':        0.75,
        'bluff_freq':            0.20,
        'call_eq_threshold':     0.35,
        'fold_vs_raise':         False,
        'ev_gain_per_100':       0.0,
        'key_advice':            '數據不足，使用標準 GTO 策略直到有更多手牌',
    },
}


# ── 主函數 ────────────────────────────────────────────────────────────────────

def calc_adaptive_sizing(
    pot_bb:        float,
    # HUD 數據（百分比，0-100）
    villain_vpip:  float = 25.0,    # e.g. 25.0 for 25%
    villain_pfr:   float = 15.0,
    villain_af:    float = 1.5,
    villain_fcbet: float = 50.0,
    villain_cbet:  float = 60.0,
    hands_observed: int  = 0,
    # 情境
    street:        str   = 'flop',
    hand_percentile: float = 0.60,   # 0-1
    in_position:   bool  = True,
) -> AdaptiveSizing:
    """
    根據對手 HUD 數據計算最優取值/詐唬注碼。

    Args:
        pot_bb:           當前底池（BB）
        villain_vpip:     對手 VPIP（百分比，如 25.0 = 25%）
        villain_pfr:      對手 PFR
        villain_af:       對手 AF
        villain_fcbet:    對手 FCbet（百分比）
        villain_cbet:     對手 CBet（百分比）
        hands_observed:   已觀察手牌數（少於 15 手時可靠性低）
        street:           街道
        hand_percentile:  英雄牌力百分位（0-1）
        in_position:      是否有位置
    """
    # 確保樣本充足
    reliable = hands_observed >= 15

    # 分類對手
    v_type = _classify_villain(villain_vpip, villain_pfr, villain_af, villain_fcbet)
    if not reliable:
        v_type = 'unknown'

    strat = _BASE_STRATEGY[v_type].copy()

    # ── AF 調整（疊加在基礎策略上）────────────────────────────────────────────
    # 高 AF → 縮小注碼（避免被加注）
    if villain_af >= 2.5:
        strat['value_size_pct'] = max(0.33, strat['value_size_pct'] - 0.10)
        strat['bluff_size_pct'] = max(0.33, strat['bluff_size_pct'] - 0.10)
    elif villain_af <= 0.8:
        # 極少加注 → 可以更自由下注
        strat['value_size_pct'] = min(1.0, strat['value_size_pct'] + 0.10)

    # ── FCbet 調整 ──────────────────────────────────────────────────────────
    # 高 FCbet → 縮小 C-bet 注碼（他們反正棄牌，小注更有效率）
    if villain_fcbet >= 70:
        strat['cbet_freq']      = min(0.95, strat['cbet_freq'] + 0.15)
        strat['bluff_size_pct'] = max(0.25, strat['bluff_size_pct'] - 0.10)
    elif villain_fcbet <= 30:
        # 對 C-bet 幾乎不棄牌 → 增大注碼逼他們投入更多
        strat['value_size_pct'] = min(1.0, strat['value_size_pct'] + 0.10)
        strat['bluff_freq']     = max(0.0, strat['bluff_freq'] - 0.10)

    # ── 手牌強度調整 ────────────────────────────────────────────────────────
    # 超強牌 → 進一步增大注碼
    if hand_percentile >= 0.85:
        strat['value_size_pct'] = min(1.0, strat['value_size_pct'] + 0.10)
    # 中等牌 → 薄取值只對 Fish/Maniac
    elif hand_percentile >= 0.60:
        if not strat['thin_value_ok']:
            strat['value_size_pct'] = max(0.33, strat['value_size_pct'] - 0.05)

    # ── 街道調整 ────────────────────────────────────────────────────────────
    if street == 'river':
        # 河牌無需保護，注碼可以更極端（魚：大取值；岩石：縮小）
        if v_type == 'fish':
            strat['value_size_pct'] = min(1.20, strat['value_size_pct'] * 1.15)
        elif v_type == 'nit':
            strat['value_size_pct'] *= 0.90

    # ── 位置調整 ────────────────────────────────────────────────────────────
    if not in_position:
        strat['cbet_freq']      = max(0.15, strat['cbet_freq'] - 0.10)
        strat['bluff_freq']     = max(0.0,  strat['bluff_freq'] - 0.05)

    # ── 換算 BB ──────────────────────────────────────────────────────────────
    value_size_bb = round(strat['value_size_pct'] * pot_bb, 1)
    bluff_size_bb = round(strat['bluff_size_pct'] * pot_bb, 1)

    # ── 完整建議文字 ─────────────────────────────────────────────────────────
    v_zh = _TYPE_ZH.get(v_type, v_type)
    adj_note = ''
    if villain_af >= 2.5:
        adj_note += f'  (AF={villain_af:.1f} 高→縮注)'
    if villain_fcbet >= 70:
        adj_note += f'  (FCbet={villain_fcbet:.0f}% 高→常C-bet)'

    full_advice = (
        f'{v_zh} VPIP={villain_vpip:.0f}%/{villain_pfr:.0f}%：'
        f'{strat["key_advice"]}。'
        f'取值注碼 {int(strat["value_size_pct"]*100)}% 底池'
        f'（GTO~50%）。{adj_note}'
    )

    tips = []
    if not reliable:
        tips.append(f'樣本不足（{hands_observed}手）：使用 GTO 基準，再觀察')
    if v_type == 'fish':
        tips.append('遇到 Fish：不要用複雜策略，簡單取值最有效')
    if v_type == 'maniac':
        tips.append('遇到狂人：過牌-跟注強牌，讓他們替你建底池')
    if villain_fcbet >= 70:
        tips.append(f'FCbet {villain_fcbet:.0f}%：這條街幾乎可以對任何手牌 C-bet')

    return AdaptiveSizing(
        villain_type            = v_type,
        villain_type_zh         = v_zh,
        hands_observed          = hands_observed,
        value_size_pct          = round(strat['value_size_pct'], 2),
        value_size_bb           = value_size_bb,
        bluff_size_pct          = round(strat['bluff_size_pct'], 2),
        thin_value_ok           = strat['thin_value_ok'],
        bluff_ok                = strat['bluff_ok'],
        cbet_freq               = round(strat['cbet_freq'], 2),
        value_bet_freq          = round(strat['value_bet_freq'], 2),
        bluff_freq              = round(strat['bluff_freq'], 2),
        call_equity_threshold   = strat['call_eq_threshold'],
        fold_vs_raise           = strat['fold_vs_raise'],
        ev_gain_per_100         = strat['ev_gain_per_100'],
        key_advice              = strat['key_advice'],
        full_advice             = full_advice,
        tips                    = tips,
    )


def sizing_summary(r: AdaptiveSizing) -> str:
    """單行摘要，用於 overlay 顯示。"""
    bluff_str = f'詐唬{int(r.bluff_size_pct*100)}%' if r.bluff_ok else '停止詐唬'
    thin_str  = '可薄取值' if r.thin_value_ok else ''
    return (f'{r.villain_type_zh[:4]}  '
            f'取值{int(r.value_size_pct*100)}%底池({r.value_size_bb:.1f}BB)  '
            f'{bluff_str}  {thin_str}').rstrip()


def quick_sizing(
    pot_bb:    float,
    vpip:      float,    # 百分比 0-100
    pfr:       float,
    af:        float    = 1.5,
    fcbet:     float    = 50.0,
    hands:     int      = 20,
) -> str:
    """快速查詢。"""
    r = calc_adaptive_sizing(pot_bb, vpip, pfr, af, fcbet, hands)
    return sizing_summary(r)
