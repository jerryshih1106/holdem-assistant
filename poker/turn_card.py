"""
轉牌/河牌到來影響分析器 (Turn/River Card Impact Analyzer)

當新的公牌出現時回答：
  1. 這張牌對英雄的底池股份有什麼影響？（勝率變化 delta）
  2. 牌面性質：空白/危險/命中聽牌/完成順子或同花
  3. 是否應繼續下注（barrel）或放棄？
  4. 這張牌更有利於誰的範圍（英雄 vs 對手）？

輸入：
  - prev_equity:   上一街英雄勝率（0-1）
  - curr_equity:   本街英雄勝率（0-1）
  - community:     完整公牌列表（含新牌）
  - has_draw_flop: 翻牌是否有聽牌
  - hero_range_advantage: 範圍優勢（0=對手 0.5=均衡 1=英雄）

輸出：
  - TurnCardResult：含 delta、牌面分類、行動建議
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class TurnCardResult:
    # 勝率變化
    equity_delta:      float    # 本街勝率變化（curr - prev），正=改善，負=惡化
    equity_label:      str      # '改善'/'空白'/'惡化'/'大幅惡化'

    # 牌面分類
    card_type:         str      # 'blank'/'paired'/'straight_draw'/'flush_completing'
                                # /'oesd_completing'/'hit_top'/'hit_draw'/'scare'
    card_type_zh:      str      # 中文標籤
    new_card:          str      # 新公牌（如 'Ah', 'Ts'）

    # 繼續或放棄的建議
    should_continue:   bool     # 是否建議繼續下注
    action:            str      # 'BARREL'/'CHECK_EVAL'/'GIVE_UP'/'POT_CONTROL'
    action_zh:         str
    action_confidence: str      # 'high'/'medium'/'low'

    # 詳細說明
    note:              str
    tips:              List[str] = field(default_factory=list)


# ── 牌型常數 ────────────────────────────────────────────────────────────────────

_RANK_VAL = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
             'T':10,'J':11,'Q':12,'K':13,'A':14}

_SCARE_RANKS = {'A','K','Q'}   # 高張出現通常對低翻牌對手有利


def _card_rank(c: str) -> str:
    return c[0].upper() if c else ''


def _card_suit(c: str) -> str:
    return c[1].lower() if len(c) >= 2 else ''


def _count_suits(cards: List[str]) -> dict:
    """返回各花色的出現次數。"""
    counts: dict = {}
    for c in cards:
        s = _card_suit(c)
        counts[s] = counts.get(s, 0) + 1
    return counts


def _check_flush_draw_completing(prev_community: List[str], curr_community: List[str]) -> bool:
    """
    新牌是否使牌面出現了同花警報（3張同花）。
    條件：當前公牌中有花色出現 3+，但之前的公牌中該花色只有 2 張。
    """
    prev_suits = _count_suits(prev_community)
    curr_suits = _count_suits(curr_community)
    for suit, cnt in curr_suits.items():
        if cnt >= 3 and prev_suits.get(suit, 0) < 3:
            return True
    return False


def _check_pairs_board(community: List[str]) -> bool:
    """牌面上是否有對子。"""
    ranks = [_card_rank(c) for c in community]
    return len(ranks) != len(set(ranks))


def _check_straight_danger(community: List[str]) -> bool:
    """牌面是否有 4 張連張（容易成順）。"""
    vals = sorted(set(_RANK_VAL.get(_card_rank(c), 0) for c in community))
    for i in range(len(vals) - 3):
        if vals[i+3] - vals[i] <= 4:
            return True
    return False


def _classify_card(
    new_card:        str,
    prev_community:  List[str],
    curr_community:  List[str],
    has_draw_flop:   bool = False,
) -> Tuple[str, str]:
    """
    分類新到的公牌。

    Returns:
        (card_type, card_type_zh)
    """
    rank = _card_rank(new_card)
    new_flush_complete = _check_flush_draw_completing(prev_community, curr_community)
    new_pair = _check_pairs_board(curr_community) and not _check_pairs_board(prev_community)
    straight_danger = _check_straight_danger(curr_community)

    # Flush completing is highest priority — overrides scare card classification
    if new_flush_complete:
        return 'flush_completing', '同花完成'

    if straight_danger and not _check_straight_danger(prev_community):
        return 'straight_draw', '順子危險牌'

    if new_pair:
        return 'paired', '配對牌面'

    if rank in _SCARE_RANKS and all(_card_rank(c) not in _SCARE_RANKS
                                    for c in prev_community):
        return 'scare', f'恐嚇牌({rank})'

    if has_draw_flop and rank not in _SCARE_RANKS:
        # 有聽牌時，中間張更可能命中
        return 'hit_draw', '可能命中聽牌'

    return 'blank', '空白牌'


def analyze_turn_card(
    prev_equity:          float,    # 上一街勝率（0-1）
    curr_equity:          float,    # 本街勝率（0-1）
    prev_community:       List[str],
    curr_community:       List[str],
    has_draw_flop:        bool  = False,
    hero_range_advantage: float = 0.5,  # 0=對手優勢 0.5=均衡 1=英雄優勢
    is_aggressor:         bool  = True,  # 英雄是否是上一街的下注者
    pot_bb:               float = 10.0,
    stack_bb:             float = 80.0,
) -> TurnCardResult:
    """
    分析轉牌/河牌對英雄的影響，給出繼續或放棄的建議。

    Args:
        prev_equity:    翻牌/轉牌的勝率
        curr_equity:    轉牌/河牌的勝率（更新後）
        prev_community: 上一街公牌（3或4張）
        curr_community: 本街公牌（4或5張）
        has_draw_flop:  翻牌是否有重要聽牌（影響新牌分類）
        hero_range_advantage: 英雄的整體範圍優勢（0-1）
        is_aggressor:   英雄是否持有主動權
        pot_bb:         當前底池
        stack_bb:       有效籌碼
    """
    # ── 找到新牌 ──────────────────────────────────────────────────────────────
    prev_set = set(c.lower() for c in prev_community)
    new_cards = [c for c in curr_community if c.lower() not in prev_set]
    new_card = new_cards[0] if new_cards else curr_community[-1]

    delta = curr_equity - prev_equity

    # ── 勝率變化標籤 ──────────────────────────────────────────────────────────
    if delta >= 0.10:
        eq_label = '大幅改善'
    elif delta >= 0.03:
        eq_label = '改善'
    elif delta >= -0.03:
        eq_label = '空白'
    elif delta >= -0.10:
        eq_label = '惡化'
    else:
        eq_label = '大幅惡化'

    # ── 牌面分類 ──────────────────────────────────────────────────────────────
    card_type, card_type_zh = _classify_card(
        new_card, prev_community, curr_community, has_draw_flop)

    # ── 行動建議 ──────────────────────────────────────────────────────────────
    spr = stack_bb / max(pot_bb, 0.1)

    if card_type in ('blank', 'paired') and curr_equity >= 0.55:
        action, action_zh = 'BARREL', '繼續 barrel'
        conf = 'high' if curr_equity >= 0.65 else 'medium'
        should_continue = True

    elif card_type in ('blank', 'paired') and 0.40 <= curr_equity < 0.55:
        action, action_zh = 'POT_CONTROL', '控底池（過牌-跟注）'
        conf = 'medium'
        should_continue = True

    elif card_type == 'flush_completing':
        if curr_equity >= 0.65:
            action, action_zh = 'BARREL', '繼續（有頂堅果）'
            conf = 'medium'
            should_continue = True
        elif curr_equity >= 0.45:
            action, action_zh = 'CHECK_EVAL', '過牌-評估（同花完成）'
            conf = 'medium'
            should_continue = False
        else:
            action, action_zh = 'GIVE_UP', '放棄（被同花完成）'
            conf = 'high'
            should_continue = False

    elif card_type in ('scare', 'straight_draw'):
        if curr_equity >= 0.60:
            action, action_zh = 'BARREL', '繼續（仍領先）'
            conf = 'medium'
            should_continue = True
        elif curr_equity >= 0.40:
            action, action_zh = 'CHECK_EVAL', '過牌-評估'
            conf = 'medium'
            should_continue = False
        else:
            action, action_zh = 'GIVE_UP', '放棄（危險牌面）'
            conf = 'high'
            should_continue = False

    elif card_type == 'hit_draw':
        if curr_equity >= 0.60:
            action, action_zh = 'BARREL', '命中！繼續取值'
            conf = 'high'
            should_continue = True
        else:
            action, action_zh = 'CHECK_EVAL', '可能命中，謹慎繼續'
            conf = 'low'
            should_continue = False

    elif curr_equity < 0.30:
        action, action_zh = 'GIVE_UP', '放棄（勝率過低）'
        conf = 'high'
        should_continue = False

    else:
        action, action_zh = 'CHECK_EVAL', '過牌-評估'
        conf = 'low'
        should_continue = False

    # ── OOP 調整：無位置時更保守 ──────────────────────────────────────────────
    if not is_aggressor and action == 'BARREL':
        action, action_zh = 'CHECK_EVAL', '過牌-評估（非主動方）'
        should_continue = False

    # ── 備注 ──────────────────────────────────────────────────────────────────
    delta_pct = int(delta * 100)
    sign = '+' if delta_pct >= 0 else ''
    note = (f'新牌 {_card_rank(new_card)} ({card_type_zh})  '
            f'勝率 {sign}{delta_pct}% ({prev_equity:.0%}→{curr_equity:.0%})')

    # ── 提示 ──────────────────────────────────────────────────────────────────
    tips: List[str] = []
    if card_type == 'flush_completing':
        tips.append('同花完成：對手的聽牌可能已到達，無頂花時謹慎')
    if card_type == 'scare':
        rank = _card_rank(new_card)
        tips.append(f'{rank}到來：此高張通常更有利翻前開牌者，若你 range 不強可考慮放棄')
    if card_type == 'blank' and delta >= 0.08:
        tips.append('空白轉牌顯著改善你的勝率，可加大注碼')
    if card_type == 'blank' and is_aggressor and curr_equity >= 0.55:
        tips.append('空白牌+翻牌主動：標準繼續 barrel，維持施壓')
    if curr_equity >= 0.75:
        tips.append('高勝率（75%+）：考慮大注或幾何注碼取值')
    if delta <= -0.12:
        tips.append(f'勝率下降超過 12%：這張牌顯著惡化你的牌力，建議放棄或過牌')
    if spr <= 2 and curr_equity >= 0.50:
        tips.append(f'SPR={spr:.1f}（低）：底池承諾區，適合全下')

    return TurnCardResult(
        equity_delta      = round(delta, 3),
        equity_label      = eq_label,
        card_type         = card_type,
        card_type_zh      = card_type_zh,
        new_card          = _card_rank(new_card),
        should_continue   = should_continue,
        action            = action,
        action_zh         = action_zh,
        action_confidence = conf,
        note              = note,
        tips              = tips,
    )


def turn_card_summary(r: TurnCardResult) -> str:
    """單行 overlay 摘要（最多 85 字）。"""
    delta_str = f'{r.equity_delta*100:+.0f}%'
    return (f'[公牌] {r.new_card} {r.card_type_zh} {delta_str}  '
            f'{r.equity_label}  → {r.action_zh}')[:85]
