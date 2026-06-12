"""
保護注計算器 (Draw Protection Calculator)

核心問題：「我需要下多少才能正確地讓對手的聽牌跟注是負 EV？」

常見漏洞：翻牌有同花/順子聽牌時直接過牌，讓對手免費抽牌。
這個模組計算：
  1. 目前牌面有哪些聽牌威脅（同花/順子/複合）
  2. 最低下注額讓對手的聽牌跟注是負期望值
  3. 如果過牌（給免費牌）的 EV 損失

──────────────────────────────────────────────────────────
保本下注公式（含隱含賠率調整）：

  對手持聽牌，有 n 張出牌，剩 r 張牌：
    立即對手跟注 EV ≤ 0  →  b >= n×P / (r-n)           [純底池賠率]
    含隱含賠率 V = 0.5P    →  b >= n×1.5P / (r-n)        [建議最低值]

  翻牌(r=47) 同花聽牌(9出)：b_min = 9P/38 = 24% pot
  翻牌含隱含(×1.5)：b_rec = 9×1.5P/38 = 36% pot
  複合聽牌(15出)：b_rec = 15×1.5P/32 = 70% pot

免費牌 EV 損失（每手）：
  EV_loss = pot × (n/r) × 0.75  （對手抽牌後贏得底池的 75% 保守估計）
──────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DrawThreat:
    draw_type:    str   # 'flush'/'oesd'/'gutshot'/'combo'/'backdoor_flush'
    outs:         int
    threat_level: str   # 'high'/'medium'/'low'
    type_zh:      str


@dataclass
class DrawProtectionResult:
    # 威脅偵測
    threats:            List[DrawThreat]
    primary_threat:     Optional[DrawThreat]   # most dangerous draw
    total_primary_outs: int                    # outs of primary threat

    # 保護注碼
    min_pot_pct:        float   # minimum bet % of pot (pure pot odds, no implied)
    rec_pot_pct:        float   # recommended % (accounts for ~0.5 pot implied odds)
    min_bet_bb:         float   # min in BB
    rec_bet_bb:         float   # recommended in BB

    # 免費牌損失
    free_card_ev_loss:  float   # EV lost per hand if hero checks (BB)

    # 街道資訊
    street:             str     # 'flop'/'turn'
    cards_remaining:    int     # 47 for flop, 46 for turn

    # 是否需要保護
    protection_needed:  bool    # True if any high/medium draw threat exists
    reasoning:          str
    summary_zh:         str


# ─── 內部輔助函數 ──────────────────────────────────────────────────────────────

_RANK_MAP = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
    '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14,
}


def _rank(card: str) -> int:
    return _RANK_MAP.get(card[0].upper(), 0)


def _suit(card: str) -> str:
    return card[-1].lower()


def _max_consecutive(ranks: List[int]) -> int:
    """Return the length of the longest consecutive sequence in the rank list."""
    if not ranks:
        return 0
    unique = sorted(set(ranks))
    best, cur = 1, 1
    for i in range(1, len(unique)):
        if unique[i] == unique[i - 1] + 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    # Ace can play as 1 for A-2-3-4-5 straights
    if 14 in unique:
        low_unique = sorted(set([1] + unique))
        cur2 = 1
        for i in range(1, len(low_unique)):
            if low_unique[i] == low_unique[i - 1] + 1:
                cur2 += 1
                best = max(best, cur2)
            else:
                cur2 = 1
    return best


def _detect_draws(community: List[str]) -> List[DrawThreat]:
    """Detect flush/straight draw threats possible given community cards."""
    threats: List[DrawThreat] = []
    n = len(community)
    if n < 3:
        return threats

    # ─── Flush draw ───────────────────────────────────────────────────────────
    suit_counts: dict = {}
    for card in community:
        s = _suit(card)
        suit_counts[s] = suit_counts.get(s, 0) + 1

    max_suit_count = max(suit_counts.values()) if suit_counts else 0

    has_flush_draw = False
    if max_suit_count >= 3:
        has_flush_draw = True
        threats.append(DrawThreat('flush', 9, 'high', '同花聽牌(9出)'))
    elif max_suit_count == 2 and n == 3:
        threats.append(DrawThreat('backdoor_flush', 3, 'low', '暗門同花(3出)'))

    # ─── Straight draw ────────────────────────────────────────────────────────
    # Use a 5-rank sliding window: a gutshot requires 3+ board cards within any
    # span of 5 consecutive rank values (e.g. [7,8,T] in window [6,10]).
    # This prevents false gutshot signals on disconnected boards like A-K-2.
    ranks = [_rank(c) for c in community]

    def _cards_in_window(lo: int, hi: int) -> int:
        return sum(1 for r in ranks if lo <= r <= hi)

    # Also consider Ace as low (1)
    ranks_with_low_ace = ranks + ([1] if 14 in ranks else [])

    def _cards_in_window_low(lo: int, hi: int) -> int:
        return sum(1 for r in ranks_with_low_ace if lo <= r <= hi)

    max_in_5 = max(
        max((_cards_in_window(lo, lo + 4) for lo in range(1, 11)), default=0),
        max((_cards_in_window_low(lo, lo + 4) for lo in range(1, 6)), default=0),
    )

    has_straight_draw = False
    if max_in_5 >= 3:
        has_straight_draw = True
        consec = _max_consecutive(ranks)
        if has_flush_draw:
            threats = [t for t in threats if t.draw_type != 'flush']
            threats.append(DrawThreat('combo', 15, 'high', '複合聽牌(15出)'))
        elif consec >= 3:
            threats.append(DrawThreat('oesd', 8, 'high', '順子聽牌(8出)'))
        else:
            threats.append(DrawThreat('gutshot', 4, 'medium', '卡肚聽牌(4出)'))

    return threats


def _primary_threat(threats: List[DrawThreat]) -> Optional[DrawThreat]:
    """Return the most dangerous draw threat."""
    if not threats:
        return None
    order = {'high': 0, 'medium': 1, 'low': 2}
    return sorted(threats, key=lambda t: (order.get(t.threat_level, 3), -t.outs))[0]


def _protection_bet(n: int, pot_bb: float, r: int) -> tuple:
    """
    Return (min_pct, rec_pct, min_bb, rec_bb).
    min: price out draws with no implied odds
    rec: price out draws with 0.5×pot implied odds
    """
    if r <= n:
        return 1.0, 1.0, pot_bb, pot_bb   # edge case: more outs than remaining cards

    min_pct = n / (r - n)                  # n*P/(r-n) / P
    rec_pct = n * 1.5 / (r - n)            # 0.5 pot implied odds
    rec_pct = max(rec_pct, 0.50)           # floor: always bet at least 50% pot

    min_bb = round(min_pct * pot_bb, 1)
    rec_bb = round(rec_pct * pot_bb, 1)
    return round(min_pct, 3), round(min_pct * 1.5, 3), min_bb, rec_bb


# ─── 公共 API ─────────────────────────────────────────────────────────────────

def analyze_draw_protection(
    community:  List[str],
    pot_bb:     float,
    hero_equity: float = 0.65,   # hero's current win probability (0-1)
    n_opponents: int  = 1,
) -> DrawProtectionResult:
    """
    Analyze draw threats and calculate protection bet recommendations.

    Args:
        community:    Community cards (list of card strings e.g. ['Ah','Kd','9h'])
        pot_bb:       Current pot in big blinds
        hero_equity:  Hero's win probability 0-1 (from MC equity)
        n_opponents:  Number of opponents in the hand
    """
    n_comm = len(community)
    if n_comm == 3:
        street = 'flop'
        cards_remaining = 47
    elif n_comm == 4:
        street = 'turn'
        cards_remaining = 46
    else:
        return DrawProtectionResult(
            threats=[], primary_threat=None, total_primary_outs=0,
            min_pot_pct=0, rec_pot_pct=0, min_bet_bb=0, rec_bet_bb=0,
            free_card_ev_loss=0, street='river', cards_remaining=44,
            protection_needed=False,
            reasoning='河牌無需保護注分析（已無更多公牌）',
            summary_zh='',
        )

    threats = _detect_draws(community)

    # Multiway: draws are more dangerous (multiple opponents could be drawing)
    if n_opponents >= 2 and threats:
        for t in threats:
            if t.threat_level == 'medium':
                t.threat_level = 'high'
            if t.outs < 12:
                t.outs = min(t.outs + 2, 15)   # effectively more outs multiway

    primary = _primary_threat(threats)
    primary_outs = primary.outs if primary else 0

    if primary and primary.threat_level in ('high', 'medium'):
        min_pct_pure, min_pct_implied, min_bb, rec_bb = _protection_bet(
            primary_outs, pot_bb, cards_remaining
        )
        rec_pot_pct = min_pct_implied
        protection_needed = True
    else:
        min_pct_pure = 0.0
        rec_pot_pct  = 0.33   # standard sizing even without major draws
        min_bb       = round(0.25 * pot_bb, 1)
        rec_bb       = round(0.33 * pot_bb, 1)
        protection_needed = False

    # Free card EV loss: if hero checks, villain gets a free look at next card
    # EV_loss = pot × P(draw completes) × P(villain wins when draw completes)
    if primary and primary_outs > 0:
        p_complete    = primary_outs / cards_remaining
        p_win_on_hit  = 0.80    # conservative: villain wins ~80% when draw completes
        free_card_ev_loss = round(pot_bb * p_complete * p_win_on_hit * (1 - hero_equity), 2)
    else:
        free_card_ev_loss = 0.0

    # Reasoning
    if primary:
        draw_kind = '同花' if 'flush' in primary.draw_type else '順子'
        reasoning = (
            f'{street}面有{draw_kind}聽牌威脅：'
            f'{primary.outs}張出牌，建議下注 >= {rec_pot_pct:.0%} 底池（{rec_bb:.0f}BB）'
            f'讓對手跟注負期望值；過牌損失約 {free_card_ev_loss:.1f}BB/手'
        )
    else:
        reasoning = f'{street}牌面威脅低，無強制保護注需求，標準注碼即可'

    # Summary line (≤85 chars)
    if protection_needed and primary:
        draw_label = primary.type_zh
        summary_zh = (
            f'[保護注] {draw_label}  '
            f'>={rec_pot_pct:.0%}pot={rec_bb:.0f}BB  '
            f'免費牌損失-{free_card_ev_loss:.1f}BB'
        )
    else:
        summary_zh = ''    # no display needed if no major threat

    return DrawProtectionResult(
        threats            = threats,
        primary_threat     = primary,
        total_primary_outs = primary_outs,
        min_pot_pct        = round(min_pct_pure, 3),
        rec_pot_pct        = round(rec_pot_pct, 3),
        min_bet_bb         = min_bb,
        rec_bet_bb         = rec_bb,
        free_card_ev_loss  = free_card_ev_loss,
        street             = street,
        cards_remaining    = cards_remaining,
        protection_needed  = protection_needed,
        reasoning          = reasoning,
        summary_zh         = summary_zh[:85],
    )


def draw_protection_summary(r: DrawProtectionResult) -> str:
    """Single-line overlay summary (up to 85 chars). Returns '' if no major threat."""
    return r.summary_zh
