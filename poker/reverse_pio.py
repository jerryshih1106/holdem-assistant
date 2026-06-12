"""
反向隱含賠率警告系統 (Reverse Implied Odds Warning)

核心問題：「我現在雖然領先，但如果落後時虧多少？」

反向隱含賠率（RIO）發生在：
  1. 頂對弱踢腳（TPWK）vs 可能的 TPTK/兩對/暗三條
  2. 第二強同花 vs 頂花（nut flush）
  3. 順子在配對或同花牌面上
  4. 弱兩對（如底部兩對）在可能有套牌的牌面

公式：
  RIO 損失 = P(我被撞牌) × (額外投入底池的BB)
  vs
  正常獲利 = P(維持領先) × (贏得的BB)

如果 RIO_loss > 正常獲利 → 手牌有負面 RIO，建議謹慎

典型場景與建議：
  K♥7♦3♣ 牌面，你有 K♠T♦ (TPWK):
    → 對手可能有 KJ+, K7s, K3s（兩對更好）, 77, 33（暗三條）
    → 應僅小注取值，不要大底池
    → 面對加注：考慮棄牌（RIO 很高）

  J♥9♥5♥ 牌面，你有 K♥Q♦ (K-high flush draw):
    → 命中非頂花：面對大注需謹慎
    → 對手可能有 A♥（頂花聽牌），你只有第二花
    → 計算淨收益：命中後贏得的 vs 被頂花打敗的損失
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class ReverseImpliedOddsResult:
    # 風險評估
    risk_level:        str      # 'high'/'medium'/'low'/'minimal'
    risk_label_zh:     str
    rio_score:         float    # 0-1（越高風險越大）

    # 觸發的場景
    scenario:          str      # 'tpwk'/'second_flush'/'weak_two_pair'/'dominated_pair'/'straight_on_pair_board' etc
    scenario_zh:       str
    scenario_notes:    List[str]

    # 具體數字
    domination_pct:    float    # 估算有多少%對手手牌可以打敗你（命中後）
    equity_edge:       float    # 當前勝率優勢（高 edge 降低 RIO 影響）

    # 建議
    recommended_action: str
    sizing_advice:     str
    facing_bet_advice: str

    # 摘要
    summary_zh:        str


_RANK_VAL = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
             'T':10,'J':11,'Q':12,'K':13,'A':14}

_BROADWAY = {'T','J','Q','K','A'}


def _rank(c: str) -> str:
    return c[0].upper() if c else ''

def _suit(c: str) -> str:
    return c[1].lower() if len(c) >= 2 else ''

def _rval(c: str) -> int:
    return _RANK_VAL.get(_rank(c), 0)


def _is_tpwk(hole: List[str], community: List[str]) -> Tuple[bool, float, str]:
    """
    檢測頂對弱踢腳（TPWK）。
    返回 (is_tpwk, risk_score, note)
    """
    if len(hole) < 2 or len(community) < 3:
        return False, 0.0, ''

    board_ranks = [_rank(c) for c in community]
    board_vals  = sorted([_rval(c) for c in community], reverse=True)
    top_board   = board_vals[0]

    h1_rank, h2_rank = _rank(hole[0]), _rank(hole[1])
    h1_val,  h2_val  = _rval(hole[0]),  _rval(hole[1])

    # 口袋對 → 暗三條/四條，不是 TPWK
    if h1_val == h2_val:
        return False, 0.0, ''

    # 找出英雄配對的牌
    paired_with_board = None
    kicker = None

    if h1_val == top_board:
        paired_with_board = h1_val
        kicker = h2_val
    elif h2_val == top_board:
        paired_with_board = h2_val
        kicker = h1_val

    if paired_with_board is None:
        return False, 0.0, ''

    # 有頂對，現在檢查踢腳強度
    kicker_rank = {v: r for r, v in _RANK_VAL.items()}.get(kicker, '?')

    # 踢腳越弱，RIO 風險越高
    if kicker >= 13:  # K 踢腳
        risk = 0.1
        note = f'TPWK 弱（頂對 K 踢腳）：RIO 低，其他 K 系手牌有限'
    elif kicker >= 11:  # J/Q 踢腳
        risk = 0.30
        note = f'TPWK 中（踢腳 {kicker_rank}）：被 AK/KQ 等壓制'
    elif kicker >= 9:   # 9/T 踢腳
        risk = 0.50
        note = f'TPWK 高（踢腳 {kicker_rank}）：大量高張手牌壓制你'
    else:               # 弱踢腳
        risk = 0.75
        note = f'TPWK 極高（踢腳 {kicker_rank}）：幾乎所有同牌值手牌壓制你'

    # 調整：頂牌是 A → TPWK 在 A 上更危險（更多手牌有 A）
    paired_rank_str = {v: r for r, v in _RANK_VAL.items()}.get(paired_with_board, '?')
    if paired_with_board == 14:  # Ace
        risk = min(1.0, risk + 0.15)
        note += '（牌面有 A，TPWK 尤其危險）'

    return True, risk, note


def _check_second_flush_draw(hole: List[str], community: List[str]) -> Tuple[bool, float, str]:
    """
    檢測第二強同花聽牌（非頂花）。
    """
    if len(hole) < 2 or len(community) < 3:
        return False, 0.0, ''

    # 統計各花色
    from collections import Counter
    suit_counts: Counter = Counter()
    hero_suits: List[Tuple[int, str]] = []  # (rank_val, suit)

    for c in hole:
        suit_counts[_suit(c)] += 1
        hero_suits.append((_rval(c), _suit(c)))
    for c in community:
        suit_counts[_suit(c)] += 1

    # 找是否有同花聽牌（4張同花）
    for s, cnt in suit_counts.items():
        if cnt >= 4:
            hero_in_suit = [rv for rv, su in hero_suits if su == s]
            if hero_in_suit:
                hero_max = max(hero_in_suit)
                # 檢查牌面最大同花牌
                board_in_suit = [_rval(c) for c in community if _suit(c) == s]
                board_max = max(board_in_suit) if board_in_suit else 0

                # 如果英雄的最大同花牌不是 A → 可能有頂花壓制
                if hero_max < 14:  # 不是 A
                    risk = 0.50
                    hero_rank_str = {v: r for r, v in _RANK_VAL.items()}.get(hero_max, '?')
                    note = f'第二花({hero_rank_str}高同花)：對手可能有 A{s} 頂花壓制'
                    if hero_max >= 13:  # K-high flush
                        risk = 0.30
                        note = f'K 高同花：有 ~25% 機率對手有 A 頂花'
                    elif hero_max >= 11:
                        risk = 0.45
                        note = f'{hero_rank_str} 高同花：RIO 中等，對手有頂花就損失慘重'
                    else:
                        risk = 0.65
                        note = f'{hero_rank_str} 高同花：RIO 高，命中後可能輸大底池'
                    return True, risk, note

    return False, 0.0, ''


def _check_weak_two_pair(hole: List[str], community: List[str]) -> Tuple[bool, float, str]:
    """
    檢測弱兩對（底部兩對、上下兩對等）。
    """
    if len(hole) < 2 or len(community) < 3:
        return False, 0.0, ''

    board_vals = sorted([_rval(c) for c in community], reverse=True)
    h1v, h2v   = _rval(hole[0]), _rval(hole[1])

    # 英雄的兩對必須包含兩張手牌各配對一張公牌
    paired_ranks = set()
    for hv in (h1v, h2v):
        if hv in board_vals:
            paired_ranks.add(hv)

    if len(paired_ranks) < 2:
        return False, 0.0, ''

    max_pair = max(paired_ranks)
    min_pair = min(paired_ranks)

    # 如果兩對中最高的不是牌面頂牌 → 弱兩對
    if max_pair < board_vals[0]:
        risk = 0.60
        note = f'弱兩對（非頂對）：對手可能有更大的兩對或暗三條'
        return True, risk, note

    # 頂對底對：底對被暗三條壓制
    if min_pair == board_vals[-1]:
        risk = 0.40
        note = f'頂對底對：底對可能被暗三條壓制（{board_vals[-1]}的暗三條）'
        return True, risk, note

    return False, 0.0, ''


def analyze_reverse_implied_odds(
    hole:            List[str],
    community:       List[str],
    equity:          float = 0.60,       # 當前勝率
    pot_bb:          float = 10.0,
    stack_bb:        float = 80.0,
    call_amount:     float = 0.0,        # 面對的注碼
    villain_vpip:    float = 0.28,
    is_aggressor:    bool  = True,
) -> ReverseImpliedOddsResult:
    """
    分析英雄手牌的反向隱含賠率風險。

    Args:
        hole:         英雄手牌
        community:    公牌
        equity:       當前勝率（蒙特卡羅）
        pot_bb:       底池大小
        stack_bb:     有效籌碼
        call_amount:  面對的注碼（0 = 英雄主動）
        villain_vpip: 對手 VPIP
        is_aggressor: 英雄是否持有主動權
    """
    scenarios: List[Tuple[bool, float, str, str, str]] = []
    # (detected, risk_score, scenario_key, scenario_zh, note)

    # ── 各場景檢測 ────────────────────────────────────────────────────────────

    is_tpwk, tpwk_risk, tpwk_note = _is_tpwk(hole, community)
    if is_tpwk:
        scenarios.append((True, tpwk_risk, 'tpwk', '頂對弱踢腳', tpwk_note))

    is_2nd_flush, flush_risk, flush_note = _check_second_flush_draw(hole, community)
    if is_2nd_flush:
        scenarios.append((True, flush_risk, 'second_flush', '第二強同花', flush_note))

    is_weak_2p, weak2p_risk, weak2p_note = _check_weak_two_pair(hole, community)
    if is_weak_2p:
        scenarios.append((True, weak2p_risk, 'weak_two_pair', '弱兩對', weak2p_note))

    # ── 選出最高風險場景 ───────────────────────────────────────────────────────

    if not scenarios:
        return ReverseImpliedOddsResult(
            risk_level         = 'minimal',
            risk_label_zh      = '風險最小',
            rio_score          = 0.0,
            scenario           = 'none',
            scenario_zh        = '無 RIO 風險',
            scenario_notes     = [],
            domination_pct     = 0.0,
            equity_edge        = max(0.0, equity - 0.50),
            recommended_action = '無需調整：正常下注/跟注',
            sizing_advice      = '正常注碼',
            facing_bet_advice  = '按勝率決策',
            summary_zh         = '',
        )

    scenarios.sort(key=lambda x: x[1], reverse=True)
    _, rio_score, scenario, scenario_zh, main_note = scenarios[0]
    all_notes = [s[4] for s in scenarios]

    # ── 調整因素 ─────────────────────────────────────────────────────────────

    # 高勝率減少 RIO 影響
    equity_edge = max(0.0, equity - 0.50)
    if equity >= 0.75:
        rio_score *= 0.6     # 高勝率時 RIO 影響更小
    elif equity >= 0.65:
        rio_score *= 0.75

    # 魚更容易觸發 RIO（他們用差牌跟到底，讓你更常面對強牌）
    if villain_vpip >= 0.40:
        # 魚的行動偶爾更難預測
        pass  # neutral for this check

    # ── 風險等級 ─────────────────────────────────────────────────────────────

    if rio_score >= 0.60:
        risk_level    = 'high'
        risk_label_zh = 'RIO 高風險'
    elif rio_score >= 0.35:
        risk_level    = 'medium'
        risk_label_zh = 'RIO 中等風險'
    elif rio_score >= 0.15:
        risk_level    = 'low'
        risk_label_zh = 'RIO 低風險'
    else:
        risk_level    = 'minimal'
        risk_label_zh = '風險最小'

    # ── 建議 ─────────────────────────────────────────────────────────────────

    if risk_level == 'high':
        recommended_action = '縮小底池：避免大底池情況'
        sizing_advice      = '只用 30-40% 底池薄薄取值'
        if call_amount > 0:
            facing_bet_advice = '面對下注：謹慎跟注，面對加注棄牌'
        else:
            facing_bet_advice = '主動：過牌或小注，避免 3-bet'

    elif risk_level == 'medium':
        recommended_action = '控制底池：避免大底池'
        sizing_advice      = '標準注碼（50-60%），但別構建太大的底池'
        if call_amount > 0:
            facing_bet_advice = '面對標準注碼可跟注，面對大注謹慎'
        else:
            facing_bet_advice = '主動：標準注碼取值，放棄加注戰'

    elif risk_level == 'low':
        recommended_action = '小心注意：RIO 存在但不嚴重'
        sizing_advice      = '正常注碼，注意對手的加注信號'
        if call_amount > 0:
            facing_bet_advice = '跟注合理，面對大注/加注時重新評估'
        else:
            facing_bet_advice = '正常下注，注意應對加注'
    else:
        recommended_action = '正常操作：RIO 風險可忽略'
        sizing_advice      = '正常注碼'
        facing_bet_advice  = '按勝率決策'

    # 估計被壓制的比例（簡化）
    domination_pct = min(0.95, rio_score * 0.8)

    summary_zh = (
        f'[RIO] {risk_label_zh}  {scenario_zh}  '
        f'建議:{recommended_action[:15]}'
    )[:80]

    return ReverseImpliedOddsResult(
        risk_level          = risk_level,
        risk_label_zh       = risk_label_zh,
        rio_score           = round(rio_score, 2),
        scenario            = scenario,
        scenario_zh         = scenario_zh,
        scenario_notes      = all_notes,
        domination_pct      = round(domination_pct, 2),
        equity_edge         = round(equity_edge, 2),
        recommended_action  = recommended_action,
        sizing_advice       = sizing_advice,
        facing_bet_advice   = facing_bet_advice,
        summary_zh          = summary_zh,
    )


def rio_summary(r: ReverseImpliedOddsResult) -> str:
    """單行 overlay 摘要（最多 80 字）。"""
    if r.risk_level == 'minimal':
        return ''
    return r.summary_zh[:80]
