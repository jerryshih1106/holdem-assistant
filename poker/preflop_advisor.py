"""
整合翻前決策顧問 (Integrated Preflop Advisor)

統一的翻前決策入口：
  1. RFI（首次開牌）— 根據位置推薦是否開牌及範圍
  2. 面對開牌（3-bet / 跟注 / 棄牌）— 根據英雄位置 vs 開牌者位置
  3. 面對 3-bet（4-bet / 跟注 / 棄牌）— 含籌碼深度調整
  4. 盲注防守（BB 防守 vs 各位置）

籌碼深度調整（有效籌碼 BB）：
  ≥100BB : 標準 GTO 範圍，可跟注 3-bet 帶隱含賠率
  60-99BB : 標準，3-bet/call 空間足夠
  40-59BB : 3-bet/jam or fold — 不應 3-bet-call 折疊（SPR 太低）
  25-39BB : push/fold 或 3-bet = all-in
  <25BB   : 純推折策略（參考 pushfold.py）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from poker.ranges import (
    RANGES, MIXED_ACTIONS, get_mixed_action,
    RFI_UTG, RFI_HJ, RFI_CO, RFI_BTN, RFI_SB,
    THREEBET_BTN_VS_UTG, THREEBET_BTN_VS_HJ, THREEBET_BTN_VS_CO,
    THREEBET_CO_VS_UTG, THREEBET_CO_VS_HJ,
    THREEBET_BB_VS_BTN, THREEBET_BB_VS_CO,
    VS3BET_CALL, VS3BET_4BET,
    BB_VS_UTG, BB_VS_HJ, BB_VS_CO, BB_VS_BTN, BB_VS_SB,
    hand_to_grid, combo_count, _r, _merge,
)

# ── IP 跟注範圍（BTN/CO vs 各位置開牌）────────────────────────────────────────
# ranges.py 只有 3-bet 範圍；IP 跟注範圍在此補全
_IP_CALL_BTN_VS_UTG = _merge(
    _r('JJ','TT','99','88','77','66','55','44','33','22', freq=0.5),
    _r('AQs','AJs','ATs','A9s','A8s'),
    _r('KQs','KJs','KTs','QJs','QTs','JTs','T9s','98s','87s','76s','65s'),
    _r('AQo', freq=0.5),
)
_IP_CALL_BTN_VS_HJ = _merge(
    _IP_CALL_BTN_VS_UTG,
    _r('55','44','33','22'),
    _r('A7s','A6s','K9s','Q9s','J9s','97s','86s','75s','64s'),
    _r('KQo','AJo', freq=0.5),
)
_IP_CALL_BTN_VS_CO = _merge(
    _IP_CALL_BTN_VS_HJ,
    _r('A5s','A4s','A3s','A2s'),
    _r('K8s','K7s','Q8s','T8s','96s','85s','74s'),
    _r('KQo','KJo','QJo', freq=0.5),
)
_IP_CALL_CO_VS_UTG = _merge(
    _r('JJ','TT','99','88','77','66', freq=0.5),
    _r('AJs','ATs','A9s','KQs','KJs','QJs','JTs','T9s','98s'),
)
_IP_CALL_CO_VS_HJ = _merge(
    _IP_CALL_CO_VS_UTG,
    _r('55','44'),
    _r('A8s','A7s','K9s','Q9s','87s','76s','65s'),
    _r('AQo', freq=0.5),
)

_IP_CALL: Dict[Tuple, Dict] = {
    ('BTN','UTG'): _IP_CALL_BTN_VS_UTG,
    ('BTN','HJ'):  _IP_CALL_BTN_VS_HJ,
    ('BTN','CO'):  _IP_CALL_BTN_VS_CO,
    ('CO','UTG'):  _IP_CALL_CO_VS_UTG,
    ('CO','HJ'):   _IP_CALL_CO_VS_HJ,
    ('BTN','SB'):  _IP_CALL_BTN_VS_CO,   # BTN vs SB open ≈ vs CO
    ('HJ','UTG'):  _IP_CALL_CO_VS_UTG,   # HJ ≈ CO vs UTG
}


@dataclass
class PreflopAdvice:
    hand:               str          # e.g. "AKs"
    hero_pos:           str          # BTN/CO/HJ/UTG/SB/BB
    villain_pos:        str          # 開牌者或 3-bet 者位置
    situation:          str          # 'rfi'/'vs_open'/'vs_3bet'/'bb_defense'
    stack_bb:           float

    # 主要建議
    action:             str          # '開牌'/'3-bet'/'跟注'/'4-bet'/'棄牌'/'全推'
    action_freq:        float        # 執行此行動的建議頻率 (0-1)
    raise_size_bb:      float        # 建議注碼（BB），0=跟/棄
    reasoning:          str

    # 替代行動
    alt_action:         str          # 第二建議（混合策略時）
    alt_freq:           float        # 第二建議頻率

    # 附加資訊
    in_range:           bool         # 此手牌是否在建議範圍內
    hand_strength:      str          # 'premium'/'strong'/'medium'/'speculative'/'marginal'
    stack_note:         str          # 籌碼深度提示
    key_hands:          List[str] = field(default_factory=list)   # 此情境的代表性手牌


# ── 位置強度 ────────────────────────────────────────────────────────────────────
_POS_RANK = {'UTG':0,'UTG1':1,'UTG2':2,'LJ':3,'HJ':4,'CO':5,'BTN':6,'SB':7,'BB':8}

def _pos_is_later(hero: str, villain: str) -> bool:
    return _POS_RANK.get(hero, 5) > _POS_RANK.get(villain, 5)


# ── 手牌強度分類 ────────────────────────────────────────────────────────────────
_PREMIUM   = {'AA','KK','QQ','JJ','AKs','AKo'}
_STRONG    = {'TT','99','88','AQs','AQo','AJs','KQs','KQo','AJo','ATs'}
_MEDIUM    = {'77','66','A9s','A8s','KJs','KTs','QJs','QTs','JTs','T9s',
              'A7s','A6s','A5s','A4s','A3s','A2s','K9s','Q9s','J9s','KJo','KTo'}
_SPECULATIVE = {'55','44','33','22','98s','87s','76s','65s','54s',
                '97s','86s','75s','64s','53s','43s'}


def _hand_strength(hand: str) -> str:
    if hand in _PREMIUM:    return 'premium'
    if hand in _STRONG:     return 'strong'
    if hand in _MEDIUM:     return 'medium'
    if hand in _SPECULATIVE: return 'speculative'
    return 'marginal'


# ── 標準化手牌格式 ─────────────────────────────────────────────────────────────
def _normalize_hand(hand: str) -> str:
    """把 'AhKs' 等格式轉成 'AKs'。輸入已是 'AKs' 直接回傳。"""
    h = hand.strip().upper()
    if len(h) == 3 and h[2] in ('S','O'):
        return h[0] + h[1] + h[2].lower()
    if len(h) == 2:   # pair like 'AA'
        return h
    return hand


# ── 場景→3-bet 範圍映射 ────────────────────────────────────────────────────────
_3BET_RANGE: Dict[str, Dict] = {
    ('BTN','UTG'):  THREEBET_BTN_VS_UTG,
    ('BTN','HJ'):   THREEBET_BTN_VS_HJ,
    ('BTN','CO'):   THREEBET_BTN_VS_CO,
    ('CO','UTG'):   THREEBET_CO_VS_UTG,
    ('CO','HJ'):    THREEBET_CO_VS_HJ,
    ('BB','BTN'):   THREEBET_BB_VS_BTN,
    ('BB','CO'):    THREEBET_BB_VS_CO,
    # 補全缺少的場景（用相近範圍近似）
    ('SB','BTN'):   THREEBET_BB_VS_BTN,   # SB≈BB vs BTN
    ('SB','CO'):    THREEBET_BB_VS_CO,
    ('SB','HJ'):    THREEBET_CO_VS_HJ,
    ('SB','UTG'):   THREEBET_CO_VS_UTG,
    ('HJ','UTG'):   THREEBET_CO_VS_UTG,   # HJ≈CO vs UTG
    ('BTN','SB'):   THREEBET_BTN_VS_CO,   # BTN vs SB slightly wider
    ('BB','SB'):    THREEBET_BB_VS_BTN,
    ('BB','HJ'):    THREEBET_BB_VS_CO,
    ('BB','UTG'):   THREEBET_CO_VS_UTG,
}

_RFI_RANGE: Dict[str, Dict] = {
    'UTG': RFI_UTG, 'HJ': RFI_HJ, 'CO': RFI_CO, 'BTN': RFI_BTN, 'SB': RFI_SB,
}

_BB_DEFEND: Dict[str, Dict] = {
    'UTG': BB_VS_UTG, 'HJ': BB_VS_HJ, 'CO': BB_VS_CO, 'BTN': BB_VS_BTN, 'SB': BB_VS_SB,
}


# ── 籌碼深度分析 ───────────────────────────────────────────────────────────────
def _stack_note(stack_bb: float) -> str:
    if stack_bb >= 100:
        return f'{stack_bb:.0f}BB 深籌碼：可跟注 3-bet 帶隱含賠率，speculative 手牌獲利'
    if stack_bb >= 60:
        return f'{stack_bb:.0f}BB 標準：3-bet/call 空間正常'
    if stack_bb >= 40:
        return f'{stack_bb:.0f}BB 注意：3-bet 後必須準備跟注全推，不要 3-bet/fold'
    if stack_bb >= 25:
        return f'{stack_bb:.0f}BB 短籌碼：3-bet = all-in，或直接全推'
    return f'{stack_bb:.0f}BB 極短：純推折策略，參考推棄圖表'


def _adjust_range_for_stack(
    hand: str,
    base_freq: float,
    stack_bb: float,
    situation: str,
) -> float:
    """根據籌碼深度調整行動頻率。"""
    hs = _hand_strength(hand)
    if stack_bb >= 60:
        return base_freq

    # 短籌碼時 speculative / marginal 手牌頻率下降（無隱含賠率）
    if hs in ('speculative', 'marginal'):
        mult = max(0.0, (stack_bb - 20) / 40)  # 60BB=1.0, 20BB=0.0
        return round(base_freq * mult, 3)

    # 中等手牌在中短籌碼時也有所收緊
    if hs == 'medium' and stack_bb < 40:
        mult = max(0.3, stack_bb / 60)
        return round(base_freq * mult, 3)

    return base_freq


# ── P0：動態範圍輔助函式 ──────────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _f2s_multiplier(f2s_pct: Optional[float]) -> float:
    """
    根據對手遇偷盲棄牌率（F2S%）計算範圍擴縮乘數。

    基準 F2S ≈ 60%：
      F2S > 60% → 對手折疊更多 → 可以偷更多 → 乘數 > 1
      F2S < 60% → 對手跟注太多 → 需要緊縮 → 乘數 < 1

    公式：mult = 1 + (f2s - 60) / 100 * 2.5，上下各限制在 [0.5, 1.5]
    """
    if f2s_pct is None:
        return 1.0
    f2s = _clamp(f2s_pct, 0, 100)
    mult = 1.0 + (f2s - 60.0) / 100.0 * 2.5
    return _clamp(mult, 0.5, 1.5)


def _iso_advice(
    hand: str, hs: str, hero_pos: str,
    base_freq: float, stack_bb: float,
    num_limpers: int, f2s_mult: float,
) -> tuple:
    """
    ISO 加注模式（底池有 limper 時）。

    核心邏輯：
    - limper 範圍寬弱 → 有利剝削 → 用更大注碼 ISO
    - 純牌力強（premium/strong）永遠 ISO
    - speculative 手牌受益於多人底池隱含賠率 → 保留
    - marginal 手牌在多人底池中缺乏保護，不 ISO

    注碼：標準加注 + 每 limper 加 1BB（防 limp/call）
    """
    # ISO 加注尺寸
    base_size = 2.5 if hero_pos in ('BTN', 'SB', 'CO') else 3.0
    iso_size  = round(base_size + num_limpers * 1.0, 1)
    if stack_bb <= 25:
        iso_size = min(stack_bb, iso_size)

    # limper 優勢加成：premium/strong 永遠 ISO；speculative 加頻率
    if hs == 'premium':
        iso_freq = 1.0
    elif hs == 'strong':
        iso_freq = 0.95
    elif hs == 'medium':
        iso_freq = _clamp(base_freq * f2s_mult * 1.2)
    elif hs == 'speculative':
        # 隱含賠率上升，小對小 suited connector 可 ISO
        iso_freq = _clamp(base_freq * f2s_mult * 0.9)
    else:  # marginal
        iso_freq = _clamp(base_freq * f2s_mult * 0.5)

    limper_str = f'{num_limpers} 個 limper'
    if iso_freq >= 0.7:
        action = 'ISO加注'
        reason = (f'ISO 加注 {iso_size}BB（{limper_str}範圍弱，'
                  f'{hs} 手牌主動剝削）')
    elif iso_freq >= 0.3:
        action = 'ISO加注'
        reason = (f'混合 ISO {iso_size}BB（{limper_str}，{iso_freq:.0%} 頻率）')
    else:
        action = '棄牌'
        iso_size = 0.0
        reason = f'面對 {limper_str} 此手牌 ISO 無優勢，棄牌'

    return iso_freq, iso_size, action, reason


# ── 主函數 ────────────────────────────────────────────────────────────────────

def advise_preflop(
    hand:                str,
    hero_pos:            str,           # BTN/CO/HJ/UTG/SB/BB
    villain_pos:         str   = '',    # 開牌者/3-bet者位置（RFI 時可省略）
    situation:           str   = 'auto',
    stack_bb:            float = 100.0,
    open_size_bb:        float = 2.5,   # 對手開牌注大小
    # P0 新增：動態範圍參數
    opp_fold_to_steal:   Optional[float] = None,  # 對手遇偷盲棄牌率 0-100（來自 HUD）
    num_limpers:         int   = 0,     # 已入池 limp 人數（>0 觸發 ISO 模式）
) -> PreflopAdvice:
    """
    統一翻前決策入口。

    Args:
        hand:        英雄手牌，如 'AKs' / 'QQ' / 'T9s'
        hero_pos:    英雄位置
        villain_pos: 開牌者位置（RFI 時留空）
        situation:   情境（auto=自動判斷）
        stack_bb:    有效籌碼
        open_size_bb: 對手開牌注大小（影響 3-bet 尺寸計算）
    """
    hand        = _normalize_hand(hand)
    hero_pos    = hero_pos.upper()
    villain_pos = villain_pos.upper() if villain_pos else ''
    hs          = _hand_strength(hand)
    s_note      = _stack_note(stack_bb)

    # F2S 調整乘數（對手棄牌越多可越寬；越少需越緊）
    f2s_mult = _f2s_multiplier(opp_fold_to_steal)

    # ── 自動判斷情境 ────────────────────────────────────────────────
    if situation == 'auto':
        if not villain_pos or villain_pos == hero_pos:
            situation = 'rfi'
        elif hero_pos == 'BB' and villain_pos not in ('', hero_pos):
            situation = 'bb_defense'
        elif hero_pos == 'SB' and villain_pos == 'BTN':
            situation = 'vs_open'
        else:
            situation = 'vs_open'

    # ─────────────────────────────────────────────────────────────────
    # 1. RFI（首次開牌）/ ISO 加注（有 limper 時）
    # ─────────────────────────────────────────────────────────────────
    if situation == 'rfi':
        rfi_range = _RFI_RANGE.get(hero_pos, RFI_CO)
        freq      = rfi_range.get(hand, 0.0)
        freq      = _adjust_range_for_stack(hand, freq, stack_bb, 'rfi')

        # ── ISO 加注模式（有 limper）─────────────────────────────────
        if num_limpers > 0:
            freq, raise_bb, action, reason = _iso_advice(
                hand, hs, hero_pos, freq, stack_bb, num_limpers, f2s_mult)
            key_hands = _top_hands(rfi_range, n=10)
            return PreflopAdvice(
                hand=hand, hero_pos=hero_pos, villain_pos='', situation='rfi',
                stack_bb=stack_bb, action=action, action_freq=freq,
                raise_size_bb=raise_bb if action == 'ISO加注' else 0.0,
                reasoning=reason,
                alt_action='棄牌' if action == 'ISO加注' else '',
                alt_freq=1 - freq,
                in_range=freq > 0,
                hand_strength=hs, stack_note=s_note, key_hands=key_hands,
            )

        # ── 標準 RFI + F2S 動態調整 ──────────────────────────────────
        freq = _clamp(freq * f2s_mult)

        # 開牌注尺寸：BTN/SB 2.5x，其他 3x
        if hero_pos in ('BTN', 'SB'):
            raise_bb = round(open_size_bb if open_size_bb > 0 else 2.5, 1)
        else:
            raise_bb = round(open_size_bb if open_size_bb > 0 else 3.0, 1)

        if stack_bb <= 25:
            raise_bb = min(stack_bb, raise_bb)

        key_hands = _top_hands(rfi_range, n=10)

        # F2S 提示
        f2s_note = ''
        if opp_fold_to_steal is not None:
            if opp_fold_to_steal > 70:
                f2s_note = f'（對手F2S {opp_fold_to_steal:.0f}%高，可放寬偷盲）'
            elif opp_fold_to_steal < 50:
                f2s_note = f'（對手F2S {opp_fold_to_steal:.0f}%低，建議收緊）'

        if freq >= 0.8:
            action, reason = '開牌', f'{hero_pos} 強牌（{hs}），{raise_bb}BB 開牌{f2s_note}'
        elif freq >= 0.3:
            action, reason = '開牌', f'{hero_pos} 混合開牌（{freq:.0%}）{f2s_note}'
        elif freq > 0:
            action, reason = '棄牌', f'邊緣牌（{freq:.0%}）{f2s_note}，建議棄牌'
        else:
            action, reason = '棄牌', f'不在 {hero_pos} 開牌範圍{f2s_note}'

        return PreflopAdvice(
            hand=hand, hero_pos=hero_pos, villain_pos='', situation='rfi',
            stack_bb=stack_bb, action=action, action_freq=freq,
            raise_size_bb=raise_bb if action == '開牌' else 0.0,
            reasoning=reason,
            alt_action='棄牌' if action == '開牌' else '',
            alt_freq=1 - freq,
            in_range=freq > 0,
            hand_strength=hs, stack_note=s_note, key_hands=key_hands,
        )

    # ─────────────────────────────────────────────────────────────────
    # 2. 面對開牌（3-bet / 跟注 / 棄牌）
    # ─────────────────────────────────────────────────────────────────
    elif situation == 'vs_open':
        key = (hero_pos, villain_pos)
        three_range = _3BET_RANGE.get(key)

        # 若無精確範圍，查最接近的
        if three_range is None:
            three_range = _fallback_3bet_range(hero_pos, villain_pos)

        three_freq = three_range.get(hand, 0.0) if three_range else 0.0
        three_freq = _adjust_range_for_stack(hand, three_freq, stack_bb, 'vs_open')

        # 跟注範圍：接近但不 3-bet 的手牌（BB 特殊處理）
        if hero_pos == 'BB':
            bb_range = _BB_DEFEND.get(villain_pos, BB_VS_CO)
            call_freq_raw = bb_range.get(hand, 0.0)
            mixed = MIXED_ACTIONS.get(f'bb_vs_{villain_pos.lower()}', {}).get(hand, (0.0, 0.0))
            call_freq = mixed[1] if mixed else call_freq_raw
            call_freq = _adjust_range_for_stack(hand, call_freq, stack_bb, 'vs_open')
        else:
            # IP 位置（BTN/CO/HJ）可跟注對手開牌
            ip_call_range = _IP_CALL.get((hero_pos, villain_pos), {})
            call_freq = ip_call_range.get(hand, 0.0)
            call_freq = _adjust_range_for_stack(hand, call_freq, stack_bb, 'vs_open')

        # 3-bet 尺寸
        if _pos_is_later(hero_pos, villain_pos):   # IP 3-bet
            three_size = round(open_size_bb * 3.0 + 1.0, 1)   # 3x + 1bb dead
        else:                                        # OOP 3-bet (BB/SB)
            three_size = round(open_size_bb * 3.5 + 1.5, 1)

        # 短籌碼：3-bet = jam
        if stack_bb <= 30:
            three_size = stack_bb
            action_name = '全推' if three_freq > 0.2 else '棄牌'
        else:
            action_name = '3-bet' if three_freq >= 0.3 else ('跟注' if call_freq >= 0.3 else '棄牌')

        # 決定主要行動
        if three_freq >= 0.5:
            action, action_f = '3-bet', three_freq
            alt_action, alt_f = '棄牌', 1 - three_freq
            r_size = three_size
            reason = _vs_open_reason(hand, hs, hero_pos, villain_pos, '3-bet', three_freq, three_size)
        elif three_freq >= 0.2:
            action, action_f = '3-bet', three_freq
            alt_action, alt_f = '棄牌', 1 - three_freq - call_freq
            r_size = three_size
            reason = f'混合策略：{three_freq:.0%} 3-bet，{call_freq:.0%} 跟注，其餘棄牌'
        elif call_freq >= 0.3:
            action, action_f = '跟注', call_freq
            alt_action, alt_f = '棄牌', 1 - call_freq
            r_size = 0.0
            reason = f'此手牌在 {hero_pos} vs {villain_pos} 以跟注為主（{call_freq:.0%}）'
        else:
            action, action_f = '棄牌', 1.0 - three_freq - call_freq
            alt_action, alt_f = '', 0.0
            r_size = 0.0
            reason = f'此手牌在 {hero_pos} vs {villain_pos} 不在 3-bet / 跟注範圍'

        key_hands = _top_hands(three_range or {}, n=8) if three_range else []

        return PreflopAdvice(
            hand=hand, hero_pos=hero_pos, villain_pos=villain_pos, situation='vs_open',
            stack_bb=stack_bb, action=action, action_freq=action_f,
            raise_size_bb=r_size, reasoning=reason,
            alt_action=alt_action, alt_freq=alt_f,
            in_range=(three_freq > 0 or call_freq > 0),
            hand_strength=hs, stack_note=s_note, key_hands=key_hands,
        )

    # ─────────────────────────────────────────────────────────────────
    # 3. 面對 3-bet（4-bet / 跟注 / 棄牌）
    # ─────────────────────────────────────────────────────────────────
    elif situation == 'vs_3bet':
        # VS3BET_4BET = 純 4-bet 手牌（AA/KK/AKs 等），優先查此表
        pure_4bet_freq = VS3BET_4BET.get(hand, 0.0)
        # VS3BET_CALL = 跟注或混合手牌，MIXED_ACTIONS 拆分了 4-bet/call 比例
        mixed = MIXED_ACTIONS.get('vs3bet_call', {}).get(hand, (0.0, 0.0))
        four_freq = max(pure_4bet_freq, mixed[0])
        call_freq = 0.0 if pure_4bet_freq >= 0.5 else mixed[1]
        four_freq = _adjust_range_for_stack(hand, four_freq, stack_bb, 'vs_3bet')
        call_freq = _adjust_range_for_stack(hand, call_freq, stack_bb, 'vs_3bet')

        # 4-bet 尺寸（約 2.2-2.5x 3-bet 注）
        assumed_3bet = open_size_bb * 3.5
        four_size = round(assumed_3bet * 2.3, 1)
        if stack_bb <= 40:
            four_size = stack_bb  # 4-bet = jam

        # 短籌碼大幅提高 4-bet 頻率（fold equity 更低，call 頻率更高）
        if stack_bb <= 30 and hs in ('premium', 'strong'):
            four_freq = min(1.0, four_freq + 0.3)
            call_freq = 0.0
            action, action_f = '全推', four_freq
            reason = f'短籌碼 ({stack_bb:.0f}BB)：{hs} 手牌面對 3-bet 直接全推'
        elif four_freq >= 0.5:
            action, action_f = '4-bet', four_freq
            reason = f'強牌 ({hs})，4-bet 至 {four_size:.1f}BB'
        elif call_freq >= 0.4:
            action, action_f = '跟注', call_freq
            four_size = 0.0
            reason = f'跟注 3-bet（{call_freq:.0%}）：{hs} 手牌有隱含賠率'
        elif four_freq >= 0.15:
            action, action_f = '4-bet', four_freq
            reason = f'混合：部分 4-bet 光注（{four_freq:.0%}），增加範圍均衡'
        else:
            action, action_f = '棄牌', max(0.0, 1 - four_freq - call_freq)
            four_size = 0.0
            reason = f'此手牌面對 3-bet 建議棄牌（4-bet={four_freq:.0%}, 跟注={call_freq:.0%}）'

        alt_action = '跟注' if (call_freq > 0.1 and action == '4-bet') else ''
        alt_freq   = call_freq if alt_action else 0.0

        key_hands = list(VS3BET_4BET.keys())[:8]

        return PreflopAdvice(
            hand=hand, hero_pos=hero_pos, villain_pos=villain_pos, situation='vs_3bet',
            stack_bb=stack_bb, action=action, action_freq=action_f,
            raise_size_bb=four_size if action in ('4-bet','全推') else 0.0,
            reasoning=reason,
            alt_action=alt_action, alt_freq=alt_freq,
            in_range=(four_freq > 0 or call_freq > 0),
            hand_strength=hs, stack_note=s_note, key_hands=key_hands,
        )

    # ─────────────────────────────────────────────────────────────────
    # 4. BB 防守（vs 各位置開牌）
    # ─────────────────────────────────────────────────────────────────
    else:  # bb_defense
        scenario_key = f'bb_vs_{villain_pos.lower()}'
        mixed = MIXED_ACTIONS.get(scenario_key, {}).get(hand, (0.0, 0.0))
        three_freq = mixed[0]
        call_freq  = mixed[1]
        three_freq = _adjust_range_for_stack(hand, three_freq, stack_bb, 'bb_defense')
        call_freq  = _adjust_range_for_stack(hand, call_freq,  stack_bb, 'bb_defense')

        three_size = round(open_size_bb * 3.5 + 1.0, 1)
        if stack_bb <= 30:
            three_size = stack_bb

        total_defend = three_freq + call_freq
        fold_freq = max(0.0, 1.0 - total_defend)

        if three_freq >= 0.5:
            action, action_f = '3-bet', three_freq
            reason = f'BB vs {villain_pos}：強牌 3-bet {three_freq:.0%}，尺寸 {three_size:.1f}BB'
        elif three_freq >= 0.2:
            action, action_f = '3-bet', three_freq
            reason = f'混合防守：3-bet {three_freq:.0%} + 跟注 {call_freq:.0%}'
        elif call_freq >= 0.3:
            action, action_f = '跟注', call_freq
            reason = f'BB 防守跟注（{call_freq:.0%}），獲得良好底池賠率'
        else:
            action, action_f = '棄牌', fold_freq
            reason = f'此手牌對 {villain_pos} 開牌不在 BB 防守範圍'

        alt_action = '跟注' if (call_freq > 0.15 and action == '3-bet') else ''
        alt_freq   = call_freq if alt_action else 0.0

        key_hands = _top_hands(_BB_DEFEND.get(villain_pos, BB_VS_CO), n=8)

        return PreflopAdvice(
            hand=hand, hero_pos='BB', villain_pos=villain_pos, situation='bb_defense',
            stack_bb=stack_bb, action=action, action_freq=action_f,
            raise_size_bb=three_size if action == '3-bet' else 0.0,
            reasoning=reason,
            alt_action=alt_action, alt_freq=alt_freq,
            in_range=(total_defend > 0),
            hand_strength=hs, stack_note=s_note, key_hands=key_hands,
        )


# ── 輔助函數 ─────────────────────────────────────────────────────────────────

def _top_hands(rng: Dict[str, float], n: int = 10) -> List[str]:
    """回傳範圍中頻率最高的前 N 個手牌。"""
    return [h for h, _ in sorted(rng.items(), key=lambda x: -x[1])][:n]


def _fallback_3bet_range(hero_pos: str, villain_pos: str) -> Optional[Dict]:
    """找最近似的 3-bet 範圍。"""
    vrank = _POS_RANK.get(villain_pos, 3)
    # 依照開牌者位置強度選最近的已定義場景
    if vrank <= 2:     # UTG 類
        return _3BET_RANGE.get(('BTN','UTG'), THREEBET_BTN_VS_UTG)
    if vrank <= 4:     # HJ 類
        return _3BET_RANGE.get(('BTN','HJ'), THREEBET_BTN_VS_HJ)
    return _3BET_RANGE.get(('BTN','CO'), THREEBET_BTN_VS_CO)


def _vs_open_reason(hand, hs, hero_pos, villain_pos, action, freq, size_bb) -> str:
    polarity = '純價值' if hs in ('premium', 'strong') else '光注詐唬'
    return (f'{hero_pos} vs {villain_pos} 開牌：{polarity} {action} '
            f'（頻率 {freq:.0%}，尺寸 {size_bb:.1f}BB）')


# ── 快速查詢：批次檢查多張手牌 ──────────────────────────────────────────────

def batch_advise(
    hands:       List[str],
    hero_pos:    str,
    villain_pos: str = '',
    situation:   str = 'auto',
    stack_bb:    float = 100.0,
) -> List[PreflopAdvice]:
    """批次查詢多張手牌的翻前建議。"""
    return [advise_preflop(h, hero_pos, villain_pos, situation, stack_bb) for h in hands]


def preflop_summary(adv: PreflopAdvice) -> str:
    """單行摘要，用於 overlay 顯示。"""
    size_str = f' → {adv.raise_size_bb:.1f}BB' if adv.raise_size_bb > 0 else ''
    return (f'翻前 [{adv.situation}] {adv.hand} @ {adv.hero_pos}  '
            f'→ {adv.action} {adv.action_freq:.0%}{size_str}  '
            f'{adv.reasoning[:40]}')
