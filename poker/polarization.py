"""
河牌極化分析（Polarization Checker）。

基於 GTO 原理：
  alpha = 下注額 / (底池 + 下注額)  → 對手跟注的最低要求
  GTO 均衡下，詐唬頻率 = alpha，價值頻率 = 1 - alpha
  詐唬:價值 = alpha : (1-alpha)

用來檢查你的河牌下注範圍是否符合 GTO 平衡，
並提示你該有多少詐唬組合。
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PolarizationResult:
    pot_bb:          float
    bet_bb:          float
    alpha:           float   # 需要多少組合是詐唬（0-1）
    bluff_pct:       float   # 詐唬佔下注範圍的理想比例
    value_pct:       float   # 價值佔下注範圍的理想比例
    bluff_to_value:  str     # "1:2.5" 格式
    status:          str     # 'balanced'/'over_bluff'/'under_bluff'/'unknown'
    advice:          str
    example_bluffs:  List[str]   # 範例詐唬手牌
    example_values:  List[str]   # 範例價值手牌


_BLUFF_EXAMPLES = {
    # 依不同河牌注碼給出典型詐唬牌型
    'polarized': ['漏牌聽牌（未成順/同花）', '頂對弱踢腳', '底對'],
    'merged':    ['中等強度牌（thin value）', '底對', '弱頂對'],
}

_VALUE_EXAMPLES = [
    '頂對強踢腳', '兩對', '暗三條', '順子', '同花', 'Full House', '四條',
]


def check_polarization(
    pot_bb:          float,
    bet_bb:          float,
    num_value_combos: Optional[int] = None,   # 實際價值組合數（可省略）
    num_bluff_combos: Optional[int] = None,   # 實際詐唬組合數（可省略）
    community:       Optional[List[str]] = None,
) -> PolarizationResult:
    """
    分析河牌下注的詐唬/價值平衡。

    Args:
        pot_bb:            底池大小（BB）
        bet_bb:            下注大小（BB）
        num_value_combos:  你的實際價值組合數
        num_bluff_combos:  你的實際詐唬組合數
        community:         公牌（用於推算典型牌型）
    """
    if pot_bb <= 0 or bet_bb <= 0:
        return PolarizationResult(
            pot_bb=pot_bb, bet_bb=bet_bb,
            alpha=0, bluff_pct=0, value_pct=1,
            bluff_to_value='N/A', status='unknown',
            advice='輸入底池和下注金額以計算',
            example_bluffs=[], example_values=[],
        )

    # alpha = 讓對手無差異需要的詐唬比例
    alpha = bet_bb / (pot_bb + bet_bb)
    bluff_pct  = alpha
    value_pct  = 1 - alpha

    # 詐唬:價值比
    if value_pct > 0:
        ratio = bluff_pct / value_pct
        bluff_to_value = f'1:{round(1/ratio, 1)}' if ratio > 0 else '0:∞'
    else:
        bluff_to_value = '∞:1'

    # 判斷當前狀態（若有具體組合數）
    status = 'unknown'
    advice_parts = []

    if num_value_combos is not None and num_bluff_combos is not None:
        total = num_value_combos + num_bluff_combos
        if total > 0:
            actual_bluff_pct = num_bluff_combos / total
            if actual_bluff_pct > bluff_pct + 0.08:
                status = 'over_bluff'
                excess = num_bluff_combos - round(num_value_combos * ratio)
                advice_parts.append(
                    f'過度詐唬！實際詐唬 {int(actual_bluff_pct*100)}% > GTO {int(bluff_pct*100)}%，'
                    f'減少約 {excess} 個詐唬組合'
                )
            elif actual_bluff_pct < bluff_pct - 0.08:
                status = 'under_bluff'
                deficit = round(num_value_combos * ratio) - num_bluff_combos
                advice_parts.append(
                    f'詐唬不足！實際詐唬 {int(actual_bluff_pct*100)}% < GTO {int(bluff_pct*100)}%，'
                    f'可增加約 {deficit} 個詐唬組合'
                )
            else:
                status = 'balanced'
                advice_parts.append('詐唬/價值比例接近 GTO 均衡')
    else:
        advice_parts.append(
            f'GTO 均衡：每 {round(1/ratio, 1) if ratio > 0 else "∞"} 個價值組合配 1 個詐唬'
        )

    # 根據注碼大小給出建議
    if bet_bb / pot_bb >= 0.8:
        advice_parts.append(f'大注（{int(bet_bb/pot_bb*100)}% 底池）→ 極化：只用超強牌和純詐唬')
        bluff_type = 'polarized'
    elif bet_bb / pot_bb >= 0.4:
        advice_parts.append(f'中注（{int(bet_bb/pot_bb*100)}% 底池）→ 半極化：可加入 thin value')
        bluff_type = 'polarized'
    else:
        advice_parts.append(f'小注（{int(bet_bb/pot_bb*100)}% 底池）→ 合併：用廣泛薄薄取值範圍')
        bluff_type = 'merged'

    # 計算對手需要的跟注頻率
    opp_mdf = 1 - alpha
    advice_parts.append(f'對手 MDF={int(opp_mdf*100)}%（需跟注 {int(opp_mdf*100)}% 才能防止純詐唬盈利）')

    return PolarizationResult(
        pot_bb          = pot_bb,
        bet_bb          = bet_bb,
        alpha           = round(alpha, 3),
        bluff_pct       = round(bluff_pct, 3),
        value_pct       = round(value_pct, 3),
        bluff_to_value  = bluff_to_value,
        status          = status,
        advice          = '  |  '.join(advice_parts),
        example_bluffs  = _BLUFF_EXAMPLES.get(bluff_type, []),
        example_values  = _VALUE_EXAMPLES[:4],
    )


def polarization_summary(result: PolarizationResult) -> str:
    """單行摘要。"""
    status_icon = {
        'balanced':    '✓ 均衡',
        'over_bluff':  '⚠ 過度詐唬',
        'under_bluff': '⚠ 詐唬不足',
        'unknown':     '',
    }.get(result.status, '')
    return (
        f'詐唬 {int(result.bluff_pct*100)}%  價值 {int(result.value_pct*100)}%  '
        f'比例 {result.bluff_to_value}  {status_icon}'
    )
