"""
盲注竊取 / 防守 EV 計算器 (Blind Steal & Defense EV)

盲注竊取是現金桌最穩定的收益來源之一，但很多玩家：
  1. 竊取頻率太低（從 BTN/CO 不夠積極）
  2. BB 防守太緊（給對手過高的竊取 EV）
  3. 不知道對手竊取尺寸與 EV 的關係

核心 EV 公式：
  EV(steal) = fold_rate × pot_before + (1 - fold_rate) × (equity × final_pot - bet)
  EV(defend) = equity × final_pot - call_amount  (vs fixed bet)

最優竊取頻率：讓 BB 在防守/棄牌之間無差異（GTO 均衡）
  MDF (BB) = pot_odds = call / (pot + call)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class StealResult:
    hero_pos:           str
    open_size_bb:       float
    sb_fold_rate:       float    # SB 棄牌率
    bb_fold_rate:       float    # BB 棄牌率
    both_fold_rate:     float    # 兩者都棄牌率

    ev_steal:           float    # 竊取 EV（BB）
    ev_limp_sb:         float    # SB limp EV（比較基準）
    steal_recommended:  bool
    optimal_freq:       float    # 英雄此位置建議竊取頻率

    # 對手防守資訊
    bb_mdf:             float    # BB 最低防守頻率（MDF）
    sb_mdf:             float    # SB 最低防守頻率
    bb_defend_too_tight: bool    # BB 防守是否過緊

    reasoning:          str
    steal_range_hint:   str      # 建議竊取範圍


@dataclass
class DefenseResult:
    hero_pos:           str      # 'BB' or 'SB'
    villain_pos:        str
    open_size_bb:       float
    call_amount_bb:     float

    pot_odds:           float    # 跟注需要的最低勝率
    mdf:                float    # 最低防守頻率（防止純竊取盈利）
    recommended_defense: str     # '3-bet'/'call'/'fold'
    defense_freq:       float    # 建議防守頻率（3-bet + call）

    # EV 分析
    ev_fold:            float    # = 0（參考點）
    ev_call_estimate:   float    # 估算跟注 EV
    ev_3bet_estimate:   float    # 估算 3-bet EV

    reasoning:          str
    key_note:           str


# ── 各位置竊取範圍寬度估算 ────────────────────────────────────────────────────
_STEAL_RANGE_PCT = {
    'BTN': 0.55,   # BTN 竊取範圍最寬
    'CO':  0.35,
    'HJ':  0.22,
    'SB':  0.45,   # SB vs BB 只需 BB 棄牌
}

# 各位置對竊取注的平均棄牌率（針對 2.5BB 開牌）
_SB_FOLD_VS = {
    'BTN': 0.62, 'CO': 0.65, 'HJ': 0.68, 'SB': 0.99,
}
_BB_FOLD_VS = {
    'BTN': 0.55, 'CO': 0.58, 'HJ': 0.60, 'SB': 0.60,
}

# 典型翻後勝率（接近 random vs random，估算）
_POSTFLOP_EQUITY = 0.45   # 跟注者通常被 dominated，約 45%


def calc_steal_ev(
    hero_pos:     str,
    open_size_bb: float = 2.5,
    sb_fold:      float = None,  # None = 使用默認值
    bb_fold:      float = None,
    hero_equity:  float = _POSTFLOP_EQUITY,
) -> StealResult:
    """
    計算從指定位置竊取盲注的 EV。

    Args:
        hero_pos:     英雄位置 ('BTN'/'CO'/'HJ'/'SB')
        open_size_bb: 開牌注大小（BB）
        sb_fold:      SB 棄牌率（None=使用典型值）
        bb_fold:      BB 棄牌率（None=使用典型值）
        hero_equity:  被跟注後的翻後勝率（估算）
    """
    sb_f = sb_fold if sb_fold is not None else _SB_FOLD_VS.get(hero_pos, 0.65)
    bb_f = bb_fold if bb_fold is not None else _BB_FOLD_VS.get(hero_pos, 0.58)

    # SB 位置只對 BB
    if hero_pos == 'SB':
        both_f = bb_f
        sb_f   = 1.0   # SB 已在行動，不存在
    else:
        both_f = sb_f * bb_f

    # 竊取前底池（SB + BB + 英雄開牌）
    pot_before = 1.5   # SB 0.5 + BB 1.0
    bet = open_size_bb

    # EV(fold) = 折疊率 × 現有底池
    ev_fold_part = both_f * pot_before

    # EV(call/3bet) = (1-fold) × (勝率 × 最終底池 - 下注額)
    final_pot = pot_before + bet + bet   # 跟注者跟注後
    ev_call_part = (1 - both_f) * (hero_equity * final_pot - bet)

    ev_steal = ev_fold_part + ev_call_part

    # SB limp EV 估算（比較基準）
    ev_limp = 0.5 * 0.45 * (pot_before + 0.5 + 1.0) - 0.5  # 粗估
    # 通常 ev_limp ≈ -0.1 ~ 0.1

    # MDF 計算（GTO 均衡，讓竊取 EV = 0）
    # EV(steal)=0 → both_fold × 1.5 = (1-both_fold) × (equity × pot_final - bet)
    # 解方程得到 MDF = 1 - both_fold
    bb_mdf = bet / (pot_before + bet)   # 標準 MDF = call / (pot+call)
    sb_mdf = bet / (pot_before + bet)   # SB 類似

    # 最優竊取頻率（讓 BB 的 MDF 剛好被充分利用）
    steal_range = _STEAL_RANGE_PCT.get(hero_pos, 0.30)
    optimal_freq = min(0.90, steal_range)

    # BB 是否防守過緊（bb_fold > 1 - bb_mdf）
    bb_defend_too_tight = bb_f > (1 - bb_mdf)

    # 竊取範圍提示
    if hero_pos == 'BTN':
        range_hint = '前55%手牌：所有對子+Ax+Kx+大部分同花+強的雜牌'
    elif hero_pos == 'CO':
        range_hint = '前35%手牌：66+/A2s+/K8s+/Q9s+/J9s+/T9s/Axo 78+o'
    elif hero_pos == 'HJ':
        range_hint = '前22%手牌：77+/ATs+/KJs+/QJs/JTs/AJo+/KQo'
    elif hero_pos == 'SB':
        range_hint = '前45%手牌（vs BB）：接近 BTN 範圍'
    else:
        range_hint = '參考位置開牌範圍表'

    steal_recommended = ev_steal > 0.05

    reasons = []
    if ev_steal > 0:
        reasons.append(f'竊取 EV = +{ev_steal:.2f}BB（正期望值）')
    else:
        reasons.append(f'竊取 EV = {ev_steal:.2f}BB（謹慎竊取）')
    if bb_defend_too_tight:
        reasons.append(f'BB 防守過緊（棄牌率 {bb_f:.0%} > MDF {1-bb_mdf:.0%}）→ 積極竊取')
    reasons.append(f'雙方棄牌率 {both_f:.0%}')

    return StealResult(
        hero_pos           = hero_pos,
        open_size_bb       = open_size_bb,
        sb_fold_rate       = sb_f,
        bb_fold_rate       = bb_f,
        both_fold_rate     = both_f,
        ev_steal           = round(ev_steal, 3),
        ev_limp_sb         = round(ev_limp, 3),
        steal_recommended  = steal_recommended,
        optimal_freq       = round(optimal_freq, 2),
        bb_mdf             = round(bb_mdf, 3),
        sb_mdf             = round(sb_mdf, 3),
        bb_defend_too_tight = bb_defend_too_tight,
        reasoning          = '；'.join(reasons),
        steal_range_hint   = range_hint,
    )


def calc_defense_ev(
    hero_pos:        str,    # 'BB' or 'SB'
    villain_pos:     str,
    open_size_bb:    float = 2.5,
    villain_equity:  float = 0.55,    # 開牌者翻後平均勝率
    villain_fold_3b: float = 0.55,    # 對手對 3-bet 的棄牌率
) -> DefenseResult:
    """
    計算 BB/SB 防守的 EV，判斷跟注/3-bet/棄牌哪個最優。

    Args:
        hero_pos:       英雄位置 (BB/SB)
        villain_pos:    開牌者位置
        open_size_bb:   開牌注大小
        villain_equity: 對手翻後平均勝率
        villain_fold_3b: 對手對 3-bet 的棄牌率
    """
    hero_equity = 1 - villain_equity

    # BB 跟注額
    if hero_pos == 'BB':
        call_amount = open_size_bb - 1.0   # 已有 1BB 在底池
    else:  # SB
        call_amount = open_size_bb - 0.5

    pot_after_call = 1.5 + open_size_bb + call_amount

    # 底池賠率（最低需要的勝率）
    pot_odds_needed = call_amount / (1.5 + open_size_bb + call_amount - call_amount + call_amount)
    pot_odds_needed = call_amount / (pot_after_call)

    # MDF
    mdf = 1 - (open_size_bb - 1.0) / (1.5 + open_size_bb)

    # EV(call) 估算
    ev_call = hero_equity * pot_after_call - call_amount

    # EV(3-bet) 估算
    # 3-bet 尺寸約 3.5x 開牌注 + 盲注
    three_size = open_size_bb * 3.5 + 1.0
    pot_after_3b = 1.5 + open_size_bb + three_size
    # 對手棄牌部分
    ev_3b_fold_part = villain_fold_3b * (1.5 + open_size_bb)
    # 對手跟注部分（英雄 IP 劣勢，勝率打折）
    ev_3b_call_part = (1 - villain_fold_3b) * (
        hero_equity * 0.9 * (pot_after_3b * 2) - three_size
    )
    ev_3bet = ev_3b_fold_part + ev_3b_call_part

    # 建議行動
    defense_freq = mdf   # 最低防守頻率

    # 按位置調整
    pos_defend_adj = {
        'BTN': -0.05, 'CO': -0.02, 'HJ': +0.02, 'UTG': +0.08
    }
    defense_freq = max(0.20, defense_freq + pos_defend_adj.get(villain_pos, 0))

    if ev_3bet > ev_call and ev_3bet > 0:
        rec = '3-bet'
        reason = f'3-bet EV (+{ev_3bet:.2f}BB) > 跟注 EV ({ev_call:.2f}BB)'
    elif ev_call > 0 and hero_equity >= pot_odds_needed:
        rec = '跟注'
        reason = f'勝率 {hero_equity:.0%} > 底池賠率 {pot_odds_needed:.0%}，跟注正 EV ({ev_call:.2f}BB)'
    else:
        rec = '棄牌'
        reason = f'勝率 {hero_equity:.0%} < 底池賠率 {pot_odds_needed:.0%}，EV 為負'

    # 若對手竊取頻率過高（fish 類），提升防守範圍
    if villain_pos == 'BTN' and villain_fold_3b > 0.60:
        key_note = f'對手 3-bet 棄牌率高（{villain_fold_3b:.0%}），積極 3-bet 反制竊取'
    elif villain_pos in ('UTG', 'HJ') and open_size_bb >= 3.0:
        key_note = '早位大注：僅防守強牌，對手範圍偏緊'
    else:
        key_note = f'MDF = {defense_freq:.0%}：至少這個頻率防守，否則對手純竊取獲利'

    return DefenseResult(
        hero_pos            = hero_pos,
        villain_pos         = villain_pos,
        open_size_bb        = open_size_bb,
        call_amount_bb      = round(call_amount, 2),
        pot_odds            = round(pot_odds_needed, 3),
        mdf                 = round(defense_freq, 3),
        recommended_defense = rec,
        defense_freq        = round(defense_freq, 3),
        ev_fold             = 0.0,
        ev_call_estimate    = round(ev_call, 3),
        ev_3bet_estimate    = round(ev_3bet, 3),
        reasoning           = reason,
        key_note            = key_note,
    )


# ── 全位置竊取 EV 總覽 ───────────────────────────────────────────────────────

def steal_ev_table(open_size_bb: float = 2.5) -> List[Dict]:
    """回傳各位置竊取 EV 對照表。"""
    rows = []
    for pos in ('BTN', 'CO', 'HJ', 'SB'):
        r = calc_steal_ev(pos, open_size_bb)
        rows.append({
            'pos':          pos,
            'ev':           r.ev_steal,
            'both_fold':    r.both_fold_rate,
            'optimal_freq': r.optimal_freq,
            'recommended':  r.steal_recommended,
        })
    return rows


def steal_summary(r: StealResult) -> str:
    """單行摘要。"""
    rec = '[OK] 竊取' if r.steal_recommended else '[X] 謹慎'
    return (f'{r.hero_pos} 竊取 EV={r.ev_steal:+.2f}BB  '
            f'折疊率 {r.both_fold_rate:.0%}  '
            f'頻率 {r.optimal_freq:.0%}  {rec}')


def defense_summary(r: DefenseResult) -> str:
    """單行摘要。"""
    return (f'BB防守 vs {r.villain_pos}：{r.recommended_defense}  '
            f'MDF={r.mdf:.0%}  '
            f'跟注EV={r.ev_call_estimate:+.2f}BB  '
            f'3betEV={r.ev_3bet_estimate:+.2f}BB')
