"""
翻前開牌 EV 速查表 (Preflop Open EV Lookup)

給定手牌和位置，回傳開牌/棄牌/跟注/3-bet 的預期 EV（BB/100 hands）。

核心問題：「我應該從這個位置開這手牌嗎？EV 有多少？」

計算邏輯：
  EV(open) = 竊取成功機率 × 竊取收益
            + 被跟注機率 × 翻後 EV（取決於手牌實力和位置）
            + 被 3-bet 機率 × (4-bet EV or 棄牌 EV)

簡化版（基於大量撲克研究的近似值）：
  - 竊取成功率：BTN 60%+, SB 55%, CO 50%, HJ 45%, UTG 40%
  - 各手牌翻後勝率 + 位置紅利 → 估算 EV

輸出：
  EV estimate (BB/100 hands)
  Recommendation: Open/RFI/3BET/FOLD + confidence
  Position premium (有位置比無位置多幾BB/100)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class PreflopEV:
    hand:              str
    position:          str
    action:            str       # 'open'/'3bet'/'call'/'fold'
    ev_estimate:       float     # BB/100 估算
    ev_vs_fold:        float     # 比純棄牌多賺幾BB/100
    confidence:        str       # 'high'/'medium'/'low'
    steal_success_pct: float     # 竊取成功估算
    postflop_edge:     float     # 翻後優勢估算
    recommendation:    str       # 中文建議
    notes:             str       # 額外說明


# ── 翻前手牌強度（基準勝率 vs 隨機範圍）─────────────────────────────────────

_HAND_STRENGTH: Dict[str, float] = {
    # Pairs
    'AA':0.852,'KK':0.823,'QQ':0.799,'JJ':0.775,'TT':0.751,
    '99':0.720,'88':0.693,'77':0.663,'66':0.632,'55':0.600,
    '44':0.569,'33':0.536,'22':0.503,
    # Suited broadways + aces
    'AKs':0.672,'AQs':0.660,'AJs':0.652,'ATs':0.644,'A9s':0.631,
    'A8s':0.625,'A7s':0.618,'A6s':0.613,'A5s':0.614,'A4s':0.607,
    'A3s':0.601,'A2s':0.595,
    'KQs':0.635,'KJs':0.627,'KTs':0.620,'K9s':0.612,'K8s':0.604,
    'K7s':0.597,'K6s':0.590,'K5s':0.583,'K4s':0.576,'K3s':0.569,'K2s':0.563,
    'QJs':0.615,'QTs':0.608,'Q9s':0.598,'Q8s':0.590,'Q7s':0.581,
    'JTs':0.608,'J9s':0.596,'J8s':0.586,'J7s':0.576,
    'T9s':0.596,'T8s':0.583,'T7s':0.572,
    '98s':0.580,'97s':0.567,'87s':0.568,'76s':0.554,'65s':0.542,
    '54s':0.528,'43s':0.514,'32s':0.499,
    # Offsuit broadways
    'AKo':0.651,'AQo':0.636,'AJo':0.625,'ATo':0.615,'A9o':0.603,
    'KQo':0.613,'KJo':0.603,'KTo':0.593,'K9o':0.583,
    'QJo':0.587,'QTo':0.578,'Q9o':0.567,
    'JTo':0.573,'J9o':0.561,'T9o':0.557,'98o':0.543,
}

# ── 各位置基礎竊取成功率 ─────────────────────────────────────────────────────

_STEAL_SUCCESS: Dict[str, float] = {
    'BTN': 0.62,    # 2 players behind
    'CO':  0.53,    # 3 players behind
    'HJ':  0.44,    # 4 players behind
    'LJ':  0.38,    # 5 players behind
    'UTG1':0.34,    # 6 players behind
    'UTG': 0.32,    # 6+ players behind
    'SB':  0.58,    # vs BB only
    'BB':  0.0,
}

# ── 各位置翻後位置紅利（BB/100，有位置比無位置優勢）──────────────────────────

_POSITION_EDGE: Dict[str, float] = {
    'BTN': 6.0,    # BTN 最強位置
    'CO':  3.5,
    'HJ':  2.0,
    'LJ':  1.0,
    'UTG1':0.5,
    'UTG': 0.0,    # 基準
    'SB': -3.0,    # OOP 劣勢
    'BB':  0.0,    # BB 防守，不算常規開牌
}

# ── 竊取收益（若成功，贏得底池）────────────────────────────────────────────────

_BLINDS_BB = 1.5    # SB(0.5) + BB(1.0) = 1.5BB
_OPEN_SIZE  = 2.5   # 標準開牌到 2.5BB


def _hand_strength(hand: str) -> float:
    return _HAND_STRENGTH.get(hand, _fallback_strength(hand))


def _fallback_strength(hand: str) -> float:
    """
    校正擬合公式（base=0.423，各係數以已知勝率校準）：
      AKo≈0.651, 72o≈0.370, 98s≈0.580 — 誤差 < 3%
    """
    ranks = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,
             '7':7,'6':6,'5':5,'4':4,'3':3,'2':2}
    r1 = ranks.get(hand[0], 7)
    r2 = ranks.get(hand[1] if len(hand) > 1 else '2', 3)
    if r1 < r2:
        r1, r2 = r2, r1
    if r1 == r2:
        return 0.50 + (r1 - 2) / 24   # pairs: 22=50%, AA=85%
    gap    = r1 - r2
    r1n    = (r1 - 2) / 12            # normalise 0–1
    r2n    = (r2 - 2) / 12
    suited = 0.025 if hand.endswith('s') else 0.0
    gap_pen = max(0, gap - 1) * 0.034
    return max(0.34, min(0.70, 0.423 + 0.200 * r1n + 0.030 * r2n + suited - gap_pen))


def calc_open_ev(
    hand:              str,
    position:          str   = 'BTN',
    villain_pfr:       float = 0.20,    # 對手的 PFR（用於估算 3-bet 頻率）
    stack_bb:          float = 100.0,
    open_size_bb:      float = 2.5,
) -> PreflopEV:
    """
    估算從指定位置開牌的 EV（BB/100）。

    Args:
        hand:         手牌字串 (e.g. 'AKo', 'QJs', 'TT')
        position:     英雄位置 ('UTG'/'HJ'/'CO'/'BTN'/'SB'/'BB')
        villain_pfr:  對手 PFR 小數（用於估算被 3-bet 機率）
        stack_bb:     有效籌碼（BB）
        open_size_bb: 開牌注碼

    Returns:
        PreflopEV
    """
    strength    = _hand_strength(hand)
    steal_pct   = _STEAL_SUCCESS.get(position, 0.50)
    pos_edge_bb = _POSITION_EDGE.get(position, 0.0)

    # 被 3-bet 的機率（取決於對手 PFR 和位置）
    threebet_pct = villain_pfr * 0.35    # 大約 35% 的 PFR 會 3-bet

    # 翻後勝率估算（基準勝率 + 位置紅利）
    postflop_strength = strength - 0.50  # 相對優勢

    # ── EV 計算 ────────────────────────────────────────────────────────────────
    # 公式：EV = P_fold×(+blinds) + P_3bet×EV_3bet + P_call×EV_postflop
    # 所有情境的 EV 均已包含開牌成本的扣除（以 neutral 0 為基準）

    p_steal   = steal_pct * (1 - threebet_pct)
    p_3bet    = threebet_pct
    p_call    = (1 - steal_pct) * (1 - threebet_pct)

    # 情境1：所有人棄牌 → 淨盈 = 盲注
    ev_when_fold = _BLINDS_BB

    # 情境2：遇到 3-bet
    if strength >= 0.78:      # AA/KK/QQ → 4-bet value，大底池獲益
        ev_vs_3bet = strength * 15.0 - open_size_bb
    elif strength >= 0.65:    # JJ/TT/AQs → 跟注 3-bet，近似保本
        ev_vs_3bet = 0.0
    else:                     # 弱牌 → 棄牌，損失開牌注碼
        ev_vs_3bet = -open_size_bb

    # 情境3：被跟注後翻牌
    # 手牌可玩性調整（非同花非連張的弱牌翻後虧更多）
    is_suited = hand.endswith('s')
    is_pair   = (len(hand) == 2 and hand[0] == hand[1])
    r1v = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,
           '7':7,'6':6,'5':5,'4':4,'3':3,'2':2}.get(hand[0], 5)
    r2v = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,
           '7':7,'6':6,'5':5,'4':4,'3':3,'2':2}.get(hand[1] if len(hand)>1 else '2', 3)
    gap_penalty = max(0, abs(r1v - r2v) - 1) * 0.015
    playability = (0.12 if is_suited else 0.0) + (0.05 if is_pair else 0.0) - gap_penalty

    # 翻後 EV = equity × pot + playability_bonus + position_premium
    pot_called    = open_size_bb * 2.0      # 開牌 + 跟注 = ~5BB
    ev_vs_call    = ((strength - 0.50) * pot_called * 2.0
                     + playability * pot_called
                     + pos_edge_bb * 0.08)

    ev_total  = (p_steal * ev_when_fold
                 + p_3bet  * ev_vs_3bet
                 + p_call  * ev_vs_call)

    ev_vs_fold = ev_total

    # ── 建議 ────────────────────────────────────────────────────────────────
    if ev_vs_fold >= 3.0:
        action = 'open'
        rec = f'強烈建議開牌（EV +{ev_vs_fold:.1f}BB/100）'
        conf = 'high'
    elif ev_vs_fold >= 0.5:
        action = 'open'
        rec = f'建議開牌（EV +{ev_vs_fold:.1f}BB/100）'
        conf = 'medium'
    elif ev_vs_fold >= -1.0:
        action = 'fold'
        rec = f'邊緣手牌（EV {ev_vs_fold:.1f}BB/100），依對手調整'
        conf = 'low'
    else:
        action = 'fold'
        rec = f'建議棄牌（EV {ev_vs_fold:.1f}BB/100）'
        conf = 'high'

    # 特殊牌型備註
    notes = ''
    if hand.endswith('s') and strength < 0.62:
        notes += '同花牌隱含賠率佳（set value + flush draws）；'
    if hand[:2] in ('AA','KK','QQ','JJ') and position == 'BB':
        notes += 'BB 位置翻後 OOP，需要更積極下注保護；'
    if position == 'SB' and strength < 0.60:
        notes += 'SB 翻後 OOP 劣勢，邊緣牌謹慎開牌；'

    return PreflopEV(
        hand              = hand,
        position          = position,
        action            = action,
        ev_estimate       = round(ev_total, 2),
        ev_vs_fold        = round(ev_vs_fold, 2),
        confidence        = conf,
        steal_success_pct = steal_pct,
        postflop_edge     = round(postflop_strength, 3),
        recommendation    = rec,
        notes             = notes.rstrip('；') or '—',
    )


def ev_summary(r: PreflopEV) -> str:
    """單行摘要，用於 overlay 顯示。"""
    ev_str = f'+{r.ev_vs_fold:.1f}' if r.ev_vs_fold >= 0 else f'{r.ev_vs_fold:.1f}'
    return (f'{r.position} {r.hand}: {r.action.upper()}  '
            f'EV{ev_str}BB/100  {r.recommendation[:18]}')


def position_ev_table(
    hand:       str,
    villain_pfr: float = 0.20,
) -> str:
    """所有位置的 EV 對比表，用於分析邊緣手牌。"""
    positions = ['BTN', 'CO', 'HJ', 'UTG', 'SB']
    lines = [f'手牌 {hand} 各位置 EV（BB/100）:']
    for pos in positions:
        r = calc_open_ev(hand, pos, villain_pfr)
        marker = 'OK' if r.ev_vs_fold >= 0.5 else ('?' if r.ev_vs_fold >= -1.0 else 'X')
        lines.append(
            f'  {pos:6s}: {marker} EV={r.ev_vs_fold:+.1f}  偷盲成功率{int(r.steal_success_pct*100)}%'
        )
    return '\n'.join(lines)


def quick_open_ev(hand: str, pos: str) -> str:
    """一行快速查詢。"""
    r = calc_open_ev(hand, pos)
    return ev_summary(r)
