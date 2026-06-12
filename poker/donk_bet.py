"""
主動無位置下注顧問 — Donk Bet / Probe Bet Advisor

現有翻後模組（barrel、bet_sizing、polarization）全站在「有位置的主動方」角度。
本模組補全另一半：跟注者/無位置方的主動下注策略。

兩種情境：
  1. Donk Bet（翻牌搶先下注）
     你在無位置（BB/SB/跟注早位），翻牌後搶在翻前主動方前面下注。
     GTO 中 donk bet 頻率很低（5-15%），但特定情境利潤顯著：
       a) 牌面對你的範圍有利（低牌面你比翻前開牌者有更多連張/低對）
       b) 強調利用的 exploitative donk（對手 C-bet 頻率過高時用來再加注）
       c) 有強牌但牌面太乾燥、難以讓對手跟注的情況

  2. Probe Bet（轉牌/河牌探測注）
     翻牌後對手過牌（或你過牌），現在你有機會在轉牌/河牌主動下注。
     比 donk bet 更常見（20-45%），因為對手過牌翻牌表示範圍較弱。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class DonkBetResult:
    bet_type:           str      # 'donk'/'probe'
    street:             str
    should_bet:         bool
    bet_freq:           float    # 建議下注頻率（0-1）
    sizing_pct:         float    # 建議注碼（底池比例）
    sizing_bb:          float    # 換算 BB 數
    rationale:          str      # 下注理由（若建議下注）
    check_reason:       str      # 過牌理由（若建議過牌）
    hand_category:      str      # 手牌分類（nuts/strong/medium/draw/weak）
    board_advantage:    str      # 'hero'/'villain'/'neutral'
    exploitative_note:  str      # 剝削性注意事項
    tips:               List[str] = field(default_factory=list)


# ── 牌面優勢判斷 ───────────────────────────────────────────────────────────────

_LOW_RANKS = {'2','3','4','5','6','7','8'}
_HIGH_RANKS = {'T','J','Q','K','A'}


def _board_advantage(
    community:       List[str],
    hero_pos:        str,        # 'oop'/'ip'
    villain_pos:     str,        # 開牌者位置 'BTN'/'CO'/'UTG'...
    street:          str,
) -> str:
    """
    判斷板面對哪方範圍有利。
    低牌面（2-8）通常對 BB/SB 有利（他們跟注了更多低連張）。
    高牌面（A/K/Q）通常對翻前開牌者（BTN/CO）有利。
    """
    if len(community) < 3:
        return 'neutral'

    flop3 = community[:3]
    ranks = [c[:-1].upper() for c in flop3]

    high_count = sum(1 for r in ranks if r in _HIGH_RANKS)
    low_count  = sum(1 for r in ranks if r in _LOW_RANKS)

    # 低牌面：BB 跟注了更多 2-8 連張
    if low_count >= 2 and high_count == 0:
        return 'hero' if hero_pos == 'oop' else 'villain'

    # 高牌面：開牌者範圍更多高牌
    if high_count >= 2:
        return 'villain' if hero_pos == 'oop' else 'hero'

    return 'neutral'


def _hand_category(equity: float, has_draw: bool = False) -> str:
    if equity >= 0.80: return 'nuts'
    if equity >= 0.65: return 'strong'
    if equity >= 0.50: return 'medium'
    if has_draw:       return 'draw'
    return 'weak'


# ── Donk Bet 分析 ─────────────────────────────────────────────────────────────

def analyze_donk(
    equity:           float,
    pot_bb:           float,
    eff_stack_bb:     float,
    community:        List[str],
    hero_pos:         str = 'bb',       # 'bb'/'sb'/'oop'
    villain_pos:      str = 'BTN',      # 翻前主動方位置
    villain_cbet_pct: float = 0.60,     # 對手 C-bet 頻率（從 HUD 取）
    has_draw:         bool = False,
    is_wet_board:     bool = False,
) -> DonkBetResult:
    """
    分析翻牌是否應該 donk bet。

    Args:
        equity:           英雄手牌勝率
        pot_bb:           翻牌底池（BB）
        eff_stack_bb:     有效籌碼
        community:        公牌
        hero_pos:         英雄位置（'bb'/'sb'/'oop'）
        villain_pos:      翻前開牌者位置
        villain_cbet_pct: 對手 C-bet 頻率（HUD 資料）
        has_draw:         是否有聽牌
        is_wet_board:     是否潮濕板面
    """
    spr = eff_stack_bb / pot_bb if pot_bb > 0 else 99
    hand_cat = _hand_category(equity, has_draw)
    board_adv = _board_advantage(community, 'oop', villain_pos, 'flop')

    # ── GTO donk bet 基礎頻率（相當低）────────────────────────────
    # GTO 中 donk bet 在大多數情況下很少（5-15%）
    base_freq = 0.08

    reasons    = []
    check_rsns = []

    # 規則 1：板面對英雄有利 → 可提高頻率
    if board_adv == 'hero':
        base_freq += 0.12
        reasons.append('低牌面對 BB 範圍有利，可使用 donk bet 保護範圍')

    # 規則 2：有強牌 → 少部分情況下 donk bet 可保護並建鍋
    if hand_cat == 'nuts':
        base_freq += 0.10
        reasons.append('超強牌：部分 donk bet 防止對手免費看牌')
    elif hand_cat == 'strong' and is_wet_board:
        base_freq += 0.08
        reasons.append('潮濕板面強牌：donk bet 保護並向對手要求決策')

    # 規則 3：剝削性調整——對手 C-bet 頻率過高時用 donk-raise
    # 若對手 C-bet > 70%，donk-check-raise 是有力武器
    exploitative = ''
    if villain_cbet_pct >= 0.70:
        exploitative = (f'對手 C-bet 頻率 {villain_cbet_pct:.0%} 過高！'
                        f'考慮 donk bet 再跟進，或 check-raise 陷阱')
    elif villain_cbet_pct <= 0.35:
        exploitative = f'對手 C-bet 低（{villain_cbet_pct:.0%}），過牌-等對手下注更佳'
        base_freq *= 0.5

    # 規則 4：有 draw 的 donk bet（半詐唬 donk）
    if has_draw and base_freq < 0.12:
        base_freq = max(base_freq, 0.10)
        reasons.append('聽牌 donk bet：半詐唬，有改善可能性')

    # 規則 5：低 SPR 更容易 donk
    if spr <= 3:
        base_freq = min(base_freq + 0.10, 0.60)
        reasons.append(f'SPR={spr:.1f} 低，接近 all-in 節奏，donk 合理')

    # 過牌理由
    if base_freq < 0.15:
        check_rsns.append('板面對對手範圍有利，讓對手 C-bet 再應對')
    if not reasons and hand_cat in ('medium', 'weak'):
        check_rsns.append(f'中等/弱牌（勝率{equity:.0%}），過牌控池較佳')
    if villain_cbet_pct <= 0.40:
        check_rsns.append(f'對手 C-bet 頻率低（{villain_cbet_pct:.0%}），過牌-跟注可能更優')

    should_bet = base_freq >= 0.18
    freq = min(round(base_freq, 2), 0.60)

    # 建議注碼
    if hand_cat in ('nuts', 'strong'):
        sizing = 0.67 if is_wet_board else 0.50
    elif has_draw:
        sizing = 0.50   # 半詐唬標準注
    elif board_adv == 'hero':
        sizing = 0.33   # 範圍優勢小注高頻
    else:
        sizing = 0.40

    sizing_bb = round(pot_bb * sizing, 1)

    tips = [
        'Donk bet 在 GTO 中使用頻率很低（5-15%），主要用於範圍優勢或剝削',
        '更常見的選擇：過牌-跟注（強牌或 draws），等對手 C-bet 後行動',
    ]
    if board_adv == 'hero':
        tips.append('低牌面 BB 有範圍優勢，這是 donk bet 最合理的情況')
    if villain_cbet_pct >= 0.70:
        tips.append('高 C-bet 對手更怕 check-raise——過牌陷阱也有效')

    return DonkBetResult(
        bet_type          = 'donk',
        street            = 'flop',
        should_bet        = should_bet,
        bet_freq          = freq,
        sizing_pct        = sizing,
        sizing_bb         = sizing_bb,
        rationale         = '；'.join(reasons) if reasons else '無強理由 donk bet',
        check_reason      = '；'.join(check_rsns) if check_rsns else '標準情況建議過牌',
        hand_category     = hand_cat,
        board_advantage   = board_adv,
        exploitative_note = exploitative,
        tips              = tips,
    )


# ── Probe Bet 分析 ────────────────────────────────────────────────────────────

def analyze_probe(
    equity:             float,
    pot_bb:             float,
    eff_stack_bb:       float,
    street:             str,              # 'turn'/'river'
    community:          List[str],
    hero_pos:           str = 'bb',
    villain_pos:        str = 'BTN',
    villain_checked:    bool = True,      # 對手是否在上一街過牌（probe 的前提）
    prev_street_action: str = 'check',    # 上一街的行動('check'/'bet')
    has_draw:           bool = False,
    runout_favorable:   bool = False,     # 新牌對英雄有利
) -> DonkBetResult:
    """
    分析轉牌/河牌是否應該 probe bet（對手過牌後的主動探測）。

    Probe bet 比 donk bet 更常用：
    - 翻牌後雙方過牌 → 轉牌 probe
    - 翻牌你過牌、對手也過牌 → 轉牌可以 probe
    - 對手翻牌過牌表示其範圍中等/弱，probe 有更好的折疊勝算

    Args:
        villain_checked:    對手是否在此街或上一街過牌（probe 的前提）
        prev_street_action: 上一街英雄的行動
        runout_favorable:   新牌是否對英雄有利（如完成聽牌）
    """
    if not villain_checked:
        # 不是 probe 情境（對手有主動下注）
        return DonkBetResult(
            bet_type='probe', street=street, should_bet=False, bet_freq=0.0,
            sizing_pct=0, sizing_bb=0,
            rationale='', check_reason='對手有主動下注，這不是探測注情境',
            hand_category=_hand_category(equity, has_draw),
            board_advantage='neutral', exploitative_note='', tips=[],
        )

    spr = eff_stack_bb / pot_bb if pot_bb > 0 else 99
    hand_cat = _hand_category(equity, has_draw)
    board_adv = _board_advantage(community, 'oop', villain_pos, street)

    # ── 基礎 probe bet 頻率 ──────────────────────────────────────
    # 對手翻牌過牌 → 範圍相對弱，可以更積極
    if street == 'turn':
        base_freq = 0.35
        street_zh = '轉牌'
    else:  # river
        base_freq = 0.28
        street_zh = '河牌'

    reasons    = []
    check_rsns = []

    # 手牌強度調整
    if hand_cat == 'nuts':
        base_freq = min(0.85, base_freq + 0.30)
        reasons.append(f'超強牌，{street_zh}探測取值')
    elif hand_cat == 'strong':
        base_freq = min(0.75, base_freq + 0.20)
        reasons.append(f'強牌，積極探測取值')
    elif hand_cat == 'medium':
        base_freq += 0.05
        reasons.append('中等牌力，探測並觀察反應')
    elif has_draw and street == 'turn':
        base_freq = min(0.55, base_freq + 0.15)
        reasons.append('聽牌半詐唬探測：可繼續 barrel 或完成後取值')
    elif hand_cat == 'weak':
        base_freq = max(0.10, base_freq - 0.15)
        check_rsns.append(f'弱牌（勝率{equity:.0%}），過牌保留 showdown value')

    # 新牌有利
    if runout_favorable:
        base_freq = min(0.85, base_freq + 0.15)
        reasons.append('有利 runout 完成手牌，積極探測')

    # 板面優勢
    if board_adv == 'hero':
        base_freq = min(0.80, base_freq + 0.08)
        reasons.append('板面對英雄範圍有利')

    # SPR 調整
    if spr <= 2:
        base_freq = min(0.90, base_freq + 0.10)
        reasons.append(f'SPR={spr:.1f} 低，接近全押節奏')

    # 河牌：過牌保留 bluff catch 價值
    if street == 'river' and hand_cat == 'medium':
        check_rsns.append('河牌中等強度：過牌-跟注可能更優（防止對手 raise）')

    should_bet = base_freq >= 0.30
    freq = min(round(base_freq, 2), 0.90)

    # 建議注碼
    if street == 'turn':
        if hand_cat in ('nuts', 'strong'):
            sizing = 0.60
        elif has_draw:
            sizing = 0.50
        else:
            sizing = 0.40
    else:  # river
        if hand_cat in ('nuts', 'strong'):
            sizing = 0.75   # 河牌大注極化
        elif hand_cat == 'medium':
            sizing = 0.40   # 薄薄取值
        else:
            sizing = 0.67   # 詐唬用大注

    sizing_bb = round(pot_bb * sizing, 1)

    exploitative = (
        f'對手{street_zh}過牌 → 其範圍移除了強牌，'
        f'你的 probe bet 有更高的折疊勝算'
    )

    tips = [
        f'{street_zh}雙方過牌後，probe bet 頻率建議 {freq:.0%}',
        '對手過牌暗示其範圍中等或在 check-raise 設陷',
        '謹防強牌過牌陷阱（尤其對手是 Nit/Trapper 類型）',
    ]

    return DonkBetResult(
        bet_type          = 'probe',
        street            = street_zh,
        should_bet        = should_bet,
        bet_freq          = freq,
        sizing_pct        = sizing,
        sizing_bb         = sizing_bb,
        rationale         = '；'.join(reasons) if reasons else '標準探測機會',
        check_reason      = '；'.join(check_rsns) if check_rsns else '',
        hand_category     = hand_cat,
        board_advantage   = board_adv,
        exploitative_note = exploitative,
        tips              = tips,
    )


# ── 摘要 ─────────────────────────────────────────────────────────────────────

def donk_summary(r: DonkBetResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    bet_type_zh = {'donk': 'Donk', 'probe': '探測注'}.get(r.bet_type, r.bet_type)
    if r.should_bet:
        return (f'{r.street} {bet_type_zh} {r.bet_freq:.0%}  '
                f'注碼 {r.sizing_pct:.0%} 底池 ({r.sizing_bb:.1f}BB)  '
                f'[{r.hand_category}]')
    else:
        return f'{r.street} 建議過牌：{r.check_reason[:30]}'


def donk_or_probe(
    equity:         float,
    pot_bb:         float,
    eff_stack_bb:   float,
    community:      List[str],
    street:         str,        # 'flop'/'turn'/'river'
    hero_pos:       str = 'bb',
    villain_pos:    str = 'BTN',
    villain_checked_prev: bool = False,   # 轉/河牌時：對手上街是否過牌
    villain_cbet_pct: float = 0.60,
    has_draw:       bool = False,
    runout_favorable: bool = False,
) -> DonkBetResult:
    """
    自動判斷是 donk 還是 probe 情境，回傳建議。
    """
    if street == 'flop':
        return analyze_donk(
            equity, pot_bb, eff_stack_bb, community,
            hero_pos, villain_pos, villain_cbet_pct, has_draw,
            is_wet_board=any(c[-1] for c in community[:3]),
        )
    else:
        return analyze_probe(
            equity, pot_bb, eff_stack_bb, street, community,
            hero_pos, villain_pos,
            villain_checked=villain_checked_prev,
            has_draw=has_draw,
            runout_favorable=runout_favorable,
        )
