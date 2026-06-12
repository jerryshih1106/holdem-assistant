"""
Villain Combo Counter (對手 Combo 計數器)

給定牌面和對手範圍，計算對手可能持有的 value / draw / bluff 組合數量。

最直接回答：「我現在應該跟注這個河牌下注嗎？」
  - 如果 bluff_pct > alpha（保本折疊率），跟注有正 EV
  - 如果 bluff_pct < alpha，棄牌有正 EV

算法：
  1. 從 PUSH_ORDER 取得對手範圍（top VPIP% 手牌）
  2. 枚舉每種手牌的所有花色組合（pair=6, suited=4, offsuit=12 combos）
  3. 移除包含英雄手牌或公牌的 dead combos
  4. 用 treys 評估每個 live combo 對牌面的強度
  5. 分類：value (2p+) / draw / bluff
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import itertools

try:
    from treys import Card, Evaluator
    _TREYS_OK = True
    _evaluator = Evaluator()
except ImportError:
    _TREYS_OK = False
    _evaluator = None

from poker.pushfold import PUSH_ORDER


# ── 手牌等級映射 ───────────────────────────────────────────────────────────────

_RANK_MAP  = {'A':14,'K':13,'Q':12,'J':11,'T':10,
              '9':9,'8':8,'7':7,'6':6,'5':5,'4':4,'3':3,'2':2}
_RANK_CHAR = {14:'A',13:'K',12:'Q',11:'J',10:'T',
              9:'9',8:'8',7:'7',6:'6',5:'5',4:'4',3:'3',2:'2'}
_SUITS = ['s', 'h', 'd', 'c']

# treys 強度分界（lower rank = stronger hand）
_TREYS_TWO_PAIR    = 3325   # 兩對以上都是 value
_TREYS_TOP_PAIR    = 5000   # 頂對+（粗略）
_TREYS_PAIR        = 6185   # 任何對子
# > 6185 = 高牌 (air)


@dataclass
class ComboCount:
    board:           List[str]
    villain_vpip:    float       # 0-1，對手範圍寬度
    hero_hole:       List[str]   # 英雄手牌（blockers）
    total_combos:    int
    value_combos:    int          # 2p+ (two pair, set, straight, flush, FH, quads)
    toppair_combos:  int          # 頂對/超對
    draw_combos:     int          # 聽牌 (flush draw / straight draw)
    bluff_combos:    int          # 廢牌 (air, bottom pair, missed draws on river)
    value_pct:       float        # value / total
    bluff_pct:       float        # bluff / total
    alpha:           float        # break-even fold rate = bet/(pot+bet)
    call_profitable: bool         # bluff_pct > alpha
    ev_call_per_combo: float      # EV of calling (per pot unit)
    summary:         str
    advice:          str


def _hand_to_combos(hand_str: str) -> List[Tuple[str, str]]:
    """
    將手牌字串（e.g. 'AKs', 'AKo', 'TT'）展開為所有花色組合。
    回傳 [(card1, card2), ...] 形式。
    """
    if len(hand_str) < 2:
        return []

    r1 = hand_str[0]
    r2 = hand_str[1]
    suited = hand_str.endswith('s')
    is_pair = (r1 == r2)

    combos = []
    if is_pair:
        # pair: C(4,2) = 6 combos
        for s1, s2 in itertools.combinations(_SUITS, 2):
            combos.append((r1 + s1, r2 + s2))
    elif suited:
        # suited: 4 combos (same suit)
        for s in _SUITS:
            combos.append((r1 + s, r2 + s))
    else:
        # offsuit: 12 combos (different suits)
        for s1 in _SUITS:
            for s2 in _SUITS:
                if s1 != s2:
                    combos.append((r1 + s1, r2 + s2))

    return combos


def _is_flush_draw(cards: List[str]) -> bool:
    """4張牌中有 3 張同花（聽同花）。"""
    if len(cards) < 4:
        return False
    from collections import Counter
    suits = Counter(c[-1] for c in cards)
    return any(v >= 3 for v in suits.values())


def _is_straight_draw(cards: List[str]) -> bool:
    """4張牌中的點數接近順子（OESD 或 gutshot）。"""
    if len(cards) < 4:
        return False
    ranks = sorted(set(_RANK_MAP.get(c[:-1], 0) for c in cards), reverse=True)
    if len(ranks) < 3:
        return False
    for i in range(len(ranks) - 2):
        span = ranks[i] - ranks[i + 2]
        if span <= 3:   # OESD or gutshot
            return True
    return False


def _classify_combo(
    c1: str, c2: str,
    board: List[str],
    is_river: bool,
) -> str:
    """
    分類一個 combo 的強度。
    回傳 'value' / 'toppair' / 'draw' / 'bluff'。
    """
    if _TREYS_OK:
        try:
            board_treys = [Card.new(c) for c in board]
            hand_treys  = [Card.new(c1), Card.new(c2)]
            rank = _evaluator.evaluate(board_treys, hand_treys)

            if rank <= _TREYS_TWO_PAIR:
                return 'value'
            elif rank <= _TREYS_TOP_PAIR:
                return 'toppair'
            elif rank <= _TREYS_PAIR:
                # Has a pair — check if it's draw territory
                if not is_river:
                    all_cards = [c1, c2] + board
                    if _is_flush_draw(all_cards) or _is_straight_draw(all_cards):
                        return 'draw'
                return 'bluff'    # low pair on river or no draw
            else:
                # Air/high card
                if not is_river:
                    all_cards = [c1, c2] + board
                    if _is_flush_draw(all_cards) or _is_straight_draw(all_cards):
                        return 'draw'
                return 'bluff'
        except Exception:
            return 'bluff'   # card conversion error → treat as bluff
    else:
        # treys unavailable — simple fallback: pair on board = value, else bluff
        board_ranks = [c[:-1] for c in board]
        if c1[:-1] in board_ranks or c2[:-1] in board_ranks:
            return 'toppair'
        return 'bluff'


def count_villain_combos(
    board:          List[str],
    villain_vpip:   float       = 0.30,   # 0-1
    hero_hole:      List[str]   = None,
    bet_fraction:   float       = 0.75,   # villain's bet as fraction of pot
    pot_bb:         float       = 10.0,
    villain_pos:    str         = 'BTN',
) -> ComboCount:
    """
    計算對手可能的 combo 分布。

    Args:
        board:          公牌（3-5張）
        villain_vpip:   對手範圍寬度（0-1，0.30 = 30% VPIP）
        hero_hole:      英雄手牌（用作 blockers）
        bet_fraction:   對手的注碼比例（計算 alpha）
        pot_bb:         底池大小
        villain_pos:    對手位置（影響範圍起始寬度）

    Returns:
        ComboCount
    """
    villain_vpip = max(0.05, min(0.95, villain_vpip))
    hero_hole = hero_hole or []
    board     = board or []

    # 死牌集合（英雄手牌 + 公牌）
    dead = set()
    for c in hero_hole + board:
        if c and len(c) >= 2:
            dead.add(c.lower())
            dead.add(c)

    # 取得對手範圍（top N% of PUSH_ORDER by position）
    n_hands = max(1, round(villain_vpip * len(PUSH_ORDER)))
    villain_range = PUSH_ORDER[:n_hands]

    # 枚舉所有 live combos
    value_combos    = 0
    toppair_combos  = 0
    draw_combos     = 0
    bluff_combos    = 0
    total_combos    = 0

    is_river = (len(board) == 5)

    for hand_str in villain_range:
        for c1, c2 in _hand_to_combos(hand_str):
            # 跳過死牌
            if c1 in dead or c2 in dead:
                continue
            # 跳過重複花色（suited 不能有 offsuit 組合等，手牌枚舉已保證）
            total_combos += 1
            cat = _classify_combo(c1, c2, board, is_river)
            if cat == 'value':
                value_combos += 1
            elif cat == 'toppair':
                toppair_combos += 1
            elif cat == 'draw':
                draw_combos += 1
            else:
                bluff_combos += 1

    if total_combos == 0:
        # Fallback
        total_combos = 1
        bluff_combos = 1

    # alpha = break-even fold rate for villain's bluff
    alpha = bet_fraction / (1 + bet_fraction)

    # value + toppair as "value" for calling analysis
    effective_value = value_combos + toppair_combos
    effective_bluff = bluff_combos + draw_combos // 2   # draws count half on river
    if is_river:
        effective_bluff = bluff_combos   # no draws on river

    value_pct = effective_value / total_combos
    bluff_pct = (total_combos - effective_value) / total_combos

    # EV of calling: if villain bluffs B/(V+B) of the time and bets f×pot
    # EV_call = bluff_pct × pot_win - value_pct × call_amount
    call_amount = bet_fraction * pot_bb
    ev_call = bluff_pct * pot_bb - value_pct * call_amount

    call_profitable = bluff_pct > alpha

    summary = (
        f'對手範圍({int(villain_vpip*100)}%)  '
        f'Total={total_combos}  '
        f'Value={value_combos}+TP={toppair_combos}  '
        f'Draw={draw_combos}  Bluff={bluff_combos}'
    )

    advice = _build_advice(
        bluff_pct, alpha, call_profitable, value_combos,
        toppair_combos, bluff_combos, total_combos,
        is_river, bet_fraction,
    )

    return ComboCount(
        board            = board,
        villain_vpip     = villain_vpip,
        hero_hole        = hero_hole,
        total_combos     = total_combos,
        value_combos     = value_combos,
        toppair_combos   = toppair_combos,
        draw_combos      = draw_combos,
        bluff_combos     = bluff_combos,
        value_pct        = round(value_pct, 3),
        bluff_pct        = round(bluff_pct, 3),
        alpha            = round(alpha, 3),
        call_profitable  = call_profitable,
        ev_call_per_combo = round(ev_call, 2),
        summary          = summary,
        advice           = advice,
    )


def _build_advice(
    bluff_pct: float, alpha: float, call_profitable: bool,
    value_c: int, tp_c: int, bluff_c: int, total_c: int,
    is_river: bool, bet_frac: float,
) -> str:
    alpha_pct = int(alpha * 100)
    bluff_pct_display = int(bluff_pct * 100)
    bet_pct = int(bet_frac * 100)

    if call_profitable:
        over_bluff = int((bluff_pct - alpha) * 100)
        return (f'跟注有利！對手詐唬{bluff_pct_display}% > 保本{alpha_pct}% '
                f'(over-bluff +{over_bluff}%)  建議跟注')
    else:
        under_bluff = int((alpha - bluff_pct) * 100)
        return (f'棄牌有利。對手詐唬{bluff_pct_display}% < 保本{alpha_pct}% '
                f'(under-bluff -{under_bluff}%)  '
                f'Value={value_c}+{tp_c}  Bluff={bluff_c}/{total_c}')


def combo_summary(r: ComboCount) -> str:
    """單行 overlay 顯示。"""
    bet_pct = int(r.alpha * 100 / (1 - r.alpha) if r.alpha < 1 else 0)
    bluff_display = int(r.bluff_pct * 100)
    alpha_display = int(r.alpha * 100)
    call_str = '跟注' if r.call_profitable else '棄牌'
    return (f'[Combo] V={r.value_combos+r.toppair_combos} '
            f'B={r.bluff_combos}/{r.total_combos}  '
            f'詐唬{bluff_display}% vs 保本{alpha_display}%  → {call_str}')
