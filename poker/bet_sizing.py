"""
GTO 下注尺寸建議。

根據街道、牌面紋理、位置（有無位置優勢）、SPR，
建議最佳注碼比例與對應的注碼 BB 數。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SizingOption:
    label:      str    # e.g. '半池'
    pct:        float  # 相對底池的比例 (0.5 = 半池)
    chips:      float  # 實際 BB 數
    use_case:   str    # 何時用這個注碼


@dataclass
class BetSizingResult:
    street:         str              # 翻牌/轉牌/河牌
    recommended:    SizingOption     # 首選
    alternatives:   List[SizingOption]
    cbet_freq:      float            # 建議 C-bet 頻率 (0-1)
    reasoning:      str


# ── 牌面紋理分類（簡化） ───────────────────────────────────────────

def _classify_texture(community: List[str]) -> str:
    """簡易牌面分類，回傳 'dry'/'semi_wet'/'wet'/'paired'。"""
    if len(community) < 3:
        return 'unknown'
    suits = [c[-1] for c in community[:3]]
    ranks = [c[:-1] for c in community]
    flush_draw = len(set(suits)) <= 2 if len(suits) == 3 else len(set(suits[:3])) <= 2
    paired = len(ranks) != len(set(ranks))

    RANK_ORDER = {'A':14,'K':13,'Q':12,'J':11,'T':10,
                  '9':9,'8':8,'7':7,'6':6,'5':5,'4':4,'3':3,'2':2}
    vals = sorted([RANK_ORDER.get(r, 0) for r in ranks[:3]], reverse=True)
    connected = (vals[0] - vals[2]) <= 4 if len(vals) >= 3 else False

    if paired:
        return 'paired'
    if flush_draw and connected:
        return 'wet'
    if flush_draw or connected:
        return 'semi_wet'
    return 'dry'


def suggest_bet_sizing(
    street:       str,           # 'flop'/'turn'/'river'
    pot_bb:       float,
    eff_stack_bb: float,
    in_position:  bool = True,
    community:    Optional[List[str]] = None,
    texture:      Optional[str] = None,   # 覆蓋自動分類
    is_aggressor: bool = True,            # 是否為翻前主動者
) -> BetSizingResult:
    """
    建議下注尺寸。

    Args:
        street:       'flop' / 'turn' / 'river'
        pot_bb:       目前底池大小（BB）
        eff_stack_bb: 有效籌碼（BB）
        in_position:  是否有位置優勢
        community:    公牌（用於牌面分類）
        texture:      手動指定牌面類型
        is_aggressor: 是否為翻前主動者（影響 C-bet 建議）
    """
    spr = eff_stack_bb / pot_bb if pot_bb > 0 else 99

    if texture is None and community:
        texture = _classify_texture(community)
    elif texture is None:
        texture = 'semi_wet'

    street_zh = {'flop': '翻牌', 'turn': '轉牌', 'river': '河牌'}.get(street, street)

    # ── 翻牌 ─────────────────────────────────────────────────────
    if street == 'flop':
        if texture == 'dry':
            rec_pct, cbet_freq = 0.33, 0.75
            rec_label, rec_use = '1/3 底池', '乾燥板面高頻小注，頻繁繼注，讓對手付出代價'
            alts = [
                SizingOption('半池', 0.5, round(pot_bb * 0.5, 1),
                             '有強牌/draw 時加大保護'),
            ]
        elif texture == 'wet':
            rec_pct, cbet_freq = 0.67, 0.45
            rec_label, rec_use = '2/3 底池', '潮濕板面低頻大注，保護強牌並賦予 draw 高昂代價'
            alts = [
                SizingOption('半池', 0.5, round(pot_bb * 0.5, 1),
                             '有 top pair 但不想嚇跑對手'),
                SizingOption('全池', 1.0, round(pot_bb, 1),
                             '極強牌（set/two pair），擔心牌面跑壞'),
            ]
        elif texture == 'paired':
            rec_pct, cbet_freq = 0.33, 0.65
            rec_label, rec_use = '1/3 底池', '配對板面通常對全範圍有利，小注探測'
            alts = [
                SizingOption('2/3 底池', 0.67, round(pot_bb * 0.67, 1),
                             '持有 trips/full house 時大注'),
            ]
        else:  # semi_wet
            rec_pct, cbet_freq = 0.5, 0.55
            rec_label, rec_use = '半池', '半潮濕板面標準注碼，平衡頻率'
            alts = [
                SizingOption('1/3 底池', 0.33, round(pot_bb * 0.33, 1),
                             '範圍優勢大時可降低注碼高頻下注'),
                SizingOption('2/3 底池', 0.67, round(pot_bb * 0.67, 1),
                             '有強聽牌或強牌時增大'),
            ]
        # 沒有位置：降低頻率，縮小尺寸
        if not in_position:
            cbet_freq *= 0.8
            rec_use += '（無位置：降低頻率）'

    # ── 轉牌 ─────────────────────────────────────────────────────
    elif street == 'turn':
        if texture in ('wet', 'semi_wet'):
            rec_pct, cbet_freq = 0.67, 0.45
            rec_label, rec_use = '2/3 底池', '轉牌聽牌完成風險高，強牌大注保護'
            alts = [
                SizingOption('半池', 0.5, round(pot_bb * 0.5, 1),
                             '持有中等強度牌，控池'),
                SizingOption('全池', 1.0, round(pot_bb, 1),
                             '超強牌希望讓 draw 付出最高代價'),
            ]
        else:
            rec_pct, cbet_freq = 0.5, 0.50
            rec_label, rec_use = '半池', '乾燥轉牌標準壓力注'
            alts = [
                SizingOption('1/3 底池', 0.33, round(pot_bb * 0.33, 1),
                             '純詐唬或有 showdown value，控制底池'),
                SizingOption('2/3 底池', 0.67, round(pot_bb * 0.67, 1),
                             '強牌或半詐唬補牌多'),
            ]
        if spr < 3:
            rec_pct = 1.0
            rec_label = '全池（SPR 低）'
            rec_use = 'SPR < 3，全押或接近全押最優'

    # ── 河牌 ─────────────────────────────────────────────────────
    else:  # river
        if spr < 1.5:
            rec_pct, cbet_freq = 1.0, 0.65
            rec_label, rec_use = '全押', 'SPR 極低，全押最大化 EV'
            alts = []
        elif in_position:
            rec_pct, cbet_freq = 0.75, 0.50
            rec_label, rec_use = '3/4 底池', '河牌有位置，極化注碼（強牌/詐唬皆用）'
            alts = [
                SizingOption('半池', 0.5, round(pot_bb * 0.5, 1),
                             '薄價值注：對手範圍廣，可能 call 更多'),
                SizingOption('全池', 1.0, round(pot_bb, 1),
                             '超強牌或純詐唬（最大極化）'),
                SizingOption('1/3 底池', 0.33, round(pot_bb * 0.33, 1),
                             '薄薄的 thin value，對手容易被嚇跑'),
            ]
        else:
            rec_pct, cbet_freq = 0.5, 0.40
            rec_label, rec_use = '半池', '無位置河牌，縮小注碼以薄薄取值'
            alts = [
                SizingOption('1/3 底池', 0.33, round(pot_bb * 0.33, 1),
                             'Blocking bet：防止對手大注'),
                SizingOption('2/3 底池', 0.67, round(pot_bb * 0.67, 1),
                             '超強牌確定被 call'),
            ]

    rec_chips = round(pot_bb * rec_pct, 1)
    recommended = SizingOption(rec_label, rec_pct, rec_chips, rec_use)

    # ── 理由 ─────────────────────────────────────────────────────
    pos_str = '有位置' if in_position else '無位置'
    tex_zh  = {'dry':'乾燥','semi_wet':'半潮濕','wet':'潮濕','paired':'配對'}.get(texture, texture)
    reasoning = (f'{street_zh}  {tex_zh}板面  {pos_str}  '
                 f'SPR={spr:.1f}  C-bet 建議頻率 {int(cbet_freq*100)}%')

    return BetSizingResult(
        street      = street_zh,
        recommended = recommended,
        alternatives = alts,
        cbet_freq   = round(cbet_freq, 2),
        reasoning   = reasoning,
    )


def sizing_summary(result: BetSizingResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    r = result.recommended
    return (f'{result.street}建議：{r.label} ({r.chips:.1f}BB)  '
            f'C-bet {int(result.cbet_freq*100)}%')
