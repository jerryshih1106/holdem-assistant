"""
3-bet 詐唬選牌器 (3-bet Bluff Hand Selector)

核心策略邏輯：
  極化 3-bet 範圍 = 純價值牌 + 純詐唬牌（不應包含中間牌如 JTs、QJs）

  最佳詐唬 3-bet 手牌需具備：
    1. 阻擋牌（Blocker）：阻擋對手最強跟注/4-bet範圍
       - Ax（A2s-A5s）：阻擋 AA、AKs、AQs（對手最強繼續範圍）
       - Kx 適度：阻擋 KK、AKs、AKo
    2. 可玩性（Playability）：被跟注後仍有翻牌後 EV
       - 同花 > 雜色；有聽牌潛力 > 純高牌
       - A5s：後門同花順、頂對+頂踢腳潛力
    3. 折疊勝算（Fold Equity）：對手開牌范圍越緊 → 折疊更多
    4. 排除中間牌：JTs、QJs 本身有足夠勝率，應歸入跟注或薄取值

  不適合做詐唬 3-bet（better as call or fold）：
    - 小對子 22-77：隱含賠率最好，多路底池比單挑好
    - 雜色中等牌（J9o、K9o）：被跟注後玩性差

GTO 均衡下 3-bet bluff:value 比例：
  標準 2.5x 3-bet（被call賺(pot+bet)，被fold賺1.5BB）：
    alpha = bet / (pot + bet) = 8.5 / (5.5 + 8.5) ≈ 0.60
    最大詐唬頻率 = (1 - alpha) / alpha ≈ 0.67 倍 value 手數
    實際：每1個value combo，搭配0.5-0.7個bluff combo

使用方式：
    from poker.threbet_bluff import analyze_3bet_bluff
    r = analyze_3bet_bluff('A4s', 'BTN', 'CO')
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from poker.ranges import (
    THREEBET_BTN_VS_CO, THREEBET_BTN_VS_HJ, THREEBET_BTN_VS_UTG,
    THREEBET_CO_VS_UTG, THREEBET_CO_VS_HJ,
    THREEBET_BB_VS_BTN, THREEBET_BB_VS_CO,
    VS3BET_4BET, _r, _merge,
)


@dataclass
class ThreeBetBluffResult:
    hand:               str
    hero_pos:           str
    villain_pos:        str

    # 評分
    bluff_score:        float      # 0-1，越高越適合做 bluff 3-bet
    blocker_score:      float      # 阻擋牌質量（0-1）
    playability_score:  float      # 可玩性（0-1）
    fold_equity_score:  float      # 折疊勝算（0-1）

    # 建議
    is_in_value_range:  bool       # True = 這是 value 3-bet，不是詐唬
    is_good_bluff:      bool       # True = 推薦作為 3-bet 詐唬
    bluff_freq:         float      # 建議詐唬頻率（0-1）
    three_bet_size_bb:  float      # 建議 3-bet 注碼
    blocker_label:      str        # 阻擋牌質量標籤
    playability_label:  str        # 可玩性標籤

    # 解釋
    reasoning:          str
    tips:               List[str] = field(default_factory=list)
    top_alternatives:   List[str] = field(default_factory=list)  # 更好的詐唬選擇


# ── 3-bet 範圍表（整合現有範圍） ─────────────────────────────────────────────

_THREEBET_TABLE: Dict[Tuple[str, str], Dict[str, float]] = {
    ('BTN', 'CO'):  THREEBET_BTN_VS_CO,
    ('BTN', 'HJ'):  THREEBET_BTN_VS_HJ,
    ('BTN', 'UTG'): THREEBET_BTN_VS_UTG,
    ('CO',  'UTG'): THREEBET_CO_VS_UTG,
    ('CO',  'HJ'):  THREEBET_CO_VS_HJ,
    ('BB',  'BTN'): THREEBET_BB_VS_BTN,
    ('BB',  'CO'):  THREEBET_BB_VS_CO,
}

# 純 value 4-bet 手牌（永遠不做詐唬）
_PURE_VALUE = set(VS3BET_4BET.keys()) | {'AA', 'KK', 'QQ', 'JJ', 'AKs', 'AKo'}

# 各手牌的阻擋牌評分（對抗典型3-bet的反應）
# 目標：阻擋對手會「繼續」的手牌（4-bet/call）
# 最強 blocker：A（阻擋 AA、AK、AQ = 對手3-bet後最常繼續的手牌）
_BLOCKER_SCORE: Dict[str, float] = {}


def _compute_blocker_score(hand: str) -> float:
    """
    計算手牌對對手繼續範圍的阻擋強度。

    阻擋對手價值範圍（他們 4-bet 或 call 我的 3-bet）：
      AA, KK, QQ, JJ → value 4-bet 手牌
      AKs, AKo, AQs  → 常見價值繼續

    Ace 阻擋 AA(6 combos→3)、AKs(4→2)、AKo(12→8)、AQs(4→2) → 大幅減少 22 combos
    King 阻擋 KK(6→3)、AKs(4→2)、AKo(12→8) → 減少 16 combos
    """
    if len(hand) == 2:
        r = hand[0]
    elif len(hand) == 3:
        r = hand[0]
    else:
        return 0.0

    rank_map = {'A': 0.95, 'K': 0.55, 'Q': 0.30, 'J': 0.15, 'T': 0.08}

    # 主牌阻擋
    score = rank_map.get(r, 0.0)

    # 副牌加成（若也有高牌）
    if len(hand) == 3:
        r2 = hand[1]
        score += rank_map.get(r2, 0.0) * 0.15

    return min(1.0, score)


def _compute_playability(hand: str) -> float:
    """
    評估手牌被跟注後的可玩性（suited > offsuit, connected > gapped）。

    被 3-bet 跟注後，我們通常是 IP（BTN/CO），在單挑多街需要能繼續的牌。
    高可玩性 = 有可能命中 top pair + 有後門 draws 的套牌。
    """
    if len(hand) == 2:
        # 對子：小對子可玩性低（錯失翻牌面更多），大對子可玩性高
        rank_val = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,'7':7,
                    '6':6,'5':5,'4':4,'3':3,'2':2}.get(hand[0], 0)
        return min(1.0, rank_val / 14 * 0.8)  # AA=0.8, 22=0.11

    r1, r2, stype = hand[0], hand[1], hand[2]
    rank_v = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,'7':7,
              '6':6,'5':5,'4':4,'3':3,'2':2}
    rv1 = rank_v.get(r1, 0)
    rv2 = rank_v.get(r2, 0)

    # 基礎分：同花 vs 雜色
    base = 0.55 if stype == 's' else 0.20

    # 連張加分
    gap = rv1 - rv2
    if gap <= 1:   base += 0.20    # 連張（JTs、65s）
    elif gap == 2: base += 0.10    # 一格（J9s）
    elif gap >= 5: base -= 0.10    # 大跨距（A2s、K7s）— 被call後不好打

    # Ax suited 特殊加分：後門 nut flush 潛力強
    if r1 == 'A' and stype == 's':
        base += 0.15

    # 高牌加分：翻牌有更多機會命中頂對
    base += min(0.10, (rv1 - 7) * 0.02)

    return max(0.0, min(1.0, base))


def _compute_fold_equity(hero_pos: str, villain_pos: str, villain_pfr: float = 0.25) -> float:
    """
    估算折疊勝算（對手繼續3-bet的頻率越高 → 折疊勝算越低）。

    典型對手 3-bet 後的繼續率：
      vs UTG 3-bet：對手繼續約 45-50%（對手範圍緊，fold 更多）
      vs BTN 3-bet：對手繼續約 55-65%（對手範圍寬，fold 更少）
    """
    # 位置越強，對手開牌範圍越寬，3-bet 後對手繼續率越高
    pos_adjust = {'UTG': +0.05, 'HJ': +0.02, 'CO': 0.0, 'BTN': -0.05, 'SB': -0.02, 'BB': -0.08}
    base_fold  = 0.50 + pos_adjust.get(villain_pos, 0.0)

    # 英雄位置越好，3-bet 的折疊勝算越高（IP 3-bet 更有威脅性）
    hero_adj = {'BTN': +0.05, 'CO': +0.02, 'BB': -0.05, 'SB': -0.08}.get(hero_pos, 0.0)
    fold_rate = max(0.20, min(0.80, base_fold + hero_adj))

    return round(fold_rate, 2)


def _is_value_hand(hand: str, threebet_range: Dict[str, float]) -> Tuple[bool, float]:
    """檢查是否為純 value 手牌（不應用作詐唬）。"""
    if hand in _PURE_VALUE:
        return True, 1.0
    freq = threebet_range.get(hand, 0.0)
    # freq=1.0 且是高頻出現在範圍 → 視為 value
    return freq >= 0.9, freq


# ── 最佳詐唬候選手牌（位置對應） ─────────────────────────────────────────────

_TOP_BLUFFS_BY_POS: Dict[Tuple[str, str], List[str]] = {
    ('BTN', 'CO'):  ['A5s','A4s','A3s','A2s','K5s','K4s','K3s','76s','65s','54s'],
    ('BTN', 'HJ'):  ['A5s','A4s','A3s','K5s','K4s','75s','64s'],
    ('BTN', 'UTG'): ['A5s','A4s','K4s','K3s'],
    ('CO',  'UTG'): ['A5s','A4s'],
    ('CO',  'HJ'):  ['A5s','A4s','A3s','K5s'],
    ('BB',  'BTN'): ['A5s','A4s','A3s','A2s','K5s','K4s','65s','54s','87s'],
    ('BB',  'CO'):  ['A5s','A4s','A3s','K5s','K4s','76s'],
}


def analyze_3bet_bluff(
    hand:         str,
    hero_pos:     str,
    villain_pos:  str,
    villain_pfr:  float = 0.25,     # 對手 PFR（HUD）
    open_size_bb: float = 2.5,      # 對手開牌注大小
    stack_bb:     float = 100.0,    # 有效籌碼
) -> ThreeBetBluffResult:
    """
    分析給定手牌作為 3-bet 詐唬的適合程度。

    Args:
        hand:         英雄手牌（如 'A5s'、'76s'）
        hero_pos:     英雄位置（'BTN'/'CO'/'BB'...）
        villain_pos:  對手位置（開牌者）
        villain_pfr:  對手 PFR（HUD 數據）
        open_size_bb: 對手開牌注大小
        stack_bb:     有效籌碼
    """
    pos_key = (hero_pos.upper(), villain_pos.upper())

    # 取得 3-bet 範圍
    threebet_range = _THREEBET_TABLE.get(pos_key, {})

    # ── 分析各維度 ───────────────────────────────────────────────────────────
    blocker   = _compute_blocker_score(hand)
    playable  = _compute_playability(hand)
    fold_eq   = _compute_fold_equity(hero_pos, villain_pos, villain_pfr)

    is_value, value_freq = _is_value_hand(hand, threebet_range)

    # 綜合詐唬分
    # 權重：阻擋牌 40% + 可玩性 30% + 折疊勝算 30%
    bluff_score_raw = blocker * 0.40 + playable * 0.30 + fold_eq * 0.30

    # 若是 value 手牌則詐唬分強制為 0
    if is_value:
        bluff_score = 0.0
    else:
        # 在範圍內（freq>0.3）的手牌有更高頻率詐唬
        in_range_bonus = min(0.10, threebet_range.get(hand, 0.0) * 0.15)
        bluff_score = min(1.0, bluff_score_raw + in_range_bonus)

    # ── 建議 3-bet 頻率 ──────────────────────────────────────────────────────
    if is_value:
        bluff_freq = 0.0
        is_good    = False
    elif bluff_score >= 0.60:
        bluff_freq = min(1.0, bluff_score * 0.90)
        is_good    = True
    elif bluff_score >= 0.40:
        bluff_freq = bluff_score * 0.60
        is_good    = True
    else:
        bluff_freq = 0.0
        is_good    = False

    # ── 3-bet 注碼建議 ───────────────────────────────────────────────────────
    if hero_pos in ('BTN', 'CO'):
        three_bet_bb = round(open_size_bb * 3.0, 1)      # IP：3x 開牌注
    else:
        three_bet_bb = round(open_size_bb * 3.5 + 1.0, 1)  # OOP：稍大

    # ── 標籤 ─────────────────────────────────────────────────────────────────
    blocker_label = (
        '極優（Ace blocker）' if blocker >= 0.90 else
        '優良（King blocker）' if blocker >= 0.50 else
        '普通（Queen blocker）' if blocker >= 0.25 else
        '無明顯阻擋牌'
    )
    play_label = (
        '高（同花+連張）' if playable >= 0.65 else
        '中（同花）' if playable >= 0.45 else
        '低（雜色/跨距大）'
    )

    # ── 推薦替代選擇 ─────────────────────────────────────────────────────────
    top_alts = _TOP_BLUFFS_BY_POS.get(pos_key, ['A5s', 'A4s', 'K5s'])
    top_alts = [h for h in top_alts if h != hand][:3]

    # ── 理由 ─────────────────────────────────────────────────────────────────
    reasons = []
    if is_value:
        reasons.append(f'{hand} 是 value 3-bet 手牌（非詐唬用途，頻率{value_freq:.0%}）')
    else:
        if blocker >= 0.90:
            reasons.append(f'Ace blocker：阻擋對手 AA/AK/AQ {blocker:.0%} combo 減少')
        elif blocker >= 0.50:
            reasons.append(f'King blocker：阻擋對手 KK/AK {blocker:.0%} combo 減少')
        else:
            reasons.append(f'阻擋牌效果有限（{blocker:.0%}）')
        reasons.append(f'可玩性{play_label}（{playable:.0%}）')
        reasons.append(f'對手預估折疊率{fold_eq:.0%}（{villain_pos} vs {hero_pos}）')
        if is_good:
            reasons.append(f'綜合詐唬分 {bluff_score:.0%} → 推薦頻率 {bluff_freq:.0%}')
        else:
            reasons.append(f'綜合詐唬分 {bluff_score:.0%} 偏低 → 建議棄牌或跟注')

    tips = [
        f'GTO 詐唬:價值比例約 0.5:1（每 1 個 value combo，搭配 0.5 個 bluff）',
        f'推薦詐唬候選：{", ".join(top_alts)}',
    ]
    if hero_pos in ('SB', 'BB'):
        tips.append('OOP 3-bet 詐唬需更高阻擋分，否則被跟注後難以獲利')
    if stack_bb < 40:
        tips.append(f'短籌碼 {stack_bb:.0f}BB：3-bet = 接近全下，只用強牌/極強詐唬')

    return ThreeBetBluffResult(
        hand               = hand,
        hero_pos           = hero_pos,
        villain_pos        = villain_pos,
        bluff_score        = round(bluff_score, 3),
        blocker_score      = round(blocker, 3),
        playability_score  = round(playable, 3),
        fold_equity_score  = round(fold_eq, 3),
        is_in_value_range  = is_value,
        is_good_bluff      = is_good,
        bluff_freq         = round(bluff_freq, 2),
        three_bet_size_bb  = three_bet_bb,
        blocker_label      = blocker_label,
        playability_label  = play_label,
        reasoning          = '；'.join(reasons),
        tips               = tips,
        top_alternatives   = top_alts,
    )


def rank_bluff_candidates(
    hands:        List[str],
    hero_pos:     str,
    villain_pos:  str,
    villain_pfr:  float = 0.25,
    open_size_bb: float = 2.5,
) -> List[ThreeBetBluffResult]:
    """批次排序，回傳詐唬分由高到低的結果列表。"""
    results = [analyze_3bet_bluff(h, hero_pos, villain_pos, villain_pfr, open_size_bb)
               for h in hands]
    return sorted(results, key=lambda r: r.bluff_score, reverse=True)


def bluff3b_summary(r: ThreeBetBluffResult) -> str:
    """單行摘要。"""
    if r.is_in_value_range:
        return f'{r.hand}@{r.hero_pos} → Value 3-bet（非詐唬）'
    status = '推薦詐唬' if r.is_good_bluff else '不建議詐唬'
    return (f'{r.hand}@{r.hero_pos} vs {r.villain_pos}  {status}  '
            f'詐唬分{r.bluff_score:.0%}  建議freq{r.bluff_freq:.0%}  '
            f'注碼{r.three_bet_size_bb:.1f}BB')
