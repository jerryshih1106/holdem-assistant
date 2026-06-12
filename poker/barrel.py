"""
Turn / River 續注（barrel）決策分析。

翻牌 C-bet 後，根據轉牌/河牌的牌面變化、位置、SPR、
手牌相對強度，建議是否繼續 barrel 及頻率。
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class BarrelResult:
    street:         str          # '轉牌' / '河牌'
    should_barrel:  bool
    barrel_freq:    float        # 建議 barrel 頻率 (0-1)
    sizing_pct:     float        # 建議注碼（底池比例）
    runout_type:    str          # 'blank'/'scare'/'improve'/'complete'
    runout_zh:      str          # 中文說明
    reasoning:      str


_RANK_ORDER = {
    'A':14,'K':13,'Q':12,'J':11,'T':10,
    '9':9,'8':8,'7':7,'6':6,'5':5,'4':4,'3':3,'2':2
}

_RUNOUT_ZH = {
    'blank':    '空白張（對範圍影響小）',
    'scare':    '恐嚇張（對手範圍改善）',
    'improve':  '有利張（我方範圍改善）',
    'complete': '聽牌完成（flush/straight）',
    'pair':     '板面配對',
}


def _rank(card: str) -> int:
    return _RANK_ORDER.get(card[:-1], 0)

def _suit(card: str) -> str:
    return card[-1]


def classify_runout(
    flop: List[str],
    new_card: str,
    hero_pos: str = 'BTN',
) -> Tuple[str, str]:
    """
    分析新牌（轉牌或河牌）對整體形勢的影響。
    回傳 (runout_type, description)
    """
    suits_on_board = [_suit(c) for c in flop]
    new_suit = _suit(new_card)
    new_rank = _rank(new_card)
    flop_ranks = sorted([_rank(c) for c in flop], reverse=True)

    # 同花聽牌完成
    suit_count = suits_on_board.count(new_suit)
    if suit_count >= 2:
        return 'complete', f'同花完成（{new_suit}）'

    # 順子完成（簡化：新牌填補連張空缺）
    all_ranks = sorted(set(flop_ranks + [new_rank]))
    for i in range(len(all_ranks) - 4):
        if all_ranks[i+4] - all_ranks[i] == 4:
            return 'complete', '順子完成'

    # 高牌 / 超牌（恐嚇張）
    board_top = max(flop_ranks)
    if new_rank > board_top and new_rank >= 11:  # J 以上
        scare_map = {14: 'A', 13: 'K', 12: 'Q', 11: 'J'}
        return 'scare', f'{scare_map[new_rank]} 超牌，對手可能 pair up'

    # 板面配對
    if new_rank in flop_ranks:
        return 'pair', f'板面配對（{new_card[:-1]}）'

    # 低連張
    min_rank = min(flop_ranks)
    if new_rank <= min_rank - 1 and new_rank >= 4:
        return 'blank', '低空白張，不改變局面'

    # 預設空白
    return 'blank', '空白張，利於開牌者（翻前主動）'


def analyze_barrel(
    hole:          List[str],
    flop:          List[str],
    new_card:      str,
    street:        str,          # 'turn' | 'river'
    pot_bb:        float,
    eff_stack_bb:  float,
    in_position:   bool = True,
    cbet_pct:      float = 0.5,  # 翻牌 C-bet 尺寸（底池比例）
    equity:        float = 0.5,  # 目前手牌勝率
) -> BarrelResult:
    """
    分析是否應該在轉牌/河牌繼續 barrel。

    Args:
        hole:          手牌
        flop:          翻牌三張
        new_card:      轉牌或河牌
        street:        'turn' / 'river'
        pot_bb:        跟注後底池（BB）
        eff_stack_bb:  有效籌碼
        in_position:   是否有位置
        cbet_pct:      上一街下注比例（用於計算底池）
        equity:        手牌勝率
    """
    street_zh = '轉牌' if street == 'turn' else '河牌'
    spr = eff_stack_bb / pot_bb if pot_bb > 0 else 99
    runout_type, runout_desc = classify_runout(flop, new_card)

    # ── 基礎 barrel 頻率 ─────────────────────────────────────
    base_freq = {
        'blank':    0.65 if in_position else 0.50,
        'scare':    0.35 if in_position else 0.25,
        'improve':  0.75 if in_position else 0.65,
        'complete': 0.40 if in_position else 0.30,
        'pair':     0.55 if in_position else 0.40,
    }.get(runout_type, 0.5)

    # 勝率調整
    if equity >= 0.65:
        base_freq = min(0.90, base_freq + 0.15)
    elif equity >= 0.50:
        base_freq = min(0.80, base_freq + 0.08)
    elif equity <= 0.30:
        base_freq = max(0.15, base_freq - 0.20)

    # 河牌頻率整體降低（更需要有理由繼續）
    if street == 'river':
        base_freq *= 0.85
        # 河牌低 SPR 更應全押
        if spr < 2:
            base_freq = min(0.90, base_freq + 0.15)

    # SPR 調整
    if spr < 1.5:
        base_freq = min(0.90, base_freq + 0.10)

    # ── 建議注碼 ─────────────────────────────────────────────
    if runout_type == 'complete':
        # 聽牌完成：小注探測或放棄
        sizing = 0.33 if equity >= 0.55 else 0.0
    elif street == 'river':
        if in_position:
            sizing = 0.75  # 河牌有位置極化大注
        else:
            sizing = 0.50
    elif runout_type in ('blank', 'improve'):
        sizing = 0.50 if in_position else 0.40
    else:
        sizing = 0.33  # 恐嚇張縮小注碼

    should_barrel = base_freq >= 0.40

    # ── 理由 ─────────────────────────────────────────────────
    reasons = []
    if runout_type == 'blank':
        reasons.append('空白張，範圍優勢維持')
    elif runout_type == 'improve':
        reasons.append('有利牌，加強注碼')
    elif runout_type == 'scare':
        reasons.append('恐嚇張，降低頻率但保持部分詐唬')
    elif runout_type == 'complete':
        reasons.append('聽牌完成，用強牌下注/弱牌放棄')
    elif runout_type == 'pair':
        reasons.append('板面配對，對開牌者有利')

    if not in_position:
        reasons.append('無位置，整體降低頻率')
    if spr < 2:
        reasons.append(f'SPR={spr:.1f} 低，接近 all-in 節奏')
    if equity >= 0.65:
        reasons.append(f'勝率高 ({int(equity*100)}%)，增加 barrel')

    return BarrelResult(
        street       = street_zh,
        should_barrel = should_barrel,
        barrel_freq  = round(base_freq, 2),
        sizing_pct   = sizing,
        runout_type  = runout_type,
        runout_zh    = _RUNOUT_ZH.get(runout_type, runout_desc),
        reasoning    = '；'.join(reasons) if reasons else '標準情況',
    )


def barrel_summary(result: BarrelResult) -> str:
    action = '繼注' if result.should_barrel else '放棄/小注'
    freq_str = f'{int(result.barrel_freq * 100)}%'
    size_str = f'注碼 {int(result.sizing_pct * 100)}% 底池' if result.sizing_pct > 0 else '查牌'
    return f'{result.street} {action} {freq_str}  {size_str}  [{result.runout_zh}]'
