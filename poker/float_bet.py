"""
浮注/延遲 C-bet 分析器 (Float Bet / Delayed Aggression Analyzer)

場景：
  翻牌：對手 C-bet，英雄有位置（IP）跟注
  轉牌：對手過牌（check）→ 英雄是否應該下注？

為什麼 float bet 是最高 EV 的翻後操作之一：
  1. 對手 C-bet 頻率越高，他們的過牌範圍越弱（大量詐唬已在翻牌下注）
  2. 被動對手過牌轉牌通常代表放棄，而非慢打
  3. IP 英雄可以用任何對牌面有利的轉牌作為攻擊機會
  4. 轉牌過牌讓英雄的下注包含取值 + 詐唬，最難應對

關鍵變數：
  villain_cbet_pct：對手 C-bet 頻率
    高（>= 70%）：過牌範圍更弱 → 更適合 float
    低（<= 40%）：過牌範圍更強 → 不適合 float

  villain_af：對手翻後激進因子
    低（<= 0.8）：給予壓力後容易棄牌
    高（>= 2.5）：可能 check-raise

  turn_card_type：轉牌性質
    blank（空白）：  對手範圍未改善 → 最適合 float
    scare（恐嚇）：  表面看起來對對手有利，但實際上對手也不敢 C-bet 轉牌
    improve（改善）：英雄摸牌 → 不再是純 float，變成有價值的半詐唬/取值

  hero_equity：轉牌勝率
    高（>= 0.60）：取值注，兼具保護意義
    中（0.35-0.60）：半詐唬，equity 作為後盾
    低（< 0.35）：純詐唬，需要高折疊勝算

Float 注碼：
  大多數情況：50-70% pot（不需要太大，對手通常在此點已放棄）
  半詐唬（有聽牌）：65-80% pot（需要足夠壓力讓對手不利跟注）
  對手 AF 高（可能 check-raise）：55% pot（降低被 CR 的風險）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class FloatBetResult:
    # 決策
    should_float_bet: bool
    float_frequency:  float    # 建議下注頻率 (0-1)
    sizing_pct:       float    # 建議注碼（底池比例）
    sizing_bb:        float    # 換算 BB

    # 分析
    float_type:       str      # 'value'/'semibluff'/'pure_float'/'check_back'
    float_type_zh:    str

    villain_weakness: float    # 0-1：對手過牌範圍有多弱（越高越適合 float）
    board_supports:   bool     # 轉牌對 float 是否有利

    # 風險
    check_raise_risk: str      # 'low'/'medium'/'high'
    cr_risk_zh:       str

    # 詳細說明
    reasoning:        str
    tips:             List[str]
    summary_zh:       str


_FLOAT_TYPE_ZH = {
    'value':       '取值注（主動取值）',
    'semibluff':   '半詐唬（聽牌 + 折疊勝算）',
    'pure_float':  '純浮注（依賴折疊勝算）',
    'check_back':  '過牌（float 條件不佳）',
}

_CR_RISK_ZH = {
    'low':    '低加注風險',
    'medium': '中等加注風險',
    'high':   '高加注風險（小心 check-raise）',
}


def _villain_weakness_score(
    villain_cbet_pct: float,   # 0-1
    villain_af:       float,
    turn_card_type:   str,     # 'blank'/'scare'/'improve'/'pair'/'complete'
) -> float:
    """
    Estimate how weak villain's check range is (0=strong, 1=very weak).
    High cbet_pct means more bluffs are in flop bet range → checking range is weak.
    """
    score = 0.0

    # C-bet frequency: main indicator of check range weakness
    if villain_cbet_pct >= 0.75:
        score += 0.45    # heavy c-bettor → very weak checking range
    elif villain_cbet_pct >= 0.60:
        score += 0.30
    elif villain_cbet_pct >= 0.45:
        score += 0.15
    else:
        score += 0.05    # tight c-bettor → checking range includes strong hands

    # AF: passive villains give up more readily
    if villain_af <= 0.8:
        score += 0.20
    elif villain_af <= 1.5:
        score += 0.10
    elif villain_af >= 2.5:
        score -= 0.10    # aggressive villain checks strong hands too

    # Turn card: blank helps (villain's range didn't improve)
    if turn_card_type == 'blank':
        score += 0.15
    elif turn_card_type in ('complete', 'pair'):
        score -= 0.15    # these boards hit villain's checking range more
    elif turn_card_type == 'scare':
        score += 0.05    # scare cards often help IP float (villain afraid too)

    return round(min(1.0, max(0.0, score)), 2)


def analyze_float_bet(
    villain_cbet_pct:  float  = 0.65,    # 對手 C-bet 頻率 (0-1)
    villain_af:        float  = 1.5,     # 翻後激進因子
    turn_card_type:    str    = 'blank', # 'blank'/'scare'/'improve'/'pair'/'complete'
    hero_equity:       float  = 0.40,    # 轉牌英雄勝率 (0-1)
    pot_bb:            float  = 20.0,    # 底池 BB
    eff_stack_bb:      float  = 80.0,    # 有效籌碼 BB
    hero_has_draw:     bool   = False,   # 英雄是否有聽牌
    n_opponents:       int    = 1,       # 對手數量（需 1 才適合 float）
    villain_hands:     int    = 0,       # HUD 手牌數
) -> FloatBetResult:
    """
    Analyze whether hero should float bet the turn after villain checked.

    This is called when:
    - Hero is IP (has position)
    - Hero called villain's flop c-bet
    - Turn came and villain checked
    - Hero must decide: bet or check?

    Args:
        villain_cbet_pct: Villain's c-bet frequency (0-1 decimal, e.g. 0.65)
        villain_af:        Villain's aggression factor from HUD
        turn_card_type:    Nature of the turn card (blank/scare/improve/pair/complete)
        hero_equity:       Hero's current win probability (0-1)
        pot_bb:            Current pot in BB
        eff_stack_bb:      Effective stack in BB
        hero_has_draw:     True if hero has a draw (flush/straight)
        n_opponents:       Number of opponents (float bet only works HU or 2-way)
        villain_hands:     HUD sample size (low = uncertain)
    """
    tips: List[str] = []
    spr = eff_stack_bb / max(pot_bb, 1)

    # ── Multiway: float bet rarely works with 2+ opponents ───────────────────
    if n_opponents >= 2:
        return FloatBetResult(
            should_float_bet = False,
            float_frequency  = 0.05,
            sizing_pct       = 0.0,
            sizing_bb        = 0.0,
            float_type       = 'check_back',
            float_type_zh    = _FLOAT_TYPE_ZH['check_back'],
            villain_weakness = 0.1,
            board_supports   = False,
            check_raise_risk = 'high',
            cr_risk_zh       = _CR_RISK_ZH['high'],
            reasoning        = f'多人底池（{n_opponents}人）：浮注成功率極低，建議過牌保留手牌價值',
            tips             = ['多人底池不適合純詐唬浮注', '若手牌強度高，可考慮取值注'],
            summary_zh       = '[浮注] 多人底池：建議過牌',
        )

    # ── Assess villain weakness ────────────────────────────────────────────────
    weakness = _villain_weakness_score(villain_cbet_pct, villain_af, turn_card_type)

    # ── Determine float type and base frequency ────────────────────────────────
    if hero_equity >= 0.60:
        float_type   = 'value'
        base_freq    = 0.85     # strong hand: almost always bet for value
        base_size    = 0.65
    elif hero_has_draw or hero_equity >= 0.40:
        float_type   = 'semibluff'
        base_freq    = 0.55     # semi-bluff: mostly bet
        base_size    = 0.70
    else:
        float_type   = 'pure_float'
        base_freq    = 0.35     # pure float: depends on fold equity
        base_size    = 0.55

    # ── Adjust frequency based on villain weakness ─────────────────────────────
    freq = base_freq + (weakness - 0.4) * 0.60     # center around 0.4 weakness
    # Direct adjustments
    if villain_cbet_pct >= 0.75:
        tips.append(f'對手C-bet頻率{villain_cbet_pct:.0%}極高 → 過牌範圍弱，浮注+')
    elif villain_cbet_pct <= 0.40:
        freq -= 0.15
        tips.append(f'對手C-bet頻率{villain_cbet_pct:.0%}偏低 → 過牌可能是強牌慢打，謹慎浮注')
    if villain_af <= 0.8:
        tips.append(f'對手AF={villain_af:.1f}偏低 → 給予壓力後易棄牌，積極浮注')
    elif villain_af >= 2.5:
        freq -= 0.10
        tips.append(f'對手AF={villain_af:.1f}高 → 可能 check-raise，縮小浮注頻率')

    if turn_card_type == 'blank':
        tips.append('空白轉牌：對手範圍未改善，最適合浮注')
    elif turn_card_type in ('complete', 'pair'):
        freq -= 0.15
        tips.append('危險轉牌：考慮過牌，對手可能命中強牌')
    elif turn_card_type == 'improve' or hero_has_draw:
        freq += 0.10
        tips.append('轉牌改善英雄手牌/聽牌：浮注同時有牌力後盾')

    if villain_hands < 20 and villain_hands > 0:
        tips.append(f'HUD樣本{villain_hands}手偏少，對手特徵不確定')
    elif villain_hands == 0:
        tips.append('無HUD資料：使用保守估計')

    # Very shallow stack: check back to avoid bad SPR
    if spr < 2:
        freq -= 0.20
        tips.append(f'SPR={spr:.1f}低，避免浮注深陷承諾')

    freq = round(max(0.05, min(0.95, freq)), 2)

    # ── Sizing ─────────────────────────────────────────────────────────────────
    # Increase size if villain AF is low (they won't check-raise much)
    size_pct = base_size
    if villain_af >= 2.5:
        size_pct = max(0.45, size_pct - 0.10)    # smaller to minimize CR loss
    if float_type == 'value' and hero_equity >= 0.72:
        size_pct = min(0.85, size_pct + 0.15)    # big sizing to extract value
    if turn_card_type == 'improve' and hero_has_draw:
        size_pct = min(0.80, size_pct + 0.10)    # charge draws

    size_pct = round(size_pct, 2)
    size_bb  = round(pot_bb * size_pct, 1)

    # ── Should float bet? ──────────────────────────────────────────────────────
    should_bet = (freq >= 0.30 and weakness >= 0.25)

    if float_type == 'value':
        should_bet = True       # always bet value hands
    elif float_type == 'check_back':
        should_bet = False

    # ── Check-raise risk ──────────────────────────────────────────────────────
    if villain_af >= 2.5 or villain_cbet_pct <= 0.40:
        cr_risk = 'high'
    elif villain_af >= 1.8:
        cr_risk = 'medium'
    else:
        cr_risk = 'low'

    # ── Board supports float? ─────────────────────────────────────────────────
    board_supports = (turn_card_type == 'blank' and weakness >= 0.30)

    # ── Reasoning ─────────────────────────────────────────────────────────────
    if not should_bet:
        reasoning = (
            f'浮注條件不佳（對手過牌範圍弱點分 {weakness:.0%}，低於門檻）。'
            f'建議過牌，保留 showdown value 或避免被 check-raise'
        )
    else:
        float_label = _FLOAT_TYPE_ZH[float_type]
        reasoning = (
            f'{float_label}：對手C-bet {villain_cbet_pct:.0%} → 過牌範圍弱點 {weakness:.0%}。'
            f'建議 {freq:.0%} 頻率下注 {size_pct:.0%} 底池 ({size_bb:.0f}BB)。'
        )

    # ── Summary ────────────────────────────────────────────────────────────────
    if should_bet:
        summary_zh = (
            f'[浮注] {_FLOAT_TYPE_ZH[float_type][:8]}  '
            f'{freq:.0%}頻率  {size_pct:.0%}pot={size_bb:.0f}BB  '
            f'{cr_risk_zh_short(cr_risk)}'
        )[:85]
    else:
        summary_zh = f'[浮注] 過牌（折疊勝算不足，弱點分={weakness:.0%}）'

    return FloatBetResult(
        should_float_bet = should_bet,
        float_frequency  = freq,
        sizing_pct       = size_pct,
        sizing_bb        = size_bb,
        float_type       = float_type if should_bet else 'check_back',
        float_type_zh    = _FLOAT_TYPE_ZH[float_type if should_bet else 'check_back'],
        villain_weakness = weakness,
        board_supports   = board_supports,
        check_raise_risk = cr_risk,
        cr_risk_zh       = _CR_RISK_ZH[cr_risk],
        reasoning        = reasoning,
        tips             = tips,
        summary_zh       = summary_zh,
    )


def cr_risk_zh_short(level: str) -> str:
    m = {'low': 'CR風險低', 'medium': 'CR風險中', 'high': 'CR風險高'}
    return m.get(level, '')


def float_bet_summary(r: FloatBetResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
