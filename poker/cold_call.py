"""
冷跟注 / 擠注場景分析器 (Cold Call & Multi-way Squeeze)

處理翻前多人底池情境：
  情境 A: 有人開牌 + 1+ 個跟注者，你考慮冷跟注（cold call）
  情境 B: 有人開牌 + 1+ 個跟注者，你考慮擠注（squeeze）

冷跟注策略：
  - 只有「有位置 + 隱含賠率足夠 + 對方跟注範圍合理」時冷跟注才獲利
  - 主要適合：投機牌（小對子/同花連張）、位置極佳（BTN）
  - 在多人底池中，speculative 手牌的隱含賠率更好

擠注策略（整合 squeeze.py）：
  - 死錢越多、位置越好、開牌者越弱，擠注越有利
  - 擠注尺寸 = 開牌注 × 3-4 + 每個跟注者 × 1BB

注意：此模組已整合 preflop_advisor.py 和 squeeze.py 的邏輯
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from poker.squeeze import analyze_squeeze, squeeze_summary
from poker.ranges import (
    THREEBET_BTN_VS_CO, THREEBET_BTN_VS_HJ, THREEBET_BTN_VS_UTG,
    THREEBET_CO_VS_HJ, THREEBET_CO_VS_UTG,
    RFI_BTN, RFI_CO, _r, _merge,
)


@dataclass
class ColdCallResult:
    hand:               str
    hero_pos:           str
    opener_pos:         str
    num_callers:        int        # 已有幾個跟注者
    stack_bb:           float
    open_size_bb:       float

    # 行動建議
    action:             str        # 'cold_call' / 'squeeze' / 'fold'
    action_freq:        float      # 執行頻率
    raise_size_bb:      float      # 擠注注碼（若 squeeze）
    squeeze_ev:         float      # 擠注 EV 估算

    # 分析
    cold_call_ok:       bool       # 冷跟注是否合理
    squeeze_ok:         bool       # 擠注是否合理
    implied_odds_ok:    bool       # 隱含賠率是否足夠
    pot_size_after:     float      # 跟注後底池大小

    reasoning:          str
    squeeze_note:       str        # 擠注分析摘要
    tips:               List[str] = field(default_factory=list)


# ── 冷跟注適合的手牌類型 ─────────────────────────────────────────────────────

# BTN 冷跟注範圍（vs CO 開牌 + 有跟注者）：主要是投機牌和中等牌
_COLD_CALL_BTN = _merge(
    _r('55','44','33','22'),                           # 小對子挖三條
    _r('JTs','T9s','98s','87s','76s','65s','54s'),    # 同花連張
    _r('A9s','A8s','A7s','A6s','A5s','A4s','A3s','A2s'),  # 同花 Ax
    _r('KTs','QTs','J9s','T8s','97s','86s','75s','64s'), # 其他同花
    _r('KQs','KJs','QJs', freq=0.5),                  # 部分強同花
)

_COLD_CALL_CO = _merge(
    _r('55','44','33'),
    _r('JTs','T9s','98s','87s','76s'),
    _r('A8s','A7s','A6s','A5s','A4s'),
    _r('KTs','QTs','J9s', freq=0.5),
)

# 可冷跟注的位置（需要有位置）
_CAN_COLD_CALL = {'BTN', 'CO', 'HJ'}  # OOP 位置通常不適合冷跟注


def _hand_strength_class(hand: str) -> str:
    """簡單分類手牌類型。"""
    if len(hand) == 2:   # 對子
        r = hand[0]
        rank_val = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,'7':7,
                    '6':6,'5':5,'4':4,'3':3,'2':2}.get(r, 0)
        if rank_val >= 10:  return 'big_pair'
        if rank_val >= 7:   return 'medium_pair'
        return 'small_pair'
    if len(hand) == 3:
        r1, r2, stype = hand[0], hand[1], hand[2]
        rank_val = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8}.get(r1, 0)
        if stype == 's' and rank_val >= 13: return 'premium_suited'
        if stype == 's': return 'suited_connector'
        return 'offsuit'
    return 'unknown'


def _implied_odds_ok(
    hand:         str,
    stack_bb:     float,
    call_amount:  float,
    num_opponents: int,
) -> Tuple[bool, str]:
    """
    判斷隱含賠率是否支持跟注投機牌。

    小對子/同花連張需要約 10-20 倍跟注額的隱含賠率（stack/call 比）
    以期望在命中時贏回足夠的籌碼。
    """
    sc_ratio = stack_bb / call_amount if call_amount > 0 else 0
    hand_class = _hand_strength_class(hand)

    # 多人底池：隱含賠率更好（更多人可能誤進底池）
    multi_bonus = min(0.20, num_opponents * 0.08)

    if hand_class == 'small_pair':
        needed_ratio = 15.0 - multi_bonus * 10
        ok = sc_ratio >= needed_ratio
        note = f'小對子需要 stack:call >= {needed_ratio:.0f}:1（現在 {sc_ratio:.0f}:1）'
    elif hand_class == 'suited_connector':
        needed_ratio = 10.0 - multi_bonus * 8
        ok = sc_ratio >= needed_ratio
        note = f'同花連張需要 stack:call >= {needed_ratio:.0f}:1（現在 {sc_ratio:.0f}:1）'
    elif hand_class == 'premium_suited':
        needed_ratio = 6.0
        ok = sc_ratio >= needed_ratio
        note = f'大同花牌需要 stack:call >= {needed_ratio:.0f}:1（現在 {sc_ratio:.0f}:1）'
    else:
        ok = sc_ratio >= 8.0
        note = f'stack:call = {sc_ratio:.0f}:1'

    return ok, note


def analyze_cold_call(
    hand:         str,
    hero_pos:     str,
    opener_pos:   str,
    caller_positions: List[str],   # 已跟注的位置列表
    open_size_bb: float = 2.5,
    stack_bb:     float = 100.0,
) -> ColdCallResult:
    """
    分析是否應冷跟注、擠注或棄牌。

    Args:
        hand:              英雄手牌
        hero_pos:          英雄位置
        opener_pos:        開牌者位置
        caller_positions:  已跟注者的位置列表
        open_size_bb:      開牌注大小
        stack_bb:          有效籌碼
    """
    num_callers = len(caller_positions)
    call_amount = open_size_bb   # 冷跟注需要付出的籌碼
    pot_after_call = 1.5 + (num_callers + 1) * open_size_bb + open_size_bb
    hand_class = _hand_strength_class(hand)
    hero_has_pos = hero_pos in _CAN_COLD_CALL

    reasons = []
    tips    = []

    # ── 擠注分析（整合 squeeze.py）──────────────────────────────────
    squeeze_res = analyze_squeeze(
        hero_pos=hero_pos,
        opener_pos=opener_pos,
        num_callers=num_callers,
        open_size_bb=open_size_bb,
        effective_stack=stack_bb,
        hero_hand=hand,
    )
    squeeze_ok = squeeze_res.should_squeeze and stack_bb >= 20

    # ── 冷跟注分析 ───────────────────────────────────────────────────
    # 查冷跟注範圍
    cold_call_range = _COLD_CALL_BTN if hero_pos == 'BTN' else _COLD_CALL_CO
    in_cold_range = cold_call_range.get(hand, 0.0) > 0.3

    # 隱含賠率
    implied_ok, implied_note = _implied_odds_ok(
        hand, stack_bb, call_amount, num_callers + 1
    )
    tips.append(implied_note)

    # 多人底池冷跟注額外條件
    multi_pot_bonus = num_callers >= 1  # 已有跟注者 → 底池更大 → 投機牌更合算
    if multi_pot_bonus:
        tips.append(f'已有{num_callers}個跟注者：底池大={pot_after_call:.1f}BB，隱含賠率更好')

    # 強牌（大對子）：不應冷跟注，應擠注或考慮
    if hand_class in ('big_pair', 'premium_suited') and not squeeze_ok:
        cold_call_ok = False
        reasons.append(f'{hand_class}手牌不應冷跟注：容易面對三倍注或多路底池失去優勢')
        tips.append('大對子/強牌在多人底池中冷跟注會讓對手免費看到後門聽牌完成')
    else:
        cold_call_ok = (in_cold_range and implied_ok and hero_has_pos
                        and hand_class in ('small_pair', 'medium_pair', 'suited_connector',
                                           'premium_suited'))

    if not hero_has_pos and not squeeze_ok:
        cold_call_ok = False
        reasons.append(f'{hero_pos} 無位置優勢，冷跟注 EV 通常為負')

    # 投機牌（小對子/同花連張）優先冷跟注，不適合擠注
    is_speculative = hand_class in ('small_pair', 'medium_pair', 'suited_connector')

    # ── 決定主要行動 ─────────────────────────────────────────────────
    if cold_call_ok and is_speculative and implied_ok:
        # 投機牌：有隱含賠率時優先冷跟注
        action      = 'cold_call'
        action_freq = cold_call_range.get(hand, 0.5)
        raise_sz    = 0.0
        reasons.append(f'有位置冷跟注：{implied_note}，{num_callers+1}人底池隱含賠率佳')
    elif squeeze_ok and not is_speculative and squeeze_res.ev_estimate > 0.5:
        # 強牌/大同花：擠注 EV 明顯為正
        action      = 'squeeze'
        action_freq = squeeze_res.squeeze_freq
        raise_sz    = squeeze_res.squeeze_size_bb
        reasons.append(f'擠注 EV={squeeze_res.ev_estimate:.1f}BB，'
                        f'死錢{1.5 + num_callers * open_size_bb:.1f}BB 足夠')
    elif cold_call_ok:
        action      = 'cold_call'
        action_freq = cold_call_range.get(hand, 0.5)
        raise_sz    = 0.0
        reasons.append(f'有位置冷跟注：{implied_note}，多人底池獲利')
    elif squeeze_ok:
        # 擠注可行但 EV 較小
        action      = 'squeeze'
        action_freq = squeeze_res.squeeze_freq * 0.6
        raise_sz    = squeeze_res.squeeze_size_bb
        reasons.append(f'輕微擠注機會（EV={squeeze_res.ev_estimate:.1f}BB），謹慎執行')
    else:
        action      = 'fold'
        action_freq = 1.0
        raise_sz    = 0.0
        if not hero_has_pos:
            reasons.append(f'無位置 + 手牌不足 + 擠注 EV 低，棄牌')
        elif not in_cold_range:
            reasons.append(f'{hand} 不在 {hero_pos} 冷跟注範圍')
        else:
            reasons.append(f'隱含賠率不足（{implied_note}），棄牌')

    # 通用提示
    if num_callers >= 2:
        tips.append(f'{num_callers}個跟注者=多人底池；以後手牌需命中才有 EV，謹慎call')
    tips.append(f'擠注範圍：{squeeze_res.range_hint}')

    return ColdCallResult(
        hand               = hand,
        hero_pos           = hero_pos,
        opener_pos         = opener_pos,
        num_callers        = num_callers,
        stack_bb           = stack_bb,
        open_size_bb       = open_size_bb,
        action             = action,
        action_freq        = round(action_freq, 2),
        raise_size_bb      = round(raise_sz, 1),
        squeeze_ev         = squeeze_res.ev_estimate,
        cold_call_ok       = cold_call_ok,
        squeeze_ok         = squeeze_ok,
        implied_odds_ok    = implied_ok,
        pot_size_after     = round(pot_after_call, 1),
        reasoning          = '；'.join(reasons),
        squeeze_note       = squeeze_summary(squeeze_res),
        tips               = tips,
    )


def cold_call_summary(r: ColdCallResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    action_zh = {'cold_call': '冷跟注', 'squeeze': '擠注', 'fold': '棄牌'}.get(r.action, r.action)
    size_str = f' {r.raise_size_bb:.1f}BB' if r.raise_size_bb > 0 else ''
    return (f'翻前多人 {r.hand}@{r.hero_pos}  {action_zh}{size_str}  '
            f'({r.action_freq:.0%})  {r.reasoning[:35]}')


def batch_cold_call(
    hands:        List[str],
    hero_pos:     str,
    opener_pos:   str,
    callers:      List[str],
    open_size_bb: float = 2.5,
    stack_bb:     float = 100.0,
) -> List[ColdCallResult]:
    """批次分析多張手牌的冷跟注/擠注建議。"""
    return [analyze_cold_call(h, hero_pos, opener_pos, callers, open_size_bb, stack_bb)
            for h in hands]
