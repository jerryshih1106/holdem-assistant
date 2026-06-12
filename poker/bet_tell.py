"""
對手下注尺寸讀牌（Villain Bet Sizing Tell Interpreter）

核心洞察：下注尺寸是對手範圍強度的明確信號
─────────────────────────────────────────────────────────────────────
尺寸                範圍特徵              最優應對策略
─────────────────────────────────────────────────────────────────────
超小（≤20%）       阻擊注/封牌注         廣泛跟注，不加注
                   封頂範圍，通常中等強度  對手避免面對大注
                   避免讓你加注
小（21-33%）       合併（merged）範圍     跟注範圍擴大
                   各種強度的牌           只用強牌加注
標準（34-60%）     均衡極化範圍           均衡跟注/棄牌
                   有強牌也有詐唬         標準 MDF
大（61-90%）       極化範圍               可考慮加注詐唬
                   要麼強牌要麼詐唬       接近 MDF 的折疊頻率
超池（>90%）       高度極化               關鍵：辨識對手是否平衡
                   要麼堅果要麼空氣       只跟注高勝率手牌
─────────────────────────────────────────────────────────────────────

GTO 支撐：
  - 小注（合併）：對手用中等強度手牌下注防止 equity 損失
    → 他們的範圍是封頂的（沒有最強牌）→ 你可以呼叫更廣
  - 大注（極化）：對手用強牌或詐唬下注最大化 EV
    → 你的弱牌應該折疊，強牌應該考慮加注
  - 超池：通常來自不平衡的魚（純強牌過大注）
    → 如果對手 VPIP 高且過大注，通常是強牌不是詐唬
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BetTellResult:
    # 注碼信息
    bet_bb:            float
    pot_bb:            float
    bet_ratio:         float    # bet / pot (e.g., 0.67 for 2/3 pot)
    size_category:     str      # 'blocker'/'small'/'standard'/'large'/'overbet'
    size_category_zh:  str

    # 範圍分析
    range_type:        str      # 'merged'/'polarized'/'highly_polar'/'capped'/'unknown'
    range_type_zh:     str
    range_notes:       List[str]  # 具體說明

    # 最優應對策略
    strategy:          str      # 'call_wide'/'standard'/'fold_or_raise'/'bluff_catch_only'
    strategy_zh:       str
    strategy_notes:    List[str]

    # 剝削建議（基於 VPIP）
    exploit_note:      str
    exploit_level:     str      # 'high'/'medium'/'low' (exploitability)

    # 單行摘要
    summary_zh:        str


def _categorize_size(ratio: float) -> tuple:
    """返回（size_category, size_category_zh）。"""
    if ratio <= 0.20:
        return 'blocker', f'阻擊注({ratio:.0%}底池)'
    elif ratio <= 0.33:
        return 'small', f'小注({ratio:.0%}底池)'
    elif ratio <= 0.60:
        return 'standard', f'標準注({ratio:.0%}底池)'
    elif ratio <= 0.90:
        return 'large', f'大注({ratio:.0%}底池)'
    else:
        return 'overbet', f'超池({ratio:.0%}底池)'


def interpret_bet_sizing(
    bet_bb:         float,
    pot_bb:         float,
    street:         str   = 'river',    # 'flop'/'turn'/'river'
    villain_vpip:   float = 0.28,       # 0-1
    villain_af:     float = 1.5,        # Aggression Factor
    is_multiway:    bool  = False,
    board_wet:      bool  = False,      # 牌面是否濕潤（聽牌多）
    villain_hands:  int   = 0,          # 樣本手數（少則不確定性高）
) -> BetTellResult:
    """
    解讀對手下注尺寸對其範圍的意義，並提供應對策略。

    Args:
        bet_bb:        對手下注金額（BB）
        pot_bb:        底池大小（BB，下注前）
        street:        當前街道
        villain_vpip:  對手 VPIP（0-1）
        villain_af:    對手 Aggression Factor（高 = 主動型）
        is_multiway:   是否多人底池（影響分析）
        board_wet:     牌面是否有聽牌（影響下注尺寸解讀）
        villain_hands: 樣本手數（少 = 數據不可靠）
    """
    ratio = bet_bb / max(pot_bb, 0.1)
    size_cat, size_cat_zh = _categorize_size(ratio)

    range_notes:    List[str] = []
    strategy_notes: List[str] = []

    # ── 範圍分析（基於尺寸 + 對手類型）──────────────────────────────────────

    if size_cat == 'blocker':
        range_type    = 'capped'
        range_type_zh = '封頂範圍'
        range_notes.append('對手通常沒有堅果牌（否則會下更大注碼）')
        range_notes.append('中等強度手牌：試圖廉價到達攤牌')
        range_notes.append('封牌注：控制底池大小，怕被加注')
        if villain_vpip >= 0.40:
            range_notes.append('魚的小注：可能是薄薄取值弱牌，範圍更廣泛')

    elif size_cat == 'small':
        range_type    = 'merged'
        range_type_zh = '合併範圍'
        range_notes.append('廣泛的各類強度手牌（不是兩極化）')
        range_notes.append('通常：頂對/中等強度牌/弱聽牌')
        if board_wet:
            range_notes.append('濕牌面小注：可能是聽牌下注保護')
        if street == 'river':
            range_notes.append('河牌小注：封頂（沒有頂強牌），通常是中等手牌')

    elif size_cat == 'standard':
        range_type    = 'balanced'
        range_type_zh = '均衡極化'
        range_notes.append('均衡的強牌 + 詐唬混合')
        range_notes.append('接近 GTO：既有強牌也有詐唬')
        if villain_af >= 2.5:
            range_notes.append('高 AF 對手：積極型，詐唬比例偏高')
        elif villain_af <= 0.8:
            range_notes.append('低 AF 對手：被動型，偏向取值為主')

    elif size_cat == 'large':
        range_type    = 'polarized'
        range_type_zh = '極化範圍'
        range_notes.append('主要是強牌或詐唬，弱中等牌很少')
        range_notes.append('GTO 建議：大注使範圍更兩極化')
        if villain_vpip >= 0.40:
            range_notes.append('魚的大注：通常偏向強牌（魚詐唬頻率不足）')
        if villain_vpip <= 0.22:
            range_notes.append('Nit/TAG 的大注：幾乎只有強牌，詐唬極少')

    else:  # overbet
        range_type    = 'highly_polar'
        range_type_zh = '高度極化'
        range_notes.append('要麼堅果要麼空氣（最兩極化的下注）')
        if villain_vpip >= 0.40:
            range_notes.append('魚的超池：高度不平衡，通常是強牌（極少空氣）')
            range_notes.append('警告：面對魚的超池，謹慎跟注！')
        else:
            range_notes.append('超池通常暗示：堅果取值 或 絕望詐唬')
            range_notes.append('GTO 跟注：只需要 >50% 勝率（alpha>50%）')

    # ── 策略建議（基於尺寸 + 對手類型 + 街道）──────────────────────────────

    if size_cat == 'blocker':
        strategy    = 'call_wide'
        strategy_zh = '廣泛跟注（範圍封頂）'
        strategy_notes.append('範圍封頂 → 跟注更多手牌，不怕被撞牌')
        strategy_notes.append('輕鬆加注：對手難以應對加注（他們不應有強牌）')
        strategy_notes.append('折疊門檻提高：只棄牌最弱的手牌')

    elif size_cat == 'small':
        strategy    = 'call_wide'
        strategy_zh = '偏廣泛跟注（合併範圍）'
        strategy_notes.append('對手範圍廣泛 → 你的邊緣手牌獲利空間更大')
        strategy_notes.append('用中等強度牌加注：他們通常折疊')
        if street == 'river':
            strategy_notes.append('河牌：呼叫所有顯示出勝率優勢的牌')

    elif size_cat == 'standard':
        strategy    = 'standard'
        strategy_zh = '均衡應對（標準 MDF）'
        strategy_notes.append('按照 MDF 防守：不過度折疊也不過度跟注')
        strategy_notes.append('用強牌加注，用弱牌折疊，中等牌跟注')

    elif size_cat == 'large':
        strategy    = 'fold_or_raise'
        strategy_zh = '折疊或加注（避免平跟）'
        strategy_notes.append('極化範圍 → 平跟是最差選擇（讓對手錯誤地實現股份）')
        strategy_notes.append('強牌：加注取值（或再加注詐唬對手的詐唬）')
        strategy_notes.append('弱牌：果斷棄牌（MDF 更嚴格）')
        if villain_vpip >= 0.40:
            strategy_notes.append('魚的大注 → 跟注門檻提高，他們詐唬頻率不足')

    else:  # overbet
        strategy    = 'bluff_catch_only'
        strategy_zh = '只用頂強牌跟注/接詐唬'
        strategy_notes.append('超池需要 >50% 勝率才能跟注（alpha高）')
        strategy_notes.append('識別對手是否不平衡：魚的超池 = 強牌居多')
        if villain_vpip >= 0.40:
            strategy_notes.append('魚超池：勝率需要 ≥60% 才值得跟注')
        else:
            strategy_notes.append('均衡對手超池：按照 pot odds 跟注，不猜測')

    # ── 剝削建議 ─────────────────────────────────────────────────────────────

    if villain_hands < 15:
        exploit_note  = f'樣本不足（{villain_hands}手）：讀牌可信度低，按預設應對'
        exploit_level = 'low'
    elif villain_vpip >= 0.45 and size_cat == 'overbet':
        exploit_note  = f'魚({villain_vpip:.0%}VPIP)超池 → 直接棄牌除非強牌'
        exploit_level = 'high'
    elif villain_vpip >= 0.40 and size_cat in ('large', 'overbet'):
        exploit_note  = f'呼叫站大注 → 比 GTO 更嚴格跟注（他們詐唬不足）'
        exploit_level = 'high'
    elif villain_vpip <= 0.20 and size_cat in ('large', 'overbet'):
        exploit_note  = f'Nit 大注 → 幾乎只有強牌，建議棄牌除非頂強牌'
        exploit_level = 'high'
    elif villain_af <= 0.8 and size_cat == 'standard':
        exploit_note  = f'被動型(AF={villain_af:.1f})標準注 → 偏取值，降低詐唬抓捕頻率'
        exploit_level = 'medium'
    elif villain_af >= 2.5 and size_cat in ('small', 'standard'):
        exploit_note  = f'主動型(AF={villain_af:.1f}) → 詐唬比例偏高，可適當跟注更廣'
        exploit_level = 'medium'
    else:
        exploit_note  = '均衡/標準應對，按 MDF 防守'
        exploit_level = 'low'

    # ── 多人底池調整 ─────────────────────────────────────────────────────────

    if is_multiway:
        range_notes.append('多人底池：下注強度更可信（其他玩家也在評估）')
        strategy_notes.append('多人底池：大幅提高跟注門檻（需要更好的手牌）')

    # ── 摘要行 ───────────────────────────────────────────────────────────────

    summary_zh = (
        f'[讀牌] {size_cat_zh}→{range_type_zh}  '
        f'策略:{strategy_zh[:10]}  {exploit_note[:25]}'
    )[:85]

    return BetTellResult(
        bet_bb           = bet_bb,
        pot_bb           = pot_bb,
        bet_ratio        = round(ratio, 3),
        size_category    = size_cat,
        size_category_zh = size_cat_zh,
        range_type       = range_type,
        range_type_zh    = range_type_zh,
        range_notes      = range_notes,
        strategy         = strategy,
        strategy_zh      = strategy_zh,
        strategy_notes   = strategy_notes,
        exploit_note     = exploit_note,
        exploit_level    = exploit_level,
        summary_zh       = summary_zh,
    )


def bet_tell_summary(r: BetTellResult) -> str:
    """單行 overlay 摘要（最多 85 字）。"""
    return r.summary_zh[:85]
