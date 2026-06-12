"""
MDF（最低防守頻率）、Alpha（詐唬保本折疊率）與多街幾何注碼規劃。

核心公式：
  alpha (詐唬保本) = bet / (pot + bet)
    → 對手必須折疊超過 alpha% 才使詐唬有利可圖

  MDF (最低防守頻率) = 1 - alpha = pot / (pot + bet)
    → 防守方必須至少守住 MDF% 的範圍，否則對手可無限詐唬

  Call equity needed = bet / (pot + bet)   （即 alpha，同樣的公式）
    → 要有這麼多的勝率才使跟注為正期望值

幾何注碼 (Geometric Sizing)：
  三街同樣的注碼比例讓 EV 最大化。
  若希望在河牌圈全下，注碼可設計為：
    flop_bet = pot × g
    turn_bet = new_pot × g
    river_bet = new_pot × g
  其中 g = (final_pot / initial_pot)^(1/3) - 1  （三街）
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class BetAnalysis:
    """面對對手下注時的數學分析。"""
    bet:            int
    pot:            int
    # 防守計算
    alpha:          float   # 詐唬保本所需折疊率 (0-1)
    mdf:            float   # 最低防守頻率 (0-1)
    equity_needed:  float   # 跟注所需最低勝率 (=alpha)
    # 詮釋
    mdf_pct:        int
    alpha_pct:      int
    pot_odds_str:   str     # 如 "2.5:1"
    desc_zh:        str


@dataclass
class GeometricPlan:
    """三街幾何注碼規劃。"""
    initial_pot:    int
    hero_stack:     int
    streets_left:   int     # 2=翻轉河, 1=轉河, 0=河
    target_shove:   bool    # 是否計畫在最後一街全下
    # 每街建議注碼
    flop_bet:       Optional[int]
    turn_bet:       Optional[int]
    river_bet:      Optional[int]
    # 摘要
    growth_factor:  float   # 每街成長倍數
    desc_zh:        str


def analyse_bet(bet: int, pot: int) -> BetAnalysis:
    """
    分析面對對手下注 bet（底池 pot）時的數學。
    """
    if pot <= 0 or bet <= 0:
        return BetAnalysis(bet, pot, 0.5, 0.5, 0.5, 50, 50, '1:1', '資料不足')

    total   = pot + bet
    alpha_v = bet / total           # 詐唬保本折疊率
    mdf_v   = 1.0 - alpha_v         # = pot / total

    # 底池賠率字串，如 "2.5:1" 表示跟注 1 可贏 2.5
    if bet > 0:
        po_ratio = f'{pot / bet:.1f}:1'
    else:
        po_ratio = '∞:1'

    # 描述
    if alpha_v > 0.60:
        desc = f'大額下注（{bet/pot*100:.0f}%底池）— 需要 {int(alpha_v*100)}% 的範圍棄牌才能詐唬獲利'
    elif alpha_v > 0.40:
        desc = f'標準下注（{bet/pot*100:.0f}%底池）— 需守住至少 {int(mdf_v*100)}% 的範圍'
    else:
        desc = f'小額下注（{bet/pot*100:.0f}%底池）— 很難詐唬，MDF={int(mdf_v*100)}%'

    return BetAnalysis(
        bet          = bet,
        pot          = pot,
        alpha        = alpha_v,
        mdf          = mdf_v,
        equity_needed= alpha_v,
        mdf_pct      = int(mdf_v * 100),
        alpha_pct    = int(alpha_v * 100),
        pot_odds_str = po_ratio,
        desc_zh      = desc,
    )


def geometric_plan(
    pot:          int,
    stack:        int,
    streets_left: int = 2,       # 2=翻→轉→河, 1=轉→河
    target_spr:   float = 0.0,   # 目標 SPR（0=全下）
) -> GeometricPlan:
    """
    計算幾何注碼計畫，讓每街注碼均等地消耗籌碼。

    streets_left:
      2 → 還有翻牌/轉牌/河牌三街（flop為起始）
      1 → 還有轉牌/河牌兩街
      0 → 只剩河牌一街

    target_spr:
      0 → 計畫在最後一街全下
      >0 → 保留此 SPR

    回傳每街的建議注碼。
    """
    if pot <= 0 or stack <= 0 or streets_left < 1:
        return GeometricPlan(pot, stack, streets_left, True, None, None, None, 1.0, '無法計算')

    target_shove = (target_spr == 0)
    final_stack  = stack if target_shove else int(stack * target_spr)

    # 幾何成長因子：讓每街 bet/pot 比例相同
    # 若 N 街後底池從 P 成長到 P+2*bet per street*n，全下時 pot ≈ stack+pot
    # 簡化：bet_i = g * pot_i，pot_{i+1} = pot_i + 2*bet_i = pot_i*(1+2g)
    # 經過 N 街：pot_N = pot * (1+2g)^N
    # 要讓 pot_N ≈ stack：g = ((stack/pot)^(1/N) - 1) / 2
    if streets_left > 0 and pot > 0:
        target_pot = min(stack + pot, (stack + pot) * 0.9)  # 不超出籌碼
        ratio      = max(1.01, target_pot / pot)
        g          = (ratio ** (1.0 / streets_left) - 1) / 2
        g          = min(g, 1.5)   # 限制最大注碼比例（不超過1.5倍底池）
    else:
        g = 0.5

    # 計算各街注碼
    bets = []
    cur_pot = pot
    for _ in range(streets_left):
        b = max(1, int(cur_pot * g))
        b = min(b, stack)
        bets.append(b)
        cur_pot = cur_pot + 2 * b  # 對手也跟注

    while len(bets) < 3:
        bets.append(None)

    # 對應各街
    if streets_left == 2:
        flop_bet, turn_bet, river_bet = bets[0], bets[1], bets[2]
    elif streets_left == 1:
        flop_bet, turn_bet, river_bet = None, bets[0], bets[1]
    else:
        flop_bet, turn_bet, river_bet = None, None, bets[0]

    bet_pct = int(g * 100)
    desc = (f'建議每街注碼約 {bet_pct}% 底池，'
            f'{"河牌全下" if target_shove else f"保留 SPR≈{target_spr}"}')

    return GeometricPlan(
        initial_pot  = pot,
        hero_stack   = stack,
        streets_left = streets_left,
        target_shove = target_shove,
        flop_bet     = flop_bet,
        turn_bet     = turn_bet,
        river_bet    = river_bet,
        growth_factor= g,
        desc_zh      = desc,
    )


def bluff_equity_needed(bet: int, pot: int) -> float:
    """詐唬時，手牌被跟注後需要的最低勝率才能使詐唬整體為正期望值。"""
    return bet / (pot + bet) if (pot + bet) > 0 else 0.5


def overbet_analysis(bet: int, pot: int) -> dict:
    """分析超池注碼（overbet）的特性。"""
    ratio = bet / pot if pot > 0 else 1.0
    if ratio > 1.0:
        category = '超池下注'
        note     = f'比底池大 {int((ratio-1)*100)}%，非常極化策略（強牌或詐唬）'
    elif ratio > 0.75:
        category = '大額下注'
        note     = f'{int(ratio*100)}%底池，施加最大壓力'
    elif ratio > 0.45:
        category = '標準下注'
        note     = f'{int(ratio*100)}%底池'
    else:
        category = '小額下注'
        note     = f'{int(ratio*100)}%底池，保護型或薄薄取值'
    mdf_v = pot / (pot + bet) if (pot + bet) > 0 else 0.5
    return {
        'category':    category,
        'ratio':       ratio,
        'mdf':         mdf_v,
        'note':        note,
    }
